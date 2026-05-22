# Prism Review：P4-11 发布前下一小切片选择

## 控制面元数据

run_id: 20260521-r1-next-slice-after-prism-report-archive-preflight
mode: review
date: 2026-05-21
topic: Next R1 slice after P4-10 Prism report archive preflight closeout
agents: claude-code, kimi; gemini unavailable; copilot policy-suppressed
verdict: consensus-select-prism-report-archive-planning-bridge

**运行 ID**：20260521-r1-next-slice-after-prism-report-archive-preflight
**Adjudicate verdict**：consensus-select-prism-report-archive-planning-bridge
**参与 Agent / quorum**：2 responded（Claude Code reviewer、Kimi challenger）；Gemini 本轮可用性不稳定未加入；Copilot 按 protected fallback 策略未调用。

## 结论

Claude Code 与 Kimi 独立评审后形成一致意见：P4-10 之后，不应直接做物理迁移、证据清理或更大的控制面 batch。下一步应进入 **Prism 报告归档的 copy-first / alias-first 迁移规划桥**。

人话解释：先把“哪些报告将来要复制到哪里、旧路径如何继续可访问、出错如何回滚、未来 apply 前要验什么”写成可机器检查的计划。现在仍不搬文件、不删文件、不清理 `prism/runs`。

## 为什么选择这条

- 它直接续接 P4-10，避免上下文重新跳到更大范围。
- 它足够小：只做 manifest、alias 草案、回滚和验证清单。
- 它是非破坏性的：不复制、不移动、不删除任何报告或 raw evidence。
- 它不需要 Norven 做发布、许可证、registry、Layer A 产品边界或证据清理决策。
- 它为未来真正做报告归档迁移建立前置证明，但不会把规划冒充成迁移完成。

## 没有选择的候选

| 候选 | 结论 | 原因 |
| --- | --- | --- |
| 直接 report archive apply | 暂不推进 | P4-10 明确仍是 preflight，当前不允许直接物理复制、移动或删除。 |
| internal control-plane batch-2 | 暂不推进 | 规模更大，涉及更多控制面契约和消费者，适合后续再拆小。 |
| internal control-plane batch-3 | 暂不推进 | 规模最大，不适合作为 P4-10 后的下一小步。 |
| Prism raw run evidence cleanup | 不自主推进 | 涉及原始运行证据，若清理或剪枝必须先做保存证明并按需人工批准。 |
| Layer A product boundary | 不由本轮裁决 | 这是 Norven 保留的产品范围决策。 |

## 下一切片必须守住的边界

- 只做 planning / manifest / alias mapping，不执行任何复制、移动、删除、重命名。
- 不修改 `prism/reports` 旧锚点，不退休旧路径。
- 不清理、不移动、不剪枝 `prism/runs` raw evidence。
- 不修改发布开关、许可证、registry、凭据或 package privacy。
- 不宣称 `prism-layer-and-evidence` blocker 已关闭。
- 不宣称 RedCap 已 release-ready。

## 下一切片建议验收

- plan-only migration manifest。
- old-anchor resolvability / alias draft。
- rollback plan。
- archive-check proof contract。
- Claude Code 与 Kimi 独立评审。
- spec-check 与 diagnose。
- closeout receipt。

## 证据

- Prompt: `prism/runs/20260521-r1-next-slice-after-prism-report-archive-preflight/prompt.md`
- Claude raw: `prism/runs/20260521-r1-next-slice-after-prism-report-archive-preflight/collect/reviewer/claude.raw.txt`
- Kimi raw: `prism/runs/20260521-r1-next-slice-after-prism-report-archive-preflight/collect/challenger/kimi.raw.txt`
- Registry: `prism/runs/20260521-r1-next-slice-after-prism-report-archive-preflight/session-registry.yaml`
- Decision asset: `references/r1-next-slice-after-prism-report-archive-preflight.json`

## 备注

Kimi 的 raw 输出中误把 JSON 的 `provider` 写成 `claude-code`。本轮按调用路径、运行目录和 `session-registry.yaml` 归一化为 Kimi 结论；原始输出保留不改。
