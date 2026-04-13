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

### L-51: 收尾消息必须能直接抽取“需你确认 / 人工验证 / 后续动作”，不能只给报告路径
- **场景**：docs 治理 tranche 的正式报告已经写清了人工检查项与后续动作，但最终回复与飞书通知只说“报告已归档”，导致真正需要人类注意的信息继续被埋在长报告里。进一步修复时又暴露出一个兼容性陷阱：若新模板强制摘要段，却让旧 pending closure 的历史报告一律失效，会反过来卡死补偿式 reconcile
- **根因**：① task report 模板缺少机器可抽取的收尾摘要段，notify/final 只能传路径 ② 把“报告已存在”误当成“人类已经看到了重点” ③ 新 schema 引入时没有区分“当前新增报告必须升级”与“历史 pending 报告需要兼容读取”的差别
- **经验规则**：① Layer B task report 开头必须显式提供 `需你确认 / 人工验证 / 后续动作` 三段摘要 ② stdout 收尾摘要、飞书通知与最终回复都要优先顶出这三段，再给报告路径 ③ 新报告门禁升级时，对当前新增报告可以更严格，但对历史 pending closure 必须保留 backward-compatible 读取能力，避免旧义务永远无法清除
- **来源**：2026-04-12，Norven 阅读 `2026-04-12-docs-governance-audit.md` 后指出信息被埋；随后在显式收尾与 report gate 改造中落地，并经独立 code review 反向暴露兼容性问题后修正
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
