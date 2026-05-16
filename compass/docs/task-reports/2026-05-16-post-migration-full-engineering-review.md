# 任务完成报告：迁移后 RedCap 全工程深度 Review

**报告日期**：2026-05-16  
**执行者**：Cap（Codex.app + Claude Code / Kimi Prism review）  
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：迁移后的 RedCap 工程状态已完成一轮独立全工程 review，结论是“当前没有新的 P0/P1 工程阻塞”。
- 详情：本轮重点检查了根目录结构、私有与公共资产边界、包面安全、历史考古链、token 风险、Prism 证据生命周期、任务状态一致性和发布前边界。Claude Code 与 Kimi 都参与了独立审查，二者一致认为 RASG-022 私有归档迁移后的工程结构可以继续推进。Kimi 审查中暴露了一个过程问题：它曾读取 `.env`，没有泄漏密钥值，但这违反了 secret-file 禁读边界；我已把这条约束补入 Prism 协议。后续全量回归又抓出任务卡字段不规范、active report inbox 超上限两类收口问题，均已按机器门禁修正。

### 0.2 上一步完成的是

- 上一步完成的是：RASG-022 第一批高风险根目录迁移已收口，`redcap-knowledge/` 私有冷归档已迁入 `private-archive/redcap-knowledge/`，并保留旧锚点解析、包面排除和 clean workspace E2E 证明。

### 0.3 下一步计划做的是

- 下一步计划做的是：如果本报告和收尾 receipt 通过，RedCap 可以继续进入下一条非发布治理任务，或者在 Norven 明确启动后进入 release readiness；当前 review 本身不进入 npm 发布。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：结构迁移第一批完成 -> 迁移后全工程 review -> 根据 review 结论继续后续治理或发布准备。
- 当前所在位置：`redcap-post-migration-full-engineering-review`，迁移后独立 review tranche。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮 review 没有发现需要 Norven 立即决策的工程阻塞。Norven 仍需在未来正式发布任务中决策 license、发布开关、registry 凭据和是否执行真实 publish。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> “好的，我赞同你们的结论和建议。请继续按照你们的建议和计划，稳步推进”

### 1.2 触发背景

RASG-022 private archive tranche 是一次“伤筋动骨”的结构迁移。它自身已经验收通过，但因为触碰了私有归档、包面安全、历史锚点、报告索引和 Prism 证据边界，所以在继续推进下一批结构治理或发布准备前，需要一次独立全工程 review。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-review-with-minimal-process-hardening |
| 原始意图 | 对大规模迁移后的 RedCap 做一轮彻底、严谨、独立的全工程 review，并判断是否可以继续推进 |
| 已覆盖 | 已完成本地只读审计、Claude Code / Kimi 双路 Prism review、Prism acceptance binding、过程问题记录和最小 Prism 协议加固 |
| 未覆盖/延期 | 未执行 npm 发布、未移动剩余高风险根目录、未清理 `prism/runs` 过期本地证据 |
| 用户可见边界 | 本轮只能声明“迁移后工程状态 review-clean”，不能声明“所有后续治理都已完成”或“RedCap 已可公开发布” |
| 后续路径 | 继续后续治理或正式 release readiness；发布仍需 Norven 明确授权 |

---

## 二、方案讨论

### 2.1 问题分析

这次 review 要回答的不是“上一条迁移是否已经做完”，而是“做完之后，工程整体有没有被迁移动作弄出新的暗伤”。因此本轮采用只读优先策略：机器检查先扫显性一致性，Prism 再从独立 reviewer 角度判断是否存在结构性阻塞。

### 2.2 决策结果

| 问题 | 采纳方案 | 决策理由 | 决策方 |
|---|---|---|---|
| 是否现在 review | 现在执行独立 review tranche | 避免继续结构改造前带着未知风险前进 | CAP_DECIDE + NORVEN_APPROVED |
| Prism 模式 | `test` 双路验收 | 当前目标是验收迁移后工程健康，不是开放式多人辩论；Claude/Kimi 两家族满足 test 模式 | CAP_DECIDE |
| Kimi 读取 `.env` 如何处理 | 记录为过程缺陷并补 Prism 协议 | 工程包面未泄漏，但 reviewer 行为越过 secret-file 禁读边界，必须举一反三防复发 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `.dev-task.md` | 修改 | 将当前任务重锚为迁移后全工程 review，并同步完成标准、承诺账本和 Prism run |
| `prism/runs/20260516-post-migration-full-engineering-review/**` | 新建 | 保存本轮 Prism prompt、Claude/Kimi 原始输出、解析结果和 acceptance binding |
| `prism/reports/2026-05-16-post-migration-full-engineering-review.md` | 新建 | 归档本轮 Prism review 结论 |
| `prism/reports/index.yaml` | 修改 | 登记本轮 Prism review |
| `prism/protocol.md` | 修改 | 增加 secret-file 禁读约束，要求 reviewer 只检查忽略规则、安全策略和候选清单 |
| `private-archive/redcap-knowledge/task-reports/2026-05-10-root-information-architecture-debt-intake.md` | 移动 | 将旧债务入口报告从 active inbox 轮转到私有冷归档，避免当前报告入口重新膨胀 |
| `references/redcap-knowledge-cold-archive-inventory.json` | 修改 | 更新私有冷归档清单，保留新归档报告的精确读取入口 |
| `references/backlogs/redcap-architecture-smell-governance.json` | 修改 | 将 RASG-017 的旧债务入口证据路径改为冷归档路径 |
| `compass/docs/task-reports/2026-05-16-post-migration-full-engineering-review.md` | 新建 | 本任务完成报告 |
| `compass/docs/catalog.json` | 修改 | 重新生成文档目录，确保 active report inbox 与冷归档后的索引状态一致 |

### 3.2 技术实现要点

本轮没有继续搬目录，而是先冻结一个独立 review 任务。这样可以避免 review 和 implementation 混在一起，导致“发现问题”被误当成“已经修复问题”。

本地机器检查显示：根目录信息架构、包面安全、alias 考古链、token 风险、clean workspace E2E 和任务中插检查都能跑通。Prism 侧 Claude Code 与 Kimi 都给出“无新 P0/P1 工程阻塞”的结论。

唯一需要立即加固的是 review 过程本身：Kimi 为了验证包面安全打开了 `.env`。这没有造成密钥值输出，但方向不对；正确做法是检查 `.gitignore`、`.npmignore`、安全策略和候选清单，而不是打开被排除的敏感文件正文。因此我把这个禁令补进 Prism 协议。

收口前机器检查还抓到一个真实的治理问题：新增本报告后，`compass/docs/task-reports/` 从 12 份变成 13 份，超过“当前报告入口只保留近期窗口”的上限。这里没有把上限改大，而是把低引用、已完成的旧债务入口报告轮转到私有冷归档，并用 alias resolver 证明旧路径仍能解析到新位置。这样既保留考古能力，也避免 active docs 再次膨胀。

全量 acceptance 还暴露了任务卡字段层面的两个问题：第一，review 任务不能用空 backlog 三元组，否则状态面会退化成“未绑定长期 backlog”；第二，`scope_status` 和 `parent_completion_claim` 不能临时自造枚举。最终任务卡被修正为绑定 `RASG-022`，`scope_status=partial-with-explicit-defer`，`parent_completion_claim=child-only`。这让 current-status、diagnose、change-intake 和 stop-review fallback 对同一任务状态达成一致。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| Prism review | `prism/runs/**` + `prism/reports/**` | 让 Claude/Kimi 这类外部 reviewer 独立审查，避免只靠主 Agent 自证完成 |
| acceptance binding | `prism/runs/.../artifacts/acceptance-binding.json` | 把这次 review 证据绑定到当前任务，防止复用旧证据 |
| private archive | `private-archive/redcap-knowledge/**` | 私有冷归档，不进入公共包，不默认读取 |
| package surface | `package.json` / `.npmignore` / package policy | 将来如果打包成 npm，哪些文件会被纳入、哪些必须排除 |
| secret-file 禁读 | `prism/protocol.md` | reviewer 不得打开 `.env` 等敏感文件，只能检查排除策略和扫描结果 |

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 是否接受本轮 review 结论 | 本轮没有发现新的 P0/P1 工程阻塞，但仍有 release 人工边界和长期治理项 | P1 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| change-intake | `bash compass/tools/redcap-change-intake-check.sh .dev-task.md` | 通过 |
| root IA | `bash compass/tools/redcap-root-information-architecture-check.sh` | 通过 |
| IA governance | `bash compass/tools/redcap-information-architecture-check.sh` | 通过 |
| package safety | `bash compass/tools/redcap-package-publish-safety-check.sh` | 通过 |
| public package surface | `bash compass/tools/redcap-public-package-surface.sh` | 通过 |
| token risk | `bash compass/tools/redcap-token-risk-audit.sh` | 通过 |
| legacy lifecycle | `bash compass/tools/redcap-legacy-asset-lifecycle-check.sh` | 通过 |
| alias resolver | `python3 compass/tools/redcap-legacy-asset-alias-resolver.py --check-result --result references/legacy-asset-migration-alias-resolver.json` | 通过 |
| archived report alias | `python3 compass/tools/redcap-legacy-asset-alias-resolver.py --resolve compass/docs/task-reports/2026-05-10-root-information-architecture-debt-intake.md` | 通过 |
| cold archive inventory | `bash compass/tools/redcap-cold-archive-inventory.sh check` | 通过 |
| root IA deferral | `bash compass/tools/redcap-root-ia-deferral-check.sh` | 通过 |
| progress meter | `bash compass/tools/redcap-progress-meter-check.sh` | 通过 |
| conclusion prism policy | `bash compass/tools/redcap-conclusion-prism-check.sh` | 通过 |
| clean workspace E2E receipt | `bash compass/tools/redcap-clean-workspace-e2e.sh --check-result` | 通过 |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过 |
| stop-review fallback targeted | `bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-falls-back-after-timeout` | 通过 |
| current-status targeted | `bash compass/tools/redcap-multi-session-acceptance.sh current-status-overview` | 通过 |
| diagnose targeted | `bash compass/tools/redcap-multi-session-acceptance.sh diagnose-overview` | 通过 |
| full acceptance suite | `bash compass/tools/redcap-multi-session-acceptance.sh all` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 未来正式发布时，Norven 仍需决策 license、发布开关和 registry 凭据。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 待 closeout 前最终同步 |
| 棱镜验收 | pass |
| closeout summary | 待生成 |
| closeout receipt | 待生成 |
| rescue audit（如有） | 无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是，review 任务与过程加固已落地 |
| 已自检 | 是 |
| 已独立验收 | 是，Claude Code + Kimi |
| 已正式完成 | 待 closeout receipt |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 剩余 4 个高风险根目录物理迁移 | 已由 RASG-022 deferral receipt 管理，不能在 review 任务中顺手移动 | P1/P2 |
| `prism/runs` 过期本地证据清理 | 需要显式 dry-run 和用户授权 `--apply`，本轮只做 review | P2 |
| 正式 npm 发布 | 需要 Norven 对 license、发布开关、凭据做人工决策 | P0-release-only |

### 6.2 触发的新问题

- Prism reviewer prompt 以前没有足够直白地禁止打开 `.env` 等敏感文件。已补入 `prism/protocol.md`。
- 新任务报告触发 active report inbox 超上限；已通过生命周期归档一份低引用旧报告修复，而不是放宽阈值。
- 当前任务卡最初使用了 `review-only` 等未受控枚举；全量回归已迫使任务卡回到 RedCap 机器词表。

### 6.3 推荐的下一步行动

1. 先完成本 review 的 closeout receipt。
2. 若继续非发布治理，按 deferral receipt 选择下一批 root group 或 Prism evidence 生命周期治理。
3. 若进入 release readiness，先明确 license、发布开关和 registry 凭据。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-candidate | Prism reviewer 不得打开 secret 文件 | 审查包面安全时，检查排除策略、候选清单和扫描器输出，不读取 `.env` 等敏感文件正文 |

### 7.2 流程改进建议

本轮已经把 secret-file 禁读写入 Prism 协议。后续如果再发现 reviewer 仍打开敏感文件，应升级为机器化 prompt template 或 dispatch gate。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| EVO-2026-05-16-001 | Kimi review process finding | archived-in-report | `prism/reports/2026-05-16-post-migration-full-engineering-review.md` |

---

## 八、附录

### 附录 A：Commits

```
0ac0efb test(e2e): 绑定报告回填后的清洁安装证明
4b77219 docs(report): 回填私有归档迁移收口凭证
25c5692 test(e2e): 刷新清洁安装证明
bee8161 refactor(ia): 迁移私有冷归档根目录
```

### 附录 B：棱镜调用记录

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|----------|
| test / Claude Code reviewer | 迁移后全工程 review | pass，无新 P0/P1 工程阻塞 | `prism/runs/20260516-post-migration-full-engineering-review/collect/reviewer/parsed.json` |
| test / Kimi challenger | 迁移后全工程 review | pass，无新 P0/P1 工程阻塞；另发现 secret-file 审查过程问题 | `prism/runs/20260516-post-migration-full-engineering-review/collect/challenger/parsed.json` |
