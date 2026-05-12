# 任务完成报告：RASG-021 棱镜降级频率与结论韧性跟踪

**报告日期**：2026-05-12  
**执行者**：Cap（Codex；棱镜复核计划使用 Claude Code + Kimi）  
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 已能在状态面和门禁中看见最近 Prism 是否正在退化，而不是只看到“通过/未通过”。
- 详情：本轮把 formal Prism 最近 10 份报告作为轻量数据源，统计完整/常规评审、resource-limited 评审和阻塞评审的比例。当前结果是健康态：最近 10 份中 1 份为 resource-limited，比例 10%，低于 25% warning 阈值。这样以后如果外部 Agent 频繁超时、限额或不可用，RedCap 会在状态面给出 warning/action，而不是悄悄把资源受限评审当作完整多视角评审。

### 0.2 上一步完成的是

- 上一步完成的是：RASG-023 已把“计划完成但后续未登记”的缺口补成机器门，避免设计/路线型任务收口后丢掉未完成项。

### 0.3 下一步计划做的是

- 下一步计划做的是：生成 closeout receipt；随后进入 RASG-022 的根目录信息架构真实物理合并。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：RASG-023 计划型完成后续登记门 → RASG-021 棱镜降级频率治理 → RASG-022 根目录信息架构物理合并 → 正式发布 readiness。
- 当前所在位置：RASG-021 已完成实现、自检、Prism 独立验收、提交和 clean workspace E2E，等待 closeout receipt。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：当前没有触及发布、license、凭据、破坏性删除或不可恢复历史改写；下一步可由 Cap 和棱镜继续完成验证与收口。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> “好的，赞同，你们继续按照自己评估的优先级来稳步推进吧”

### 1.2 触发背景

RASG-018 曾指出，最近几次棱镜评审里出现过 `resource-limited-pass`：这代表至少有一个原本应该参与评审的 Agent 因限额、超时、登录态或输出不可用而未形成完整证据。如果这种情况只留在单份报告里，长期看会让 RedCap 误以为自己仍在稳定使用多 Agent 评审，实则逐渐退回单视角决策。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 继续按既定优先级治理发布前历史债务。 |
| 已覆盖 | RASG-021 的降级频率政策、统计脚本、状态面、diagnose/spec-check 接线、字典和执行保障登记。 |
| 未覆盖/延期 | RASG-022 物理目录合并、正式 npm 发布。 |
| 用户可见边界 | 本轮完成后不能宣称 RedCap 已进入正式发布，也不能宣称根目录结构已物理合并。 |
| 后续路径 | RASG-021 收口后进入 RASG-022。 |

---

## 二、方案讨论

### 2.1 问题分析

本轮问题不是“某一次 Prism 是否通过”，而是“RedCap 是否能看见 Prism 质量正在下降”。如果只在单个报告里写 resource-limited，后续会话很容易漏读；如果每次都全量读取 `prism/runs/**`，又会制造新的 token 和时间黑洞。因此方案必须以报告索引为默认数据源，只在确需审计原始证据时才按 run 精读。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 状态面统计 | 读取 `prism/reports/index.yaml`，按最近窗口统计 resource-limited 比例 | 轻量、稳定、符合渐进披露 | 只能反映报告索引质量，不能替代 raw run 审计 |
| Q1 | 原始 run 全扫 | 每次扫描 `prism/runs/**` 计算真实细节 | 最细 | 会重新制造 token/时间黑洞 |
| Q1 | 只靠人工报告 | 在每份任务报告里写明是否 resource-limited | 成本最低 | 容易被长任务和新会话遗漏 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 状态面统计 + 阈值行动 | 既能把 Prism 退化显性化，又不扩大默认读取范围；raw evidence 仍保留为按需审计证据。 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `references/prism-degradation-policy.json` | 新建 | 定义最近窗口、最低样本数、warning/action 阈值、可见行动和当前任务验收分类。 |
| `compass/tools/redcap-prism-degradation-check.py` | 新建 | 只读 Prism 报告索引，统计完整/资源受限/阻塞频率，并分类当前任务验收状态。 |
| `compass/tools/redcap-prism-degradation-check.sh` | 新建 | Prism 降级频率检查入口。 |
| `compass/tools/redcap-current-status.py` | 修改 | 在“棱镜 / 独立评审”段展示最近降级率、当前任务 Prism 验收类别和行动提示。 |
| `compass/tools/redcap-diagnose.sh` | 修改 | 接入降级频率检查。 |
| `compass/tools/redcap-spec-check.sh` | 修改 | 接入降级频率检查，并在 action-required 阈值触发时 fail-closed。 |
| `references/execution-guarantees.json` | 修改 | 把 Prism 降级频率纳入执行保障。 |
| `references/file-lookup-dictionary.md` / `references/file-lookup-dictionary-policy.json` | 修改 | 为新政策和新检查器补上人类/机器查阅入口。 |
| `references/reference-asset-lifecycle.json` | 修改 | 刷新大型 reference 生命周期登记。 |
| `references/redcap-knowledge-cold-archive-inventory.json` | 修改 | 因旧报告移入私有知识区，同步刷新冷归档清单。 |
| `references/pre-release-product-architecture-review.json` | 修改 | 同步 package candidate count，避免 release-readiness 事实延迟。 |
| `prism/reports/2026-05-12-rasg-021-prism-degradation-frequency.md` / `prism/reports/index.yaml` | 新建 / 修改 | 记录 Claude Code + Kimi 独立复核结论。 |
| `redcap-knowledge/task-reports/2026-05-09-pre-release-final-convergence-audit.md` | 移动 | 将一个旧活跃报告移入私有知识区，保持活跃 task-reports 不膨胀。 |

### 3.2 技术实现要点

核心做法是把 Prism 健康从“单份报告里的备注”升级成“每次状态刷新都能看到的趋势指标”。默认只读取 `prism/reports/index.yaml`，最近窗口为 10 份报告，最低样本为 5 份；超过 25% resource-limited 时提示 warning，超过 50% 或出现 blocked/escalate 时触发 action-required。

当前任务验收也被单独分类：如果 `.dev-task.md` 声明了 Prism run，但 run registry 或 acceptance binding 还没生成，状态面会显示 `pending`；如果后续发现 `resource-limited.json`，则显示 `resource-limited`，不会冒充 `full-quorum`。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| Prism 降级率 | `redcap-prism-degradation-check` | 最近正式棱镜评审里，有多少次不是完整多 Agent 证据，而是资源受限后勉强通过。 |
| resource-limited | Prism report verdict / artifact | 有 Agent 因超时、限额、登录态等原因没形成完整证据，但剩余证据仍允许继续。 |
| full-quorum | 当前任务 Prism acceptance 分类 | 本任务已有完整多视角验收绑定。 |
| action-required | `references/prism-degradation-policy.json` | 降级比例或阻塞情况已经不能当作正常，需要打开治理动作。 |

### 3.3 关联变更

本轮没有启动 RASG-022 物理目录迁移，也没有改动正式发布开关。由于新增 reference 和脚本会影响包候选数量，后续验证会同步刷新 release-readiness 事实，避免包面检查出现延迟现实。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 无必须人工审核项 | 当前任务没有触及 Norven 保留决策；如果后续 resource-limited 频率升高，再决定是否暂停重任务或调整 provider 策略。 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| Prism 降级频率 | `bash compass/tools/redcap-prism-degradation-check.sh --task-file .dev-task.md --fail-on-action-required` | ✅ healthy，resource-limited=10.0%，action=继续正常 Prism 验收并保持展示 |
| 文件查阅字典 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | ✅ |
| 执行保障 | `bash compass/tools/redcap-execution-guarantee-check.sh` | ✅ |
| current-status | `bash compass/tools/redcap-current-status.sh .dev-task.md` | ✅ 已显示降级率和当前任务 pending 验收 |
| docs retention | `bash compass/tools/redcap-docs-catalog.sh retention-check` | ✅ |
| tracking health | `bash compass/tools/redcap-tracking-health.sh .dev-task.md` | ✅ |
| 人类可读报告质量 | `bash compass/tools/redcap-human-output-quality-check.sh --task-file .dev-task.md` | ✅ |
| runtime package manifest | `bash compass/tools/redcap-runtime-package-manifest.sh --check` | ✅ candidate_count=187 |
| pre-release product architecture | `bash compass/tools/redcap-pre-release-product-architecture-check.sh` | ✅ release blockers 仍为 Norven 保留决策 |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | ✅ full-quorum，responded=2，family_count=2 |
| clean workspace E2E | `bash compass/tools/redcap-clean-workspace-e2e.sh --write-result` | ✅ 以最终提交后的 clean workspace E2E 机器凭证为准；candidate_count=187，npm_pack_dry_run=true |
| spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | ✅ |
| diagnose | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | ✅ |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [x] 无必须人工验证项。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 待最终同步 |
| 棱镜验收 | 通过，Claude Code + Kimi，无 blocker |
| closeout summary | 待生成 |
| closeout receipt | 待生成 |
| rescue audit（如有） | 无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，Prism acceptance 已通过 |
| 已正式完成 | 否，receipt 尚未生成 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| RASG-022 根目录信息架构真实物理合并 | 本轮只做 Prism 韧性前置治理；物理迁移风险更高，必须独立执行。 | P1-before-public-release |
| 正式 npm 发布 | 仍属于 Norven 保留发布决策与后续 release readiness。 | P0 release task |

### 6.2 触发的新问题

无新增独立问题；本轮暴露出的 package candidate count 延迟现实将作为本任务验证收口的一部分同步修正。

### 6.3 推荐的下一步行动

1. 提交 clean workspace E2E receipt 刷新。
2. 生成 closeout receipt 后进入 RASG-022。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| 无 | 无新增 Lesson | 本轮是既定治理门落地，未形成新的跨任务经验。 |

### 7.2 流程改进建议

Prism 质量不应只靠“某份报告写了 resource-limited”来维持记忆，应该进入状态面和机器门；本轮已完成这项机制化。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选 | RASG-021 | no-promote | 本轮没有形成可公开复用的新方法论条目 |

---

## 八、附录

### 附录 A：Commits

```
edac1d5 feat(prism): 固化棱镜降级频率状态面
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|----------|
| acceptance-review | RASG-021 棱镜降级频率治理是否可接受 | pass-after-report-refresh，无 blocker | `prism/reports/2026-05-12-rasg-021-prism-degradation-frequency.md` |
