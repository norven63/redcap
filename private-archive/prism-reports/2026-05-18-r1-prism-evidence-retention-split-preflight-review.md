# Prism Review: R1 Prism Evidence Retention Split Preflight

## 控制面元数据

run_id: 20260518-r1-prism-evidence-retention-split-preflight
mode: review
date: 2026-05-18
topic: Formal release R1 Prism layer and evidence retention split preflight
agents: claude-code, kimi; gemini absent
verdict: pass-with-concerns

**运行 ID**：20260518-r1-prism-evidence-retention-split-preflight
**Adjudicate verdict**：weak-consensus
**参与 Agent / quorum**：3 slots；2 responded/followed_up（Claude Code reviewer、Kimi challenger）；1 absent（Gemini observer，本轮未调用）；N_quorum=2。

## 结论

Claude Code 与 Kimi 均确认：P4-2q 严格保持 preflight / analysis-only 边界，没有把 Prism 层物理拆分、证据清理、R1 关闭或 public release ready 提前说成完成。两路都没有提出阻塞性问题。

## 共同确认

- `references/r1-prism-evidence-retention-split-preflight.json` 保持 `is_prism_layer_physically_split=false`、`is_prism_evidence_physically_cleaned=false`、`is_r1_closed=false`、`is_public_release_ready=false`，并继续把 `prism-layer-and-evidence` 标为 release blocker。
- 包候选统计由 `redcap-runtime-package-manifest.sh` 实时复验；Prism package candidates 只包含工具与 README，不包含 `prism/reports` 或 `prism/runs`。
- 消费者矩阵覆盖 package manifest、Prism acceptance/closeout、报告归档、provider routing/availability、runs lifecycle status 五类主要消费者。
- future split gate 明确区分物理拆分前置条件和证据清理前置条件；证据清理必须另走 inventory dry-run、inactive/unreferenced proof、Norven 显式批准、回滚/保全方案与归档检查。
- spec-check、diagnose、acceptance 与 formal release readiness plan 都已接入新检查，能够 fail-closed 拒绝把预检冒充 physical split、evidence cleanup 或 release-ready。

## concerns 与处理

- Kimi 指出 `references/backlogs/framework-upgrade.json` 的 `current_focus` 仍停留在 P4-2p。本轮已修复为 P4-2q，并重新同步人类说明 spec。
- Kimi 指出全局 spec-check 当时因迁移锚点过期呈红色。本轮已修复 5 月 4 日报告锚点、刷新 docs catalog、cold archive inventory 与 legacy asset snapshot。
- Claude Code 指出本次 Prism verdict 必须写入 `prism/reports/` 并更新 `index.yaml`。本报告即为 tracked Prism report，后续 acceptance binding 会把本报告绑定回 `.dev-task.md`。

## 风险边界

- 不得把本轮外推为 `prism` 已经物理迁移或可公开发布。
- 不得把本轮外推为 `prism/runs` 已经清理、可清理或允许批量删除。
- 不得把本轮外推为 R1 cleanup closed、public-release-ready、license 已选、发布开关已开或 registry release 可执行。
- Claude Code raw 输出尾部出现宿主 SessionEnd hook warning，但 follow-up JSON verdict 已完整返回；该 warning 不影响本轮 Prism verdict。

## 证据

- Prompt: `prism/runs/20260518-r1-prism-evidence-retention-split-preflight/prompt.md`
- Registry: `prism/runs/20260518-r1-prism-evidence-retention-split-preflight/session-registry.yaml`
- Claude raw: `prism/runs/20260518-r1-prism-evidence-retention-split-preflight/collect/claude-code-reviewer.raw.md`
- Claude follow-up JSON: `prism/runs/20260518-r1-prism-evidence-retention-split-preflight/collect/claude-code-reviewer.followup.raw.md`
- Kimi raw: `prism/runs/20260518-r1-prism-evidence-retention-split-preflight/collect/kimi-challenger.raw.md`
