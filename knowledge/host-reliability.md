# 宿主 Agent 可靠性调研报告

> **调研日期**：2026-04  
> **调研背景**：RedCap E2E 测试中 `on_ALL_DONE` 飞书通知被遗漏（L-9 复现），需评估宿主 Agent 的指令持久性和可靠性保障机制，为 RedCap 的关键动作防遗漏策略提供决策依据。  
> **核心发现**：指令注入物理上每轮都在，但 LLM attention 衰减使执行率随对话长度下降。唯一 100% 保证的是 Hooks（绕过 LLM 的 shell 命令）。4 个宿主工具中 Claude Code 和 Kimi CLI 支持 Hooks。

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
- JIT 加载可部分弥补（工具访问目录时自动扫描 GEMINI.md）

**Hooks 状态（v0.36.0 源码深度审计）**：

| 层面 | 状态 | 证据 |
|------|------|------|
| **Schema 定义** | ✅ 存在 | `settingsSchema.js`: `enableHooks`（默认 false）、`hooks` 配置对象 |
| **Hooks 库** | ✅ 完整实现 | `@google/gemini-cli-core/hooks/`: `hookRunner.js`（spawn shell）、`hookRegistry.js`、`hookPlanner.js`、`hookAggregator.js`、`types.js` |
| **事件类型** | ✅ 11 种已定义 | `BeforeTool`、`AfterTool`、`BeforeAgent`、`AfterAgent`、`SessionStart`、`SessionEnd`、`PreCompress`、`BeforeModel`、`AfterModel`、`BeforeToolSelection`、`Notification` |
| **Agent 循环集成** | ❌ **未接入** | 整个代码库中，**没有任何非测试文件** import 或实例化 `HookRunner`/`HookRegistry`；`config.js` 标注 `// TODO: loading of hooks based on workspace trust` |
| **MessageBus** | ⚠️ 仅用于 policy | `MessageBus` 存在但只服务于 tool confirmation（ALLOW/DENY/ASK_USER），未连接到 hooks |

**结论**：Gemini CLI 的 hooks 是**已实现但未集成**的独立库——hookRunner 通过 `spawn` 执行 shell 命令、支持退出码 0/1/2、并行执行、60s 超时，架构已就绪。一旦 Google 将其接入 agent 循环，可快速适配 RedCap。当前版本（v0.36.0）**无法提供有效的 hooks 执行**。

### 3.4 Kimi CLI Hooks

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
- **局限**：Beta 阶段（截至 2026-04），API 可能变更

#### 实测验证（v1.30.0, 2026-04-04）

使用标记文件法实测 4 种事件，**全部确认可用**：

| 事件 | 触发时机 | stdin JSON 关键字段 | 验证结果 |
|------|----------|---------------------|----------|
| `SessionStart` | 会话创建后立即触发 | `session_id`, `cwd`, `source: "startup"` | ✅ |
| `PostToolUse` | 工具调用完成后 | `tool_name`, `tool_input`, `tool_output`, `tool_call_id` | ✅ |
| `Stop` | Agent 轮次结束 | `session_id`, `stop_hook_active: false` | ✅ |
| `SessionEnd` | 会话关闭时 | `session_id`, `reason: "exit"` | ✅ |

**关键发现**：
- 触发顺序严格为 `SessionStart → PostToolUse(×N) → Stop → SessionEnd`
- `--print` 模式下 `Stop` 不触发（直接跳到 `SessionEnd`），`-p` 模式正常触发
- stdin JSON 包含完整上下文（session_id、cwd、工具输入/输出等），可用于条件判断
- `stop_hook_active` 字段可用于检测是否处于防循环状态
- 环境变量：hook 脚本中无 Kimi 特有环境变量注入，事件名通过 stdin JSON 的 `hook_event_name` 传递

> 官方文档：https://moonshotai.github.io/kimi-cli/zh/customization/hooks.html

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

#### Kimi CLI 环境

可利用 `Stop` + `SessionEnd` 双 hook 实现 100% 保证：
```toml
# ~/.kimi/config.toml（或项目级 .kimi/config.toml）
[[hooks]]
event = "Stop"
command = "bash tools/redcap-on-complete.sh $PROJECT_DIR $INITIAL_HEAD $PROJECT_NAME"
timeout = 60

[[hooks]]
event = "SessionEnd"
command = "bash tools/redcap-on-complete.sh $PROJECT_DIR $INITIAL_HEAD $PROJECT_NAME"
timeout = 60
```

> `SessionEnd` 作为 `Stop` 的兜底：即使 Stop 因 `stop_hook_active` 反循环被跳过，SessionEnd 仍会在会话关闭时触发。

### 4.3 收尾脚本封装（已实现）

关键 hook 的多步动作已封装为确定性 shell 脚本：

| 脚本 | 对应 Hook | 封装的动作 | 调用示例 |
|------|----------|-----------|---------|
| `tools/redcap-on-complete.sh` | `on_ALL_DONE` | ① 清除 .workflow/ 临时文件（§5.9）② 输出交付摘要 ③ 飞书通知（§5.11） | `bash tools/redcap-on-complete.sh <project_dir> <initial_head> <project_name>` |
| `tools/redcap-on-qa-pass.sh` | `on_QA_PASS` | ① git add -A && git commit（按 commit-standards.md）② 检查 lesson 字段 | `bash tools/redcap-on-qa-pass.sh <project_dir> <type> <scope> <message> [body]` |

**好处**：Dispatcher 只需记住"调一个脚本"，而不是"记住 N 个步骤每步的细节"。

### 4.4 下次启动审计（Layer 3）

在 §5.1 启动流程中增加检查（已实现为 §5.1 步骤 2.5）：
- 若 `pending_actions` 非空 → 说明上次会话遗漏了收尾动作 → 立即补执行
- 这一层在新会话第一轮执行，attention 最强，最可靠

### 4.5 工作流节点→防护措施映射

基于系统性梳理，将 RedCap 所有工作流节点按可靠性风险分类：

#### Category 1 — 关键节点（必须 100% 执行）

| 节点 | 风险 | 已有防护 | 剩余风险 |
|------|------|---------|---------|
| `on_ALL_DONE`（清理+摘要+飞书） | E2E 已实际遗漏（L-9） | ✅ 脚本封装 + pending_actions + 启动审计 + Claude Stop hook + Kimi Stop/SessionEnd hook | 低：仅 VS Code/Gemini 无 hook，依赖 Layer 2+3 |
| `on_QA_PASS`（git commit） | 遗漏则代码可能丢失 | ✅ 脚本封装 + pending_actions | 低：pending_actions 原子写入保障 |
| `§5.13 pending_actions 写入` | 递归遗忘问题 | ✅ 原子写入铁律（与 current_state 同一次写入） | 中：仍为 LLM 执行，但降为单一操作 |

#### Category 2 — 可恢复节点（遗漏可补救）

| 节点 | 恢复方式 |
|------|---------|
| §5.7 交付物校验 | 下轮 QA 会发现 |
| §5.5 Fallback 路由 | Agent 失败自动触发 |
| §5.8 经验沉淀 | 手动补录，不阻塞流程 |

#### Category 3 — 已天然安全的节点

| 节点 | 安全原因 |
|------|---------|
| §5.2 步骤 1 读 state.yaml | 事件循环首步，attention 最强 |
| §5.3 状态解析 | 机械操作，不依赖记忆 |
| §5.6 Session 管理 | 查询型操作，幂等 |

---

## 5. 总结

| 结论 | 详情 |
|------|------|
| **指令注入是可靠的** | 三个工具都做到了每轮/每次物理注入 |
| **LLM 执行是概率性的** | 随对话长度必然衰减，无法 100% |
| **唯一 100% 保证是 Hooks** | 绕过 LLM，宿主程序直接执行 shell（Claude Code、Kimi CLI 均支持） |
| **RedCap 最佳策略** | 用脚本封装关键动作 + 宿主 Hooks（如有）+ 下次启动审计 |
| **Hook 覆盖率** | 4 个宿主中 2 个有 Hooks（Claude Code: Stop; Kimi CLI: Stop+SessionEnd 等 13 种），2 个无（VS Code Copilot、Gemini CLI） |
