# RedCap Assets

`assets/` 是 RedCap 的项目资产总入口。它收纳“需要被考古、检索、审计或长期复用”的内容；源码、宿主入口、运行时工具和本地临时状态不放在这里。

这次收敛的目标不是把所有东西塞进一个桶里，而是让人和 Agent 能一眼分清：哪些是可读文档，哪些是活知识，哪些是机器契约，哪些是审计证据，哪些只是私有冷归档。

## 先看这张地图

RedCap 根目录不是要压缩成一个目录，而是要让每个可见入口都有清楚身份：

| 根目录区域 | 人话解释 | 是否应该搬进 `assets/` |
|---|---|---|
| 人类入口 | `README.md`、`ARCHITECTURE.md`，让第一次接触 RedCap 的人快速理解它。 | 否，应该留在根目录。 |
| 宿主入口 | `AGENTS.md`、`CLAUDE.md`、`GEMINI.md`、`SKILL.md` 和 `.claude/.codex/.gemini/.github`。 | 否，宿主会按固定位置发现它们。 |
| 运行入口 | `bin/`、`runtime/`、`revive-cap.sh`、`closeout-cap.sh`。 | 否，它们是 runtime/CLI facade。 |
| 长期资产 | `assets/` 本身。 | 是，docs、knowledge、references、formal reports、private archive 都以这里为主位置。 |
| 兼容桥 | `references`、`private-archive`、`compass/docs`、`compass/knowledge`、`prism/reports`。 | 已经指向 `assets/`；保留是为了避免旧 receipt 和旧脚本断链。 |
| 评审系统 | `prism/`。 | 不整体搬入 `assets/`；只有 formal reports 进 `assets/evidence/`，raw runs 留在 `prism/runs/` 生命周期里。 |
| 本地状态 | `.dev-task.md`、`.env`、`.tmp/`、`prompt.txt`、`cli_console.md`。 | 否，它们是本机状态，应忽略、排除出包。 |

## 目录职责

| 目录 | 人话解释 | 读取原则 |
|---|---|---|
| `assets/docs/` | 设计稿、规格、研究材料、近期任务报告和 docs catalog。 | 先看 `assets/docs/catalog.json` 或旧兼容入口 `compass/docs/catalog.json`，再按需打开具体文件。 |
| `assets/knowledge/` | 活知识：lessons、宿主差异、长任务防漂移、LLM-wiki-lite、运行记忆解释。 | 先看 `assets/knowledge/index.md` 或旧兼容入口 `compass/knowledge/index.md`，禁止默认全文加载。 |
| `assets/references/` | 机器可读契约、策略、backlog、发布安全政策、文件查阅字典。 | 这是控制面资产的真实位置；旧 `references/` 只保留兼容入口。 |
| `assets/evidence/prism-reports/` | formal Prism 评审报告归档。 | 报告可被索引和考古；raw run 证据仍在 `prism/runs/`，不迁入这里。 |
| `assets/private-archive/` | 私有冷归档：旧报告、旧研究、旧 trace。 | 默认不进公开包，不默认加载；只在考古或 receipt 追溯时精确读取。 |

## 兼容入口

为了不破坏旧报告、脚本和 receipt 的历史路径，本轮保留以下兼容入口：

| 旧入口 | 指向 |
|---|---|
| `compass/docs` | `assets/docs` |
| `compass/knowledge` | `assets/knowledge` |
| `references` | `assets/references` |
| `prism/reports` | `assets/evidence/prism-reports` |
| `private-archive` | `assets/private-archive` |

这些入口是桥，不是新的内容主位置。新资产默认写入 `assets/` 下对应目录；只有宿主或旧工具明确要求旧路径时，才通过兼容入口访问。

## 不属于 assets 的内容

- `compass/tools/`：RedCap 自身工具源码。
- `runtime/`、`bin/`、`revive-cap.sh`、`closeout-cap.sh`：runtime 与 CLI 入口。
- `.dev-task.md`、`.env`、`.tmp/`、`compass/.workflow/`：本地或会话状态。
- `prism/runs/`：Prism raw run 证据，仍按 run 生命周期管理，避免把运行残留混进长期报告层。
- `loom/`、`prism/tools/`、`contracts/`、`internal/`：执行、评审、契约和内部控制面的源码或镜像层。

## 发布边界

`assets/references/` 中少量发布契约会进入 readiness 包候选；`assets/docs/`、`assets/knowledge/`、`assets/evidence/` 和 `assets/private-archive/` 默认不进入公开包。发布前仍必须通过 package safety、public package surface 和 clean workspace E2E 检查。
