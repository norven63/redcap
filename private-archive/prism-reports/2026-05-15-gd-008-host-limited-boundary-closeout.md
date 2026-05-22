# Prism 验收报告：GD-008 host-limited 边界收口

**日期**：2026-05-15
**run_id**：`20260515-gd008-host-limited-boundary-closeout`
**任务**：GD-008 host-limited boundary closeout
**结论**：pass-with-concerns

## 人类结论

Claude Code 和 Kimi 均认可：GD-008 不应继续作为“仓库内仍能实现但未实现”的开放治理债务。RedCap 已经完成可由仓库控制的部分：执行保障登记、host reliability 文档、Codex CLI / Codex.app 边界、evolution-grade baseline 和状态面展示。剩余的完整 reply-time veto 属于宿主是否提供 pre-reply/pre-send Hook 的物理能力边界。

## 必须带上的边界

- 可以把 GD-008 标为 `design-complete / done`，但 `done` 的意思是“host-limited 边界已被诚实建模”，不是“主 Agent live reply 已经可 100% 物理拦截”。
- `governance debt open=0` 不能被解释为所有保障都达到 G1；Codex.app interactive 和完整 reply-veto 仍必须保持 degraded / separately-unproven 口径。
- 必须新增 reactivation sentinel：未来若任一宿主声明并验证 repo-owned pre-reply/pre-send veto，应新开 host-adapter upgrade task，而不是重开 GD-008。

## 棱镜意见摘要

| 角色 | Agent | 结论 | blocker | 关键要求 |
|---|---|---|---|---|
| reviewer | Claude Code | pass-with-concerns | 无 | 增加 reactivation sentinel，避免 `done` 被误读成问题消失 |
| challenger | Kimi | pass-with-concerns | 无 | 更新 GD-008 文案，保留 future trigger，并确认状态面不把 open=0 误读成 full G1 |

## 本轮采纳动作

- 更新 `compass/knowledge/governance-debt-register.md` 中 GD-008 的状态与 resolution。
- 更新 `references/host-session-capability-matrix.json`，增加 `gd008_reactivation_sentinel` 与各宿主 `reply_veto_status`。
- 更新 `redcap-hook-contract-check.sh`，让 sentinel 成为诊断链可检查事实。

## 后续

本轮不进入 npm 发布。若未来 Codex.app、Claude、Gemini、Copilot 或其他宿主提供可验证的 pre-reply/pre-send Hook，应新开独立 host-adapter upgrade task。
