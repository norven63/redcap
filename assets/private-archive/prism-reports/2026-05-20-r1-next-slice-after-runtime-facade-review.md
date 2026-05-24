# Prism Review: Next R1 Slice After Runtime Facade

## 控制面元数据

run_id: 20260520-r1-next-slice-after-runtime-facade
mode: review
date: 2026-05-20
topic: Next R1 slice after P4-6 runtime facade closeout
agents: claude-code, kimi; gemini availability-error; copilot policy-suppressed
verdict: weak-consensus-select-prism-package-visible-support

**运行 ID**：20260520-r1-next-slice-after-runtime-facade
**Adjudicate verdict**：weak-consensus
**参与 Agent / quorum**：3 slots；2 responded（Claude Code reviewer、Kimi challenger）；1 absent（Gemini observer，可用性嗅探返回 Operation not permitted）；N_quorum=2。Copilot 按保护性 fallback 策略未调用。

## 结论

下一条 RedCap 父任务线建议进入：

`prism-layer-and-evidence batch-1: package-visible Prism support and provider-routing contract`

这是 P4-6 之后最适合自主推进的小切片。它只有 8 个候选，能削减 `prism-layer-and-evidence` 这条 R1 发布前债务，而且不需要删除、移动、清理证据，也不需要 Norven 裁决 Layer A 产品范围。

## 为什么没有选择控制面 batch-2

Claude Code 建议继续推进 `internal-control-plane batch-2`，理由是它最直接延续 P4-6，并继续削减 `internal-control-plane` blocker。这个判断成立，但 batch-2 有 53 个候选，下一步更适合先拆成更小的实施 tranche，避免一次性进入大批量分类和 import-map 风险。

本轮主裁决采用更保守路线：先做 Prism batch-1 这个小切片。控制面 batch-2 继续保留为后续候选，不能因为这次未选中而从路线中消失。

## 本轮允许推进的范围

- 为 package-visible Prism support 建立 copy-first / alias-first 入口。
- 审查 provider routing contract，确保包面调用不绕过既有 Prism 策略。
- 产出 package surface / runtime manifest diff 证据。
- 保持旧 `prism/` 锚点可解析、可考古。
- 运行 package safety、clean workspace E2E、Prism review 与 closeout receipt。

## 禁止越界

- 不删除、移动、重命名、替换旧 `prism/` 锚点。
- 不清理 `prism/runs`，不执行 cleanup apply 或 prune-local apply。
- 不修改 release switch、package privacy、license、registry 或凭据。
- 不替 Norven 裁决 Layer A / `loom` 产品范围。
- 不宣称 `prism-layer-and-evidence` blocker 已完全解决。
- 不宣称 RedCap 已 release-ready。

## 必要门禁

- runtime package manifest diff。
- provider routing review。
- package safety proof。
- clean workspace E2E。
- Prism implementation review。
- spec-check / diagnose。
- closeout receipt。

## 证据

- Prompt: `prism/runs/20260520-r1-next-slice-after-runtime-facade/prompt.md`
- Claude raw: `prism/runs/20260520-r1-next-slice-after-runtime-facade/claude.raw.txt`
- Kimi raw: `prism/runs/20260520-r1-next-slice-after-runtime-facade/kimi.raw.txt`
- Gemini raw: `prism/runs/20260520-r1-next-slice-after-runtime-facade/gemini.raw.txt`
- Registry: `prism/runs/20260520-r1-next-slice-after-runtime-facade/session-registry.yaml`
