# Prism Report: Runtime 最小兼容物理布局落地

- run_id: `20260508-runtime-layout-minimum-compatible-apply`
- mode: `planning-review`
- date: 2026-05-08
- agents: Claude Code + Kimi
- verdict: pass-with-warning

## 结论

Claude Code 与 Kimi 都认可本轮应处理 AI 可推进的 runtime layout blocker，而不是进入 npm 发布、license 决策或物理清理。Kimi 给出 `warn`，原因是 package surface、pre-release review facts 与 split manifest 之间强耦合，必须同步更新。

## 共识边界

- 可以新增 `runtime/redcap-core/**` 与 `runtime/host-adapters/**` 最小布局。
- 根 `bin/redcap`、`revive-cap.sh`、`closeout-cap.sh` 必须保持兼容入口。
- 不移动 `compass/tools` 或 `prism/tools`。
- 不修改 `private=true`、`UNLICENSED`、`publish_allowed=false`。
- 不声明 full runtime split 或 public release ready。

## 已吸收动作

- Runtime wrapper 采用委托根入口的方式，避免生成不可运行的死副本。
- Package candidate count 从 234 同步到 239。
- P4-2a runtime blocker 降级为 should-fix；发布开关与 license 仍是 release blocker。

## 证据

- Raw outputs: `prism/runs/20260508-runtime-layout-minimum-compatible-apply/collect/*`
- Parsed verdicts: `prism/runs/20260508-runtime-layout-minimum-compatible-apply/collect/*/parsed.json`
- Acceptance binding: `prism/runs/20260508-runtime-layout-minimum-compatible-apply/artifacts/acceptance-binding.json`
