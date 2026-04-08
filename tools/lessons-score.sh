#!/usr/bin/env bash
# tools/lessons-score.sh
# 计算 knowledge/lessons.md 每条 Lesson 的评分，输出排序报告
# 用途：判断哪些 Lesson 可归档到 lessons-archive.md（score < 1.0 且 impact ≠ high 且 age > 3 个月）
#
# 用法：
#   bash tools/lessons-score.sh                  # 默认从脚本所在目录推断 redcap 根
#   bash tools/lessons-score.sh /path/to/redcap  # 显式指定路径

REDCAP_DIR="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
LESSONS_FILE="$REDCAP_DIR/knowledge/lessons.md"

if [[ ! -f "$LESSONS_FILE" ]]; then
    echo "错误：找不到 $LESSONS_FILE" >&2
    exit 1
fi

python3 - "$LESSONS_FILE" <<'PYEOF'
import sys, re
from datetime import date

LESSONS_FILE = sys.argv[1]
TODAY = date.today()

def months_since(ym_str):
    try:
        y, m = map(int, ym_str.split("-"))
        return (TODAY.year - y) * 12 + (TODAY.month - m)
    except Exception:
        return 0

def recency(mo):
    if mo < 6:  return 1.0
    if mo <= 12: return 0.6
    return 0.3

def freq(n):
    return min(n, 5) / 5

impact_w = {"high": 4, "medium": 2, "low": 1}
GRACE_MONTHS = 3  # 新 Lesson 豁免期：3 个月内不计入归档候选

text = open(LESSONS_FILE).read()
blocks = re.split(r"(?=^### L-)", text, flags=re.MULTILINE)

results = []
for block in blocks:
    m_id = re.search(r"^### (L-\d+):", block, re.MULTILINE)
    if not m_id:
        continue
    lid = m_id.group(1)
    m_imp  = re.search(r"\*\*影响度\*\*[：:]\s*(\w+)", block)
    m_freq = re.search(r"\*\*复现次数\*\*[：:]\s*(\d+)", block)
    m_last = re.search(r"\*\*最后命中\*\*[：:]\s*(\d{4}-\d{2})", block)
    hardened = "⚙️ 已硬化" in block

    if not (m_imp and m_freq and m_last):
        print(f"⚠  {lid}: 缺少元数据字段，跳过评分")
        continue

    imp  = m_imp.group(1).lower()
    n    = int(m_freq.group(1))
    last = m_last.group(1)
    mo   = months_since(last)
    iw   = impact_w.get(imp, 2)
    score = iw * recency(mo) * freq(n)

    # 归档资格判断
    if mo < GRACE_MONTHS:
        verdict = "⏳ 豁免（< 3月）"
    elif imp == "high":
        verdict = "🔒 保留（high 免疫）"
    elif score >= 1.0:
        verdict = "✅ 保留"
    else:
        verdict = "📦 归档候选"

    results.append((score, lid, imp, n, last, mo, verdict, hardened))

results.sort(key=lambda x: x[0])

print(f"\n📊 Lessons 评分报告（基准日期：{TODAY}，归档阈值：score < 1.0 且 impact ≠ high 且 age ≥ 3月）")
print(f"{'Score':>6}  {'ID':<6}  {'Impact':<8}  {'Hits':>4}  {'Last':<8}  {'Age(mo)':>7}  {'Hdnd':>4}  状态")
print("─" * 85)
for score, lid, imp, n, last, mo, verdict, hardened in results:
    h = "✓" if hardened else "-"
    print(f"{score:>6.2f}  {lid:<6}  {imp:<8}  {n:>4}  {last:<8}  {mo:>7}  {h:>4}  {verdict}")

archive_candidates = [r for r in results if "归档候选" in r[6]]
print(f"\n{'─'*85}")
print(f"当前可归档条目：{len(archive_candidates)} 条")
if archive_candidates:
    print("  → 执行归档：将上述条目从 lessons.md 移至 lessons-archive.md")
else:
    print("  → 暂无需归档（所有 score < 1.0 的条目均在豁免期内或为 high-immune）")

total_lines = sum(1 for _ in open(LESSONS_FILE))
print(f"当前 lessons.md 行数：{total_lines}（阈值：300 行）")
if total_lines > 300:
    print(f"  ⚠  超出阈值 {total_lines - 300} 行，建议执行归档或等豁免期到期")
else:
    print(f"  ✅ 行数在阈值内")
PYEOF
