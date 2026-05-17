# 任务完成报告：R1 延期根目录处置预检

**报告日期**：2026-05-17
**执行者**：Cap（Codex，Prism 已验收）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 已把正式发布 R1 阶段的 4 类延期根目录做成机器可查的处置预检。
- 结果：`workspace-state` 被证明只是本地状态和草稿，不进入候选包；`internal-control-plane`、`prism-layer-and-evidence`、`internal-layer-a` 仍然阻塞正式发布，不能被“没有泄漏到包里”冒充成“历史资产已清理”。

### 0.2 上一步完成的是

- 上一步完成的是：历史资产物理清理和高价值经验候选化已经升级为正式发布前硬门。
- 仍缺的关键一步：硬门要求“延期根目录必须逐项有处置结论”，但此前没有把 4 类延期根目录逐项落成可检查矩阵。

### 0.3 下一步计划做的是

- 下一步计划做的是：后续真正进入正式发布任务时，先处理仍阻塞的 3 类根目录组，再谈发布授权、许可证、账号和版本。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：发布准备计划 -> 历史资产硬门 -> 高价值经验硬门 -> R1 延期根目录处置预检 -> 后续正式发布任务分 tranche 处理 3 个 blocker。
- 当前所在位置：P4-2o / formal-release-r1-root-group-disposition-preflight。
- 当前边界：本轮是预检和拦截能力，不是发布、不删除、不迁移、不改许可证、不改发布开关。

### 0.5 是否需要 Norven 人工介入

- 人工介入：当前不需要。
- 说明：后续只有遇到不可逆删除、历史证据损失风险、许可证选择、外部分发账号/凭据或正式发布授权时，才需要 Norven 人工介入。

---

## 一、需求背景

### 1.1 原始问题

正式发布前需要证明：历史资产和延期根目录不能继续以“先延期”的口径进入发布任务。尤其不能把“没有进入候选包”误当成“历史资产已经物理清理完成”。

### 1.2 本轮要解决的核心问题

R1 延期根目录分成两类：

| 类别 | 人话解释 | 本轮结论 |
|---|---|---|
| `internal-control-plane` | RedCap 的控制面、规则、检查脚本和任务真相源 | 仍阻塞发布 |
| `prism-layer-and-evidence` | 棱镜协议、工具、报告和运行证据 | 仍阻塞发布 |
| `internal-layer-a` | Layer A 兼容/旧工作流边界 | 仍阻塞发布 |
| `workspace-state` | 当前工作区本地状态、密钥、草稿、临时目录 | 不属于历史资产；必须排除出包 |

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 已覆盖 | 处置矩阵、检查脚本、正式发布计划接入、acceptance 回归、父任务账本、Prism 双路评审 |
| 未覆盖/延期 | 三个 blocker 的真实物理拆分/迁移、公开发布、许可证、账号凭据、不可逆删除 |
| 用户可见边界 | 只能说“R1 延期根目录有了预检结论”，不能说“R1 已关闭”或“RedCap 已可公开发布” |

---

## 二、方案与决策

### 2.1 方案

本轮不搬目录，也不删除资产，而是先做“发布前交通灯”：

- 绿灯：`workspace-state` 不进包，保持本地私有状态。
- 红灯：3 个历史/产品根目录组仍然阻塞发布。
- 禁止灰区：不允许新增“package-visible but acceptable”这种第五种口径。

### 2.2 决策理由

| 决策 | 原因 |
|---|---|
| 先做预检矩阵 | 正式发布任务需要先知道哪些根目录组仍阻塞，不能到发布前才临时判断 |
| 严格沿用 release gate 的 4 种处置 | 避免新增模糊口径，导致未来绕开硬门 |
| workspace-state 只做排除证明 | 它包含本地任务、草稿和密钥类路径，不应该迁移进公共工程资产 |
| 三个根目录组继续阻塞 | 它们是产品/控制面/证据链问题，不能靠候选包排除来证明治理完成 |

---

## 三、落地结果

### 3.1 完成内容

| 完成项 | 人话解释 |
|---|---|
| R1 处置矩阵 | 把 4 类延期根目录逐项写成机器可查结论 |
| R1 检查脚本 | 每次检查都会重新计算候选包文件，防止矩阵里的数字过期 |
| 发布计划接入 | 正式发布路线现在会把这份预检当作 R1 前置输入 |
| 回归用例 | 如果有人新增第五种处置口径，acceptance 会失败 |
| 包排除补强 | `.dev-task.md` 与 `.tmp/` 已补进 `.npmignore`，配合既有 `.env`、`prompt.txt`、`cli_console.md` 排除规则 |
| 父任务状态更新 | P4-2o 已进入父任务账本，并明确 3 个 blocker 仍未解决 |

### 3.2 本轮没有做什么

- 没有执行任何物理迁移。
- 没有删除历史资产。
- 没有改许可证。
- 没有改发布开关。
- 没有授权外部分发。
- 没有宣称 RedCap 已正式发布就绪。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|---|---|---|
| R1 disposition matrix | `references/formal-release-r1-root-group-disposition-preflight.json` | 4 类延期根目录的发布前交通灯：哪些还挡住发布，哪些只是本地状态 |
| release gate disposition | `references/historical-asset-physical-cleanup-release-gate.json` | 发布前允许使用的固定处置类型；本轮禁止新增第五种灰色分类 |
| workspace-state | `.dev-task.md`、`.env`、`.tmp/`、`prompt.txt`、`cli_console.md` | 当前机器上的任务状态、密钥或草稿；目标是别进包，不是迁到公共源码里 |
| package candidate | `redcap-runtime-package-manifest.sh` 生成的候选清单 | 将来可能进入安装包的文件集合；它能证明“不泄漏”，不能证明“历史治理完成” |
| release blocker | R1 矩阵里的红灯项 | 不代表当前开发失败，只代表正式发布前必须另开 tranche 解决 |

---

## 四、验证与评审

### 4.1 Prism 独立评审

| Agent | 结论 | 要点 |
|---|---|---|
| Claude Code | pass | 确认矩阵只使用 4 种 gate disposition，3 个历史组仍阻塞，workspace-state 有出包排除证明 |
| Kimi | pass | 确认 release-readiness plan 把预检当作 blocker-aware input，acceptance 能拒绝第五种处置 |

### 4.2 自动化验证

| 验证项 | 命令 | 结果 |
|---|---|---|
| R1 处置预检 | `bash compass/tools/redcap-formal-release-r1-root-group-disposition-check.sh` | 通过，remaining_blockers=3 |
| 正式发布计划检查 | `bash compass/tools/redcap-formal-release-readiness-plan-check.sh` | 通过，已登记 R1 preflight |
| 处置预检 acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh formal-release-r1-root-group-disposition-check` | 待最终回归填入 |
| 发布计划 acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh formal-release-readiness-plan-check` | 待最终回归填入 |
| spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 待最终回归填入 |
| diagnose | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 待最终回归填入 |

---

## 五、遗留问题与下一步

| 遗留项 | 为什么没在本轮做 | 后续触发 |
|---|---|---|
| `internal-control-plane` 物理拆分/迁移 | 涉及控制面工具、规则、索引和任务真相源，必须单独 tranche | 正式发布 R1 或稳定版发布前 |
| `prism-layer-and-evidence` 证据链分层 | 涉及棱镜协议、工具、报告和本地证据保留策略 | 正式发布 R1 或 Prism 证据生命周期重构时 |
| `internal-layer-a` 产品边界 | 需要决定 Layer A 兼容是否属于公开 RedCap 产品面 | 发布声明包含或排除 Layer A 前 |

### 5.4 完成等级（禁止混报）

| 等级 | 当前结果 |
|---|---|
| 已实现 | 是，R1 处置矩阵、检查脚本、发布计划接线和父任务状态已落地 |
| 已自检 | 是，新增 checker、targeted acceptance、package surface、字典、知识索引、信息架构和 backlog 检查已通过；spec/diagnose 仍需最终 closeout 后复跑 |
| 已独立验收 | 是，Claude Code 与 Kimi 均给出 pass；Gemini observer 因本地可用性探测失败记为 absent |
| 已正式完成 | 否，等待 closeout runtime 生成当前 confirmed_hash 的正式 receipt |

---

## 六、经验沉淀

| 问题源 | 解决方案 | 最后效果 |
|---|---|---|
| “不进包”容易被误解成“资产已清理” | 把 workspace-state 与历史/产品根目录组分开：前者做排除证明，后者继续阻塞发布 | 未来发布任务不能再用 package exclusion 代替物理治理 |
| 发布前根目录延期口径容易漂移 | 建立 R1 disposition matrix，并由检查脚本对照 release gate 和 deferral receipt | 4 类根目录的当前处置有唯一机器真相 |
| 容易新增模糊的第五种处置 | acceptance 专门构造非法 disposition 并要求失败 | 阻止“看起来可接受”的灰区绕过 release gate |

经验正文已沉淀到 `compass/knowledge/lessons/l-164.md`，索引入口为 `compass/knowledge/lessons.md` 的 L-164。

---

## 七、关键证据入口

- R1 处置矩阵：`references/formal-release-r1-root-group-disposition-preflight.json`
- R1 检查脚本：`compass/tools/redcap-formal-release-r1-root-group-disposition-check.sh`
- 正式发布计划：`references/formal-release-readiness-plan.json`
- Prism 报告：`prism/reports/2026-05-17-formal-release-r1-root-group-disposition-preflight-review.md`
- Prism 证据：`prism/runs/20260517-formal-release-r1-root-group-disposition-preflight/`

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|---|---|---|---|
| L-164 | 本轮发布前预检发现“出包排除证据容易被误当成历史资产治理完成” | promoted；沉淀为经验，供后续 release / package / historical cleanup 类任务复用 | `compass/knowledge/lessons/l-164.md` |
| no-promote | 3 个剩余 blocker 的真实物理拆分/迁移 | no-promote-with-reason；它们不是经验条目，而是未来 formal release tranche 的工程任务 | `references/formal-release-r1-root-group-disposition-preflight.json` |
| no-promote | Gemini observer unavailable | no-promote-with-reason；这是本轮 Prism availability 事实，不构成新的机制经验 | `prism/runs/20260517-formal-release-r1-root-group-disposition-preflight/collect/observer/unavailable.json` |

## 八、禁止外推

- 不能外推为 R1 历史资产清理完成。
- 不能外推为 RedCap 已经正式发布就绪。
- 不能外推为 3 个 blocker 已解决。
- 不能外推为 Norven 已授权许可证、发布开关、外部分发账号或真实发布。
