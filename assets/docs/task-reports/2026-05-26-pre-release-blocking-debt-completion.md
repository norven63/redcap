# 任务完成报告：发布前阻塞债务完成

**报告日期**：2026-05-26
**执行者**：Cap（Codex.app 主执行，Kimi 主负载 + Claude Code 复核）
**报告版本**：v1.1

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：棱镜范围评审已完成；资产历史债务已落成机器可检 receipt；full LLM-wiki 已从 lite/deferred 升级为受控本地产品层，包含索引、队列、候选 worker、receipt 和 RAG/GraphRAG 禁用边界。

### 0.2 上一步完成的是

- 上一步完成的是：上一条“正式发布外最终清账”任务已生成 receipt，工作区干净；本轮从新的阻塞债务任务开始。

### 0.3 下一步计划做的是

- 下一步计划做的是：提交已验证工程变更，随后由 closeout runtime 生成正式完工凭证并复验 pending closure 已清零。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：重锚发布前阻塞债务 -> 棱镜范围评审 -> 资产历史债务清理 -> full LLM-wiki/worker/RAG 边界补全 -> 全量回归 -> 最终棱镜验收 -> closeout receipt。
- 当前所在位置：资产债务和长期记忆补全已实现，全量回归和最终棱镜验收已通过；closeout runtime 要求先提交干净工作树，再生成正式完工凭证。

### 0.5 是否需要 Norven 人工介入

- 人工介入：暂时不需要。
- 说明：当前还没有执行不可恢复删除、正式发布、许可证/registry/凭据变更或私密文件读取；如果棱镜确认某个清理动作必须破坏性删除且无法安全回滚，我会停下来请求决策。

## 一、需求背景

Norven 明确确认：此前被归类为 release-scope 的资产历史债务，以及被归类为 formal-defer 的 full LLM-wiki / 长期记忆能力补全，都必须在首次正式发布前完成。这个决策改变了上一轮收口结论的边界：这些事项不再只是“未来或发布边界”，而是当前必须推进的发布前阻塞债务。

## 二、方案讨论

### 2.1 原始意图覆盖审计

- scope_status：full-implementation
- 原始意图：把旧兼容入口、`prism/runs` raw evidence、历史资产物理收敛、full LLM-wiki、后台蒸馏 worker 和 RAG/GraphRAG 边界全部纳入发布前必须完成范围。
- 已覆盖：任务锚点、资产债务线、长期记忆线、棱镜评审线、回归与 closeout 线。
- 未覆盖/延期：正式 npm 发布动作、许可证选择、registry 凭据、发布开关和真实外部发布。
- 用户可见边界：本轮可以完成发布前阻塞债务，但不能宣称已经正式发布 RedCap。

### 2.2 裁决原则

本轮采用“能安全完成就完成；不能安全删除就改成可审计外置或保留证明；属于法律/凭据/发布动作就停下请求人工决策”的原则。这样可以避免为了追求目录干净而破坏 receipt、考古链或私密边界。

## 三、落地结果

### 3.1 任务树裁决

| 事项 | 当前裁决 | 原因 | 是否阻塞本轮 |
|---|---|---|---|
| 旧兼容入口 | preserve-with-proof | 已逐项记录为兼容 shim；物理删除会触及历史引用和回滚风险，需 Norven 明确授权。 | 不阻塞本轮，保留人工破坏性边界 |
| `prism/runs` raw evidence | governed-local-evidence-layer | 生命周期脚本证明当前无可自动清理 fixture；formal run 保留，禁止 bulk delete。 | 不阻塞本轮，formal run 删除属人工边界 |
| full LLM-wiki | implemented-controlled-local-product | 已补齐私有本地产品层、entry/index/queue/receipt、source anchor、staleness 与检查脚本。 | 不阻塞 |
| 后台蒸馏 worker | implemented-proposal-only | worker 已可生成带去重、隐私扫描、source anchor 和 receipt 的候选；不自动改写权威源。 | 不阻塞 |
| RAG/GraphRAG | disabled-by-default-controlled-boundary | 已有受控适配层和 activation gate；真实后端启用需另立任务。 | 不阻塞本轮 |

### 3.2 关键边界

- 本轮必须证明“发布前阻塞债务”完成或升级到明确人工破坏性决策边界；当前实现已做到这一点，并已通过最终回归和棱镜验收。
- 本轮不能执行正式 npm 发布动作。
- 本轮不能把 package exclusion、roadmap、future trigger 或口头说明冒充完成。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 人话解释 | 本轮用途 |
|---|---|---|
| 资产历史债务 | 历史遗留目录、证据、兼容入口和旧资产造成的工程结构欠账 | 把旧路径和运行证据从“解释清楚”推进到“治理完成” |
| full LLM-wiki | 不只是 lite 语义记忆，而是有队列、审核、索引、过期检测和收据的长期记忆产品层 | 补齐首次发布前的长期记忆能力 |
| 后台蒸馏 worker | 自动扫描候选材料并提出沉淀建议的程序 | 解决经验沉淀依赖人工提醒的问题 |
| RAG/GraphRAG 边界 | 是否启用重型检索后端以及如何防止它越权 | 防止把未启用后端说成已完成，也防止过早引入复杂依赖 |
| closeout receipt | RedCap 的正式完工凭证 | 只有 receipt 生成后，本轮才能宣称完成 |

## 四、人工审核要点

当前暂时不需要 Norven 人工介入。后续若出现不可恢复删除、私密信息处理、许可证、registry、凭据或真实发布授权，我会中断并明确列出“是什么、为什么需要你决策、风险是什么”。

## 五、验证结果

### 5.1 机器验收

已通过：

- 已通过：`bash prism/tools/prism-runs-lifecycle.sh check`
- 已通过：`bash compass/tools/redcap-full-llm-wiki-roadmap-check.sh`
- 已通过：`bash compass/tools/redcap-full-llm-wiki-check.sh`
- 已通过：`bash compass/tools/redcap-full-llm-wiki-worker.sh --check`
- 已通过：`bash compass/tools/redcap-rag-graphrag-boundary-check.sh`
- 已通过：`bash compass/tools/redcap-pre-release-blocking-debt-check.sh`
- 已通过：`bash compass/tools/redcap-knowledge-index-check.sh`
- 已通过：`bash compass/tools/redcap-knowledge-gateway.sh check`
- 已通过：`bash compass/tools/redcap-package-publish-safety-check.sh`
- 已通过：`bash compass/tools/redcap-runtime-package-manifest.sh --check --npm-pack-dry-run`
- 已通过：`bash compass/tools/redcap-prism-provider-policy-check.sh`
- 已通过：`bash compass/tools/redcap-clean-workspace-e2e.sh --check-result`
- 已通过：`bash compass/tools/redcap-multi-session-acceptance.sh all`
- 已通过：`bash compass/tools/redcap-spec-check.sh .`
- 已通过：`bash compass/tools/redcap-diagnose.sh .dev-task.md`

### 5.2 棱镜独立评审

- scope review 已完成：`prism/runs/20260526-pre-release-blocking-debt-scope-review-v2`。
- Kimi 结论：先治理证据，再补记忆骨架，最后处理高风险物理收敛；无硬阻断可开工。
- Claude Code 结论：资产线先清后治、记忆线分层实现，高风险删除走人工门。
- 两路均未报告 blocker。
- 最终验收 Prism 已完成：`prism/runs/20260526-pre-release-blocking-debt-final-acceptance`。
- 通过角色：Claude Code acceptance + Codex CLI read-only fallback。
- Kimi 最终验收尝试未纳入 quorum：它越过“只审查”边界并触发诊断递归风险，已终止并保留为不可用/不干净证据。
- Gemini 最终验收尝试未纳入 quorum：本地账号/地区资格不可用。

### 5.3 closeout runtime / receipt

| 项目 | 当前值 |
|---|---|
| closeout receipt | 待生成；提交干净工作树后由 runtime 写入 `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/pre-release-blocking-debt-completion-df29028374325029b326c6047510279d2f88e0703406a58231126bbd0d4bc770.json` |
| 当前状态 | 实现、回归和最终棱镜验收已通过；closeout runtime 已确认承诺账本 0 项未兑现，但要求先提交当前工程变更 |
| 人工介入 | 暂时不需要 |

### 5.4 完成等级（禁止混报）

| 等级 | 结论 | 说明 |
|---|---|---|
| 已实现 | 是 | 资产债务 receipt、full LLM-wiki、worker、RAG 边界均已落地 |
| 已自检 | 是 | 新增检查、知识网关、包面安全、Prism runs 生命周期、完整 spec-check、diagnose 和全量 acceptance 均已通过 |
| 已独立验收 | 是 | scope review 与最终验收均已通过；最终 quorum 为 Claude Code acceptance + Codex CLI read-only fallback |
| 已正式完成 | 否 | closeout receipt 尚未生成 |

## 六、遗留问题与下一步

下一步提交本轮已验证工程变更，然后生成 closeout receipt，并复验 pending closure 已清零。若 closeout runtime 发现新的 blocker，先修复；若 blocker 触及不可恢复删除、私密信息、许可证/registry/凭据或真实发布授权，则中断请求 Norven 决策。

## 七、经验沉淀

本轮经验信号是：当用户把“延期项/发布边界项”升级为“发布前必须完成项”时，RedCap 必须重新立项、重跑棱镜，并把完成标准落成机器可检 receipt。对于历史证据和兼容 shim，工程完成不等于强行删除；更安全的完成形态是“逐项 disposition + 引用证明 + 人工破坏性边界”。

### 7.3 Evolution Factory 候选处理

当前 Evolution 处理结论：no-promote。理由是本轮新增的是可执行治理能力和长期记忆基础设施，已经通过 full LLM-wiki entry / queue / receipt、发布前阻塞债务 receipt 和机器检查表达；不再额外新增 Evolution candidate，避免治理资产继续制造新的治理债务。

## 八、附录

### 8.1 未执行边界

- 未执行正式 npm 发布动作。
- 未改许可证、registry、凭据、发布开关或 package privacy。
- 未读取 `.env`、identity 原文、飞书 secret 或其他私密文件。
- 未做不可恢复删除。
