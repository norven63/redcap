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

## 2. Hooks 能力（v0.36.0 源码深度审计）

| 层面 | 状态 | 证据 |
|------|------|------|
| **Schema 定义** | ✅ 存在 | `settingsSchema.js`: `enableHooks`（默认 false）、`hooks` 配置对象 |
| **Hooks 库** | ✅ 完整实现 | `@google/gemini-cli-core/hooks/`: `hookRunner.js`（spawn shell）、`hookRegistry.js`、`hookPlanner.js`、`hookAggregator.js`、`types.js` |
| **事件类型** | ✅ 11 种已定义 | `BeforeTool`、`AfterTool`、`BeforeAgent`、`AfterAgent`、`SessionStart`、`SessionEnd`、`PreCompress`、`BeforeModel`、`AfterModel`、`BeforeToolSelection`、`Notification` |
| **Agent 循环集成** | ❌ **未接入** | 整个代码库中，**没有任何非测试文件** import 或实例化 `HookRunner`/`HookRegistry`；`config.js` 标注 `// TODO: loading of hooks based on workspace trust` |
| **MessageBus** | ⚠️ 仅用于 policy | `MessageBus` 存在但只服务于 tool confirmation（ALLOW/DENY/ASK_USER），未连接到 hooks |

**结论**：Gemini CLI 的 hooks 是**已实现但未集成**的独立库——hookRunner 通过 `spawn` 执行 shell 命令、支持退出码 0/1/2、并行执行、60s 超时，架构已就绪。一旦 Google 将其接入 agent 循环，可快速适配 RedCap。当前版本（v0.36.0）**无法提供有效的 hooks 执行**。

---

## 3. RedCap 部署建议

无原生 hooks，退守为：
1. GEMINI.md 中保持关键提醒（每次 prompt 重发）
2. 下次启动审计

**可靠性评估**：无 Layer 0（宿主 Hook），依赖 Layer 1-3 补救。待 Google 接入 hooks 后可快速升级。
