# 任务完成报告：正式发布外最终清账

**报告日期**：2026-05-25
**执行者**：Cap（Codex.app 主执行，Kimi 主负载 + Claude Code 复核）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：正式发布外最终清账已经完成；实现、专项回归、完整 `spec-check`、`diagnose`、棱镜独立验收和 closeout receipt 均已通过。

### 0.2 上一步完成的是

- 上一步完成的是：Kimi 完成长文/任务树主审，Claude Code 完成工程风险复核；两边都给出可收口结论，且无阻塞项。

### 0.3 下一步计划做的是

- 下一步计划做的是：本轮非发布清账不再追加开发事项；后续进入正式发布准备线，并继续保留人工授权、许可证、registry 和发布开关等发布前决策边界。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：重新锚定非发布清账任务 -> 固化 Kimi/Claude 工作量策略 -> 裁决旧路径、运行证据和 full LLM-wiki 三类容易误判事项 -> 棱镜评审 -> 回归 -> closeout receipt。
- 当前所在位置：本轮已完成 receipt 收口；正式发布之外的已知可做事项已完成、正式延期或转入发布任务边界。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮没有触及许可证、registry、凭据、发布开关、私密文件读取或破坏性删除；如需真实删除 `prism/runs` 或移除旧兼容入口，才会进入人工保留决策。

---

## 一、需求背景

Norven 要求把“记录在案、未记录在案、以及两个容易误判点”全部纳入同一任务树：凡是正式发布之外已知可做的优化项，都要实现、验证或正式延期，直到剩余事项只属于正式发布任务本身。

## 二、方案讨论

### 2.1 原始意图覆盖审计

- scope_status：full-implementation
- 原始意图：防止 RedCap 把“登记到发布线、兼容保留、长期延期”误报成“已经完成”，并把正式发布外的已知可做事项一次性清账。
- 已覆盖：本轮已覆盖非发布清账任务锚点、Prism Kimi 倾斜策略、两个容易误判点、full LLM-wiki 状态、机器检查、完整回归、棱镜验收和待收口事项。
- 未覆盖/延期：正式发布动作、许可证选择、registry 凭据、发布开关、破坏性删除、旧兼容入口彻底消失、`prism/runs` 物理清空、full LLM-wiki 完整产品实现。
- 用户可见边界：完成后只能说“正式发布外清账已完成、正式延期或转入发布任务”，不能说 RedCap 已发布。

### 2.2 裁决原则

本轮采用“能做就做、不能擅自做就写清边界、属于发布任务就转入发布线”的裁决原则。这样可以避免把高风险删除、正式发布授权、长期产品能力误算成本轮普通开发债务。

## 三、落地结果

### 3.1 任务树裁决

| 事项 | 当前裁决 | 原因 | 是否阻塞本轮 |
|---|---|---|---|
| Prism Kimi 倾斜策略 | done | 已写入 provider policy、README、CONTRIBUTING.core、文件查阅字典，并有机器检查。 | 不阻塞 |
| 旧路径兼容入口 | release-scope | 旧路径是历史报告、receipt 和脚本的兼容入口；彻底移除旧路径名属于正式发布前高风险边界处理，不能在本轮无破坏性删除承诺下硬删。 | 不阻塞本轮，但阻塞正式发布前最终结构证明 |
| `prism/runs` 本地运行证据 | human-decision-required-before-apply | 该目录是本地原始运行证据；可 inventory / dry-run，但真实删除或批量归档会影响考古链，必须等显式破坏性操作授权。 | 不阻塞本轮，但阻塞“物理清空运行证据”声明 |
| full LLM-wiki | formal-defer | 当前只有 LLM-wiki-lite；完整 Wiki 产品、后台蒸馏 worker、RAG/GraphRAG 已有 roadmap 和触发条件，但不是本轮必须实现的普通债务。 | 不阻塞本轮，但不能冒充已实现 |
| 正式发布相关任务 | release-scope | 包发布安全、release readiness、人工授权、registry、版本号、发布动作均属于正式发布任务本体。 | 不属于本轮 |

### 3.2 关键边界

- 本轮可以说：provider 策略已落地，旧路径和 `prism/runs` 不会再被误报为“普通开发债务已完成”，full LLM-wiki 保持显式延期。
- 本轮不能说：RedCap 已经正式发布、旧路径已物理消失、`prism/runs` 已清空、full LLM-wiki 已实现。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 人话解释 | 本轮用途 |
|---|---|---|
| provider policy | 棱镜选择外部 Agent 的规则 | 把 Kimi 优先承担长文、Claude Code 独立复核写成可检查约束 |
| release-scope | 属于正式发布任务本体 | 防止把发布前高风险边界误算成本轮普通开发任务 |
| human-decision-required-before-apply | 真正执行前必须人工授权 | 用于破坏性删除、证据清空、私密信息处理等 AI 不能擅自决定的动作 |
| formal-defer | 正式延期但不遗忘 | 用于 full LLM-wiki 这类有 roadmap、但当前不应静默实现的长期能力 |
| closeout receipt | RedCap 的完工凭证 | 只有 receipt 生成后，才允许宣称任务正式完成 |

## 四、人工审核要点

当前不需要 Norven 人工介入。本轮所有实际改动都停留在规则、检查器、报告和快照同步层；没有执行正式发布、没有读取私密文件、没有删除历史证据。

如果后续要让旧兼容入口消失，或要清空 `prism/runs`，那会改变历史考古能力和证据生命周期，必须另行取得显式授权。

## 五、验证结果

### 5.1 机器验收

已通过：

- `bash compass/tools/redcap-prism-provider-policy-check.sh`
- `bash compass/tools/redcap-file-lookup-dictionary-check.sh`
- `bash compass/tools/redcap-workflow-gate-stratification-check.sh --task-file .dev-task.md`
- `bash compass/tools/redcap-r1-control-plane-contract-split-check.sh`
- `bash compass/tools/redcap-r1-prism-evidence-retention-split-check.sh`
- `bash compass/tools/redcap-r1-prism-package-visible-support-copy-first-apply-check.sh`
- `bash compass/tools/redcap-r1-layera-product-boundary-check.sh`
- `bash compass/tools/redcap-pre-release-product-architecture-check.sh`
- `bash compass/tools/redcap-multi-session-acceptance.sh spec-check-propagates-control-gate-failures`

已通过：

- 完整 `spec-check`
- `diagnose`
- `bash compass/tools/redcap-human-output-quality-check.sh --task-file .dev-task.md`
- `bash compass/tools/redcap-intent-coverage-check.sh .dev-task.md`
- `bash compass/tools/redcap-evolution-harvest-check.sh .dev-task.md`
- `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md`

待完成：

- closeout receipt

### 5.2 棱镜独立评审

- 当前状态：通过。
- Kimi 负责长文/任务树主审，Claude Code 负责工程风险复核。
- 验收运行：`20260525-pre-release-non-publish-final-closure`。
- 结果：2 个 provider 均已响应，未发现阻塞项。
- 低风险意见：Claude Code 提醒 provider workload scope 需要避免和路由覆盖策略混淆；已用 `scope_note` 写清该比例只约束长文评审/委托负载，不改变轻量健康嗅探或直接 CLI 调用。

### 5.3 closeout runtime / receipt

| 项目 | 当前值 |
|---|---|
| closeout receipt | /tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/pre-release-non-publish-final-closure-52d8c6ce6a7ca165f654e3458fba53cfbdd333d7082d0670574bd84f65131bfa.json |
| 当前状态 | completed，pending closure 已由 closeout runtime 清除 |
| 人工介入 | 不需要 |

### 5.4 完成等级（禁止混报）

| 等级 | 结论 | 说明 |
|---|---|---|
| 已实现 | 是 | provider 策略、争议项裁决、快照同步和控制面检查都已落地 |
| 已自检 | 是 | 专项检查、完整 spec-check、diagnose 和人类可读报告检查均已通过 |
| 已独立验收 | 是 | Kimi 主审与 Claude Code 复核均无阻塞项 |
| 已正式完成 | 是 | closeout receipt 已生成，独立验收与承诺账本均为通过状态 |

## 六、遗留问题与下一步

本轮正式发布外最终清账已经完成。下一步不再追加非发布开发事项，进入正式发布准备线；正式发布仍需要单独处理许可证、registry、版本号、发布开关、发布安全和人工授权。

## 七、经验沉淀

本轮经验是：RedCap 不能把“分类、延期、转入发布任务”写成“完成”。凡是长期任务中被用户反复追问的事项，都需要进入任务树裁决，并明确是 done、formal-defer、release-scope 还是 human-decision-required。

### 7.3 Evolution Factory 候选处理

本轮命中高价值经验信号：用户明确指出“登记到发布线/延期/兼容保留”容易被误报为“完成”，这属于 RedCap 长任务治理中的典型口径漂移问题。

处理结论：deferred-with-owner owner=RedCap-Forge trigger=post-closeout-evolution-harvest。

原因：本轮先完成主任务收口；经验沉淀应在 closeout 后由 Forge 判断是否晋升为长期模式，避免未收口时继续扩大任务范围。

## 八、附录

### 8.1 未执行边界

- 未执行正式发布。
- 未改许可证、registry、凭据、发布开关或 package privacy。
- 未读取 `.env`、identity 原文、飞书 secret 或其他私密文件。
- 未做破坏性删除。
- 未迁移或清空 `prism/runs` raw evidence。
