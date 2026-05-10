# 任务完成报告：RASG-017 根目录信息架构目标模型

## 0.1 当前已完成

- 当前已完成：RedCap 已为“根目录直接父级过散、知识/报告/证据/模板语义重叠”这项历史债务产出可审查的根目录信息架构目标模型。
- 关键结论：本轮没有搬目录、删资产或发布 npm；完成的是施工图和硬门禁。后续如果要真实移动目录，必须另开 apply 任务，重新经过别名、回滚、棱镜评审、package safety、clean workspace E2E 和 receipt。

## 0.2 上一步

- 上一步完成的是：`RASG-018` 全局架构坏味审判，确认 `RASG-017` 是发布准备前仍需处理的结构性历史债务。

## 0.3 下一步

- 下一步计划做的是：继续处理剩余开放债务 `RASG-019`、`RASG-020`、`RASG-021`。如果未来要执行真实根目录迁移，需要先把本报告中的目标模型转成单独的 apply tranche。

## 0.4 整体任务全景图与当前位置

- 整体计划脉络图是：全局坏味审判 -> 根目录目标模型 -> 人类输出去术语化 -> public runtime contract 分层 -> Prism 降级韧性 -> release readiness。
- 当前所在位置：`RASG-017` 规划已完成；发布前开放债务从 4 个降为 3 个。

## 0.5 是否需要 Norven 人工介入

不需要。本轮没有触发许可证、registry 凭据、公开发布、不可恢复删除或产品哲学强制二选一。真正需要 Norven 参与的是未来物理迁移前的方向确认，例如哪些根目录概念要保留为公开产品层、哪些要收进内部层。

## 1. 本轮解决的问题

用户此前指出：RedCap 虽然治理过 token 风险、报告膨胀、公共/私有边界和 package 白名单，但根目录本身仍像一个历史现场。`compass`、`prism`、`loom`、`references`、`runtime`、`redcap-knowledge`、`shared-knowledge` 等直接父级同时承载控制面、证据、知识、模板和 runtime 语义，对新用户和新 Agent 都不够直观。

这不是“所有目录必须合并成一个”的问题，而是产品骨架需要可解释：哪些是公开 runtime，哪些是宿主入口，哪些是内部治理，哪些是私有考古，哪些只是兼容期遗留。

## 2. 本轮如何解决

本轮新增一份机器可读目标模型：`references/root-information-architecture-consolidation-plan.json`。

它做了四件事：

- 第一，把当前根目录直接资产逐项登记，说明它现在做什么、给谁用、是否进 package、未来应归到哪类父级、迁移风险是什么。
- 第二，定义目标父级模型，把未来 RedCap 分成人类入口、宿主入口、公开 runtime、root 工具契约、内部控制面、Prism/证据、私有归档、公共模板、Layer A 兼容、工作区本地状态这些层。
- 第三，列出消费者影响矩阵，防止未来搬目录时漏掉 host entry、runtime facade、validator、Prism evidence、docs archaeology、package surface 和人类通知。
- 第四，写死后续 apply 门禁：本轮不允许物理迁移；未来每次迁移最多处理一个语义父级，并且必须有 dry-run、alias、rollback、棱镜、package safety、clean E2E 和 receipt。

## 3. 本轮补上的硬保障

新增 checker：`bash compass/tools/redcap-root-information-architecture-check.sh`。

它现在会阻断这些回退：

- 根目录出现新直接资产但没有登记。
- inventory 里写了不存在的目标父级。
- 目标父级模型缺关键层。
- 消费者矩阵缺关键消费方。
- 本轮 plan 声称已经物理迁移。
- `RASG-017` backlog 没有把 plan/checker/Prism/report 作为证据。

这个 checker 已接入 `spec-check` 和 `diagnose`，不是只停留在文档里。

## 4. 棱镜评审结果

本轮使用 Claude Code 与 Kimi 两路棱镜评审，结论均为 pass，且无 blocker。

Claude Code 抓到一个有价值的非阻塞风险：早版 plan 里的 `target_parent` 有些是人类描述，不是严格目标父级 id；checker 也没有交叉验证。这个风险已在本轮直接修复：现在 inventory 的 `target_parent` 必须匹配 `target_parent_model` 的真实 id。

Kimi 重点确认：本轮方案保留了活知识、冷归档、公共模板和原始证据的边界，没有把它们粗暴合并成一个“知识目录”。

## 5. 本轮没有做什么

- 没有移动、删除、改名任何根目录。
- 没有把 `RASG-019`、`RASG-020`、`RASG-021` 冒充为已完成。
- 没有把内部 plan 或 checker 放入 public package surface；package 候选数仍保持 180。
- 没有声明 RedCap 已经 public release ready。

## 6. 验收结果

| 验收项 | 结果 |
| --- | --- |
| root IA checker | 通过 |
| architecture smell governance | 通过，done=18 planned=3 |
| Prism acceptance | 通过，2 个模型族，0 blocker |
| file lookup dictionary | 通过 |
| reference asset lifecycle | 通过 |
| runtime package manifest + npm pack dry-run | 通过，candidate_count=180 |
| public package surface | 通过，candidate_count=180 |

## 7. 经验沉淀

- 问题源：过去的信息架构治理解决了“每类资产如何被索引、检索、归档和排除 package”，但没有充分回答“仓库根目录本身作为产品骨架是否可解释”。
- 解决方案：先用机器可读 target model 描述未来父级结构，再用 checker 防止 inventory、消费者矩阵和后续 apply 门禁漂移。
- 最后效果：根目录治理从“人类觉得乱”变成了“每个 root child 都有角色、去向、风险和消费者约束”的可审计计划。

## 8. 完成边界

`RASG-017` 可以关闭的含义是：规划、模型、门禁和评审完成。

它不代表物理目录整理已完成。真实迁移必须另开任务，并且那时才可以决定是否把 `compass`、`prism`、`redcap-knowledge`、`shared-knowledge` 等目录移动到新的父级模型下。
