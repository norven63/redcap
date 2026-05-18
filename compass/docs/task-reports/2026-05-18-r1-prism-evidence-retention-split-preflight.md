# 任务完成报告：R1 Prism 证据保留拆分预检

**报告日期**：2026-05-18
**执行者**：Cap（Codex.app 主执行；Prism：Claude Code + Kimi）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：R1 的 `prism-layer-and-evidence` blocker 已被拆成可机器检查的“Prism 证据保留拆分预检”，但它仍然阻塞正式发布。
- 详情：本轮解决的是“Prism 里哪些是可打包工具、哪些是正式评审报告、哪些是本地运行证据”的边界问题。现在 RedCap 已经能证明：`prism/tools` 与 `prism/README.md` 是当前包面候选；`prism/reports` 与 `prism/runs` 不进入包面；未来如果要真实迁移或清理运行证据，必须另开任务并满足独立门禁。

### 0.2 上一步完成的是

- 上一步完成的是：P4-2p 已把 `internal-control-plane` 做成控制面契约拆分预检，并保留 R1 仍未关闭的事实。

### 0.3 下一步计划做的是

- 下一步计划做的是：继续推进正式发布前剩余 R1 边界，优先处理真实物理拆分 dry-run 或 `internal-layer-a` 产品边界；正式 registry 发布、许可证和发布开关仍留到未来人工授权任务。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：正式发布准备路线 → R1 延期根目录分类 → 控制面契约拆分预检 → Prism 证据保留拆分预检 → 剩余物理拆分 / Layer A 产品边界 / 最终发布授权。
- 当前所在位置：`framework-upgrade / P4-2q`，处于 `prism-layer-and-evidence` 技术预检完成点。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮只做预检、检查器、账本、报告、Prism 复核和回归，不触碰许可证、发布开关、registry 凭据、真实发布、Prism 证据清理或不可逆删除。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> OK，我赞同你们的建议，那么你们按照自己的计划来吧，我打断和干扰你们

### 1.2 触发背景

P4-2p 完成后，R1 仍剩 `prism-layer-and-evidence` 与 `internal-layer-a` 等发布 blocker。Prism 目录本身又混合了三类性质完全不同的资产：维护者工具、正式评审报告、本地运行证据。若不先把它们分清，后续发布检查可能误把 raw evidence 带入公开包，或者为了“目录干净”误删仍有考古价值的运行证据。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 按既定优先级继续推进 RedCap 父任务线，不需要人工决策时由 Cap 与 Prism 自动完成。 |
| 已覆盖 | 已完成 P4-2q Prism 证据保留拆分预检、检查器、acceptance、账本、报告、Prism 复核和索引修复。 |
| 未覆盖/延期 | 未执行真实发布、未选择许可证、未打开发布开关、未移动或删除 `prism` / `prism/reports` / `prism/runs`、未裁决 Layer A 产品范围。 |
| 用户可见边界 | 只能说“Prism 证据保留拆分预检已完成”；不能说“Prism 已物理拆分”“证据已清理”“R1 已关闭”“RedCap 可正式发布”。 |
| 后续路径 | 后续 tranche 继续处理真实物理拆分、Prism 运行证据清理审批链或 `internal-layer-a` 产品边界。 |

---

## 二、方案讨论

### 2.1 问题分析

Prism 目录不是单一用途目录。`prism/tools` 是维护者工具，`prism/reports` 是 tracked 评审归档，`prism/runs` 是 gitignored 的本地运行证据。发布前必须区分这三层，否则包面、安全审计、证据保留和任务收口会互相污染。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 直接移动或清理 Prism 目录 | 立刻整理 `prism` 结构 | 看起来进展快 | 容易误删运行证据，也可能破坏 report / acceptance 绑定 |
| Q1 | 只保留 R1 blocker，不继续细分 | 等正式发布任务再处理 | 当前改动少 | 未来 release readiness 仍不清楚如何判断安全边界 |
| Q1 | 先做证据保留拆分预检 | 先写清工具、报告、运行证据、消费者和未来 gate | 安全、可复验、不会冒充清理完成 | 不解决真实物理拆分和清理本身 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 先做证据保留拆分预检 | 当前还没有授权删除、移动或发布；先把边界机器化，能为后续真实拆分降低风险。 | CAP_DECIDE + PRISM_REVIEW |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `references/r1-prism-evidence-retention-split-preflight.json` | 新建 | 记录 Prism 工具、报告、运行证据的当前边界、消费者矩阵、未来拆分/清理门禁和禁止声明。 |
| `compass/tools/redcap-r1-prism-evidence-retention-split-check.py` / `.sh` | 新建 | 校验预检不能冒充物理拆分、证据清理、R1 关闭或发布就绪，并动态核对包候选数与 Prism runs 摘要。 |
| `compass/tools/redcap-formal-release-readiness-plan-check.py` | 修改 | 正式发布计划检查新增 P4-2q 预检硬门。 |
| `compass/tools/redcap-spec-check.sh` / `redcap-diagnose.sh` / `redcap-multi-session-acceptance.sh` | 修改 | 把新检查接入总体验证、诊断和回归用例。 |
| `references/formal-release-readiness-plan.json` / `references/formal-release-r1-root-group-disposition-preflight.json` | 修改 | 同步 P4-2q 后的包面事实和 R1 blocker 边界。 |
| `references/backlogs/framework-upgrade.json` / `references/redcap-parent-task-ledger.md` | 修改 | 把 P4-2q 登记为当前 release-readiness 控制面任务。 |
| `references/file-lookup-dictionary.md` | 修改 | 把新预检和检查器加入文件查阅字典，避免后续 Agent 找不到入口。 |
| `prism/reports/2026-05-18-r1-prism-evidence-retention-split-preflight-review.md` / `prism/reports/index.yaml` | 新建 / 修改 | 记录 Claude Code + Kimi 的独立评审结论。 |
| `compass/docs/catalog.json` / `references/reference-asset-lifecycle.json` / `references/redcap-knowledge-cold-archive-inventory.json` / `references/legacy-asset-migration-dry-run.json` | 修改 | 因报告迁移、spec 行数和索引变化刷新计数型 registry。 |
| `private-archive/redcap-knowledge/task-reports/2026-05-11-rasg-019-human-product-surface.md` | 移动 | 将一份旧 RASG 报告迁入私有冷归档，保持活跃 task-reports inbox 不超过 12 份。 |

### 3.2 技术实现要点

本轮把 `prism-layer-and-evidence` 拆成三层：工具层、报告层、运行证据层。检查器会实时读取 package manifest，确认当前只有 Prism 工具与 README 进入包面候选，报告和 runs 都不进入。它还会读取 Prism runs lifecycle，确认运行证据只做保留/审查/清理资格判断，不允许在本轮执行清理。

预检文件中的 claim boundary 全部保持 false：没有物理拆分、没有证据清理、没有 R1 关闭、没有发布授权。Acceptance 里还加入了反例：如果有人把 `is_prism_evidence_physically_cleaned` 改成 true 或把 blocker 改成 resolved，检查必须失败。

Prism 评审采用 Claude Code + Kimi 两路。Kimi 发现 `framework-upgrade` 当前焦点仍停在 P4-2p，以及全局 spec-check 受报告迁移锚点影响曾经呈红色；本轮已把这些 closeout 前必须修正的同步项全部修复。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| R1 | `references/formal-release-readiness-plan.json` | 正式发布前的一组根目录/资产清理边界，不是发布动作本身。 |
| prism-layer-and-evidence | `references/formal-release-r1-root-group-disposition-preflight.json` | Prism 相关工具、报告和本地运行证据混在同一目录下造成的发布前风险。 |
| evidence retention split preflight | `references/r1-prism-evidence-retention-split-preflight.json` | 真正移动或清理 Prism 证据前的施工图和安全证明，不是清理完成。 |
| package candidates | `redcap-runtime-package-manifest.sh` 输出 | 当前可能进入包面的文件清单。 |
| consumer matrix | 预检文件中的 `consumer_matrix` | 列出哪些入口依赖 Prism 工具、报告或运行证据，防止迁移时断链。 |
| future cleanup gate | 预检文件中的 `required_before_evidence_cleanup` | 未来清理 `prism/runs` 前必须满足的审批、证明和回滚条件。 |
| Prism binding | `redcap-prism-acceptance-bind.sh` | 把本次棱镜评审和当前任务卡绑定，防止拿旧评审冒充本轮验收。 |

### 3.3 关联变更

本轮新增了检查器、报告和 Prism 评审归档，因此包候选数从 202 变为 205。相关旧快照包括 product architecture review、docs catalog、cold archive inventory、reference asset lifecycle 和 legacy migration dry-run 都已同步刷新。这里刷新的是“证据索引与计数”，不是发布授权。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 无需本轮人工决策 | 本轮没有发布、许可证、凭据、不可逆删除或产品范围裁决。 | P0 |
| 2 | 后续若进入 Prism 证据清理 | 必须先证明待清理 run 非活跃、未被报告/知识资产引用，并获得 Norven 显式批准。 | P0 |
| 3 | 后续若进入正式发布 | 许可证、`private=false`、`publish_allowed=true`、registry 凭据和发布窗口仍必须由 Norven 决定。 | P0 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| Python 语法 | `python3 -m py_compile compass/tools/redcap-r1-prism-evidence-retention-split-check.py compass/tools/redcap-formal-release-readiness-plan-check.py` | 通过 |
| R1 Prism 预检 | `bash compass/tools/redcap-r1-prism-evidence-retention-split-check.sh` | 通过 |
| 正式发布计划检查 | `bash compass/tools/redcap-formal-release-readiness-plan-check.sh` | 通过 |
| Prism 证据检查 | `bash prism/tools/prism-evidence-check.sh && bash prism/tools/prism-runs-lifecycle.sh check` | 通过 |
| Prism 验收绑定 | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过 |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh r1-prism-evidence-retention-split-check` | 通过 |
| formal release acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh formal-release-readiness-plan-check` | 通过 |
| spec-check 传播回归 | `bash compass/tools/redcap-multi-session-acceptance.sh spec-check-propagates-control-gate-failures` | 通过 |
| 文件查阅字典 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过 |
| 旧资产计数 registry | `bash compass/tools/redcap-legacy-asset-migration-check.sh && bash compass/tools/redcap-legacy-asset-migration-apply-plan.sh` | 通过 |
| 总体验证 | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 无本轮必需人工验证项。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | closeout 前同步 |
| 棱镜验收 | 通过：`20260518-r1-prism-evidence-retention-split-preflight` |
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
| `prism-layer-and-evidence` 真实物理拆分 | 本轮只做预检；真实移动需要文件级消费者矩阵、alias/rollback 和 clean workspace E2E。 | P0-before-release |
| `prism/runs` 物理清理 | 清理需要独立 inventory、引用证明、Norven 显式批准和回滚方案。 | P0-before-release |
| `internal-control-plane` 真实物理拆分 | P4-2p 只是预检，后续仍需真实 physical split tranche。 | P0-before-release |
| `internal-layer-a` 产品范围裁决 | 是否把 Layer A 纳入公开 RedCap 产品范围属于 Norven 保留决策。 | P0-before-release |
| 正式 registry 发布 | 许可证、发布开关、registry 凭据和发布窗口仍未授权。 | P0-release-task |

### 6.2 触发的新问题

| 问题 | 处理 |
|------|------|
| `framework-upgrade` current_focus 陈旧 | 已更新为 P4-2q，并同步人类说明 spec。 |
| 报告迁移导致 Evolution candidate 旧锚点失效 | 已恢复 5 月 4 日报告锚点，并把另一份较早 RASG 报告迁入私有归档。 |
| 包候选数从 202 变 205 | 已刷新 product architecture review、package surface policy、runtime readiness policy、R1 预检快照和 clean checks。 |

### 6.3 推荐的下一步行动

1. 继续做 `prism-layer-and-evidence` 的真实物理拆分 dry-run，或转入 `internal-layer-a` 产品边界裁决前置分析。
2. 保持 Prism runs 清理为独立任务，禁止顺手执行 `--apply`。
3. 继续保持“正式发布动作”独立，不在技术预检任务里隐式开启。

---

## 七、经验沉淀

### 7.1 新增 Lesson

本轮未新增独立 Lesson。已复用既有发布边界、证据保留、Prism 报告归档和计数型 registry 刷新经验。

### 7.2 流程改进建议

后续涉及包面、报告归档或旧资产锚点的预检任务，应把“计数型 registry / cold archive inventory / docs catalog / backlog current focus 是否同步”列入 closeout 前固定检查。否则新增检查器或迁移报告入口这类正常变更，也会让最后的 spec-check 因陈旧快照而失败。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选 | Prism verdict + release blocker 预检 + 索引漂移修复 | no-promote：本轮没有形成新的可复用 skill / lesson 候选；相关经验已由既有发布边界和 registry 刷新规则覆盖 | `prism/reports/2026-05-18-r1-prism-evidence-retention-split-preflight-review.md` |

---

## 八、附录

### 附录 A：Commits

```
待提交
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|----------|
| 正式复核 | P4-2q 是否安全、完整、未冒充完成 | weak-consensus / pass-with-concerns；无 blocker，concerns 已处理。 | `prism/reports/2026-05-18-r1-prism-evidence-retention-split-preflight-review.md` |

### 附录 C：相关文档索引

- 当前任务卡：`.dev-task.md`
- 预检证据：`references/r1-prism-evidence-retention-split-preflight.json`
- 发布计划：`references/formal-release-readiness-plan.json`
- 棱镜报告：`prism/reports/2026-05-18-r1-prism-evidence-retention-split-preflight-review.md`
