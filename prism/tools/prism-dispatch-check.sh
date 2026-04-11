#!/usr/bin/env bash
# prism-dispatch-check.sh — Prism Dispatch 前置校验（硬门禁）
#
# 用法:
#   bash prism/tools/prism-dispatch-check.sh --mode redteam --agents "claude-opus-4.6:challenger,gpt-5.4:reviewer,gemini-3.1-pro-preview:historian"
#   bash prism/tools/prism-dispatch-check.sh --mode explore  --agents "claude-sonnet-4.6:explorer,gpt-5.4:explorer,gemini-3.1-pro-preview:explorer"
#
# 退出码:
#   0 → 校验通过，可以继续 Dispatch
#   1 → 校验失败，必须中止 Dispatch

set -euo pipefail

MODE=""
AGENTS_RAW=""
PROBLEM_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)     MODE="$2";         shift 2 ;;
    --agents)   AGENTS_RAW="$2";   shift 2 ;;
    --problem)  PROBLEM_FILE="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "$MODE" || -z "$AGENTS_RAW" ]]; then
  echo "❌ 用法: $0 --mode <redteam|explore|test|council> --agents \"model:role,...\" [--problem <file>]"
  exit 1
fi

LINE_COUNT=0
if [[ -n "$PROBLEM_FILE" && -f "$PROBLEM_FILE" ]]; then
  LINE_COUNT=$(wc -l < "$PROBLEM_FILE" | tr -d ' ')
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRISM_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

python3 - "$MODE" "$AGENTS_RAW" "$LINE_COUNT" "$PRISM_DIR" << 'PYEOF'
import sys, os

mode = sys.argv[1]
agents_raw = sys.argv[2]
line_count = int(sys.argv[3])
prism_dir = sys.argv[4] if len(sys.argv) > 4 else ""

agents = []
for spec in agents_raw.split(','):
    spec = spec.strip()
    if ':' in spec:
        model, role = spec.split(':', 1)
    else:
        model, role = spec, 'unknown'
    agents.append({'model': model.strip(), 'role': role.strip()})

def get_family(model):
    m = model.lower()
    if m.startswith('claude') or m.startswith('kimi'):
        return 'claude'
    elif m.startswith('gpt') or m.startswith('o1') or m.startswith('o3') or m.startswith('o4'):
        return 'gpt'
    elif m.startswith('gemini'):
        return 'gemini'
    return 'unknown'

roles = [a['role'] for a in agents]
families = list(set(get_family(a['model']) for a in agents))
total = len(agents)
unique_families = len(families)

print(f"=== Prism Dispatch 前置校验 (mode: {mode}) ===")
print(f"Agents: {agents_raw}")
print()

fail = False

# 检查 1: 对抗角色（redteam/council 必须）
if mode in ('redteam', 'council'):
    print("[1/4] 检查强制对抗角色...")
    for required in ('challenger', 'reviewer', 'historian'):
        if required in roles:
            print(f"  ✅ {required} 已分配")
        else:
            print(f"  ❌ 缺少强制角色: {required}")
            fail = True
else:
    print(f"[1/4] 对抗角色检查（跳过，模式 {mode} 不要求）")

# 检查 2: 家族多样性
print()
print("[2/4] 检查模型家族多样性...")
required_families = 3 if mode == 'redteam' else 2
if unique_families < required_families:
    print(f"  ❌ 家族数 {unique_families} < 要求 {required_families}（当前: {', '.join(families)}）")
    fail = True
else:
    print(f"  ✅ 家族数 {unique_families} ≥ {required_families}（{', '.join(families)}）")

# 检查 3: Agent 数量
print()
print("[3/4] 检查 Agent 数量...")
limits = {'redteam': (4,6), 'explore': (3,5), 'test': (2,4), 'council': (3,6)}
min_n, max_n = limits.get(mode, (2,6))
if total < min_n:
    print(f"  ❌ Agent 数 {total} < 最小要求 {min_n}")
    fail = True
elif total > max_n:
    print(f"  ⚠️  Agent 数 {total} > 推荐上限 {max_n}（可继续，但注意 Synthesize 复杂度）")
else:
    print(f"  ✅ Agent 数 {total} 符合 {min_n}~{max_n} 范围")

# 检查 4: 问题包长度
print()
print("[4/4] 检查问题包长度...")
if line_count > 0:
    if line_count > 800:
        print(f"  ⚠️  问题包 {line_count} 行 > 800 行，GPT 系模型可能静默截断（见 L-11）")
    else:
        print(f"  ✅ 问题包 {line_count} 行，无截断风险")
else:
    print("  ℹ️  未提供 --problem 文件，跳过长度检查")

print()
print("[5/5] 检查 redteam 角色 System Prompt 文件...")
if mode == 'redteam' and prism_dir:
    for role in roles:
        prompt_file = os.path.join(prism_dir, 'roles', role, 'system-prompt.md')
        if os.path.isfile(prompt_file):
            print(f"  ✅ {role}: system-prompt.md 存在")
        else:
            print(f"  ❌ {role}: 缺少 {prompt_file}")
            fail = True
    universal = os.path.join(prism_dir, 'roles', 'universal-constraints.md')
    if os.path.isfile(universal):
        print(f"  ✅ universal-constraints.md 存在")
    else:
        print(f"  ❌ 缺少 universal-constraints.md（{universal}）")
        fail = True
else:
    print(f"  ℹ️  非 redteam 模式（{mode}），跳过 System Prompt 校验")

print()
print("===")
if fail:
    print("❌ Dispatch 校验失败 — 必须修正以上问题后重新校验")
    sys.exit(1)
else:
    print("✅ Dispatch 校验通过 — 可以继续执行")
    sys.exit(0)
PYEOF
