# RedCap 框架级经验库（Framework Lessons Learned）

> 本文件记录跨项目可复用的经验教训。由 Dispatcher 在识别到高价值经验时手动归档。
> 项目级经验存放在各项目的 `开发手册/shared/lessons-learned.md`。

### 归档触发检查点

每轮框架变更完成后，Dispatcher 必须执行以下自检：

1. 本轮是否发现了**新的失败模式或反直觉行为**？→ 如果是，归档为 Lesson
2. 本轮是否验证了一个**之前文档中写错的假设**？→ 如果是，归档为 Lesson
3. 本轮使用的**工作方法本身**是否值得复用？→ 如果是，归档为方法论 Lesson

> 此检查点的目的：防止"做了但没沉淀"的遗漏。Lesson 的价值在于跨项目复用，漏掉一条可能导致下个项目踩同样的坑。

---

### L-1: Agent 文件路径必须使用绝对路径或明确基准
- **场景**：QA Agent 将 `last-result.json` 写到项目根目录而非 `开发手册/.workflow/` 下
- **根因**：Agent 对"当前工作目录"的理解与 Dispatcher 预期不一致，相对路径基准不同
- **经验规则**：Prompt 中涉及文件读写路径时，一律使用从项目根目录起算的完整相对路径，不依赖 Agent 自行推断基准目录
- **来源**：AI-Coding-Museum 冒烟测试, QA Agent, 2025-07

### L-2: Prompt 中必须包含交付物文件清单
- **场景**：Agent 完成工作但遗漏部分交付文件，Dispatcher 无法可靠验证
- **根因**：Prompt 仅描述任务目标，未明确列出 Agent 必须写入的文件列表
- **经验规则**：每个 Agent 的 Prompt 末尾必须附带 `## 必须写入的文件` 清单，Dispatcher 据此做交付物完整性校验（§5.7）
- **来源**：AI-Coding-Museum 冒烟测试, 多角色, 2025-07

### L-3: Shell 重定向符构造文件路径时可能创建异常目录
- **场景**：Agent 执行 Shell 命令写入文件时，`>` 重定向符与绝对路径拼接（如 `>/abs/path`），在项目根目录创建了名为 `>` 的目录
- **根因**：Shell 命令中 `>` 与路径之间缺少空格，或 Agent 构造命令时未正确转义，导致 `>` 被作为目录名而非重定向操作符
- **经验规则**：所有文件写入操作必须使用 Agent 内建的 Write 工具，严禁通过 Shell 重定向 `>` / `>>` 写文件。参见 agent-adapters.md §10
- **来源**：TRPG-Server 实测, Step 1, 2026-03

### L-4: Agent Fallback 深度不足导致铁律系统性违反
- **场景**：gemini 频控 + claude-code 幻觉，2 级 Fallback 全部失败后 Dispatcher 被迫手动代劳，从步骤 3 到步骤 5 共 9 个 Session 全部为 dispatcher-manual
- **根因**：Fallback 路由只有 2 级（首选 + 1 个备选），且没有新步骤自动重置失败计数的机制，Agent 一旦被标记失败就永远不再尝试
- **经验规则**：① Fallback 路由至少 3 级深度 ② 每步自动重置 Agent 健康状态 ③ 增加用户授权降级路径替代绝对禁止代劳
- **来源**：TRPG-Server 实测, Step 3-5, 2026-03

### L-5: Agent 超时应优先从自身调用方式排查
- **场景**：多次调用 Agent 超时，初步判断为 Agent 工具质量问题
- **根因**：实际多为 Prompt 过长、交互式阻塞（sandbox 确认、权限确认）、工作目录错误等自身调用问题
- **经验规则**：Agent 超时时按以下顺序排查：Prompt 长度 → 交互式阻塞参数 → 工作目录 → Session 恢复 → 网络代理 → 最后才怀疑 Agent 工具质量
- **来源**：TRPG-Server 实测, 全程, 2026-03

### L-6: 模型检测应在项目初始化时完成并缓存
- **场景**：Dispatcher 不知道 claude-code 背后是 Kimi 2.5（SiliconFlow 代理），导致路由决策基于 CLI 名而非模型能力
- **根因**：路由表硬编码 CLI 名称，不感知底层模型
- **经验规则**：项目初始化时检测所有 CLI 的底层模型，结果缓存到 agent-registry.yaml，路由决策基于 `{cli}&{model}` 标识
- **来源**：TRPG-Server 实测, 全程, 2026-03

### L-7: Gemini `--approval-mode auto_edit` 在 headless 模式会永久挂起
- **场景**：gemini Agent 执行需要 Shell 命令的任务（如运行测试、安装依赖）时超时失败
- **根因**：`--approval-mode auto_edit` 仅自动审批文件编辑操作，Shell 命令仍弹出 `[Y/n]` 交互确认。在 headless/非交互模式下，无人应答导致 Agent 永久挂起直至超时
- **经验规则**：gemini CLI 必须使用 `--yolo` 而非 `--approval-mode auto_edit`。`--yolo` 自动审批所有工具操作（含文件编辑和 Shell 命令），是 headless 模式唯一可靠的参数
- **来源**：CLI 实测验证, gemini 0.35.3, 2026-03

### L-8: 框架变更必须"先测再改"——实测驱动而非假设驱动
- **场景**：第四轮优化中，通过实际运行 3 个 CLI（gemini/kimi/claude）发现模型名全错、`--approval-mode auto_edit` 导致挂起、claude `--session-id` 能力未知等关键问题——这些问题仅靠读文档无法发现
- **根因**：之前的框架文档基于 CLI 官方文档和推测编写，未做实际验证。CLI 的真实行为（如 gemini 实际用 flash 而非 pro、claude 背后是 Kimi K2.5）与文档假设存在显著偏差
- **经验规则**：任何涉及 Agent 调用方式的变更，必须遵循"实测 → 记录 → 再改文档"的顺序：① 先用真实 CLI 命令跑冒烟测试 ② 记录实际返回值和行为 ③ 基于实测结果修改框架文档。严禁仅凭文档假设修改调用参数
- **来源**：RedCap 第四轮优化, CLI 全面审计, 2026-03

### L-9: 长任务上下文压缩导致框架规则退化——必须用文件重读对冲
- **场景**：长任务中 SKILL.md 的 hooks 细节、交付物校验规则、Fallback 路由优先级等逐渐被压缩丢失，Dispatcher 行为退化（如忘记飞书通知、跳过校验步骤）
- **根因**：SKILL.md 在 skill 触发时一次性读入上下文，之后全靠上下文记忆存活。LLM 摘要压缩会保留"有 hooks 机制"的概念但丢失具体触发条件和动作细节
- **经验规则**：① 所有关键规则必须有"检查点重读"机制（`read_file` 重新注入最新上下文位置）② 重读频率以角色切换为主检查点 ③ 待办事项持久化到 state.yaml 而非依赖上下文记忆 ④ 不可压缩的规则提升为系统级指令（copilot-instructions.md）
- **来源**：RedCap 防退化机制设计, 2026-04

### L-10: 跨工具指令文件必须用索引模式而非内容复制
- **场景**：为 Claude Code 和 Gemini CLI 创建系统级指令文件（CLAUDE.md / GEMINI.md），直接复制了 copilot-instructions.md 中的 R1-R6 规则全文
- **根因**：未遵守"单一权威来源"原则。多份内容副本必然漂移——修改 CONTRIBUTING.md 后需手动同步三个文件，遗漏是必然的
- **经验规则**：① 工具特定指令文件只写"索引 + 工具特有语法"，规则内容统一维护在 CONTRIBUTING.md ② Claude Code 和 Gemini CLI 均支持 `@file` 原生导入语法，应优先使用（工具层面保证加载，不依赖 Agent 是否遵守 read_file 指令） ③ 文件位置必须查官方文档验证，不可凭记忆假设（违反 L-8 同理）
- **来源**：跨 Agent 工具兼容性实现, 2026-04
