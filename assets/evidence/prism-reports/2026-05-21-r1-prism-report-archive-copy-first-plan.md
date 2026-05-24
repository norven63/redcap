# Prism Review：P4-12 Prism 报告归档迁移规划

## 控制面元数据

run_id: 20260521-r1-prism-report-archive-copy-first-plan
mode: review
date: 2026-05-21
topic: P4-12 Prism report archive copy-first / alias-first migration planning review
agents: claude-code, kimi; gemini unavailable; copilot policy-suppressed
verdict: consensus-pass-plan-only-with-followups

**运行 ID**：20260521-r1-prism-report-archive-copy-first-plan
**Adjudicate verdict**：consensus-pass-plan-only-with-followups
**参与 Agent / quorum**：2 responded（Claude Code reviewer、Kimi challenger）；Gemini 本轮可用性异常未加入；Copilot 按 protected fallback 策略未调用。

## 结论

Claude Code 与 Kimi 独立评审后形成一致意见：P4-12 的 plan-only 方案可以继续收口。

人话解释：这一步已经把“当前 52 份 Prism 正式报告将来要复制到哪里、旧路径如何继续可访问、出错如何回滚、未来执行前要验什么”写成了机器可检查的规划。但它仍然没有搬报告、没有删旧路径、没有清理 `prism/runs`，也没有关闭发布前 blocker。

## 评审发现

- 规划清单覆盖当前 tracked Prism 报告，并绑定 P4-10 预检与 P4-11 路线选择的来源真相。
- 机器检查会拒绝 source hash 过期、缺失 mapping、提前 copy/delete、raw evidence cleanup、release-ready 等越界声明。
- 旧 `prism/reports` 路径必须继续可访问，未来旧锚点退休必须另开 delete-last 任务。
- `private-archive/prism-reports` 本轮不能出现真实报告副本；若出现，checker 会失败。
- `prism/runs` 仍是本地原始运行证据，本轮未清理、未移动、未提交。

## 已处理的评审跟进

Claude Code 建议补强 acceptance 负例覆盖。收口前已追加这些越界场景：

- 提前声明 delete-last。
- 声明触碰 raw run evidence。
- 允许 destructive operations。
- 本轮创建真实 `private-archive/prism-reports/*.md` 副本。

Kimi 关注的是 closeout 状态而不是 plan 本身缺陷：任务卡、提交、clean workspace E2E 与 receipt 需要在本轮收口完成。

## 本轮允许声明

- Prism 报告归档迁移已有 plan-only 清单、旧锚点兼容要求、回滚方案和验证条件。
- 机器检查已接入 spec-check、diagnose 与 targeted acceptance，用来阻止把规划冒充成迁移完成。

## 本轮禁止声明

- Prism reports 已经物理迁移。
- 旧 `prism/reports` 锚点已经退休、替换或删除。
- `private-archive/prism-reports` 已经承接正式报告。
- Prism raw run evidence 已经清理、移动、删除或剪枝。
- `prism-layer-and-evidence` blocker 已关闭。
- RedCap 已 public-release-ready。

## 后续建议

下一条安全切片应继续保持 copy-first / alias-first 原则。建议先做“报告归档 apply readiness / rehearsal”：用 P4-12 计划验证未来 copy-first apply 的执行顺序、别名兼容和回滚证明；仍不得在没有独立验收前退休旧锚点或清理 raw evidence。

## 证据

- Prompt: `prism/runs/20260521-r1-prism-report-archive-copy-first-plan/prompt.md`
- Claude raw: `prism/runs/20260521-r1-prism-report-archive-copy-first-plan/collect/reviewer/claude.raw.txt`
- Claude parsed: `prism/runs/20260521-r1-prism-report-archive-copy-first-plan/collect/reviewer/parsed.json`
- Kimi raw: `prism/runs/20260521-r1-prism-report-archive-copy-first-plan/collect/challenger/kimi.raw.txt`
- Kimi parsed: `prism/runs/20260521-r1-prism-report-archive-copy-first-plan/collect/challenger/parsed.json`
- Registry: `prism/runs/20260521-r1-prism-report-archive-copy-first-plan/session-registry.yaml`
- Binding: `prism/runs/20260521-r1-prism-report-archive-copy-first-plan/artifacts/acceptance-binding.json`
- Plan asset: `references/r1-prism-report-archive-copy-first-plan.json`
- Checker: `compass/tools/redcap-r1-prism-report-archive-copy-first-plan-check.sh`
