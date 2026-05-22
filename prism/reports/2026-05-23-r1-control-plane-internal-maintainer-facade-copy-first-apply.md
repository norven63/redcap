# P4-21 Prism 评审：internal-control-plane facade 小批次

## 控制面元数据

run_id: 20260523-r1-control-plane-internal-maintainer-facade-copy-first-apply
mode: explore
date: 2026-05-23
topic: R1 internal-control-plane maintainer facade copy-first apply
agents: claude-code, kimi; gemini not needed; copilot policy-suppressed
verdict: consensus-C-internal-control-plane-small-facade-batch

**运行 ID**：20260523-r1-control-plane-internal-maintainer-facade-copy-first-apply
**参与 Agent / quorum**：2 responded（Claude Code reviewer、Kimi challenger）；Gemini 未调用；Copilot 按 protected fallback 策略未调用。

## 结论

P4-21 应执行 C：用不超过 10 个内部维护 shell 入口做 `internal-control-plane` copy-first facade 小批次。

这条路线延续 P4-20 的裁决：下一刀回到 `internal-control-plane`，但不能一次性处理全部 111 个条目，也不能触碰发布、证据清理或 Layer A 产品边界。本轮选择 8 个内部维护 shell facade，只做镜像和委托，旧 `compass/tools` 继续是权威实现。

## 为什么不是其他路线

- A（public contract mirror）：本身可作为后续候选，但会偏离 P4-20 已选定的 `internal-control-plane` 路线。
- B（internal contract mirror）：范围可控，但仍属于另一层 contract mirror，不应在本轮替代 control-plane 小批次。
- D（只做预检）：已有 dry-run 与 P4-20 路线裁决，再做空预检会制造零进度切片。

## 仍然不能做什么

- 不能说 `internal-control-plane` blocker 已经解决。
- 不能说全部 111 个 internal-control-plane 条目都已 mirror。
- 不能删除、移动、替换或重定向旧 `compass/tools` 锚点。
- 不能修改 `prism/reports`、清理 `prism/runs` 原始证据。
- 不能裁决 Layer A 产品边界。
- 不能修改 npm 发布开关、许可证、registry、凭据或 package privacy。
- 不能说 RedCap 已经可以正式公开发布。

## 棱镜意见

| Agent | 建议 | 主要理由 |
| --- | --- | --- |
| Claude Code | C | P4-20 已裁决回到 internal-control-plane；小批次 facade 能产生真实 copy-first 证据，同时不越过人工硬门。 |
| Kimi | C | A/B 虽小但偏离路线，D 零进度；C 可用 5-10 个内部维护入口控制爆炸半径。 |
| Gemini | 未调用 | Claude Code 与 Kimi 已形成双路 quorum。 |
| Copilot | 策略抑制 | Copilot 是保护性兜底；Claude Code 与 Kimi 可用时不调用。 |

## 验收要求

- 新增 8 个 `internal/control-plane/tools` facade。
- 每个 facade 必须委托旧 `compass/tools` 权威脚本。
- P4-21 checker 必须验证 batch 大小、来源 dry-run 条目、旧锚点保留、禁止动作和 release blocker 仍 open。
- spec-check、diagnose、Prism acceptance、clean workspace E2E 与 closeout runtime 必须通过。

## 证据

- Apply manifest: `references/r1-control-plane-internal-maintainer-facade-copy-first-apply.json`
- Checker: `compass/tools/redcap-r1-control-plane-internal-maintainer-facade-copy-first-apply-check.sh`
- Task report: `compass/docs/task-reports/2026-05-23-r1-control-plane-internal-maintainer-facade-copy-first-apply.md`
- Claude Code raw: `prism/runs/20260523-r1-control-plane-internal-maintainer-facade-copy-first-apply/claude-code-review.txt`
- Kimi raw: `prism/runs/20260523-r1-control-plane-internal-maintainer-facade-copy-first-apply/kimi-review.txt`
- Registry: `prism/runs/20260523-r1-control-plane-internal-maintainer-facade-copy-first-apply/session-registry.yaml`
