# 任务完成报告：RedCap 发布前结构重构任务树重锚定

**报告日期**：2026-05-04
**执行者**：Cap（Codex + Prism: Kimi, Claude Code）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 已把 public CLI/npm 发布前的结构重构任务树重新锚定。新的顺序是：先做 npm 白名单预检，确认哪些东西会进入包面；再做 runtime/project/user 物理边界拆分；再补 CLI 的 doctor/debug/trace/help 等公共产品面；最后处理 package 身份、license 和 release readiness。
- 详情：本轮没有做真实 npm 发布，也没有大规模移动历史资产。它解决的是“深水区任务树别再漂移”的问题：P4-2f 已从旧的 in-progress 纠正为 completed；P4-2g 成为当前任务树重锚点；历史资产默认保留为私有考古证据，只有被 npm 包面或公共导出链路命中时才进入手术范围。

### 0.2 上一步完成的是

- 上一步完成的是：P4-2f 信息架构与运行时产物治理，已经把任务报告、私有知识、运行时证据、RedCap Forge 和 redcap-arsenal 的边界分清并接入机器门禁。

### 0.3 下一步计划做的是

- 下一步计划做的是：进入 P4-2b，真正处理 runtime/project/user 物理边界与 CLI workspace context。换成人话：RedCap 要从“在 Norven 这台机器的 skill 目录里工作”，继续走向“作为可安装 runtime/CLI，在任意被管理项目里工作”。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P4-2a 发布前审判 → P4-2f 信息架构治理 → P4-2g 任务树重锚定与 npm 白名单预检原则 → P4-2b/c/d 发布前 P0 整改 → release readiness → npm publish。
- 当前所在位置：P4-2g 已完成实现与棱镜验收；父任务 P4-2 仍处于 public release 之前的整改阶段。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 如果我们接下来就要做npm发布前的检测，那么我理解这个“历史资产手术”是不是应该要先被完成的？否则在npm发布前的检测会被这些不符合规范的资产所误导。还是说，为了能够安全执行npm发布检测，就是要保留这些资产（比如为了receipt 锚点和考古价值）来做兜底呢？

> 好的，目前我们应该算是进入到redcap的项目工程结构体系重构的深水区（再上一次的重构，应该是工作流重构那次了吧？我不知道有没有记错）了，所以当前进行的、尚未完成的、新计划要增加的这些任务，你可以和棱镜团队一起仔细深度的评审与讨论，应该如何重组任务树并有条不紊的安全推进与落地

### 1.2 触发背景

用户担心两个方向同时出问题：如果先做历史资产手术，可能误删 receipt、报告、Prism 证据和考古锚点；如果不做历史资产手术，又担心 npm 发布前检测被旧资产污染。这个问题不是单个文件处理问题，而是发布前工程结构重构的顺序问题。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 重新组织 RedCap public CLI/npm 发布前的结构重构任务树，防止旧账本状态、历史资产和发布检测互相误导。 |
| 已覆盖 | P4-2f 状态纠正、P4-2g 当前任务登记、P4-2h 历史资产公共蒸馏延期登记、npm 白名单预检优先原则、历史资产默认保留原则、Prism 双路审查和机器检查器。 |
| 未覆盖/延期 | 未执行真实 runtime/project/user 物理拆分；未实现 CLI doctor/debug/trace/help；未最终确定 public package identity/license；未批量公共导出历史资产；未 npm publish。 |
| 用户可见边界 | 可以声明“发布前结构重构任务树已重新锚定”；不能声明 release-ready、历史资产手术完成或 redcap-arsenal 已有实质公共知识内容。 |

---

## 二、方案讨论

### 2.1 问题分析

本轮核心结论是：历史资产手术不是 npm 发布检测的前置条件，但它是 release-ready 结论的前置治理域之一。正确顺序不是“先删干净再测”，也不是“全留着直接发”，而是先用白名单预检确定真实包面，再决定哪些资产需要手术、哪些资产必须保留为私有证据、哪些可以未来进入 RedCap Forge 公共蒸馏流程。

父任务账本也暴露出一个具体漂移：P4-2f 真实已完成，但账本还说 in-progress。这个错误如果不先修，后续任何基于父账本的任务计划都会继承假状态。

### 2.2 Prism 复审结论

| Agent | 角色 | 结论 | 是否有 blocker |
|---|---|---|---|
| Kimi | architect | 历史资产迁移不阻塞 npm 预检；应先白名单预检映射，再做物理拆分与 CLI 硬化。 | 无 |
| Claude Code | challenger | 先跑 npm 白名单预检再动历史资产手术；父账本陈旧措辞必须先修正。 | 无 |

两路审查的共同结论非常一致：先拍片，再手术；P4-2b/c/d 是 release blocker 主线；P4-2e/h 重要，但不应默认卡死 CLI release engineering。

---

## 三、落地结果

### 3.1 本轮做成了什么

本轮把发布前结构重构变成了一个机器可检查的任务树，而不是口头计划。父任务账本已经从“P4-2f 进行中”改为“P4-2f 已完成，P4-2g 当前进行”，并新增 P4-2h 来承接未来历史资产公共蒸馏，而不是把历史资产治理和 npm 发布混成一团。

### 3.2 新任务树的人话版本

| 顺序 | 节点 | 人话解释 | 是否阻塞发布 |
|---|---|---|---|
| 1 | P4-2g | 先确定发布包里到底会有什么，并修正任务树真相。 | 是 |
| 2 | P4-2b | 把 runtime、项目工作区、用户本地状态真正分开。 | 是 |
| 3 | P4-2c | 给外部用户补齐可理解的诊断、调试、帮助和错误解释。 | 是 |
| 4 | P4-2d | 最终确定包名、license、源码可见性和发布包表面。 | 是 |
| 5 | P4-2e | 说明 redcap-arsenal 目前是 template-only，避免宣传误导。 | 否，P1 |
| 6 | P4-2h | 将历史资产经 RedCap Forge 逐条脱敏、去重、安全审查后，未来再选择性导出公共库。 | 否，P1/deferred |
| 7 | P4-2 | 真正 npm/public release。 | 只在前置都完成后执行 |

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|---|---|---|
| npm 白名单预检 | `redcap-runtime-package-manifest.sh --check --npm-pack-dry-run` | 先看如果打包会带上哪些文件，避免靠猜测删除历史资产。 |
| 历史资产手术 | P4-2h / RedCap Forge export triage | 对旧报告、知识和证据做选择性脱敏、去重、归档或公共导出，不是批量清仓。 |
| release blocker | `references/pre-release-product-architecture-review.json` | 不修就不能宣称 public release-ready 的硬阻塞项。 |
| runtime/project/user 三层边界 | P4-2b | 把 RedCap 工具本体、被管理项目、用户本地状态分开，避免 CLI 离开本机后还依赖开发现场。 |
| redcap-arsenal template-only | P4-2e | 当前公共库只有模板和命名空间，不能宣传成已经有实质公共知识内容。 |

### 3.3 变更文件清单

| 文件 | 变更摘要 |
|---|---|
| `.dev-task.md` | 新建 P4-2g 当前任务卡，锁定原始需求、完成标准和漂移哨兵。 |
| `references/redcap-parent-task-ledger.md` | 修正 P4-2f 状态，新增 P4-2g/P4-2h，并重排推荐执行顺序。 |
| `references/pre-release-structure-refactor-task-tree.json` | 新增机器可读发布前结构重构任务树。 |
| `compass/tools/redcap-pre-release-structure-task-tree-check.py/.sh` | 新增任务树检查器，阻断旧账本状态、错误依赖和 release-ready 混报。 |
| `compass/tools/redcap-diagnose.sh` / `redcap-spec-check.sh` | 将新检查器接入诊断和总体验证。 |
| `references/execution-guarantees.json` | 将发布前结构任务树登记为执行保障。 |
| `references/file-lookup-dictionary.md` / policy | 登记新增任务树和检查器，避免后续考古靠猜。 |
| `prism/runs/20260504-redcap-structure-reorg-planning/**` | 保存 Kimi 与 Claude Code 的独立审查证据。 |

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|---|---|---|---|
| 1 | 当前无必须人工介入项 | 本轮只是任务树重锚定和发布前顺序治理，不涉及真实 npm publish、license 最终选择或大规模删除历史资产。 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|---|---|---|
| 结构任务树检查 | `bash compass/tools/redcap-pre-release-structure-task-tree-check.sh` | 通过 |
| 执行保障登记 | `bash compass/tools/redcap-execution-guarantee-check.sh` | 通过 |
| 文件查找字典 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过 |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过，Kimi + Claude Code |
| 全量多会话回归 | `bash compass/tools/redcap-multi-session-acceptance.sh all` | 通过，`ACCEPTANCE_OK` |
| 发布包白名单预检 | `bash compass/tools/redcap-runtime-package-manifest.sh --check --npm-pack-dry-run` | 通过，candidate_count=204，publish_allowed=false |
| 发布安全扫描 | `bash compass/tools/redcap-package-publish-safety-check.sh` | 通过，files_scanned=204 |
| 发布前产品架构审计 | `bash compass/tools/redcap-pre-release-product-architecture-check.sh` | 通过，结论仍是 not-ready，release_blockers=5 |
| 信息架构 / Forge | `bash compass/tools/redcap-information-architecture-check.sh && bash compass/tools/redcap-forge-check.sh` | 通过 |

### 5.2 人工验证项

- [x] 当前无必须人工验证项。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|---|---|
| 执行承诺账本 | 待 closeout runtime 同步 |
| 棱镜验收 | `20260504-redcap-structure-reorg-planning` pass，Kimi + Claude Code，2 个模型家族，无 blocker |
| closeout summary | 待 closeout runtime 生成 |
| closeout receipt | 待 closeout runtime 生成 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|---|---|
| 已实现 | 是，任务树重锚定、父账本修正、机器检查器和 Prism 证据已实现。 |
| 已自检 | 是，新增门禁、文件字典、执行保障、package/pre-release 相关检查、全量 acceptance、diagnose/spec-check 已通过。 |
| 已独立验收 | 是，Kimi + Claude Code 双路 Prism acceptance 已通过。 |
| 已正式完成 | 否，待 closeout runtime 生成 receipt 后才可改为“是”。 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|---|---|---|
| runtime/project/user 物理拆分 | 这是 P4-2b 的实现任务，不应混入本轮任务树重锚定。 | P0 |
| CLI doctor/debug/trace/help | 这是 P4-2c，需要等边界拆分方向明确后实现。 | P0 |
| public package identity/license/surface | 这是 P4-2d，涉及发布口径和 license 决策。 | P0 |
| 历史资产公共导出 | 这是 P4-2h，需要逐条 RedCap Forge 审查，不应批量搬。 | P1 |

### 6.2 推荐的下一步行动

1. 进入 P4-2b：从 dry-run 走向 runtime/project/user 物理边界 apply 方案。
2. 保持 npm package whitelist 作为“拍片工具”，不要为了检测结果去删除考古证据。
3. 等 P4-2b/c/d 全部通过后，再讨论 release readiness，而不是直接 npm publish。

---

## 七、经验沉淀

### 7.3 Evolution Factory 候选处理

- 本轮新增经验已沉淀为 L-151：发布前结构手术要先拍片，再开刀。
- 本轮不新增 Evolution Factory 候选：no-promote，原因是该经验已经足够具体，直接进入 lessons 热经验区；后续如果 P4-2b/c/d 实施中再次复现“先手术后拍片”的风险，再升级为 RedCap Forge / release-readiness skill 候选。

---

## 八、附录

### 附录 A：关键证据路径

| 证据 | 路径 |
|---|---|
| 任务树策略 | `references/pre-release-structure-refactor-task-tree.json` |
| 任务树检查器 | `compass/tools/redcap-pre-release-structure-task-tree-check.sh` |
| Prism run | `prism/runs/20260504-redcap-structure-reorg-planning/` |
| 任务报告 | `compass/docs/task-reports/2026-05-04-redcap-pre-release-structure-refactor-task-tree-reanchor.md` |

### 附录 B：棱镜调用记录

| Agent | 角色 | 输出 |
|---|---|---|
| Kimi | architect | `prism/runs/20260504-redcap-structure-reorg-planning/collect/architect/parsed.json` |
| Claude Code | challenger | `prism/runs/20260504-redcap-structure-reorg-planning/collect/challenger/parsed.json` |
