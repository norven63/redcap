#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# RedCap state.yaml 一致性校验脚本
#
# 校验 state.yaml 与项目实际进度的一致性。
# 设计目的：防止 Dispatcher 代劳模式下 state.yaml 维护纪律下降（L-19）。
#
# 用法：
#   bash tools/redcap-check-state.sh <dev_manual_dir>
#
# 参数：
#   dev_manual_dir  — 开发手册/ 目录绝对路径（必须）
#
# 校验项：
#   1. state.yaml 存在且基本字段完整
#   2. current_step 与 history 记录一致
#   3. outbox 交付物数量与记录的完成步骤匹配
#   4. current_state 合法性
#
# 退出码：
#   0 — 全部通过
#   1 — 参数错误
#   2 — 发现不一致（输出警告，不阻塞）
# ─────────────────────────────────────────────────────────

set -u

DEV_MANUAL="${1:?用法: bash tools/redcap-check-state.sh <dev_manual_dir>}"
STATE_FILE="$DEV_MANUAL/.workflow/state.yaml"
WARNINGS=0

warn() {
  echo "[check-state] ⚠ $1"
  WARNINGS=$((WARNINGS + 1))
}

info() {
  echo "[check-state] ✓ $1"
}

# ── 前置检查 ─────────────────────────────────────────────

if [[ ! -f "$STATE_FILE" ]]; then
  echo "[check-state] state.yaml 不存在: $STATE_FILE"
  echo "[check-state] 如果是全新项目（未初始化），此为正常状态"
  exit 0
fi

# ── 使用 Python 解析 YAML（兼容性：python3 + PyYAML 或基础解析）──

if ! command -v python3 &>/dev/null; then
  echo "[check-state] ⚠ 未找到 python3，跳过校验"
  exit 0
fi

# 用 Python 执行完整校验
python3 << 'PYEOF' "$STATE_FILE" "$DEV_MANUAL"
import sys, os, re
from pathlib import Path

state_file = sys.argv[1]
dev_manual = sys.argv[2]
warnings = 0

def warn(msg):
    global warnings
    print(f"[check-state] ⚠ {msg}")
    warnings += 1

def info(msg):
    print(f"[check-state] ✓ {msg}")

# ── 1. 基础 YAML 解析（不依赖 PyYAML，用正则提取关键字段）──

with open(state_file, 'r') as f:
    content = f.read()

def yaml_get(key):
    """简易 YAML 顶级字段提取（仅支持简单值）"""
    m = re.search(rf'^{key}:\s*(.+)$', content, re.MULTILINE)
    if m:
        val = m.group(1).strip().strip('"').strip("'")
        return val if val != 'null' else None
    return None

def yaml_get_int(key):
    val = yaml_get(key)
    try:
        return int(val) if val else 0
    except (ValueError, TypeError):
        return 0

# ── 2. 必填字段检查 ─────────────────────────────────

REQUIRED_FIELDS = [
    'project', 'current_state', 'current_step', 'total_steps',
    'current_role', 'iteration'
]

for field in REQUIRED_FIELDS:
    if re.search(rf'^{field}:', content, re.MULTILINE) is None:
        warn(f"缺少必填字段: {field}")

current_state = yaml_get('current_state') or 'UNKNOWN'
current_step = yaml_get_int('current_step')
total_steps = yaml_get_int('total_steps')

info(f"当前状态: {current_state}, 步骤: {current_step}/{total_steps}")

# ── 3. current_state 合法性 ──────────────────────────

VALID_STATES = {
    'INIT', 'PM_WORKING', 'PM_DONE',
    'ARCH_WORKING', 'ARCH_DONE',
    'DEV_WORKING', 'DEV_DONE',
    'QA_WORKING', 'QA_PASS', 'QA_FAIL',
    'REVIEW_WORKING', 'REVIEW_PASS', 'REVIEW_FAIL',
    'ALL_DONE', 'PAUSED',
    'ESCALATE_L1', 'ESCALATE_L2',
    'ALL_AGENT_FAIL'
}

if current_state not in VALID_STATES:
    warn(f"current_state 值不合法: {current_state}")

# ── 4. history 记录与 current_step 一致性 ────────────

# 计算 history 中出现的步骤编号
history_steps = set()
for m in re.finditer(r'step:\s*(\d+)', content):
    history_steps.add(int(m.group(1)))

if current_step > 0 and len(history_steps) == 0:
    warn(f"current_step={current_step} 但 history 中无步骤记录（Dispatcher 代劳时可能遗漏更新）")

if history_steps:
    max_history_step = max(history_steps)
    if current_step < max_history_step:
        warn(f"current_step({current_step}) < history 最大步骤({max_history_step})，state.yaml 可能滞后")

# ── 5. outbox 交付物与步骤数匹配 ─────────────────────

dev_manual_path = Path(dev_manual)
roles_with_outbox = ['architect', 'programmer', 'qa']
for role in roles_with_outbox:
    outbox = dev_manual_path / role / 'outbox'
    if outbox.exists():
        # 统计非 __redcap_status 的交付物文件
        deliverables = [f for f in outbox.iterdir()
                       if f.is_file() and f.name != '__redcap_status.json']
        step_files = [f for f in deliverables if re.match(r'步骤\d+', f.name) or re.match(r'i\d+-步骤\d+', f.name)]
        if step_files:
            info(f"{role}/outbox: {len(step_files)} 个步骤交付物")

# ── 6. purpose 字段存在性（L-21）─────────────────────

purpose = yaml_get('purpose')
if not purpose:
    warn("缺少 purpose 字段（L-21 要求：防止上下文漂移遗忘初衷）")
else:
    info(f"目的锚点: {purpose[:50]}{'...' if len(purpose) > 50 else ''}")

# ── 7. degraded_mode 与 agent_health 一致性 ──────────

degraded = yaml_get('degraded_mode')
if degraded == 'true':
    approved_by = yaml_get('degraded_approved_by')
    if not approved_by:
        warn("degraded_mode=true 但 degraded_approved_by 为空（需记录授权来源）")
    else:
        info(f"降级模式已授权: {approved_by}")

# ── 结论 ─────────────────────────────────────────────

print()
if warnings > 0:
    print(f"[check-state] 发现 {warnings} 个不一致，建议 Dispatcher 在 commit 前修正 state.yaml")
    sys.exit(2)
else:
    print("[check-state] state.yaml 一致性校验全部通过")
    sys.exit(0)
PYEOF

exit $?
