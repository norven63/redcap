# Gemini CLI — Hooks 与指令注入详情

> 本文件从 [host-reliability.md](host-reliability.md) 拆分而来，记录 Gemini CLI 的指令注入机制和 Hook 能力。

---

## 1. 指令注入机制（`GEMINI.md`）

| 维度 | 结论 |
|------|------|
| **注入方式** | 所有 GEMINI.md 文件内容拼接后，**随每个 prompt 一起发送**给模型 |
| **注入频率** | **每次 prompt** |
| **注入位置** | 与 prompt 拼接（不是 system prompt） |
| **压缩后存活** | ✅ 每次 prompt 重发 |

> 官方原话（Gemini CLI Docs）："It loads various context files, **concatenates** the contents, and **sends them to the model with every prompt**."

**JIT 加载**：当工具访问某个目录时，自动扫描该目录的 GEMINI.md —— 目录级指令是按需动态注入的。

**`--system-prompt-file` 参数**：可注入到 system prompt 级别，优先级最高。

---

## 2. Hooks 能力（v0.36.0 实测验证）

> ⚠️ 历史注记：本框架曾根据源码审计将 Gemini CLI hooks 标记为"已实现但未集成"。2026-04-07 实测验证证实 hooks 在 v0.36.0 **已完全可用**——源码静态扫描遗漏了运行时加载机制，实测才是最终真相（L-28）。

| 层面 | 状态 | 说明 |
|------|------|------|
| **事件支持** | ✅ | 11 种事件（含 BeforeTool/AfterTool/SessionEnd 等） |
| **config 配置** | ✅ | `.gemini/settings.json`（项目级）/ `~/.gemini/settings.json`（全局） |
| **stdin/stdout 协议** | ✅ | JSON 输入，JSON 响应（`decision: allow/deny`） |
| **Matcher 正则** | ✅ | 支持正则（如 `"write_.*"`） |
| **多层级生效** | ✅ | 项目 > 用户全局 > 系统 > 扩展，优先级明确 |
| **安全 Fingerprinting** | ✅ | Hook 路径变更时 CLI 提示用户确认 |

### 支持的事件列表

| 事件 | 说明 |
|------|------|
| `SessionStart` | 会话开始 |
| `SessionEnd` | 会话结束 ← **Stop Hook 等价物** |
| `BeforeAgent` | Agent 回合开始前 |
| `AfterAgent` | Agent 回合结束后 |
| `BeforeModel` | LLM 调用前 |
| `AfterModel` | LLM 调用后 |
| `BeforeToolSelection` | 工具选择前 |
| `BeforeTool` | 工具执行前（支持 Matcher 正则） |
| `AfterTool` | 工具执行后（支持 Matcher 正则） |
| `PreCompress` | 上下文压缩前 |
| `Notification` | 通知事件 |

### 配置格式

配置文件位置（按优先级从高到低）：
1. 项目级：`.gemini/settings.json`
2. 用户全局：`~/.gemini/settings.json`
3. 系统全局：`/etc/gemini-cli/settings.json`
4. 扩展 Hook

```json
{
  "hooks": {
    "BeforeTool": [
      {
        "matcher": "run_shell_command",
        "hooks": [
          {
            "name": "redcap-tool-check",
            "type": "command",
            "command": "/path/to/hook-script.sh"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "matcher": "*",
        "hooks": [
          {
            "name": "redcap-cleanup",
            "type": "command",
            "command": "/path/to/on-session-end.sh"
          }
        ]
      }
    ]
  }
}
```

> ⚠️ 源码中存在 `enableHooks` 配置项（旧版默认 `false`）。实测未明确验证此开关的当前默认值——若 hooks 未触发，请检查是否需要显式设置 `"enableHooks": true`。

### stdin/stdout 协议

**stdin（CLI → Hook 脚本）**：JSON 格式，字段包括：
- `session_id`：当前会话 ID
- `hook_event_name`：事件名（如 `BeforeTool`）
- `tool_name`：工具名（BeforeTool/AfterTool 时存在）
- `tool_input`：工具输入参数（BeforeTool 时存在）

**stdout（Hook 脚本 → CLI）**：必须输出合法 JSON，例：
- `{"decision": "allow"}`：放行，继续执行
- `{"decision": "deny"}`：拦截，终止工具调用

> ⚠️ 调试信息必须重定向到 `stderr` 或写文件，输出到 stdout 会破坏 JSON 解析。

### 退出码

| 退出码 | 含义 | CLI 行为 |
|--------|------|---------|
| `0` | 成功 | 解析 stdout JSON，执行 decision |
| `2` | System Block（严重错误） | 立刻终止后续动作，将 stderr 内容显示给用户 |
| 其他 | 警告 | 显示警告信息，但继续执行原有动作 |

---

## 3. RedCap 部署建议

Gemini CLI hooks 已具备完整能力，可部署 Layer 0 防护，但**尚未部署**（⏳）。

**Layer B（开发 RedCap 自身）**：使用 `SessionEnd` 作为 Stop Hook 等价物：

```json
// redcap/.gemini/settings.json
{
  "hooks": [
    {
      "trigger": "SessionEnd",
      "command": "/absolute/path/to/redcap/tools/redcap-on-stop-review-gemini.sh"
    }
  ]
}
```

**Layer A（RedCap 开发用户项目）**：由 RedCap 在项目初始化时创建 `.gemini/settings.json`，使用 `SessionEnd` 实现收尾审计。

**可靠性评估**：已具备 Layer 0 能力，部署后与 Claude Code/Kimi CLI 看齐。

> ⚠️ 部署后必须用标记文件法做端到端验证（L-16）：确认 SessionEnd Hook 物理触发，不可假设"配置了就生效了"。
