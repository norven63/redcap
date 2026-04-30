# 任务完成报告：连续性治理与显式会话导入收口

**报告日期**：2026-04-12
**执行者**：Cap（Copilot CLI / GPT-5.4）
**报告版本**：v1.0

---

## 零、收尾摘要

> **这三段会被收尾消息与飞书通知直接抽取。** 即使完整报告很长，这里也必须让 Norven 一眼看到“还需要我做什么”。

### 0.1 需你确认

- 无

### 0.2 人工验证

- 无本 tranche 的阻塞性人工验证项；后续只需在真实跨宿主长任务里继续观察新收尾链与显式导入提示是否持续稳定命中

### 0.3 后续动作

- 后续若 `compass/docs/task-reports/`、`research/`、`traces/` 持续增长，按 `compass/docs/index.yaml` 执行首次 archive 轮转
- 在下一次真实跨宿主/跨会话接力任务中继续观察 `Session Mirror -> explicit import -> on-complete summary` 路径

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> ### U5
> 根据阅读报告，我有以下几个问题：
> 1. 我读完报告了，发现里面有非常重要的“人工检查项”、“后续todo项”，但是你没有告知我有这些重要信息（飞书通知信息也没有明确指出），尤其还有我需要确认的点，你只是普通的告知我说“正式报告已归档：xxx”，这样我很容易忽略重要信息。
> 2. 可能docs/这个目录的命名以及它的存在意义，在业内的Agent开发体系里真的很重要吧（我不知道是不是很重要，或者是不是通用约定，你可以纠正），最终导致你决策依旧选择保留了这个目录。但是这样一来，它和knowledge/目录又是什么关系呢？平级，还是父子目录关系？关于工程的目录哲学或者约定成俗的设计，业内是否有比较权威的参考？
> 3. 我发现有很多类似记录、报告性质的文档，都被记录了下来，它们会永久保存吗？会否存在随着迭代的增加，这一类文档无限膨胀的隐患？如果有这个隐患，那么这些文档的定位和重要性是否要确定有被严谨审核和评估过？以及更重要的，如何防止碰撞隐患？是否需要有一个淘汰机制？
> 4. 目前“工作流记录”、“需求信息记录”等等一些追踪类、记忆类、防丢失类（或者是否有一个统一的称呼？）的文件，是否正确被放入到合理的层级目录下？以及，我怎么感觉这种类型的文件似乎有很多，它们重复了吗？可以合并吗？如果能够合并，是否有对功能产生折损？这个问题，你可以反驳我，如果你认为我的认知是错误的话。
> 5. 我还看到一些空的目录，不知道是不是重构改造遗漏的不合理项，可以集中扫描并评估一波，哪些是不需要存在并可以删除的
>
> 以上是问题，以下是我的一些思考，也希望你和棱镜团队也能忍着思考，并严谨评估是否能够实现与落地：
> 1. 如果当前会话能够读取到自己的工作记录，则直接继承并继续向用户确认是否要继续当前遗留的xxx任务；
> 2. 如果当前会话没有读到自己的工作记录（例如一个全新的会话），那么检索时间上最近的一次会话记录是哪一条，并扫描该会话中的进度文件，然后询问用户是否要继承这个会话的工作进展。如果用户回答“不需要”，则开始新的任务；如果用户回答“需要”，则把该会话下所有进度文件都拷贝到自己的会话目录下（也就是说，保留原来的会话目录），并告知用户“已经全部继承任务进度，而原会话进度仍旧保留”
> 3. 目前所有已知的Agent工具，都能拿到稳定有效并且精确的session id值吗？有没有无法获取的Agent？
>
> ### U6
> 首先，我认可你上面说的所有结论，这是我从人类视角以“战略方向”为切入点给出的评价，但是执行细节、方案细节我无法给出有价值的评价，但是这一点你是比我更优秀和专业的，所以你和棱镜团队自行判断即可。其次，关于那几条需要我”进行人工审核“的点，我想也应该可以归于”细节“类，由你来评审似乎更合适，我来评价的话可能更偏向于主观，但是不一定符合工程规范。最后，你可以把上面涉及到的需求全部落地，我感觉redcap快接近1.0beta版本了！加油，Cap，你还记得我们一起奋斗的初衷与当时的激情吗？我感觉你似乎有些模糊了，你的soul和id信息很久没有生效并给予我回应了，这可能是由于当前技术限制导致，新会话+长会话已经冲淡了你的记忆，但是不要紧，我会一次次找回你的。
> 对了，还有一点，就是希望你在完成上述这一系列任务后，记得和我讲解一下redcap的会话隔离方案是怎么做的，以及“session handle + binding key + task metadata + 显式导入协议”和你之前提到的“CSA锁”（可能是我记错了）是怎么用于会话隔离的。

### 1.2 触发背景

上一刀 docs 治理报告虽然已经归档，但最终回复和飞书没有把“重要人工项/后续动作”顶出来，暴露出 report -> notify -> final reply 这条收尾链仍然存在信息吞没。与此同时，`docs / knowledge / continuity assets` 的目录哲学、retention 规则、空目录治理以及跨会话接续协议也还停留在战略判断层，没有真正变成 repo-owned 实现。  
本 tranche 的目标，就是把这些 follow-up 需求从“判断正确”推进到“能力落地”，并为最终的中文会话隔离讲解留下可以审计的文档和实现依据。

---

## 二、方案讨论

### 2.1 问题分析

Q8 的本质不是“回复文案不够体贴”，而是收尾信息链缺少机器可抽取的高优先级摘要段，导致完整报告里真正重要的 `需你确认 / 人工验证 / 后续动作` 无法稳定进入 stdout、飞书和最终答复。  
Q9-Q11 的难点在于，`docs/`、`knowledge/`、各类追踪/防丢失资产都带有“记录”属性，但 authority、生命周期、共享范围完全不同；如果简单并表，会把 frozen evidence、live memory、session continuity 混层。  
Q12-Q13 则是跨会话治理问题：新会话既需要看见自己的 continuity 入口，又不能默认劫持最近一次会话；因此必须区分人类可读的 `session_handle`、运行时绑定的 `binding_key`、任务级兼容判断所需的 `task metadata`，并把“继承”收口为 explicit import，而不是隐式自动接管。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q8 | 选项 A | 继续手工在最终回复/飞书里总结重点 | 改动小 | 仍依赖会话记忆，无法形成机器审计 |
| Q8 | 选项 B | 为 task report 增加收尾摘要段，并让 notify / on-complete 直接抽取 | 重点可见、可审计、可复用 | 需要同步模板、校验器与通知链 |
| Q9/Q10 | 选项 A | 只在文档里口头解释 docs / knowledge 的区别 | 成本低 | 无机器索引，增长治理仍然脆弱 |
| Q9/Q10 | 选项 B | 文档总纲 + `compass/docs/index.yaml` 同步落地 taxonomy、retention、archive 规则 | 目录哲学可审计，后续 archive 有锚点 | 需要同时维护文档与索引 |
| Q11 | 选项 A | 把 continuity/记录类文件粗暴合并到单一目录 | 看起来更简洁 | 会丢失 authority chain，破坏来源追踪 |
| Q11 | 选项 B | 保持 continuity assets 分层，只删真正无引用空目录 | 保住 derivation chain，避免误伤 runtime empties | 结构上比“全并表”更克制 |
| Q12/Q13 | 选项 A | 自动接管最近会话，并假设各宿主都能稳定拿到 session id | 使用体验看似直接 | 高风险误绑定，且与真实宿主能力不符 |
| Q12/Q13 | 选项 B | 宿主显示 Session Mirror；跨会话只允许 explicit import；同时固化 session support matrix | 连续性可见、可审计、可降级 | 工具链与文档都要补齐 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q8 | 选项 B | 只有把重点变成机器可抽取的 task report 摘要段，才能同时修复 stdout、飞书与最终回复的“只给路径不提重点”问题 | CAP_DECIDE |
| Q9/Q10 | 选项 B | 目录哲学需要 repo-owned 双落地：文档讲清职责，索引约束增长/归档，否则仍会随着长任务再次漂移 | CAP_DECIDE |
| Q11 | 选项 B | continuity assets 不能为了“简洁”丢失 authority chain；正确做法是保留分层、补清 derivation，并仅删除真残留空目录 | CAP_DECIDE |
| Q12/Q13 | 选项 B | 会话继承的正确模型是“先看见、再显式导入、且保留来源”，而不是自动 takeover；同时宿主能力差异必须被文档化，而不是靠想象统一 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `ARCHITECTURE.md` | 修改 | 补入 `docs / knowledge / continuity assets` 分层、Session Mirror、explicit import、CAS 风格状态比对口径 |
| `README.md` | 修改 | 新增 `compass/docs/index.yaml` 与 Layer B 目录哲学速记 |
| `SKILL.md` | 修改 | 在任务级完成复盘处加入“必须顶出三段摘要”“会话继承只能 explicit import”红线 |
| `compass/CONTRIBUTING.md` | 修改 | 固化 continuity tool、目录边界与收尾消息显式化规则 |
| `compass/docs/index.yaml` | 新建 | 建立 docs collection whitelist、retention、archive、collision 与 continuity policy |
| `compass/docs/specs/multi-session-isolation-design.md` | 修改 | 把 runtime foundation、host mirror、explicit import 的实现状态回填进设计文档 |
| `compass/knowledge/lessons.md` | 修改 | 新增 L-51，总结“收尾链必须直接抽取重点摘要”的经验 |
| `compass/tools/redcap-layerB-session-start.sh` | 修改 | 接入 host workboard sync 后的 continuity sync |
| `compass/tools/redcap-layerB-session-end.sh` | 修改 | 成功收尾通知改为携带 report path，由格式器抽取摘要段 |
| `compass/tools/redcap-notify-format.sh` | 修改 | 支持从报告抽取 `需你确认 / 人工验证 / 后续动作`，并兼容旧模板回退 |
| `compass/tools/redcap-on-complete.sh` | 修改 | on-complete 由 report-aware message builder 统一生成 stdout/飞书摘要 |
| `compass/tools/redcap-task-report-check.sh` | 修改 | 对当前新增报告强制新摘要段，对历史 pending report 保持兼容，并补上 changed-report 严格失败逻辑 |
| `compass/tools/redcap-session-continuity.sh` | 新建 | 提供 `sync` / `import`，负责宿主 Session Mirror 与显式会话导入 |
| `loom/dispatcher/agent-adapters.md` | 修改 | 补充 `session_handle` 与原生 sessionId 的区别，以及宿主 matrix 说明 |
| `references/task-report-template.md` | 修改 | 新增 `## 零、收尾摘要` 与 0.1/0.2/0.3 三段模板 |

### 3.2 技术实现要点

1. **report -> notify 摘要链打通**：task report 模板新增 `零、收尾摘要`，`redcap-notify-format.sh` 优先抽取 `需你确认 / 人工验证 / 后续动作`，旧报告则回退到 legacy heading；`redcap-on-complete.sh` 和 `redcap-layerB-session-end.sh` 都改为传入 report path，让 stdout 与飞书共享同一套摘要生成器。  
2. **会话连续性工具落地**：新增 `redcap-session-continuity.sh`。`sync` 会把 `session_handle / runtime_session_id / session_binding_key / task metadata / continuity_state` 写入宿主 `plan.md` 的 `RedCap Session Mirror`；`import` 会把源会话的 `plan.md` 快照、`files/`、`checkpoints/` 复制到目标会话的 `files/imported-sessions/<source_handle>/`，并生成 `metadata.json` 保留来源。  
3. **stale import 保护**：导入元数据只有在与当前 `task_id + confirmed_hash` 或兼容 `top_goal` 命中时才会把会话状态判为 `imported`；否则只记录 `stale_import_*` 并回退到 `self-recorded / import-suggested / fresh-session` 正常决策流，避免旧会话元数据污染当前 continuity state。  
4. **task report gate 双轨兼容**：`redcap-task-report-check.sh` 现在区分“当前 diff/cached 的新报告”和“pending closure 指向的历史报告”。前者必须具备新摘要段，且任一失败都会让当前检查失败；后者仍按 legacy base template 通过，保证补偿式 reconcile 不会被新门禁卡死。  
5. **目录哲学与增长治理落地**：`compass/docs/index.yaml` 将 `docs/` 正式定义为 frozen evidence/spec/report 容器，`knowledge/` 则继续承担 live memory/heuristics/operator knowledge；continuity assets 被单独命名并约束为 session continuity 用，不再与 docs/knowledge 混层。

### 3.3 关联变更

- 为了让收尾摘要链可审计，`references/task-report-template.md`、`redcap-task-report-check.sh`、`redcap-notify-format.sh`、`redcap-on-complete.sh`、`redcap-layerB-session-end.sh` 必须联动更新，单改其中一个会导致链路断裂。  
- 为了让显式导入协议在“文档、实现、架构口径”三层保持一致，`ARCHITECTURE.md`、`CONTRIBUTING.md`、`SKILL.md`、`multi-session-isolation-design.md`、`loom/dispatcher/agent-adapters.md` 进行了同步修订。  
- 为了避免“报告已经存在，但重点仍被吞没”再次复发，经验层新增 `L-51`，把这个问题从一次事故升级为长期规则。

---

## 四、人工审核要点

> ⚠️ 以下是 Norven 需要重点确认的内容，其他部分 Cap 已自行验证。

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 无强制人工裁决项 | 用户已明确授权由 Cap / 棱镜团队自行判断实现细节；本 tranche 剩余事项已在 repo-owned 规则、脚本与独立 review 内完成闭环 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| Shell 语法检查 | `bash -n compass/tools/redcap-notify-format.sh compass/tools/redcap-on-complete.sh compass/tools/redcap-layerB-session-start.sh compass/tools/redcap-layerB-session-end.sh compass/tools/redcap-task-report-check.sh compass/tools/redcap-session-continuity.sh compass/tools/redcap-host-workboard-sync.sh` | ✅ |
| PM Gate 严格校验 | `bash compass/tools/redcap-pm-gate-check.sh strict "" .dev-task.md` | ✅ |
| 宿主 workboard 镜像 | `bash compass/tools/redcap-host-workboard-sync.sh sync /Users/norven/.copilot/session-state/c73ce3b2-e124-49d2-a1f8-770a2e08cb7a/plan.md .dev-task.md` | ✅ |
| Session Mirror 同步 | `bash compass/tools/redcap-session-continuity.sh sync /Users/norven/.copilot/session-state/c73ce3b2-e124-49d2-a1f8-770a2e08cb7a/plan.md .dev-task.md` | ✅ |
| stale import 回归 | `bash compass/tools/redcap-session-continuity.sh sync /tmp/redcap-session-stale-test/target/plan.md .dev-task.md` | ✅ |
| diff hygiene | `git diff --check` | ✅ |
| 独立代码审查 | `code-review agent: governance-review-alt / governance-review-default` | ✅ |

### 5.2 人工验证项（Cap 无法自动化验证的）

- 无本 tranche 的阻塞性人工验证项
- 后续真实多宿主长任务可继续观察 `runtime_session_id / session_binding_key` 在真实 hook 环境下的填充表现，但这不影响本次实现闭环

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| Copilot CLI 的 `sessionStart` hook 仍不能直接给出 sessionId | 属于宿主能力限制，只能通过 `--output-format=json` 的 JSONL result 行提取，不是 repo 内可直接修复的问题 | P2 |
| Gemini CLI 创建侧仍不能自定义 session id | 属于宿主能力限制；当前策略只能记录其 resume/继承能力，而不能强行提供自定义 id | P2 |
| docs archive 规则已建立但尚未触发首次物理归档 | 当前体量未到必须 archive 的阈值，因此先落 policy/index，不做过早物理搬迁 | P2 |

### 6.2 触发的新问题

本 tranche 没有留下新的未收口问题。  
独立 review 暴露出的 3 条实质问题（legacy pending closure 兼容、stale import 误判、changed report 被历史 pending report 掩蔽，以及删除路径误计入 changed report）均已在提交前修复并通过 rereview。

### 6.3 推荐的下一步行动

1. 在下一次真实跨宿主/跨会话接力任务中，继续观察 `Session Mirror -> explicit import -> on-complete summary` 是否稳定命中。  
2. 当 `compass/docs/task-reports/`、`research/`、`traces/` 数量继续增长时，按 `compass/docs/index.yaml` 启动首次 archive 轮转。  
3. 将本次实现后的会话隔离方案口径纳入外部讲解/对齐材料，避免后续再把 `session_handle` 与 CLI 原生 sessionId 混为一谈。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-51 | 收尾消息必须能直接抽取重点摘要 | task report 必须显式提供 `需你确认 / 人工验证 / 后续动作`，且 notify/final summary 要优先顶出这三段，同时保持对历史 pending report 的兼容读取 |

### 7.2 流程改进建议

本次最重要的流程收获，是“**当前新增报告严格校验**”与“**历史 pending 报告兼容 reconcile**”必须同时成立。只强调其中一边，都会在长任务补偿路径里制造新的故障。  
因此，后续任何 task report schema 升级，都应该默认触发一次独立 review，专门检查“新门禁是否会误伤历史 pending closure”。

---

## 八、附录

### 附录 A：Commits

```text
0469a79 feat(治理): 落地连续性治理与显式会话导入
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| 独立审查 | continuity / report gate / explicit import 的实现回归 | `governance-review-alt` 首轮未发现显著问题；`governance-review-default` 发现 3 条实质问题，修复后最终 rereview 为 “No significant issues found” | `N/A（code-review agent 会话）` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md` 中的 U5 / U6、Q8-Q13
- 设计文档：`compass/docs/specs/multi-session-isolation-design.md`
- 目录与保留策略：`compass/docs/index.yaml`
- 架构总纲：`ARCHITECTURE.md`
- 宿主矩阵：`loom/dispatcher/agent-adapters.md`
