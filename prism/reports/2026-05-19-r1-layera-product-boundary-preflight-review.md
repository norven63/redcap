# Prism Review: R1 Layer A Product Boundary Preflight

## 控制面元数据

run_id: 20260519-r1-layera-product-boundary-preflight
mode: review
date: 2026-05-19
topic: Formal release R1 Layer A product boundary preflight
agents: claude-code, kimi
verdict: pass-with-concerns

**运行 ID**：20260519-r1-layera-product-boundary-preflight
**Adjudicate verdict**：weak-consensus
**参与 Agent / quorum**：2 slots；2 responded（Claude Code reviewer、Kimi challenger）；N_quorum=2。

## 结论

Claude Code 与 Kimi 均确认：P4-2r 严格保持 product-boundary preflight 边界，没有把 Layer A 公开纳入、退休、物理迁移、R1 关闭或 public release ready 提前说成完成。两路都没有提出阻塞性问题。

## 共同确认

- `references/r1-layera-product-boundary-preflight.json` 保持 `is_layera_public_product_decided=false`、`is_layera_included_in_public_release=false`、`is_layera_retired_or_removed=false`、`is_layera_physically_moved=false`、`is_r1_closed=false`、`is_public_release_ready=false`。
- `loom` 当前 package candidate count 为 0；这只证明不会误打包，不等于产品范围已经被裁决。
- `loom/dispatcher`、`loom/roles`、`loom/tools`、`loom/test-reports`、`loom/fixtures` 五类资产已进入 surface contract。
- 消费者矩阵覆盖 Layer A 状态机/路由、角色手册/提示词、hooks/tools、E2E 队列、人类文档、Layer B fallback 和边界检查。
- future decision gate 明确区分公开纳入、排除/退休、物理迁移三条路径，均要求 Norven 产品范围裁决、兼容测试、包面安全、clean workspace E2E、Prism review 与 closeout receipt。
- spec-check、diagnose、acceptance 与 formal release readiness plan 都已接入新检查，能够 fail-closed 拒绝错误 claim、陈旧统计、缺失消费者矩阵或缺失 future gate。

## concerns 与处理

- Claude Code 建议补强 acceptance 的 sad-path 覆盖。本轮已追加缺失消费者矩阵与缺失 future decision gate 两个失败用例。
- Claude Code 指出 catalog 中 P4-2r 的 `summary_points` 为空。本轮已把任务报告补成标准“当前/上一步/下一步/位置”结构，并重新生成 catalog。
- Kimi 提醒 Prism report、acceptance binding、完成勾选与 Evolution harvest gate 需要在 closeout 前补齐。这些属于收口步骤，本报告与后续 closeout 会处理。
- Kimi 提醒旧 ledger 中存在历史包候选数字。当前权威数字由各 preflight checker 实时复验；旧数字只代表旧 baseline，不作为当前完成声明。

## 风险边界

- 不得把本轮外推为 Layer A 已属于公开 RedCap 产品。
- 不得把本轮外推为 Layer A 已退休、删除或物理迁移。
- 不得把本轮外推为 `internal-layer-a` blocker 已解决。
- 不得把本轮外推为 R1 cleanup closed、public-release-ready、license 已选、发布开关已开或 registry release 可执行。

## 证据

- Prompt: `prism/runs/20260519-r1-layera-product-boundary-preflight/prompt.md`
- Registry: `prism/runs/20260519-r1-layera-product-boundary-preflight/session-registry.yaml`
- Claude raw: `prism/runs/20260519-r1-layera-product-boundary-preflight/collect/claude-code-reviewer.raw.md`
- Kimi raw: `prism/runs/20260519-r1-layera-product-boundary-preflight/collect/kimi-challenger.raw.md`
- Claude parsed: `prism/runs/20260519-r1-layera-product-boundary-preflight/collect/reviewer/parsed.json`
- Kimi parsed: `prism/runs/20260519-r1-layera-product-boundary-preflight/collect/challenger/parsed.json`
