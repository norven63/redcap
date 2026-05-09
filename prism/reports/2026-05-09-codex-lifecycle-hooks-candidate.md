# Prism Report: Codex lifecycle hooks candidate

- run_id: `20260509-codex-lifecycle-hooks-candidate`
- mode: `acceptance-review`
- date: 2026-05-09
- agents: Claude Code + Kimi
- verdict: pass

## 结论

Claude Code 与 Kimi 都通过本轮审查：RedCap 已把 Codex 官方 lifecycle hooks 接成保守候选能力，没有把它冒充成完整宿主强保障。后续加固中，本机 Codex CLI 已完成 live marker E2E，证明 `codex exec` 下的 `SessionStart` 与 `Stop` 会物理触发；但 Codex.app 交互面、完整 reply-veto 与完整沙箱仍不能被宣称 ready。

## 共识边界

- Codex 当前只能声明为 CLI marker partial-ready / app interactive unverified，不能声明为 full parity 或完整 reply-veto。
- `SessionStart` 能作为复活与状态恢复候选入口；本机 CLI 物理触发已验证，Codex.app 交互面仍需单独验证。
- `Stop` 已有 JSON continuation 与 `stop_hook_active` 防循环处理，但它不是完整 SessionEnd，也不替代 receipt closeout。
- `PreToolUse` 能拦截明显高危动作，但只是护栏，不是完整沙箱。

## 风险说明

- Codex.app interactive live marker E2E 仍未执行；这会决定 Codex.app 是否能从 unverified 升级为 ready。
- `PermissionRequest`、`PostToolUse`、`UserPromptSubmit` 尚未接入；后续需要单独设计策略。
- 危险命令拦截是简单规则匹配，未来如要扩大安全边界，需要更强的策略层和更多回归样例。

## Follow-up live marker E2E review

- Claude Code follow-up verdict: pass。提醒：发布前仍要防止 package surface 继续膨胀，并继续用唯一信源检查防宿主配置分叉。
- Kimi follow-up verdict: pass。提醒：生产 `.codex/hooks.json` 不能注入 `REDCAP_CODEX_HOOK_E2E_PROBE`；Stop 的 `stop_hook_active` 循环保护需要单独 acceptance。
- 处理结果：两个提醒均已转为机器检查。`redcap-codex-hooks-check.sh` 会拒绝生产 hook 配置携带 E2E probe env，`codex-hooks-candidate-check` 会单独验证 `stop_hook_active=true` 时安全放行。

## 证据

- Raw outputs: `prism/runs/20260509-codex-lifecycle-hooks-candidate/collect/*-raw/*.raw.txt`
- Parsed verdicts: `prism/runs/20260509-codex-lifecycle-hooks-candidate/collect/*/parsed.json`
- Acceptance binding: `prism/runs/20260509-codex-lifecycle-hooks-candidate/artifacts/acceptance-binding.json`
- Live marker evidence: `references/codex-live-marker-e2e.json`
