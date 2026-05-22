# 任务完成报告：P4-13 Prism 报告归档 apply readiness / rehearsal

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P4-13 已把 Prism 报告归档从“只有迁移规划”推进到“未来执行前可先完整演练并被机器检查”。
- 人话解释：我们现在不只是知道未来要把报告复制到哪里，还能在临时目录里真实演练复制、校验 checksum、生成索引草案、证明旧路径仍可用，并确认这些内容不会进入公开包候选面。
- 关键边界：本轮没有在真实仓库复制、移动、删除、重命名任何 Prism 报告；没有创建正式归档副本；没有清理 `prism/runs` 原始证据；没有关闭 release blocker；没有执行 npm 发布。

### 0.2 上一步完成的是

- 上一步完成的是：P4-12 迁移规划。它列出了当前 Prism 正式报告的未来归档路径、旧锚点兼容要求、回滚条件和验证清单，但只停留在 plan-only。

### 0.3 下一步计划做的是

- 下一步计划做的是：继续选择 `prism-layer-and-evidence` blocker 的下一条安全小切片。合理方向是独立评审“是否进入 live copy-first apply preflight / apply”，但仍不得顺手退休旧锚点或清理 raw evidence。
- 仍然不能做的事：真实发布、旧锚点退休、raw evidence cleanup、声明 RedCap release-ready。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：正式发布准备路线 → 控制面与 Prism 预检 → runtime facade → Prism package-visible support → Prism report archive 预检 → 下一切片选择 → 迁移规划 → **P4-13 apply readiness / rehearsal** → 后续 live apply preflight / apply。
- 当前所在位置：`framework-upgrade / P4-13`，属于发布前 R1 的安全小切片，不是正式发布任务。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮没有触碰许可证、registry、npm 发布、凭据、secret、raw evidence cleanup、旧锚点删除或 Layer A 产品范围裁决。

## 一、需求背景

P4-12 已经证明“未来要如何迁移报告”，但计划本身不能证明执行动作真的安全。如果下一步直接 live copy，很容易出现三类风险：把 rehearsal 误报成真实迁移、无意写入真实归档目录、或者让旧路径/包面/回滚证明没有被同步验证。

P4-13 的作用是补上“执行前演练硬门”：先让未来 live apply 的关键动作在临时目录里跑一遍，并把越界口径写成机器会拒绝的条件。

## 二、方案讨论

### 2.1 如何解决

本轮把 readiness 做成三层保护：

| 层 | 作用 | 结果 |
| --- | --- | --- |
| 临时目录演练 | 真实复制到临时目录，而不是只口头推演 | 54 份当前报告都能按 P4-12 plan 演练复制并校验 checksum。 |
| 越界拒绝 | 明确本轮不能 live apply、不能退休旧锚点、不能清理 raw evidence | 任一越界字段改成 true，checker 会失败。 |
| 包面证明 | 确认报告、raw runs 和未来私有归档路径都不进入 package candidates | 候选数同步到 287，但禁入路径仍保持排除。 |

### 2.2 棱镜评审结论

Claude Code 结论是带关注通过。它指出两个改良点：包面策略需要显式禁入 `private-archive/prism-reports/**`，live archive 检测不应只看 `.md`。本轮已当场加固。

Kimi 结论是带关注通过。它指出 reference asset lifecycle registry 因大 reference 文件联动变化而过期，必须在 closeout 前刷新。本轮已更新并通过检查。

两边没有提出阻塞性 bug，也都确认 P4-13 可以继续 closeout。

## 三、落地结果

### 3.1 当前效果

RedCap 现在不会只靠“未来迁移应该安全”这种软承诺。P4-13 已经能阻止以下错误：

- P4-12 plan hash 过期。
- 少覆盖当前某份 Prism 正式报告。
- 演练时 source hash 不匹配。
- 提前声明 live apply、旧锚点退休、raw evidence cleanup 或 release-ready。
- 本轮偷偷创建 `private-archive/prism-reports` 下任何真实文件。
- 把 `prism/reports`、`prism/runs` 或未来私有归档路径放进公开 npm 包候选面。

### 3.2 已验证

| 验证项 | 当前结果 |
| --- | --- |
| readiness checker | 通过；54 份报告、54 次临时复制演练，blocker 仍开放 |
| targeted acceptance | 通过；覆盖 stale plan、live apply、old-anchor retirement、raw evidence、release-ready、live archive 文件等负例 |
| Prism review | Claude Code + Kimi 已完成；Copilot 未调用；Gemini 本轮不可用 |
| package surface | 通过；候选数 287，禁入路径包含 `private-archive/prism-reports/**` |
| closeout runtime | 待最终 receipt 更新 |

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 人话解释 | 本轮作用 |
| --- | --- | --- |
| readiness / rehearsal | 正式执行前先演练，证明顺序、校验和回滚都可行。 | 防止从“有计划”直接跳到“已迁移”。 |
| temporary directory | 临时目录，用完自动清掉，不属于真实仓库归档。 | 让复制动作可真实运行，但不会污染仓库。 |
| alias compatibility | 旧路径继续能被找到，不能突然断历史链接。 | 保护 `prism/reports` 的考古价值。 |
| package surface | 将来 npm 包里会出现的文件集合。 | 证明报告、raw runs、私有归档都不会被误打包。 |
| release blocker | 发布前仍未解决的阻塞项。 | P4-13 完成后 blocker 仍保持开放。 |

## 四、人工审核要点

| 审核项 | 说明 |
| --- | --- |
| 无需本轮人工审核 | 本轮只做演练、机器门禁和评审，不触碰人工保留决策。 |

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 当前结果 |
| --- | --- | --- |
| readiness checker | `bash compass/tools/redcap-r1-prism-report-archive-apply-readiness-check.sh` | 通过 |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh r1-prism-report-archive-apply-readiness-check` | 通过 |
| package surface | `bash compass/tools/redcap-public-package-surface.sh --json` | 通过；candidate_count=287 |
| reference lifecycle | `bash compass/tools/redcap-reference-asset-lifecycle.sh check` | 通过 |
| full spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| diagnose | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 通过 |
| clean workspace E2E | `bash compass/tools/redcap-clean-workspace-e2e.sh --write-result --timeout 180` | 通过；head=6276487，candidate_count=287 |

### 5.3 closeout runtime / receipt

| 项目 | 当前结果 |
| --- | --- |
| 执行承诺账本 | 11/11 已核对 |
| closeout receipt | 已生成：`/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/redcap-r1-prism-report-archive-apply-readiness-afaf934d000dc9f5e44cebbc43db1c4c5cd60e65fb6a02ee1b84bc6921199a48.json` |

### 5.4 完成等级（禁止混报）

| 层级 | 结论 | 说明 |
| --- | --- | --- |
| 已实现 | 是 | apply readiness 资产、临时目录 rehearsal checker、targeted acceptance 和 Prism 报告已落地。 |
| 已自检 | 是 | readiness checker、targeted acceptance、package surface、reference lifecycle、full spec-check、diagnose、clean workspace E2E 均已通过。 |
| 已独立验收 | 是 | Claude Code 与 Kimi 已完成棱镜评审，无 blocker，concerns 已处理或纳入 closeout 必做项。 |
| 已正式完成 | 是 | closeout runtime 已生成 receipt，且 11/11 执行承诺已核对。 |

## 六、遗留问题与下一步

| 问题 | 当前处理 | 建议优先级 |
| --- | --- | --- |
| 真实 report archive copy-first apply | 本轮只演练，不执行 | P0-before-release |
| 旧锚点退休 | 必须等待 live copy-first apply、alias proof、archive-check 和单独 delete-last receipt | future-after-apply |
| raw evidence cleanup | 仍需保存证明和按需人工批准 | manual-boundary-if-destructive |
| `prism-layer-and-evidence` blocker | 仍然开放 | P0-before-release |

### 6.1 推荐下一步

在 P4-13 收口后，重新让 Prism 选择下一条最小安全切片。若进入 live apply，也必须是单独任务，且只允许 copy-first，不允许 delete-last 或 raw evidence cleanup 混入。

## 七、经验沉淀

### 7.1 新增 Lesson 候选

| 标题 | 问题源 | 解决方案 | 最后效果 |
| --- | --- | --- | --- |
| rehearsal checker 不能只看目标扩展名 | Claude Code 发现 live archive 检测只看 `.md`，可能漏掉 `index.yaml` 等非报告文件 | 改为拒绝 `private-archive/prism-reports` 下任何 live 文件 | 演练任务无法偷偷留下真实归档文件或索引草稿。 |
| 大 reference 快照联动要同步 lifecycle registry | Kimi 发现包候选数更新导致大 reference 文件变更，registry 过期会让 spec-check 提前失败 | 运行 `redcap-reference-asset-lifecycle.sh update` 并纳入 closeout 验证 | 防止 spec-check 因 registry stale 而挡在真实检查之前。 |

### 7.2 是否晋升正式 lesson

暂不晋升为正式 lesson。本轮已经把两个问题直接固化到 checker、policy 和 lifecycle registry 中；若未来再次出现“只检查某类扩展名导致 live residue 漏检”，再晋升为跨任务经验。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
| --- | --- | --- | --- |
| live archive residue 必须按目录而非扩展名拒绝 | Claude Code P4-13 评审 | no-promote；已直接修进 checker | `compass/tools/redcap-r1-prism-report-archive-apply-readiness-check.py` |
| 大 reference 变更必须刷新 lifecycle registry | Kimi P4-13 评审 | no-promote；已通过 lifecycle update 处理 | `references/reference-asset-lifecycle.json` |

## 八、附录

- 当前任务卡：`.dev-task.md`
- readiness 资产：`references/r1-prism-report-archive-apply-readiness.json`
- Prism review 报告：`prism/reports/2026-05-21-r1-prism-report-archive-apply-readiness.md`
- Prism 运行目录：`prism/runs/20260521-r1-prism-report-archive-apply-readiness/`
- 长期路线权威：`references/backlogs/framework-upgrade.json`
