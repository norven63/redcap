# Prism Report: Codex lifecycle hooks candidate

- run_id: `20260509-codex-lifecycle-hooks-candidate`
- mode: `acceptance-review`
- date: 2026-05-09
- agents: Claude Code + Kimi
- verdict: pass

## 结论

Claude Code 与 Kimi 都通过本轮审查：RedCap 已把 Codex 官方 lifecycle hooks 接成保守候选能力，没有把它冒充成完整宿主强保障。两路评审都认可当前可以进入 closeout，但要求继续保留 “candidate / degraded” 口径，直到真实 trusted Codex 会话完成 marker E2E。

## 共识边界

- Codex 当前只能声明为 lifecycle hooks candidate，不能声明为 hook-ready、full parity 或完整 reply-veto。
- `SessionStart` 能作为复活与状态恢复候选入口，但 project trust 和 feature flag 是否真实生效仍需物理验证。
- `Stop` 已有 JSON continuation 与 `stop_hook_active` 防循环处理，但它不是完整 SessionEnd，也不替代 receipt closeout。
- `PreToolUse` 能拦截明显高危动作，但只是护栏，不是完整沙箱。

## 风险说明

- 真实 Codex project trust / live marker E2E 仍未执行；这会决定 Codex 能否从 candidate 升级为 ready。
- `PermissionRequest`、`PostToolUse`、`UserPromptSubmit` 尚未接入；后续需要单独设计策略。
- 危险命令拦截是简单规则匹配，未来如要扩大安全边界，需要更强的策略层和更多回归样例。

## 证据

- Raw outputs: `prism/runs/20260509-codex-lifecycle-hooks-candidate/collect/*-raw/*.raw.txt`
- Parsed verdicts: `prism/runs/20260509-codex-lifecycle-hooks-candidate/collect/*/parsed.json`
- Acceptance binding: `prism/runs/20260509-codex-lifecycle-hooks-candidate/artifacts/acceptance-binding.json`
