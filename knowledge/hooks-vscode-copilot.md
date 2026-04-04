# VS Code Copilot — Hooks 与指令注入详情

> 本文件从 [host-reliability.md](host-reliability.md) 拆分而来，记录 VS Code Copilot 的指令注入机制和 Hook 能力。

---

## 1. 指令注入机制（`copilot-instructions.md`）

| 维度 | 结论 |
|------|------|
| **注入方式** | VS Code 在构造**每一次 API 请求**时，自动将 `.github/copilot-instructions.md` 作为 context 附件发送 |
| **注入频率** | **每轮对话**（不是只在会话开始） |
| **注入位置** | Context/附件，不是 system prompt |
| **压缩后存活** | ✅ 因为每轮重新注入，不依赖上下文记忆 |

> 官方原话（VS Code Docs）："Instructions are **automatically included in every chat request**"

**SKILL.md / Skill 文件**：仅在 skill 触发时 `read_file` 一次性加载到上下文，后续不自动重注入。这就是 §5.12 防退化机制存在的原因。

---

## 2. Hooks 能力

```jsonc
// .vscode/settings.json
{
  "chat.agent.hooks": {
    "afterEdit": {
      "command": "npm run lint ${file}"
    }
  }
}
```

- 在 Agent 生命周期点（文件编辑后等）自动运行 shell 命令
- 官方原话："Hooks **guarantee** that your code runs at defined lifecycle points"
- **局限**：hook 点有限，目前无 "onSessionEnd" 或 "onTaskComplete" 专用 hook

---

## 3. RedCap 部署建议

当前无 "onTaskComplete" 专用 hook，退守为：
1. SKILL.md `on_ALL_DONE` 中用**极简、高亮**措辞写关键步骤（减少 3 个动作到 1 个脚本调用）
2. `copilot-instructions.md` 中保持提醒（每轮重注入）
3. 下次启动时 §5.1 审计未完成动作

**可靠性评估**：无 Layer 0（宿主 Hook），依赖 Layer 1-3 补救。
