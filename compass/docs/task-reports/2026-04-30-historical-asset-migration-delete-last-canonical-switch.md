# 任务完成报告：历史资产 delete-last / canonical-switch 风险窗口

**报告日期**：2026-04-30
**执行者**：Cap（Codex）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P4-1 的 private delete-last / canonical switch 已完成。54 个旧 `compass/docs/**` 历史锚点已通过 preflight、Prism review、guarded apply、catalog 刷新和 resolver 复验后退休。
- 详情：旧历史文件不再作为 docs catalog 的普通入口；`redcap-knowledge/**` 中的私有副本成为迁移资产的 canonical path，旧路径只通过 alias resolver 和 receipt correspondence 承担历史对账角色。
- 详情：`references/legacy-asset-delete-last-apply.json` 是本轮物理收据，证明旧锚点已删除、新副本 hash 一致且可从私有副本回滚；`references/legacy-asset-delete-last-preflight.json` 当前状态为 `APPLIED`，而不是删除前 `READY`。

### 0.2 上一步完成的是

- 上一步完成的是：`historical-asset-migration-main-tree-copy-apply` 已创建 54 个私有副本，并保持旧 `compass/docs/**` 作为权威锚点。

### 0.3 下一步计划做的是

- 下一步计划做的是：继续父任务线的剩余边界，即 P4-2 正式 public release / package publish 和 P4-3 clean workspace / cross-machine E2E；这两项不属于本轮 P4-1 完成声明。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：collection dry-run → file-level preflight → temp-copy rehearsal → true worktree rehearsal → durable alias resolver → main-tree copy-first apply → delete-last/canonical-switch preflight → guarded delete-last apply。
- 当前所在位置：guarded delete-last apply 已执行并通过 post-delete resolver/catalog/checker 对账；父任务仍因 P4-2/P4-3 保持 incomplete。

---

## 一、需求背景

P4-1 的核心风险不是“文件能不能移动”，而是“旧路径是不是还被活跃控制面当作真相源”。如果直接删除，README、索引、验收脚本或机器账本中的旧路径可能会变成断链，导致新会话考古失败或回归误判。

因此本轮先做一个 fail-closed 的机器闸门：能证明安全时才允许继续，不安全时输出精确 blockers，而不是把自然语言判断包装成完成。

## 二、方案讨论

方案采用三层判断。

第一层是 hash 与副本完整性：每个旧路径都必须对应一个私有 `redcap-knowledge/**` 副本，且 hash 与 main-tree copy-first receipt 一致。

第二层是引用分类：迁移 receipt、历史 receipt 对应关系、acceptance alias 兼容引用可以保留；README、ARCHITECTURE、registry、evolution、execution guarantees 等活跃控制面不能继续把旧历史文件当 canonical。

第三层是 catalog 与 resolver 转场：删除前 catalog 列旧文件是合理现象；删除后 catalog 必须不再列旧文件，resolver 必须把旧路径解析到新的 `redcap-knowledge/**` canonical path。

## 三、落地结果

### 3.1 本次完成

- 建立了 `redcap-legacy-asset-delete-last-preflight`，输出 ready/blocked 两类可机读结果。
- 建立了 `redcap-legacy-asset-delete-last-apply`，只在 preflight ready 且 hash/路径边界全部满足时退休旧锚点，并写入 rollback-capable receipt。
- 将 preflight 与 apply 接入 spec-check、diagnose、acceptance、文件查找字典和 execution guarantees。
- 把活跃控制面中可迁移的旧历史文件引用切换到 `redcap-knowledge/**`。
- 明确保留 parent receipt policy 的历史路径引用作为 receipt correspondence；当旧报告文件已退休时，parent checker 会通过 alias resolver 验证新 canonical 文件仍存在。
- 执行物理 delete-last：旧 `compass/docs/**` 中 54 个已迁移历史文件退休，`compass/docs/catalog.json` 刷新后只保留当前 docs 入口。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| delete-last preflight | `redcap-legacy-asset-delete-last-preflight.sh` | 删除旧历史文件前后的体检单；删除前证明 ready，删除后证明 applied |
| delete-last apply | `redcap-legacy-asset-delete-last-apply.sh` | 真正执行旧锚点退休并写收据的安全施工入口 |
| active hard reference | `reference_scan[].classification` | 还在活跃控制面里把旧路径当可用入口的引用 |
| historical receipt reference | `references/parent-receipt-aggregation-policy.json` | 为了核对旧收据内容而保留的事实引用，不代表旧路径仍是 canonical |
| catalog transition | `compass/docs/catalog.json` | 删除后旧文件不能再出现在 docs catalog |
| alias resolver | `references/legacy-asset-migration-alias-resolver.json` | 旧路径退休后，把历史旧路径解析到新的私有 canonical path |

## 四、人工审核要点

本轮没有需要用户立即决策的 blocker。需要注意的是：P4-1 只完成 private historical asset canonical switch；不包含 public export、npm publish 或跨机器安装 E2E。

## 五、验证结果

- 已运行：`bash compass/tools/redcap-legacy-asset-delete-last-apply.sh --apply --write-result --check-result`
- 当前输出：`LEGACY_ASSET_DELETE_LAST_APPLY_OK entries=54 deleted=54 retired=54`
- 已运行：`bash compass/tools/redcap-legacy-asset-delete-last-preflight.sh --write-result --check-result`
- 当前输出：`LEGACY_ASSET_DELETE_LAST_PREFLIGHT_APPLIED entries=54 hard_reference_file_count=0 blockers=0`
- 已运行：`bash compass/tools/redcap-spec-check.sh "$PWD"` 与 `bash compass/tools/redcap-diagnose.sh .dev-task.md`，均通过。

### 5.3 closeout runtime / receipt

| 项目 | 状态 |
|------|------|
| closeout receipt | 待 closeout runtime 生成；本报告已进入提交前最终回归阶段 |
| closeout 边界 | 本轮可声明 P4-1 private delete-last/canonical switch 完成；不得声明 P4-2/P4-3 或父任务整体完成 |

### 5.4 完成等级（禁止混报）

| 维度 | 结论 |
|------|------|
| 已实现 | 是，preflight、guarded apply、post-delete resolver/catalog、parent receipt correspondence 与控制面接线已完成 |
| 已自检 | 是，已运行 targeted acceptance、spec-check、diagnose、文件字典、执行保障、registry、token risk 与 parent aggregation |
| 已独立验收 | 是，`20260430-historical-asset-migration-delete-last-canonical-switch` 为 resource-limited Prism pass，Claude Code reviewer 无 blocker |
| 已正式完成 | 待 closeout runtime receipt；代码与物理状态已完成，最终完成声明以 receipt 为准 |

## 六、遗留问题与下一步

父任务剩余边界是 P4-2 public release / package publish 与 P4-3 clean workspace / cross-machine E2E。P4-1 不再是 deferred；它已完成 private canonical switch，但私有历史材料仍不得直接进入公共库或发布包。

## 七、经验沉淀

问题源：历史资产迁移不能只看“副本是否存在”，还要看旧路径是否仍被控制面依赖。

解决方案：把“旧路径依赖”拆成活跃 hard reference、历史证据、receipt 对应关系、acceptance alias 兼容引用和 catalog 转场引用，再用机器 preflight fail-closed。

最后效果：删除动作从主观判断变成可审计状态；旧 docs 淤积显著降低，真实考古入口转为 catalog + resolver + `redcap-knowledge/**`，并且父任务不会因 P4-1 完成而误判 P4-2/P4-3 已完成。

### 7.3 Evolution Factory 候选处理

无新增候选。本轮暴露的是已知旧资产迁移链路中的控制面接线与 post-delete 兼容问题，已直接落地为 apply tool、resolver、parent checker、acceptance 与 execution guarantee，不需要新增待孵化候选。

## 八、附录

- 结果文件：`references/legacy-asset-delete-last-preflight.json`
- 物理收据：`references/legacy-asset-delete-last-apply.json`
- 工具入口：`compass/tools/redcap-legacy-asset-delete-last-preflight.sh`
- apply 入口：`compass/tools/redcap-legacy-asset-delete-last-apply.sh`
