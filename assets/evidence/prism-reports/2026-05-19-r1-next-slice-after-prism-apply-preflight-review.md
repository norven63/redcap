# Prism Review: Next R1 Slice After Prism Apply Preflight

## 控制面元数据

run_id: 20260519-r1-next-slice-after-prism-apply-preflight
mode: review
date: 2026-05-19
topic: Next R1 slice after P4-5 Prism evidence apply preflight closeout
agents: claude-code, kimi; gemini auth-prompt-invalid; copilot policy-suppressed
verdict: weak-consensus-select-control-plane-runtime-public-support-copy-first

**运行 ID**：20260519-r1-next-slice-after-prism-apply-preflight
**Adjudicate verdict**：weak-consensus
**参与 Agent / quorum**：3 slots；2 responded（Claude Code reviewer、Kimi challenger）；1 absent（Gemini observer，本轮真实调用返回交互式登录提示，未形成有效 verdict）；N_quorum=2。Copilot 按当前保护性 fallback 策略未调用。

## 结论

Claude Code 建议下一步推进 `internal-control-plane batch-1 runtime-public-support copy-first apply`。Kimi 建议先做 `R2 public package surface analysis-only`，理由是物理 apply 风险更高。

裁决：采用 Claude Code 的方向，但把任务边界收紧为非破坏性的 runtime-public-support facade copy-first apply。理由是 R1 blockers 已经完成 preflight，继续只做 analysis-only 会延后发布前硬门的真实落地；而 batch-1 是 control-plane 三个批次中最小、最贴近 runtime/CLI 产品面的可执行切片，且旧 `compass/tools` 锚点保持权威，不删除、不移动、不关闭 blocker。

## 本轮允许推进的范围

- 为 batch-1 的 runtime-public-support 条目创建 `runtime/redcap-core/tools` 下的兼容 facade。
- 旧 `compass/tools` 路径继续保留且仍是权威实现。
- 新 facade 只转调旧实现，不复制 secret，不引入 release switch 变化。
- 新增 apply manifest、checker、acceptance 与任务报告。
- 更新 package surface snapshot、clean workspace E2E、Prism review 与 closeout receipt。

## 禁止越界

- 不移动、删除、重命名或替换旧 `compass/` / `references/` 锚点。
- 不执行 control-plane batch-2 或 batch-3。
- 不清理 Prism raw evidence，不运行 cleanup/prune apply。
- 不修改 Layer A / `loom`。
- 不修改 package privacy、license、registry、credentials 或发布开关。
- 不宣称 `internal-control-plane` blocker 已解决。
- 不宣称 RedCap 已 release-ready。

## 必要门禁

- facade 清单必须与 P4-4 batch-1 source map 对齐。
- 每个 facade 必须可解析且保持旧实现为权威。
- package safety、runtime manifest、clean workspace E2E、spec-check、diagnose、Prism acceptance 与 closeout receipt 必须通过。

## 证据

- Prompt: `prism/runs/20260519-r1-next-slice-after-prism-apply-preflight/prompt.md`
- Claude raw: `prism/runs/20260519-r1-next-slice-after-prism-apply-preflight/claude.raw.txt`
- Kimi raw: `prism/runs/20260519-r1-next-slice-after-prism-apply-preflight/kimi.raw.txt`
- Gemini raw: `prism/runs/20260519-r1-next-slice-after-prism-apply-preflight/gemini.raw.txt`
- Registry: `prism/runs/20260519-r1-next-slice-after-prism-apply-preflight/session-registry.yaml`
