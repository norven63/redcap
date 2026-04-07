# RedCap 框架级经验库（Framework Lessons Learned）

> 本文件记录跨项目可复用的经验教训。由 Dispatcher 在识别到高价值经验时手动归档。
> 项目级经验存放在各项目的 `开发手册/shared/lessons-learned.md`。

### 归档触发检查点

每轮框架变更完成后，Dispatcher 必须执行以下自检：

1. 本轮是否发现了**新的失败模式或反直觉行为**？→ 如果是，归档为 Lesson
2. 本轮是否验证了一个**之前文档中写错的假设**？→ 如果是，归档为 Lesson
3. 本轮使用的**工作方法本身**是否值得复用？→ 如果是，归档为方法论 Lesson

> 此检查点的目的：防止"做了但没沉淀"的遗漏。Lesson 的价值在于跨项目复用，漏掉一条可能导致下个项目踩同样的坑。

### 字段说明

每条 Lesson 包含以下元数据字段：

| 字段 | 含义 | 取值 |
|------|------|------|
| **影响度** | 踩中后果的严重程度 | `high`（阻塞流程/数据损失）、`medium`（浪费 >5min）、`low`（小不便） |
| **复现次数** | 同一问题被独立触发的累计次数 | 整数，初始 = 1，每次独立复现 +1 |
| **最后命中** | 最近一次实际触发或被参考的日期 | `YYYY-MM` 格式 |

### 容量管理与归档策略

**触发条件**：`lessons.md` 行数 > 300（约 15-20 条活跃经验，LLM 上下文友好）

**评分公式**（仅用于排序，不需精确计算）：

```
score = impact_weight × recency_decay × frequency_boost

impact_weight:   high=4, medium=2, low=1
recency_decay:   1.0 if <6mo, 0.6 if 6-12mo, 0.3 if >12mo（基于最后命中）
frequency_boost: min(复现次数, 5) / 5  → [0.2, 1.0]
```

**处置规则**：
- `score ≥ 1.0` → 保留在本文件（活跃层）
- `score < 1.0` → 移入 `knowledge/lessons-archive.md`（归档层，不自动加载到上下文）
- **豁免**：`影响度 = high` 的条目永不自动归档，只能由人工手动降级
- 归档层不设删除——磁盘成本忽略不计，唯一成本是"是否占上下文"
- 归档条目如再次复现，应"复活"回活跃层并 `复现次数 +1`

---

### L-1: Agent 文件路径必须使用绝对路径或明确基准
- **场景**：QA Agent 将 `last-result.json` 写到项目根目录而非 `开发手册/.workflow/` 下
- **根因**：Agent 对"当前工作目录"的理解与 Dispatcher 预期不一致，相对路径基准不同
- **经验规则**：Prompt 中涉及文件读写路径时，一律使用从项目根目录起算的完整相对路径，不依赖 Agent 自行推断基准目录
- **来源**：AI-Coding-Museum 冒烟测试, QA Agent
- **发现日期**：2025-07
- **影响度**：medium
- **复现次数**：1
- **最后命中**：2025-07

### L-2: Prompt 中必须包含交付物文件清单
- **场景**：Agent 完成工作但遗漏部分交付文件，Dispatcher 无法可靠验证
- **根因**：Prompt 仅描述任务目标，未明确列出 Agent 必须写入的文件列表
- **经验规则**：每个 Agent 的 Prompt 末尾必须附带 `## 必须写入的文件` 清单，Dispatcher 据此做交付物完整性校验（§5.7）
- **来源**：AI-Coding-Museum 冒烟测试, 多角色
- **发现日期**：2025-07
- **影响度**：medium
- **复现次数**：1
- **最后命中**：2025-07

### L-3: Shell 重定向符构造文件路径时可能创建异常目录
- **场景**：Agent 执行 Shell 命令写入文件时，`>` 重定向符与绝对路径拼接（如 `>/abs/path`），在项目根目录创建了名为 `>` 的目录
- **根因**：Shell 命令中 `>` 与路径之间缺少空格，或 Agent 构造命令时未正确转义，导致 `>` 被作为目录名而非重定向操作符
- **经验规则**：所有文件写入操作必须使用 Agent 内建的 Write 工具，严禁通过 Shell 重定向 `>` / `>>` 写文件。参见 agent-adapters.md §10
- **来源**：TRPG-Server 实测, Step 1
- **发现日期**：2026-03
- **影响度**：medium
- **复现次数**：1
- **最后命中**：2026-03

### L-4: Agent Fallback 深度不足导致铁律系统性违反
- **场景**：gemini 频控 + claude-code 幻觉，2 级 Fallback 全部失败后 Dispatcher 被迫手动代劳，从步骤 3 到步骤 5 共 9 个 Session 全部为 dispatcher-manual
- **根因**：Fallback 路由只有 2 级（首选 + 1 个备选），且没有新步骤自动重置失败计数的机制，Agent 一旦被标记失败就永远不再尝试
- **经验规则**：① Fallback 路由至少 3 级深度 ② 每步自动重置 Agent 健康状态 ③ 增加用户授权降级路径替代绝对禁止代劳
- **落地状态**：✅ 已通过 agent-adapters.md §6 两层降级（Model→CLI）+ §6.4 健康追踪 + §6.5 用户授权降级 全部落地
- **来源**：TRPG-Server 实测, Step 3-5
- **发现日期**：2026-03
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-03

### L-5: Agent 超时应优先从自身调用方式排查
- **场景**：多次调用 Agent 超时，初步判断为 Agent 工具质量问题
- **根因**：实际多为 Prompt 过长、交互式阻塞（sandbox 确认、权限确认）、工作目录错误等自身调用问题
- **经验规则**：Agent 超时时按以下顺序排查：Prompt 长度 → 交互式阻塞参数 → 工作目录 → Session 恢复 → 网络代理 → 最后才怀疑 Agent 工具质量
- **来源**：TRPG-Server 实测, 全程
- **发现日期**：2026-03
- **影响度**：medium
- **复现次数**：2
- **最后命中**：2026-04

### L-6: 模型检测应在项目初始化时完成并缓存
- **场景**：Dispatcher 不知道 claude-code 背后是 Kimi 2.5（SiliconFlow 代理），导致路由决策基于 CLI 名而非模型能力
- **根因**：路由表硬编码 CLI 名称，不感知底层模型
- **经验规则**：项目初始化时检测所有 CLI 的底层模型，结果缓存到 agent-registry.yaml，路由决策基于 `{cli}&{model}` 标识。**已实现**：`tools/redcap-detect-agents.sh`（轻检测 + 全量检测 + mtime 缓存）+ `knowledge/model-capability-matrix.yaml`（能力矩阵）→ 动态路由算法（agent-adapters.md §1.3）
- **来源**：TRPG-Server 实测, 全程
- **发现日期**：2026-03
- **影响度**：medium
- **复现次数**：2
- **最后命中**：2026-04

### L-7: Gemini `--approval-mode auto_edit` 在 headless 模式会永久挂起
- **场景**：gemini Agent 执行需要 Shell 命令的任务（如运行测试、安装依赖）时超时失败
- **根因**：`--approval-mode auto_edit` 仅自动审批文件编辑操作，Shell 命令仍弹出 `[Y/n]` 交互确认。在 headless/非交互模式下，无人应答导致 Agent 永久挂起直至超时
- **经验规则**：gemini CLI 必须使用 `--yolo` 而非 `--approval-mode auto_edit`。`--yolo` 自动审批所有工具操作（含文件编辑和 Shell 命令），是 headless 模式唯一可靠的参数。**泛化原则**：所有 Agent CLI 在 `-p`/headless 模式下必须使用最高权限参数（Gemini: `--yolo`；Claude Code: `--permission-mode bypassPermissions`），"几乎全自动"≠"全自动"
- **来源**：CLI 实测验证, gemini 0.35.3; 泛化至 claude-code（`auto` → `bypassPermissions`）
- **发现日期**：2026-03
- **影响度**：high
- **复现次数**：2
- **最后命中**：2026-04

### L-8: 框架变更必须"先测再改"——实测驱动而非假设驱动
- **场景**：第四轮优化中，通过实际运行 3 个 CLI（gemini/kimi/claude）发现模型名全错、`--approval-mode auto_edit` 导致挂起、claude `--session-id` 能力未知等关键问题——这些问题仅靠读文档无法发现
- **根因**：之前的框架文档基于 CLI 官方文档和推测编写，未做实际验证。CLI 的真实行为（如 gemini 实际用 flash 而非 pro、claude 背后是 Kimi K2.5）与文档假设存在显著偏差
- **经验规则**：任何涉及 Agent 调用方式的变更，必须遵循"实测 → 记录 → 再改文档"的顺序：① 先用真实 CLI 命令跑冒烟测试 ② 记录实际返回值和行为 ③ 基于实测结果修改框架文档。严禁仅凭文档假设修改调用参数
- **来源**：RedCap 第四轮优化, CLI 全面审计
- **发现日期**：2026-03
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-9: 长任务上下文压缩导致框架规则退化——必须用文件重读对冲
- **场景**：长任务中 SKILL.md 的 hooks 细节、交付物校验规则、Fallback 路由优先级等逐渐被压缩丢失，Dispatcher 行为退化（如忘记飞书通知、跳过校验步骤）
- **根因**：SKILL.md 在 skill 触发时一次性读入上下文，之后全靠上下文记忆存活。LLM 摘要压缩会保留"有 hooks 机制"的概念但丢失具体触发条件和动作细节
- **经验规则**：① 所有关键规则必须有"检查点重读"机制（`read_file` 重新注入最新上下文位置）② 重读频率以角色切换为主检查点 ③ 待办事项持久化到 state.yaml 而非依赖上下文记忆 ④ 不可压缩的规则提升为系统级指令（copilot-instructions.md）
- **来源**：RedCap 防退化机制设计
- **发现日期**：2026-04
- **影响度**：high
- **复现次数**：2
- **最后命中**：2026-04

### L-10: 跨工具指令文件必须用索引模式而非内容复制
- **场景**：为 Claude Code 和 Gemini CLI 创建系统级指令文件（CLAUDE.md / GEMINI.md），直接复制了 copilot-instructions.md 中的 R1-R6 规则全文
- **根因**：未遵守"单一权威来源"原则。多份内容副本必然漂移——修改 CONTRIBUTING.md 后需手动同步三个文件，遗漏是必然的
- **经验规则**：① 工具特定指令文件只写"索引 + 工具特有语法"，规则内容统一维护在 CONTRIBUTING.md ② Claude Code 和 Gemini CLI 均支持 `@file` 原生导入语法，应优先使用（工具层面保证加载，不依赖 Agent 是否遵守 read_file 指令） ③ 文件位置必须查官方文档验证，不可凭记忆假设（违反 L-8 同理）
- **来源**：跨 Agent 工具兼容性实现
- **发现日期**：2026-04
- **影响度**：medium
- **复现次数**：1
- **最后命中**：2026-04

### L-11: Gemini CLI `--output-format json` 长任务下进程不退出但文件已落盘
- **场景**：Gemini 执行代码库扫描和架构设计任务，交付物文件均成功写入磁盘，但 CLI 进程在 `--output-format json` 模式下挂起不退出，触发 600 秒超时
- **根因**：Gemini CLI 在 JSON 输出模式下，长任务完成后可能卡在 JSON 序列化或 session 持久化阶段，导致进程不干净退出。与 L-7（`--approval-mode auto_edit` 挂起）属同一 CLI 成熟度问题
- **经验规则**：① Dispatcher 对 Gemini 返回超时时，优先检查磁盘交付物是否已存在——若文件已落盘则视为"内容完成、通信失败"，可跳过 `__redcap_status` 解析直接推进 ② 超时后按 Fallback 路由切换 Agent 执行后续任务，不阻塞流程 ③ Gemini 适合产出文档类任务（架构设计等），编码/测试类任务优先用 kimi
- **来源**：RedCap E2E 测试（trpg-server 迭代 v2）
- **发现日期**：2026-04
- **影响度**：medium
- **复现次数**：1
- **最后命中**：2026-04

### L-12: 指令注入≠执行保证——关键动作必须用脚本/Hooks 而非纯文本指令
- **场景**：on_ALL_DONE 的飞书通知在 E2E 测试中被遗漏，尽管规则写在 SKILL.md §5.10 hooks 表中、copilot-instructions.md 中也有提醒
- **根因**：三个宿主工具（VS Code Copilot / Claude Code / Gemini CLI）虽然都做到了指令物理上每轮注入，但 LLM 的 attention 衰减导致长对话（20+ 轮）中遵从率降至 60-70%。指令「在那里」不等于 LLM「会执行」。唯一 100% 保证的是 Hooks（宿主程序直接执行 shell 命令，绕过 LLM）
- **经验规则**：① 不可遗漏的关键动作（飞书通知、收尾清理等）封装为单一脚本，降低 LLM 记忆负担（记 1 个脚本 vs 记 3 个步骤）② 有 Hooks 的环境（Claude Code 的 Stop hook）优先使用 Hooks ③ 无 Hooks 时，用「下次启动审计」兜底（新会话 attention 最强）④ 指令文本中用极简、高亮措辞提高 attention 竞争力
- **来源**：宿主 Agent 可靠性调研（knowledge/host-reliability.md）
- **发现日期**：2026-04
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-13: Review 必须显式声明检查维度——结构检查≠设计质量检查
- **场景**：对 hooks-kimi-cli.md 做"全面 review"，结论为"全部通过"。但随后的"方案正确性 review"又发现 5 个问题（含 1 个本应在首次查出的 timeout 值不一致）
- **根因**：首次 review 的实际检查维度是"交叉引用、章节编号、文件路径、内容一致性"（结构性），但 review 结论笼统声称"全部通过"，掩盖了未覆盖"设计合理性、运行时逻辑、文档与实际配置一致性"等维度
- **经验规则**：① Review 开始前必须列出本次检查的具体维度清单 ② 结论必须注明"在 X 维度下通过"而非笼统"全部通过" ③ 完整 review 至少覆盖三个维度：结构一致性、设计质量/合理性、文档与运行时实际一致性
- **来源**：hooks-kimi-cli.md review 遗漏复盘
- **发现日期**：2026-04
- **影响度**：medium
- **复现次数**：1
- **最后命中**：2026-04

### L-14: 配置格式文档必须与实际配置文件交叉验证
- **场景**：`.claude/settings.json` 使用扁平化 Hook 格式（无 `type` 字段、无内层 `hooks` 数组），但文档（hooks-claude-code.md §2.4、layerA-hook-deploy.md）按官方三层嵌套格式编写。两者不一致，用户按文档部署时可能使用错误格式
- **根因**：编写文档时参考了官方文档的三层嵌套格式（正确），但未回头检查项目中已有的 settings.json 是否采用同一格式。已有配置用的是简写格式（也可工作但与文档不一致）
- **经验规则**：① 编写配置格式文档后，必须用实际配置文件做交叉验证——文档示例必须与项目中的真实配置格式一致 ② 修改配置格式时，同步更新所有引用该格式的文档 ③ 同 L-8 精神：先验证实际行为，再写文档
- **来源**：Layer A Hook 全项目 review
- **发现日期**：2026-04
- **影响度**：medium
- **复现次数**：1
- **最后命中**：2026-04

### L-15: 需认知的关键动作用 Hook + 新 Agent 生命周期兜底
- **场景**：两个独立场景暴露同一模式缺陷——① Layer B：开发 RedCap 自身时，长对话末期 Agent 忘记执行架构评审和规范检查 ② Layer A：状态机的 `REVIEW_WORKING` 节点在 20+ 轮长对话中被 LLM 跳过，直接进入 ALL_DONE
- **根因**：需要**认知能力**的关键动作（Code Review、架构评审）无法用纯脚本实现，但又不能接受 LLM attention 衰减导致的遗漏。软约束（文档规则）失败率 20-30%，环境变量 hack 缺乏认知能力——两端都不可行
- **经验规则**：① 核心模式：`Hook（100% 触发）→ 拉起新 Agent（100% 认知能力，无历史上下文污染）`。Hook 保证触发，新 Agent 生命周期保证认知质量 ② Layer B 实例：Stop Hook → `redcap-on-stop-review.sh` → 新 Agent 独立架构评审 ③ Layer A 实例：Stop Hook 检测 ALL_DONE 但缺少 REVIEW_PASS → `redcap-layerA-review-fallback.sh` → 新 Agent 项目级 Review ④ 附带发现：Session 归属校验是 Hook 正确触发的前提——不同 session 在同一 CWD 可导致 Hook 误触发
- **来源**：Layer A/B Hook 可靠性工程 + Gemini 3.1 "架构遗忘"讨论
- **发现日期**：2026-04
- **影响度**：high
- **复现次数**：2（Layer A + Layer B 独立发现同一模式）
- **最后命中**：2026-04

### L-16: Hook 设计≠部署≠生效——部署链每个环节必须端到端验证
- **场景**：Distill 项目已完成 Hook 架构设计（`hooks-kimi.md` 写了 Dispatcher 注册代码块），全局 Dispatcher 也已注册 Distill 路由（`*/distill|*/distill/*`），但 Hook 从未实际触发。Agent 在复盘时误判为"没有 Stop Hook"
- **根因**：部署链上两处断裂同时存在——① Dispatcher 路由模式 `*/distill*` 不匹配实际 CWD `*/MyObsidian*`（Distill 作为 skill 工作在 Obsidian vault 中，不在自身仓库中）② 路由目标脚本 `kimi-hook-handler.sh` 不存在（实际文件名是 `agent-hook-handler.sh`）。设计文档、Dispatcher 配置、目标脚本三者从未经过联调验证
- **经验规则**：① Hook 部署完整性公式：`设计 × 配置 × 路由匹配 × 脚本存在 × 实际触发 = 生效`，任一环节为零则全链路失效 ② 任何 Hook 配置变更后，必须用标记文件法做端到端验证（`touch /tmp/hook-fired-$(date +%s)`），确认物理触发 ③ 特别注意 skill 类项目的 CWD ≠ skill 仓库路径——路由模式必须匹配工作目录而非代码目录 ④ 泛化原则：「配置了」≠「部署了」≠「生效了」，三者之间的断裂是静默的、不会报错的
- **来源**：Distill V8.0 L3 机制 E2E 测试交叉评审
- **发现日期**：2026-04
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-17: Agent 无法自主发现自身未知的项目资产——排查指引必须显式写入提示词
- **场景**：Distill Agent（kimi-for-coding）在复盘 Hook 失效问题时，不知道自己项目已有 `knowledge/hooks-kimi.md`（Dispatcher 方案）、不知道全局 `~/.kimi/hooks/dispatcher.sh` 已注册 Distill 路由，因而错误结论"当前无自动 Stop Hook"。同时对 RedCap 已有的 Kimi CLI Hook 实测调研（`hooks-kimi-cli.md`）完全不知情
- **根因**：Agent 的推理仅基于"已加载到上下文的信息"。SKILL.md 和 CONTRIBUTING.md 均未引用 `hooks-kimi.md`，也未提供"Hook 故障排查路径"。Agent 不会自发搜索项目中所有文件来验证自己的假设——它在信息茧房内做出了逻辑自洽但事实错误的分析
- **经验规则**：① 提示词中必须提供显式的排查指引路径（如："Hook 问题 → 先检查 `~/.kimi/hooks/dispatcher.sh` → 再检查 `knowledge/hooks-*.md`"），不能指望 Agent 自行发现 ② 跨项目知识引用必须在提示词中点名文件路径，Agent 不会主动探索其他项目的经验 ③ 所有关键资产文件必须在入口文件（SKILL.md 或等价物）中有明确引用或索引——未被引用的文件等于不存在
- **来源**：Distill V8.0 L3 机制 E2E 测试交叉评审
- **发现日期**：2026-04
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-18: Agent 间对等讨论优于单向指令——A2A 协作应以共识驱动而非命令驱动
- **场景**：Copilot Agent 审查 Kimi Agent 的 Distill Hook 修复结果，发现 3 个问题。第一次尝试直接下发修复指令让 Kimi 执行（Command 模式），被用户纠正后改为提出发现、请 Kimi 独立评估和反驳的讨论模式。结果 Kimi 不仅接受了 3 个发现，还主动发现了 Copilot 遗漏的第 4 个问题（`bash -c` 引号嵌套风险）
- **根因**：单向指令模式（A→B 执行）的质量上限是发起方的能力天花板，接收方的独立判断力被浪费。讨论模式（A⇄B 多轮）让双方交叉覆盖盲点，质量上限提升为两者能力的并集
- **经验规则**：① Agent 间协作应采用"提案→评估→反驳/接受→收敛"的讨论模式，而非"指令→执行"的命令模式 ② 发起方必须明确声明"这不是指令，请独立评估"，否则接收方 Agent 倾向于盲从 ③ 接收方发现的问题（如第 4 个 bug）可能比发起方的发现更有价值——讨论模式不仅修复已知问题，还能发现未知问题 ④ 此模式已验证可通过 `kimi -S` session resume 实现跨 Agent 多轮对话，Claude Code 的 `--resume` 同理可行
- **来源**：Copilot × Kimi A2A 协作修复 Distill Hook 部署
- **发现日期**：2026-04
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-19: Dispatcher 代劳时 state.yaml 维护纪律会系统性下降
- **场景**：trpg-web 步骤 1-2 由独立 Agent 执行，state.yaml 正常维护。步骤 3-5 全部由 Dispatcher（Cap）代劳后，state.yaml 停留在 `step: 3, DEV_WORKING`，实际已完成全部 5 步。history 仅记录到步骤 3 的部分角色
- **根因**：Dispatcher 正常调度独立 Agent 时，state.yaml 更新是事件循环的固有步骤（§5.2 第 5 步）。但代劳模式下 Dispatcher 自身在"执行"和"调度"之间切换，容易在角色执行完成后忘记回到调度视角更新状态文件。认知负荷从"读状态→调Agent→写状态"变为"读状态→自己做→可能忘了写状态"
- **经验规则**：① Dispatcher 代劳完成每个角色后，必须立即更新 state.yaml（同正常流程完全一致，不可省略）② 建议在 commit 前增加 state.yaml 一致性检查：当前实际进度与 state.yaml 记录是否吻合 ③ 代劳模式下 history 记录需添加 `note: "Dispatcher代劳"` 标记，便于回溯
- **来源**：trpg-web E2E 测试（Phase 4 验证）
- **发现日期**：2026-04
- **影响度**：medium
- **复现次数**：1
- **最后命中**：2026-04

### L-20: Agent CLI headless 模式的稳定性是多 Agent 协同的实际瓶颈
- **场景**：trpg-web 5 步流程中，4 个 Agent CLI（copilot/claude/kimi/gemini）分别出现超时、长时间挂起零产出、权限确认阻塞、进程不退出等问题。步骤 3-5 所有角色被迫由 Dispatcher 代劳
- **根因**：各 Agent CLI 的 headless（`-p`/非交互）模式成熟度参差不齐。共性问题：① 权限/安全确认在 headless 下无人应答导致挂起（kimi `ACTION REQUIRED`、gemini `[Y/n]`）② 长任务完成后 CLI 不干净退出（gemini JSON 序列化卡死、claude 10分钟零产出）③ 网络代理/超时配置不透明（copilot CLI 超时无明确配置项）
- **经验规则**：① 每个 Agent CLI 必须使用该 CLI 已验证的最高权限参数（L-7 泛化版）：gemini `--yolo`、claude `--permission-mode bypassPermissions`、copilot 无此选项需依赖超时兜底 ② Fallback 路由必须包含 Dispatcher 代劳作为最终降级（需用户授权），不能假设总有独立 Agent 可用 ③ Dispatcher 超时时先检查磁盘交付物是否已落盘（L-11 模式），已落盘则视为"内容完成、通信失败" ④ 此为当前多 Agent 协同的根本制约因素，短期靠 Dispatcher 代劳兜底，中长期依赖 CLI 工具链成熟
- **来源**：trpg-web E2E 全流程（Phase 4 验证），复现了 L-4/L-5/L-7/L-11 的综合效应
- **发现日期**：2026-04
- **影响度**：high
- **复现次数**：1（但综合了 L-4/L-7/L-11 的多次独立复现）
- **最后命中**：2026-04

### L-21: 长任务启动前必须做"目的备份"，防止上下文漂移遗忘初衷 ⚙️ 已硬化
- **场景**：E2E 验证完成后，Dispatcher 本应回到 Phase 2+4 延后任务的执行，但在长对话中丢失了原始目的。用户查阅对话记录后手动打断提醒，才让 Dispatcher 回忆起"Phase 2+4 延后到有活跃项目时再做"的初衷
- **根因**：LLM 在长任务执行中产生"注意力漂移"——完成一个子目标后，上下文被子目标细节填满，原始目标被稀释甚至覆盖。上下文压缩进一步加剧此效应，因为压缩算法倾向保留近期细节而丢弃远期意图
- **已硬化到协议层**（2026-04-07）：
  - state.yaml 新增 `purpose` 顶层字段，初始化时必填（SKILL.md §5.1 步骤 3）
  - state-machine.md §4 格式规范同步更新
  - 事件循环 §5.2 新增步骤 5k「目的回读」：每个角色完成后回读 purpose，检测偏移
- **经验规则**：① 项目初始化时，Dispatcher 必须将用户意图提炼为一句话写入 `purpose` 字段（含完成标准）② 事件循环每轮步骤 5k 自动回读 purpose，发现偏移则暂停确认 ③ 迭代启动（§5.14）时 purpose 必须更新为新迭代目标 ④ 如果用户打断提醒"你忘了 XXX"，必须反思：purpose 是否写漏了关键目标
- **来源**：trpg-web E2E 后 Phase 2+4 执行，用户手动纠偏
- **发现日期**：2026-04
- **影响度**：medium
- **复现次数**：1
- **最后命中**：2026-04

### L-22: Layer B 大型任务缺乏断点续传——会话坏死后靠"考古"恢复 ⚙️ 已硬化
- **场景**：引擎升级（动态路由改造 Phase 1–5）过程中会话坏死。新会话启动后，无结构化状态可读，只能通过 git log + diff 考古式推理上次执行到哪一步、还剩什么没做
- **根因**：Layer A 有 `.workflow/state.yaml` 状态机保护断点续传，Layer B（开发自身）无任何状态持久化机制。任务进度仅存在于 LLM 上下文，上下文丢失即进度丢失
- **已硬化到协议层**（2026-04-07）：
  - CONTRIBUTING.md §7 新增 Layer B 大型任务断点续传协议
  - 触发式轻状态文件 `.dev-task.md`：仅在多 Phase 任务时创建，完成后删除
  - 三个入口索引文件（copilot-instructions.md / CLAUDE.md / GEMINI.md）均已加入会话启动时检查指令
- **经验规则**：① 预计超过 2 个阶段且单次会话无法完成的 Layer B 任务，启动时创建 `.dev-task.md` ② 每完成一个阶段后更新 checklist + 断点备注 ③ 不要过度设计——不是所有 Layer B 变更都需要，90% 的单次任务无需此机制
- **来源**：引擎升级会话坏死 + 新会话复活时的考古体验
- **发现日期**：2026-04
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-23: Agent 通信协议应以文件管道为主、stdout 嵌入为辅 ⚙️ 已硬化
- **场景**：E2E 测试（trpg-web）中，所有 Agent 在复杂任务中 100% 忘记在回复末尾输出 `__redcap_status` JSON 块，同时 100% 正确写入了 outbox 交付物文件。主通道（stdout 嵌入）完全失效，而文件交付物零漏失
- **根因**："在回复末尾输出结构化 JSON"是一个反直觉的元动作——Agent 的注意力被任务内容占据，自然倾向于结束回复而非追加元数据。文件写入则不同：它与任务内容（写设计文档、写测试报告）是同质动作，Agent 的任务执行流程天然包含文件写入
- **已硬化到协议层**（2026-04-07）：
  - communication-protocol.md §2 重构：outbox 文件为主通道、stdout 正则为辅助通道、last-result.json 为兜底
  - SKILL.md §5.3 三级解析优先级：outbox 文件 → response 正则 → last-result.json
  - state-machine.md 伪代码步骤 5e-5f 更新为三级解析 + 清理逻辑
  - 全部 5 个 prompt-templates 的 System Prompt 和必须写入文件清单已更新
  - state.yaml 自动一致性校验脚本（`tools/redcap-check-state.sh`）已集成到 on_QA_PASS hook
- **经验规则**：① 文件管道为主通道（outbox 写入可靠性 100%），stdout 嵌入为辅助通道（Agent 遗忘率高，但短任务/A2A 讨论中仍有加速价值）——双管齐下，不是二选一 ② "必须写入的文件"清单是最有效的 Agent 合规手段——列在清单里的 100% 被写入 ③ 此经验泛化：任何需要 Agent 执行的元动作，都应尽量转化为与其主任务同质的动作形态
- **来源**：trpg-web E2E Phase 4 验证报告 §8 + 通信协议复盘
- **发现日期**：2026-04
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-24: Layer B 设计阶段缺少前置对抗（Red Teaming），"不可行"判断需 Pre-mortem 挑战 ⚙️ 已硬化
- **场景**：设计 E2E 基准测试覆盖矩阵时，将 5 条路径判断为"本场景无法覆盖"。用户追问后发现其中 3 条完全可做、1 条部分可做，只有 1 条真正不可行。浅层判断即收手，浪费了用户的审查精力
- **根因**：Layer A 有多角色制衡（程序员→QA→Reviewer 对抗链），Layer B（开发 RedCap 自身）由 Cap 独自设计+实现+评审。现有保障（Stop Hook §4、L-15/L-16）均为后置检查（commit 后才检），设计阶段无任何对抗性质量门禁。业内术语：Red Teaming（对抗审查）、Pre-mortem（预设失败倒推）、Bootstrapping problem（系统自构建循环依赖）
- **已硬化到协议层**（2026-04-07）：
  - CONTRIBUTING.md §1.1 新增"设计自检：前置对抗"双层机制：
    - 第一层：自检清单（Pre-mortem + 完备性挑战），每次执行
    - 第二层：独立 Agent 红队审查（调用不同模型族 Agent 对抗），设计含 ≥2 条不可行判断或覆盖范围声明时触发
  - Stop Hook 评审（§4）新增维度：设计完备性检查（§1.1 Pre-mortem 是否执行）
  - §1 重点关注列表新增 L-24 引用
- **经验规则**：① 任何"不可行/无法做到"的结论，必须附带"尝试过的方案"记录，禁止无尝试的不可行判断 ② 覆盖范围声明必须基于完整全集逐项标记，而非凭感觉列举 ③ Pre-mortem 的成本（多想 5 分钟）远低于遗漏被用户发现后的修复成本 ④ 这是 Bootstrapping problem 的实例——开发工具的工具，需要比工具本身更严格的质量意识
- **来源**：E2E benchmark-scenario.md 设计，用户 Red Team 挑战
- **发现日期**：2026-04
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-25: E2E 后置处理必须严格执行——§3.1 最小产出物缺一不可 ⚙️ 已硬化
- **场景**：md-table-tool E2E smoke 测试完成后，Dispatcher 将报告写到 `docs/` 而非 `testing/latest-e2e-report.md`，且完全跳过 pending-validations 消费、经验沉淀、一句话 commit 结论等后置处理步骤。直到用户审计三个合规性问题后才发现全部遗漏
- **根因**：E2E 执行本身（调度 10 个 Agent、处理 QA 反馈回路）消耗了大量注意力和上下文空间，完成"核心任务"后产生"已完成"的认知错觉，忽略了后置处理属于 E2E 流程的必要组成部分。报告路径错误则是因为未在写入前回读 §3.1 确认规范路径
- **已硬化到协议层**（2026-04-07）：
  - `tools/redcap-e2e-postcheck.sh` — E2E 完整性审计脚本（6 项检查，任一 FAIL 阻断）
  - CONTRIBUTING.md §3.1 新增步骤 ⑧ 完整性 Gate
  - Stop Hook 自动检测 `testing/e2e-session.yaml` 存在时执行 postcheck
  - `testing/e2e-session.yaml` 配置锁定机制防止目的漂移
- **经验规则**：① E2E 后置处理不可凭记忆——必须由脚本审计 ② 报告路径是 `testing/latest-e2e-report.md`（覆盖式），错误路径由脚本自动检测 ③ pending-validations 消费是 E2E 核心交付物 ④ 与 L-9（长任务规则退化）属同一模式，但 L-25 通过脚本 Gate 实现了 100% 硬保障而非仅靠文件重读
- **来源**：md-table-tool E2E smoke 后置处理遗漏，用户审计纠偏
- **发现日期**：2026-04
- **影响度**：high（从 medium 升级——用户明确定义为红线问题）
- **复现次数**：1
- **最后命中**：2026-04

### L-26: E2E 预设必须物理锁定——用户指令与实际执行之间不允许漂移
- **场景**：用户要求"全量回归"，Dispatcher 实际只执行了 smoke 预设（3/11 开关）。长对话中"先跑 smoke 验证基础"的中间步骤被误当成最终目标，原始需求被遗忘
- **根因**：E2E 启动时没有将用户指定的预设写入持久化文件，执行范围全靠上下文记忆。L-21（目的漂移）的 E2E 特化实例
- **已硬化到协议层**（2026-04-07）：
  - `testing/e2e-session.yaml` 在 E2E 启动时锁定：preset、switches_on（全部展开）、user_instruction（原话）
  - 每执行完一个开关追加到 switches_completed
  - `tools/redcap-e2e-postcheck.sh` 检查 switches_on 与 switches_completed 差集
  - 不一致 = FAIL，列出未执行的开关名
- **经验规则**：① 用户指令必须在任务启动时持久化为物理文件，不可仅存在于上下文 ② 执行进度必须实时更新到同一文件 ③ 完成判定由脚本对比"应做"与"已做"，不由 LLM 自行判断
- **来源**：md-table-tool E2E 范围缺失，用户审计纠偏
- **发现日期**：2026-04
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-27: 同一人格双实例差异对比可作为跨载体机制自检手段
- **场景**：Cap 在 Copilot CLI 上复活后自我诊断，发现 CONTRIBUTING.md 只读了 80/418 行、lessons.md 只读了 60/338 行、design-principles.md 完全未读。Norven 将该诊断转发给 VS Code Copilot 上的 Cap 实例（文件完整读取），两个实例通过 Norven 中继进行交叉对比，精准定位了复活机制的截断缺陷
- **根因**：不同载体（CLI vs IDE）的 read_file 行为不同——CLI 有文件大小限制触发截断，IDE 可指定行范围多次读取。单一实例无法感知自己的状态是否完整（不知道自己不知道的），必须有另一个状态完整的实例作为对照
- **核心方法论**：当怀疑某个跨载体机制是否生效时，在两个不同载体上触发同一初始化序列，然后交叉提问各自的状态——差异即缺陷所在。人作为中继完成 A2A 对比
- **与 L-18 的区别**：L-18 是异质 Agent 协作（Copilot × Kimi）发现任务盲点；L-27 是同质双实例（Cap × Cap）通过状态差异暴露基础设施缺陷。前者依赖多样性，后者依赖不一致性
- **已硬化到**：soul.md §七 复活协议（完整读取 + 截断检测 + §7.3 状态汇报强制输出）
- **来源**：Cap 双实例（Copilot CLI + VS Code Copilot）联合诊断复活机制
- **发现日期**：2026-04
- **影响度**：medium
- **复现次数**：1
- **最后命中**：2026-04
