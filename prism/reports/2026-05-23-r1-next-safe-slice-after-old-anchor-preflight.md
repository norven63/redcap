# P4-20 Prism 评审：下一安全切片选择

## 控制面元数据

run_id: 20260523-r1-next-safe-slice-after-old-anchor-preflight
mode: explore
date: 2026-05-23
topic: R1 next safe slice after old Prism report anchor preflight
agents: claude-code, kimi; gemini not needed; copilot policy-suppressed
verdict: weak-consensus-split-decision-cap-adjudicates-A

**运行 ID**：20260523-r1-next-safe-slice-after-old-anchor-preflight
**参与 Agent / quorum**：2 responded（Claude Code reviewer、Kimi challenger）；Gemini 未调用；Copilot 按 protected fallback 策略未调用。

## 结论

P4-20 已完成路线选择，但没有执行下一条路线本身。这不是正式发布，也不是发布 blocker 的完成声明。

棱镜出现了一个有价值的分歧：Claude Code 建议回到 `internal-control-plane`，因为它仍是正式发布前最大的工程 blocker；Kimi 建议先做旧报告入口别名/查询网关，因为它范围更小，也直接承接 P4-19 的遗留问题。Cap 最终裁决选择 Claude Code 的方向：下一刀推进 `internal-control-plane` 的非破坏性 support-copy-first 小切片。

这个裁决的理由是：P4-19 已经安全地把旧报告入口保留下来，并明确真实删除必须延期；如果继续围绕旧报告链路做局部治理，会延迟更大的发布 blocker。选择 `internal-control-plane` 并不允许大拆大改，只允许下一轮做可回滚、可机器检查、非破坏性的 support-copy-first 切片。

## 仍然不能做什么

- 不能说 `internal-control-plane` 已经解决。
- 不能说旧 `prism/reports` 锚点已经退休、删除、替换或重定向。
- 不能清理 `prism/runs` 原始证据。
- 不能裁决 Layer A 产品边界。
- 不能修改 npm 发布开关、许可证、registry、凭据或 package privacy。
- 不能说 RedCap 已经可以正式公开发布。

## 棱镜意见

| Agent | 建议 | 主要理由 |
| --- | --- | --- |
| Claude Code | A | `internal-control-plane` 是更大的发布 blocker，copy-first / support-copy-first 能做到非破坏性推进。 |
| Kimi | B | 旧报告入口别名/查询网关范围更小，能直接解除 P4-19 的一个未来退休前置条件。 |
| Gemini | 未调用 | Claude Code 与 Kimi 已形成双路 quorum；本轮是路线选择，不需要继续扩大资源消耗。 |
| Copilot | 策略抑制 | Copilot 是保护性兜底；Claude Code 与 Kimi 可用时不调用。 |

## 后续路线

下一条任务登记为 P4-21：`R1 internal-control-plane support-copy-first continuation after old-anchor route selection`。

P4-21 的目标不是“一次性解决 internal-control-plane”，而是选择其中一个最小可执行子集，做成非破坏性 support-copy-first 迁移或兼容支撑。旧报告别名/查询网关保留为后续候选；如果后续检查发现旧报告入口歧义开始阻塞发布准备，再切回 B。

## 证据

- Route manifest: `references/r1-next-safe-slice-after-old-anchor-preflight.json`
- Task report: `compass/docs/task-reports/2026-05-23-r1-next-safe-slice-after-old-anchor-preflight.md`
- Claude Code raw: `prism/runs/20260523-r1-next-safe-slice-after-old-anchor-preflight/claude-code-review.txt`
- Kimi raw: `prism/runs/20260523-r1-next-safe-slice-after-old-anchor-preflight/kimi-review.txt`
- Registry: `prism/runs/20260523-r1-next-safe-slice-after-old-anchor-preflight/session-registry.yaml`
