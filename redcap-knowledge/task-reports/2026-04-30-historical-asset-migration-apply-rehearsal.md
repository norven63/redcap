# 任务完成报告：Historical asset migration apply rehearsal

**报告日期**：2026-04-30
**执行者**：Cap（Codex.app + Prism: Kimi CLI / Claude Code）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P4-1 已从“文件级 preflight”推进到“临时 copy-first 演练可机器验证”，但 main tree 历史资产仍未真实迁移、删除或导出到公共库。
- 详情：本轮解决的是“真实迁移前仍缺一次可回滚演练”的问题。演练器读取现有文件级施工清单，只在临时沙箱中复制 `copy-first` 项，验证 source/target hash 一致、旧路径保留、alias map 与 rollback plan 一一对应，并确认 main tree 没有出现目标文件。它还会先扫描全量 manifest，因此即使危险项不属于 copy-first 执行集合，也会被 fail-closed 拦截。

### 0.2 上一步完成的是

- 上一步完成的是：P4-1 file-level apply preflight 已随本轮报告同步刷新为 87 个文件级条目，明确哪些文件可 copy-first、哪些只能 preserve / blocked-translate / retention-check-only，并阻断 delete/move/public export 等危险计划。

### 0.3 下一步计划做的是

- 下一步计划做的是：真实迁移仍需另开风险窗口，在真实 throwaway worktree 中复验 alias/link map、docs catalog、receipt anchor 和 rollback，再决定是否进入 main-tree apply。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：collection dry-run → file-level preflight → temp-copy apply rehearsal → true throwaway-worktree rehearsal → catalog/link/receipt/rollback 复验 → main-tree apply。
- 当前所在位置：P4-1 `historical-asset-migration-apply-rehearsal` 正在收口；父任务仍因真实 apply、public release、clean workspace E2E 保持 incomplete。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 好的，那么请继续推进主任务线，务必要和棱镜团队之间配合好，稳步迭代、谨慎评审与验收

### 1.2 触发背景

父任务 P4-1 的下一步是历史资产真实迁移，但 RedCap 过去已经多次暴露“文档/证据/索引迁移不能靠口头确认”的风险。上一轮 preflight 只证明施工清单安全，还没有证明 copy-first 动作本身可执行、可回滚、不会污染 main tree。因此本轮先做临时演练门，把真实迁移前的执行风险压到可验证状态。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | partial-with-explicit-defer |
| 原始意图 | 继续推进主任务线，并使用棱镜协作、评审与回归保证质量。 |
| 已覆盖 | 已建立临时 copy-first 演练工具、机器结果、acceptance/spec/diagnose 接线、文件字典、执行保障、父任务状态面、棱镜评审处置和经验沉淀。 |
| 未覆盖/延期 | 不执行 main-tree 真实迁移，不删除旧历史资产，不向 `redcap-arsenal` 导出 raw history，不关闭父任务。 |
| 用户可见边界 | “演练通过”不等于“资产已迁移”。 |
| 后续路径 | 真实迁移前继续做 true throwaway-worktree rehearsal，并把 alias/link map 接入 docs catalog / link resolver 后再讨论 main-tree apply。 |

---

## 二、方案讨论

### 2.1 问题分析

历史资产迁移的风险不只是“文件能不能复制”。更关键的是：旧路径是不是仍可作为 receipt anchor 追溯、候选新路径会不会覆盖现有文件、公共库会不会误收 raw history、回滚是否只删除 copy target 而不触碰 source。若这些问题只靠人工读报告，很容易在长任务中漏掉。因此本轮把演练变成可重复执行的机器检查。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 直接进入 main-tree apply | 按 preflight 计划在主工作树中复制/移动 | 表面推进最快 | 风险窗口过大，容易断 receipt/catalog/link anchor |
| Q1 | 只保留 preflight | 不做演练，等待下一轮再处理 | 安全 | 无法验证 apply 动作本身 |
| Q1 | temp-copy rehearsal | 在临时沙箱复制 copy-first 项，验证 hash/alias/rollback/no-mutation | 可自动回归、不会污染主树 | 仍不是完整真实 worktree 迁移 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | temp-copy rehearsal | 它能在不触碰 main tree 的前提下验证最关键的迁移动作，并为后续 true worktree rehearsal 提供机器基线。 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `.dev-task.md` | 修改 | 切换为 P4-1 apply rehearsal 任务卡，锁定本轮边界、漂移哨兵和承诺账本。 |
| `compass/tools/redcap-legacy-asset-migration-rehearsal.py` | 新建 | 执行临时 copy-first 演练、全量危险项扫描、alias map、rollback 和 result 校验。 |
| `compass/tools/redcap-legacy-asset-migration-rehearsal.sh` | 新建 | 演练器 shell 入口。 |
| `references/legacy-asset-migration-apply-rehearsal.json` | 新建 | 本轮真实 preflight manifest 的机器演练结果。 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 增加 rehearsal acceptance，覆盖成功演练、apply_allowed、move、路径逃逸、public target、重复 target、已有 target。 |
| `compass/tools/redcap-spec-check.sh` / `compass/tools/redcap-diagnose.sh` | 修改 | 将 rehearsal 纳入总回归和诊断。 |
| `references/file-lookup-dictionary.md` / `references/file-lookup-dictionary-policy.json` | 修改 | 登记 rehearsal 结果和工具，维持按需定位。 |
| `references/execution-guarantees.json` | 修改 | 新增 rehearsal 执行保障规则。 |
| `references/redcap-parent-task-ledger.md` / `references/parent-receipt-aggregation-policy.json` | 修改 | 父任务状态更新为“temp-copy rehearsal 已落地，真实 main-tree apply 仍 deferred”。 |
| `references/token-structural-governance.json` | 修改 | 登记 rehearsal 结果为生成型大文件，要求通过字典和 checker 渐进式读取。 |
| `compass/knowledge/lessons.md` | 修改 | 沉淀“只处理安全项的工具也必须先扫描危险项”。 |

### 3.2 技术实现要点

演练器把“迁移计划”拆成两层处理。第一层先扫描 manifest 全部条目，任何 `delete`、`move`、public target、路径逃逸、unsafe flags 都会直接失败；第二层才只对 `copy-first` 项做临时沙箱复制。这避免了“危险项没有被执行，所以可以留在计划里”的漏洞。

演练结果不是人类说明，而是机器可复验的 receipt-like 证据。它记录 source manifest hash、copy-first 数量、alias map 数量、rollback 数量、task report anchor 数量，并要求 `main_tree_mutated=false`。后续真实 worktree rehearsal 可以拿它做基线对账。

本轮仍刻意不做主树迁移。因为 docs catalog/link resolver/receipt anchor 的旧路径 alias 还没有接入真实解析链，贸然移动历史资产会让考古能力和 closeout 证据链承担不必要风险。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| temp-copy rehearsal | `redcap-legacy-asset-migration-rehearsal.py` | 在临时目录里模拟复制，不改主工作树，用来证明复制和回滚动作本身可行。 |
| alias map | `references/legacy-asset-migration-apply-rehearsal.json` | 旧路径到候选新路径的映射表，后续 catalog/link resolver 必须用它保护旧锚点。 |
| rollback plan | 同上 | 如果演练创建了 copy target，回滚只删除这些 target，不允许删除 source。 |
| main_tree_mutated=false | 同上 | 本轮演练没有在 RedCap 主工作树创建迁移目标或移动历史资产。 |

### 3.3 关联变更

`spec-check`、`diagnose` 和 acceptance 都接入了 rehearsal，这让它成为后续收口的持续门禁，而不是一次性脚本。Kimi 评审指出 `--check-result` 不能只检查缓存结构，因此现在会把已落盘 result 与 live rehearsal 的 manifest hash、summary、safety checks、alias map、rollback plan 对齐；只要 manifest 或 source 变化，旧 result 会被判定为 stale。文件字典和 token 治理也同步登记，避免新生成的 alias map 自己变成新的默认首读大文件。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 暂无必须人工介入项 | 本轮只做临时演练和机器门禁，没有进入真实资产搬迁、公共库导出或 release 发布。 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 入口门禁 | `redcap-pm-gate-check / intent-coverage / change-intake / drift-check` | ✅ |
| 演练器真实清单 | `bash compass/tools/redcap-legacy-asset-migration-rehearsal.sh --write-result --check-result` | ✅ |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh legacy-asset-migration-rehearsal` | ✅ |
| 关联迁移门 | `bash compass/tools/redcap-multi-session-acceptance.sh legacy-asset-migration-apply-preflight` | ✅ |
| spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | ✅ |
| diagnose | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | ✅ |
| full acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh all` | ✅ |
| Prism review | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | ✅ |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 无本轮必须人工验证项；真实 main-tree apply 前需要单独风险窗口。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 收口前核对 |
| 棱镜验收 | 已通过；Kimi + Claude Code，0 blocker |
| closeout summary | 待生成 |
| closeout receipt | 待生成 |
| rescue audit（如有） | 待 closeout 判定 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，Prism acceptance pass |
| 已正式完成 | 否，receipt 是唯一正式完工凭证 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| true throwaway-worktree rehearsal | 本轮先做 temp-copy 基线；真实 worktree 复验需在下一风险窗口执行，避免和工具接线混在一起扩大改动面。 | P1 |
| docs catalog / link resolver alias 接入 | 本轮产出 alias map，但不改解析语义，避免还没评审就改变 docs 考古路径。 | P1 |
| main-tree apply | 必须等待 true rehearsal、alias 接入、receipt anchor 复验和 rollback review。 | P1 |

### 6.2 触发的新问题

targeted acceptance 发现第一版演练器只执行 copy-first，却没有先扫描全量 manifest；这个缺口已修复并沉淀为 L-143。棱镜随后又指出缓存 result 可能 stale、item 级安全旗标和 guard 缺失回归不足、symlink containment 不够严；这些缺口已在本轮修复并回归通过。

### 6.3 推荐的下一步行动

1. 使用棱镜复审本轮 rehearsal 安全边界，尤其是“temp-copy 是否足够作为下一刀，还是必须立即补 true worktree 模式”。
2. 若棱镜通过，下一刀进入 alias/link resolver 和 docs catalog old-path mapping 设计，而不是直接 main-tree apply。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-143 | “只处理安全项”的工具也必须先扫描危险项 | apply/rehearsal 工具必须先审计全量 manifest，再执行允许集合。 |

### 7.2 流程改进建议

暂无新增流程改动；本轮沿用“任务卡 → 机器门禁 → targeted acceptance → Prism → 全量回归 → closeout receipt”的 Layer B 主链。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选 | 本轮缺口已直接沉淀为 lesson，不需要升格为 skill。 | no-promote | `compass/knowledge/lessons.md` |

---

## 八、附录

### 附录 A：Commits

```
本报告随 `historical-asset-migration-apply-rehearsal` 本次提交归档。
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| Kimi + Claude Code | Historical asset migration apply rehearsal review | 初审发现 stale-result、guard、item flags、symlink containment 风险；已修复并绑定 acceptance，当前 0 blocker | `prism/runs/20260430-historical-asset-migration-apply-rehearsal/` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- 演练结果：`references/legacy-asset-migration-apply-rehearsal.json`
