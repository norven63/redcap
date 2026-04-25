#!/bin/bash
# redcap-detect-agents.sh — 嗅探本地 Agent 工具与底层模型
#
# 用法:
#   bash compass/tools/redcap-detect-agents.sh [output_path] [--agent <name>] [--probe]
#
# 参数:
#   output_path   输出路径（默认: compass/.workflow/agent-registry.yaml）
#   --agent NAME  只检测指定 Agent（claude-code|gemini|kimi|copilot|codex）
#   --probe       对支持的 CLI 执行实际调用探测底层模型（慢，可能挂起）
#
# 调用时机:
#   - 项目初始化 (INIT 状态)
#   - agent-registry.yaml 不存在
#   - 配置文件 mtime 变化（轻检测发现后触发全量重检）
#   - Agent 调用失败时（--agent 单独重检）
#   - 用户手动触发
#
# 设计原则:
#   默认模式（无 --probe）仅读配置文件 + command -v，秒级完成。
#   --probe 模式会实际调用 CLI（注意 L-11: gemini 可能挂起）。
#   provider 冻结期内不得调用对应 CLI；冻结 agent 只记录 binary 可见和 frozen 状态。

set -euo pipefail

# ── 参数解析 ──────────────────────────────────────────
OUTPUT_PATH=""
TARGET_AGENT="all"
PROBE_MODE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent)   TARGET_AGENT="$2"; shift 2 ;;
    --probe)   PROBE_MODE=true; shift ;;
    *)
      if [[ -z "$OUTPUT_PATH" ]]; then
        OUTPUT_PATH="$1"; shift
      else
        echo "❌ 未知参数: $1" >&2; exit 1
      fi
      ;;
  esac
done

OUTPUT_PATH="${OUTPUT_PATH:-compass/.workflow/agent-registry.yaml}"
mkdir -p "$(dirname "$OUTPUT_PATH")"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
MATRIX_PATH="$(cd "$(dirname "$0")/.." && pwd)/knowledge/model-capability-matrix.yaml"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROVIDER_POLICY="$SCRIPT_DIR/redcap-provider-policy.sh"

# ── 工具函数 ──────────────────────────────────────────
file_mtime() {
  # 跨平台: 用 python3 获取 mtime（macOS stat 格式不一致）
  python3 -c "
import os, datetime
try:
    t = os.path.getmtime('$1')
    print(datetime.datetime.fromtimestamp(t).strftime('%Y-%m-%dT%H:%M:%S'))
except: print('unknown')
" 2>/dev/null
}

# ── 检测: Claude Code ─────────────────────────────────
detect_claude_code() {
  local cli_path
  cli_path=$(command -v claude 2>/dev/null || echo "")

  if [[ -z "$cli_path" ]]; then
    cat <<EOF
  claude-code:
    available: false
    reason: "CLI not installed"
EOF
    return
  fi

  local version
  version=$(claude --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")

  # 从 settings.json 解析模型和 API 配置
  local settings_file="$HOME/.claude/settings.json"
  local model_alias="unknown"
  local base_url=""
  local actual_model="unknown"
  local api_provider="anthropic"

  if [[ -f "$settings_file" ]]; then
    # 用 python3 一次性提取所有字段（避免多次解析）
    eval "$(python3 -c "
import json, sys
try:
    d = json.load(open('$settings_file'))
    env = d.get('env', {})
    print(f'model_alias=\"{d.get(\"model\", \"unknown\")}\"')
    print(f'base_url=\"{env.get(\"ANTHROPIC_BASE_URL\", \"\")}\"')
    ak = env.get('ANTHROPIC_API_KEY', '')
    print(f'api_key_prefix=\"{ak[:10]}\"' if ak else 'api_key_prefix=\"\"')
except Exception as e:
    print(f'model_alias=\"parse-error\"', file=sys.stderr)
" 2>/dev/null)"

    # 根据 base_url 判断实际模型提供商
    if [[ "$base_url" == *"kimi.com"* ]]; then
      api_provider="kimi-siliconflow"
      # Kimi 代理下 model 别名无意义，实际是 Kimi K2.5
      actual_model="kimi-k2.5"
    elif [[ "$base_url" == *"openai.com"* || "$base_url" == *"openrouter"* ]]; then
      api_provider="openai-proxy"
      actual_model="$model_alias"
    elif [[ -z "$base_url" || "$base_url" == *"anthropic.com"* ]]; then
      api_provider="anthropic"
      # 原生 Anthropic: alias 直接映射
      case "$model_alias" in
        opus)   actual_model="claude-opus-4.6" ;;
        sonnet) actual_model="claude-sonnet-4.6" ;;
        *)      actual_model="claude-$model_alias" ;;
      esac
    else
      api_provider="custom-proxy"
      actual_model="$model_alias"
    fi
  fi

  local config_mtime
  config_mtime=$(file_mtime "$settings_file")

  cat <<EOF
  claude-code:
    available: true
    cli_path: "$cli_path"
    version: "$version"
    model_alias: "$model_alias"
    actual_model: "$actual_model"
    api_provider: "$api_provider"
    base_url: "${base_url:-https://api.anthropic.com}"
    config_file: "$settings_file"
    config_mtime: "$config_mtime"
    supports_model_switch: true
    model_switch_flag: "--model"
EOF
}

# ── 检测: Gemini CLI ──────────────────────────────────
detect_gemini() {
  local cli_path
  cli_path=$(command -v gemini 2>/dev/null || echo "")

  if [[ -z "$cli_path" ]]; then
    cat <<EOF
  gemini:
    available: false
    reason: "CLI not installed"
EOF
    return
  fi

  local version
  version=$(gemini --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")

  # 默认模型推断（避免实际调用 — L-11 风险）
  local actual_model="gemini-3-flash"

  # --probe 模式: 实际调用获取精确模型（带 10s 超时防 L-11 挂起）
  if [[ "$PROBE_MODE" == true ]]; then
    local probe_result
    probe_result=$(timeout 10 gemini -p "respond with only: ok" --output-format json --yolo 2>/dev/null || echo "")
    if [[ -n "$probe_result" ]]; then
      local detected
      detected=$(echo "$probe_result" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    models = d.get('stats',{}).get('models',{})
    print(list(models.keys())[0] if models else '')
except: pass
" 2>/dev/null || echo "")
      [[ -n "$detected" ]] && actual_model="$detected"
    fi
  fi

  local settings_file="$HOME/.gemini/settings.json"
  local config_mtime
  config_mtime=$(file_mtime "$settings_file")

  cat <<EOF
  gemini:
    available: true
    cli_path: "$cli_path"
    version: "$version"
    actual_model: "$actual_model"
    api_provider: "google"
    config_file: "$settings_file"
    config_mtime: "$config_mtime"
    supports_model_switch: true
    model_switch_flag: "--model"
    known_issues:
      - "L-7: headless 必须 --yolo"
      - "L-11: JSON 输出长任务可能挂起"
EOF
}

# ── 检测: Kimi CLI ────────────────────────────────────
detect_kimi() {
  local cli_path
  cli_path=$(command -v kimi 2>/dev/null || echo "")

  if [[ -z "$cli_path" ]]; then
    cat <<EOF
  kimi:
    available: false
    reason: "CLI not installed"
EOF
    return
  fi

  local version
  version=$(kimi --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")

  local config_file="$HOME/.kimi/config.toml"
  local actual_model
  actual_model=$(grep 'default_model' "$config_file" 2>/dev/null | cut -d'"' -f2 || echo "kimi-for-coding")

  local config_mtime
  config_mtime=$(file_mtime "$config_file")

  cat <<EOF
  kimi:
    available: true
    cli_path: "$cli_path"
    version: "$version"
    actual_model: "$actual_model"
    api_provider: "moonshot"
    config_file: "$config_file"
    config_mtime: "$config_mtime"
    supports_model_switch: false
EOF
}

# ── 检测: Copilot CLI ─────────────────────────────────
detect_copilot() {
  local cli_path
  cli_path=$(command -v copilot 2>/dev/null || echo "")

  if [[ -z "$cli_path" ]]; then
    cat <<EOF
  copilot:
    available: false
    reason: "CLI not installed"
EOF
    return
  fi

  if [[ ! -x "$PROVIDER_POLICY" ]]; then
  cat <<EOF
  copilot:
    available: true
    cli_path: "$cli_path"
    version: "policy-unavailable"
    actual_model: "claude-opus-4.6"
    api_provider: "github"
    supports_model_switch: true
    model_switch_flag: "--model"
    switchable_models:
      - "claude-opus-4.6"
      - "gpt-5.4"
      - "claude-sonnet-4.6"
    known_issues:
      - "provider policy gate unavailable; skipped copilot version/probe to avoid accidental CLI use"
EOF
    return
  fi

  if "$PROVIDER_POLICY" is-frozen copilot agent-detect >/dev/null 2>&1; then
  cat <<EOF
  copilot:
    available: true
    cli_path: "$cli_path"
    version: "frozen"
    actual_model: "claude-opus-4.6"
    api_provider: "github"
    supports_model_switch: true
    model_switch_flag: "--model"
    switchable_models:
      - "claude-opus-4.6"
      - "gpt-5.4"
      - "claude-sonnet-4.6"
    known_issues:
      - "provider frozen by references/prism-provider-policy.json"
EOF
    return
  fi

  local version
  version=$(copilot --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")

  # Copilot CLI 默认模型由 GitHub 后端控制，通常是 claude-opus-4.6
  # 可通过 --model 切换
  cat <<EOF
  copilot:
    available: true
    cli_path: "$cli_path"
    version: "$version"
    actual_model: "claude-opus-4.6"
    api_provider: "github"
    supports_model_switch: true
    model_switch_flag: "--model"
    switchable_models:
      - "claude-opus-4.6"
      - "gpt-5.4"
      - "claude-sonnet-4.6"
EOF
}

# ── 检测: Codex CLI ───────────────────────────────────
detect_codex() {
  local cli_path
  cli_path=$(command -v codex 2>/dev/null || echo "")

  if [[ -z "$cli_path" ]]; then
    cat <<EOF
  codex:
    available: false
    reason: "CLI not installed"
EOF
    return
  fi

  local version
  version=$(codex --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")

  local config_file="$HOME/.codex/config.toml"
  local actual_model="gpt-5.4"
  if [[ -f "$config_file" ]]; then
    actual_model=$(grep -E '^[[:space:]]*model[[:space:]]*=' "$config_file" 2>/dev/null | head -1 | cut -d'"' -f2 || echo "gpt-5.4")
    [[ -n "$actual_model" ]] || actual_model="gpt-5.4"
  fi

  local config_mtime
  config_mtime=$(file_mtime "$config_file")

  cat <<EOF
  codex:
    available: true
    cli_path: "$cli_path"
    version: "$version"
    actual_model: "$actual_model"
    api_provider: "openai"
    config_file: "$config_file"
    config_mtime: "$config_mtime"
    supports_model_switch: true
    model_switch_flag: "--model"
EOF
}

# ── 轻检测: 配置文件变化检查 ──────────────────────────
# 用途: 对比现有 registry 中的 config_mtime 与当前磁盘 mtime
# 若一致，说明配置未变，可跳过全量检测
check_config_staleness() {
  if [[ ! -f "$OUTPUT_PATH" ]]; then
    echo "stale"  # registry 不存在，必须全量检测
    return
  fi

  local stale=false

  # Claude Code
  local saved_mtime current_mtime
  saved_mtime=$(grep -A 20 "claude-code:" "$OUTPUT_PATH" | grep "config_mtime:" | head -1 | cut -d'"' -f2 2>/dev/null || echo "")
  current_mtime=$(file_mtime "$HOME/.claude/settings.json")
  [[ "$saved_mtime" != "$current_mtime" ]] && stale=true

  # Kimi
  saved_mtime=$(grep -A 20 "kimi:" "$OUTPUT_PATH" | grep "config_mtime:" | head -1 | cut -d'"' -f2 2>/dev/null || echo "")
  current_mtime=$(file_mtime "$HOME/.kimi/config.toml")
  [[ "$saved_mtime" != "$current_mtime" ]] && stale=true

  # Gemini
  saved_mtime=$(grep -A 20 "gemini:" "$OUTPUT_PATH" | grep "config_mtime:" | head -1 | cut -d'"' -f2 2>/dev/null || echo "")
  current_mtime=$(file_mtime "$HOME/.gemini/settings.json")
  [[ "$saved_mtime" != "$current_mtime" ]] && stale=true

  # Codex
  saved_mtime=$(grep -A 20 "codex:" "$OUTPUT_PATH" | grep "config_mtime:" | head -1 | cut -d'"' -f2 2>/dev/null || echo "")
  if [[ -n "$saved_mtime" ]] || command -v codex >/dev/null 2>&1; then
    current_mtime=$(file_mtime "$HOME/.codex/config.toml")
    [[ "$saved_mtime" != "$current_mtime" ]] && stale=true
  fi

  if [[ "$stale" == true ]]; then
    echo "stale"
  else
    echo "fresh"
  fi
}

# ── 主逻辑 ────────────────────────────────────────────
main() {
  # 如果不是指定 Agent，先做轻检测
  if [[ "$TARGET_AGENT" == "all" && -f "$OUTPUT_PATH" ]]; then
    local freshness
    freshness=$(check_config_staleness)
    if [[ "$freshness" == "fresh" ]]; then
      echo "✅ Agent registry is fresh (config files unchanged), skipping detection."
      echo "   Use --agent or delete $OUTPUT_PATH to force re-detection."
      exit 0
    fi
  fi

  {
    echo "# Auto-generated by redcap-detect-agents.sh"
    echo "# 由嗅探脚本自动生成，勿手动编辑"
    echo "# 重新检测: bash compass/tools/redcap-detect-agents.sh [--probe]"
    echo "#"
    echo "# capability_matrix: $MATRIX_PATH"
    echo "detected_at: \"$TIMESTAMP\""
    echo "probe_mode: $PROBE_MODE"
    echo "agents:"

    case "$TARGET_AGENT" in
      all)
        detect_claude_code
        detect_gemini
        detect_kimi
        detect_copilot
        detect_codex
        ;;
      claude-code) detect_claude_code ;;
      gemini)      detect_gemini ;;
      kimi)        detect_kimi ;;
      copilot)     detect_copilot ;;
      codex)       detect_codex ;;
      *)
        echo "❌ Unknown agent: $TARGET_AGENT" >&2
        echo "   Supported: claude-code, gemini, kimi, copilot, codex" >&2
        exit 1
        ;;
    esac
  } > "$OUTPUT_PATH"

  echo "✅ Agent registry written to: $OUTPUT_PATH"
  echo "   capability matrix: $MATRIX_PATH"
}

main
