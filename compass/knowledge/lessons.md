# RedCap 框架级经验库（Framework Lessons Learned）

> 本文件记录跨项目可复用的经验教训。由 Dispatcher 在识别到高价值经验时手动归档。
> 项目级经验存放在各项目的 `开发手册/shared/lessons-learned.md`。

## 热点主题速览

- **收尾 / 账面一致性**：先看 L-54、L-56~L-61、L-70~L-74、L-86~L-93。适用于 pending closure、task report、validator chain、closure ledger、current-status 打架时。
- **宿主 / Hook / runtime 边界**：先看 L-15、L-16、L-39、L-41~L-49、L-62~L-69、L-77~L-90。适用于宿主适配、review runner、session-start/session-end、host-limited 行为边界。
- **docs / knowledge / token 风险**：先看 L-50~L-52、L-64~L-66、L-91~L-97。适用于首读入口、说人话、渐进披露、`CONTRIBUTING` / docs / acceptance / `prism/runs` 的上下文压力治理。
- **评审 / 对抗 / 执行保障**：先看 L-24、L-30、L-32~L-34、L-53、L-91~L-97。适用于 red team、review 轨道、治理规则落执行保障、manual-only / host-limited 诚实建模。

> 使用方式：先按主题命中热点簇，再精读对应 L-编号；不要为了找一条相关经验默认全量扫完整个 lessons 文件。

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
- **新增豁免**：最后命中 < 3 个月的条目不计入归档候选（豁免期）
- 归档层不设删除——磁盘成本忽略不计，唯一成本是"是否占上下文"
- 归档条目如再次复现，应"复活"回活跃层并 `复现次数 +1`

**工具辅助**：运行 `bash compass/tools/lessons-score.sh` 可自动计算所有条目评分并输出归档候选清单

**选型说明（为何不引入 RAG 或向量数据库）**：
热/冷分层分文件加载是 LLM context management 的业内标准做法（活跃层直接加载，归档层按需查阅）。RAG 适合 > 500 条场景，向量检索的基础设施成本与运维复杂度远超收益；在 < 50 条规模下，关键词过滤即可满足需求。当前方案即长期设计，无需迁移到向量数据库。

---

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
- **经验规则**：项目初始化时检测所有 CLI 的底层模型，结果缓存到 `compass/.workflow/agent-registry.yaml`，路由决策基于 `{cli}&{model}` 标识。**已实现**：`compass/tools/redcap-detect-agents.sh`（轻检测 + 全量检测 + mtime 缓存）+ `compass/knowledge/model-capability-matrix.yaml`（能力矩阵）→ 动态路由算法（`loom/dispatcher/agent-adapters.md` §1.3）
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
- **场景**：md-table-tool E2E smoke 测试完成后，Dispatcher 将报告写到 `docs/` 而非 `test-reports/latest-e2e-report.md`，且完全跳过 pending-validations 消费、经验沉淀、一句话 commit 结论等后置处理步骤。直到用户审计三个合规性问题后才发现全部遗漏
- **根因**：E2E 执行本身（调度 10 个 Agent、处理 QA 反馈回路）消耗了大量注意力和上下文空间，完成"核心任务"后产生"已完成"的认知错觉，忽略了后置处理属于 E2E 流程的必要组成部分。报告路径错误则是因为未在写入前回读 §3.1 确认规范路径
- **已硬化到协议层**（2026-04-07）：
  - `tools/redcap-e2e-postcheck.sh` — E2E 完整性审计脚本（6 项检查，任一 FAIL 阻断）
  - CONTRIBUTING.md §3.1 新增步骤 ⑧ 完整性 Gate
  - Stop Hook 自动检测 `test-reports/e2e-session.yaml` 存在时执行 postcheck
  - `test-reports/e2e-session.yaml` 配置锁定机制防止目的漂移
- **经验规则**：① E2E 后置处理不可凭记忆——必须由脚本审计 ② 报告路径是 `test-reports/latest-e2e-report.md`（覆盖式），错误路径由脚本自动检测 ③ pending-validations 消费是 E2E 核心交付物 ④ 与 L-9（长任务规则退化）属同一模式，但 L-25 通过脚本 Gate 实现了 100% 硬保障而非仅靠文件重读
- **来源**：md-table-tool E2E smoke 后置处理遗漏，用户审计纠偏
- **发现日期**：2026-04
- **影响度**：high（从 medium 升级——用户明确定义为红线问题）
- **复现次数**：1
- **最后命中**：2026-04

### L-26: E2E 预设必须物理锁定——用户指令与实际执行之间不允许漂移
- **场景**：用户要求"全量回归"，Dispatcher 实际只执行了 smoke 预设（3/11 开关）。长对话中"先跑 smoke 验证基础"的中间步骤被误当成最终目标，原始需求被遗忘
- **根因**：E2E 启动时没有将用户指定的预设写入持久化文件，执行范围全靠上下文记忆。L-21（目的漂移）的 E2E 特化实例
- **已硬化到协议层**（2026-04-07）：
  - `test-reports/e2e-session.yaml` 在 E2E 启动时锁定：preset、switches_on（全部展开）、user_instruction（原话）
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

### L-29: Hook + 子 Agent CLI 模式——同时获得 100% 触发保证 + LLM 认知质量
- **场景**：需要在 Agent 会话结束时"100% 执行"某个认知型任务（如架构评审、Review 兜底），但纯 shell hook 没有推理能力，纯 LLM 指令又受 attention 衰减无法 100% 执行
- **根因**：这是两个正交的能力维度——"触发可靠性"（shell 的强项）和"认知质量"（LLM 的强项）。两者不能互相替代，但可以组合
- **解决方案**：在 hook shell 脚本中调用 Agent CLI 的 headless 模式（`agent -p -y "prompt"`），以 hook 的 100% 触发保证启动一个独立的新 Agent 进程执行认知型任务：
  - **触发层**：shell hook（Layer 0，100% 确定）
  - **执行层**：新 Agent 进程（全新上下文，零 attention 衰减）
  - **组合效果**：100% 触发 × 完整认知质量 = 两难同时解决
- **已有实例**：
  - `tools/redcap-on-stop-review.sh`：Stop Hook → `kimi -p -y` 或 `claude -p` 执行独立架构评审
  - `tools/redcap-layerA-review-fallback.sh`：ALL_DONE 且无 REVIEW_PASS → Agent CLI 执行补充 Review
- **注意事项**：
  - headless 参数必须使用 L-7 验证的最高权限版本（Gemini: `--yolo`；Claude: `--permission-mode bypassPermissions`）
  - 新 Agent 的上下文需通过 prompt 参数显式传入（L-17：Agent 不会自动发现项目资产）
  - 结果写入 `/tmp` 文件而非 stdout，防止输出污染 hook 的 exit code 逻辑
- **与 L-15 的区别**：L-15 讲"为什么"要用 Hook + 新 Agent 兜底（原理层），L-29 讲"如何"通过 `agent -p -y` 在 hook 中实现（实现层）
- **来源**：`redcap-on-stop-review.sh` 和 `redcap-layerA-review-fallback.sh` 实际设计，用户提炼为显式架构模式
- **发现日期**：2026-04
- **影响度**：medium
- **复现次数**：2（L-15 发现原理，本次显式命名实现模式）
- **最后命中**：2026-04

### L-30: 并行分析 Agent 的结论必须经独立 Red Teaming 才能用于实施决策

- **场景**：启动多个并行 explore Agent 分析框架（Q3 红线盘点 + Q4 冗余审计），汇总报告后直接进入实施规划，其中一个 Agent 建议"归档 L-2/L-10"，另一个建议"合并 5 处降级说明"，第三个建议"提取 2 行公共 preamble"
- **问题**：这三条建议均为误判——L-2/L-10 已在上一 session 归档（Agent 没看到 lessons-archive.md）；降级说明是 handbook 自洽的必要成分，不是无意重复；2 行共同内容引入专用导入机制得不偿失
- **根因**：并行 Agent 各自独立、视野受限（可能看不到所有相关文件），且不会互相交叉验证。聚合者（Dispatcher）如果直接信任汇总结果，会把误报纳入实施计划
- **经验规则**：
  1. 并行分析 Agent 的输出是"假设性候选清单"，不是可信任的行动指令
  2. 所有分析报告在进入实施前，必须经过独立 Red Teaming（critic agent 或 Dispatcher 亲自阅读原始文件验证）
  3. 对于"精简/删除/合并"类建议，默认举证责任在"建议方"：需要解释为什么重复是有害的（维护成本、认知负担、一致性风险），而不是仅指出"存在重复"
  4. 特别警惕"这是重复"的判断——重复不总是坏事，handbook 自洽、防御性冗余、渐进性指南都是合理的重复
- **正确流程**：parallel agents → aggregate → Red Team critic（验证每条建议的原始文件依据）→ approve → implement
- **来源**：本次 Q3/Q4 分析中三条被 Red Teaming 否决的建议，以及 Q4 知识文档 Agent 的 L-2/L-10 误报
- **发现日期**：2026-04
- **影响度**：high（防止无效重构污染稳定框架）
- **复现次数**：1
- **最后命中**：2026-04

### L-28: 静态源码审计不等于运行时行为——"不可行"结论必须经实测验证
- **场景**：对 Gemini CLI v0.36.0 做了源码深度审计，发现 `HookRunner/HookRegistry` 在所有非测试文件中均未被显式 import/实例化，`config.js` 标注 `// TODO: loading of hooks based on workspace trust`，据此得出"hooks 已实现但未集成"的结论，并在框架文档中标注 `❌ 不支持`。实测（同版本 v0.36.0）证实 hooks 完全可用——全局和项目级 hooks 均正确触发，数据正确透传
- **根因**：静态源码审计只检查"可见的显式 import 链"，遗漏了延迟加载、动态 require、Plugin 系统等运行时机制。源码中的 `TODO` 注释也不等于"功能未实现"——可能是"功能已实现但部分逻辑待完善"
- **经验规则**：① 静态源码审计只能证明"此链路明确不存在"，无法证明"功能不可用"——动态/延迟/插件机制不可见 ② 任何关于 CLI 工具能力的"不支持"结论，必须通过实际运行测试验证（L-8 的强化版：不仅"先测再改文档"，连"源码审计结论"也需要实测验证）③ `TODO` 注释 ≠ "功能不可用"，可能只是标记"实现路径待优化" ④ 前人的源码审计结论有时效性——同版本号的 CLI 可能在 patch 版本间已有变化
- **来源**：Gemini CLI hooks 可用性审查，源码审计结论与实测结果矛盾（knowledge/hooks-gemini-cli.md §2）
- **发现日期**：2026-04
- **影响度**：medium
- **复现次数**：1
- **最后命中**：2026-04

### L-31: 长任务需求漂移——执行期注意力衰减导致偏离原始需求
- **场景**：用户同时提出 Q1-Q8 八个问题，经过多轮 Gap Analysis 和方案讨论后，部分 Q 的执行内容偏离了原始描述（Q5/Q6 Layer 归属错误、Q8 细节被简化）
- **根因**：① 需求描述在对话早期，随轮次增加被压缩截断 ② `.dev-task.md` 断点续传机制设计用于"跨会话恢复进度"，不解决"同会话内需求保真"问题 ③ Cap 执行时依赖记忆概括而非原始文本 ④ 二阶风险：PM 澄清阶段本身若轮次过多，原始文本同样会在确认前就已失真
- **经验规则**：① 触发确认门后第一件事是将用户原文写入 `.dev-task.md`「原始输入」段（在任何澄清讨论之前）② PM 对话结束后写入「已确认需求」段作为执行依据 ③ 两段分工：原始输入=防失真底稿（永不修改）；已确认需求=执行依据（可合理演进）④ 执行每个 Q 前必须 re-read 确认描述，不依赖记忆 ⑤ 即使只有 1 个 Q 也全流程走，单 Q 同样可能因澄清轮次过多而失真
- **落地状态**：✅ CONTRIBUTING.md §10 Layer B 需求确认门（含 Step 0 原文即时固化）
- **来源**：Q1-Q8 执行漂移复盘，2026-04
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-32: 协议文档的"强制"≠机器强制——设计意图必须有执行闸门
- **场景**：Prism v0.1 的 Dispatch Firewall 在协议中以粗体标注「强制」，但无任何技术执行机制。Agent 通过 task tool 启动后拥有完整文件系统访问权限，"禁止读取 prism/reports/" 只是 prompt 级约束。三个独立评审 Agent（Opus/GPT-5.4/Sonnet）全部独立发现此问题
- **根因**：同 L-16——"文档写了"≠"部署了"≠"生效了"。多 Agent 协议中，prompt 约束是已知最弱的强制形式，LLM 可忽略
- **经验规则**：① 协议中的任何"强制/必须"，必须有对应的执行闸门（前置校验、硬终态、或技术拦截）② prompt 约束只能作为最后一道防线，不能作为主防护 ③ 发布协议前，问：「如果 Agent 决定忽略这条规则，系统会怎样？」——如果答案是"顺利通过"，就需要加机器校验
- **来源**：Prism v0.1 redteam 自评（20260410-redteam-001），2026-04
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-33: 协议先 Pilot 再固化——文档假设不能代替实测记录
- **场景**：Prism v0.1 的完整协议（30min 超时、quorum 计算、跨家族验证、Archive 链路）均为文档假设，从未运行过（index.yaml: reports: []）。该协议已写入 CONTRIBUTING.md §11 作为正式机制，但第一次真实运行将发生在"生产环境"而非"pilot 实验"中
- **根因**：L-8 的子集——任何涉及多 Agent 协作方式的新协议，不能仅凭逻辑推导就固化。实际 Agent 行为（模型偏差、超时频率、Schema 遵守率）只有跑过才知道
- **经验规则**：① 新多 Agent 协议必须先完成 1 次完整 Pilot 运行（含 Dispatch→Collect→Adjudicate→Archive），index.yaml 写入第一条记录后，才算"已实测" ② Pilot 后根据实际行为 patch 协议（超时太短？quorum 门槛太高？），再写入正式规范 ③ 协议文档中的参数值（超时、阈值、人数）必须标注"实测基础"或"文档假设"，避免假精确
- **来源**：Prism v0.1 redteam 自评（20260410-redteam-001），旧错者（claude-sonnet-4.6）发现，2026-04
- **影响度**：medium
- **复现次数**：1
- **最后命中**：2026-04

### L-34: 评审提示词需覆盖"假设但未实现"检查——不只是找错
- **场景**：Prism v0.1 的 Council 协议写了"多轮收敛、共享前轮摘要"，三个跨家族 Agent（Opus/GPT-5.4/Sonnet）评审后均未指出"多轮到底怎么实现"这个机制空缺。原因是评审提示词问的是"找设计缺陷"，而 session 复用机制是"文档暗示有、但从未描述 HOW"——这类问题不在"找错"的视野里
- **根因**：① 评审提示词框架是"找错/找问题"，不是"找假设" ② 协议文档写了"功能描述"（多轮收敛）而没有"机制描述"（write_agent/agent_id），读者脑补了实现 ③ Cap 既是协议作者又是 Synthesize 者，同一盲区在两个阶段都没有被触发
- **经验规则**：① Prism Dispatch 的提示词模板中必须包含一个专项检查：**"列出本文档中所有『假设存在但未描述实现方式』的机制"**，独立于"找缺陷"问题 ② 区分"功能描述"和"机制描述"：前者说做什么，后者说怎么做——任何只有前者的部分都是潜在空缺 ③ Cap 作为协议作者时，第一个 Dispatch 的 Agent 应当是"机制核查员"，专门列出所有"说了做什么但没说怎么做"的项目
- **来源**：Prism v0.1 council 多轮 session 管理空缺复盘，Norven 人工介入发现，2026-04
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-35: 约束驱动的系统性排错——向 distill 借鉴"不变量优先"思维
- **场景**：distill skill 经常能自主发现并修复深层 bug，原因不是提示词更好或模型更强，而是设计了一套"约束驱动+闭环检查+证据验证"的 QA 机制：① 先找系统不变量（输入→产物→归档→状态同步→失败门禁的完整链路）② 把问题当状态机断裂而非单点报错看 ③ 用真实文件/脚本输出去证伪怀疑。Prism 从文档协议借鉴此思维，引入 `prism-dispatch-check.sh` 和 `prism-archive-check.sh`
- **经验规则**：① 任何协议中的"强制/必须"，背后需要有一个对应的脚本检查点（bash exit code 1 = 阻断） ② 关键状态必须写入物理文件（session_registry.yaml），不能只存在于"运行内存"——物理文件可观察、可 debug、可被脚本读取 ③ 检查要覆盖整个链路闭环：Dispatch 前（角色/家族/长度）→ Archive 前（verdict/quorum/lessons更新）→ 不只是"中间产物生成了"就算完 ④ 先写脚本，再写协议文档——脚本是可证伪的，文档不是
- **来源**：与 distill skill 的跨 skill 学习，distill L3_HOOK_GUIDE.md + agent-hook-handler.sh，2026-04
- **影响度**：high
- **复现次数**：0（新规则，预防性）
- **最后命中**：2026-04

### L-36: "技术债"标签容易成为推迟简单工作的借口——先估实现成本再贴标签
- **场景**：Prism v0.2 时，三个评审 Agent（Opus/GPT-5.4/Sonnet）全部将 Dispatch Firewall 缺乏机器强制标为 BLOCKING，Norven 也在需求中明确提出 hook 保障机制。Cap 的处理是：记录为"技术实现需要较大工程量"的技术债，推迟到 v0.3。实际上，prism-dispatch-check.sh 不到 150 行，20分钟内完成，属于"感觉麻烦但并不难"的工作
- **根因**：① "技术债"标签本应用于真正复杂、需要大量架构设计的工作，但容易被误用于"当下不想做"的任何工作 ② BLOCKING 级别问题被降级为技术债，说明 Adjudicate 阶段存在"选择性忽视"偏差 ③ 没有先写一个 proof-of-concept 来验证实现成本，直接估判"工程量大"
- **经验规则**：① 收到 BLOCKING 标记时，先问"10分钟内能验证这有多难吗"——写个最小可用版本，再决定是否推迟 ② "技术债"只适用于真正需要较大架构变更的工作（如 Prism Orchestrator 状态机），不适用于"写个脚本做检查"这类事情 ③ 用户明确提出 + 多 Agent 独立确认 = 至少尝试一次 proof-of-concept，不应直接推迟
- **来源**：Prism v0.2 Firewall 推迟复盘，Norven 追问发现，2026-04
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-37: git mv 时目标目录已存在会导致内容嵌套而非覆盖
- **场景**：三体重组时，先 `mkdir -p compass/knowledge`，再 `git mv knowledge compass/knowledge`。期望将 knowledge/ 重命名为 compass/knowledge/，实际上 git mv 语义是"移入目标目录"——目标目录存在时，knowledge/ 整体落入 compass/knowledge/knowledge/，造成双层嵌套
- **根因**：git mv 与 mv 一样：当目标路径是已存在目录时，源目录会被放入该目录下，而非替换它。`mkdir -p` 预创建了目标目录，触发了此行为
- **修复方式**：`git mv compass/knowledge/knowledge/* compass/knowledge/ && git rm -r compass/knowledge/knowledge`
- **经验规则**：git mv src/ dest/ 前，不要预先 mkdir dest/。如果 dest/ 已存在，应先检查：① 不存在则直接 git mv；② 已存在则用 git mv src/* dest/（移动内容而非目录本身）
- **来源**：2026-05 三体重组，compass/knowledge 嵌套 bug 复盘
- **影响度**：medium
- **复现次数**：1
- **最后命中**：2026-05

### L-38: 三体架构脚本路径规则——REDCAP_ROOT = SCRIPT_DIR/../..
- **场景**：三体重组后，所有脚本从 tools/ 迁移到 loom/tools/ 或 compass/tools/，深度增加一层。原有 `REDCAP_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)` 计算出的是 loom/ 或 compass/ 的父级——即 redcap 根目录，并非预期的 loom/ 或 compass/
- **经验规则**：迁移后统一规则：`REDCAP_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)`，变量名统一为 REDCAP_ROOT（非 SCRIPT_ROOT/PROJECT_ROOT）。跨层引用格式：`$REDCAP_ROOT/loom/test-reports/`，`$REDCAP_ROOT/compass/tools/`，不使用相对路径 ../../
- **来源**：2026-05 三体重组，script-path-fixer agent 修复 13 个脚本后总结
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-05

### L-39: Copilot CLI sessionStart Hook 不暴露 sessionId 字段
- **场景**：设计 Copilot CLI Session 续接机制时，计划用 sessionStart Hook 捕获 UUID
- **根因**：官方 sessionStart Hook 的输入 schema 不包含 sessionId 字段（已验证），hook 只能做初始化动作，无法获取 session UUID
- **经验规则**：需要 Copilot CLI session_id 时，改用 `--output-format=json` 让 CLI 输出 JSONL，从 JSONL 中解析 session_id 字段。sessionStart Hook 仅适合做环境初始化（如记录 git HEAD），不适合做 session ID 捕获
- **来源**：2026-04-11，copilot-session-hook todo 修复，官方文档验证
- **影响度**：medium
- **复现次数**：1
- **最后命中**：2026-04-11

### L-40: Session 续接能力 ≠ Prism Collect 追问能力
- **场景**：Prism redteam E2E（run `20260411-redteam-003`）中，协议把“backend 支持追问”写得过于抽象。reviewer 与 challenger 同时指出：CLI 理论支持 `--resume`，不代表本轮运行一定保留了可复用 session handle，也不代表 Dispatcher 已实现“补充 prompt 后继续同一 session”的模板
- **根因**：把“CLI 产品级能力”（支持 resume/session）和“本轮 runtime 可执行能力”（有 handle + 有模板 + 当前调用真的保存了 session 信息）混为一谈，导致 Collect 阶段的追问/absent 判定失真
- **经验规则**：Prism 只有在同时满足 ① `session_registry` 已落盘可复用 handle ② 适配层已实现该 backend 的 follow-up/resume 模板 ③ 本轮调用实际保留了恢复所需 session 信息 时，才可判定 `supports_follow_up=true`；否则直接记录 backend limitation 并标记 `absent`。该判定应落到 Collect 协议与适配器文档，而不是停留在 CLI 能力表的抽象描述
- **来源**：2026-04-11，Prism run `20260411-redteam-003` / report `20260411-redteam-001`，reviewer R-003 + challenger C-005 交叉命中，并在 Collect/adapter 协议中落地
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-11

### L-41: Hook 能力存在 ≠ 已部署 ≠ 已生效
- **场景**：Layer B 收尾问题排查时，文档一度同时出现三种错位：① 把 Copilot CLI 的“支持仓库级 Hook”写成“当前仓库已部署” ② Gemini Layer B 实际复用了通用 SessionEnd 分发器，但文档写成“已完整覆盖” ③ 任务完成报告虽然在规范中被强制要求，却没有任何物理归档点或 Hook 审计，导致“口头汇报”长期被误当成已完成
- **根因**：把产品能力、仓库配置、E2E 触发证据混为同一个概念。只要任一环节缺失——没有 `.github/hooks/*.json`、没有真实触发证据、没有可观测产物——系统就会静默退化，而文档却仍可能自我感觉“已覆盖”
- **经验规则**：涉及 Hook / 收尾链的结论必须分三层陈述：① **能力存在**（官方文档/CLI 支持）② **已部署**（能指出真实配置文件和脚本路径）③ **已生效**（有本地独立验证或 E2E 证据）。此外，凡是需要 Hook 审计的流程产物，必须有**物理落盘载体**（如 `compass/docs/task-reports/*.md`），禁止把“仅在对话里输出”当作可审计完成态
- **来源**：2026-04-11，Layer B hook-chain investigation；由“任务报告未按模板 + 飞书通知缺失”追查并落地到 Copilot/Gemini/Claude 三宿主收尾链
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-11

### L-42: Hook stdout 契约必须按宿主隔离，不能复用 Gemini 的 allow JSON
- **场景**：为统一 Layer B SessionEnd 分发器复用同一份脚本时，脚本一律输出 `{"decision": "allow"}`。Gemini CLI 可接受，但 Claude Code 的 SessionEnd 生命周期 Hook 会把这段 JSON 当成不合法输出并报 schema error
- **根因**：把“Gemini 需要 stdout JSON”误推广成“所有宿主都能接受同一 JSON”。实际不同宿主对生命周期 Hook 的 stdout 协议并不一致，Claude/Copilot 的安全返回结构与 Gemini 的 decision JSON 不是同一套接口
- **经验规则**：Hook 适配层必须按宿主分别处理 stdout：Gemini 输出其要求的合法 JSON；Claude / Copilot 生命周期 Hook 默认保持静默，只有在官方协议明确要求时才返回宿主特定结构。禁止把某一宿主的控制 JSON 直接复用到全部宿主
- **来源**：2026-04-11，Claude / Gemini Layer B SessionEnd 真实 smoke；Claude 实测报 `Hook JSON output validation failed`，随后修复 `loom/tools/redcap-layerA-session-end.sh`
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-11

### L-43: 宿主 Agent 内运行 RedCap 时，必须防 authority inversion
- **场景**：多会话隔离长任务中，状态留存（plan / todos / checkpoints / reports）仍然健康，但 `.dev-task.md` 没有接管 Layer B 主真相，宿主 `plan.md` 逐渐承担了实施策略与当前停留点；同时宿主直接 skill 调用也暴露出绕过 RedCap-native delegation 的治理缺口
- **根因**：① 没有把 canonical truth、mirror sync、lifecycle/transaction gate 明确成可执行机制 ② 宿主 session/workboard/skill 机制天然更顺手，若 RedCap 不主动夺回控制面，它们就会反向成为事实 authority ③ 只做文档约束，不做 Hook / 脚本门禁，最终仍会退化成“靠人类纠偏”
- **经验规则**：① `.dev-task.md` 必须是 Layer B canonical ledger，宿主 workboard 只能镜像 pointer/hash，不得承载真相 ② PM Gate / drift check 需要物理脚本门禁，不能只写在规范里 ③ RedCap 自己的 Skill-Delegation 必须经过 request/result 文件边界；宿主直接 skill 调用不算协议内 delegation ④ acceptance 只能在治理边界落地后收口，不能在错误 truth/control model 上宣称完成
- **来源**：2026-04-12，多会话隔离主线中途 review + authority inversion 复盘（Norven 人工纠偏触发）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-12

### L-44: `session_binding_key` 只负责定位，恢复写权限必须显式过 capability gate
- **场景**：多会话隔离 acceptance 阶段，需要同时处理 resume/recovery、unmanaged Copilot degraded mode、Layer A legacy 清理与 Prism 多 run 并发。若把 `session_binding_key` 直接当作“可恢复写权限”的凭证，就会把 locate 和 authorize 混成一件事，并诱发伪 full-isolation 语义
- **根因**：① binding key 天然更容易拿到，容易被误用成 capability 恢复通道 ② unmanaged 宿主路径若为了补功能而写 project-scoped pseudo-session marker，会绕开 safe degraded mode 的禁止项 ③ 没有物理 acceptance harness 时，这类语义错位很难在日常 smoke 中暴露
- **经验规则**：① `session_binding_key` 只负责定位 runtime session，不等于恢复写权限 ② 从磁盘恢复 capability 必须显式开启独立 gate，禁止“只给 binding 就恢复写权限” ③ unmanaged / no-bind 宿主必须停留在 safe degraded mode，只能记审计/告警，不得写 pseudo-session marker、once-only 状态或其他伪 session 私有态
- **来源**：2026-04-12，multi-session isolation acceptance harness（binding-recovery-gate / copilot-safe-degraded）与独立 review 收口
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-12

### L-45: closure/notified 成功标记必须绑定到关键副作用真正完成，不能在“尝试过”时提前写入
- **场景**：两条收尾链暴露同一失败模式——① Layer A：`redcap-layerA-stop.sh` 即使 `redcap-on-complete.sh` 或 review fallback 失败，也仍然写 `layerA/notified`，导致后续 Stop/SessionEnd 不再重试 ② Layer B：`redcap-task-report-register.sh` 曾在 pending closure 写入失败前先写 report marker；`redcap-layerB-session-end.sh` 也只盯显式 FAIL，而无法识别“有 diff 但 review 根本没跑”
- **根因**：把“脚本被调用/流程被尝试”误当成“closure 已完成”。一旦去重标记、current marker、review 通过态先落盘，后续兜底 Hook 会被这些伪成功证据提前熄火，系统丧失重试与补偿式 reconcile 的机会
- **经验规则**：① 所有 `notified` / `current-*` / success marker 只能在关键副作用真正完成后写入，失败时必须保留重试机会 ② 关键副作用失败时应返回显式失败信号，让上层 Hook 决定“不去重、记录缺口、等待下次重试” ③ review/notify 这类 closure 红线既要识别显式 FAIL，也要识别 `MISSING` / `INCONCLUSIVE` ④ 对弱 Hook / 无 Hook 宿主，必须把失败写入可延续的 pending closure，而不是只打一条 warning
- **来源**：2026-04-12，host-agent interop governance tranche（pending closure contract / Layer A on_COMPLETE 收尾链 / Claude stop-review 缺口修复）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-12

### L-46: 跨会话 owner lease 必须在 EXIT 级清理，不能只在成功路径释放
- **场景**：`redcap-layerA-stop.sh` 在 review fallback 失败时会提前退出；如果 `layerA/workflow-owner-session` 只在 on-complete 成功后才释放，旧 session 会把 owner file 卡死，后续 session 即使接手项目也无法再完成 ALL_DONE closure
- **根因**：把 owner claim 当成“收尾完成后顺手清理”的附属步骤，而不是跨会话事务资源。fail-closed 分支一旦提前 return，就会留下僵尸 lease，导致治理系统自己制造永久阻塞
- **经验规则**：① `workflow-owner-session`、ownership lease、类似的跨 session 锁必须通过 EXIT trap / finally 语义清理，不能依赖单一路径 ② 释放前仍要校验当前 owner 身份，避免误删其他 session 的 lease ③ fail-closed 应阻断推进，但不能把锁资源永久遗留给失败会话
- **来源**：2026-04-12，closure-review 独立 code-review 指出 `layerA/workflow-owner-session` 在 review fallback 失败路径未释放，随后修复为 EXIT 级释放
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-12

### L-47: delegation 文件边界必须校验真实路径，不能只看字符串前缀
- **场景**：`baton-delegate.sh` 之前只校验 request/result 文件名与字符串路径前缀；如果 `.workflow/skill-delegation-*.md` 或结果文件是 symlink，就能把 delegation 请求或结果物理落到边界外，形成“路径看起来合法、真实落点却越界”的旁路
- **根因**：把“路径字符串位于 boundary 内”误当成“文件物理上位于 boundary 内”。symlink、broken symlink、`..` 归一化等文件系统语义不会被普通前缀比较捕获，导致 request/result file boundary 退化成表面约束
- **经验规则**：① request/result 这类治理边界必须校验 canonical realpath，而不是只校验 basename 或字符串前缀 ② 对已存在的 symlink / broken symlink 应直接拒绝；只允许缺失叶子文件在其真实父目录已被验证为边界内时创建 ③ “文件边界”如果不能证明物理落点，就不算真正的 authority boundary
- **来源**：2026-04-12，`baton-delegate.sh` symlink boundary probe 暴露 request/result 可越界，随后修复为真实路径校验
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-12

### L-48: 宿主通用 skill 只能是 overlay，不能把可自治决策升级成人工阻断
- **场景**：在 RedCap 已有 `.dev-task.md` canonical truth、Norven 自主执行授权与棱镜支撑的前提下，宿主侧 brainstorming skill 仍以“必须 ask_user / 必须等用户批准”的默认流程劫持了 tranche 分解与设计收口，导致本可内部吸收的决策被错误升级成人工介入
- **根因**：① 通用 skill 的默认协议没有声明“遇到拥有自治控制面的宿主框架时必须让位” ② RedCap 自身虽然已有 mirror-only / authority inversion / PM Gate 规则，但没有把“overlay skill subordinate”单独写成显式硬约束 ③ ask_user 属于宿主层工具调用，仓库内脚本无法物理拦截，若没有 repo-owned 的降级口径，就容易误以为“去改宿主 skill 本体”也是可接受修复
- **经验规则**：① 宿主通用 brainstorming / planning / visual skill 只能作为 advisory overlay，不能覆盖 `.dev-task.md`、PM Gate 与自主执行授权 ② ask_user / need_user / blocked_on_user 只允许用于 AI 无法推断的外部事实、AI 无法直接执行/验证的人类动作、或用户保留决策（包括外部依赖/架构方向禁区） ③ Prism / Dispatcher 只能建议上抛，不能把“内部死锁/内部建议”本身当成人工介入理由；真正上抛前必须指出具体缺口 ④ 若必须人工介入，先记录“为什么 AI 不能自己算出来或为什么必须由人来操作”，再上抛给人类 ⑤ 共享宿主 skill 不是 RedCap 的 patch surface；若不改宿主 skill 就无法稳定工作，该能力必须按 degraded / unsupported overlay 处理
- **来源**：2026-04-12，Norven 指出 brainstorming ask_user 导致自治升级失效；随后在 P0 复盘中进一步指出“不能通过修改其他 skill 完成目标”，据此修正最终治理口径
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-12

### L-49: 共享宿主 skill 不是 RedCap 可修改资产
- **场景**：为快速消除 overlay skill 与 RedCap-native 控制面的冲突，曾直接修改宿主共享 brainstorming skill 的原始文件来让其“兼容” RedCap；随后用户指出这等同于改写宿主共享资产，而不是修 RedCap 自身
- **根因**：把宿主 shared skill 误当成 RedCap 可拥有的依赖，而忽略了它其实属于 carrier-owned asset，会影响其他任务、其他框架和其他会话
- **经验规则**：① RedCap 只能修改 repo-owned 资产与明确归属自己的适配层，不能把共享宿主 skill 本体当成修复面 ② 若某能力只有在改宿主 shared skill 后才成立，应判定为 **degraded / unsupported**，而不是宣称“已经修好” ③ 若未来需要宿主 skill 兼容，应通过宿主侧独立版本化适配或上游维护者变更来实现，而不是由 RedCap 任务直接改写共享原件
- **来源**：2026-04-12，Norven 对 autonomy-escalation P0 收尾方案复盘后指出“修改其他 skill 属于破坏原数据”
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-12

### L-50: docs / artifact 审计若只看内容正确性，会漏掉目录边界与生命周期污染
- **场景**：在多会话隔离主线完成后的整体 review 中，注意力主要集中在 authority chain、hook/commit/notify 是否恢复，结果没有继续追问 `compass/docs/` 是否已变成“大杂烩”，也没发现 `compass/.workflow/agent-registry.yaml` 这类本地 runtime cache 仍被 git 跟踪。直到用户从 docs 目录结构切入，才暴露出“历史证据、设计快照、技术调研、runtime cache”被放在错误层级的问题
- **根因**：① review prompt 偏向功能/脚本/路径正确性，缺少“文件为什么在这里、应不应该进 git”的生命周期视角 ② 把“文档都能打开”误当成“信息架构健康”，没有区分 specs / research / traces / task-reports 这几类 authority 完全不同的资产 ③ 长任务中先前的 P0 与治理切片吸走注意力，导致 docs IA 与 artifact hygiene 没被当成独立的必审面
- **经验规则**：① review 不能只看内容是否正确，还必须检查 **authority / lifecycle / ownership**：这个文件属于 canonical history、共享证据、会话状态还是本地 cache ② `compass/docs/` 必须按 `specs/`、`research/`、`traces/`、`task-reports/` 分层；禁止再把不同职责的文档平铺混放 ③ `.workflow/`、`.dev-task.md`、本机探测缓存、宿主配置、临时 prompt/result 一律视为 session-isolated / local-only / temporary，默认不进 git ④ stop-review 提示词必须显式加入“目录与生命周期边界”检查，否则这类问题会被功能性检查淹没
- **来源**：2026-04-12，Norven 从 `compass/docs/` 杂糅问题切入的主线复盘；随后完成 docs 迁移、`.gitignore` 收口与 stop-review 硬化
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-12

### L-51: 收尾消息必须能直接抽取报告开头的重点摘要，不能只给报告路径
- **场景**：docs 治理 tranche 的正式报告已经写清了人工检查项与后续动作，但最终回复与飞书通知只说“报告已归档”，导致真正需要人类注意的信息继续被埋在长报告里。进一步修复时又暴露出一个兼容性陷阱：若新模板强制摘要段，却让旧 pending closure 的历史报告一律失效，会反过来卡死补偿式 reconcile
- **根因**：① task report 模板缺少机器可抽取的开头摘要段，notify/final 只能传路径 ② 把“报告已存在”误当成“人类已经看到了重点” ③ 新 schema 引入时没有区分“当前新增报告必须升级”与“历史 pending closure 报告需要兼容读取”的差别
- **经验规则**：① Layer B task report 开头必须显式提供可抽取的重点摘要；当前规范是 `当前已完成 / 上一步完成的是 / 下一步计划做的是 / 整体计划脉络图与当前位置` 四段入口 ② stdout 收尾摘要、飞书通知与最终回复都要优先顶出这组摘要，再给报告路径 ③ 新报告门禁升级时，对当前新增报告可以更严格，但对历史 pending closure 必须保留 backward-compatible 读取能力，避免旧义务永远无法清除
- **来源**：2026-04-12 初次落地；2026-04-15 升级为“四句先看懂”结构
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-12

### L-52: Validator / gate 脚本必须验证失败退出码，不能只看错误输出
- **场景**：在为 stop-review 接入 `redcap-validator-chain.sh` 时，`redcap-drift-check.sh` 明明已经打印了 `changed files exceed current active_slice scope`，但 validator chain 仍把它判成 pass。进一步单独执行后发现，drift-check 在 Python 校验返回非零后，脚本尾部仍无条件 `exit 0`，导致 scope drift 长期处于“看起来在报错，实际上不会阻断”的假失败状态
- **根因**：把“stderr 已打印错误”误当成“gate 已 fail-closed”。shell 脚本如果不显式传播子进程退出码，最终退出码可能被尾部的 `exit 0` 覆盖，导致控制面检查形同虚设
- **经验规则**：① 新增或重构 validator / gate 时，必须同时验证正向成功和反向失败场景，且检查退出码而不只看日志 ② shell gate 中调用 Python / 子脚本后，应显式传播失败状态，不能默认依赖 stderr 文案代表阻断 ③ 编排类入口（validator chain / orchestrator）接入已有 gate 时，要先验证每个下游检查器的 fail-closed 语义是否真实成立
- **来源**：2026-04-13，在实现 `redcap-validator-chain.sh` 时触发；随后修复 `redcap-drift-check.sh` 的退出码传播，并用正反两类场景复测 validator chain
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-53: 质量关键审查若卡住，必须做等同质量回收，不能因等待而降级
- **场景**：在 Tranche 1 中途 review 时，reviewer 已回，但 challenger / auditor 较慢。此时若因为等待成本上升，就直接用较弱审查层级或较少角色先给结论，会把“时间焦虑”错误提升到高于质量保障的位置
- **根因**：把“拿到部分结果”误当成“足以收口”，忽略了 reviewer / challenger / auditor 本就承担不同盲点覆盖职责；质量关键审查的价值不只在有没有结论，还在是否维持了原定保障层级
- **经验规则**：① 质量关键审查（中途 review、多角色对抗、决定是否继续实现的独立审查）中，质量优先于时间 ② 某一路长时间未返回时，正确动作是发起**同等质量回收任务**，而不是降级审查层级 ③ 只有在同等级回收路径也不可用时，才允许诚实标记 degraded ④ 未拿到等同质量结果前，不得把“先推进后补审”当默认策略
- **来源**：2026-04-13，Norven 明确指出“宁愿降级也不愿等结果回来”具有风险，要求将“等同质量回收优先于时间因素”沉淀为必须遵守的铁律
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-54: closure obligation 的终态必须与原 identity 绑定，且不能先 clear 再处理晚到红线
- **场景**：在实现 closure-ledger 第一版时，独立审查命中了两类容易被忽略的失真：① `session-end` 若先清 pending closure，再在 notify 失败后补写 blocked redline，会形成“同一 obligation 先 cleared 又 blocked”的矛盾轨迹 ② 若 pending closure 已按旧 `confirmed_hash` 创建，后续 `.dev-task.md` 演进后再清理/更新 obligation，ledger 可能把 `pending` 和 `cleared` 分裂到两个 hash 文件里
- **根因**：把“当前 canonical 已更新”误当成“历史 obligation identity 也应跟着漂移”，以及把 notify 这类晚到红线从 obligation 的终态事务中拆开，导致 closure 轨迹失去单一真相
- **经验规则**：① outstanding obligation 一旦创建，就应保留其原始 `task_id + confirmed_hash + active_slice` 作为生命周期 identity，后续 update / clear / blocked 都应优先复用这组 identity ② `notify`、lock/CAS clear 这类晚阶段动作若会影响 obligation 是否真正闭合，就不能放在“clear 之后再补救”的顺序里 ③ 若必须在 happy path 上记录 degraded / blocked，也要确保不会伪造出与同一 obligation 冲突的 cleared 轨迹
- **来源**：2026-04-13，closure authority ledger tranche 的 reviewer / challenger / auditor 复审中发现并修复
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-55: 把独立 gate 收口到 validator chain 时，preflight / contract-break 失败也必须留下 closure 证据
- **场景**：在把 `on-complete` 的 `commit proof / PM Gate / drift / task report / artifact lifecycle` 重构到统一 validator chain 后，独立审查发现两类证据黑洞：① `commit-proof-check` 失败只写 closure ledger、不写 pending closure，导致最基础 gate 与 obligation contract 不对称 ② 若 `current HEAD` 无法解析、validator chain 缺失，或返回了无可解析 step 的异常输出，`on-complete` 虽然仍 fail-closed，但 ledger 只留下 `started`，失败原因完全丢失
- **根因**：把“结构化 step 输出已经统一”误当成“所有失败路径都会天然落到结构化输出里”，忽略了 preflight guard、脚本缺失、协议破损这类失败可能发生在 chain 产出任何 step 之前
- **经验规则**：① 被 validator chain 编排的每个 blocking gate，都要同时保持 `closure-ledger` 与 `pending closure` 的证据对称性，不能只在一侧记账 ② 统一编排后，必须专门覆盖“无 step 输出”“输出不可解析”“脚本缺失”这类 contract-break 路径，不能默认它们会落到正常 step 解析里 ③ 若 validator chain 自身成功返回，却没有任何可记录 step，应视为 evidence-system/contract failure，而不是当作正常通过
- **来源**：2026-04-13，GD-002 validator-chain-hardening tranche 的 reviewer / challenger / auditor 复审中发现并修复
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-56: closure 入口接入 validator chain 时，必须同时统一判定、redline 映射与 step-level ledger
- **场景**：在把 `session-end` 接到 `validator-chain session-end` 时，若只让它消费统一的 pass/fail 结果，而不把 `review / reanchor / PM Gate / drift / task report / artifact lifecycle` 的 step 结果同步写回 closure-ledger，那么 authority chain 仍然只有一条聚合的 `session-end blocked/pass` 记录，真正的 blocker 细节仍散落在即时告警和脚本输出里
- **根因**：把“统一编排链”误当成“统一 authority 证据链”。实际上，closure 入口完成链化后，还需要同时统一 redline 命名、blocked 条件和 ledger phase 记账，否则只是把判定搬家，没有把审计真相搬过去
- **经验规则**：① 任何 closure 入口迁移到 validator chain 时，都要同步收口三件事：最终通过条件、pending closure redline 映射、step-level closure-ledger 证据 ② 若 validator chain 基础设施失败且没有产出可判定 step，不能只给一个聚合 blocked 结果，必须留下显式的 infra blocker（如 `validator-chain`）③ 新增 step 名称后，要显式检查它在 validator 输出、redline、ledger phase、告警文案四处的映射是否一一对应
- **来源**：2026-04-13，tranche-1-closure-validator-unification 实现过程中归纳
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-57: obligation reconcile 入口必须能权威重写 blocker 集，不能让 redline 只会并集膨胀
- **场景**：pending closure 初次写入时往往来自 stop-review、task-report-register、on-complete 等局部入口；如果后续 `session-end` 在重新审计 review / reanchor / PM Gate / drift / task report / artifact lifecycle 时，仍只把新的 blocker 与历史 `required_redlines` 做并集，那么已经修复的 `review`、`task-report` 等 redline 会永久残留，形成 stale obligation，并持续误导后续 reconcile / notify / task-report gate
- **根因**：把“pending closure 是 outstanding obligation”误解成“它的 blocker 集也必须只增不减”。实际上，局部入口适合 additive write，但 authority reconcile 入口必须有能力根据**当前全量判定**覆盖旧 blocker 集，否则 pending closure 会从“当前缺口”退化成“历史缺口墓地”
- **经验规则**：① additive write 与 authoritative rewrite 要分层：局部 hook 可以 merge redlines，但最终 reconcile 入口必须按当前 blocker set 重写 `required_redlines` ② 若 pending closure 还保存 `baseline_head / audited_head / artifact_path` 一类辅助字段，权威重写时也要允许用新的判定上下文刷新，避免历史元数据继续污染 reanchor 与 task-report 兼容逻辑 ③ 任何读取 `required_redlines` 决策行为（如 review requirement、pending report 兼容）都默认依赖“它代表当前 blocker”，因此要优先修 stale redline，而不是在消费方堆特判
- **来源**：2026-04-13，Tranche 1 stale-obligation-management 第一刀中发现 `redcap_interop_write_pending_closure()` 只会并集累积 redlines；随后为 `session-end` 引入 authority rewrite 语义修复
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-58: closure 证据写失败本身就是 blocker，不能“判定正确但持久化缺失”后仍按成功收尾
- **场景**：`session-end` 已经能算出 blocker，也能决定 `pending closure` 是否可清除；但如果 `closure-ledger` 或 `pending closure` 的写入失败，只在 runtime degraded 里记一笔然后继续 `exit 0`，就会出现“内存里知道有 blocker，磁盘上却没有任何 authoritative 证据”的假闭环，甚至在 notify 已发送后留下 false-clear 轨迹
- **根因**：把“判定逻辑正确”误当成“authority chain 完整成立”，忽略了 closure 治理真正依赖的是**判定 + 持久化**二者同时成立。对 authority 链来说，证据写失败不是普通降级，而是新的 closure blocker
- **经验规则**：① closure 入口只要已经判定出 blocker，就必须把 `pending closure` 与 `closure-ledger` 的写入视为事务关键路径；写失败时要 fail-closed，而不是吞错后继续按成功退出 ② 即使原始业务 blocker 已全部通过，若 `session-end pass` / `obligation cleared` 等 ledger 证据写失败，也要反向生成新的 closure blocker（如 `closure-ledger`），把未完成的 authority reconcile 重新挂回 pending closure ③ 需要清理 runtime claim 时，应只释放最小必要锁，不要顺手清掉会帮助后续恢复的 report/head marker
- **来源**：2026-04-13，closure-challenger recovery 指出 `session-end` 在 blocker persistence 失败后仍 exit 0；随后将其修复为 fail-closed，并用 ledger 不可写 smoke 覆盖
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-59: authority 脚本的 fail-closed 退出码，不能在宿主分发器里被吞掉
- **场景**：`compass/tools/redcap-layerB-session-end.sh` 已修成在 authority persistence failure 时返回非零，但宿主通用 SessionEnd 分发器 `loom/tools/redcap-layerA-session-end.sh` 仍沿用旧时代的 `|| true` 包裹调用，导致 Layer B 明明已经 fail-closed，Claude / Gemini / Copilot 侧看到的却还是“分发器正常结束”
- **根因**：把“分发器应该尽量稳”误扩大成“下游 authority 脚本任何非零都该吞掉”，忽略了分发器本身也是 authority chain 的一环；一旦它把下游 fail-closed 信号吃掉，就会把真实 blocker重新伪装成成功收尾
- **经验规则**：① 当下游脚本是 RedCap authority gate / closure entry 时，分发器必须传播它的 fail-closed 结果，不能一律 `|| true` ② 若宿主对退出码有特殊协议（如 Gemini 只有 `exit 2` 才是 system-block），分发器必须做**宿主语义映射**，而不是简单保留历史默认值 ③ “统一分发器”不代表“统一成功口径”；宿主适配层应负责让 authority 结果真实可见，而不是把它抹平
- **来源**：2026-04-13，stale-obligation-management slice 中 auditor 指出 `layerA-session-end.sh` 仍吞掉 Layer B 的新 `exit 1` 路径；随后修复为传播/映射 fail-closed 退出码，并用代理 smoke 覆盖
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-60: 补偿 warning 与失败 alert 必须使用独立去重 marker，不能共用 `ALERTED_FILE`
- **场景**：为修复“成功通知已发出，但后续 persistence 失败”新增补偿 warning 后，一度直接把 warning 也写进 `ALERTED_FILE`。结果下一次同一 HEAD 下真正出现 validator / PM Gate / drift 等失败时，failure-path alert 会被误判成“已经提醒过”，从而被静默抑制
- **根因**：把“同一 HEAD 上的所有提醒都可以共享一个 dedup 标记”当作理所当然，忽略了 warning 与 blocker alert 代表的是不同语义、不同触发面。它们一旦共享 marker，就会发生跨语义去重污染
- **经验规则**：① 任何新的提醒类型接入 `session-end` 时，都要先判断它是不是与现有 alert 属于同一语义；不同语义必须用独立 marker（如 `warned-head` vs `alerted-head`）② dedup marker 的所有者必须单一，禁止让 warning path 与 failure path 共同写同一标记文件 ③ 若最终成功闭环，应同时清掉与该义务相关的 warning / alert marker，避免旧 dedup 残留影响新一轮判断
- **来源**：2026-04-13，stale-challenger recovery 指出补偿 warning 复用 `ALERTED_FILE` 会压制下一次真正失败告警；随后拆分为独立 `warned-head` marker
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-61: advisory 的 auto-reconcile 只能消费“当前可证明且 identity 匹配”的 blocker，不能把 SessionStart 做成隐式清账闸门
- **场景**：为补齐独立 stale obligation / auto-reconcile 入口时，最直接的做法是把 `session-end` 那套 authority 行为搬进 `session-start`。但这会同时引入两个风险：① 把原本公开口径里的 advisory SessionStart 偷偷升级成 blocking / side-effect-heavy gate ② 当 pending closure 来自旧 `confirmed_hash` 或旧 pointer 时，新会话可能在没有证明“还是同一 canonical 任务”的情况下误清旧 obligation
- **根因**：把“下一次 re-anchor 负责消费 obligation”误解成“只要重新进入会话就可以直接清账”。真正安全的条件有两层：一是这个入口只能收缩**当前能被 validator 重新证明**的 blocker，不能顺手代做 notify / review 等未证明动作；二是它必须确认 pending closure 仍属于当前 `task_id + confirmed_hash`，否则只能保留 blocker、等待严格入口处理
- **经验规则**：① 对 `session-start` 这类 advisory 入口，应把 auto-reconcile 限定为“deterministic blocker shrink / auto-clear”而不是完整 closure transaction ② 对 auto-clear / rewrite 至少校验 `task_id + confirmed_hash` 仍匹配当前 canonical pointer；identity mismatch 时不得静默清账 ③ 对 helper 不拥有的 blocker（如 `notify`、`closure-ledger`）要保留原状，让严格入口继续 fail-closed 接管
- **来源**：2026-04-13，独立 stale obligation / auto-reconcile 入口落地时，先做 shared helper + `session-start` advisory 触发，再补入 confirmed-hash mismatch acceptance 边界
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-62: continuity authority 必须先落 repo-local manifest，再渲染宿主 mirror；缺 runtime id 时只能显式降级
- **场景**：会话连续性最初同时依赖 sibling `plan.md` 扫描、`files/imported-sessions/*/metadata.json` 回读与宿主 Session Mirror。这样虽然“看起来能工作”，但 continuity 真相分散在宿主目录里：一旦 mirror 被手改、旧 metadata 残留、或当前会话缺少稳定 `runtime_session_id`，系统就可能误判 `self-recorded / import-suggested / imported`
- **根因**：把“宿主可见性”与“continuity authority”混成一层，导致宿主资产既当显示层又当判定层；同时把缺少 runtime identity 时的 best-effort 推断误当成可接受的 continuity 结果
- **经验规则**：① continuity 协议必须先把当前真相发布到 `compass/.runtime/sessions/<runtime_session_id>/manifest.yaml` / `provenance.yaml`，再由宿主 workboard 渲染 mirror ② compatible source 只允许从 repo-local manifest 扫描，不得再靠 sibling `plan.md` 或导入目录里的 `metadata.json` 反向充当 authority ③ 缺少 `runtime_session_id` 时只能显式降级成 `fresh-session + continuity_authority=degraded-no-runtime-manifest`，不能伪造 `self-recorded / import-suggested / imported`
- **来源**：2026-04-13，`tranche-1-continuity-authority-centralization` 落地 `compass/.runtime/` continuity manifest、registry 与 acceptance 时归纳
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-63: session resume gate 必须先判 isolation mode；`continuity_state` 不能代替宿主隔离能力
- **场景**：Layer B SessionStart 以前只要拿到 `binding_key` 就直接尝试 attach/create runtime；同时 Session Mirror 只展示 `continuity_state`，没有显式区分当前宿主到底是 `full`、`degraded` 还是 `unsupported`
- **根因**：把“连续性记录状态”和“宿主隔离能力状态”混在一起，导致 Copilot wrapper/full、unmanaged degraded、unknown host unsupported 这些关键差异只能散落在文档和经验里，没法通过统一 gate 与 mirror 诚实发布
- **经验规则**：① `redcap-layerB-session-start.sh` 必须先经过独立 `session-resume-gate`，由 host capability matrix 给出 `full / degraded / unsupported` ② 只有 gate 明确授权时，才允许 attach/create runtime 并开启 disk/capability recovery ③ `continuity_state` 与 `isolation_mode` 必须分字段维护：前者回答“记录/导入状态”，后者回答“宿主隔离能力”
- **来源**：2026-04-13，`tranche-1-session-resume-gate-capability-matrix` 落地时归纳
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-64: 面向 Norven 的汇报若依赖内部黑话而不解释，理解率会断崖式下降
- **场景**：同一批变更在技术上已经完成，但终局报告里直接使用 `validator chain`、`pending closure`、`closure ledger`、`artifact lifecycle` 这类内部术语，且没有同步说明对应文件/功能与作用，导致 Norven 对内容的理解度只停留在 10-20%；改成“说人话”并补术语解释后，理解度立即提升到 80-90%
- **根因**：把“与实现对齐”误当成“已经表达清楚”，忽略了 Norven 与 RedCap 并没有预先共享这些内部命名；结果是报告在写给系统自己看，而不是写给协作者看
- **经验规则**：① 面向 Norven 的交流、汇报、报告、规范文档必须先追求人类可直接理解，不能把内部黑话当压缩表达 ② 凡是未共同约定过的术语、缩写、阶段名、链路名，首次出现必须解释它对应哪个文件/功能、做了什么、为什么重要 ③ `0.2 人工验证` 这类模板标题可以保留，但正文必须说明“这不等于只能人工完成”，避免把“未自动化穷尽覆盖”误写成“人工阻塞门”
- **来源**：2026-04-14，第一阶段收尾报告后续澄清与 Norven 反馈
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-66: 进度汇报若不先交代“现在、上一刀、下一刀、全局位置”，人类会很难接管评审
- **场景**：即使技术工作已经连续推进，当汇报只给“做了什么”或只给报告路径时，Norven 仍然难以在短时间内判断当前完成度、上一步与下一步的因果关系，以及整条路线的所在位置；改成“当前已完成 / 上一步完成的是 / 下一步计划做的是 / 整体计划脉络图与当前位置”后，状态判断与接管评审明显更顺畅
- **根因**：状态汇报默认站在执行者视角组织，而不是站在接手评审的人类视角组织；缺少稳定入口结构时，人类必须自己重建上下文，阅读成本会陡增
- **经验规则**：① 面向 Norven 的状态汇报、阶段汇报、终局摘要与任务报告开头，默认先给“四句先看懂”结构 ② 再长的报告也要先让人类在 15-30 秒内看懂“现在 / 上一步 / 下一步 / 全局位置” ③ 若后文还有人工审核或人工验证项，必须在四句摘要后继续显式顶出，不能埋进长文正文
- **来源**：2026-04-15，Norven 要求把汇报模板固定为四句入口后落实
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-15

### L-65: 长期路线如果只留在说明文档里，状态很快就会陈旧；必须拆成“机器权威 + 人类说明”
- **场景**：`framework-upgrade backlog` 最初只有一份 spec 文档，虽然能保住“后面还有哪些阶段”，但随着 A1/A2/B1/B2/B3/E1/F1 等条目陆续落地，文档状态开始明显滞后；人类读不清当前已完成什么，脚本也无法拿它做执行保障
- **根因**：把“路线说明”与“机器要验证的长期状态”混在一份文档里，既会让 spec 承担不该承担的 authority，又会让真实状态缺少可执行锚点；一旦任务跨会话拉长，状态同步完全靠自觉，迟早漂移
- **经验规则**：① 长期路线若要进入执行保障，必须拆成机器可读权威（如 `references/backlogs/*.json`）与人类说明文档两层 ② 当前 live task 仍由 `.dev-task.md` 负责，backlog 只管长期路线与阶段状态 ③ 机器权威一旦更新，必须用脚本同步人类说明里的自动摘要区块，否则收尾门应直接报错
- **来源**：2026-04-14，framework-upgrade backlog 机制化落地
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-67: 任何断言“当前没有 runtime claim”的 acceptance，都必须在 case 内自行清上下文
- **场景**：`report-register-requires-claim` 在单独跑时能通过，但放进 `redcap-multi-session-acceptance.sh all` 时会被前序 case 残留的 `REDCAP_HOST_PROCESS_PID` 污染，导致“本应无 claim”却意外附着到旧 claim，从而把真实的负向断言跑成假阳性
- **根因**：把“脚本开头已经清过一次 runtime context”误当成对每个 case 都成立的前提，忽略了 acceptance 是长脚本顺序执行，前面 case 完全可能重新写入 host pid / capability / recovery 相关环境变量
- **经验规则**：① 凡是断言“当前没有 runtime/process claim”的 case，必须在 case 内显式执行 `redcap_runtime_clear_context` 并清掉 recovery 相关环境变量 ② 负向用例不能依赖全局初始化，必须在自身内部重建前提 ③ 如果某条 acceptance 只在 `all` 模式失败，先怀疑 case 前提被前序状态污染，而不是先怀疑主逻辑退化
- **来源**：2026-04-15，修复 `report-register-requires-claim` 在 full acceptance 中的前提污染
- **影响度**：medium
- **复现次数**：1
- **最后命中**：2026-04-15

### L-68: Copilot hook 没有 sessionId 时，可用 `session-state + inuse.<pid>.lock` 补出 repo-owned 身份锚点
- **场景**：Copilot 的 `sessionStart / sessionEnd` Hook 输入始终不给 `sessionId`，导致当前会话长期停在 `degraded-no-runtime-manifest`，Session Mirror 无法判断“这是不是我自己的 continuity 记录”
- **根因**：把“宿主没有直接给官方 sessionId”误等同于“RedCap 无法识别当前宿主会话”，忽略了 Copilot 本地 `~/.copilot/session-state/<session_handle>/inuse.<pid>.lock` 与活跃宿主进程链之间其实存在稳定、可验证的对应关系
- **经验规则**：① 对 Copilot，优先用 repo-owned wrapper 扫描 `session-state/*/inuse.<pid>.lock`，结合当前 hook 进程可见的父进程链定位 `session_handle` ② 找到后生成显式 `session_binding_key=host/copilot/session/<session_handle>`，并把宿主 `plan.md` 路径一并注入 `sessionStart / sessionEnd` 主链 ③ 这层锚点解决的是 RedCap 的宿主兼容，不等于官方 Hook 已经提供 `sessionId`；如果锁或目录结构不可验证，必须诚实回退到 safe degraded
- **来源**：2026-04-16，Copilot 身份锚点 follow-up（`.github/hooks/scripts/redcap-copilot-session-context.sh` + 当前会话实测）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-16

### L-69: `sessionStart / sessionEnd` 已经落地，不等于 `task-complete` 自动收尾也已经落地
- **场景**：本轮明明已经有 Copilot `sessionStart / sessionEnd` hook，也已经补好了会话身份锚点，但真实长任务里仍然出现“最终回复已经发出，飞书和其它 must-run completion 逻辑却没执行”的事故。排查后发现，问题不在飞书脚本，而在于 `.dev-task.md` 进入 `task-complete` 时没有任何 repo-owned 物理触发器会自动跑 `redcap-on-complete.sh`
- **根因**：把“会话开始/结束都有 hook”误当成“任务完成时也一定会自动收尾”，忽略了长对话里最容易漏掉的是**中途不关会话的 task-complete 时刻**。只靠 Agent 自己记得手动执行 `redcap-on-complete.sh`，本质上仍是软约束，不是保障机制
- **经验规则**：① 对 Copilot，`task-complete` 必须有独立的 repo-owned 物理触发器；当前实现是 `postToolUse -> redcap-layerB-post-tool.sh -> redcap-layerB-task-complete-guard.sh` ② completion guard 需要做去重，并在缺少当前报告 marker 时优先自动登记本轮最新报告，再触发 `redcap-on-complete.sh` ③ 若 pending closure 还锚在旧 confirmed hash 上，不能让它继续永久挡住新收尾；要么重锚到当前 identity，要么显式 supersede，但不能再“看到旧 state 就一律拦住”
- **来源**：2026-04-16，completion 主链可靠性 follow-up（`postToolUse` task-complete guard + stale pending closure 修复）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-16

### L-70: 报告锚点校验不能停留在 glob / `-f` 层
- **场景**：closeout follow-up 中，报告锚点路径一度只做了字符串与文件存在性层面的检查，`../` traversal、absolute path、symlink file、symlinked report root 等路径仍可能混进收尾主链
- **根因**：把“路径能打开”误当成“路径属于合法报告域”，缺少统一 canonicalize 与 repo-relative 归一化，导致 closeout 对 artifact 边界的安全模型停留在脆弱的文件系统表象
- **经验规则**：① 任何消费 task report 路径的 closeout 入口，都必须统一 canonicalize 后再判断归属 ② 必须显式拒绝 traversal、absolute path、symlink file、symlinked report root ③ pending closure / session-end / task-complete guard / reconcile 回写的都应是 canonical repo-relative artifact，而不是宿主传进来的原始字符串
- **来源**：2026-04-17，closeout follow-up hardening（报告锚点 canonical helper 与相关 acceptance）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-17

### L-71: 锁格式升级不能只做 stale prune，还要考虑 live legacy holder 与 PID reuse 的并存
- **场景**：pending closure lock / task-complete guard lock 从 legacy 2-field 结构升级到新格式后，单靠“旧锁就删”会误杀仍然活着的升级期 legacy holder；反过来若完全不删，又会把 PID reuse 的旧锁误认成活锁
- **根因**：把“legacy”与“stale”混为一谈，没有在兼容期同时校验 live holder 与 PID reuse，导致锁升级路径在保守和误删之间摇摆
- **经验规则**：① 锁格式升级期必须保留 legacy 兼容分支 ② 兼容分支既要识别 live legacy holder，也要继续识别 PID reuse 的伪活锁 ③ 任何 lock prune 都必须建立在“这个 holder 不再代表当前真实活进程”的证据上，而不是仅凭格式老旧
- **来源**：2026-04-17，closeout follow-up hardening（legacy lock 兼容与 acceptance 回归）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-17

### L-72: pending anchor 的放行条件必须是“唯一最新 changed report”，不能只看它是否曾经 changed 过
- **场景**：真实 live runtime 回放中，pending closure 指向的是当前长任务真正最新的报告，但 validator 仍把“有多份 changed report”一刀切判成冲突；反过来，如果只看 anchor 曾出现在 changed set 里，旧报告又可能被误认成当前报告
- **根因**：把“anchor 是否出现过”误当成“anchor 是否仍代表当前最新报告”，缺少对 changed report 新旧顺序与唯一性的判定
- **经验规则**：① pending anchor 只能在它是唯一最新 changed report 时放行 ② 只要出现更新报告，或同级并列最新报告，就必须继续按 stale fail-closed ③ 负向回归既要覆盖“anchor 不在 changed set”，也要覆盖“anchor 曾 changed 过但已不是最新”
- **来源**：2026-04-17，live closeout 最终阻塞补丁（pending latest/stale acceptance + root 回放）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-17

### L-73: task-report-register 这类 closeout 入口必须区分 live claim 与显式 runtime env 的权威级别
- **场景**：真实 closeout 中，一旦 live process claim 已死、但 runtime session 仍可附着，旧实现就无法登记新报告；而如果直接盲信显式 runtime env，又会把 stale runtime、same-repo sibling runtime 或 foreign runtime 错当成本会话
- **根因**：没有明确 runtime 身份权威顺序，把 live claim、显式 env、host/repo/binding identity 混成一个“能 attach 就算对”的弱模型
- **经验规则**：① live process claim 始终是第一权威 ② 只有没有可用 live claim 时，显式 `REDCAP_RUNTIME_SESSION_ID + REDCAP_RUNTIME_CAPABILITY` 才能作为恢复入口 ③ 显式 fallback 必须同时校验 host / project_root / binding identity；缺一即 ambiguous / foreign fail-closed
- **来源**：2026-04-17，live closeout 最终阻塞补丁（binding-aware runtime attach 与 targeted acceptance）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-17

### L-74: marker anchor 与 pending anchor 不能有两套 stale 语义
- **场景**：pending anchor 已经改成“唯一最新 changed report”后，marker anchor 仍沿用旧条件，导致旧 marker 只要曾经 changed 过，就还能从另一条入口冒充当前报告
- **根因**：把 pending 与 marker 当成两条独立边缘路径，没有把它们视为同一“当前报告锚点”判定问题，结果 stale 防线只修了一半
- **经验规则**：① pending / marker anchor 必须共享同一套 uniquely-latest 语义 ② acceptance 必须同时覆盖 marker allow 与 stale reject 两个方向 ③ 若一条路径已升级 stale 规则，所有能把报告送进同一 validator 的兄弟入口都必须同步升级
- **来源**：2026-04-17，marker stale-anchor follow-up（`redcap-task-report-check.sh` + marker acceptance 补强）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-17

### L-75: acceptance 要锁定目标性质，不能把 root worktree / 当前 HEAD 偶然状态写成硬编码断言
- **场景**：`layerb-concurrency`、`sessionstart-auto-reconcile-*`、`task-report-check-prefers-anchor` 等 case 在单独跑时能通过，放进 full suite 或遇到 repo HEAD 演化后却随机变红，因为它们实际上断言的是“当前仓库历史刚好长这样”，不是想验证的隔离/锚点性质
- **根因**：把真实目标性质与环境偶然状态耦合在一起，让 acceptance 依赖 root worktree 残留、前序 case 副作用或特定 commit 形态
- **经验规则**：① root-sensitive case 优先迁到 fixture repo / validator stub ② 并发场景要断言真正的不变量（如每个 runtime 都写出自己的终态 marker），而不是绑死某一条 blocker/成功路径 ③ 如果一条 case 只在 `all` 模式失败，先怀疑前提污染或环境耦合，而不是先怀疑主逻辑退化
- **来源**：2026-04-17，marker follow-up 与 acceptance 去脆弱化
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-17

### L-76: acceptance cleanup 不得对真实仓库 task-report 目录做通配删除
- **场景**：最后一轮 code review 发现，acceptance 脚本残留的 cleanup helper 会对真实仓库 `compass/docs/task-reports` 下的 `zz-acceptance-*` / `zz-review-*` 执行 glob delete；哪怕 helper 已不再是主路径，只要保留，就意味着回归脚本有能力误删开发者工作区文件
- **根因**：为了追求“清理干净”，把测试隔离问题错误地转化成对真实工作区做模式匹配删除，忽略了 acceptance 清理本身也必须遵守 fail-safe 边界
- **经验规则**：① acceptance cleanup 只能删除本次 case 明确创建并记录过的精确文件，或直接在 fixture repo / 临时目录里完成隔离 ② 不允许对真实仓库 task-report 目录做通配删除 ③ 对 review 指出的危险 dead helper，若已无必要，应优先直接移除而不是靠“约定不调用”维持安全
- **来源**：2026-04-17，final code review follow-up（移除 `clear_root_acceptance_task_reports()`）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-17

### L-77: 独立评审执行器必须区分“命令存在”与“当前健康可用”，并透传真实宿主身份
- **场景**：最终 live `session-end` 回放中，独立评审脚本只要检测到 `kimi` 命令存在，就会优先硬撞 `kimi`；一旦该 CLI 未登录，就把整个真实 `session-end` 误打成 review P0。与此同时，脚本还把宿主身份写死成 `claude`，导致 Copilot 场景下的 review log / review gap 记录失真
- **根因**：把“binary exists”误当成“当前已认证且健康可用”，缺少 timeout / auth failure / 空输出 fallback；同时把最早的 Claude Stop hook 脚本直接复用到多宿主场景，却没有把宿主身份参数化
- **经验规则**：① 独立评审 runner 必须对 timeout、auth failure、空输出做可用性判定并自动 fallback，不能命中首个 CLI 就停止 ② 对当前环境，默认顺序应先尝试低成本且健康的候选，再 fallback 到 copilot / 其他 CLI，而不是一旦发现某个命令存在就锁死 ③ stop-review 被其他宿主复用时，必须透传真实 host，不能继续把日志、binding 与 pending closure 证据写死成 `claude`
- **来源**：2026-04-18，live closeout 最终回放（`redcap-on-stop-review.sh` / `redcap-layerB-session-end.sh` review fallback 修补）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-18

### L-78: review runner 的 transport error 检测必须让位于结构化评审结果解析
- **场景**：stop-review runner 加上 auth / rate-limit failure 识别后，新的 code review 立即指出另一类误杀：如果合法评审 JSON/正文里提到 `unauthorized`、`login required`、`rate limit` 等词，旧检测会把这份**正常评审结果**错当成 CLI transport failure，继续 fallback 或直接判失败
- **根因**：把 transport failure 识别放在了结构化结果解析之前，并且用的是过宽的裸子串匹配（如 `FAIL`、`unauthorized`），没有区分“这是评审内容”还是“这是 CLI 本身的执行错误”
- **经验规则**：① 对有固定输出契约的 reviewer CLI，必须先解析结构化 `PASS/FAIL` 结果，再做 transport failure 兜底 ② 文本兜底也要用严格 token / 形状匹配，不能用会命中 `FAILED`、正文说明句的宽子串 ③ transport failure 检测的职责是识别“CLI 没有真正完成评审”，不是覆盖评审本身讨论到的异常词汇
- **来源**：2026-04-18，stop-review fallback follow-up code review（structured result vs transport failure 误杀修补）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-18

### L-79: structured review 的接纳条件必须同时满足“结果值归一化”与“CLI 成功退出”
- **场景**：在修完 L-78 后，red team 又继续把边界推实：如果 reviewer CLI 以非零状态退出，但 stderr/stdout 里混入了 `result: PASS/FAIL` 一类 token，旧逻辑仍会把它误当成合法评审；反过来，合法 JSON `{\"result\":\"pass\"}` 又因为大小写未归一化而被错判成“评审结果无法解析”
- **根因**：把“文本里出现 PASS/FAIL”误当成足够强的成功信号，同时又默认 JSON `result` 必须正好等于大写 `PASS/FAIL`，没有把“进程退出状态”和“结构化字段归一化”一并纳入接纳条件
- **经验规则**：① 结构化评审结果只有在 reviewer CLI **成功退出**时才能被直接接受，非零退出必须先按 transport/exit failure 处理 ② JSON `result` 解析后要先做 trim + upper normalization，再与 `PASS/FAIL` 契约比对 ③ 文本 token 兜底只能作为成功退出后的弱兼容层，不能反过来覆盖 CLI 失败信号
- **来源**：2026-04-18，stop-review fallback follow-up red team（exit status vs token parsing / lowercase structured result 修补）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-18

### L-80: reviewer output 必须分离 payload / stderr / 残余文本，且成功但不可解析的输出必须继续 fallback
- **场景**：在修完 L-79 后，新的 code review / red team 又继续把 stop-review runner 压实：如果 reviewer CLI `exit 0` 但没有给出可解析结果，旧逻辑会直接停在当前 agent，后续 fallback 永远不跑；同时如果把 stdout/stderr 生拼到一起，raw JSON、stderr 警告、以及 plain-text `PASS` + `fail-closed` 这类正常输出也会互相污染，制造新的假失败/假通过
- **根因**：把“CLI 成功退出”误当成“结果已经可消费”，没有区分 review payload 与 transport noise；文本兜底仍按宽 token 匹配，导致 `FAIL` 会命中 `fail-closed` 一类正常说明句
- **经验规则**：① reviewer runner 要显式区分 stdout review payload、stderr transport noise、以及 structured JSON 外残余文本，再分别做结构化解析与 transport failure 识别 ② `exit 0` 但结果不可解析时，必须把它视为 retryable failure，继续 fallback 到下一个 reviewer，而不是停在当前 agent ③ plain-text 兜底只能识别强形状结果行（如独立 `PASS` / `FAIL` 或 `result: PASS`），不能扫任意裸 token
- **来源**：2026-04-18，stop-review final hardening（stdout/stderr 分离、unknown-success fallback、plain-text token 收紧）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-18

### L-81: fenced JSON 解析必须兼容 bare fence 与大小写变体
- **场景**：在修完 L-80 后，最终 red team 又补出一个 parser 兼容性漏网：stop-review runner 的 fenced JSON 提取只认小写 ` ```json `，不认 bare ` ``` ` 或大写 ` ```JSON `。结果是合法 structured PASS/FAIL 会被错打成 `unparseable-output`，继续 fallback 或直接 fail-closed
- **根因**：fenced JSON 提取正则写成了大小写敏感、且只覆盖单一 language tag 形态，没有把实际 reviewer 可能产出的 bare fence / uppercase fence 算进合法输入面
- **经验规则**：① 对 markdown fenced JSON 的解析，必须显式兼容 bare fence、lowercase/uppercase `json` 语言标记，以及大小写变体 ② 同一类 fence 提取正则如果在多个解析点复用（结果提取、残余文本分离、summary 提取），必须一起更新，不能只修其中一处 ③ 对结构化输出 parser 的兼容性修补，必须补对应 acceptance 覆盖 bare / uppercase 两个最小复现
- **来源**：2026-04-18，stop-review final red team（uppercase/bare fenced JSON 兼容修补）
- **影响度**：medium
- **复现次数**：1
- **最后命中**：2026-04-18

### L-82: transport failure detector 必须匹配“整行 CLI 错误形状”，不能扫 residual prose 的宽子串
- **场景**：在修完 L-81 后，最后一轮 red team 继续把 residual text 边界压实：如果 JSON fence 外有正常说明句，例如 `The authentication failed path remains fail-closed.`，旧 detector 仍会因为其中包含 `authentication failed` 宽子串，而把这份合法 structured PASS 误打成 transport failure
- **根因**：虽然已经把 structured payload / residual text 分离，但 transport detector 仍然对 residual prose 做整段 substring 命中，没有继续收紧到“这是一行 CLI 错误”而不是“这是一句解释文字”
- **经验规则**：① transport failure detector 应按**逐行、整行形状**识别已知 CLI 错误（如 `Authorization failed, please check your login status`），而不是在 residual prose 里扫宽子串 ② residual text 的存在本身不是异常，只有当某一行符合明确 CLI error 形状时，才应触发 fallback ③ 对 detector 收紧后，必须补一条“structured review + residual prose containing auth/rate-limit words 仍应通过”的 acceptance 正例
- **来源**：2026-04-18，stop-review final red team（residual prose false positive 修补）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-18

### L-83: bare fence 兼容不能退化成“第一个 bare fence 优先”，而必须选择真正可解析的 JSON 候选
- **场景**：在修完 L-82 后，最后一轮 red team 又补出一个 parser 选择策略问题：为了兼容 bare fence，如果实现退化成“看到第一个 bare fence 就拿它当 review payload”，那么前面普通示例代码块里的 ` ``` ... ``` ` 会抢先被消费，后面真正的 ` ```json ` PASS/FAIL 反而被漏掉
- **根因**：只放宽了 fenced JSON 的输入面，却没有同步定义“多个 fence 同时存在时，应该选哪个 candidate”；缺少“先验证能否 parse 成 JSON，再按 tag/位置择优”的选择策略
- **经验规则**：① fenced review payload 的提取必须扫描所有候选 block，并只接受**真正能 parse 成 JSON** 的候选 ② 选择顺序应优先带 `json` tag 的合法 block，其次才是 bare fence 中合法的 JSON block，不能简单“第一个 bare fence 赢” ③ 对 parser 扩兼容后，必须补一条“non-json bare fence 在前、valid json fence 在后仍应接受 PASS/FAIL”的 acceptance 正例
- **来源**：2026-04-18，stop-review final red team（fence candidate 选择策略修补）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-18

### L-84: 结构化 payload 选定后，residual transport scan 必须忽略所有 fenced blocks，只看 fence 外 prose
- **场景**：在修完 L-83 后，最终 code review 又继续把 residual scan 的边界压实：即便已经正确选中了后面的 ` ```json ` PASS/FAIL，如果 residual 文本里还残留前面示例 bare fence 中的 `Authorization failed, please check your login status` 这类错误行，旧 detector 仍会把这份合法 structured review 误判成 transport failure
- **根因**：虽然 fenced payload 选择策略已经正确，但 residual text 仍只剔除了“被选中的那个 block”，没有把其他 fenced example blocks 一并排除，导致示例代码里的错误行继续污染 transport detector
- **经验规则**：① 一旦结构化 review payload 已选定，residual transport scan 必须只保留 fence 外 prose，不能再扫描任何 fenced blocks 里的内容 ② 示例代码块、历史错误摘录、quoted CLI output 即使包含真实错误文案，也只能作为说明上下文，不能继续参与 transport failure 判定 ③ 对 residual scan 的这类收紧，必须补一条“non-json bare fence 中引用真实 CLI 错误行、后面仍有合法 json fence 时应该通过”的 acceptance 正例
- **来源**：2026-04-18，stop-review final code review（residual fenced block exclusion 修补）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-18

### L-85: stdout 已有 structured result 时，stderr 与 stdout residual 不能共用同一套 transport detector 语义
- **场景**：在修完 L-84 后，最后一轮 red team 先追出“quoted error line in stderr prose 会误杀 structured PASS”，随后又追出反向漏报：stderr 里的 `Authorization failed ...` + `Hint: run login again` 必须继续按真实 transport failure fallback；但如果把 stdout residual 也放宽到同样的 `failure-block` 规则，reviewer 在正文里原样引用同一段错误块时，又会被误杀成 transport failure
- **根因**：把 stderr 与 stdout residual 当成同一种载体来处理。实际上 stderr 更接近 transport noise，而 stdout residual 更接近 reviewer 正文 / 说明文本；两者虽然都可能包含错误文案，但误判代价与可接受启发式完全不同，不能强行统一成一条 detector 规则
- **经验规则**：① 当 stdout 已拿到结构化 `PASS/FAIL` 时，stderr 可以用 failure-block 判定识别 `error line + hint/note` 这类真实 transport failure ② stdout residual 必须保持更严格的纯错误块语义，避免把正文里原样引用的错误块误杀 ③ 这类非对称 detector 设计至少要成组覆盖：stdout residual 的 `single error line -> fallback`、`quoted error block -> pass`、`quoted prose -> pass`，以及 stderr 的 `single error line -> fallback`、`error line + hint -> fallback`、`quoted prose -> pass`
- **来源**：2026-04-18，stop-review final red team（structured review transport detector 非对称收口）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-18

### L-86: `on-complete` 的 validator host 必须来自当前宿主或绑定身份，不能被项目名或陈旧 runtime env 污染
- **场景**：Copilot `task-complete` 收尾链路中，`redcap-layerB-task-complete-guard.sh` 已经知道当前宿主是 `copilot`，但调用 `redcap-on-complete.sh` 时仍把第三参数留给展示用项目名 `redcap`；旧版 `redcap-on-complete.sh` 又把 validator chain host 固定成 `redcap`，或可能被外层残留的 `REDCAP_RUNTIME_HOST=claude` 污染。结果是同一次收尾里“当前宿主是 copilot”，但 validator / report register 看到的 host 可能是 `redcap` 或 `claude`
- **根因**：把飞书/展示用的 project_name、runtime host、session binding 这三种不同身份混成了一层；同时环境变量优先级没有防 stale 值，导致旧会话残留可以抢过当前真实宿主
- **经验规则**：① `task-complete guard` 调用 `redcap-on-complete.sh` 时必须用当前 `HOST` 覆盖 `REDCAP_ON_COMPLETE_HOST`，不能保留外层旧值 ② `redcap-on-complete.sh` 解析 validator host 时应按“显式 host → `host/<宿主>/session/<会话>` 绑定身份 → runtime host → `redcap` 兜底”的顺序，不得让 project_name 参与 runtime host 判定 ③ 选定的 host 必须同时传给 validator chain 的位置参数和 `REDCAP_RUNTIME_HOST` 环境变量，避免“参数正确、环境陈旧”的分裂 ④ acceptance 必须显式注入陈旧 host 环境，证明当前宿主仍能压过旧值
- **来源**：2026-04-18，Copilot live closeout 最后一轮 host passthrough review（`redcap-on-complete.sh` / `redcap-layerB-task-complete-guard.sh`）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-18

### L-87: `session-end` 清 pending 前必须刷新并证明当前 pending 仍被本次成功覆盖
- **场景**：`on-complete` host follow-up commit 形成后，真实 Copilot `session-end` 再次回放时，review / reanchor / PM Gate / drift / backlog / spec / task-report / artifact-lifecycle 全部 PASS，但最终 pending closure 仍被写回成 `required_redlines=pending-closure`
- **根因**：`redcap-layerB-session-end.sh` 在脚本开头读取了 pending closure 的 `updated_at`，随后长耗时 review / validator 窗口里，兼容路径或重试路径改写了同一 closure obligation；最后脚本仍用旧 `updated_at` 做 CAS 清理，被保护机制正确拒绝。旧实现只知道“清理失败”，不知道先重新读取并证明当前 pending 是否仍是同一任务身份、同一 head 覆盖窗口内的等价义务
- **经验规则**：① CAS 失败不能靠无条件重试或跳过保护解决，必须先刷新读取当前 pending ② 刷新后只有在 confirmed hash 仍匹配当前 `.dev-task.md`、pending baseline/audited head 仍被本次 validator 覆盖、required redlines 属于本次成功路径可核销集合时，才能用最新 `updated_at` 清理 ③ acceptance 要模拟 validator 运行中途改写同一 pending closure，证明成功路径不会因为陈旧 `updated_at` 永久留下 `pending-closure`
- **来源**：2026-04-18，Copilot live `session-end` 最终回放（`redcap-layerB-session-end.sh` pending refresh 修补）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-18

### L-88: reviewer fallback 列表必须覆盖当前可用宿主族，并隔离 CLI 噪声与评审 payload
- **场景**：`session-end` pending refresh commit 通过 spec / acceptance / commit-proof 后，真实 Copilot `session-end` 再次卡在独立评审：`gemini` / `copilot` / `claude` / `kimi` 全部不可用或超时，但本机 `codex exec` 可在 read-only headless 模式下稳定返回结构化评审结果
- **根因**：stop-review runner 的 fallback 列表只覆盖旧四类 CLI，没有把 Codex CLI 这个当前可用的 OpenAI 族 reviewer 纳入；同时 Codex CLI 会在 stdout/stderr 打印 banner、插件预热 warning、网络重连提示等噪声，若直接消费 stdout/stderr 会污染评审 payload
- **经验规则**：① reviewer fallback 不应固定在历史宿主集合里，发现当前环境有新的健康 reviewer CLI 时要纳入嗅探与 stop-review fallback ② Codex CLI 程序化调用必须优先读取 `--output-last-message` 结果文件，把 stdout/stderr 当 transport noise 处理 ③ acceptance 要模拟“前序 reviewer 不可用 + Codex 有 stdout/stderr 噪声但 last-message 给出合法 JSON”的路径，防止再次把健康 fallback 判成不可用
- **来源**：2026-04-18，Copilot live `session-end` review gap follow-up（`redcap-on-stop-review.sh` / `redcap-detect-agents.sh` / `agent-adapters.md`）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-18

### L-89: headless reviewer timeout 必须杀整个进程组，不能只等父进程返回
- **场景**：Codex fallback 接入后首次真实 `session-end` 回放时，runner 仍先尝试 Gemini；Gemini CLI timeout 后留下了 Node 子进程，`redcap-on-stop-review.sh` 也在 Bash 字符串处理里高 CPU 自旋，导致流程没有继续进入健康的 Codex fallback
- **根因**：timeout wrapper 只依赖 `subprocess.run(..., timeout=...)` 处理直接子进程，没有把 reviewer CLI 放进独立进程组并在 timeout 时杀掉整组；对 Node / CLI wrapper 这类会再拉子进程的工具，父进程被杀不等于执行树已清干净
- **经验规则**：① 所有 headless reviewer CLI 都必须用独立进程组启动 ② timeout 时先 SIGTERM 整个进程组，短暂等待后再 SIGKILL 兜底 ③ acceptance 要让假 reviewer 在 timeout 前拉起长寿命子进程，并断言 fallback 后该子进程不再存活
- **来源**：2026-04-18，Codex reviewer fallback live 回放（Gemini timeout descendant 逃逸）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-18

### L-90: headless reviewer 的长 prompt 必须从构造开始文件化，不能放进 Bash 大字符串
- **场景**：进程组级 timeout 与 Codex stdin 修补后，真实 Copilot `session-end` 再次回放仍卡在 `redcap-on-stop-review.sh`；一层原因是 Bash 拼接包含 CONTRIBUTING / diff / 中文评审说明的长 `REVIEW_PROMPT`，另一层原因是 Codex 用量限制 / 连接失败时可能把大段输入上下文混进 stderr，旧脚本再用 `${output//[[:space:]]/}` 判断“是否空白”，继续触发 `wcslen` 热点
- **根因**：只把 Codex 调用末尾参数改成 stdin 还不够；如果先在 Bash 里拼大块多语言字符串，或对大块 reviewer output 做 Bash 字符类替换 / 空白剥离，shell 仍会做宽字符扫描。timeout wrapper 只能管已启动的 reviewer 子进程，管不到“还卡在父 Bash 解释器里”的阶段
- **经验规则**：① 大块 review prompt 必须从 diff 提取、截断、模板拼装开始就走临时文件 / Python 处理，Bash 只传文件路径 ② 支持 stdin 的 headless CLI（如 `codex exec -`）必须直接从 prompt 文件输入；需要 `-p` 参数的 fallback CLI 也应由 Python wrapper 从文件替换 argv 占位符，不能用 Bash `$(cat prompt)` ③ 对 reviewer stdout/stderr 这类可能很大的文本，空白判断、结构化解析、failure detector 都应走 Python stdin，不能用 Bash `${var//[[:space:]]/}` ④ acceptance 要让假 reviewer 同时记录 argv 与 stdin，断言 prompt 出现在 stdin、不会泄入 argv；真实 live 回放要观察不再出现 Bash 99% CPU 卡在 reviewer 启动前或失败输出解析阶段
- **来源**：2026-04-18，Codex reviewer fallback live 回放（Bash prompt 构造 / argv 挂起）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-18

### L-91: 收尾评审的 P0/P1 必须能追到同一条物理证据链，不能让报告、验证账本与入口规范分叉
- **场景**：Codex reviewer fallback、进程组 timeout、file-backed prompt 与 host passthrough 已分别有 acceptance / full suite / live runtime 证据，但最终独立评审仍打出 P0：`pending-validations.md` 还停在部分验证，`latest-e2e-report.md` 未记录本次 hook-level replay，`SKILL.md` 与 A2A 文档也没有同步 Codex CLI 的实际边界
- **根因**：把“代码路径已经测过”误当成“治理证据已经连成一条链”。Stop Hook review 看的不是单个脚本是否通过，而是入口规范、验证账本、任务报告、经验库能否共同证明同一件事
- **经验规则**：① 涉及 Agent 适配器 / Hook runner / Prompt 输入通道的变更，除了 acceptance 通过，还要同步入口规范、A2A/适配器文档、pending-validations 与 latest E2E 报告 ② 若某验证只覆盖 hook-level replay，不得冒领完整用户项目 E2E，必须明确与 V-4 这类全链路验证拆账 ③ review 指出“未沉淀经验”时，先交叉检索已有 L-编号；已有则在任务报告和验证报告中显式引用，缺失才新增
- **来源**：2026-04-18，Codex 接盘继续 live closeout，独立评审指出 V-11 消费与入口文档联动缺口
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-18

### L-92: 强制规则必须进入执行保障目录，不能只散落在复活协议或报告里
- **场景**：docs catalog 补丁后，用户继续指出 lessons 沉淀、Cap 灵魂人格、复活协议、多 Agent 宿主适配 hook 等规则虽然已经形成，但并没有统一进入“复活协议 + 多宿主 hook + validator”的执行保障链；如果只靠 Agent 读到某段文档，下一次上下文压缩或中途接盘仍会遗漏
- **根因**：自然语言规范、宿主入口文件、hook standards、task report 模板与实际 validator 之间缺少一张机器可读的“规则 -> 保障机制”目录，导致新增规则很容易停留在“应该做”，没有被 hard gate、revival check、manual-only 边界或 acceptance 消费
- **经验规则**：① 新增 P0/P1 强制规则时，必须同步登记到 `references/execution-guarantees.json`，说明 source_paths、guarantee_paths、priority、category 与 auto_enforceable ② 能自动化的规则要接入脚本 / Hook / validator / acceptance，不能只写进 `soul.md` 或任务报告 ③ 不宜自动化的规则必须写清 manual-only 原因，避免为了“全自动”误伤 identity 内容、lessons 内容质量、外部 CLI 凭证或自然语言表达 ④ `redcap-spec-check.sh` 应消费执行保障检查，让“规则没进保障体系”在收尾前可见
- **来源**：2026-04-19，Codex 接盘后对复活协议与执行保障遗漏的治理补丁
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-19

### L-93: 上层 validator 消费下层控制面检查时必须显式传播失败
- **场景**：Gemini/Kimi headless 路径恢复后，Kimi 对 docs catalog / execution guarantees / revival check 补丁做只读审查，指出 `redcap-spec-check.sh` 虽然顺序调用了三类控制面检查，但脚本没有 `set -e`，也没有对这些子检查的非零退出做显式处理；因此某个保障检查失败时，spec-check 总结果仍可能被后续命令覆盖成通过
- **根因**：把“接入检查脚本”误当成“检查结果已进入 hard gate”。在 Bash 中，只要没有 `set -e` 或 `if ! cmd; then exit` 包装，子命令失败并不会自动成为父 validator 失败；越是控制面保障脚本，越不能依赖隐式 shell 行为
- **经验规则**：① 高层 validator 消费任何下层控制面检查时，必须显式捕获非零退出并 fail-closed ② acceptance 不能只测 happy path，必须为每个被消费的控制面 gate 建一个失败 fixture，证明失败会传播到父 validator ③ 这类“保障系统自身的保障”必须登记到 `references/execution-guarantees.json`，否则后续新增 gate 仍可能只接线、不传播
- **来源**：2026-04-19，Kimi 外部只读审查发现 `redcap-spec-check.sh` 控制面 gate failure propagation 缺口
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-19

### L-94: docs catalog 只能止血，彻底防上下文爆炸还需要 plan/budget 渐进披露门
- **场景**：docs catalog 补齐后，用户追问“是否已经彻底解决 docs 淤积污染”，并明确要求新会话不能被 `compass/docs/**` 擅自打爆上下文、后续迭代也必须遵守按需加载、且真实考古能力不能折损
- **根因**：catalog freshness 只能保证“索引不陈旧”，不能单独阻止 Agent 直接 bulk-read 目录，也不能证明“要打开的源文档集合”是精确、低预算、可解释的。若只写“先看 catalog”，仍可能在紧张接盘时把索引当跳板继续全量打开历史证据
- **经验规则**：① docs 首读必须分三步：summary 看体量，plan 按问题选候选，budget 审计精确路径集合 ② directory / glob / uncataloged / too-many-files / over-budget 读取应默认 fail-closed ③ 不应为省 token 删除 closure evidence；真实归档必须有 retention log、迁移记录和替代入口
- **来源**：2026-04-19，docs 淤积二次收口（progressive disclosure + retention check）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-19

### L-95: FSM 文档新增状态后，state.yaml 校验器必须同步合法状态集
- **场景**：F3 治理硬化扫描时发现 `loom/dispatcher/state-machine.md` 已记录 `DEGRADED / SCAN_WORKING / SCAN_DONE / STEP_DONE`，但 `redcap-check-state.sh` 的 `VALID_STATES` 没有全部同步，可能把合法运行状态误报为不合法
- **根因**：状态机文档、通信协议与 state 校验器缺少一条 contract check；新增状态时只改了文档，没有让脚本自动证明文档枚举和校验器枚举一致
- **经验规则**：① 修改 FSM、通信协议或 state 校验器时，必须运行 `redcap-state-machine-check.sh` ② 检查应至少证明文档状态枚举被脚本接受，通信协议 status 值仍完整 ③ 这类文档/脚本契约漂移必须接入 `redcap-spec-check.sh`，不能只靠人工 review
- **来源**：2026-04-19，F3 hook / contract / FSM 治理硬化扫描
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-19

### L-96: token 风险不能只治理 docs，还要覆盖入口自动导入、巨型脚本与 ignored 运行残留
- **场景**：docs catalog / plan / budget 落地后，继续扫 token 大户发现 `AGENTS.md` / `CLAUDE.md` / `GEMINI.md` / Copilot 入口仍可能默认展开 `CONTRIBUTING.md` 与 `lessons.md`，`redcap-multi-session-acceptance.sh` 单文件已经很大，`prism/runs/` 又存在大量 gitignored 运行夹具。即使 docs 不再 bulk-read，这些入口仍可能在新会话或排查单 case 时吞掉大量上下文
- **根因**：把“docs 目录治理”误当成“上下文治理全部完成”。真实 token 风险来自所有默认首读路径、巨型单文件和运行残留目录；只要其中任一项没有索引/预算/审计，后续接盘就可能从新入口重新爆炸
- **经验规则**：① 宿主入口只应默认导入轻量人格还原点，大文件规范与 lessons 必须通过 current-status、knowledge index 与精确章节读取 ② 巨型 acceptance 脚本必须先用 `redcap-acceptance-index.sh summary/find/check` 定位 case，再按行号精读局部 ③ `prism/runs`、`compass/.runtime`、`compass/.workflow` 等 ignored 运行目录不能默认读取，也不能未经用户批准删除；应由 `redcap-token-risk-audit.sh` 报告体量、mitigation 与 no-bulk-read 策略 ④ token 风险审计必须接入 spec-check / diagnose / acceptance，防止旧入口写法回流
- **来源**：2026-04-19，docs token 淤积后续扫面与 token-risk audit 补丁
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-19

### L-97: 权威规范变大时不能简单贴“token 陷阱”标签，必须拆成核心契约与章节路由
- **场景**：在入口自动导入治理后，用户指出 `compass/CONTRIBUTING.md` 不能因为体积大就被粗暴降级为“不应读取”的文件；它本来就是 RedCap 权威规范，问题不是权威规范存在，而是把全文无差别注入每个新会话
- **根因**：把“上下文预算风险”和“规范权威性”混为一谈。大文件可能同时是必要规范与 token 风险源；如果只做禁止读取，会折损执行质量，如果继续默认全文注入，又会吞噬新会话上下文
- **经验规则**：① 权威规范全文必须保留权威地位，不得因体积大被误标为垃圾或陷阱 ② 启动路径应抽出轻量 `CONTRIBUTING.core.md` 承接必须立即遵守的红线，再通过章节路由按需读取全文细则 ③ stop-review / revival / token-risk audit 要消费 core + selected guidance，而不是重新把全文塞回 prompt ④ 这类信息架构调整必须有机器 gate，防止后续入口文件又恢复 `@CONTRIBUTING.md` 全文注入
- **来源**：2026-04-20，用户质询 CONTRIBUTING 是否被误判为 token trap 后的 core + section routing 补丁
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-20

### L-98: 历史 formal Prism 报告的“索引存在”不等于“可重放审计”
- **场景**：formal Prism follow-up redteam 中，Explorer 指出 `prism/reports/index.yaml` 已登记两份历史报告，但它们既没有可重放的 `run_id + session_registry + archive-check` 证据链，也都处于 `archived=false`。如果继续把“index 里有两份报告”说成“已有 formal baseline”，就会误导后续 quorum 判断和运行残留清理决策
- **根因**：把“历史留档”与“可重放审计”混成一个概念。对于 formal Prism，真正可复核的权威并不是报告文件本身，而是报告与 run-scoped registry 的绑定关系是否仍能被脚本验证
- **经验规则**：① `prism/reports/index.yaml` 中只有 `archived=true` 的条目才能对外称为 replay-auditable formal baseline ② `archived=false` 的历史记录只能算 legacy / non-auditable reference，不能拿来冒充当前 formal 成熟度 ③ `redcap-current-status.sh`、task report 和汇报口径必须显式区分这两类数量
- **来源**：2026-04-21，formal Prism follow-up（run `20260421-redteam-001`）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-21

### L-99: `prism/runs` 物理清理前必须先做 machine-readable 生命周期分类
- **场景**：formal Prism follow-up redteam 中，Historian / Challenger / Explorer 都指出 `prism/runs/` 下同时混有 418 个 acceptance 夹具、当前 formal run、以及 `debug-run` / `council-*` / `review-*` 这类命名本地证据。如果没有 machine-readable lifecycle，哪怕拿到“可以清理”的授权，也无法安全判断哪些能删、哪些必须保留
- **根因**：此前只有“未经批准不要删”的负面约束，没有“批准后按什么规则删”的正面判定面。结果就是既不能安全清理，也不能诚实说出 token 风险到底来自哪一类残留
- **经验规则**：① `prism/runs` 必须先按 `acceptance-fixture / formal-run / named-local-evidence / infra-locks` 分类 ② 自动清理安全集只能包含非 active、未被报告绑定的 `acceptance-fixture` ③ formal run、named/manual run 与 `.locks` 默认 preserve，不得被“顺手清理”波及
- **来源**：2026-04-21，formal Prism follow-up（run `20260421-redteam-001`）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-21

### L-100: 完整用户项目 E2E 队列不能只有 benchmark 说明，必须有 repo-owned benchmark carrier
- **场景**：`pending-validations.md` 里 7 项完整用户项目 E2E 队列长期挂起，根因不是验证点没有定义，而是仓库里只有 `benchmark-scenario.md` 这份纸面说明，没有一个可以真正初始化出来的 benchmark carrier。结果每次想清这些项，都还要先临时寻找“真实用户项目上下文”
- **根因**：把“测试场景定义”误当成“测试载体已经存在”。前者只告诉你测什么，后者才解决“在哪个可重放的项目上下文里执行”
- **经验规则**：① benchmark-scenario 一旦成为长期待验证队列的唯一执行依据，就必须同步提供 repo-owned benchmark carrier 生成器 ② carrier 解决的是“可执行载体缺失”，不等于验证项已消费；真正消费仍要走 `e2e-session.yaml`、`latest-e2e-report.md`、`pending-validations.md` 与 postcheck ③ 后续完整用户项目 E2E 应优先使用固定 carrier，而不是临时抓一个外部项目来碰运气
- **来源**：2026-04-21，formal Prism follow-up（run `20260421-redteam-001`）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-21

### L-101: `codex` 宿主下的 stop-review 不能把 `codex` 自己排到最后，也不能让 `copilot` reviewer 子进程再触发 task-complete guard
- **场景**：formal Prism follow-up 补丁落成后，真实 `session-end` 再次回放时，`stop-review` 在 `codex` 宿主下先后出现两层问题：一开始默认 reviewer 顺序把 `codex` 排到最后，导致它先撞 `gemini/copilot`；顺序修正后，`codex` timeout 再 fallback 到 `copilot` 时，又被 `copilot` reviewer 子进程触发自己的 `task-complete guard`，让 stop-review 进入宿主内递归/挂起风险
- **根因**：一是 `redcap-on-stop-review.sh` 里 `REVIEW_HOST=codex` 的默认顺序仍残留旧写法，没有跟“优先健康的 Codex，再 fallback”这条治理结论同步；二是 reviewer CLI 作为“被调评审子进程”运行时，没有显式抑制 repo-owned completion hook，导致宿主把评审过程误认成新的任务完成事件
- **经验规则**：① `codex` 宿主下的默认 reviewer 顺序必须优先尝试 `codex`，不能把它降到最后 ② 任一 reviewer CLI 若可能触发宿主 completion hook，stop-review 在调用它时必须显式传入抑制标记，让 guard 直接 no-op ③ 这类 reviewer 路由/宿主隔离修补必须配 targeted acceptance，至少覆盖“codex host 默认优先 codex”和“copilot fallback 时已拿到 suppress guard 环境变量”两条回归
- **来源**：2026-04-21，live closeout follow-up 最后一公里（`c2058de` pending closure 清账前）
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-21

### L-102: shell heredoc 调 Python 时，参数位置写反会把数据文件当脚本执行
- **场景**：完整用户项目 E2E tranche 中实际调用 `compass/tools/redcap-check-state.sh` 时，脚本没有读取 `state.yaml`，而是把 `state.yaml` 本身当成 Python 脚本执行，直接抛出 `SyntaxError`
- **根因**：`python3 <<'PYEOF' "$STATE_FILE" "$DEV_MANUAL"` 把位置参数写在 heredoc 重定向之后，等价于执行 `python3 "$STATE_FILE" "$DEV_MANUAL"`。这里 `state.yaml` 被 Python 当成脚本文件，不再从标准输入读取内联程序
- **经验规则**：① 通过 heredoc 调 Python 时，若要同时传位置参数，必须写成 `python3 - "$arg1" "$arg2" <<'PY'` ② 任何“脚本校验器”第一次用于真实 E2E 前都要先跑一遍物理 smoke，不能只靠静态阅读脚本自信 ③ 这类调用错误应优先补 targeted acceptance，避免再次静默回归
- **来源**：md-table-tool benchmark E2E tranche / V-2 收口
- **发现日期**：2026-04
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-103: `on_QA_PASS` 的 state guard 必须 fail-closed，不能把不一致 state 只当警告
- **场景**：同一轮 E2E 中，`redcap-on-qa-pass.sh` 即使拿到 `redcap-check-state.sh` 的非零退出码，也只是打印一条警告然后继续执行后续动作
- **根因**：`on_QA_PASS` 把 state guard 当成 advisory check，而不是 gate。这样一来，state.yaml 不一致时，后续 git/lesson 流程仍会继续推进，违背了 V-2 对“校验失败时阻断流程”的预期
- **经验规则**：① 任何用于守住账本一致性的 guard，只要其职责是“阻止错误状态继续传播”，就必须 fail-closed ② hook/validator 的调用方必须显式传播 guard 的失败，不允许把状态不一致退化成日志提示 ③ 验证这类 gate 时必须同时覆盖“正常通过”和“失败阻断”两条物理路径
- **来源**：md-table-tool benchmark E2E tranche / V-2 收口
- **发现日期**：2026-04
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04

### L-104: 完整用户项目 E2E 可用“固定 benchmark carrier + focused replay 副本”高密度消费历史验证队列
- **场景**：`pending-validations.md` 中剩余 7 项条目并不适合都在一条从零开始的项目链里硬塞；若每项都重跑一次绿地项目，token 和时间成本都会显著膨胀
- **根因**：完整用户项目 E2E 同时承担“真实项目主链验证”和“特定状态路径回放”两类目标。把两者绑成同一条超长 run，会让无关步骤反复重演，效率极低
- **经验规则**：① 先用固定 benchmark carrier 跑一条 smoke/multi-step 主链，确认项目可交付 ② 再从该完成版派生 focused replay 副本，分别验证 rollback / escalation / infra 等特定路径 ③ focused 副本仍需维护独立 `开发手册/.workflow` 与最终回归，不能只写空报告 ④ 这种模式适合清历史验证队列，但必须在最终 E2E 报告里诚实注明“副本回放”而非伪装成多次绿地项目
- **来源**：md-table-tool benchmark E2E tranche / V-4,V-6,V-7,V-8,V-9 收口
- **发现日期**：2026-04
- **影响度**：medium
- **复现次数**：1
- **最后命中**：2026-04

### L-105: reviewer / Prism 选型不能长期继承某次 live 修补的静态家族偏置，必须回到“模型能力 + 本地稳定性”的统一排序
- **场景**：此前为了修复 `codex` 宿主 live closeout 的 stop-review 缺口，仓库一度把“优先健康的 Codex，再 fallback”固化成默认顺序；与此同时，另一条文档口径又把外部审查写成“优先 Gemini/Kimi CLI”。两种历史补丁都带着强场景色彩，最终让 reviewer 选择逻辑出现彼此冲突的静态偏置
- **根因**：把一次 live 事故里的“局部最优修补”误抬升成长期全局排序规则；同时 stop-review 真脚本、能力矩阵与文档没有共享同一套机器可消费的 reviewer 选型真相源
- **经验规则**：① reviewer / stop-review / Prism 的默认候选排序必须统一回到 `model-capability-matrix.yaml`：第一层看业内模型能力画像，第二层看本机该 CLI 的 headless / review 稳定性 ② `Copilot` / `Codex` 不能被静态压低，`Gemini` / `Kimi` 也不能因历史习惯被静态抬高 ③ `Codex-family ≤ 2` 只是并发控制红线，不是排序上的惩罚项或奖励项 ④ 如需强制手工顺序，只能通过显式 override（如测试夹具、临时事故绕行），不能反向改写默认算法
- **来源**：2026-04-21，用户要求移除 Copilot/Codex 静态优先级限制后，对 stop-review / matrix / agent-adapters 的统一收敛补丁
- **影响度**：high
- **复现次数**：1
- **最后命中**：2026-04-21
