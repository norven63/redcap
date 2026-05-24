# Prism Review: R1 Control-Plane Contract Split Preflight

## 控制面元数据

run_id: 20260518-r1-control-plane-contract-split-preflight
mode: review
date: 2026-05-18
topic: Formal release R1 internal-control-plane contract split preflight
agents: claude-code, kimi; gemini absent
verdict: pass-with-concerns

**运行 ID**：20260518-r1-control-plane-contract-split-preflight
**Adjudicate verdict**：weak-consensus
**参与 Agent / quorum**：3 slots；2 responded（Claude Code reviewer、Kimi challenger）；1 absent（Gemini observer，本轮未调用）；N_quorum=2。

## 结论

Claude Code 与 Kimi 均确认：P4-2p 严格保持 preflight / analysis-only 边界，没有把控制面物理拆分、R1 关闭或 public release ready 提前说成完成。Kimi 的 concerns 指向 closeout 前的索引/报告/binding 补齐，不构成设计 blocker。

## 共同确认

- `references/r1-control-plane-contract-split-preflight.json` 保持 `is_control_plane_physically_split=false`、`is_r1_closed=false`、`is_public_release_ready=false`，并继续把 `internal-control-plane` 标为 release blocker。
- 包候选统计由 `redcap-runtime-package-manifest.sh` 实时复验，checker 会拒绝陈旧数字。
- 消费者矩阵覆盖 root runtime facade、release safety、Layer B closeout/governance、knowledge/docs gateway、Prism acceptance binding 五类主要消费者。
- future split gate 包含 dry-run manifest、consumer matrix、alias/rollback、package-safety proof、clean workspace E2E、Prism review、closeout receipt 等后续物理拆分前置条件。
- spec-check、diagnose、acceptance 与 formal release readiness plan 都已接入新检查，能够 fail-closed 拒绝把 preflight 冒充 release-ready。

## concerns 与处理

- Kimi 指出 docs catalog、reference asset lifecycle、legacy asset migration 这类计数型 registry 会因新增文件变陈旧。本轮已刷新这些 registry。
- Kimi 指出 consumer matrix 不是逐脚本依赖全集。本轮接受该边界，因为 P4-2p 是拆分预检；未来真实物理移动 tranche 必须扩展到更精确的文件级/调用级矩阵。
- 两路均指出 task report、Prism report、acceptance binding 和 closeout receipt 必须在 closeout 前补齐。本报告即为 repo-tracked Prism report，binding 和 receipt 由后续收口步骤生成。

## 风险边界

- 不得把本轮外推为 `compass` / `references` 已经物理迁移。
- 不得把本轮外推为 `internal-control-plane` 已经 resolved。
- 不得把本轮外推为 R1 cleanup closed、public-release-ready、license 已选、发布开关已开或 registry 发布可执行。
- Claude Code raw 输出尾部出现宿主 SessionEnd hook warning，但评审 JSON 已完整返回；该 warning 不影响本轮 Prism verdict。

## 证据

- Prompt: `prism/runs/20260518-r1-control-plane-contract-split-preflight/prompt.md`
- Registry: `prism/runs/20260518-r1-control-plane-contract-split-preflight/session-registry.yaml`
- Claude raw: `prism/runs/20260518-r1-control-plane-contract-split-preflight/collect/reviewer/raw.txt`
- Claude parsed: `prism/runs/20260518-r1-control-plane-contract-split-preflight/collect/reviewer/parsed.json`
- Kimi raw: `prism/runs/20260518-r1-control-plane-contract-split-preflight/collect/challenger/raw.txt`
- Kimi parsed: `prism/runs/20260518-r1-control-plane-contract-split-preflight/collect/challenger/parsed.json`
- Acceptance binding: `prism/runs/20260518-r1-control-plane-contract-split-preflight/artifacts/acceptance-binding.json`
