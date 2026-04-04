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

```jsonc
// .claude/settings.json
{
  "hooks": {
    "Stop": [{ "command": "bash ./on-complete.sh" }],
    "PreToolUse": [{ "command": "..." }],
    "PostToolUse": [{ "command": "..." }],
    "InstructionsLoaded": [{ "command": "..." }]
  }
}
```

- `Stop` hook 在 Claude 结束时**确定性执行**——最适合 on_ALL_DONE 场景
- `InstructionsLoaded` 可用于审计哪些指令被加载
- **支持工程级配置**：`.claude/settings.json` 放在项目目录内，不影响其他项目
- **局限**：仅适用于 Claude Code CLI 环境，4 种事件类型

---

## 3. RedCap 部署建议

可利用 `Stop` hook 实现 100% 保证：
```jsonc
// 项目级 .claude/settings.json
{
  "hooks": {
    "Stop": [{
      "command": "bash ${PROJECT_DIR}/tools/redcap-on-complete.sh"
    }]
  }
}
```

**可靠性评估**：Layer 0 可用（Stop hook = 100% 确定性执行），是当前最可靠的宿主环境之一。
