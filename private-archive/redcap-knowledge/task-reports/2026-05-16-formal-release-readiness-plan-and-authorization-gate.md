# 任务完成报告：正式发布准备计划与人工授权矩阵

**报告日期**：2026-05-16
**执行者**：Cap（Codex + Prism: Claude Code / Kimi）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 已把正式发布前的总计划、人工决策边界和自动执行边界落成机器可检查的 release readiness 控制面。
- 详情：本轮解决的是“发布计划散在 handoff、E2E matrix、package policy 和对话解释里”的问题。现在正式发布前路线被收束成 10 个阶段，授权边界被拆成 Norven 必须决策、Cap + Prism 可自主决策、可条件提前授权三类，并由新检查器防止它们漂移。Claude Code 与 Kimi 已做独立评审，结论是无 P0/P1 blocker。

### 0.2 上一步完成的是

- 上一步完成的是：迁移后的 RedCap 全工程 review 已关闭，结论是没有新的 P0/P1 工程阻塞；但正式发布仍缺少独立 release 父任务树和授权矩阵。

### 0.3 下一步计划做的是

- 下一步计划做的是：如果 Norven 想进入真实 formal release task，下一步应回答 `references/release-authorization-matrix.json` 中的 10 个发布授权问题；回答前 RedCap 仍保持 private/readiness-only，不改变发布开关。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：迁移后全工程 review 完成 -> 发布准备计划与授权矩阵落盘 -> Norven 授权问卷 -> formal release task -> 最终发布前全量门禁。
- 当前所在位置：P4-2l / formal-release-readiness-plan-and-authorization-gate；本轮是发布任务前的控制面补齐，不是真实发布。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要完成本轮任务。
- 说明：本轮只补齐发布前计划和授权矩阵，Cap + Prism 可以自主完成。若下一步要进入真实发布任务，则需要 Norven 回答许可证、发布目标、版本号、账号权限、发布开关和风险接受等问题。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> “好的，我赞同你们的建议，开始吧”

### 1.2 触发背景

此前已经确认：发布前工程材料存在，但没有完整形成独立 release 父任务树。用户同时要求把人工决策提前分类，尽可能通过问答方式一次性冻结，后续由 Cap + Prism 自动推进，只有真正不可推断的人类保留决策才中断。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 把发布前总计划与人工决策分类真正落到 RedCap 控制面中，而不是继续停留在对话解释 |
| 已覆盖 | 发布准备计划、授权矩阵、条件授权边界、handoff 指向、字典索引、diagnose 检查、棱镜评审 |
| 未覆盖/延期 | Norven 尚未回答发布授权问卷；本轮不选择许可证、不改变发布开关、不触发外部 registry 状态变化 |
| 用户可见边界 | 不能把本轮说成正式发布，也不能说 RedCap 已具备无条件 public-release-ready |
| 后续路径 | 回答授权问卷后另开 formal release task，按 10 阶段路线执行 |

## 二、方案讨论

### 2.1 问题分析

发布准备和正式发布不是同一件事。发布准备可以由 Cap + Prism 自动做很多技术工作；但许可证、公开发布意愿、账号权限、版本语义、风险接受和外部 registry 状态变化不能由 AI 代替 Norven 决定。本轮的核心不是“马上发布”，而是把这些边界做成 RedCap 可以持续执行和审计的控制面。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|---|---|---|---|
| Q1 | 继续使用 handoff + E2E matrix | 不新增统一计划，只依赖已有文件 | 改动少 | 仍然分散，后续容易遗忘 |
| Q1 | 新增 release plan + authorization matrix | 把路线和授权边界做成机器权威 | 可检查、可复用、可给问卷 | 需要新增检查脚本和索引 |
| Q1 | 直接进入发布任务 | 立刻问授权并推进 | 快 | 缺少计划门禁，容易再次漂移 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---|---|---|
| Q1 | 新增 release plan + authorization matrix | 这是最符合 RedCap “不要靠口头协议、要可审计落盘”的方案 | NORVEN_DECIDE + CAP_DECIDE |

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|---|---|---|
| `.dev-task.md` | 修改 | 重锚到 P4-2l 发布准备计划与授权矩阵任务 |
| `references/formal-release-readiness-plan.json` | 新建 | 10 阶段正式发布准备路线图 |
| `references/release-authorization-matrix.json` | 新建 | 人工决策、自主决策、条件授权矩阵和 10 问发布问卷 |
| `compass/tools/redcap-formal-release-readiness-plan-check.py` | 新建 | 校验 release plan、authorization matrix、handoff、E2E matrix 与包策略一致 |
| `compass/tools/redcap-formal-release-readiness-plan-check.sh` | 新建 | 新检查器 shell 入口 |
| `compass/tools/redcap-diagnose.sh` | 修改 | 接入 formal release readiness plan 检查 |
| `references/public-release-handoff.md` | 修改 | 增加 release plan 与 authorization matrix 的先读入口 |
| `references/file-lookup-dictionary.md` | 修改 | 加入新增 release 控制面资产 |
| `references/file-lookup-dictionary-policy.json` | 修改 | 把新增资产纳入字典强门 |
| `references/public-package-surface-policy.json` | 修改 | 包候选数量上限从 190 同步到 194，反映新增发布控制面文件 |
| `references/redcap-parent-task-ledger.md` | 修改 | 登记 P4-2l 当前子任务 |
| `prism/reports/2026-05-16-formal-release-readiness-plan-review.md` | 新建 | 棱镜评审报告 |
| `prism/reports/index.yaml` | 修改 | 登记本轮棱镜 review |

### 3.2 技术实现要点

本轮新增的核心是两份权威文件。`formal-release-readiness-plan.json` 负责回答“正式发布前后到底要走哪些阶段”，而 `release-authorization-matrix.json` 负责回答“哪些事必须 Norven 决策、哪些事 Cap + Prism 可以自动做”。这两个文件被新检查器和 `diagnose` 串起来，避免后续又退化成我临场解释。

检查器不只看文件是否存在，还会交叉校验：当前包名是否仍是 `@norven63/redcap`、当前许可证是否仍是 `UNLICENSED`、发布开关是否仍保持关闭、条件授权是否仍是 `not-yet-granted`、10 个 Norven 必须决策是否都有问卷入口。棱镜提出“required_sources 应检查物理存在”和“条件授权应防止 waiver / partial override”后，我已直接加固。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|---|---|---|
| release readiness plan | `references/formal-release-readiness-plan.json` | 正式发布前的路线图，告诉 RedCap 先做什么、什么情况停止、什么证据算通过 |
| authorization matrix | `references/release-authorization-matrix.json` | 发布授权表，告诉 RedCap 哪些问题必须问 Norven，哪些技术问题可以自己和棱镜判断 |
| conditional authorization | `release-authorization-matrix.json` | 条件授权，不是空白支票；只有所有列出的门禁都通过，才允许继续 |
| fail-closed | 新检查器与授权矩阵 | 只要检查失败或授权缺失，就停止，而不是先发布再补救 |

### 3.3 关联变更

`public-package-surface-policy.json` 的候选文件上限从 190 更新为 194，是因为本轮新增 4 个会进入 package readiness surface 的控制面文件。它们是发布准备所需的公开/维护者检查资产，不是私密资产；包安全检查和 dry-run 已确认没有私有文件进入候选包面。

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|---|---|---|---|
| 1 | 下一步是否进入 formal release task | 本轮已准备好问卷入口，但是否真的开始发布任务仍取决于 Norven | P0 |
| 2 | 发布授权问卷答案 | 许可证、发布目标、版本、账号权限、发布开关和风险接受必须由 Norven 决定 | P0 |

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|---|---|---|
| 发布计划检查 | `bash compass/tools/redcap-formal-release-readiness-plan-check.sh` | 通过 |
| 文件查阅字典 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过 |
| Release E2E 矩阵 | `bash compass/tools/redcap-release-e2e-matrix-check.sh` | 通过 |
| 公共包面 | `bash compass/tools/redcap-public-package-surface.sh` | 通过，candidate_count=194 |
| 包发布安全 | `bash compass/tools/redcap-package-publish-safety-check.sh` | 通过，files_scanned=194 |
| runtime package manifest | `bash compass/tools/redcap-runtime-package-manifest.sh --check --npm-pack-dry-run` | 通过，publish_allowed=false |
| runtime contract surface | `bash compass/tools/redcap-runtime-contract-surface-check.sh` | 通过 |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过，2 reviewers / 2 families |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 如果要进入真实 formal release task，Norven 需要回答 `references/release-authorization-matrix.json` 中的 10 个发布授权问题。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|---|---|
| 执行承诺账本 | 收口时核对 |
| 棱镜验收 | 已通过，run=`20260516-formal-release-readiness-plan` |
| closeout summary | 收口后生成 |
| closeout receipt | 收口后生成 |
| rescue audit（如有） | 无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|---|---|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，Claude Code + Kimi |
| 已正式完成 | 待 closeout receipt |

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|---|---|---|
| Norven 发布授权问卷尚未回答 | 这是下一步进入 formal release task 的人工边界，不属于本轮控制面落盘 | P0-before-release-task |
| 外部机器 / 多 OS 验证 | 当前 E2E matrix 明确延期到 formal release task；如果发布 stable，不能跳过 | P0-before-stable |

### 6.2 触发的新问题

无新的 P0/P1。棱镜提出的 P2/P3 加固项已在本轮直接处理。

### 6.3 推荐的下一步行动

1. 如果 Norven 要继续推进正式发布，下一步由 Cap 给出 10 问发布授权问卷。
2. Norven 回答后，Cap + Prism 按 `formal-release-readiness-plan.json` 另开 formal release task。

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|---|---|---|
| 无新增 | 本轮是发布控制面落盘 | 经验已体现在 release plan / authorization matrix 与 checker 中，不单独新增 lesson |

### 7.2 流程改进建议

发布前人工决策不应散在聊天里。RedCap 应先用授权矩阵把人类保留决策列出来，再允许 Cap + Prism 自动推进技术任务。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|---|---|---|---|
| 无新增候选 | 本轮控制面治理 | no-promote | 本轮产物为 release 控制面，不进入公共 arsenal |

## 八、附录

### 附录 A：Commits

```
9f9ce85 test(e2e): 刷新收口报告后的清洁证明
20e4f56 docs(report): 回填迁移后审查收口凭证
6752a6b test(e2e): 刷新迁移后清洁工作区证明
```

### 附录 B：棱镜调用记录

| 模式 | 问题 | 结论 | 报告路径 |
|---|---|---|---|
| review | 发布准备计划与授权矩阵是否足够 fail-closed | pass，无 P0/P1 blocker | `prism/reports/2026-05-16-formal-release-readiness-plan-review.md` |
