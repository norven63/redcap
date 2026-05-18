# 任务完成报告：正式发布 R1 控制面契约拆分预检

**报告日期**：2026-05-18
**执行者**：Cap（Codex.app 主执行；Prism：Claude Code + Kimi）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：R1 的 `internal-control-plane` blocker 已被拆成可机器检查的“控制面契约拆分预检”，但它仍然阻塞正式发布。
- 详情：本轮解决的是“`compass` 和 `references` 还在包候选面里，后续到底该怎么安全拆”的问题。现在 RedCap 已经有一份可复验的预检：说明哪些入口还依赖它们、当前候选包面是多少、未来真搬目录前必须准备哪些门禁。重要边界也被锁住：这不是物理迁移完成，不是 R1 关闭，也不是 public release ready。

### 0.2 上一步完成的是

- 上一步完成的是：P4-2o 把 R1 延期根目录分成 4 类，其中 `workspace-state` 已证明不进包，`internal-control-plane`、`prism-layer-and-evidence`、`internal-layer-a` 仍是 release blockers。

### 0.3 下一步计划做的是

- 下一步计划做的是：继续处理剩余 R1 release blockers，优先在 `prism-layer-and-evidence` 与后续 `internal-control-plane` 真实物理拆分之间选择下一条可自动推进的 tranche；正式 npm 发布、许可证、发布开关和 registry 发布仍需未来人工授权任务。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：发布准备路线 → R1 延期根目录分类 → 控制面契约拆分预检 → 剩余证据层 / Layer A 产品边界 / 真实发布授权。
- 当前所在位置：`framework-upgrade / P4-2p`，处于正式发布 R1 的第一个 blocker 技术预检完成点。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮只做技术预检、检查器、账本、经验沉淀和 Prism 复核，不触碰许可证、发布开关、registry 凭据、真实发布或不可逆删除。下一步仍可由 Cap 与 Prism 自动推进，直到遇到这些人工保留边界。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 好的，那么请你们继续稳步推进吧，在推进到需要人工校验的步骤之前，所有任务都由你和棱镜负责自动完成

### 1.2 触发背景

P4-2o 关闭后，R1 仍剩三个发布 blocker。为了避免直接进入破坏性目录迁移，本轮先选择候选包面最大的 `internal-control-plane` 做“拍片”：先把依赖、包面、未来移动条件和不能声明的边界写清，再让机器和 Prism 审核它。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 继续推进 RedCap 父任务线，在不需要人工校验前由 Cap 与 Prism 自动完成。 |
| 已覆盖 | 已续接 P4-2o，完成 P4-2p 控制面契约拆分预检、检查器、acceptance、账本、经验和 Prism 复核。 |
| 未覆盖/延期 | 未执行真实发布、未选择许可证、未打开发布开关、未移动或删除 `compass` / `references`、未裁决 Layer A 是否纳入公开产品范围。 |
| 用户可见边界 | 只能说“控制面拆分前置条件已机器化”；不能说“控制面已物理拆分”“R1 已关闭”“RedCap 可正式发布”。 |
| 后续路径 | 后续 tranche 继续处理 `prism-layer-and-evidence`、`internal-layer-a` 或真实 control-plane physical split。 |

---

## 二、方案讨论

### 2.1 问题分析

`compass` 和 `references` 当前同时承担 runtime 支撑、维护者控制面、发布安全策略、状态诊断和考古索引等职责。直接搬目录风险太高：会影响 revive/status/diagnose/closeout、发布安全检查、Prism 验收绑定和文件查阅入口。因此本轮只做 contract split preflight，让后续真实拆分有可审计的施工图。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 直接移动 `compass` / `references` | 立刻把控制面根目录迁到新位置 | 看起来进展快 | 断链风险高，容易破坏收尾、诊断和包面检查 |
| Q1 | 只保留 P4-2o blocker，不继续细化 | 等未来发布任务再处理 | 当前改动少 | 未来 release task 仍会不清楚如何拆 |
| Q1 | 先做 contract split preflight | 先写清消费者矩阵、包面快照、未来 split gate | 安全、可复验、不会冒充完成 | 不解决物理迁移本身 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 先做 contract split preflight | Claude Code 建议先显性化三 blocker 计划，Kimi 建议优先处理候选面最大的控制面 blocker；本轮合并两者：先计划，再预检。 | CAP_DECIDE + PRISM_REVIEW |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `references/r1-control-plane-contract-split-preflight.json` | 新建 | 记录 R1 三 blocker 顺序、控制面包面快照、消费者矩阵、未来物理拆分门禁和禁止声明。 |
| `compass/tools/redcap-r1-control-plane-contract-split-check.py` / `.sh` | 新建 | 校验预检不能冒充物理拆分完成或 release-ready，并实时核对包候选数。 |
| `compass/tools/redcap-formal-release-readiness-plan-check.py` | 修改 | 正式发布计划检查新增 R1 控制面预检硬门。 |
| `compass/tools/redcap-spec-check.sh` / `redcap-diagnose.sh` / `redcap-multi-session-acceptance.sh` | 修改 | 把新检查接入总体验证、诊断和回归用例。 |
| `references/formal-release-readiness-plan.json` / `references/formal-release-r1-root-group-disposition-preflight.json` | 修改 | 同步 P4-2p 后的包面事实和发布前路线边界。 |
| `references/backlogs/framework-upgrade.json` / `references/redcap-parent-task-ledger.md` | 修改 | 把 P4-2p 登记为当前 release-readiness 控制面任务。 |
| `references/file-lookup-dictionary.md` / `references/file-lookup-dictionary-policy.json` | 修改 | 把新预检和检查器加入文件查阅字典，避免后续 Agent 找不到入口。 |
| `compass/knowledge/lessons/l-165.md` / `compass/knowledge/lessons.md` | 新建 / 修改 | 沉淀“控制面拆分预检不能冒充物理拆分完成”的经验。 |
| `prism/reports/2026-05-18-r1-control-plane-contract-split-preflight-review.md` / `prism/reports/index.yaml` | 新建 / 修改 | 记录 Claude Code + Kimi 的独立评审结论。 |
| `references/token-structural-governance.json` | 修改 | 将增长到 50KB 阈值以上的 Prism report index 纳入结构化 token 风险治理，避免索引本身变成新上下文风险。 |
| `private-archive/redcap-knowledge/task-reports/2026-05-15-gd-008-host-limited-boundary-closeout.md` / `prism/reports/index.yaml` | 移动 / 修改 | 将一份旧 GD-008 任务报告迁入私有冷归档，保持活跃 task-reports inbox 不超过 12 份。 |
| `compass/docs/catalog.json` / `references/reference-asset-lifecycle.json` / `references/legacy-asset-migration-*.json` | 修改 | 因新增报告、经验和 spec 行数变化刷新索引与计数型 registry。 |

### 3.2 技术实现要点

本轮把 `internal-control-plane` 从一个笼统 blocker 拆成“现在是什么、谁依赖它、未来怎么搬、搬之前要证明什么”。核心做法是让预检文件保持 analysis-only 状态，并让检查器强制所有关键 claim 都必须是 false：没有物理迁移、没有发布授权、没有 R1 完成。

检查器不是只读 JSON 字段，它会调用真实 package manifest 重新计算候选包面。如果后续有人新增文件导致数字变了、却没有更新预检，检查会失败；如果有人把 release blocker 改成 resolved 但没有物理拆分证据，检查也会失败。

Prism 评审采用 Claude Code + Kimi 两路。两者都认可设计边界；Kimi 额外指出索引/registry 会随文件新增变陈旧，本轮已经刷新这些 registry，并把这个摩擦点保留为后续物理拆分 tranche 要继续注意的风险。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| R1 | `references/formal-release-readiness-plan.json` | 正式发布前的一组根目录/资产清理边界，不是 npm 发布动作本身。 |
| internal-control-plane | `references/formal-release-r1-root-group-disposition-preflight.json` | RedCap 自己的控制面工具和策略层；当前主要落在 `compass` 与 `references`。 |
| contract split preflight | `references/r1-control-plane-contract-split-preflight.json` | 真正搬目录前的施工图和风险证明，不是搬迁完成。 |
| consumer matrix | 预检文件中的 `consumer_matrix` | 列出哪些入口依赖控制面，避免搬目录时把 revive/status/diagnose/closeout 等入口打断。 |
| future split gate | 预检文件中的 `future_split_gate` | 后续真搬目录前必须先通过的门禁清单。 |
| Prism binding | `redcap-prism-acceptance-bind.sh` | 把本次棱镜评审和当前任务卡绑定，防止拿旧评审冒充本轮验收。 |

### 3.3 关联变更

因为本轮新增了 lesson、报告、Prism report 和修改了 backlog spec，若不刷新 docs catalog、reference asset lifecycle、cold archive inventory 和 legacy asset migration 计数，诊断会失败。Kimi 评审也指出了这一点，因此本轮把这些关联 registry 一并刷新。新增 Prism 索引后，`prism/reports/index.yaml` 刚好越过 token 风险阈值；本轮没有放宽阈值，而是把它登记进结构化治理计划。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 无需本轮人工决策 | 本轮没有发布、许可证、凭据、不可逆删除或产品范围裁决。 | P0 |
| 2 | 后续若进入真实物理拆分 | 真正移动 `compass` / `references` 前，需要再次做文件级消费者矩阵、alias/rollback、clean workspace E2E 和 Prism review。 | P1 |
| 3 | 后续若进入正式发布 | 许可证、`private=false`、`publish_allowed=true`、npm registry 和发布窗口仍必须由 Norven 决定。 | P0 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| Python 语法 | `python3 -m py_compile compass/tools/redcap-r1-control-plane-contract-split-check.py compass/tools/redcap-formal-release-readiness-plan-check.py` | 通过 |
| R1 控制面预检 | `bash compass/tools/redcap-r1-control-plane-contract-split-check.sh` | 通过 |
| 正式发布计划检查 | `bash compass/tools/redcap-formal-release-readiness-plan-check.sh` | 通过 |
| R1 根目录处置检查 | `bash compass/tools/redcap-formal-release-r1-root-group-disposition-check.sh` | 通过 |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh r1-control-plane-contract-split-check` | 通过 |
| formal release acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh formal-release-readiness-plan-check` | 通过 |
| 文件查阅字典 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过 |
| backlog 对账 | `bash compass/tools/redcap-backlog-check.sh strict .dev-task.md` | 通过 |
| 包候选与包面 | `bash compass/tools/redcap-runtime-package-manifest.sh --check && bash compass/tools/redcap-public-package-surface.sh` | 通过 |
| 知识索引 | `bash compass/tools/redcap-knowledge-index-check.sh` | 通过 |
| 旧资产计数 registry | `bash compass/tools/redcap-legacy-asset-migration-check.sh && bash compass/tools/redcap-legacy-asset-migration-apply-plan.sh` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 无本轮必需人工验证项。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | closeout 前同步 |
| 棱镜验收 | 通过：`20260518-r1-control-plane-contract-split-preflight` |
| closeout summary | closeout 后生成 |
| closeout receipt | closeout 后生成 |
| rescue audit（如有） | 无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，Claude Code + Kimi Prism 复核通过 |
| 已正式完成 | 否，receipt 将在 closeout runtime 完成后成为唯一正式完工凭证 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| `internal-control-plane` 真实物理拆分 | 本轮只做预检；真实移动需要文件级消费者矩阵、alias/rollback 和独立 tranche。 | P0-before-release |
| `prism-layer-and-evidence` release blocker | 证据层保留/归档/公开边界需要单独任务处理。 | P0-before-release |
| `internal-layer-a` 产品范围裁决 | 是否把 Layer A 纳入公开 RedCap 产品范围属于 Norven 保留决策。 | P0-before-release |
| 正式 npm 发布 | 许可证、发布开关、registry 凭据和发布窗口仍未授权。 | P0-release-task |

### 6.2 触发的新问题

Kimi 指出计数型 registry 会因为文件新增而频繁变陈旧。这不是本轮 blocker，但未来真实物理拆分时，应该优先使用自动生成/实时对账，减少人工维护数字造成的 closeout 摩擦。

### 6.3 推荐的下一步行动

1. 继续处理 `prism-layer-and-evidence` blocker，明确证据层哪些必须保留、哪些可归档、哪些不得进包。
2. 或者另开 `internal-control-plane` physical split tranche，把本轮 preflight 扩展成文件级迁移/alias/rollback 方案。
3. 继续保持“正式发布动作”独立，不在技术预检任务里隐式开启。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-165 | 控制面拆分预检不能冒充物理拆分完成 | 预检可以拍片和制定施工图，但必须保持 release blocker，不能把未来拆分条件冒充成已经拆完。 |

### 7.2 流程改进建议

后续涉及包面或目录结构的任务，应默认把“计数型 registry 是否需要刷新”列入 closeout 前检查项。否则新增报告、lesson、spec 行数这类正常变更，也会让诊断在最后阶段失败。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选；L-165 | release blocker 预检 + Prism review | no-promote：本轮未新增 Evolution candidate，直接沉淀为 Lesson L-165 | `compass/knowledge/lessons/l-165.md` |

---

## 八、附录

### 附录 A：Commits

```
待提交
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|----------|
| 路线选择 | 三个 R1 blockers 下一步先做什么 | Claude Code 倾向先做三 blocker plan；Kimi 倾向先做 internal-control-plane；本轮合并为“先计划，再做控制面预检”。 | `prism/runs/20260518-r1-next-blocker-tranche-selection/` |
| 正式复核 | P4-2p 是否安全、完整、未冒充完成 | weak-consensus / pass-with-concerns；无 blocker，Kimi concerns 已处理。 | `prism/reports/2026-05-18-r1-control-plane-contract-split-preflight-review.md` |
