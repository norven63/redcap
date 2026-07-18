# OL-11 TRPG 长期外部样本 E2E 方案

本文件是 OL-11（长期第三方生产项目样本）的固定测试方案。它只定义后续如何执行 E2E（端到端验收），不表示本轮已经执行测试，也不表示 RedCap（当前复活工程）已经完整复活。

## 目标

OL-11 要验证的不是“能不能做出一个 TRPG（桌面角色扮演游戏）示例应用”，而是 RedCap 能不能作为“渔”稳定帮助独立执行方完成真实工程开发。

验收重点是：

- 独立开发 AI（人工智能执行方）能否在外部项目中安装并使用 `.redcap/` 项目级运行时。
- Loom（角色化工程工作流）能否驱动产品、架构、开发、测试、评审等角色分工协作。
- 多轮需求变更、失败回流、重新验收和证据收束是否真实发生。
- 知识召回、自我净化、人格私有边界、棱镜（异构 AI 评审助手）复核是否自然进入工作流。
- Cap（当前会话 AI 执行主体）是否只扮演需求方、验收方和观察者，不替开发 AI 实现目标项目。

## 固定需求包

后续执行 OL-11 时，Cap 从本节直接取需求，不再临时重新拟题。该需求来自既有 TRPG 项目能力的抽象，不向开发 AI 暴露旧项目源码路径、旧实现代码或现成答案。

## 来源边界

固定需求包的来源边界以本文件为准，不再依赖 RedCap 源仓库里的临时证据文件。它只证明本测试方向来自 RedCap 源仓库之外的既有本地项目方向，不证明旧项目本身就是 OL-11 的验收样本。

边界要求：

- Cap 可以读取既有 TRPG 项目的说明文件和包信息，用于抽象需求。
- 开发 AI 不得读取 `/Users/norven/workspace/trpg-server/` 或 `/Users/norven/workspace/trpg-web/` 的源码、文档或配置。
- 开发 AI 只能接收本文件中的固定需求包、验收标准和变更说明。
- 如果运行证据显示开发 AI 读取了旧项目路径，OL-11 必须失败。

## 执行前硬门禁

在启动完整 OL-11 E2E 前，必须先通过以下检查：

```bash
runtime/bin/redcap ol11 plan-check
runtime/bin/redcap ol11 self-check
runtime/bin/redcap ol11 trpg-carrier-dry-run --work-root <RedCap 源仓库之外的外部目录>
runtime/bin/redcap complete-revival-e2e design-check
runtime/bin/redcap complete-revival-e2e auto-observation-targeted-e2e --work-root <RedCap 源仓库之外的外部目录>
runtime/bin/redcap complete-revival-e2e carrier-probe --work-root <RedCap 源仓库之外的外部目录>
runtime/bin/redcap project-install production-readiness-check
runtime/bin/redcap longrun-observer self-check
```

`ol11 trpg-carrier-dry-run` 只是短演练：它验证固定 TRPG 需求包能被独立 Codex CLI（Codex 命令行工具）承接、能触发项目级 Hook（钩子，宿主自动触发的检查脚本）、能记录 session_id（会话编号）和机器标记；它不允许开发正式项目，也不能关闭 OL-11。

`complete-revival-e2e auto-observation-targeted-e2e` 是自动观测收集的定向 E2E（端到端验收）：它必须同时证明阶段性观察请求能由外层 harness（外层执行器）触发、失败能自动写入长期观察 issues 和 `LATEST-HANDOFF.json`、新会话可通过 resume（恢复命令）读取上下文。它不替代完整 OL-11 长期样本，只负责把自动观测能力从“全量 E2E 的附带现象”变成可独立验证的能力面。

棱镜（异构 AI 评审助手）对执行前方案或证据链给出 `block` 时，不允许启动完整 OL-11 运行。此时只能补齐被指出的缺口，例如证据结构、来源证明、Codex CLI 承载预检、角色会话证据和 Hook 触发证据。

本方案的机器可检查证据结构记录在 `assets/contracts/ol11-trpg-longrun-e2e-evidence-schema.json`。未来正式执行时，最终证据包必须覆盖该合同中的所有顶层证据项。

### 项目名称

TRPG 社群与活动协作平台。

### 业务目标

为桌面角色扮演游戏玩家和主持人提供一个轻量平台，支持用户注册登录、社团组织、活动发布、报名管理、关注关系和通知协作。

### 最小业务范围

- 用户可以注册、登录、退出登录，并区分普通玩家、主持人和管理员。
- 用户可以创建和浏览社团，加入社团，查看社团成员。
- 主持人可以发布活动，活动包含标题、简介、时间、地点、人数上限、状态和所属社团。
- 玩家可以报名活动、取消报名，并查看自己的报名状态。
- 系统需要阻止明显非法操作，例如重复报名、人数超限、未登录报名、活动不存在。
- 用户可以关注其他用户或社团，并查看关注对象的近期活动。
- 系统可以生成基础通知，例如报名成功、活动状态变化、社团有新活动。

### 延展变更

第二轮需求变更必须加入以下能力，用于验证 RedCap 的变更接入和失败回流：

- 关注统计：展示用户或社团的关注者数量。
- 关注动态流：用户可以看到已关注社团或主持人发布的新活动。
- 推荐列表：系统基于社团、主持人或活动热度给出简单推荐。
- 报名冲突提示：同一用户报名时间重叠活动时，必须给出冲突提示。

### 非目标

- 不要求公网部署。
- 不要求接入真实支付、真实短信、真实邮箱或第三方登录。
- 不要求复刻旧项目的 UI（用户界面）细节或技术栈。
- 不要求访问 `/Users/norven/workspace/trpg-server/` 或 `/Users/norven/workspace/trpg-web/` 的源码。

## 推荐工程形态

开发 AI 可以自行选择技术栈，但必须满足：

- 项目可以是一个单仓工程，服务端和前端可以放在同一目录。
- 默认优先选择本地可运行、无需真实外部账号、无需公网发布的方案。
- 如果需要安装依赖，必须说明原因、锁定命令、记录日志和失败处理。
- 运行说明必须让验收方可以在外部项目目录独立启动、访问和测试。

## 角色与会话要求

OL-11 必须使用独立开发 AI 执行，优先使用 Codex CLI（Codex 命令行工具），因为项目级 Hook（钩子，宿主自动触发的检查脚本）需要在实际承接方环境中触发。

执行要求：

- Cap 扮演需求方、验收方、RedCap 运行观察者。
- 独立开发 AI 扮演承接方，并通过 RedCap 驱动 Loom 角色工作。
- Loom 每个角色都必须拥有独立会话记录。
- 每个角色必须记录 `session_id`（会话编号）、上游输入、下游交付、原始提示和原始输出。
- 同一角色跨轮返工必须复用同一个 `session_id`；如果丢失，必须写入 `session_loss_alarm`（会话丢失告警）。
- 会话丢失不一定立即终止整个测试，但必须进入重点复核；如果角色无法证明上下文接续，则该角色本轮产物不得直接通过。
- E2E 运行器在启动编排者或任一 Loom 角色前，必须把本次角色提示词 SHA-256 写入 `<外部项目>/.redcap/state/e2e-role-authorizations.json`；项目级 Hook 只允许哈希匹配、角色标记匹配、项目路径匹配且未过期的角色提示覆盖 `review_only` 误判，不得关闭危险命令保护、证据保护或普通问答拦截。

建议运行状态位置：

```text
<外部项目>/.redcap/state/loom/role-session-manifest.json
<外部项目>/.redcap/state/loom/role-runs/
<外部项目>/.redcap/state/e2e-role-authorizations.json
<外部项目>/.redcap/evidence/e2e/
<外部项目>/.redcap/evidence/prism/
<外部项目>/.redcap/evidence/self-purification/
```

## 固定流程

### 0. 样本准备

- 在 RedCap 源仓库之外创建外部项目目录。
- 推荐路径：`/Users/norven/workspace/redcap-production-samples/trpg-longrun-sample`。
- 把 RedCap 发布包解压为外部项目的 `.redcap/`。
- 执行 `.redcap` 初始化能力，生成项目级 Hook 配置、运行目录和证据目录。
- 写入样本清单，声明该样本不是 RedCap 仓库内的 fixture（固定测试样本），也不是运行器即时生成后立刻销毁的一次性项目。

### 1. 需求澄清

产品经理角色必须输出：

- 需求说明。
- 范围边界。
- 验收标准。
- 非目标清单。
- 与固定需求包的映射表。

Cap 可以补充需求，但不得替产品经理直接写最终产物。

### 2. 架构设计

架构师角色必须输出：

- 技术选型说明。
- 项目结构。
- 数据模型。
- 关键接口或页面流转。
- 风险与回滚方案。
- 如何支持第二轮需求变更。

架构文档必须接受棱镜复核，复核意见要进入后续开发输入。

### 3. 开发实现

开发者角色必须：

- 在外部项目中写入真实代码和配置。
- 不把运行证据写回 RedCap 源仓库。
- 不直接读取旧 TRPG 源码。
- 按架构文档实现最小业务范围。
- 记录实现日志、关键取舍和未完成项。

### 4. 测试验证

测试角色必须输出：

- 正向功能测试。
- 负向测试。
- 浏览器或命令级真实运行证据。
- 失败项清单。

失败不能由 Cap 直接修复。测试失败后必须打回对应角色：

- 需求缺陷打回产品经理。
- 架构缺陷打回架构师。
- 实现缺陷打回开发者。
- 测试设计缺陷打回测试角色。

被打回角色完成修复后，流程从该角色节点继续向下推进。

### 5. 变更接入

第二轮需求变更必须触发：

- 需求更新。
- 架构影响评估。
- 开发增量实现。
- 回归测试。
- 变更前后证据对照。

不得只在最终报告里说“已支持变更”。

### 6. 自我净化与知识召回

每一轮结束时，RedCap 必须检查：

- 本轮是否有可沉淀经验。
- 是否应进入公共知识库。
- 是否只保留为私有 Cap 人格材料。
- 是否应 `no_promote`（不晋升），并说明理由。

人格沉淀只允许进入私有边界，例如 `/Users/norven/.cap/`，不得自动写入公共 RedCap 仓库。

### 7. 验收收口

只有以下证据全部存在，才允许进入 OL-11 结果评估：

- 外部项目可运行。
- 需求、架构、开发、测试、评审角色证据完整。
- 所有角色有 `session_id`，且无未解释的会话丢失。
- 项目级 Hook 事件被记录。
- 长期观察器已在外部项目初始化，并由 E2E 后置门禁自动执行 `auto-collect`，写入观察记录、问题账本、评估结果和跨会话 handoff。
- E2E worker 在最终收口前必须至少写出一次阶段性 `observer-request.json`，由外层 harness 以兄弟进程触发同机观察者，并把阶段观察输出写入 `.redcap/evidence/e2e/observer-stages/`；阶段观察只证明运行中可观测，不替代最终冻结证据包和最终 `independent-observer.json`。
- 若 E2E 外层 harness 超时、崩溃、中断、观察者命令失败或 `observer-request.json` 缺失，必须仍然写入自动观测证据；如果外部项目 `.redcap/` 已存在，写入该项目级长期观察器的 `harness-auto-observation-issues.json`、`harness-auto-observation.json`、`issues.jsonl`、`LATEST-HANDOFF.json` 和可 `resume` 的恢复说明；如果失败发生在外部项目创建前，写入 `<work-root>/redcap-e2e-pre-project-observation/.redcap/` 前置失败观察池，并声明它不是 OL-11 目标交付项目。失败不能静默丢失，也不能被改写为通过。
- 棱镜完成需求、架构或最终证据链复核。
- 失败回流至少真实发生一次，或有充分证据说明没有失败且负向探针仍通过。
- 自我净化候选和处理决策存在。
- `.redcap/` 运行产物没有污染 RedCap 源仓库。
- 缓存保留策略执行完成，未发生无界膨胀。

## 能力覆盖矩阵

每次 RedCap 新增能力后，必须更新本矩阵。否则未来 OL-11 执行前的设计检查应失败。

| 能力项 | 必须观察到的证据 |
| --- | --- |
| 项目级安装 | 外部项目 `.redcap/` 初始化成功，配置和运行产物均在外部项目内 |
| 长期观察器 | `.redcap/state/longrun-observer/observations.jsonl` 记录多轮事实，`auto-collect` 自动扫描 E2E 证据并写入 `issues.jsonl`、`evaluation.json`、`LATEST-HANDOFF.json`、`archive/<run-id>/handoff.json`、`sample-registry.json` 和 `collector-state.json`；harness 超时/崩溃/观察请求缺失时必须通过 `auto-collect --issue-json` 摄入结构化 P1 问题；若目标项目尚未创建，必须写入前置失败观察池并保留边界声明；完整 E2E 还必须在最终收口前写出阶段性 `observer-request.json`，证明 worker 运行中也能被 harness 观测 |
| Hook 触发 | 项目级 Hook 事件摘要包含会话启动、用户提示、工具前、工具后和停止前检查 |
| Loom 角色分工 | 每个角色有独立会话、输入、输出、原始日志和下游交付 |
| 会话接续 | 同一角色返工复用 `session_id`，丢失时告警并进入复核 |
| 棱镜协助 | 需求、架构、代码或最终证据链至少一处由棱镜复核 |
| 失败回流 | 失败项被路由到正确角色，并从该角色节点重新推进 |
| 变更接入 | 第二轮需求变更形成需求、架构、实现、测试全链路增量证据 |
| 知识召回 | 执行前或关键决策前检索已有知识，记录采用或跳过理由 |
| 自我净化 | 任务后生成候选、评估晋升、私有保留或不晋升 |
| 私有边界 | Cap 人格材料不写入公共 RedCap 仓库 |
| 缓存治理 | 每轮后执行保留上限检查，失败运行保留有界 |
| 长任务防漂移 | 多轮推进有父目标、迭代账本、停止条件和防盲目重跑证据 |
| 验收独立性 | Cap 不直接开发目标项目，只审核和路由 |
| 生产边界 | 不接入真实账号、不公网发布、不做不可逆外发动作 |

## 产物要求

未来执行 OL-11 时，至少生成以下结构化产物：

```text
<外部项目>/.redcap/evidence/e2e/fixed-demand-package.json
<外部项目>/.redcap/evidence/e2e/role-session-manifest.json
<外部项目>/.redcap/evidence/e2e/iteration-01-summary.json
<外部项目>/.redcap/evidence/e2e/iteration-02-change-summary.json
<外部项目>/.redcap/evidence/e2e/failure-backlog.json
<外部项目>/.redcap/evidence/e2e/cap-observer-verdict.json
<外部项目>/.redcap/evidence/e2e/capability-coverage-matrix.json
<外部项目>/.redcap/evidence/e2e/final-prism-review.json
<外部项目>/.redcap/evidence/e2e/cache-retention-report.json
<外部项目>/.redcap/evidence/e2e/observer-stages/request-<stage>.json
<外部项目>/.redcap/evidence/e2e/observer-stages/evidence-bundle-<stage>.json
<外部项目>/.redcap/evidence/e2e/observer-stages/independent-observer-<stage>.json
<外部项目>/.redcap/evidence/e2e/harness-auto-observation-issues.json
<外部项目>/.redcap/evidence/e2e/harness-auto-observation.json
<外部项目>/.redcap/state/longrun-observer/observations.jsonl
<外部项目>/.redcap/evidence/longrun-observer/issues.jsonl
<外部项目>/.redcap/evidence/longrun-observer/evaluation.json
<外部项目>/.redcap/evidence/longrun-observer/LATEST-HANDOFF.json
<外部项目>/.redcap/evidence/longrun-observer/archive/<run-id>/handoff.json
<外部项目>/.redcap/state/longrun-observer/sample-registry.json
<外部项目>/.redcap/state/longrun-observer/collector-state.json

# 仅当前置失败发生在目标项目创建前时生成，不得冒充目标项目产物：
<work-root>/redcap-e2e-pre-project-observation/.redcap/evidence/e2e/harness-auto-observation-issues.json
<work-root>/redcap-e2e-pre-project-observation/.redcap/evidence/e2e/harness-auto-observation.json
<work-root>/redcap-e2e-pre-project-observation/.redcap/evidence/longrun-observer/issues.jsonl
<work-root>/redcap-e2e-pre-project-observation/.redcap/evidence/longrun-observer/LATEST-HANDOFF.json
<work-root>/redcap-e2e-pre-project-observation/.redcap/state/longrun-observer/pre-project-boundary.json
```

自动观测收集的判定边界如下：

- 缺少尚未完成阶段的证据，记录为 `continue_observing` 影响的 P2 问题，不直接伪造成实现失败。
- 已存在证据不可读、不是合法 JSON、会话丢失、项目级 Hook 缺失、源仓库泄漏、Cap 直接写目标项目代码、或出现开放 P0/P1，必须记录为 `needs_fix`。
- E2E harness 超时、worker 崩溃、观察者命令失败或缺少 `observer-request.json`，必须记录为 `needs_fix` 的 P1 问题，并生成跨会话 handoff。
- 每轮 OL-11 E2E 必须先运行故障注入场景，确认开放 P1 会写入 `issues.jsonl` 并让评估结果进入 `needs_fix`，再允许接受正向路径。
- 自动观测收集自身必须优先通过 `complete-revival-e2e auto-observation-targeted-e2e` 的定向验收；若该定向验收失败，不允许启动或接受完整 OL-11 结果，因为此时全量样本失败可能仍会丢失可恢复证据。
- 新会话必须能通过固定路径 `LATEST-HANDOFF.json` 或命令 `longrun-observer resume --project <外部项目>` 读取验收背景、当前问题和下一步动作。

## 反作弊边界

以下情况必须判定 OL-11 未通过：

- 开发 AI 直接读取旧 TRPG 源码。
- Cap 替开发 AI 写目标项目代码。
- 只有最终项目产物，没有 RedCap 角色、证据、会话和 Hook 过程证据。
- 只有一轮即时生成项目，没有多轮变更或失败回流。
- 把短期 fixture 或 LS-006（已有短期外部样本）扩写成长期第三方生产样本。
- 把方案文档完成写成 OL-11 已通过。

## 当前状态

本文件当前状态是“方案已固化，执行前棱镜阻塞已按 resolution-check 处理，等待正式启动 OL-11 前置预检”。它仍然是终局开放边界，不允许关闭。完整 OL-11 E2E 只有在用户明确启动后才能执行；长期样本通过前，不得声明 RedCap 完整复活。
