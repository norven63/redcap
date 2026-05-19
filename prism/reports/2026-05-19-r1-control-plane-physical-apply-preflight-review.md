# Prism Review: R1 Control-Plane Physical Apply Preflight

## 控制面元数据

run_id: 20260519-r1-control-plane-physical-apply-preflight
mode: review
date: 2026-05-19
topic: R1 control-plane physical apply preflight implementation review
agents: claude-code, kimi; gemini absent-not-needed; copilot policy-suppressed
verdict: consensus-pass

**运行 ID**：20260519-r1-control-plane-physical-apply-preflight
**Adjudicate verdict**：consensus
**参与 Agent / quorum**：3 slots；2 responded（Claude Code reviewer、Kimi challenger）；1 absent（Gemini observer，本轮因两路 distinct-family pass 已满足验收未调用）；N_quorum=2。Copilot 按当前降级策略未调用。

## 结论

Claude Code 与 Kimi 均给出 `pass`，没有 P0/P1 blocker。P4-4 可以进入提交、clean workspace E2E 刷新和 closeout 流程。

安全可声明的结论只有一条：`internal-control-plane` 未来 copy-first / alias-first apply 已有机器可检查的 preflight、旧锚点保留策略、回滚门禁和验证计划。

## 共同确认

- 该实现没有复制、移动、删除、重命名或替换旧 `compass/` / `references/` 锚点。
- apply preflight 对 source hash stale、source count stale、delete/move/rename/old-anchor replacement、release switch change、blocker closure 都保持 fail-closed。
- 新增两个 checker 脚本和一个 manifest 后，package candidate count 从 208 同步为 211，control-plane candidate count 从 184 同步为 187；该变化合理且已同步到相关快照。
- `redcap-spec-check` / `diagnose` 当前剩余失败来自 stale clean workspace E2E 结果；这是提交后必须刷新的 closeout 前置项，不是本轮实现 blocker。

## closeout 前必须完成

- 重新运行 clean workspace E2E，并更新 `references/clean-workspace-install-e2e.json`。
- 核对 `.dev-task.md` 完成标准与执行承诺账本。
- 生成 closeout receipt 后，才允许声明 P4-4 正式完成。

## 风险边界

- 不得说 control-plane 已物理拆分。
- 不得说旧 `compass/` / `references/` 锚点已迁移、删除或替换。
- 不得说 `internal-control-plane` blocker 已关闭。
- 不得说 RedCap 已 release-ready。
- 不得执行或暗示允许 registry publish、license decision、release switch change 或 destructive cleanup。

## 证据

- Prompt: `prism/runs/20260519-r1-control-plane-physical-apply-preflight/prompt.md`
- Claude raw: `prism/runs/20260519-r1-control-plane-physical-apply-preflight/claude.raw.txt`
- Kimi raw: `prism/runs/20260519-r1-control-plane-physical-apply-preflight/kimi.raw.txt`
- Registry: `prism/runs/20260519-r1-control-plane-physical-apply-preflight/session-registry.yaml`
