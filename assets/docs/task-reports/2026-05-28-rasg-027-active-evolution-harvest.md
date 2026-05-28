# 任务完成报告：RASG-027 自我升级实体化

## 零、先看懂当前局面

这轮要解决的核心问题不是“再写一条经验沉淀规则”，而是修掉一个更底层的缺口：RedCap 过去能检查候选池里已经登记的经验项，却不能证明高价值信号已经被主动发现。也就是说，如果一次任务暴露了值得沉淀的 bug、纠偏或方法论，但 Agent 没有主动登记，旧机制很容易只靠报告文字蒙混过关。

### 0.1 当前已完成

- 当前已完成：RASG-027 已把自我升级从“报告里手写候选处理小节”推进为“主动收割账本”。现在高价值任务信号需要先生成 harvest 记录，再明确进入候选、暂缓或不晋升；如果缺少这条记录，检查会失败。

### 0.2 上一步完成的是

- 上一步完成的是：revive 外部工作区边界热修，确保外部项目执行 `redcap revive` 时不会误读 RedCap 自己仓库的任务卡。该热修已经生成 receipt，并作为本轮真实历史样本，被新的 harvest 产线处理。

### 0.3 下一步计划做的是

- 下一步计划做的是：本轮完成 RASG-027 后，父任务线继续推进后续债务项：公共武器库真实扩容、目录结构最终收敛、以及反空转方法论沉淀。它们不能被 RASG-027 冒充完成。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：先修 revive 工作区边界，再修主动 harvest 生产线，然后继续公共武器库、目录收敛和反空转方法论，最后才进入正式发布授权。
- 当前所在位置：正式发布前历史债务治理中的“自我升级能力补强”。

整体脉络：

- 已完成：revive 工作区边界热修，避免外部项目状态混入 RedCap 自身开发状态。
- 本轮完成：主动 harvest 生产线，让 RedCap 能主动抓住值得沉淀的经验信号。
- 后续待做：把抓到的高价值经验安全蒸馏进公共武器库，并继续治理历史目录与长期记忆能力。
- 仍未触碰：正式 npm 发布授权、registry、版本发布开关。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：没有触发 secret、不可恢复删除、正式发布授权或产品方向保留决策。

## 一、需求背景

Norven 多次指出 RedCap 的“自我升级”和“公共武器库”长期停留在记录、报告和声明层面，没有稳定地在真实任务中自动触发。尤其是经验沉淀失效在第一步：不是候选池没有规则，而是值得进入候选池的信号根本没有被稳定发现。

本轮 RASG-027 的目标就是把这个第一步补上：任务完成前，RedCap 必须能证明高价值信号已经被主动处理过，而不是只让报告作者写一句“没有新增候选”。

## 二、方案讨论

采用的方案是“主动收割账本”：

- 任务卡、任务报告、用户纠偏、review/bugfix 标签、closeout 与回归信号会被生产器汇总成 harvest 记录。
- 每条记录必须有来源、摘要、证据路径、处理结论和理由。
- 处理结论只允许三类：进入候选、不晋升、暂缓并指定 owner 和触发条件。
- 检查器不再只看报告章节；对高价值信号，如果没有新鲜的 harvest 记录，就判定失败。

这个方案的重点是把“是否值得沉淀”从主观口头判断，变成可追踪、可复验、可阻断的工程事实。

## 三、落地结果

已落地的结果：

- 新增主动 harvest ledger，用来记录真实收割结果，而不是替代候选池或公共武器库。
- 新增 harvest producer，可从任务卡和报告生成结构化记录，也支持对历史报告做只读样本处理。
- 新增 harvest ledger checker，校验记录字段、证据路径、处理结论和候选引用。
- 加固 harvest gate：高价值任务如果缺少新鲜记录，不能通过。
- 接入 diagnose、spec-check、closeout runtime 和 progress meter，让这条产线不是孤立脚本。
- 更新文件查阅字典、执行保障、Evolution README 与包公开面证明，使新增脚本处在可查、可验、可发布边界内。
- 同步了因新增脚本带来的 release-readiness 快照和哈希链，避免旧快照把新实现误判为游离资产。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 人话解释 | 本轮作用 |
|---|---|---|
| harvest ledger | 自我升级的收割账本 | 记录“这次任务有没有值得沉淀的经验，以及怎么处理” |
| harvest producer | 收割记录生成器 | 从任务卡和报告生成机器可检查的记录 |
| harvest gate | 收割检查门 | 防止高价值信号没有记录却被当作完成 |
| candidate pool | 候选池 | 只承接真正需要后续沉淀的事项，不再负责发现信号 |
| no-promote | 不晋升 | 表示已经评估过，但本事项不需要再变成普通候选 |

## 四、人工审核要点

Norven 需要知道的结论是：本轮没有宣称公共武器库已经扩容，也没有宣称 full LLM-wiki 已经实现。它只把“发现高价值经验”这一步实体化。

如果后续继续推进 RASG-028/RASG-030，这条产线会成为前置保障：先发现并登记，再决定是否蒸馏、公开、延期或拒绝。

## 五、验证结果

已通过的验证：

- `python3 -m py_compile` 覆盖新增 Python 脚本与被修改检查器。
- `bash compass/tools/redcap-evolution-harvest-ledger-check.sh`
- `bash compass/tools/redcap-progress-meter-check.sh`
- `bash compass/tools/redcap-file-lookup-dictionary-check.sh`
- `bash compass/tools/redcap-multi-session-acceptance.sh evolution-harvest-check`
- `bash compass/tools/redcap-r1-control-plane-contract-split-check.sh`
- `bash compass/tools/redcap-r1-prism-evidence-retention-split-check.sh`
- `bash compass/tools/redcap-formal-release-r1-root-group-disposition-check.sh`
- `bash compass/tools/redcap-r1-layera-product-boundary-check.sh`
- `bash compass/tools/redcap-spec-check.sh "$PWD"`
- `bash compass/tools/redcap-prism-acceptance-bind.sh --run-id 20260528-rasg-027-active-evolution-harvest --task-file .dev-task.md`

spec-check 曾连续抓出多处发布边界快照和哈希链过期问题；这些不是新功能失败，而是新增 4 个控制面脚本后，旧证明文件必须同步刷新。当前已逐项修复并复验。

复验期间还抓到一个并发写入问题：两个检查链同时触发 identity 本地状态初始化时，会争抢同一个临时文件。已改为按进程号生成临时文件，并用 `redcap-runtime-workspace-boundary-check` 复验通过，避免长任务并行门禁互相误伤。

棱镜复核结果：Kimi 与 Claude Code 均返回 pass、无 blocker。Kimi 提醒 `spec-check` 也应直接执行当前任务 harvest gate；该建议已在本轮补齐，并重新通过 `spec-check`。

### 5.4 完成等级（禁止混报）

| 完成层级 | 结论 |
|---|---|
| 已实现 | 是，RASG-027 主动 Evolution harvest 生产线已实现并接入主要检查链。 |
| 已自检 | 是，基础脚本、acceptance、spec-check 与包边界证明已自检通过。 |
| 已独立验收 | 是，Kimi 与 Claude Code targeted review 均 pass，且无 blocker。 |
| 已正式完成 | 否，仍待最终 closeout receipt。 |

本轮不可声明完成：公共武器库批量扩容、full LLM-wiki、目录最终收敛、正式 npm 发布。

## 六、遗留问题与下一步

本轮不覆盖以下任务：

- RASG-028：公共武器库真实扩容与重复检测。
- RASG-029：工程目录最终结构收敛。
- RASG-030：反空转方法论完整沉淀。
- 正式 npm 发布、发布授权、registry 登录态、版本号与 license 决策。

这些仍应继续作为父任务线后续工作，不应被本报告关闭。

## 七、经验沉淀

### 7.1 问题源

旧机制的问题不是“没有经验库”，而是缺少主动发现层。只检查候选池是否清空，会漏掉“本该生成候选但没有生成”的情况。

### 7.2 解决方案

把发现层变成机器账本：先生成 harvest 记录，再决定候选、不晋升或延期；并让 closeout/spec/diagnose 都能检查这条记录。

### 7.3 Evolution Factory 候选处理

- 处理结论：no-promote
- 记录依据：本轮 RASG-027 本身已经把“主动发现与候选化”升级为 RedCap 原生控制面能力，不需要再把同一事项重复登记为普通候选。
- 已生成记录：`compass/evolution/harvest-ledger.json` 中的真实历史样本记录已经覆盖 revive workspace boundary 热修。
- 后续关系：RASG-028/RASG-030 会继续使用这条生产线处理公共武器库与反空转方法论沉淀。

### 7.4 最后效果

后续任务如果出现明显值得沉淀的经验信号，却没有对应 harvest 记录，检查会失败。这比“报告里写一下是否沉淀”更接近 Norven 要求的强保障。

## 八、附录

关键产物：

- `compass/evolution/harvest-ledger.json`
- `compass/tools/redcap-evolution-harvest-producer.py`
- `compass/tools/redcap-evolution-harvest-ledger-check.py`
- `compass/tools/redcap-evolution-harvest-check.py`
- `assets/references/execution-guarantees.json`
- `assets/references/file-lookup-dictionary.md`

关键边界：

- 不读取私密文件。
- 不修改 identity 原文。
- 不执行正式发布。
- 不做不可恢复删除。
