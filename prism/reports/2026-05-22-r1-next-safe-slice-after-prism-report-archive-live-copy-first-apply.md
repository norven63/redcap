# Prism Review：P4-17 Prism 报告归档后的下一安全切片选择

## 控制面元数据

run_id: 20260522-r1-next-safe-slice-after-prism-report-archive-live-copy-first-apply
mode: review
date: 2026-05-22
topic: R1 next safe slice after Prism report archive live copy-first apply
agents: claude-code, kimi; gemini unavailable; copilot policy-suppressed
verdict: weak-consensus-split-decision-cap-adjudicates-conservative-D

**运行 ID**：20260522-r1-next-safe-slice-after-prism-report-archive-live-copy-first-apply
**参与 Agent / quorum**：2 responded（Claude Code reviewer、Kimi challenger）；Gemini 当前可用性缓存不可用；Copilot 按 protected fallback 策略未调用。

## 结论

Claude Code 和 Kimi 对下一刀出现分歧。

- Claude Code 建议先做 **正式发布就绪收敛评估**：把剩余 blocker 和人工决策边界合成一张差距地图。
- Kimi 建议先做 **旧报告锚点 delete-last 预检**：延续 P4-16 copy-first 链路，但只做预检，不删除。

Cap 裁决采用 Claude Code 的方向：**P4-18 先做正式发布就绪收敛评估**。

人话解释：P4-16 已经完成报告副本，但 RedCap 还不能直接进入删除旧锚点、清理原始证据或发布。下一步先做全局差距地图，能防止我们继续只盯着 Prism 报告这一条局部链路，而漏掉 release readiness 的其他边界。

## 评审重点

### 1. 为什么不立刻做旧锚点 delete-last

结论：可以作为后续候选，但不作为 P4-18。

旧锚点退休确实是 copy-first 后的自然下一步；但 delete-last 即使先做预检，也会把注意力继续锁在 Prism 报告归档局部。P4-17 的更安全选择是先确认整体发布差距，再决定 delete-last 是否仍是最高优先级。

### 2. 为什么不做 raw evidence cleanup

结论：不能自主执行。

`prism/runs` raw evidence 是审计链材料。任何 cleanup apply 都需要保全证明和 Norven 明确批准；本轮不触碰。

### 3. 为什么不做 Layer A 产品边界裁决

结论：不能由 Cap 或棱镜裁决。

Layer A 是否进入公开产品，是 Norven 保留产品决策；本轮只识别这个人工边界，不替用户做决定。

### 4. 为什么选择 release readiness 收敛评估

结论：最稳。

它不删除文件、不清理证据、不改变发布开关、不替用户做产品选择，只把剩余 blocker、已完成预检和下一步安全顺序整理成一张可审计地图。

## P4-18 建议边界

建议登记为：**R1 formal release readiness convergence assessment after Prism report archive apply**。

P4-18 只能做：

- 汇总 internal-control-plane、prism-layer-and-evidence、Layer A 产品边界和包面状态。
- 标出剩余差距、人工决策点、可自主推进的安全小切片。
- 形成下一步排序建议。

P4-18 不能做：

- 删除或退休旧 `prism/reports` 锚点。
- 清理或裁剪 `prism/runs` raw evidence。
- 裁决 Layer A 产品范围。
- 修改发布开关、registry、license 或 package privacy。
- 宣称 RedCap 已 ready for public release。

## 验收要求

- `references/r1-next-safe-slice-after-prism-report-archive-live-copy-first-apply.json` 记录候选矩阵、棱镜分歧、Cap 裁决和禁止声明。
- P4-17 标记为 done，P4-18 登记为 pending。
- P4-15 churn/freeze guard 与 P4-16 live apply checker 在新增 P4-17 报告后仍通过。
- spec-check、diagnose、Prism acceptance、clean workspace E2E 与 closeout receipt 通过。

## 结论边界

本报告只证明“下一安全切片已选定”。它不证明旧锚点已删除、raw evidence 已清理、Layer A 已裁决或 RedCap 已可公开发布。
