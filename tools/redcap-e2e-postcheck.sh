#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# RedCap E2E 后置完整性审计脚本
#
# E2E 验证完成后的 exit gate — 所有检查项必须 PASS 才算 E2E 后置处理完成。
#
# 用法：
#   bash tools/redcap-e2e-postcheck.sh
#
# 触发方式（双重保障）：
#   1. Dispatcher 在 E2E 后置流程步骤 ⑧ 手动执行
#   2. Stop Hook 检测到 testing/e2e-session.yaml 存在时自动执行
#
# 退出码：
#   0 — 全部 PASS
#   1 — 有 FAIL（必须修复后重新执行）
# ─────────────────────────────────────────────────────────

set -u

# 跨平台获取文件 mtime（秒级时间戳）
get_mtime() {
    local file="$1"
    # 优先用 python3（最可移植），否则用 GNU stat
    python3 -c "import os,sys; print(int(os.path.getmtime(sys.argv[1])))" "$file" 2>/dev/null \
        || stat -c "%Y" "$file" 2>/dev/null \
        || echo "0"
}

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

SESSION_FILE="$PROJECT_DIR/testing/e2e-session.yaml"
REPORT_FILE="$PROJECT_DIR/testing/latest-e2e-report.md"
PENDING_FILE="$PROJECT_DIR/testing/pending-validations.md"
LESSONS_FILE="$PROJECT_DIR/knowledge/lessons.md"

FAIL_COUNT=0
WARN_COUNT=0

pass() { echo "  ✅ PASS: $1"; }
fail() { echo "  ❌ FAIL: $1"; FAIL_COUNT=$((FAIL_COUNT + 1)); }
warn() { echo "  ⚠️  WARN: $1"; WARN_COUNT=$((WARN_COUNT + 1)); }

echo "═══════════════════════════════════════════════════"
echo " RedCap E2E 后置完整性审计"
echo " 时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════════════════"
echo ""

# ── 检查 1: e2e-session.yaml 是否存在 ──

echo "[1/6] E2E Session 配置文件"
if [[ ! -f "$SESSION_FILE" ]]; then
    fail "testing/e2e-session.yaml 不存在 — E2E 启动时未创建配置锁定文件"
    echo "  → 无法验证开关覆盖完整性，后续检查可能不准确"
else
    pass "testing/e2e-session.yaml 存在"

    # 检查 switches_on vs switches_completed 是否一致
    if command -v python3 &>/dev/null; then
        SWITCH_CHECK=$(python3 -c "
import sys
try:
    import yaml
    with open('$SESSION_FILE') as f:
        data = yaml.safe_load(f)
    on = set(data.get('switches_on', []))
    done = set(data.get('switches_completed', []))
except ImportError:
    # PyYAML 不可用，用简单文本解析
    import re
    text = open('$SESSION_FILE').read()
    on_match = re.search(r'switches_on:\s*\[([^\]]*)\]', text)
    done_match = re.search(r'switches_completed:\s*\[([^\]]*)\]', text)
    on = set(x.strip().strip('\"').strip(\"'\") for x in (on_match.group(1).split(',') if on_match else []) if x.strip())
    done = set(x.strip().strip('\"').strip(\"'\") for x in (done_match.group(1).split(',') if done_match else []) if x.strip())
except Exception as e:
    print('ERROR:' + str(e))
    sys.exit(0)
missing = on - done
if missing:
    print('FAIL:' + ','.join(sorted(missing)))
else:
    print('PASS')
" 2>/dev/null || echo "ERROR:python3 解析失败")

        case "$SWITCH_CHECK" in
            PASS)
                pass "所有启用开关均已执行完毕"
                ;;
            FAIL:*)
                MISSING="${SWITCH_CHECK#FAIL:}"
                fail "以下开关已启用但未执行: $MISSING"
                ;;
            ERROR:*)
                fail "无法解析 e2e-session.yaml: ${SWITCH_CHECK#ERROR:} — 无法验证开关覆盖完整性"
                ;;
        esac
    else
        warn "python3 不可用，无法校验开关覆盖完整性"
    fi
fi
echo ""

# ── 检查 2: 报告是否写到正确路径 ──

echo "[2/6] E2E 报告路径"
if [[ ! -f "$REPORT_FILE" ]]; then
    fail "testing/latest-e2e-report.md 不存在"
else
    # 检查报告是否在最近 2 小时内更新
    REPORT_MTIME=$(get_mtime "$REPORT_FILE")
    NOW=$(date +%s)
    AGE=$(( (NOW - REPORT_MTIME) / 60 ))

    if [[ $AGE -le 120 ]]; then
        pass "testing/latest-e2e-report.md 已更新（${AGE}分钟前）"
    else
        fail "testing/latest-e2e-report.md 最后更新于 ${AGE} 分钟前 — 未在本次 E2E 中更新"
    fi
fi
echo ""

# ── 检查 3: pending-validations 是否被消费 ──

echo "[3/6] pending-validations 消费"
if [[ ! -f "$PENDING_FILE" ]]; then
    fail "testing/pending-validations.md 不存在"
else
    # 检查是否有任何 ✅ 状态的条目（表示有消费动作）
    CONSUMED=$(grep -c '✅' "$PENDING_FILE" 2>/dev/null || echo "0")
    PENDING=$(grep -c '🔴' "$PENDING_FILE" 2>/dev/null || echo "0")

    if [[ "$CONSUMED" -gt 0 ]]; then
        pass "有 ${CONSUMED} 个条目已标记 ✅（仍有 ${PENDING} 个 🔴 待验证）"
    else
        # 检查归档区是否有条目
        ARCHIVED=$(grep -c '已验证归档' "$PENDING_FILE" 2>/dev/null || echo "0")
        if [[ "$ARCHIVED" -gt 0 ]]; then
            # 检查归档区下方是否有实际归档条目
            ARCHIVE_ITEMS=$(awk '/已验证归档/,0' "$PENDING_FILE" | grep -c '###' 2>/dev/null || echo "0")
            if [[ "$ARCHIVE_ITEMS" -gt 0 ]]; then
                pass "归档区有 ${ARCHIVE_ITEMS} 个已验证条目"
            else
                fail "pending-validations 无任何已消费条目（全部 🔴）— E2E 未消费待验证项"
            fi
        else
            fail "pending-validations 无任何已消费条目 — E2E 未消费待验证项"
        fi
    fi
fi
echo ""

# ── 检查 4: lessons.md 是否有本次沉淀 ──

echo "[4/6] 经验沉淀"
if [[ ! -f "$LESSONS_FILE" ]]; then
    fail "knowledge/lessons.md 不存在"
else
    LESSONS_MTIME=$(get_mtime "$LESSONS_FILE")
    NOW=$(date +%s)
    AGE=$(( (NOW - LESSONS_MTIME) / 60 ))

    if [[ $AGE -le 120 ]]; then
        pass "knowledge/lessons.md 已更新（${AGE}分钟前）— 有经验沉淀"
    else
        warn "knowledge/lessons.md 未在本次 E2E 中更新 — 可能确实无新发现，也可能遗漏沉淀"
    fi
fi
echo ""

# ── 检查 5: commit message 是否包含 E2E 结论 ──

echo "[5/6] Commit E2E 结论"
RECENT_COMMITS=$(git -C "$PROJECT_DIR" --no-pager log --oneline -10 2>/dev/null || echo "")
E2E_COMMIT=$(echo "$RECENT_COMMITS" | grep -i 'E2E(' | head -1)

if [[ -n "$E2E_COMMIT" ]]; then
    pass "找到 E2E 结论 commit: $E2E_COMMIT"
else
    fail "最近 10 个 commit 中未找到包含 'E2E(' 的结论 commit"
fi
echo ""

# ── 检查 6: E2E 报告路径 ──

echo "[6/6] E2E 报告路径"
REPORT_FILE="$PROJECT_DIR/testing/latest-e2e-report.md"
if [[ -f "$REPORT_FILE" ]]; then
    REPORT_MTIME=$(get_mtime "$REPORT_FILE")
    NOW=$(date +%s)
    AGE=$(( (NOW - REPORT_MTIME) / 60 ))
    if [[ $AGE -le 120 ]]; then
        pass "testing/latest-e2e-report.md 已更新（${AGE}分钟前）"
    else
        warn "testing/latest-e2e-report.md 最后更新于 ${AGE} 分钟前"
    fi
else
    fail "testing/latest-e2e-report.md 不存在（E2E 报告必须写入此路径）"
fi
echo ""

# ── 汇总 ──

echo "═══════════════════════════════════════════════════"
if [[ $FAIL_COUNT -eq 0 ]]; then
    echo " ✅ 全部通过（${WARN_COUNT} 个警告）"
    echo " → 可以提交 E2E 汇总 commit 并删除 e2e-session.yaml"
    echo "═══════════════════════════════════════════════════"
    exit 0
else
    echo " ❌ ${FAIL_COUNT} 项未通过（${WARN_COUNT} 个警告）"
    echo " → 修复后重新执行: bash tools/redcap-e2e-postcheck.sh"
    echo "═══════════════════════════════════════════════════"
    exit 1
fi
