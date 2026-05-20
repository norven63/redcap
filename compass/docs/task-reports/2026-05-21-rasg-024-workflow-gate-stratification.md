# 任务完成报告：RASG-024 工作流门禁分级治理

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：已把 RedCap 的任务检查强度拆成三档：轻量任务、标准实现任务、发布/结构迁移任务。核心效果是：报告、索引这类低风险收尾漂移不会再自动拖进发布级回归；但发布、安全、包公开面、破坏性迁移、validator 链路和 closeout runtime 仍然保持最高强度。
- 已新增机器检查，校验“高风险任务不能降级”“当前任务必须声明门禁层级和原因”“样本预期不能漂移”。这避免以后只靠口头判断任务该跑多少回归。
- 已把这套检查接入 `spec-check`、`diagnose`、进度仪和 acceptance 回归。换句话说，它不是单独放着的文档，而是进入了 RedCap 的常规检查链。
- 已把 P4-8 暴露出的“报告/catalog 更新导致 clean workspace E2E 证据反复失效”固化成样本：只允许任务报告、文档索引、指定报告索引这类非包面结果漂移；包面、runtime、工具、发布策略仍然会阻断。
- 已同步更新包候选数量和 R1 发布前快照账本：新增 4 个治理资产后，候选数从 272 变为 276；相关发布前审计快照已跟随更新。

### 0.2 上一步完成的是

- 上一步完成的是：完成 P4-8 正式发布前最终 E2E 证据刷新与 closeout 收口后，发现 RedCap 工作流仍有一个系统性坏味：小任务经常被迫支付发布级验证成本，导致任务耗时变成数小时，并增加被打断风险。

### 0.3 下一步计划做的是

- 下一步计划做的是：完成 Prism 独立评审、`diagnose`、clean workspace E2E 刷新和 closeout receipt。如果评审发现 blocker，先修 blocker；如果没有 blocker，本任务进入正式收口。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：历史债务坏味 -> RASG-024 工作流门禁分级治理 -> 正式发布前 readiness 任务集。
- 当前所在位置：RASG-024 正在收口前验证；它完成后，RedCap 再回到发布前 readiness 主线。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮不涉及许可证、发布开关、registry 凭据、私密资产公开、破坏性迁移或是否正式发布的人工决策。

## 一、需求背景

RedCap 之前的门禁策略偏“全局高强度默认”。这对发布安全是好事，但对轻量收尾、报告补记、索引刷新会变成成本黑洞。最危险的不是“跑得多”，而是“跑得多但没有说明为什么”：用户看不到任务为什么要几小时，Agent 也容易把所有任务都当成同一级别。

本轮的结论是：检查强度必须显式分级。轻量任务可以轻，但发布级任务不能轻；低风险漂移可以不刷新 clean workspace E2E，但包面和 runtime 变化必须继续 fail-closed。

## 二、方案讨论

- 门禁分级政策：`references/workflow-gate-stratification-policy.json`
- 分级回归样本：`references/workflow-gate-stratification-samples.json`
- 机器检查入口：`compass/tools/redcap-workflow-gate-stratification-check.sh`
- 上层接入点：`redcap-spec-check.sh`、`redcap-diagnose.sh`、`redcap-progress-meter.py`、`redcap-clean-workspace-e2e.py`
- 回归覆盖：`redcap-multi-session-acceptance.sh workflow-gate-stratification-check` 与 `spec-check-propagates-control-gate-failures`

## 三、落地结果

- `bash compass/tools/redcap-workflow-gate-stratification-check.sh --task-file .dev-task.md`：通过
- `bash compass/tools/redcap-progress-meter-check.sh`：通过
- `bash compass/tools/redcap-multi-session-acceptance.sh workflow-gate-stratification-check`：通过
- `bash compass/tools/redcap-multi-session-acceptance.sh spec-check-propagates-control-gate-failures`：通过
- `bash compass/tools/redcap-file-lookup-dictionary-check.sh`：通过
- `bash compass/tools/redcap-spec-check.sh "$PWD"`：通过

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 人话解释 | 本轮作用 |
| --- | --- | --- |
| 门禁分级 | 按任务风险决定检查强度 | 让轻量任务不再被迫跑发布级流程，同时保护高风险任务不能降级 |
| post-result drift | 验证后又出现的低风险结果文件变化 | 把报告、索引这类可解释漂移和包面/runtime 漂移区分开 |
| package surface | 将来公开包可能包含的文件集合 | 本轮新增治理资产后，同步证明公开面数量变化可解释 |
| release-structural | 发布、安全、迁移、validator、closeout 等高风险层级 | 保证关键任务继续 fail-closed，不因分级而变松 |

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
| --- | --- | --- | --- |
| 1 | 无需本轮人工审核 | 本轮只是内部工作流治理，不触碰发布开关、凭据、许可证或破坏性删除。 | P1 |

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 当前结果 |
| --- | --- | --- |
| 门禁分级专项检查 | `bash compass/tools/redcap-workflow-gate-stratification-check.sh --task-file .dev-task.md` | 通过 |
| 进度仪检查 | `bash compass/tools/redcap-progress-meter-check.sh` | 通过 |
| 专项 acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh workflow-gate-stratification-check` | 通过 |
| 控制门传播回归 | `bash compass/tools/redcap-multi-session-acceptance.sh spec-check-propagates-control-gate-failures` | 通过 |
| 文件查阅字典 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过 |
| Prism 验收 | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过 |

### 5.2 人工验证项

- 无。本轮不需要 Norven 选择发布目标、凭据、许可证、删除策略或私密资产公开范围。

### 5.3 closeout runtime / receipt

| 项目 | 当前结果 |
| --- | --- |
| 执行承诺账本 | 正在收口前核对 |
| 棱镜验收 | Claude Code 与 Kimi 已完成；Gemini 作为 absent 槽位记录；Copilot 未调用 |
| closeout receipt | 尚未生成，需等待最终 closeout runtime 通过 |

### 5.4 完成等级（禁止混报）

| 层级 | 结论 | 说明 |
| --- | --- | --- |
| 已实现 | 是 | 门禁分级政策、样本、检查器与接入点已落地。 |
| 已自检 | 是 | 专项检查、acceptance、字典检查与 Prism acceptance 已通过；完整 diagnose 正在收口。 |
| 已独立验收 | 是 | Claude Code 与 Kimi 均无 blocker，相关建议已回填。 |
| 已正式完成 | 否 | 还需最终 `diagnose`、clean workspace E2E 和 closeout receipt 完成后才能改为“是”。 |

## 六、遗留问题与下一步

- 本轮不宣称 RedCap 已正式发布。
- 本轮不改变许可证、发布开关或 npm registry 状态。
- 本轮不做大规模历史资产迁移，也不删除历史证据。
- 本轮不是降低发布前安全标准，而是让不同风险等级的任务使用不同验证强度。

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
| --- | --- | --- |
| L-169 | 重型门禁要按风险触发，不能让轻量证据漂移制造回归循环 | 低风险报告/索引漂移不应反复触发发布级 E2E；但包面、runtime、安全和 closeout 仍必须 fail-closed。 |

### 7.2 流程改进建议

当一次任务因为验证成本过高而反复被打断时，不要简单降低所有检查强度；应先分清“轻量结果漂移”和“高风险公开面变化”，再把这个判断固化为机器检查。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
| --- | --- | --- | --- |
| RASG-024-risk-tier-gate | 本轮 RASG-024 | no-promote；已沉淀为 L-169，暂不晋升 public arsenal，因为它仍是 RedCap 内部控制面经验 | 本报告、`compass/knowledge/lessons/l-169.md`、Prism review 报告 |

## 八、附录

- 任务卡：`.dev-task.md`
- Prism 报告：`prism/reports/2026-05-21-rasg-024-workflow-gate-stratification.md`
- 工作流门禁策略：`references/workflow-gate-stratification-policy.json`
- 工作流门禁样本：`references/workflow-gate-stratification-samples.json`
