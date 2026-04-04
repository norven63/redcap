# Kimi CLI — Hooks 与指令注入详情

> 本文件从 [host-reliability.md](host-reliability.md) 拆分而来，记录 Kimi CLI 的 Hook 能力、实测验证结果及 Dispatcher 协议。

---

## 1. Hooks 能力

```toml
# ~/.kimi/config.toml
[[hooks]]
event = "Stop"
command = "bash ./tools/redcap-on-complete.sh"

[[hooks]]
event = "SessionEnd"
matcher = ""
command = "bash ./tools/redcap-on-complete.sh"
```

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

[[hooks]]
event = "PreToolUse"
matcher = "WriteFile|StrReplaceFile"
command = "/Users/norven/.kimi/hooks/dispatcher.sh PreToolUse"
timeout = 5

[[hooks]]
event = "PostToolUse"
matcher = "WriteFile|StrReplaceFile"
command = "/Users/norven/.kimi/hooks/dispatcher.sh PostToolUse"
timeout = 5
```

### 3.4 各项目的接入规则（AI Agent 操作指南）

| 规则 | 说明 |
|------|------|
| **禁止** 直接在 config.toml 添加 `[[hooks]]` | 所有 hook 必须通过 dispatcher 路由 |
| **必须** 在 dispatcher.sh 的 `route()` 函数中添加 case 分支 | 格式：`*/project-name\|*/project-name/*)` |
| **必须** 将项目 hook 脚本放在项目目录内 | 如 `tools/kimi-hook-handler.sh` 或 `scripts/kimi-hook-handler.sh` |
| **必须** 从 stdin 读取 JSON | dispatcher 会 pipe JSON 到项目脚本，第一个参数是事件名 |
| **必须** 在脚本内部按事件名过滤 | 只处理自己关心的事件，其他事件 exit 0 |
| **建议** 脚本内检查 cwd 做二次确认 | 防止路径匹配歧义 |

### 3.5 项目 hook 脚本模板

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

## 4. RedCap 部署建议

可利用 `Stop` + `SessionEnd` 双 hook 通过 Dispatcher 实现 100% 保证。

> `SessionEnd` 作为 `Stop` 的兜底：即使 Stop 因 `stop_hook_active` 反循环被跳过，SessionEnd 仍会在会话关闭时触发。

**可靠性评估**：Layer 0 可用（Stop + SessionEnd = 100% 确定性执行），事件覆盖面最广（13 种），但需通过 Dispatcher 协议解决全局配置限制。
