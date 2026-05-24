# Prism Report: Codex live marker E2E hardening

- run_id: `20260509-codex-live-marker-e2e-hardening`
- mode: `acceptance-review`
- date: 2026-05-09
- agents: Claude Code + Kimi
- verdict: pass

## 结论

Claude Code 与 Kimi 对当前未提交 diff 重新验收，结论均为 pass，无 blocker。本轮可以收口为“Codex CLI live marker partial-ready”：本机 `codex exec` 已证明 `SessionStart` 与 `Stop` 会物理触发；但 Codex.app 交互面、完整 reply-veto、完整安全沙箱仍然不在本轮声明范围内。

## 共识边界

- Hook 唯一信源成立：`.codex/hooks.json` 只做事件适配，业务规则保留在 RedCap-native wrapper 与检查脚本中。
- 生产 hook 配置不得携带 `REDCAP_CODEX_HOOK_E2E_PROBE`，probe 只能由 live marker E2E runner 注入。
- `stop_hook_active=true` 的 Stop 循环保护已被 acceptance 单独覆盖，避免收尾 hook 自己造成递归阻塞。
- 新增 live marker 脚本与清洗证据必须随本轮变更一起提交，否则干净 checkout 上的 readiness/spec-check 会断裂。

## 非阻塞风险

- Codex.app interactive live marker E2E 仍需另做，不能把 CLI 证据外推到 App。
- `PreToolUse` 仍是高危命令护栏，不是完整命令安全沙箱。
- package surface 从 246 到 248，属于已登记的发布前瘦身/产品化治理风险，不阻塞本轮 hook 加固。

## 证据

- Parsed verdicts: `prism/runs/20260509-codex-live-marker-e2e-hardening/collect/reviewer/parsed.json`, `prism/runs/20260509-codex-live-marker-e2e-hardening/collect/challenger/parsed.json`
- Acceptance binding: `prism/runs/20260509-codex-live-marker-e2e-hardening/artifacts/acceptance-binding.json`
- Live marker evidence: `references/codex-live-marker-e2e.json`
