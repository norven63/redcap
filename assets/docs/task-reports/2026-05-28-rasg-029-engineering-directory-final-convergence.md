# 任务完成报告：RASG-029 工程目录最终收敛

## 零、先看懂当前局面

这轮要解决的不是“把根目录做得看起来空一点”，而是回答一个更实在的问题：RedCap 为什么还有这么多根级路径，它们分别做什么，会不会继续污染上下文、包发布和后续自升级。

本轮结论很明确：`assets/` 是项目资产主位置；根目录保留的是人类入口、宿主入口、运行入口、包契约、评审系统、Layer A 兼容层和本地状态。旧路径主要是兼容桥，`prism/runs` 是本地运行证据，它们都不应该被默认读取，也不能因为“看起来旧”就被危险删除。

### 0.1 当前已完成

- 当前已完成：RASG-029 已把 RedCap 根目录重新解释成可验证的工程目录模型，并把兼容入口、`prism/runs` 生命周期、本地状态、包边界和正式发布边界同步到 manifest、README、ARCHITECTURE、assets README 和发布前硬门中。

### 0.2 上一步完成的是

- 上一步完成的是：RASG-028 让 redcap-arsenal 完成第二批真实公共条目扩容，避免“只有机制、没有内容”的公共武器库假完成。

### 0.3 下一步计划做的是

- 下一步计划做的是：完成 RASG-029 的最终回归、提交和 closeout receipt；通过后，发布之外的工程目录历史债务应只剩正式发布任务里的人工授权和 release readiness 边界。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：先修外部工作区边界，再补强主动经验收割，再让公共武器库真实增长，然后完成工程目录最终收敛，最后才进入正式发布授权。
- 当前所在位置：正式发布前历史债务治理中的“工程目录最终收敛”。

整体进度用人话概括如下：

- 已完成：revive 外部工作区边界热修、自我升级主动 harvest 产线、公共武器库第二批扩容。
- 本轮完成：工程目录不再按“旧路径名是否还在”来判断是否干净，而是按 owner、生命周期、包边界和读取规则来判断。
- 后续继续：正式发布任务中的许可证、发布开关、registry、版本号、发布回滚和高风险资产发布前复查。
- 仍未触碰：正式发布动作、危险删除、full LLM-wiki、RAG、GraphRAG。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮没有触发 secret、不可恢复删除、正式发布授权、license、registry 或用户保留产品决策。

## 一、需求背景

Norven 多次指出一个核心坏味：RedCap 的目录和资产治理耗时很长，却仍然容易让人看到分散的 `docs`、`knowledge`、`references`、`private-archive`、`prism/runs` 路径，从而怀疑“是不是一直在清理清理产生的新资产”。

RASG-029 因此被限定为一个发布前历史债务闭环：它必须证明当前工程目录结构是有意设计，而不是旧资产无序残留；也必须防止 RedCap 把“解释了为什么保留”冒充“已经物理删除”。

## 二、方案讨论

本轮采用的是“分类收敛”，不是“危险搬迁”：

- 对已经迁入 `assets/` 的长期资产，明确 `assets/` 是主位置，旧路径只是兼容桥。
- 对宿主入口、runtime 入口、包契约、控制面源码、Prism 系统和 Layer A 兼容层，明确它们为什么不能为了目录美观随便搬走。
- 对本地状态和运行证据，明确它们应当被忽略、排除出包、按生命周期检查，而不是塞进公共资产层。
- 对正式发布前仍需裁决的高风险问题，明确留给 release task，不在本轮偷偷删除或发布。

棱镜结论是 `pass_with_nits`，无 blocker。两个 nit 都已修复：一个是 assets README 的中文表达，另一个是 `retention_days=7` 的含义说明。

## 三、落地结果

本轮落地了三类结果：

| 结果 | 人话解释 | 作用 |
|---|---|---|
| 工程目录 manifest | 把根目录分成 11 类，并写清每类为什么存在 | 让目录结构从“看起来乱”变成“有 owner、有生命周期、有包边界” |
| 人类入口说明 | README、ARCHITECTURE、assets README 都补了根目录地图 | 让新接手的人不用先读内部门禁，也能理解当前结构 |
| 运行证据边界 | `prism/runs` 明确为本地 raw evidence，有 summary/check/safe apply 路径 | 阻止默认全文读取、误打包、误删证据和“清理无底洞” |

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 人话解释 | 本轮作用 |
|---|---|---|
| `assets/` | RedCap 长期资产主目录 | docs、knowledge、references、formal reports、private archive 都以这里为主位置 |
| 兼容桥 | 旧路径名继续指向新主位置 | 保护旧脚本、旧报告和 receipt，不让历史证据断链 |
| `prism/runs` | Prism 本地运行证据目录 | 不默认读取、不进入公开包、只通过生命周期工具安全检查 |
| release task | 正式发布专项任务 | 处理许可证、发布开关、registry、版本号、危险删除和发布风险接受 |
| manifest | 机器和人都能读的事实清单 | 固定本轮到底完成了什么、没完成什么、哪些路径为什么保留 |

## 四、人工审核要点

Norven 需要重点看三个结论：

- 第一，旧入口还在不是因为治理失败，而是因为它们承担兼容桥职责；新内容主位置已经是 `assets/`。
- 第二，`prism/runs` 不是要默认清空的垃圾目录，而是本地 raw evidence；它必须先保护可引用证据，再做有限、安全、显式的清理。
- 第三，本轮完成的是发布前非发布目录债务收敛，不是正式发布授权，也不是危险删除授权。

## 五、验证结果

已通过的验证：

- `bash compass/tools/redcap-root-information-architecture-check.sh`
- `bash compass/tools/redcap-root-ia-deferral-check.sh`
- `bash prism/tools/prism-runs-lifecycle.sh check`
- `bash compass/tools/redcap-public-package-surface.sh`
- `bash compass/tools/redcap-runtime-package-manifest.sh --check --npm-pack-dry-run`
- `bash compass/tools/redcap-package-publish-safety-check.sh`
- `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md`

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|---|---|
| closeout receipt | 无 |
| 当前状态 | 已完成实现、棱镜复核和主要回归，仍需最终 closeout runtime 生成 receipt |

### 5.4 完成等级（禁止混报）

| 完成层级 | 结论 |
|---|---|
| 已实现 | 是，工程目录 manifest、人类入口说明、兼容桥边界和 `prism/runs` 生命周期说明已落地。 |
| 已自检 | 是，root IA、延期根组、Prism runs、包公开面、候选包清单和发布安全检查已通过。 |
| 已独立验收 | 是，Kimi 与 Claude Code 均完成 targeted review，结论为 pass_with_nits、无 blocker。 |
| 已正式完成 | 否，仍待最终 closeout receipt。 |

## 六、遗留问题与下一步

本轮不覆盖以下事项：

- 正式发布、发布授权、版本号、registry、license 和发布回滚策略。
- full LLM-wiki、后台蒸馏 worker、RAG、GraphRAG 或向量库。
- 旧兼容入口的无条件物理删除。
- `prism/runs` 的无条件物理清空。

下一步是完成剩余回归、提交并生成 RASG-029 closeout receipt。receipt 通过后，发布之外已知工程目录历史债务才可以正式闭环。

## 七、经验沉淀

### 7.1 问题源

目录治理很容易变成“看起来还乱，所以继续清理”的无底洞。根因是没有把“主位置、兼容桥、运行证据、本地状态、发布边界”分开表达，导致任何旧路径名都会被误判成未完成债务。

### 7.2 解决方案

用分类收敛替代盲目搬迁：每个可见入口必须有 owner、生命周期、包边界和读取规则；旧入口如果是兼容桥，就明确它保护什么；运行证据如果不能安全删除，就明确检查和 apply 边界。

### 7.3 Evolution Factory 候选处理

- 处理结论：no-promote。
- 理由：本轮经验已经进入 RASG-029 manifest、README、ARCHITECTURE 和 assets README；同时 RASG-030 已沉淀过“机制完成不能冒充目标完成”的反空转方法论。本轮不再新增重复候选。
- 后续触发：如果未来 release task 真正执行兼容桥删除、Prism raw evidence 归档或 runtime profile split，需要重新沉淀更具体的迁移方法论。

### 7.4 最后效果

RedCap 现在可以用更清楚的方式回答“为什么目录还是这样”：因为根目录承载产品入口、宿主入口、runtime、控制面、Prism、Layer A 和本地状态；长期资产已经归到 `assets/`，旧路径保留是为了兼容和考古，而不是新的资产主线。

## 八、附录

关键证据：

- 目录收敛清单：`assets/references/rasg-029-engineering-directory-final-convergence-manifest.json`
- 根目录主计划：`assets/references/root-information-architecture-consolidation-plan.json`
- 剩余根组边界：`assets/references/root-ia-remaining-root-groups-deferral.json`
- 发布前历史资产硬门：`assets/references/historical-asset-physical-cleanup-release-gate.json`
- 棱镜运行：`prism/runs/20260528-rasg-029-engineering-directory-final-convergence/`
- 任务账本：`.dev-task.md`

关键边界：

- 不执行正式发布。
- 不改 license、registry、版本号或发布开关。
- 不读取、迁移或发布私密原文、identity、secret、Prism raw transcript。
- 不做不可恢复删除。
- 不把 RASG-029 冒充 release readiness 已完成。
