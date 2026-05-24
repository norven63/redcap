# Prism Review：P4-14 发布前下一小切片选择

## 控制面元数据

run_id: 20260521-r1-next-slice-after-prism-report-archive-apply-readiness
mode: review
date: 2026-05-21
topic: Next R1 slice after P4-13 Prism report archive apply readiness closeout
agents: claude-code, kimi; gemini unavailable; copilot policy-suppressed
verdict: split-decision-cap-adjudicates-conservative-B

**运行 ID**：20260521-r1-next-slice-after-prism-report-archive-apply-readiness
**Adjudicate verdict**：split-decision-cap-adjudicates-conservative-B
**参与 Agent / quorum**：2 responded（Claude Code reviewer、Kimi challenger）；Gemini 本轮 Operation not permitted；Copilot 按 protected fallback 策略未调用。

## 结论

Claude Code 和 Kimi 没有形成同选项共识，但都没有报告 blocker。

Claude Code 建议下一步进入 **Prism report archive live copy-first apply**，理由是 P4-12 plan 与 P4-13 rehearsal 已经铺好了复制、checksum、包面排除和回滚基础。Kimi 建议先做 **Prism report archive churn/freeze guard**，理由是每新增一份正式 Prism report 都会让 P4-12/P4-13 的 report_count 和 hash 快照过期，直接 live apply 前应先把这个 churn 风险变成可执行策略。

Cap 裁决选择 Kimi 的更保守方案：下一步先做 **churn/freeze guard**。人话解释：先解决“报告集合一直变，计划快照一直过期”的问题，再进入真实 copy-first apply。这样不会创建真实归档文件，也不会删除旧锚点或清理 raw evidence。

## 为什么选择 churn/freeze guard

- 它更小：只处理策略、快照刷新和检查规则，不创建 `private-archive/prism-reports` 下的真实文件。
- 它直接解决本轮已经暴露的风险：新增 P4-14 Prism 报告本身就会让 P4-12/P4-13 的报告集合从 54 变为 55。
- 它不需要 Norven 人工决策：不碰许可证、registry、secret、Layer A 产品边界、raw evidence cleanup 或旧锚点退休。
- 它让后续 live apply 更稳：未来 copy-first apply 可以基于明确的 freeze window 或 auto-refresh 规则，而不是每次靠人工发现 hash 漂移。

## 没有选择的候选

| 候选 | 结论 | 原因 |
| --- | --- | --- |
| Prism report archive live copy-first apply | 暂不作为下一步 | 方向合理，但会创建真实归档副本；先补 churn/freeze guard 更安全。 |
| internal control-plane batch-2 | 暂不推进 | 规模更大，且会切离当前 Prism report archive 主线。 |
| internal control-plane batch-3 | 暂不推进 | 规模最大，不符合“最小安全小切片”。 |
| Prism raw run evidence cleanup | 不自主推进 | 涉及原始运行证据，若清理或剪枝必须先做保存证明并按需人工批准。 |
| Layer A product boundary | 不由本轮裁决 | 这是 Norven 保留的产品范围决策。 |

## 下一切片必须守住的边界

- 不创建 `private-archive/prism-reports` 下任何真实归档文件。
- 不复制、移动、删除、重命名或替换 `prism/reports` 下任何旧锚点。
- 不删除、移动或清理 `prism/runs` raw evidence。
- 不修改发布开关、许可证、registry、凭据或 package privacy。
- 不宣称 `prism-layer-and-evidence` blocker 已关闭。
- 不宣称 RedCap 已 release-ready。

## 下一切片建议验收

- machine-readable churn/freeze policy。
- 明确 freeze window / planned formal report addition / unexpected drift 的区别。
- checker 或脚本能区分正常新增报告与异常漂移。
- P4-12/P4-13 快照刷新到当前 report set。
- Claude Code 与 Kimi 独立评审。
- spec-check、diagnose、clean workspace E2E。
- closeout receipt。

## 证据

- Prompt: `prism/runs/20260521-r1-next-slice-after-prism-report-archive-apply-readiness/prompt.md`
- Claude raw: `prism/runs/20260521-r1-next-slice-after-prism-report-archive-apply-readiness/collect/reviewer/claude.raw.txt`
- Kimi raw: `prism/runs/20260521-r1-next-slice-after-prism-report-archive-apply-readiness/collect/challenger/kimi.raw.txt`
- Registry: `prism/runs/20260521-r1-next-slice-after-prism-report-archive-apply-readiness/session-registry.yaml`
- Decision asset: `references/r1-next-slice-after-prism-report-archive-apply-readiness.json`
