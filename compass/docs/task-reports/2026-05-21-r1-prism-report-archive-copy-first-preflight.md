# 任务完成报告：P4-10 Prism 报告归档预检

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P4-10 已把 Prism 报告归档从“后续想做”变成了可机器检查的安全预检。
- 人话解释：现在 RedCap 能证明 `prism/reports` 里的报告、报告索引和 `prism/runs` 的原始运行证据还在原位，并且不会被这一步误删、误搬、误清理。

### 0.2 上一步完成的是

- 上一步完成的是：P4-9 通过 Claude Code 与 Kimi 评审，选定“先做 Prism 报告归档预检”作为下一条安全小切片。

### 0.3 下一步计划做的是

- 下一步计划做的是：完成 P4-10 的最终回归和 closeout receipt；随后进入 P4-11，重新评审剩余发布前 blocker 并选择下一条安全小切片。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：正式发布准备路线 → R1 延期根目录分类 → 控制面与 Prism 预检 → 控制面 runtime facade → Prism package-visible support → P4-9 下一切片选择 → **P4-10 Prism report archive 预检**。
- 当前所在位置：`framework-upgrade / P4-10`，属于发布前结构安全预检，不是正式发布，也不是报告物理迁移。

### 0.5 是否需要 Norven 人工介入

- 人工介入：暂不需要。
- 说明：本轮没有触碰许可证、registry、凭据、发布开关、`.env`、旧报告删除、raw evidence cleanup 或 Layer A 产品范围裁决。

## 一、需求背景

P4-8 让 Prism 的一部分工具具备 package-visible facade，但 Prism 还有两类非常敏感的资产：已经追踪的正式评审报告，以及 `prism/runs` 下的原始运行证据。

如果后续为了发布准备直接搬迁或清理这些内容，风险会很高：报告路径可能断裂，索引可能对不上，raw evidence 可能被误删。本轮 P4-10 的目标不是“动它们”，而是先建立一个可审计的预检闸门，证明未来如果要迁移，也必须走 copy-first、alias-first、delete-last 的安全路线。

## 二、方案讨论

### 2.1 如何解决

本轮用一个新的预检资产记录边界，再用一个新 checker 反复审计它：

| 目标 | 处理方式 | 结果 |
| --- | --- | --- |
| 报告仍在旧位置 | 检查 `prism/reports/*.md` 仍被 git 追踪 | 保留旧锚点 |
| 索引能找到报告 | 检查 `prism/reports/index.yaml` 覆盖现有报告 ID 或路径 | 补强可追踪性 |
| raw runs 不被清理 | 检查 `prism/runs` 仍为本地 evidence，且不进入包面 | 禁止清理和误发布 |
| 发布口径不越界 | 检查不能宣称 blocker closed 或 public-release-ready | 防止误报完成 |

### 2.2 边界裁决

本轮只允许声明：Prism 报告归档已有 copy-first / index migration 预检。

本轮不能声明：

- Prism 报告已经物理迁移。
- 旧 `prism/reports` 锚点已经退休。
- `prism/runs` raw evidence 已清理、移动或删除。
- `prism-layer-and-evidence` blocker 已关闭。
- RedCap 已 public-release-ready。

## 三、落地结果

### 3.1 当前效果

RedCap 现在有一个明确的发布前护栏：任何未来想迁移 Prism 报告归档或处理 raw run evidence 的任务，都必须先面对这套预检边界。它降低了“为了整理目录而破坏考古证据”的风险。

### 3.2 已验证

- 新预检资产已记录报告归档、索引、raw runs、禁止操作和未来 apply 前置条件。
- 新 checker 已接入 `spec-check`、`diagnose` 和 acceptance。
- acceptance 负例已覆盖：缺 source truth、过期 source hash、误称清理 raw evidence、误称 blocker 已关闭。
- package surface 已同步到 280 个候选，并保持 `prism/reports` 与 `prism/runs` 不进入候选包面。
- `prism/reports/index.yaml` 已补上若干历史报告路径锚点，避免旧 ID 与文件名不完全一致时被误判为不可追踪。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 / 文件 | 人话解释 | 本轮作用 |
| --- | --- | --- |
| report archive | 报告归档 | 已追踪的 Prism 评审报告，不等于 raw run evidence。 |
| raw run evidence | 原始运行证据 | `prism/runs` 里的本地运行材料，不能顺手清理。 |
| copy-first / alias-first | 先复制、先保留旧入口 | 未来迁移时先保证新旧路径都能访问，再谈删除旧路径。 |
| release blocker | 发布阻塞项 | 本轮只是预检，不关闭整个 Prism 阻塞项。 |
| `references/r1-prism-report-archive-copy-first-preflight.json` | 本轮预检的机器说明书 | 记录哪些事允许做、哪些事绝对不能做。 |
| `prism/reports/index.yaml` | Prism 正式报告索引 | 让历史评审报告能被检索和考古。 |
| `compass/tools/redcap-r1-prism-report-archive-copy-first-preflight-check.sh` | 本轮安全检查入口 | 反复确认报告、索引、运行证据和发布口径没有越界。 |

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
| --- | --- | --- | --- |
| 1 | 暂无人工决策 | 本轮没有 destructive cleanup、证据丢失、发布开关或产品范围裁决。 | P1 |

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 当前结果 |
| --- | --- | --- |
| P4-10 checker | `bash compass/tools/redcap-r1-prism-report-archive-copy-first-preflight-check.sh` | 通过 |
| P4-10 acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh r1-prism-report-archive-copy-first-preflight-check` | 通过 |
| file lookup dictionary | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过 |
| package surface chain | `bash compass/tools/redcap-public-package-surface.sh` 等相关链路 | 通过 |
| full spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 待最终复跑 |
| diagnose | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 待最终复跑 |
| clean workspace E2E | `bash compass/tools/redcap-clean-workspace-e2e.sh --write-result --timeout 180` | 待最终复跑 |

### 5.2 棱镜评审

| Agent | 当前状态 | 说明 |
| --- | --- | --- |
| Claude Code | 通过（带收口 followup） | 核心实现可接受；原始评审指出的报告、索引、binding、backlog 等收口缺口已纳入本轮收口。 |
| Kimi | 通过（带收口 followup） | 挑战式评审确认预检资产和 checker 设计正确；提醒不能把预检冒充成物理迁移或 release-ready。 |
| Gemini | 未调用 | 当前 Prism 可用性中 Gemini 不稳定；Claude Code 与 Kimi 已形成两模型族 quorum。 |
| Copilot | 未调用 | 受 protected fallback 策略保护；Claude Code 与 Kimi 可用时不调用。 |

### 5.3 closeout runtime / receipt

| 项目 | 当前结果 |
| --- | --- |
| 执行承诺账本 | 待最终 closeout 同步 |
| 棱镜验收 | 通过；run=`20260521-r1-prism-report-archive-copy-first-preflight` |
| closeout receipt | 待生成 |

### 5.4 完成等级（禁止混报）

| 层级 | 结论 | 说明 |
| --- | --- | --- |
| 已实现 | 是 | 预检资产、checker、索引补强、包面计数和门禁接入已落地。 |
| 已自检 | 进行中 | 关键局部自检通过，full spec-check / diagnose / clean E2E 正在最终复跑。 |
| 已独立验收 | 是 | Claude Code 与 Kimi 已完成评审，Prism acceptance 已绑定当前任务。 |
| 已正式完成 | 否 | 还没有 closeout receipt。 |

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
| --- | --- | --- |
| Prism report archive 真实迁移 | 本轮只做预检，未执行物理 copy / alias / delete-last。 | P0-before-release |
| Prism raw run evidence cleanup | 涉及本地原始证据，若有删除风险必须单独任务和按需人工批准。 | manual-boundary-if-destructive |
| control-plane batch-2 | 仍是较大控制面拆分任务，不归入本轮。 | P0-before-release |
| Layer A 产品边界 | 仍是 Norven 保留产品决策。 | manual-boundary |

### 6.2 触发的新问题

- `prism/reports/index.yaml` 里部分历史条目的 ID 与实际文件名不完全一致。本轮没有重写历史 ID，而是在 `files_affected` 中补上实际报告路径，让索引覆盖关系更稳。
- 创建当前 Prism run 后，`prism/runs` 数量自然从 106 增至 107；acceptance 已避免再把运行目录数量写死为固定值。

### 6.3 推荐的下一步行动

1. 等待并处理 Claude Code / Kimi 棱镜评审意见。
2. 复跑 full spec-check、diagnose、clean workspace E2E。
3. 生成 closeout receipt。
4. 完成后再由棱镜选择下一条发布前 blocker 小切片。

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 处理结果 | 标题 | 核心内容 |
| --- | --- | --- |
| no-promote | 报告索引覆盖不能只看 ID 字符串 | 本轮已把这个经验落实到 checker：同时看 ID、实际路径和旧锚点可解析性；暂不新增 Evolution candidate，避免把一次具体预检重复沉淀成独立机制项。 |

### 7.2 流程改进建议

涉及历史证据迁移时，验收不应该只看“目录存在”或“数量差不多”，而要证明：旧路径还在、索引能追踪、包面不泄漏、raw evidence 没被清理、发布口径没有越界。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
| --- | --- | --- | --- |
| 报告索引覆盖不能只看 ID | 本轮 P4-10 | no-promote；已直接落实到 P4-10 checker，不新增独立候选 | 本报告与 P4-10 checker |

## 八、附录

### 附录 A：相关文档索引

- 当前任务卡：`.dev-task.md`
- 预检资产：`references/r1-prism-report-archive-copy-first-preflight.json`
- 新 checker：`compass/tools/redcap-r1-prism-report-archive-copy-first-preflight-check.sh`
- Prism 评审运行目录：`prism/runs/20260521-r1-prism-report-archive-copy-first-preflight/`
- 长期路线权威：`references/backlogs/framework-upgrade.json`

## 九、剩余边界

本轮不可声明：

- Prism report archive 已物理迁移。
- `prism/runs` raw evidence 已清理。
- 旧 `prism/reports` 锚点已退休。
- `prism-layer-and-evidence` blocker 已关闭。
- Layer A 产品边界已裁决。
- RedCap 已 release-ready 或可发布。
