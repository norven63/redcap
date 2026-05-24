# 任务完成报告：P4-2h-0 historical asset public distillation preflight

**报告日期**：2026-05-06
**执行者**：Cap（Codex.app 主执行，Claude Code + Copilot 轻量棱镜评审）
**报告版本**：v0.2

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 已把“历史资产未来是否能进入公共 redcap-arsenal”先收束成 dry-run 预检强门。
- 详情：本轮解决的是“不能因为公共库还空，就把私有历史报告、经验库或运行证据直接搬出去填充内容”的风险。现在 RedCap Forge 只能先做候选分类和边界检查，公共写入、raw 私有资料导出、历史资产删除/移动、npm 发布都被明确禁止。这样后续如果真的要公开沉淀知识，必须先经过脱敏、去重、安全审查、append-only 条目和索引刷新。

### 0.2 上一步完成的是

- 上一步完成的是：P4-2e 已把公共 `redcap-arsenal` 仍为 template-only 的事实和宣传边界机器化，防止把空模板说成已填充知识库。

### 0.3 下一步计划做的是

- 下一步计划做的是：本轮完成 closeout 后，P4-2h 仍保持真实公共蒸馏 deferred；若未来要公开具体条目，需要另开 RedCap Forge promotion 任务。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P4-2a 产品架构审判 -> P4-2b workspace 边界 -> P4-2c CLI 产品面 -> P4-2d 包身份/包面 -> P4-2e 公共 arsenal claim 边界 -> P4-2h-0 公共蒸馏预检 -> P4-2h 真实公共蒸馏 -> P4-2 正式发布。
- 当前所在位置：P4-2h-0 已完成实现、回归、棱镜验收与 closeout receipt；真实 P4-2h 公共蒸馏仍保持 deferred。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮只做 dry-run 预检机制，不公开导出任何历史内容；未来如果出现具体公共候选条目，再进入需要 Norven 判断隐私和公开边界的阶段。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 好的，接下来需要如何推进，由你和棱镜团队共同评审和决策

### 1.2 触发背景

P4-2e 完成后，父任务线出现三个可能方向：正式发布、历史资产公共蒸馏、运行证据清理。由于正式 npm 发布仍被阻塞，`prism/runs` 物理清理又涉及证据保留风险，Cap 先用 Claude Code 与 Copilot 做独立路线评审。两路评审都建议进入 P4-2h-0，即只做历史资产公共蒸馏的安全预检。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 由 Cap 与棱镜团队共同决定下一步，并继续推进 RedCap 父任务线。 |
| 已覆盖 | 已完成路线评审、P4-2h-0 任务锚定、公共蒸馏 dry-run policy/checker、控制面接线和 targeted 回归。 |
| 未覆盖/延期 | 不执行真实 npm 发布；不向公共库写入实质知识；不删除或移动历史资产；不执行真实 P4-2h promotion。 |
| 用户可见边界 | 可以声明“公共蒸馏预检机制已具备”；不能声明“历史知识已经公开沉淀”或“redcap-arsenal 已填充”。 |
| 后续路径 | 未来若要公开具体条目，另开 RedCap Forge promotion 任务。 |

---

## 二、方案讨论

### 2.1 问题分析

本轮的核心不是“要不要把内容搬到公共库”，而是“在搬任何内容之前，先建立不会误泄漏、误删除、误发布的判断门”。历史任务报告、lessons、identity、runtime evidence 都可能有私密路径、身份信息、失败轨迹或用户上下文，不能作为公共知识条目原文发布。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 进入 npm 发布 | 直接开始 release readiness 或 publish | 路线看似更快 | 发布仍 blocked，且没有解决公共知识边界 |
| Q1 | 清理 prism/runs | 优先处理运行证据堆积 | 能降低局部噪声 | 物理删除证据需要独立授权，不是父任务主线 |
| Q1 | P4-2h-0 dry-run preflight | 只做公共蒸馏候选分类和安全门 | 能推进主线，又不公开导出 | 还不会产生公共库实质内容 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | P4-2h-0 dry-run preflight | Claude Code 与 Copilot 都判断这是当前唯一既能推进父任务、又不越过发布/隐私/证据边界的路线。 | CAP_DECIDE + PRISM_REVIEW |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `.dev-task.md` | 修改 | 将当前任务锚定为 P4-2h-0，并写入完成标准与承诺账本。 |
| `references/public-distillation-preflight-policy.json` | 新建 | 定义 dry-run 边界、可作为来源的私有资产、禁止 raw 公开来源、四类 triage 和未来公共条目 schema。 |
| `compass/tools/redcap-public-distillation-preflight.py` / `.sh` | 新建 | 校验公共蒸馏预检策略、跨策略一致性、公共库 template-only 状态和 P4-2h-0 任务树锚点。 |
| `references/pre-release-structure-refactor-task-tree.json` | 修改 | 增加 P4-2h-0 当前节点，明确它不是 release blocker。 |
| `references/redcap-parent-task-ledger.md` | 修改 | 将 P4-2h-0 加入父任务全景图，并说明它只做预检。 |
| `references/execution-guarantees.json` | 修改 | 把公共蒸馏预检纳入执行保障。 |
| `references/file-lookup-dictionary.md` / `references/file-lookup-dictionary-policy.json` | 修改 | 增加新策略与检查器的定位入口。 |
| `compass/tools/redcap-diagnose.sh` / `compass/tools/redcap-spec-check.sh` | 修改 | 接入新检查器，确保诊断和总回归会 fail-closed。 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 增加 targeted acceptance，并让 spec-check 传播新门禁失败。 |
| `references/pre-release-product-architecture-review.json` | 修改 | 同步新增 3 个包面文件后的 package candidate count。 |
| `compass/tools/redcap-clean-workspace-e2e.py` / `references/clean-workspace-install-e2e.json` | 修改 | closeout 发现新增包面文件让跨环境安装证据变旧后，补上报告类后续漂移白名单，并用干净 HEAD 重新生成 clean workspace install E2E 证据。 |
| `prism/reports/2026-05-06-public-distillation-preflight-route-review.md` / `prism/reports/index.yaml` | 新建 / 修改 | 记录 Claude Code + Copilot 的路线评审结论。 |

### 3.2 技术实现要点

公共蒸馏预检被设计成“先筛选，不落库”。它只允许 RedCap 判断哪些私有资产未来可能被重写成公共候选，禁止直接把原始报告、知识库、身份锚点或运行证据写入公共仓库。

检查器同时读取 RedCap Forge、信息架构、公共 arsenal claim 边界和 P4 任务树，防止某个文件单独改口。只要有人把 dry-run 改成 public write、去掉 secret scan、让公共库有实质条目，或删掉 P4-2h-0 任务锚点，回归就会失败。

本轮还同步修正了发布前产品架构审查和 clean workspace E2E 的包面证据。新增策略、检查器和 Prism 报告后，npm pack 候选文件从 218 变为 221；如果不更新，spec-check 会继续 fail-close。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| P4-2h-0 | `.dev-task.md` / `references/pre-release-structure-refactor-task-tree.json` | P4-2h 的安全前置切片，只证明“可以安全筛选”，不做真实公开沉淀。 |
| RedCap Forge | `references/redcap-forge-policy.json` | 把私有经验变成公共候选的流水线，核心职责是脱敏、去重、安全审查、索引和晋升决策。 |
| public distillation preflight | `references/public-distillation-preflight-policy.json` | 公共蒸馏前的体检门，确认现在只分类、不导出、不删除、不发布。 |
| redcap-arsenal | `../redcap-arsenal` | 外部公共能力库，目前仍是模板和用户命名空间占位，没有实质历史知识条目。 |

### 3.3 关联变更

P4-2h-0 新增了 3 个可打包文件，所以发布前产品架构审查的 package candidate count 必须从 218 同步到 221。这个变更不代表发布状态改变，只是让现有 release blocker 审查继续与真实包面一致。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 未来是否公开具体历史经验 | 本轮没有产生公共候选条目；未来若进入真实 promotion，需要 Norven 判断隐私、公开范围和团队共享边界。 | P1 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| public distillation preflight | `bash compass/tools/redcap-public-distillation-preflight.sh` | ✅ |
| file lookup dictionary | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | ✅ |
| execution guarantees | `bash compass/tools/redcap-execution-guarantee-check.sh` | ✅ |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh public-distillation-preflight-check` | ✅ |
| spec-check propagation | `bash compass/tools/redcap-multi-session-acceptance.sh spec-check-propagates-control-gate-failures` | ✅ |
| pre-release architecture | `bash compass/tools/redcap-pre-release-product-architecture-check.sh` | ✅ |
| clean workspace E2E | `bash compass/tools/redcap-clean-workspace-e2e.sh --write-result --timeout 180` | ✅ |
| spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | ✅ |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 未来真实公共候选条目的公开价值、隐私边界和团队共享策略需要 Norven 或后续专门任务判断。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 7/7 已完成 |
| 棱镜验收 | 通过，run `20260506-next-route-decision` |
| closeout summary | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/summaries/redcap-public-distillation-preflight-d81aa55d85f490ea3044b563f85bfe60adc8cbb38e7c59018ddf98fb2900c7ce.md` |
| closeout receipt | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/redcap-public-distillation-preflight-d81aa55d85f490ea3044b563f85bfe60adc8cbb38e7c59018ddf98fb2900c7ce.json` |
| rescue audit（如有） | 无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，Claude Code + Copilot 路线评审和 Prism acceptance binding 已通过 |
| 已正式完成 | 是，receipt 已生成 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 真实公共条目 promotion | 需要先有具体候选内容，并进行隐私、去重、公开价值和 append-only 审查。 | P1 |
| npm 正式发布 | 仍属于 P4-2 formal release task，需要独立发布边界和凭据决策。 | P2 |
| `prism/runs` 物理清理 | 证据清理必须单独评估保留价值，不能混入公共蒸馏预检。 | P2 |

### 6.2 触发的新问题

无新增必须立即处理的问题。包面计数漂移已经在本轮同步修复。

### 6.3 推荐的下一步行动

1. 后续若要继续公共知识库内容建设，另开 RedCap Forge promotion 任务。
2. 真实 npm 发布仍保持 deferred，需要独立 release readiness 任务判断。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| 无新增 Lesson | 本轮是既有 Forge / 信息架构原则的执行落地 | 已有经验足以覆盖，不新增 lessons.md，避免把报告结论重复沉淀成噪声。 |

### 7.2 流程改进建议

未来涉及“公开知识库变得更有内容”的任务，必须先通过 dry-run preflight，再进入真实 promotion；不要用公共仓库空不空来倒逼隐私边界放松。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选 | 本轮没有新失败模式或新方法论，只是固化既有公共蒸馏边界 | no-promote | `references/public-distillation-preflight-policy.json` |

---

## 八、附录

### 附录 A：Commits

```text
d986e4e feat(forge): 增加公共蒸馏预检强门
352a97d test(e2e): 接纳公共蒸馏报告后续漂移
c376e67 test(e2e): 刷新公共蒸馏安装验收
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| test | 下一步进入 P4-2h-0、npm 发布、prism/runs 清理还是停下来问用户 | 建议进入 P4-2h-0 dry-run preflight | `prism/reports/2026-05-06-public-distillation-preflight-route-review.md` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- RedCap Forge 策略：`references/redcap-forge-policy.json`
- 公共蒸馏预检策略：`references/public-distillation-preflight-policy.json`
- 父任务账本：`references/redcap-parent-task-ledger.md`
