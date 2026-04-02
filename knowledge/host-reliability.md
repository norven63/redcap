# 宿主 Agent 可靠性调研报告

> **调研日期**：2026-04  
> **调研背景**：RedCap E2E 测试中 `on_ALL_DONE` 飞书通知被遗漏（L-9 复现），需评估宿主 Agent 的指令持久性和可靠性保障机制，为 RedCap 的关键动作防遗漏策略提供决策依据。  
> **核心发现**：指令注入物理上每轮都在，但 LLM attention 衰减使执行率随对话长度下降。唯一 100% 保证的是 Hooks（绕过 LLM 的 shell 命令）。

---

## 1. 三个宿主工具的指令注入机制

### 1.1 VS Code Copilot（`copilot-instructions.md`）

| 维度 | 结论 |
|------|------|
| **注入方式** | VS Code 在构造**每一次 API 请求**时，自动将 `.github/copilot-instructions.md` 作为 context 附件发送 |
| **注入频率** | **每轮对话**（不是只在会话开始） |
| **注入位置** | Context/附件，不是 system prompt |
| **压缩后存活** | ✅ 因为每轮重新注入，不依赖上下文记忆 |

> 官方原话（VS Code Docs）："Instructions are **automatically included in every chat request**"

**SKILL.md / Skill 文件**：仅在 skill 触发时 `read_file` 一次性加载到上下文，后续不自动重注入。这就是 §5.12 防退化机制存在的原因。

### 1.2 Claude Code（`CLAUDE.md`）

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

### 1.3 Gemini CLI（`GEMINI.md`）

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

## 2. 执行可靠性的真正瓶颈

### 2.1 注入 vs 执行的区别

| 层面 | 三个工具的表现 | 100% 保证？ |
|------|--------------|------------|
| **物理注入**（文本是否在 LLM 输入中） | 三个工具均做到每轮/每次重注入 | ✅ 是 |
| **LLM 执行**（是否遵从指令） | 受 attention 衰减影响 | ❌ 不可能 |

### 2.2 Attention 衰减效应

虽然指令每轮物理存在，但 LLM 在长对话中遵从度下降：

1. **Context window 稀释**：对话越长，指令在 context 中的相对权重越低
2. **Lost in the Middle**：LLM 对 context 中间位置内容的 attention 最低（首尾效应）
3. **任务聚焦偏移**：LLM 越来越关注近期对话内容，远处的指令"淡化"

**经验估算**（基于 RedCap E2E 测试观察）：

| 对话长度 | 指令遵从率（估算） |
|---------|-------------------|
| 1-5 轮 | ~95%+ |
| 6-15 轮 | ~85-90% |
| 15-30 轮 | ~70-80% |
| 30+ 轮 | ~60% 以下 |

> RedCap 完整流程通常在 20-40 轮，恰好处于遵从率显著下降的区间。

---

## 3. 宿主工具提供的确定性机制（Hooks）

**Hooks 是唯一能 100% 保证执行的机制**——因为它由宿主程序直接执行 shell 命令，完全绕过 LLM。

### 3.1 VS Code Copilot Hooks

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

### 3.2 Claude Code Hooks

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
- **局限**：仅适用于 Claude Code CLI 环境

### 3.3 Gemini CLI

- `--system-prompt-file` 可注入 system prompt 级指令（最高优先级）
- 无原生 hooks 机制（截至 v0.36.0）
- JIT 加载可部分弥补（工具访问目录时自动扫描 GEMINI.md）

---

## 4. 对 RedCap 的部署建议

### 4.1 防遗漏策略（三层防御修正版）

基于调研结果，修正可靠性估算：

| 层 | 机制 | 可靠性 | 说明 |
|----|------|--------|------|
| **Layer 2** | SKILL.md `on_ALL_DONE` hooks | ~60-70% | 长任务中 attention 衰减，Dispatcher 可能遗漏 |
| **Layer 1** | 系统级指令提醒（copilot-instructions.md / CLAUDE.md） | 补救率 ~30-50% | 每轮都在但可能被忽视 |
| **Layer 3** | 下次启动审计 | ~95-100% | 新会话第一轮，attention 最强 |
| **Layer 0** | **宿主 Hooks**（如有） | **100%** | 绕过 LLM，确定性执行 |

### 4.2 各环境的推荐配置

**原则**：将关键不可遗漏动作（飞书通知、收尾清理）封装为单一脚本，降低 LLM 记忆负担。

#### VS Code Copilot 环境

当前无 "onTaskComplete" 专用 hook，退守为：
1. SKILL.md `on_ALL_DONE` 中用**极简、高亮**措辞写关键步骤（减少 3 个动作到 1 个脚本调用）
2. `copilot-instructions.md` 中保持提醒（每轮重注入）
3. 下次启动时 §5.1 审计未完成动作

#### Claude Code 环境

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

#### Gemini CLI 环境

无原生 hooks，退守为：
1. GEMINI.md 中保持关键提醒（每次 prompt 重发）
2. 下次启动审计

### 4.3 收尾脚本封装（降低 LLM 记忆负担）

将 on_ALL_DONE 的 3 个动作封装为 1 个脚本：

```bash
# tools/redcap-on-complete.sh
# 用途：on_ALL_DONE 收尾动作一站式执行
# 参数：$1 = 项目名  $2 = 初始 commit hash（可选）
```

脚本内容应包含：
1. 清除 `.workflow/` 临时文件（§5.9）
2. 飞书通知（§5.11，附带 commit 记录）
3. 输出最终摘要到 stdout

**好处**：Dispatcher 只需记住"调一个脚本"，而不是"记住 3 个步骤每步的细节"。

### 4.4 下次启动审计（Layer 3）

在 §5.1 启动流程中增加检查：
- 若 `current_state == ALL_DONE` 且 `pending_actions` 非空 → 说明上次遗漏了收尾动作 → 立即补执行
- 这一层在新会话第一轮执行，attention 最强，最可靠

---

## 5. 总结

| 结论 | 详情 |
|------|------|
| **指令注入是可靠的** | 三个工具都做到了每轮/每次物理注入 |
| **LLM 执行是概率性的** | 随对话长度必然衰减，无法 100% |
| **唯一 100% 保证是 Hooks** | 绕过 LLM，宿主程序直接执行 shell |
| **RedCap 最佳策略** | 用脚本封装关键动作 + 宿主 Hooks（如有）+ 下次启动审计 |
| **不应过度依赖指令文本** | L-9 的根因不是"指令丢失"而是"指令被忽视" |
