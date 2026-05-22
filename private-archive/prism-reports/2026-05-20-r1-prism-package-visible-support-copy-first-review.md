# Prism Review: P4-8 Prism Package-Visible Support Copy-First Apply

## 控制面元数据

run_id: 20260520-r1-prism-package-visible-support-copy-first
mode: review
date: 2026-05-20
topic: P4-8 Prism package-visible support copy-first implementation review
agents: claude-code, kimi; gemini not-invoked; copilot policy-suppressed
verdict: consensus-pass-with-notes

**运行 ID**：20260520-r1-prism-package-visible-support-copy-first
**Adjudicate verdict**：consensus-pass-with-notes
**参与 Agent / quorum**：3 slots；2 responded（Claude Code reviewer、Kimi challenger）；1 absent/not-invoked（Gemini observer，本轮 quorum 已由 Claude Code 与 Kimi 满足）；N_quorum=2。Copilot 按保护性 fallback 策略未调用。

## 结论

Claude Code 与 Kimi 均接受本轮实现。P4-8 已把 Prism 的第一批 package-visible support 与 provider-routing contract 做成 `runtime/redcap-core/prism-tools` 下的 copy-first facade：外部包面能看到稳定入口，旧 `prism/*` 锚点仍保留为权威实现。

这不是 Prism 物理拆分，也不是证据清理，更不是 release blocker 关闭。它只是把下一段可发布前验证的 Prism 支撑面先安全接出来。

## 已确认完成

- 8 个 batch-1 Prism 目标被精确覆盖：5 个 package-visible support，3 个 provider-routing contract。
- 新增 facade 都只是薄包装，委托旧 `prism/tools` 或 `prism/README.md`，没有复制或替换旧实现。
- 包候选数量从 264 增加到 272，增长完全等于 8 个 facade；任务专用 checker 和清单不进入包面。
- Claude Code / Kimi 优先、Copilot protected fallback、Codex last-resort 的路由保护未被弱化。
- dedicated checker 已接入 spec-check、diagnose、acceptance 和文件查阅字典。

## 评审中抓到的注意点

Kimi 对 `references/r1-prism-evidence-retention-apply-preflight.json` 的 coverage 统计提出过疑问：它看到 `local-run-evidence-store: 3`，而 package-visible 列表中只有 2 个 local-run 条目。

复核结果：这不是 P4-8 缺陷。该统计字段统计的是 package-visible targets 加 source-evidence targets 的合计，不只是 package-visible 列表。现有 `redcap-r1-prism-evidence-retention-apply-preflight-check.sh` 会按源清单重算 `by_target_layer`，已证明当前统计一致。

## 仍然不能声明

- 不能声明 Prism layer 已经物理拆分。
- 不能声明旧 `prism/tools`、`prism/reports` 或 `prism/runs` 已被移动、删除、清理或替换。
- 不能声明 Prism report archive migration 已完成。
- 不能声明 local run evidence cleanup 已完成。
- 不能声明 `prism-layer-and-evidence` blocker 已关闭。
- 不能声明 RedCap 已 public-release-ready。

## closeout 前必须补齐

- 写入本 Prism report 并更新 Prism index。
- 写入 P4-8 task report 并更新 docs catalog。
- 绑定 Prism acceptance 到 `.dev-task.md`。
- 重跑 package surface、targeted acceptance、spec-check、diagnose 与 closeout runtime。

## 证据

- Prompt: `prism/runs/20260520-r1-prism-package-visible-support-copy-first/prompt.md`
- Claude raw: `prism/runs/20260520-r1-prism-package-visible-support-copy-first/claude.raw.txt`
- Kimi raw: `prism/runs/20260520-r1-prism-package-visible-support-copy-first/kimi.raw.txt`
- Claude parsed: `prism/runs/20260520-r1-prism-package-visible-support-copy-first/collect/reviewer/parsed.json`
- Kimi parsed: `prism/runs/20260520-r1-prism-package-visible-support-copy-first/collect/challenger/parsed.json`
- Registry: `prism/runs/20260520-r1-prism-package-visible-support-copy-first/session-registry.yaml`
