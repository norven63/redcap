#!/usr/bin/env bash
# shellcheck shell=bash
# Shared helpers for RedCap .dev-task.md parsing.

if [[ "${_REDCAP_DEV_TASK_SH:-0}" == "1" ]]; then
    return 0 2>/dev/null || exit 0
fi
_REDCAP_DEV_TASK_SH=1

redcap_dev_task_default_file() {
    local script_dir root

    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    root="$(cd "$script_dir/../.." && pwd)"
    printf '%s/.dev-task.md\n' "$root"
}

redcap_dev_task_resolve_file() {
    local task_file="${1:-}"

    if [[ -n "$task_file" ]]; then
        if [[ "$task_file" = /* ]]; then
            printf '%s\n' "$task_file"
        else
            printf '%s/%s\n' "$PWD" "$task_file"
        fi
        return 0
    fi

    redcap_dev_task_default_file
}

redcap_dev_task_validate_path_component() {
    local value="${1:-}"

    [[ -n "$value" ]] || return 1
    [[ "$value" =~ ^[A-Za-z0-9._-]+$ ]] || return 1
    return 0
}

redcap_dev_task_extract_section() {
    local task_file="$1"
    local heading_prefix="$2"

    python3 - "$task_file" "$heading_prefix" <<'PY'
import pathlib
import sys

task_file = pathlib.Path(sys.argv[1])
heading_prefix = sys.argv[2]
if not task_file.is_file():
    sys.exit(1)

text = task_file.read_text(encoding="utf-8")
capture = False
buffer = []
for raw_line in text.splitlines():
    line = raw_line.rstrip("\n")
    if line.startswith("## "):
        heading = line[3:].strip()
        if capture:
            break
        if heading.startswith(heading_prefix):
            capture = True
            continue
    if capture:
        buffer.append(line)

content = "\n".join(buffer).strip()
if content:
    print(content)
PY
}

redcap_dev_task_extract_first_section() {
    local task_file="$1"
    shift
    local heading_prefix section=""

    for heading_prefix in "$@"; do
        section=$(redcap_dev_task_extract_section "$task_file" "$heading_prefix" 2>/dev/null || true)
        if [[ -n "$section" ]]; then
            printf '%s\n' "$section"
            return 0
        fi
    done

    return 1
}

redcap_dev_task_metadata_section() {
    local task_file="$1"

    redcap_dev_task_extract_first_section "$task_file" "控制面元数据" "Canonical Metadata"
}

redcap_dev_task_extract_kv() {
    local task_file="$1"
    local key="$2"
    local section=""

    section=$(redcap_dev_task_metadata_section "$task_file") || return 1
    python3 - "$key" "$section" <<'PY'
import re
import sys

key = sys.argv[1]
text = sys.argv[2]
pattern = re.compile(rf"^{re.escape(key)}:\s*(.*?)\s*$", re.MULTILINE)
match = pattern.search(text)
if match:
    print(match.group(1))
PY
}

redcap_dev_task_list_bullets() {
    local task_file="$1"
    local heading_prefix="$2"
    local section=""

    section=$(redcap_dev_task_extract_first_section "$task_file" "$heading_prefix") || return 1
    python3 - "$section" <<'PY'
import sys

for raw_line in sys.argv[1].splitlines():
    line = raw_line.strip()
    if line.startswith("- "):
        print(line[2:].strip())
PY
}

redcap_dev_task_confirmed_hash() {
    local task_file="$1"
    local section=""

    section=$(redcap_dev_task_extract_section "$task_file" "已确认需求") || return 1
    [[ -n "$section" ]] || return 1
    python3 - "$section" <<'PY'
import hashlib
import sys

print(hashlib.sha256(sys.argv[1].encode("utf-8")).hexdigest())
PY
}
