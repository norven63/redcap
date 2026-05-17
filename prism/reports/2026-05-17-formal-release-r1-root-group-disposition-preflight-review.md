# Prism Review: Formal Release R1 Root Group Disposition Preflight

## 控制面元数据

run_id: 20260517-formal-release-r1-root-group-disposition-preflight
mode: review
date: 2026-05-17
topic: Formal release R1 deferred root group disposition preflight
agents: claude-code, kimi; gemini absent
verdict: pass

**运行 ID**：20260517-formal-release-r1-root-group-disposition-preflight
**Adjudicate verdict**：consensus
**参与 Agent / quorum**：3 slots；2 responded（Claude Code reviewer、Kimi challenger）；1 absent（Gemini observer，availability probe unavailable）；N_quorum=2。

## 结论

Claude Code 与 Kimi 均通过复审。两条评审都确认：本轮只是 R1 发布前处置预检，不是发布授权，也不是 R1 历史资产清理关闭。

## 共同确认

- 4 个允许处置类型严格来自 `references/historical-asset-physical-cleanup-release-gate.json`，没有新增第五种“看似可接受”的灰色口径。
- `internal-control-plane`、`prism-layer-and-evidence`、`internal-layer-a` 仍然是 release blockers。
- `workspace-state` 只作为本地状态处理：它不进入包候选集，并由 `.npmignore` 明确排除。
- `formal-release-readiness-plan` 只把这份预检当作 blocker-aware input，不把它当作 release-safe certificate。
- acceptance 已覆盖“伪造第五种 disposition 会被拒绝”的回归。

## 风险边界

- 不得把本轮外推为 R1 cleanup closed。
- 不得把本轮外推为 public-release-ready。
- 不得把本轮外推为已经执行物理迁移、删除、许可证选择或发布开关变更。
- Claude Code raw 输出尾部出现宿主 SessionEnd hook warning，但评审 JSON 已完整返回；该 warning 不影响本轮 Prism verdict。

## 证据

- Prompt: `prism/runs/20260517-formal-release-r1-root-group-disposition-preflight/prompt.md`
- Registry: `prism/runs/20260517-formal-release-r1-root-group-disposition-preflight/session-registry.yaml`
- Claude raw: `prism/runs/20260517-formal-release-r1-root-group-disposition-preflight/collect/reviewer/raw.txt`
- Claude parsed: `prism/runs/20260517-formal-release-r1-root-group-disposition-preflight/collect/reviewer/parsed.json`
- Kimi raw: `prism/runs/20260517-formal-release-r1-root-group-disposition-preflight/collect/challenger/raw.txt`
- Kimi parsed: `prism/runs/20260517-formal-release-r1-root-group-disposition-preflight/collect/challenger/parsed.json`
- Gemini unavailable evidence: `prism/runs/20260517-formal-release-r1-root-group-disposition-preflight/collect/observer/unavailable.json`
- Acceptance binding: `prism/runs/20260517-formal-release-r1-root-group-disposition-preflight/artifacts/acceptance-binding.json`
