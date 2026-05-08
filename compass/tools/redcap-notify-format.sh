#!/usr/bin/env bash
# 用途：运行时与收尾脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#runtime-and-closeout

redcap_notify_flatten_field() {
    printf '%s' "${1:-}" | tr '\n' ' ' | sed -E 's/[[:space:]]+/ /g; s/^ //; s/ $//'
}

redcap_notify_commit_count() {
    local commit_log="${1:-}"
    if [[ -z "$commit_log" || "$commit_log" == "(无法获取)" ]]; then
        echo "0"
        return 0
    fi
    printf '%s\n' "$commit_log" | awk 'NF {count++} END {print count+0}'
}

redcap_notify_latest_commit() {
    local commit_log="${1:-}"
    if [[ -z "$commit_log" || "$commit_log" == "(无法获取)" ]]; then
        return 0
    fi
    printf '%s\n' "$commit_log" | awk 'NF {print; exit}'
}

redcap_notify_commit_bullets() {
    local commit_log="${1:-}"
    if [[ -z "$commit_log" || "$commit_log" == "(无法获取)" ]]; then
        return 0
    fi
    printf '%s\n' "$commit_log" | awk 'NF {print "- " $0}'
}

redcap_notify_first_report_ref() {
    local report_ref="${1:-}"
    printf '%s\n' "$report_ref" | awk 'NF {print; exit}'
}

redcap_notify_resolve_report_path() {
    local project_root="${1:-}"
    local report_ref="${2:-}"
    local first_line=""

    first_line=$(redcap_notify_first_report_ref "$report_ref")
    if [[ -z "$project_root" || -z "$first_line" || "$first_line" != *.md ]]; then
        return 1
    fi

    if [[ "$first_line" = /* ]]; then
        printf '%s\n' "$first_line"
    else
        printf '%s/%s\n' "$project_root" "$first_line"
    fi
}

redcap_notify_relative_path() {
    local project_root="${1:-}"
    local absolute_path="${2:-}"

    if [[ -z "$project_root" || -z "$absolute_path" ]]; then
        return 1
    fi

    case "$absolute_path" in
        "$project_root"/*)
            printf '%s\n' "${absolute_path#$project_root/}"
            ;;
        *)
            printf '%s\n' "$absolute_path"
            ;;
    esac
}

redcap_notify_extract_report_items() {
    local report_path="${1:-}"
    local kind="${2:-}"

    if [[ -z "$report_path" || ! -f "$report_path" || -z "$kind" ]]; then
        return 0
    fi

    python3 - "$report_path" "$kind" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
kind = sys.argv[2]
text = path.read_text(encoding="utf-8")
lines = text.splitlines()


def capture_heading(prefixes):
    capture = False
    level = 0
    buffer = []
    for line in lines:
        match = re.match(r"^(#+)\s*(.+?)\s*$", line)
        if match:
            heading_level = len(match.group(1))
            heading = match.group(2).strip()
            if capture and heading_level <= level:
                break
            if any(heading.startswith(prefix) for prefix in prefixes):
                capture = True
                level = heading_level
                continue
        if capture:
            buffer.append(line.rstrip())
    return "\n".join(buffer).strip()


def clean(value):
    value = re.sub(r"`([^`]*)`", r"\1", value)
    value = re.sub(r"\*\*(.*?)\*\*", r"\1", value)
    value = re.sub(r"^\[[ xX]\]\s*", "", value)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(
        r"^(当前已完成|详情|上一步完成的是|下一步计划做的是|整体计划脉络图是|当前所在位置|人工介入|说明)[：:]\s*",
        "",
        value,
    )
    return value.strip(" -")


def list_items(block):
    items = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.match(r"^[-*]\s+", line):
            items.append(clean(re.sub(r"^[-*]\s+", "", line)))
        elif re.match(r"^\d+\.\s+", line):
            items.append(clean(re.sub(r"^\d+\.\s+", "", line)))
    items = [item for item in items if item]
    if items:
        return items

    paragraph_lines = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line or line.startswith("|") or line.startswith(">"):
            continue
        paragraph_lines.append(clean(line))

    paragraph_lines = [line for line in paragraph_lines if line]
    if paragraph_lines:
        return [" ".join(paragraph_lines)]
    return []


def table_items(block, primary_key, detail_keys):
    table_lines = [line for line in block.splitlines() if line.strip().startswith("|")]
    if len(table_lines) < 3:
        return []

    headers = [clean(cell) for cell in table_lines[0].strip().strip("|").split("|")]
    items = []
    for raw in table_lines[2:]:
        row = [clean(cell) for cell in raw.strip().strip("|").split("|")]
        if len(row) < len(headers):
            row.extend([""] * (len(headers) - len(row)))
        record = dict(zip(headers, row))
        primary = clean(record.get(primary_key, ""))
        if not primary:
            continue
        detail = ""
        for key in detail_keys:
            detail = clean(record.get(key, ""))
            if detail:
                break
        items.append(f"{primary} — {detail}" if detail else primary)
    return items


summary_map = {
    "done": ["0.1 当前已完成"],
    "previous": ["0.2 上一步完成的是"],
    "next": ["0.3 下一步计划做的是", "0.3 后续动作"],
    "roadmap": ["0.4 整体计划脉络图与当前位置"],
    "intervention": ["0.5 是否需要 Norven 人工介入"],
    "confirm": ["0.1 需你确认"],
    "verify": ["0.2 人工验证"],
}

fallback_map = {
    "done": ([], None, None),
    "previous": ([], None, None),
    "roadmap": ([], None, None),
    "confirm": (["四、人工审核要点"], "审核项", ["说明", "优先级"]),
    "verify": (["5.2 人工验证项"], None, None),
    "next": (["6.3 推荐的下一步行动"], None, None),
}

items = []
summary_block = capture_heading(summary_map.get(kind, []))
if summary_block:
    items = list_items(summary_block)

if not items:
    headings, primary_key, detail_keys = fallback_map.get(kind, ([], None, None))
    fallback_block = capture_heading(headings)
    if fallback_block:
        if primary_key:
            items = table_items(fallback_block, primary_key, detail_keys)
        else:
            items = list_items(fallback_block)

if kind in {"confirm", "verify"}:
    items = [
        item
        for item in items
        if not re.match(r"^(无|当前没有|不需要)([；。，、\s]|$)", item)
    ]

for item in items[:3]:
    print(item)
PY
}

redcap_notify_markdown_list_or_none() {
    local raw_items="${1:-}"

    if [[ -z "$raw_items" ]]; then
        printf -- '- 无\n'
        return 0
    fi

    printf '%s\n' "$raw_items" | awk 'NF {print "- " $0}'
}

redcap_build_completion_message() {
    local headline="${1:-RedCap Layer B 收尾完成}"
    local project="${2:-redcap}"
    local commit_log="${3:-}"
    local source_label report_ref project_root report_path report_label
    local commit_count latest_commit bullet_list done_items previous_items next_items roadmap_items intervention_items confirm_items verify_items

    source_label=$(redcap_notify_flatten_field "${4:-}")
    report_ref="${5:-}"
    project_root="${6:-}"
    commit_count=$(redcap_notify_commit_count "$commit_log")
    latest_commit=$(redcap_notify_latest_commit "$commit_log")
    bullet_list=$(redcap_notify_commit_bullets "$commit_log")

    report_path=$(redcap_notify_resolve_report_path "$project_root" "$report_ref" 2>/dev/null || true)
    if [[ -n "$report_path" && -f "$report_path" ]]; then
        report_label=$(redcap_notify_relative_path "$project_root" "$report_path" 2>/dev/null || true)
        done_items=$(redcap_notify_extract_report_items "$report_path" "done")
        previous_items=$(redcap_notify_extract_report_items "$report_path" "previous")
        next_items=$(redcap_notify_extract_report_items "$report_path" "next")
        roadmap_items=$(redcap_notify_extract_report_items "$report_path" "roadmap")
        intervention_items=$(redcap_notify_extract_report_items "$report_path" "intervention")
        confirm_items=$(redcap_notify_extract_report_items "$report_path" "confirm")
        verify_items=$(redcap_notify_extract_report_items "$report_path" "verify")
    else
        report_label=$(redcap_notify_flatten_field "$report_ref")
    fi

    {
        printf '%s\n\n' "$headline"
        printf -- '- 项目：%s\n' "$project"
        [[ -n "$source_label" ]] && printf -- '- 来源：%s\n' "$source_label"

        printf '\n**结论**\n'
        if [[ -n "$report_label" ]]; then
            printf '%s\n' "$(redcap_notify_markdown_list_or_none "$done_items")"
        else
            printf -- '- 详见本次节点提交或终端汇报\n'
        fi

        if [[ -n "$report_label" ]]; then
            printf '\n**任务位置**\n'
            if [[ -n "$previous_items" ]]; then
                printf '%s\n' "$(redcap_notify_markdown_list_or_none "$previous_items")"
            fi
            printf '%s\n' "$(redcap_notify_markdown_list_or_none "$roadmap_items")"
        else
            printf '\n**任务位置**\n- 未绑定任务报告；请以终端汇报或 closeout receipt 为准\n'
        fi

        printf '\n**下一步**\n'
        if [[ -n "$report_label" ]]; then
            printf '%s\n' "$(redcap_notify_markdown_list_or_none "$next_items")"
        else
            printf -- '- 详见本次节点提交或终端汇报\n'
        fi

        printf '\n**需要 Norven**\n'
        if [[ -n "$intervention_items" ]]; then
            printf '%s\n' "$(redcap_notify_markdown_list_or_none "$intervention_items")"
        elif [[ -n "$confirm_items" || -n "$verify_items" ]]; then
            printf -- '- 需要；详见“仍需你介入 / 仍需人工验证”。\n'
        else
            printf -- '- 不需要；若需要 Norven 决策，RedCap 会改用 manual-intervention 通知。\n'
        fi

        printf '\n**阻塞状态**\n- 无；此消息是节点汇报，不是内部审核失败告警。\n'

        if [[ -n "$confirm_items" ]]; then
            printf '\n**仍需你介入**\n%s\n' "$(redcap_notify_markdown_list_or_none "$confirm_items")"
        fi
        if [[ -n "$verify_items" ]]; then
            printf '\n**仍需人工验证**\n%s\n' "$(redcap_notify_markdown_list_or_none "$verify_items")"
        fi

        printf '\n**关键证据**\n'
        [[ -n "$report_label" ]] && printf -- '- 任务报告：%s\n' "$report_label"
        if [[ "$commit_count" -gt 0 ]]; then
            printf -- '- 本轮提交数：%s\n' "$commit_count"
        fi
        [[ -n "$latest_commit" ]] && printf -- '- 最新提交：%s\n' "$latest_commit"
        if [[ -z "$report_label" && "$commit_count" -eq 0 && -z "$latest_commit" ]]; then
            printf -- '- 详见 closeout receipt 或终端汇报\n'
        fi
    }
}
