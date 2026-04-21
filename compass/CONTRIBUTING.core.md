# RedCap 启动核心契约

> 本文件是 `compass/CONTRIBUTING.md` 的启动必读核心契约。
> compass/CONTRIBUTING.md 仍是权威规范全文；本文件只负责把新会话必须立即遵守的高密度规则压缩成首读入口。

## 读取边界

1. **必须先遵守核心契约**：新会话、复活、接盘、长任务继续时，先读本文件，再运行 `compass/tools/redcap-current-status.sh`。
2. **不得把全文规范当默认上下文**：`compass/CONTRIBUTING.md` 不应被宿主入口无差别全文注入；需要细则时，先按章节路由精确读取。
3. **全文仍是权威**：当本文件和 `compass/CONTRIBUTING.md` 冲突时，以全文规范为准，并修正本文件，不能让核心契约漂移。

## 必守红线

1. **`.dev-task.md` 是 Layer B 当前任务真相源**：任务目的、确认需求、active slice、允许修改范围、backlog 锚点，以 `.dev-task.md` 为准。
2. **不要伪装完成**：backlog、pending validation、governance debt、Prism quorum、真实 E2E 如果没有物理证据，不得标 done。
3. **变更前必须做经验回顾**：框架/治理/控制面变更前，先通过 `compass/knowledge/index.md` 与 `lessons.md` 的热点主题速览定位相关经验，不能因为 lessons 大就跳过已知失败模式。
4. **强制规则必须进执行保障**：P0/P1 规则不能只写在报告或自然语言里；能自动化的接入脚本、validator、hook、acceptance，不能自动化的写清 manual-only 原因。
5. **收尾必须 fail-closed**：stop-review、on-complete、session-end、spec-check、diagnose 等控制面失败时，不能用后续成功覆盖失败。
6. **上下文必须渐进披露**：docs 先 catalog summary/plan/budget，knowledge 先 index，acceptance 先 acceptance-index；大文件不默认 bulk-read。
7. **人类可读输出必须说人话**：首次出现内部术语、缩写、阶段名时，要解释对应文件/功能、做了什么、为什么重要。
8. **宿主面只能镜像 RedCap 真相**：`cli_console.md`、宿主 workboard、plan mirror 不能反向改写 `.dev-task.md`、runtime state 或 task report。
9. **运行残留不能擅自删除**：`prism/runs`、`compass/.runtime`、`compass/.workflow` 等 ignored 本地证据目录默认 no-bulk-read；物理清理需用户显式批准。
10. **Codex 子 Agent 默认克制但不是禁用**：仅在确实能提效提质时开启，且 RedCap / Prism 主动拉起的 Codex-family 执行进程总数默认不超过 2（当前宿主也计入）；外部审查 / reviewer 选择统一按“模型能力画像 + 本地 CLI 稳定性”排序，不得静态压低 Copilot / Codex。
11. **飞书不是唯一收尾动作**：飞书通知只是可见信号；真正收尾还要看 review、validator、task report、lessons、backlog、catalog、diagnose 与 pending closure。
12. **首读/诊断入口当前要求可写临时目录**：`current-status`、`diagnose`、`docs-catalog`、`acceptance-index`、`token-risk-audit` 在当前实现下不承诺 read-only sandbox 可跑；只读 reviewer 宿主必须走 wrapper、手工账本查验，或显式接受 degraded/manual-only 边界。

## 章节路由

| 场景 | 先读章节 |
|---|---|
| 设计/治理变更 | `CONTRIBUTING.md` §1、§6、§9、§10、§13 |
| commit / 收尾 / 飞书 | `CONTRIBUTING.md` §2、§3、§4、§5、§13 |
| docs / knowledge / token 风险 | `CONTRIBUTING.md` §6、§7 的 docs/knowledge 边界、`compass/docs/index.yaml`、`compass/knowledge/index.md` |
| hook / validator / runtime state | `CONTRIBUTING.md` §4、§7 控制面硬化、`references/hook-standards.md` |
| Prism / 多 Agent 审查 | `CONTRIBUTING.md` §8、§9、§11、`prism/protocol.md` |
| 需求确认 / 人工介入边界 | `CONTRIBUTING.md` §10、`references/agent-constraints.md` |
| 调研结论 | `CONTRIBUTING.md` §14 |

## 必跑入口

1. `bash compass/tools/redcap-current-status.sh .dev-task.md`（当前要求可写临时目录）
2. `bash compass/tools/redcap-diagnose.sh .dev-task.md`（当前要求可写临时目录）
3. `bash compass/tools/redcap-token-risk-audit.sh`（当前要求可写临时目录）
4. 涉及 docs：`bash compass/tools/redcap-docs-catalog.sh plan "<query>"` 与 `budget <paths...>`（当前要求可写临时目录）
5. 涉及 acceptance：`bash compass/tools/redcap-acceptance-index.sh find "<case>"`（当前要求可写临时目录）
