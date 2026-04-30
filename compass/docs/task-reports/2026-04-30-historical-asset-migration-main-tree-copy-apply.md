# 任务完成报告：历史资产 main-tree copy-first apply

**报告日期**：2026-04-30  
**执行者**：Cap（Codex.app + Prism/Claude Code resource-limited review）  
**报告版本**：v1.0

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P4-1 已从 durable alias resolver 推进到 main-tree copy-first 私有副本创建，54 个旧 `compass/docs/**` 历史资产已复制到 `redcap-knowledge/**`。
- 详情：本轮解决的是“resolver 证明未来可复制，但真实 main tree 还没有副本”的缺口。现在 copy target 已真实存在、hash 与旧源一致，旧 `compass/docs/**` 仍全部保留并继续作为权威锚点。此次没有执行删除、移动、公开导出、canonical path 切换或 package release。

### 0.2 上一步完成的是

- 上一步完成的是：durable alias resolver 已落地；旧路径可解析为 canonical anchor，新路径可作为候选 target 查询，但当时所有 target 仍是 `planned-not-applied`。

### 0.3 下一步计划做的是

- 下一步计划做的是：另开 delete-last / canonical-switch 风险窗口前，复审 receipt anchor、docs catalog、local links、resolver、rollback 和 Prism verdict；父任务还剩正式公开发布与跨机器 clean workspace E2E。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：collection dry-run → file-level preflight → temp-copy rehearsal → true worktree rehearsal → durable alias resolver → main-tree copy-first apply → delete-last/canonical switch。
- 当前所在位置：`historical-asset-migration-main-tree-copy-apply` 已正式收口：Prism resource-limited review、全量回归、提交与 closeout receipt 均已完成；父任务仍保持 incomplete。

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 好的，那么请继续推进主任务线，务必要和棱镜团队之间配合好，稳步迭代、谨慎评审与验收

### 1.2 触发背景

上一轮 resolver 切片已经证明“旧路径权威、新路径候选”的解析模型可工作，但它并没有创建真实副本。父任务账本也明确 P4-1 的下一刀是 main-tree apply 风险窗口。本轮因此只推进最保守的物理动作：copy-first 到私有目录，不进入删除或公开共享。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | partial-with-explicit-defer |
| 原始意图 | 继续推进主任务线，并与棱镜团队配合完成谨慎评审与验收 |
| 已覆盖 | 建立 main-tree copy-first apply 工具、真实创建私有候选副本、刷新 resolver applied 状态、接入控制面验收 |
| 未覆盖/延期 | 不做 delete-last，不改变 canonical path，不写入公共 `redcap-arsenal`，不发布 runtime/package，不关闭父任务 |
| 用户可见边界 | 本轮只代表历史资产私有副本已创建且旧锚点仍安全，不代表历史资产已经从执行层删除或公开共享 |
| 后续路径 | copy-first apply 通过后，父任务仍需另开 delete-last / public release / clean workspace E2E 风险窗口 |

## 二、方案讨论

### 2.1 问题分析

历史资产治理如果直接 move/delete，会同时威胁三件事：旧 task report/receipt 的考古锚点、docs catalog 的渐进式披露入口，以及未来公共知识库的隐私边界。copy-first 是当前最安全的中间态，因为它让我们获得真实副本，同时保持旧路径权威和可回滚。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|---|---|---|---|
| Q1 | 只保留 resolver，不执行 apply | 停在 planned target 状态 | 风险最低 | 父任务物理迁移继续没有实质进展 |
| Q1 | copy-first 私有 apply | 只复制到 `redcap-knowledge/**`，旧路径不动 | 有真实副本、可回滚、隐私边界清楚 | 仍需要后续 delete-last/canonical switch |
| Q1 | 直接 move/delete | 把旧 docs 迁到新位置 | 表面上最干净 | 断锚和误删风险过高，不符合当前安全证据 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---|---|---|
| Q1 | copy-first 私有 apply | 它能推进真实物理迁移，同时不牺牲旧锚点、receipt、catalog 和 rollback 安全 | CAP_DECIDE |

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|---|---|---|
| `redcap-knowledge/**` | 新建 | 54 个 copy-first 私有副本，hash 与旧源一致 |
| `references/legacy-asset-migration-main-tree-apply.json` | 新建 | main-tree copy-first apply receipt |
| `compass/tools/redcap-legacy-asset-main-tree-apply.py` / `.sh` | 新建 | apply、check-result、rollback 和 resolver refresh 工具 |
| `compass/tools/redcap-legacy-asset-migration-apply-plan.py` | 修改 | 跳过当前活跃 task report，允许已应用且 hash 一致的 copy target |
| `compass/tools/redcap-legacy-asset-migration-rehearsal.py` / `redcap-legacy-asset-migration-worktree-rehearsal.py` | 修改 | post-apply 支持 stored-result-only 校验 |
| `compass/tools/redcap-execution-layer-split-check.py` | 修改 | post-apply 后允许已明确延期的 split target 做安全路径校验，而不是继续要求 target 必须物理缺席 |
| `compass/tools/redcap-spec-check.sh` / `redcap-diagnose.sh` / `redcap-multi-session-acceptance.sh` | 修改 | 接入 main-tree apply gate 与 acceptance |
| `references/*.json` / `references/file-lookup-dictionary.md` | 修改 | 更新执行保障、token 治理、父任务账本和查找字典 |
| `compass/knowledge/lessons.md` | 修改 | 新增 L-146、L-147 |

### 3.2 技术实现要点

main-tree apply 工具只接受 worktree rehearsal 的 alias map，并逐项验证 plan source、target、source hash、target hash 和旧路径保留状态。它不会根据目录扫描自由复制文件，避免把未审计文件带入迁移。

apply 后 resolver 被刷新为 `applied-copy-present`，但 `canonical_path` 仍等于旧路径。这让接盘 Agent 能知道副本真实存在，同时不会误把新路径当成权威入口。

pre-apply rehearsal 在副本创建后不能再 live 要求 target 不存在，否则会误报。因此 post-apply 阶段改为校验 stored rehearsal receipt，而实时安全由 main-tree apply receipt 承担。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|---|---|---|
| copy-first apply | `redcap-legacy-asset-main-tree-apply.sh` | 先复制新副本、不删除旧文件的安全迁移方式 |
| old authoritative anchor | `references/legacy-asset-migration-alias-resolver.json` | 旧 `compass/docs/**` 路径仍是 receipt 和 catalog 的权威锚点 |
| applied-copy-present | alias resolver target state | 新 `redcap-knowledge/**` 副本已经真实存在且 hash 对得上 |
| stored-result-only | rehearsal checker mode | apply 后不再 live 复演“target 不存在”，只校验当时的 rehearsal receipt |
| rollback plan | main apply receipt | 只允许删除新副本，不允许碰旧源文件 |

### 3.3 关联变更

本轮同步更新父任务聚合策略，把 `P4-1a` 作为已完成子任务接入，但父任务仍因 delete-last/canonical switch、public release 和 clean E2E 不可 complete。File Lookup Dictionary 与 token governance 也加入 main apply receipt，避免接盘者为了找证据 bulk-read 整个迁移目录。

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|---|---|---|---|
| 1 | 是否进入 delete-last/canonical switch | 这是删除旧锚点的高风险决策，需要另开任务并重新评审 | P1 |
| 2 | 是否做 public release / clean E2E | 涉及外部发布边界、凭证和干净环境，不在本轮自动推进 | P2 |

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|---|---|---|
| 语法检查 | `python3 -m py_compile ... && bash -n ...` | 通过 |
| main apply check | `bash compass/tools/redcap-legacy-asset-main-tree-apply.sh --check-result` | 通过 |
| resolver check | `bash compass/tools/redcap-legacy-asset-alias-resolver.sh --check-result` | 通过，applied=54 |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh legacy-asset-main-tree-apply` | 通过 |
| 控制面专项 | file lookup / execution guarantees / token risk / parent aggregation | 通过 |
| Prism review | `prism/runs/20260430-historical-asset-migration-main-tree-copy-apply` | resource-limited 通过：Claude Code 高置信、无 blocker；Gemini/Kimi/Copilot/Codex 不可用或冻结证据已绑定 |
| full regression | `redcap-spec-check` / `redcap-diagnose` / `acceptance all` | 通过；第一次 full acceptance 暴露父任务聚合 fixture 未覆盖新增 P4-1a 的问题，修复后第二轮完整通过；acceptance residue 已用 lifecycle 工具清理并复验 |
| closeout preflight | `./closeout-cap.sh complete ...` | 首次 closeout 被 token-risk gate 拦截：新增 `redcap-knowledge` 大文件缺少结构化治理；已补治理策略并复验 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- 无当前必须人工验证项；delete-last、公网发布和跨机器 E2E 将在后续独立任务中再确认。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|---|---|
| 执行承诺账本 | 已核对：6/6 完成，pending=0 |
| 棱镜验收 | 已绑定：`resource-limited-pass`，1 个 Claude reviewer responded，额外 provider 不可用证据齐全 |
| closeout summary | 已生成：runtime summary 存于本地 `/tmp/redcap/project/.../closeout-runtime/summaries/` |
| closeout receipt | 已生成：`historical-asset-migration-main-tree-copy-apply-1cf7042428ed6f77d4baf58a4491155a08c6fcdb781ac0b0ef883d6d5fbf2103.json` |
| rescue audit（如有） | 首次 closeout 因 token-risk 治理缺口被拦截；已补治理并重新 closeout 成功 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|---|---|
| 已实现 | 是：copy-first apply 已落地 |
| 已自检 | 是：targeted 与控制面专项已通过 |
| 已独立验收 | 是：Prism resource-limited 验收通过，无 blocker |
| 已正式完成 | 是：closeout receipt 已生成，pending closure 已清 |

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|---|---|---|
| delete-last / canonical switch | 删除旧锚点风险高，必须另开任务重审 | P1 |
| public release | 需要发布目标、凭证和包名边界 | P2 |
| clean workspace E2E | 需要干净目标环境 | P2 |

### 6.2 触发的新问题

活跃 task report 不适合同轮迁移，已通过 apply-plan exclusion 固化；apply 后旧 rehearsal 的 live 语义也已改为 stored receipt 校验。全量 acceptance 还暴露出父任务聚合用例在切换“当前 child”测试时没有给新增的 `P4-1a` 补 fixture receipt，已修正为先补齐其它已完成 child 的 receipt，再验证当前 child pre-receipt 语义。

### 6.3 推荐的下一步行动

1. 后续如继续历史资产治理，应单独立项 delete-last / canonical switch。
2. public release 与 clean workspace E2E 仍保持父任务后续风险窗口，不在本轮冒充完成。

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|---|---|---|
| L-146 | copy-first apply 的 receipt 只能记录稳定事实 | receipt 不记录幂等命令过程数，只记录可长期对账的状态 |
| L-147 | 活跃任务报告不要参加同一轮历史资产迁移 | 当前报告会持续变化，应留给下一轮迁移 |

### 7.2 流程改进建议

后续所有“先演练、再 apply”的机制都要定义 apply 前后 gate 语义变化：apply 前可以 live 验证 target 不存在，apply 后应改为 receipt 对账与实时 target/hash 检查。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|---|---|---|---|
| 无新增候选 | 测试失败与实现复验 | no-promote：已直接固化为工具行为与 lessons | `compass/knowledge/lessons.md` |

## 八、附录

### 附录 A：Commits

```
ad116bb feat(legacy-assets): 执行 main-tree copy-first apply
8f36e38 fix(token-risk): 补齐 redcap-knowledge 大文件治理
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|---|---|---|---|
| review | main-tree copy-first apply 安全性 | Claude Code 高置信无 blocker；建议提交前跑 full regression、回填报告并绑定 acceptance，均已纳入本轮收口动作 | `prism/runs/20260430-historical-asset-migration-main-tree-copy-apply/` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- 父任务账本：`references/redcap-parent-task-ledger.md`
- 关键 receipt：`references/legacy-asset-migration-main-tree-apply.json`
