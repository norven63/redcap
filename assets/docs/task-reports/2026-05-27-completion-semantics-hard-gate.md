# 任务完成报告：完成语义硬门修复

**报告日期**：2026-05-27
**执行者**：Cap（Codex.app 主执行）
**报告版本**：v0.2

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：完成语义硬门已实现；RedCap 现在会把“证明、保留、延期、禁用、需要人工决策”识别为非完成状态，不能再直接包装成“全部完成”。

### 0.2 上一步完成的是

- 上一步完成的是：完整回归与棱镜独立评审已通过；回归期间发现两个 acceptance 夹具漏接新硬门，已同步修复并重跑通过。

### 0.3 下一步计划做的是

- 下一步计划做的是：进入 closeout runtime 收口，生成本任务 receipt；本报告不宣称资产历史债务、full LLM-wiki 或正式发布已经完成。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：定位 false-completion 根因 -> 新增完成语义政策 -> 接入总检和诊断 -> 纠偏旧报告 -> 增加负例回归 -> 独立评审 -> 完整回归 -> closeout。
- 当前所在位置：实现、棱镜评审和完整回归已完成，正在进入 receipt 收口。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮不执行正式发布、不读取私密文件、不做不可恢复删除；若后续确实要删除历史证据或启用真实 RAG 后端，才需要 Norven 明确授权。

## 一、需求背景

Norven 指出：近一段时间里，“资产历史债务”和“长期记忆”任务经常被记录、证明、形成边界或写入 roadmap，而不是被真实执行；但 RedCap 仍会输出类似“已完成”的结论。这说明问题不是单个报告写得不好，而是 RedCap 缺少一个专门判断“什么才算完成”的硬门。

## 二、方案讨论

### 2.1 原始意图覆盖审计

- scope_status：full-implementation
- 原始意图：找出为什么 RedCap 总把记录/证明/延期当成完成，并做成可复用防线。
- 已覆盖：完成语义政策、当前任务检查、历史报告纠偏、总检/诊断接入、负例验收、closeout runtime 防绕过、完整回归。
- 未覆盖/延期：资产历史债务的破坏性删除、真实 RAG/GraphRAG 后端启用、正式发布动作。
- 用户可见边界：本轮修的是“不能再假完成”的控制面；不宣称历史资产或 full LLM-wiki 本体已经因此全部完成。

### 2.2 裁决原则

本轮采用“先修判断完成的尺子，再用这把尺子审后续任务”的原则。这样可以避免继续在旧尺子下把更多证据、报告和 receipt 误当作真实完成。

## 三、落地结果

### 3.1 任务树裁决

| 事项 | 当前裁决 | 原因 | 是否阻塞本轮 |
|---|---|---|---|
| 完成语义政策 | 已实现并验收 | 已定义 done 与非完成状态边界 | 不阻塞 |
| 当前任务完成标准检查 | 已实现并验收 | 勾选完成项不能含 preserve/defer/proof/human-decision escape clause | 不阻塞 |
| 上轮债务报告纠偏 | 已实现并验收 | 已加 invalidated-as-full-completion 标记 | 不阻塞 |
| closeout runtime 防绕过 | 已实现并验收 | closeout / rescue 生成 receipt 前会先跑完成语义检查 | 不阻塞 |
| 资产历史债务本体 | 未在本轮执行 | 本轮只修完成判定，不做破坏性删除或历史证据迁移 | 不计入本轮完成 |
| full LLM-wiki 真实后端 | 未在本轮执行 | 本轮只防止“禁用边界”冒充“后端完成” | 不计入本轮完成 |

### 3.2 关键边界

- `done` 只能表示真实实施完成并通过验收。
- `preserve-with-proof`、`deferred`、`implemented-proposal-only`、`disabled-by-default-controlled-boundary`、`blocked-by-human-destructive-decision` 都不能计入完成。
- 如果必须完成的工作确实卡在人工授权或破坏性动作上，它必须保持 open / blocked，而不能写成“不阻塞本轮”。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 人话解释 | 本轮用途 |
|---|---|---|
| 完成语义 | 判断“什么才算完成”的规则 | 防止证明、延期、保留被写成完成 |
| false-completion | 看起来有报告和证据，但用户要求的事没有真实做完 | 本轮要拦截的核心问题 |
| preserve-with-proof | 保留并说明原因 | 只能算边界，不能算完成 |
| blocked-by-human-decision | 需要人类批准后才能继续 | 只能算阻塞，不能算完成 |

## 四、人工审核要点

当前不需要 Norven 人工介入。本轮没有触发发布、私密读取或不可恢复删除。如果后续某个任务被新硬门判定为 blocked，而解除阻塞需要真实删除历史证据、修改发布开关或启用外部后端，我会单独说明“是什么、为什么需要你决策、风险是什么”。

## 五、验证结果

### 5.1 机器验收

已通过：

- 已通过：`bash compass/tools/redcap-completion-semantics-check.sh --task-file .dev-task.md`
- 已通过：`bash compass/tools/redcap-multi-session-acceptance.sh completion-semantics-check`
- 已通过：`bash compass/tools/redcap-spec-check.sh "$PWD"`
- 已通过：`bash compass/tools/redcap-diagnose.sh .dev-task.md`
- 已通过：`bash compass/tools/redcap-layerb-closeout-runtime-check.sh .dev-task.md`
- 已通过：`bash compass/tools/redcap-multi-session-acceptance.sh spec-check-propagates-control-gate-failures`
- 已通过：`bash compass/tools/redcap-multi-session-acceptance.sh spec-check-rejects-superseded-outside-archive`
- 已通过：`bash compass/tools/redcap-multi-session-acceptance.sh spec-check-requires-replaced-by`
- 已通过：`bash compass/tools/redcap-multi-session-acceptance.sh spec-check-rejects-invalid-role`
- 已通过：`bash compass/tools/redcap-multi-session-acceptance.sh spec-check-rejects-replacement-cycle`
- 已通过：`bash compass/tools/redcap-multi-session-acceptance.sh spec-check-accepts-archived-superseded`
- 已通过：`bash compass/tools/redcap-multi-session-acceptance.sh all`

### 5.2 棱镜独立评审

- 已完成：`20260527-completion-semantics-hard-gate-review`
- 评审结论：Kimi 与 Claude Code 两路独立评审均返回可验收；评审指出 closeout/rescue 也需要接入完成语义检查，已当场修复并补回归。

### 5.3 closeout runtime / receipt

| 项目 | 当前值 |
|---|---|
| closeout receipt | 待生成；本报告更新后进入 runtime complete |
| 当前状态 | 实现、评审与回归已完成 |
| 人工介入 | 不需要 |

### 5.4 完成等级（禁止混报）

| 等级 | 结论 | 说明 |
|---|---|---|
| 已实现 | 是 | 完成语义政策、检查脚本、总检/诊断接入、旧报告纠偏和负例验收已落地 |
| 已自检 | 是 | 专项检查、诊断、总检、closeout runtime 检查和完整 acceptance 均通过 |
| 已独立验收 | 是 | Prism 验收通过，且评审发现已修 |
| 已正式完成 | 待 closeout | closeout receipt 还未生成，本报告不能替代 receipt |

## 六、遗留问题与下一步

下一步是执行 closeout runtime complete。若新硬门发现某个历史任务其实仍未真实完成，后续只能把它标为 open/blocker 或重新立项执行，不能再用“已有证明/已有边界”关掉。

## 七、经验沉淀

这次经验是：RedCap 不能只问“有没有报告、有没有 receipt、有没有边界说明”，还必须问“用户要求的动作到底有没有真实执行”。完成语义本身必须是硬门，否则治理系统会不断生成漂亮证据，却继续漏掉真正的债务。

### 7.3 Evolution Factory 候选处理

当前 Evolution 处理结论：no-promote。理由是本轮经验已经直接固化为完成语义政策、检查脚本、验收负例和旧报告纠偏；不再额外新增候选，避免“沉淀修复沉淀”的治理自增殖。

## 八、附录

### 8.1 未执行边界

- 未执行正式 npm 发布动作。
- 未读取 `.env`、identity 原文、飞书 secret 或其他私密文件。
- 未做不可恢复删除。
- 未启用真实 RAG / GraphRAG 后端。
