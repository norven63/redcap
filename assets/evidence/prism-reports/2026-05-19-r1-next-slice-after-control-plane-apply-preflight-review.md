# Prism Review: Next R1 Slice After Control-Plane Apply Preflight

## 控制面元数据

run_id: 20260519-r1-next-slice-after-control-plane-apply-preflight
mode: review
date: 2026-05-19
topic: Next R1 slice after P4-4 control-plane apply preflight closeout
agents: claude-code, kimi; gemini auth-prompt-invalid; copilot policy-suppressed
verdict: weak-consensus-select-prism-evidence-apply-preflight

**运行 ID**：20260519-r1-next-slice-after-control-plane-apply-preflight
**Adjudicate verdict**：weak-consensus
**参与 Agent / quorum**：3 slots；2 responded（Claude Code reviewer、Kimi challenger）；1 absent（Gemini observer，本轮真实调用返回交互式登录提示，未形成有效 verdict）；N_quorum=2。Copilot 按当前保护性 fallback 策略未调用。

## 结论

Claude Code 建议直接进入 `control-plane` 第一批 copy-first apply；Kimi 建议先做 `prism-layer-and-evidence` 的 apply preflight。裁决采用 Kimi 的更保守路线：先做 `redcap-r1-prism-evidence-retention-apply-preflight`。

原因很直接：control-plane batch-1 会复制一批真实文件，虽然是 copy-first，但变更面更大；Prism evidence apply preflight 只补“未来动手前必须通过的护栏”，不移动、不删除、不清理证据，更适合作为 P4-4 后的下一小切片。

## 本轮允许推进的范围

- 新增 Prism evidence apply preflight manifest。
- 绑定 P4-3e dry-run 真相源，防止过期 dry-run 被复用。
- 增加 checker、acceptance、spec-check、diagnose 与 release-readiness plan 接线。
- 完成 Prism implementation review、closeout receipt 与 clean workspace E2E。

## 禁止越界

- 不移动、删除、重命名或清理任何 `prism/` 文件或证据。
- 不运行 `prism/runs` cleanup 或 prune 的真实 apply。
- 不修改 release switch、package privacy、license、registry 或凭据。
- 不修改 Layer A / `loom`。
- 不执行 control-plane copy-first apply。
- 不宣称 `prism-layer-and-evidence` blocker 已解决。
- 不宣称 RedCap 已 release-ready。

## 必要门禁

- apply preflight 必须保持 no-apply、no-cleanup、no-release。
- source hash / source counts 必须能发现 stale dry-run。
- old anchors 必须继续保留且可考古。
- `spec-check`、`diagnose`、targeted acceptance、clean workspace E2E、Prism review 与 closeout receipt 必须全部通过。

## 证据

- Prompt: `prism/runs/20260519-r1-next-slice-after-control-plane-apply-preflight/prompt.md`
- Claude raw: `prism/runs/20260519-r1-next-slice-after-control-plane-apply-preflight/claude.raw.txt`
- Kimi raw: `prism/runs/20260519-r1-next-slice-after-control-plane-apply-preflight/kimi.raw.txt`
- Gemini raw: `prism/runs/20260519-r1-next-slice-after-control-plane-apply-preflight/gemini.raw.txt`
- Registry: `prism/runs/20260519-r1-next-slice-after-control-plane-apply-preflight/session-registry.yaml`
