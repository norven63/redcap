# Prism Review：P4-9 发布前下一小切片选择

## 控制面元数据

run_id: 20260521-r1-next-slice-after-prism-support
mode: review
date: 2026-05-21
topic: Next R1 slice after P4-8 Prism package-visible support closeout
agents: claude-code, kimi; gemini unavailable; copilot policy-suppressed
verdict: consensus-select-prism-report-archive-copy-first-preflight

**运行 ID**：20260521-r1-next-slice-after-prism-support
**Adjudicate verdict**：consensus-select-prism-report-archive-copy-first-preflight
**参与 Agent / quorum**：3 slots；2 responded（Claude Code reviewer、Kimi challenger）；1 absent（Gemini observer，本工作区当前不可稳定调用）；N_quorum=2。Copilot 按 protected fallback 策略未调用。

## 结论

Claude Code 与 Kimi 独立评审后形成一致意见：下一条应进入 `Prism tracked report archive copy-first / report-index migration preflight`。

人话解释：P4-8 已经把 Prism 的运行支撑入口架好，下一步不要急着清理运行证据，也不要跳到更大的控制面 batch-2；先把“Prism 报告如何安全归档、索引如何迁移、旧报告锚点如何继续可访问”证明清楚。

## 为什么选择这条

- 它是剩余 Prism 任务里最小、最不破坏的一刀。
- 它不需要 Norven 做产品边界或删除证据的人工决策。
- 它为未来处理 `prism/runs` 本地运行证据建立前置证明。
- 它比控制面 batch-2 更小，避免一次进入 53 个候选的大批量变更。
- 它不触碰 Layer A / `loom` 的产品范围裁决。

## 没有选择的候选

| 候选 | 结论 | 原因 |
| --- | --- | --- |
| Prism local run evidence cleanup | 暂不推进 | 涉及 raw evidence 清理或剪枝，若不可逆必须人工批准。 |
| internal control-plane batch-2 | 暂不推进 | 候选数量更大，需要后续单独拆小批次。 |
| Layer A product boundary | 不由本轮裁决 | 这是 Norven 保留产品决策。 |

## 下一切片必须守住的边界

- 不删除、移动、替换旧 `prism/reports` 锚点。
- 不删除、移动、清理、剪枝 `prism/runs` raw evidence。
- 不修改发布开关、许可证、registry、凭据或 package privacy。
- 不宣称 `prism-layer-and-evidence` blocker 已关闭。
- 不宣称 RedCap 已 release-ready。

## 下一切片建议验收

- report index migration proof。
- archive-check pass。
- old report anchors remain resolvable。
- Prism acceptance binding。
- Claude Code 与 Kimi 独立评审。
- spec-check 与 diagnose。
- closeout receipt。

## 证据

- Prompt: `prism/runs/20260521-r1-next-slice-after-prism-support/prompt.md`
- Claude raw: `prism/runs/20260521-r1-next-slice-after-prism-support/claude.raw.txt`
- Kimi raw: `prism/runs/20260521-r1-next-slice-after-prism-support/kimi.raw.txt`
- Registry: `prism/runs/20260521-r1-next-slice-after-prism-support/session-registry.yaml`
- Decision asset: `references/r1-next-slice-after-prism-support.json`
