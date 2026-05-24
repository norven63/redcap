# Prism Review: Evolution Harvest Signal Gate

**运行 ID**：20260517-evolution-harvest-signal-gate-review
**日期**：2026-05-17
**模式**：review
**参与 Agent**：Kimi（reviewer）、Claude Code（challenger）
**结论**：consensus pass

## 结论

两路评审均认为本轮补丁已经从“只检查已登记候选”前移到“先发现高价值信号，再强制候选判断”。这补的是经验沉淀链路第一步：发现与候选化。

## 共同确认

- `references/evolution-harvest-signal-policy.json` 定义了高价值信号和 fail-closed 边界。
- `redcap-evolution-harvest-check.py` 会在 review、bugfix、release、安全、用户纠偏、测试失败、递归/进程风暴等信号出现时要求报告 `7.3 Evolution Factory 候选处理`。
- `evolution-candidate-check --strict` 只负责已登记候选池，不再被冒充为“发现能力已经生效”。
- release-readiness 计划、授权矩阵、handoff 和 E2E 矩阵都已引用 Evolution harvest signal gate。

## 评审中发现并已处理

- Kimi 指出 shell wrapper 注释仍停留在 governance 旧口径；已改为 high-value signal tasks。
- Kimi 与 Claude Code 都指出 `deferred-with-owner` 不应空壳通过；已补 owner / trigger 校验和 acceptance。
- Claude Code 要求验证 closeout runtime 链路；已运行 `layerb-closeout-runtime-evolution-harvest-blocks` acceptance，通过。

## 剩余风险

- 关键词方案仍可能误杀低价值文本；当前选择 fail-closed，误杀代价是多写候选判断理由。
- 如果任务作者完全避开高价值关键词，仍可能漏杀；已补 `bugfix_tranche`、`release_tranche`、`security_tranche`、`privacy_tranche` 等显式元数据入口，后续 PM Gate 可继续强化声明纪律。

## Verdict

`pass`。无必须阻断提交的 blocker。
