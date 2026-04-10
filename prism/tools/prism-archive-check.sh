#!/usr/bin/env bash
# prism-archive-check.sh — Prism Archive 前置校验
#
# 用法:
#   bash tools/prism-archive-check.sh --report prism/reports/20260410-redteam-001.md
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

# 检查 3: quorum 说明
echo ""
echo "[3/5] 检查 quorum 记录..."
if grep -qiE "(quorum|法定人数|参与 Agent|ABSENT)" "$REPORT_FILE" 2>/dev/null; then
  echo "  ✅ quorum 信息已记录"
else
  echo "  ⚠️  未找到 quorum/ABSENT 说明（可能 quorum 满足，但建议明确记录）"
fi

# 检查 4: index.yaml 已更新（报告 ID 存在于 index 中）
echo ""
echo "[4/5] 检查 index.yaml 已更新..."
REPORT_ID=$(basename "$REPORT_FILE" .md)
if grep -q "$REPORT_ID" "$INDEX" 2>/dev/null; then
  echo "  ✅ index.yaml 已包含 $REPORT_ID"
else
  echo "  ❌ index.yaml 未包含 $REPORT_ID，请先更新 prism/reports/index.yaml"
  FAIL=1
fi

# 检查 5: lessons.md 已更新（如果 verdict 是可执行的）
echo ""
echo "[5/5] 检查 lessons.md 沉淀..."
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
  echo "  ℹ️  verdict=$VERDICT，无需强制更新 lessons.md"
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
