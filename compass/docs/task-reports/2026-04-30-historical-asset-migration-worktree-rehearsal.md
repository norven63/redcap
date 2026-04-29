# 任务完成报告：Historical asset migration true worktree rehearsal

**报告日期**：2026-04-30
**执行者**：Cap（Codex.app + Prism: Kimi initial review / Claude Code final review）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P4-1 已从“临时 copy-first 演练”推进到“真实 git worktree 演练可机器验证”，但 main tree 历史资产仍未真实迁移、删除或导出到公共库。
- 详情：本轮解决的是“临时目录演练还不等于真实 git worktree 隔离演练”的问题。新 gate 会创建 detached throwaway worktree，在里面复制 copy-first target、验证 hash、旧路径、alias overlay、docs catalog 旧锚点和 rollback，再清理 worktree，并证明 main tree 状态没有被演练改变。

### 0.2 上一步完成的是

- 上一步完成的是：P4-1 temp-copy rehearsal 已证明 copy-first 可以在临时沙箱中复制、回滚，并阻断危险 manifest。

### 0.3 下一步计划做的是

- 下一步计划做的是：把 alias overlay 接入持久 docs/catalog resolver，再为 main-tree apply 另开风险窗口；真实 move/delete/public export 仍不在本轮执行。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：collection dry-run → file-level preflight → temp-copy apply rehearsal → true throwaway-worktree rehearsal → durable catalog/link resolver alias → main-tree apply risk window。
- 当前所在位置：P4-1 `historical-asset-migration-worktree-rehearsal` 已通过实现、棱镜审查和回归验收，正在执行提交与 closeout receipt 收口；父任务仍因真实 apply、public release、clean workspace E2E 保持 incomplete。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 好的，那么请继续推进主任务线，务必要和棱镜团队之间配合好，稳步迭代、谨慎评审与验收

### 1.2 触发背景

上一轮 temp-copy rehearsal 证明“复制动作本身”可以在临时目录中安全执行，但它仍没有走 git worktree 这条更接近真实施工环境的路径。历史资产迁移一旦进入 main tree 风险窗口，会影响 docs catalog、receipt anchor、任务报告考古和后续回滚。因此本轮先把真实 worktree 演练变成机器 gate，让后续迁移不再依赖口头确认。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | partial-with-explicit-defer |
| 原始意图 | 继续推进主任务线，并使用棱镜协作、评审与回归保证质量。 |
| 已覆盖 | 已建立真实 git worktree rehearsal 工具、机器结果、acceptance/spec/diagnose 接线、文件字典、执行保障、父任务状态面和 Prism resource-limited final review。 |
| 未覆盖/延期 | 不执行 main-tree 真实迁移，不删除旧历史资产，不向 `redcap-arsenal` 导出 raw history，不发布 npm/runtime，不关闭父任务。 |
| 用户可见边界 | “worktree 演练通过”不等于“资产已迁移”。 |
| 后续路径 | 继续将 alias overlay 接入持久 catalog/link resolver，并另立 main-tree apply 风险窗口。 |

---

## 二、方案讨论

### 2.1 问题分析

历史资产迁移不能只证明“文件能复制”。它还要证明复制发生在隔离环境、主工作树没有被污染、旧 task-report anchor 没有从 docs catalog 消失、alias overlay 能把旧路径指向候选新路径、rollback 只删除 copy target 而不碰 source。缺少这些证据时，真实迁移会把考古能力和 closeout receipt 暴露在不可控风险里。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 直接 main-tree apply | 在主工作树里创建 copy target 或移动文件 | 推进最快 | 风险窗口过大，失败后难区分工具 bug 与真实污染 |
| Q1 | 继续只跑 temp-copy | 保留上一轮临时目录演练 | 安全、简单 | 不够接近真实 git 施工环境 |
| Q1 | true git-worktree rehearsal | 临时 `git worktree add --detach`，在隔离 worktree 中执行 copy-first、catalog/alias/rollback 校验 | 接近真实 apply，且不触碰 main tree | 仍不是正式迁移；alias resolver 持久接入需下一步 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | true git-worktree rehearsal | 它把真实施工环境、隔离性和回滚证据统一到一个可重复 gate 中，同时避免直接污染主树。 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `.dev-task.md` | 修改 | 切换为 worktree rehearsal 任务卡，锁定本轮边界、漂移哨兵和承诺账本。 |
| `compass/tools/redcap-legacy-asset-migration-worktree-rehearsal.py` | 新建 | 创建 detached git worktree，执行 copy-first 演练、catalog old-anchor 校验、alias overlay 校验、rollback 和 stale result 检查。 |
| `compass/tools/redcap-legacy-asset-migration-worktree-rehearsal.sh` | 新建 | worktree 演练 shell 入口。 |
| `references/legacy-asset-migration-worktree-rehearsal.json` | 新建 | 本轮真实 git worktree 演练结果。 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 增加 worktree rehearsal acceptance，覆盖成功演练、stale result、非 git root、危险操作和已有 target。 |
| `compass/tools/redcap-spec-check.sh` / `compass/tools/redcap-diagnose.sh` | 修改 | 将 worktree rehearsal 纳入总回归和诊断。 |
| `references/file-lookup-dictionary.md` / `references/file-lookup-dictionary-policy.json` | 修改 | 登记 worktree rehearsal 结果和工具，维持按需定位。 |
| `references/execution-guarantees.json` | 修改 | 新增 worktree rehearsal 执行保障规则。 |
| `references/legacy-asset-migration-dry-run.json` | 修改 | 同步新增 task report 与 lesson 后的历史资产 dry-run 统计，保持迁移清单自洽。 |
| `references/redcap-parent-task-ledger.md` / `references/parent-receipt-aggregation-policy.json` | 修改 | 父任务状态更新为“true git-worktree rehearsal 已落地，真实 main-tree apply 仍 deferred”。 |
| `references/token-structural-governance.json` | 修改 | 登记 worktree result 为生成型证据，要求通过字典和 checker 渐进式读取。 |

### 3.2 技术实现要点

worktree rehearsal 的核心是“真实隔离，而不是口头隔离”。工具会记录 main tree 的 git status digest，创建 detached 临时 worktree，在 worktree 里创建 copy target，校验 source/target hash 一致，然后生成 alias overlay 与 rollback plan。rollback 执行后，工具会验证 source 仍存在、target 已清理、main tree target 从未出现，最后移除临时 worktree。

docs catalog 校验目前采取保守策略：旧 `compass/docs/task-reports/**` 仍是 authoritative anchor，worktree 生成的 docs catalog 必须继续包含这些旧路径；新 `redcap-knowledge/**` target 由 alias overlay 解析验证。也就是说，本轮证明“旧锚点不丢 + 新 target 可解析”，但不把 alias overlay 永久接入 docs catalog，这留给下一道更小、更可审的 resolver 任务。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| true git-worktree rehearsal | `redcap-legacy-asset-migration-worktree-rehearsal.py` | 在临时 git worktree 中模拟真实复制，尽量接近正式施工，但不改主工作树。 |
| alias overlay | `references/legacy-asset-migration-worktree-rehearsal.json` | 旧路径到候选新路径的映射层；当前是演练证据，后续才会接入持久 resolver。 |
| docs catalog old anchor | `compass/docs/catalog.json` / worktree 临时 catalog | 旧任务报告路径仍能被 docs catalog 找到，receipt 和考古不会突然断线。 |
| main_tree_status_unchanged | worktree result safety check | 演练前后主工作树状态一致，证明演练没有污染主树。 |

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 暂无必须人工介入项 | 本轮仍只做隔离演练和机器门禁，没有进入真实资产搬迁、公共库导出或 release 发布。 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 入口门禁 | `redcap-pm-gate-check / intent-coverage / change-intake` | ✅ |
| worktree 演练器真实清单 | `bash compass/tools/redcap-legacy-asset-migration-worktree-rehearsal.sh --write-result --check-result` | ✅ |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh legacy-asset-migration-worktree-rehearsal` | ✅ |
| spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | ✅ |
| diagnose | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | ✅ |
| full acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh all` | ✅ |
| Prism review | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | ✅ resource-limited-pass |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 无本轮必须人工验证项；真实 main-tree apply 前需要单独风险窗口。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 已清；closeout runtime 可读取 6/6 已完成 |
| 棱镜验收 | resource-limited-pass；Kimi 初审抓到 blocker，修复后 Kimi 429，Claude final review 复核通过 |
| closeout summary | 待提交后生成 |
| closeout receipt | 待提交后生成 |
| rescue audit（如有） | 待 closeout 判定 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，Prism resource-limited-pass |
| 已正式完成 | 否，提交后 closeout receipt 才是唯一正式完工凭证 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| durable catalog/link resolver alias 接入 | 本轮只证明 alias overlay 可用；持久解析语义需要单独设计和评审，避免误改 docs 考古入口。 | P1 |
| main-tree apply | 必须等待 durable resolver、receipt anchor 复验、rollback review 与 Prism 复审。 | P1 |

### 6.2 触发的新问题

Kimi 初审抓到一个真实 blocker：`git worktree remove --force` 失败会被静默吞掉，可能让文件系统目录被清理但 git worktree registry 留下脏引用。该问题已修复为 fail-closed：只有 git remove 成功才清理父目录，并额外检查 `git worktree list --porcelain` 不再包含临时路径。Claude final review 复核认为原 blocker 已解除，无新增 blocker。

首次 closeout 时，drift gate 又抓到任务卡允许范围漏列 `references/legacy-asset-migration-dry-run.json`。这不是 gate 误报，而是 dry-run 统计确实随新增报告/lesson 同步更新；已把它补回任务卡与本报告的变更说明，避免用不完整账本收口。

### 6.3 推荐的下一步行动

1. 下一刀进入 durable alias/link resolver，让旧路径锚点和候选新路径解析从“演练证据”进入持久机制。
2. resolver 通过后，再单独开启 main-tree apply 风险窗口；不要直接跳到真实迁移。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-144 | 迁移演练要同时证明隔离环境和旧锚点不丢 | 文件迁移类任务不能只校验 hash；还要校验主树不变、旧锚点仍可查、新 target 可由 alias 层解析。 |

### 7.2 流程改进建议

暂无新增流程改动；本轮沿用“任务卡 → 机器门禁 → targeted acceptance → Prism → 全量回归 → closeout receipt”的 Layer B 主链，并在 full acceptance 后清理 acceptance fixture 残留，避免测试夹具污染正式 lifecycle gate。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| worktree rehearsal 安全模板 | Kimi blocker + Claude final review | no-promote；已沉淀为 L-144，暂不升格为 skill，避免为单一迁移阶段过早抽象 | `compass/knowledge/lessons.md#l-144` |

---

## 八、附录

### 附录 A：Commits

```
待提交
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| Kimi initial review | Historical asset migration worktree rehearsal review | 发现 worktree remove 静默失败 blocker；已修复 | `prism/runs/20260430-historical-asset-migration-worktree-rehearsal/collect/kimi-reviewer/raw.txt` |
| Claude final review | Kimi blocker fix follow-up | 原 blocker 已解除，0 blocker | `prism/runs/20260430-historical-asset-migration-worktree-rehearsal/collect/claude-reviewer/parsed.json` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- 演练结果：`references/legacy-asset-migration-worktree-rehearsal.json`
