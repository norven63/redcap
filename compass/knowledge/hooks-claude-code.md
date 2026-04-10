# Claude Code — Hooks 与指令注入详情

> 本文件从 [host-reliability.md](host-reliability.md) 拆分而来，记录 Claude Code 的指令注入机制和 Hook 能力。

---

## 1. 指令注入机制（`CLAUDE.md`）

| 维度 | 结论 |
|------|------|
| **注入方式** | 会话启动时作为 **user message** 注入（在 system prompt **之后**），不是 system prompt 本身 |
| **注入频率** | 会话开始一次 + `/compact` 后从磁盘重新读取并重注入 |
| **注入位置** | User message（优先级低于 system prompt） |
| **压缩后存活** | ✅ `/compact` 后从磁盘重读，内容不会丢失 |

> 官方原话（Anthropic Docs）：
> - "CLAUDE.md content is delivered as a **user message after the system prompt**, not as part of the system prompt itself."
> - "CLAUDE.md **fully survives compaction**."
> - "Claude reads it and tries to follow it, but **there's no guarantee of strict compliance**."

**`--append-system-prompt` 参数**：唯一能注入到真正 system prompt 级别的方式，但需每次启动时传入，适合脚本/自动化场景。

---

## 2. Hooks 能力

### 2.1 事件类型

Claude Code 支持 **24 种** hook 事件（截至 2026-04 官方文档）：

| 分类 | 事件 | 可阻止？ | 典型用途 |
|------|------|---------|---------|
| 生命周期 | `SessionStart` | 否 | 环境初始化、HEAD 捕获 |
| | `SessionEnd` | 否 | 清理、日志 |
| | `Stop` | ✅ | 收尾通知、质量门禁 |
| | `StopFailure` | 否 | 错误告警 |
| 工具 | `PreToolUse` | ✅ | 权限控制、安全审查 |
| | `PostToolUse` | 否（可反馈） | lint、测试 |
| | `PostToolUseFailure` | 否 | 失败日志 |
| | `PermissionRequest` | ✅ | 自动审批 |
| | `PermissionDenied` | 否 | 重试控制 |
| 用户 | `UserPromptSubmit` | ✅ | 提示词过滤 |
| 子Agent | `SubagentStart` / `SubagentStop` | 否 / ✅ | 子Agent监控 |
| 任务 | `TaskCreated` / `TaskCompleted` | ✅ | 任务门禁 |
| | `TeammateIdle` | ✅ | 质量检查 |
| 配置 | `ConfigChange` | ✅ | 审计 |
| | `InstructionsLoaded` | 否 | 指令审计 |
| 环境 | `CwdChanged` / `FileChanged` | 否 | 环境响应 |
| 压缩 | `PreCompact` / `PostCompact` | 否 | 日志 |
| MCP | `Elicitation` / `ElicitationResult` | ✅ | 自动应答 |
| Worktree | `WorktreeCreate` / `WorktreeRemove` | ✅ / 否 | VCS集成 |
| 通知 | `Notification` | 否 | 自定义通知 |

### 2.2 通信协议

- **输入**：所有事件通过 **stdin JSON** 传递上下文，包含 `session_id`、`cwd`、`transcript_path` 等公共字段
- **输出**：exit 0 = 成功（可输出 JSON 控制行为），exit 2 = 阻止（stderr 反馈给 Claude）
- **四种 Hook 类型**：`command`（shell）、`http`（POST）、`prompt`（LLM 单轮判断）、`agent`（子Agent 验证）

### 2.3 配置层级

| 位置 | 作用域 | 可提交 |
|------|--------|--------|
| `~/.claude/settings.json` | 用户级（所有项目） | 否 |
| `.claude/settings.json` | 项目级 | 是 |
| `.claude/settings.local.json` | 项目级（本地） | 否 |
| Managed policy | 组织级 | 是（管理员） |
| Skill/Agent frontmatter | 组件生命周期 | 是 |

### 2.4 配置格式（三层嵌套）

```jsonc
{
  "hooks": {
    "<EventName>": [           // 1. 事件类型
      {
        "matcher": "<regex>",  // 2. 过滤器（可选）
        "hooks": [             // 3. 处理器数组
          {
            "type": "command",
            "command": "/path/to/script.sh",
            "timeout": 600,    // 秒，默认 600
            "async": false     // true = 后台执行不阻塞
          }
        ]
      }
    ]
  }
}
```

---

## 3. RedCap 部署现状

### 3.1 Layer B（开发 RedCap 自身）

项目级 `.claude/settings.json` 配置，仅在 RedCap 自身 repo 生效：

```jsonc
// redcap/.claude/settings.json
{
  "hooks": {
    "InstructionsLoaded": [{
      "hooks": [{ "type": "command", "command": "bash tools/redcap-claude-hook-init.sh" }]
    }],
    "Stop": [{
      "hooks": [{ "type": "command", "command": "bash tools/redcap-claude-hook-stop.sh" }]
    }]
  }
}
```

| 脚本 | 触发事件 | 功能 |
|------|---------|------|
| `tools/redcap-claude-hook-init.sh` | InstructionsLoaded | 捕获初始 HEAD 到 `/tmp/redcap-claude-initial-head` |
| `tools/redcap-claude-hook-stop.sh` | Stop | 检测新 commit → 飞书通知 |

### 3.2 Layer A（RedCap 开发用户项目）

用户级 `~/.claude/settings.json` 配置，所有项目生效，通过 `state.yaml` 检测过滤：

```jsonc
// ~/.claude/settings.json（合并到现有配置中）
{
  "hooks": {
    "SessionStart": [{
      "hooks": [{ "type": "command", "command": "<REDCAP_DIR>/tools/redcap-layerA-session-start.sh" }]
    }],
    "Stop": [{
      "hooks": [{ "type": "command", "command": "<REDCAP_DIR>/tools/redcap-layerA-stop.sh" }]
    }],
    "SessionEnd": [{
      "hooks": [{ "type": "command", "command": "<REDCAP_DIR>/tools/redcap-layerA-session-end.sh" }]
    }]
  }
}
```

> ⚠ 将 `<REDCAP_DIR>` 替换为实际绝对路径。部署详见 [`layerA-hook-deploy.md`](../knowledge/layerA-hook-deploy.md)。

| 脚本 | 触发事件 | 功能 |
|------|---------|------|
| `tools/redcap-layerA-session-start.sh` | SessionStart | 僵尸标记清理 + 捕获初始 HEAD |
| `tools/redcap-layerA-stop.sh` | Stop | 三重过滤检测 ALL_DONE → 调用 `redcap-on-complete.sh` |
| `tools/redcap-layerA-session-end.sh` | SessionEnd | 清理 session 标记文件 |

**三重过滤机制**（防误触发）：

1. `开发手册/.workflow/state.yaml` 存在 → 确认是 RedCap 管理的项目
2. `current_state == ALL_DONE` → 确认流程已完成
3. `/tmp/redcap-layerA-notified-<session_id>` 不存在 → 确认本 session 未通知过

**可靠性评估**：Layer 0（Stop hook = 100% 确定性执行）。`on_ALL_DONE` 从 Layer 2（依赖 Dispatcher 记忆）提升至 Layer 0。
