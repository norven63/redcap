# Kimi CLI — Hooks 与指令注入详情

> 本文件从 [host-reliability.md](host-reliability.md) 拆分而来，记录 Kimi CLI 的 Hook 能力、实测验证结果及 Dispatcher 协议。

---

## 1. Hooks 能力

```toml
# ~/.kimi/config.toml — 示例（单项目简单场景）
[[hooks]]
event = "Stop"
command = "bash /path/to/project/tools/on-complete.sh"
timeout = 60
```

> ⚠️ 多项目环境下**不要**直接注册项目级脚本，必须通过 Dispatcher 路由（§3）。

- 支持 **13 种生命周期事件**（远超 Claude Code 的 4 种）：`PreToolUse`、`PostToolUse`、`PostToolUseFailure`、`UserPromptSubmit`、`Stop`、`StopFailure`、`SessionStart`、`SessionEnd`、`SubagentStart`、`SubagentStop`、`PreCompact`、`PostCompact`、`Notification`
- `Stop` hook 在 Agent 轮次结束时执行——与 Claude Code 等价，适合 `on_ALL_DONE`
- `SessionEnd` hook 在会话关闭时执行——**比 Stop 更可靠**，因为即使 Stop 被跳过，SessionEnd 仍会触发
- 通信协议：stdin 接收 JSON 上下文，退出码 0=继续 / 2=阻止
- **Fail-Open 策略**：hook 超时/崩溃按"允许"处理，不阻塞 Agent
- **Stop 防循环**：Stop hook 最多重新触发一次，`stop_hook_active=true` 标志位防止无限循环
- 配置位置：`~/.kimi/config.toml`（`[[hooks]]` 数组）
- **局限**：Beta 阶段（截至 2026-04），API 可能变更；**仅支持全局配置，无工程级 hook 配置**

> 官方文档：https://moonshotai.github.io/kimi-cli/zh/customization/hooks.html

---

## 2. 实测验证（v1.30.0, 2026-04-04）

使用标记文件法实测 4 种事件，**全部确认可用**：

| 事件 | 触发时机 | stdin JSON 关键字段 | 验证结果 |
|------|----------|---------------------|----------|
| `SessionStart` | 会话创建后立即触发 | `session_id`, `cwd`, `source: "startup"` | ✅ |
| `PostToolUse` | 工具调用完成后 | `tool_name`, `tool_input`, `tool_output`, `tool_call_id` | ✅ |
| `Stop` | Agent 轮次结束 | `session_id`, `stop_hook_active: false` | ✅ |
| `SessionEnd` | 会话关闭时 | `session_id`, `reason: "exit"` | ✅ |

**关键发现**：
- 触发顺序严格为 `SessionStart → PreToolUse → PostToolUse(×N) → Stop → SessionEnd`
- `--print` 模式下 `Stop` 不触发（直接跳到 `SessionEnd`），`-p` 模式正常触发
- **matcher 过滤有效**：`matcher = "WriteFile|StrReplaceFile"` 精确匹配 `tool_name` 字段，Shell 等其他工具不触发
- stdin JSON 包含完整上下文（session_id、cwd、工具输入/输出等），可用于条件判断
- `stop_hook_active` 字段可用于检测是否处于防循环状态
- 环境变量：hook 脚本中无 Kimi 特有环境变量注入，事件名通过 stdin JSON 的 `hook_event_name` 传递

**stdin JSON 字段名注意**（与 Claude Code 不同）：
- 文件路径：`.tool_input.path`（非 `.tool_input.file_path`）
- 编辑内容：`.tool_input.edit.old` / `.tool_input.edit.new`（StrReplaceFile）
- 工具输出：`.tool_output`（字符串，含 `is_error`、`output`、`message`、`display` 等）

---

## 3. Hook Dispatcher 协议（所有 AI Agent 必须遵守）

### 3.1 问题

Kimi CLI 仅支持全局配置（`~/.kimi/config.toml`），不支持工程级 hook 配置。全局 `[[hooks]]` 对所有项目生效，如果各项目各自注册 hook，会导致：
- 跨项目误触发（A 项目的 hook 在 B 项目中执行）
- 同一事件多个 hook 并行执行，结果不可预测

### 3.2 方案

全局只注册一个 **dispatcher 脚本**作为所有事件的唯一入口，由 dispatcher 读取 stdin JSON 中的 `cwd` 字段，按项目路径路由到对应的处理脚本。

**架构图**：
```
Kimi CLI
  │
  ├─ [PreToolUse]  ─┐
  ├─ [PostToolUse] ─┤
  ├─ [Stop]        ─┼──► ~/.kimi/hooks/dispatcher.sh <EVENT>
  ├─ [SessionEnd]  ─┤        │
  └─ [SessionStart]─┘        ├─ cwd 含 "redcap"  → redcap/tools/kimi-hook-handler.sh
                              ├─ cwd 含 "distill" → distill/scripts/kimi-hook-handler.sh
                              ├─ cwd 含 "xxx"     → xxx/hooks/handler.sh
                              └─ 未匹配            → exit 0（静默跳过）
```

**Dispatcher 位置**：`~/.kimi/hooks/dispatcher.sh`

### 3.3 config.toml 注册方式（全局唯一一份 hook 配置）

```toml
# ~/.kimi/config.toml — 所有事件统一路由到 dispatcher
[[hooks]]
event = "PreToolUse"
matcher = "WriteFile|StrReplaceFile"
command = "/Users/norven/.kimi/hooks/dispatcher.sh PreToolUse"
timeout = 5

[[hooks]]
event = "PostToolUse"
matcher = "WriteFile|StrReplaceFile"
command = "/Users/norven/.kimi/hooks/dispatcher.sh PostToolUse"
timeout = 3

[[hooks]]
event = "Stop"
command = "/Users/norven/.kimi/hooks/dispatcher.sh Stop"
timeout = 60

[[hooks]]
event = "SessionEnd"
command = "/Users/norven/.kimi/hooks/dispatcher.sh SessionEnd"
timeout = 60

[[hooks]]
event = "SessionStart"
command = "/Users/norven/.kimi/hooks/dispatcher.sh SessionStart"
timeout = 5
```

> 以上顺序与实际 `~/.kimi/config.toml` 一致。

### 3.4 各项目的接入规则（AI Agent 操作指南）

| 规则 | 说明 |
|------|------|
| **禁止** 直接在 config.toml 添加 `[[hooks]]` | 所有 hook 必须通过 dispatcher 路由 |
| **必须** 在 dispatcher.sh 的 `route()` 函数中添加 case 分支 | 格式：`*/project-name\|*/project-name/*)` |
| **必须** 将项目 hook 脚本放在项目目录内 | 如 `tools/kimi-hook-handler.sh` 或 `scripts/kimi-hook-handler.sh` |
| **必须** 从 stdin 读取 JSON | dispatcher 会 pipe JSON 到项目脚本，第一个参数是事件名 |
| **必须** 在脚本内部按事件名过滤 | 只处理自己关心的事件，其他事件 exit 0 |
| **建议** 脚本内检查 cwd 做二次确认 | 防止路径匹配歧义 |

### 3.5 如何在 dispatcher.sh 中添加新项目路由

打开 `~/.kimi/hooks/dispatcher.sh`，在 `route()` 函数的 case 语句中 `*)` 默认分支**之前**添加：

```bash
        # --- My Project ---
        */my-project|*/my-project/*)
            local script
            # 从 cwd 提取项目根目录（处理可能在子目录中的情况）
            script=$(echo "$CWD" | sed 's|\(.*my-project\).*|\1|')
            script="$script/tools/kimi-hook-handler.sh"
            if [[ -f "$script" ]]; then
                echo "$JSON" | bash "$script" "$EVENT"
                return $?
            fi
            ;;
```

**要点**：
- `*/my-project|*/my-project/*)`：匹配项目根目录及其所有子目录
- `sed 's|\(.*my-project\).*|\1|'`：从 cwd 中截取到项目根路径（即使 cwd 是子目录也能找到）
- `if [[ -f "$script" ]]`：脚本不存在时静默跳过，不报错
- `echo "$JSON" | bash "$script" "$EVENT"`：将完整 JSON 上下文通过 stdin 传给项目脚本，事件名作为 $1

### 3.6 项目 hook 脚本模板

```bash
#!/bin/bash
# tools/kimi-hook-handler.sh — 项目级 Kimi hook 处理器
EVENT="$1"
JSON=$(cat)

case "$EVENT" in
    Stop|SessionEnd)
        # 在此处理收尾逻辑
        ;;
    PreToolUse)
        # 在此处理工具调用前检查
        ;;
    *)
        # 不关心的事件，跳过
        ;;
esac
exit 0
```

---

## 4. RedCap 部署现状

### 4.1 已实现

| 组件 | 位置 | 功能 |
|------|------|------|
| Dispatcher | `~/.kimi/hooks/dispatcher.sh` | 全局路由，按 cwd 分发到项目脚本 |
| config.toml | `~/.kimi/config.toml` | 5 个事件注册到 Dispatcher |
| kimi-hook-handler.sh | `tools/kimi-hook-handler.sh` | RedCap 项目级处理器 |

### 4.2 hook-handler 逻辑

- **SessionStart**：捕获当前 `git HEAD` 到 `/tmp/redcap-kimi-initial-head`
- **Stop**：检测新 commit → 有则飞书通知（**不清理**临时文件，留给 SessionEnd 兜底）
- **SessionEnd**：检测新 commit → 有则飞书通知 → **清理**临时文件

通过「Stop 不清理 + SessionEnd 清理」实现**去重**：
- Stop 通知后更新了 HEAD → SessionEnd 对比发现无增量 → 不重复通知（✅ 当前未实现，见 §4.3）

### 4.3 待优化：Stop/SessionEnd 双触发去重

当前 `handle_session_end()` 在 Stop 和 SessionEnd 都会触发通知。正常退出时两个事件依次触发，导致**同一内容发两次飞书通知**。

**解法**：Stop 通知成功后将已通知的 HEAD 写入 `/tmp/redcap-kimi-last-notified-head`，SessionEnd 先检查此文件，若 HEAD 未变则跳过。

> 此优化为低优先级——重复通知不影响正确性，仅影响用户体验。

### 4.4 可靠性评估

Layer 0 可用（Stop + SessionEnd = 100% 确定性执行），事件覆盖面最广（13 种），需通过 Dispatcher 协议解决全局配置限制。

> `SessionEnd` 作为 `Stop` 的兜底：即使 Stop 因 `stop_hook_active` 反循环被跳过，SessionEnd 仍会在会话关闭时触发。
