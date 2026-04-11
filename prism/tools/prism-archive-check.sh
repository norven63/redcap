#!/usr/bin/env bash
# prism-archive-check.sh — Prism Archive 前置校验
#
# 用法:
#   bash prism/tools/prism-archive-check.sh --report prism/reports/20260410-redteam-001.md
#
# 退出码:
#   0 → 校验通过，可以 Archive + commit
#   1 → 校验失败，必须修正后再 Archive

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDCAP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LESSONS="$REDCAP_ROOT/compass/knowledge/lessons.md"
INDEX="$REDCAP_ROOT/prism/reports/index.yaml"
SESSION_REGISTRY="$REDCAP_ROOT/prism/reports/.session-registry.yaml"

REPORT_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --report) REPORT_FILE="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "$REPORT_FILE" ]]; then
  echo "❌ 用法: $0 --report <report_file>"
  exit 1
fi

echo "=== Prism Archive 前置校验 ==="
echo "报告文件: $REPORT_FILE"
echo ""

FAIL=0
VERDICT=""
REPORT_RUN_ID=""

required_quorum() {
  case "$1" in
    3) echo 2 ;;
    4) echo 3 ;;
    5) echo 3 ;;
    6) echo 4 ;;
    *) echo 0 ;;
  esac
}

# 检查 1: 报告文件存在
echo "[1/5] 检查报告文件..."
if [[ ! -f "$REPORT_FILE" ]]; then
  echo "  ❌ 报告文件不存在: $REPORT_FILE"
  FAIL=1
else
  echo "  ✅ 报告文件存在"
fi

# 检查 2: 报告包含 Adjudicate verdict
echo ""
echo "[2/5] 检查 Adjudicate verdict..."
if grep -qiE "(consensus|weak-consensus|deadlock|escalate)" "$REPORT_FILE" 2>/dev/null; then
  VERDICT=$(grep -iEo "(consensus|weak-consensus|deadlock|escalate)" "$REPORT_FILE" | head -1)
  echo "  ✅ verdict 已写入: $VERDICT"
else
  echo "  ❌ 报告中未找到 verdict（consensus/weak-consensus/deadlock/escalate）"
  FAIL=1
fi

# 检查 3: 报告 run_id
echo ""
echo "[3/7] 检查报告 run_id..."
REPORT_RUN_ID="$(
  python3 - "$REPORT_FILE" <<'PY'
import re
import sys

path = sys.argv[1]
pattern = re.compile(r"\*\*运行 ID\*\*：\s*([A-Za-z0-9._-]+)")

with open(path, encoding="utf-8") as f:
    for line in f:
        match = pattern.search(line)
        if match:
            print(match.group(1))
            break
PY
)"
if [[ -z "$REPORT_RUN_ID" ]]; then
  echo "  ❌ 报告缺少 **运行 ID** 元数据，无法绑定 session_registry"
  FAIL=1
else
  echo "  ✅ 报告 run_id: $REPORT_RUN_ID"
fi

# 检查 4: session registry / quorum 物理校验
echo ""
echo "[4/7] 检查 session_registry 与 quorum..."
if [[ ! -f "$SESSION_REGISTRY" ]]; then
  echo "  ❌ 缺少 session registry: $SESSION_REGISTRY"
  FAIL=1
else
  eval "$(
    python3 - "$SESSION_REGISTRY" <<'PY'
import re
import sys

path = sys.argv[1]
agents = []
current = None
run_id = ""
mode = ""

with open(path, encoding="utf-8") as f:
    for raw in f:
        line = raw.rstrip("\n")
        m = re.match(r"^run_id:\s*(.+)$", line)
        if m:
            run_id = m.group(1).strip().strip('"')
            continue
        m = re.match(r"^mode:\s*(.+)$", line)
        if m:
            mode = m.group(1).strip().strip('"')
            continue
        m = re.match(r"^\s*-\s+handle_type:\s*(.+)$", line)
        if m:
            if current is not None:
                agents.append(current)
            current = {"handle_type": m.group(1).strip().strip('"')}
            continue
        m = re.match(r"^\s+([A-Za-z_]+):\s*(.*)$", line)
        if m and current is not None:
            current[m.group(1)] = m.group(2).strip().strip('"')
    if current is not None:
        agents.append(current)

responded_roles = [a.get("role", "?") for a in agents if a.get("status") in ("responded", "followed_up")]
absent_roles = [a.get("role", "?") for a in agents if a.get("status") == "absent"]
dispatched_roles = [a.get("role", "?") for a in agents if a.get("status") == "dispatched"]
schema_bad_roles = [
    a.get("role", "?")
    for a in agents
    if a.get("status") in ("responded", "followed_up") and a.get("schema_ok") != "true"
]
missing_injection_roles = [
    a.get("role", "?")
    for a in agents
    if a.get("injection_mode") not in ("native", "prefixed")
]
invalid_status_roles = [
    a.get("role", "?")
    for a in agents
    if a.get("status") not in ("dispatched", "responded", "absent", "followed_up")
]

def emit(key, value):
    print(f'{key}="{value}"')

emit("REGISTRY_RUN_ID", run_id)
emit("REGISTRY_MODE", mode)
emit("REGISTRY_TOTAL", str(len(agents)))
emit("REGISTRY_RESPONDED", str(len(responded_roles)))
emit("REGISTRY_ABSENT", str(len(absent_roles)))
emit("REGISTRY_DISPATCHED", str(len(dispatched_roles)))
emit("REGISTRY_SCHEMA_BAD", str(len(schema_bad_roles)))
emit("REGISTRY_MISSING_INJECTION", str(len(missing_injection_roles)))
emit("REGISTRY_INVALID_STATUS", str(len(invalid_status_roles)))
emit("RESPONDED_ROLES", ",".join(responded_roles))
emit("ABSENT_ROLES", ",".join(absent_roles))
emit("DISPATCHED_ROLES", ",".join(dispatched_roles))
emit("SCHEMA_BAD_ROLES", ",".join(schema_bad_roles))
emit("MISSING_INJECTION_ROLES", ",".join(missing_injection_roles))
emit("INVALID_STATUS_ROLES", ",".join(invalid_status_roles))
PY
  )"

  QUORUM_REQUIRED=$(required_quorum "$REGISTRY_TOTAL")
  if [[ "$QUORUM_REQUIRED" -eq 0 ]]; then
    echo "  ❌ session_registry 中 Agent 数非法: ${REGISTRY_TOTAL}（仅支持 3~6）"
    FAIL=1
  else
    echo "  ℹ️  run_id=${REGISTRY_RUN_ID:-unknown}, mode=${REGISTRY_MODE:-unknown}"
    if [[ -z "$REPORT_RUN_ID" ]]; then
      :
    elif [[ "$REPORT_RUN_ID" != "${REGISTRY_RUN_ID:-}" ]]; then
      echo "  ❌ 报告 run_id=${REPORT_RUN_ID} 与当前 session_registry run_id=${REGISTRY_RUN_ID:-unknown} 不匹配"
      FAIL=1
    else
      echo "  ✅ 报告与 session_registry 已绑定到同一 run_id"
    fi
    echo "  ℹ️  响应数: ${REGISTRY_RESPONDED}/${REGISTRY_TOTAL}（N_quorum=${QUORUM_REQUIRED}）"
    [[ -n "${RESPONDED_ROLES:-}" ]] && echo "  ℹ️  responded: $RESPONDED_ROLES"
    [[ -n "${ABSENT_ROLES:-}" ]] && echo "  ℹ️  absent: $ABSENT_ROLES"

    if [[ "$REGISTRY_RESPONDED" -lt "$QUORUM_REQUIRED" ]]; then
      echo "  ❌ quorum 不达标：需要 ≥$QUORUM_REQUIRED 个 responded/followed_up"
      FAIL=1
    else
      echo "  ✅ quorum 达标"
    fi

    if [[ "$REGISTRY_DISPATCHED" -gt 0 ]]; then
      echo "  ❌ 仍有未收敛 Agent 处于 dispatched: $DISPATCHED_ROLES"
      FAIL=1
    fi

    if [[ "$REGISTRY_SCHEMA_BAD" -gt 0 ]]; then
      echo "  ❌ responded/followed_up 中存在 schema_ok!=true: $SCHEMA_BAD_ROLES"
      FAIL=1
    fi

    if [[ "$REGISTRY_MISSING_INJECTION" -gt 0 ]]; then
      echo "  ❌ 缺少 injection_mode 记录: $MISSING_INJECTION_ROLES"
      FAIL=1
    fi

    if [[ "$REGISTRY_INVALID_STATUS" -gt 0 ]]; then
      echo "  ❌ 存在非法 status: $INVALID_STATUS_ROLES"
      FAIL=1
    fi
  fi
fi

# 检查 5: 报告中显式记录 quorum/ABSENT
echo ""
echo "[5/7] 检查报告中的 quorum/ABSENT 记录..."
if grep -qiE "(quorum|法定人数|参与 Agent|ABSENT)" "$REPORT_FILE" 2>/dev/null; then
  echo "  ✅ quorum/ABSENT 信息已写入报告"
else
  echo "  ⚠️  未找到 quorum/ABSENT 说明（建议显式写入）"
fi

# 检查 6: index.yaml 已更新（报告 ID 存在于 index 中）
echo ""
echo "[6/7] 检查 index.yaml 已更新..."
REPORT_ID=$(basename "$REPORT_FILE" .md)
if grep -q "$REPORT_ID" "$INDEX" 2>/dev/null; then
  echo "  ✅ index.yaml 已包含 $REPORT_ID"
else
  echo "  ❌ index.yaml 未包含 ${REPORT_ID}，请先更新 prism/reports/index.yaml"
  FAIL=1
fi

# 检查 7: lessons.md 已更新（如果 verdict 是可执行的）
echo ""
echo "[7/7] 检查 lessons.md 沉淀..."
if [[ -n "$VERDICT" ]] && [[ "$VERDICT" != "deadlock" && "$VERDICT" != "escalate" ]]; then
  # 检查 lessons.md 的最后修改时间是否晚于报告文件
  if [[ -f "$LESSONS" ]]; then
    LESSONS_MTIME=$(python3 -c "import os; print(os.path.getmtime('$LESSONS'))")
    REPORT_MTIME=$(python3 -c "import os; print(os.path.getmtime('$REPORT_FILE'))")
    if python3 -c "exit(0 if float('$LESSONS_MTIME') >= float('$REPORT_MTIME') else 1)"; then
      echo "  ✅ lessons.md 已在报告之后更新"
    else
      echo "  ⚠️  lessons.md 早于报告文件——是否忘记沉淀核心结论？"
      echo "     （若本次无新教训，可忽略此警告）"
    fi
  fi
else
  echo "  ℹ️  verdict=${VERDICT}，无需强制更新 lessons.md"
fi

# ── 最终判决 ─────────────────────────────────────────
echo ""
echo "==="
if [[ $FAIL -eq 1 ]]; then
  echo "❌ Archive 校验失败 — 必须修正以上问题后再执行 git commit"
  exit 1
else
  echo "✅ Archive 校验通过 — 可以执行 git add + commit"
  exit 0
fi
