# 任务完成报告：Historical asset migration durable alias resolver

**报告日期**：2026-04-30
**执行者**：Cap（Codex.app + Prism）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P4-1 已从“真实 worktree 演练”推进到“持久 alias resolver 可机器验证”，但历史资产仍没有真实搬迁、删除或导出。
- 详情：本轮解决的是“演练里的 alias overlay 还不能长期被后来者安全查询”的问题。现在旧 `compass/docs/**` 路径继续作为权威锚点，新 `redcap-knowledge/**` 路径只作为候选目标；查询、诊断、总回归和 acceptance 都会阻止陈旧结果、断锚、路径逃逸、公共库误写和 hash 不一致。

### 0.2 上一步完成的是

- 上一步完成的是：P4-1 true git-worktree rehearsal 已证明 copy-first 可以在隔离 worktree 中执行、回滚，并保持主工作树和旧 docs catalog 锚点安全。

### 0.3 下一步计划做的是

- 下一步计划做的是：另开 main-tree apply 风险窗口，在物理创建 copy target 前重新复审 rollback、receipt anchor、docs catalog、resolver target state 和 Prism verdict。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：collection dry-run → file-level preflight → temp-copy rehearsal → true worktree rehearsal → durable alias resolver → main-tree apply risk window。
- 当前所在位置：P4-1 `historical-asset-migration-alias-resolver` 已完成实现、本地专项验证、棱镜 resource-limited 评审、spec/diagnose 和 full acceptance，正在进行提交与 closeout receipt 收口；父任务仍因真实 apply、public release、clean workspace E2E 保持 incomplete。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 好的，那么请继续推进主任务线，务必要和棱镜团队之间配合好，稳步迭代、谨慎评审与验收

### 1.2 触发背景

上一轮 worktree rehearsal 已经证明迁移动作可以在隔离环境中安全演练，但 alias 关系仍只是演练结果里的证据。后续如果没有持久 resolver，接盘者可能误把候选新路径当成已迁移完成，或者在旧 receipt/catalog anchor 仍是权威时提前断链。本轮把“路径解析层”单独落成机器门禁，为真正 main-tree apply 前增加一层可查询、可复验、可审计的安全缓冲。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | partial-with-explicit-defer |
| 原始意图 | 继续推进主任务线，并使用棱镜协作、评审与回归保证质量。 |
| 已覆盖 | 已建立 durable alias resolver manifest、查询入口、docs catalog pointer、spec/diagnose/acceptance 接线、文件字典、执行保障、父任务账本、经验沉淀和 Prism resource-limited review。 |
| 未覆盖/延期 | 不执行 main-tree 真实迁移，不删除旧历史资产，不向 `redcap-arsenal` 导出 raw history，不发布 npm/runtime，不关闭父任务。 |
| 用户可见边界 | “resolver 可工作”只代表旧路径与候选新路径可安全解析，不代表任何历史资产已经物理搬迁。 |
| 后续路径 | 另立 main-tree apply 风险窗口，并在 apply 前复验 resolver、rollback、receipt anchor、catalog 与 Prism verdict。 |

---

## 二、方案讨论

### 2.1 问题分析

P4-1 的核心风险不是“能不能把文件复制到新目录”，而是复制之前、复制期间和复制之后，所有考古入口是否还能解释同一个事实：旧路径仍是权威锚点，新路径只是候选目标。resolver 必须同时服务人类和机器：人类先从 docs catalog 看到摘要，机器通过命令查询具体路径；任何陈旧、越界或误写公共库的情况都要 fail-closed。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 直接进入 main-tree apply | 在主工作树创建 copy target 后再补 resolver | 推进最快 | resolver 变成事后补丁，出错时已进入真实风险窗口 |
| Q1 | 只保留 worktree rehearsal alias overlay | 继续把 alias 关系藏在演练结果里 | 改动最少 | 后续接盘者难以发现和查询，容易误判迁移状态 |
| Q1 | 单独建立 durable alias resolver | 从 worktree rehearsal 结果生成持久 resolver，并接入 catalog、diagnose、spec 与 acceptance | 可先证明解析层安全，再进入真实 apply | 真实物理迁移仍要另开任务 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 单独建立 durable alias resolver | 这能把“候选新路径”和“权威旧锚点”明确分层，避免把路径解析能力误报为物理迁移完成。 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `.dev-task.md` | 修改 | 建立 resolver 任务卡，锁定本轮不做真实迁移、不删除旧资产、不导出公共库。 |
| `compass/tools/redcap-legacy-asset-alias-resolver.py` / `compass/tools/redcap-legacy-asset-alias-resolver.sh` | 新建 | 生成、校验和查询 durable alias resolver。 |
| `references/legacy-asset-migration-alias-resolver.json` | 新建 | 记录 54 条旧路径到候选新路径的解析关系，所有 target 当前均为 planned-not-applied。 |
| `compass/tools/redcap-docs-catalog.py` / `compass/docs/catalog.json` | 修改 | 在 docs catalog 顶层暴露 resolver 摘要和查询命令，避免默认打开大 JSON。 |
| `compass/tools/redcap-spec-check.sh` / `compass/tools/redcap-diagnose.sh` / `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 把 resolver 纳入总校验、诊断和专项 acceptance。 |
| `references/file-lookup-dictionary.md` / `references/file-lookup-dictionary-policy.json` | 修改 | 登记 resolver manifest 与工具入口，保证后续接盘者按需定位。 |
| `references/execution-guarantees.json` / `references/token-structural-governance.json` | 修改 | 把 resolver 升级为执行保障节点和 token 风险治理对象。 |
| `references/redcap-parent-task-ledger.md` / `references/parent-receipt-aggregation-policy.json` | 修改 | 父任务状态推进到 durable resolver，仍明确真实 apply 未完成。 |
| `compass/knowledge/lessons.md` | 修改 | 沉淀“候选新路径与权威旧锚点必须分开”的经验。 |

### 3.2 技术实现要点

resolver 的核心规则是 old-path-authoritative：旧 `compass/docs/**` 路径是 canonical path，新 `redcap-knowledge/**` 路径只是 requested_new_path_resolves_to 的候选目标。target 不存在时标记为 `planned-not-applied`，未来真实 apply 之后只有 hash 与源文件一致，才允许变成 `applied-copy-present`。

校验链路采取 fail-closed：生成结果绑定 worktree rehearsal 文件 hash 和 docs catalog；一旦来源变了、旧路径不在 catalog、source hash 不一致、候选 target 已存在但 hash 不一致、路径逃逸、重复路径或公共库 target 出现，resolver 都会失败。`--resolve` 查询也会先比对 live result，避免使用陈旧磁盘结果回答。

docs catalog 只暴露 summary 和 resolver command，不把 54 条 alias 全量塞进首读入口。这样可以继续遵守渐进式披露：先看 catalog 摘要，只有审计具体路径时才查询 resolver 明细。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| durable alias resolver | `redcap-legacy-asset-alias-resolver.py` | 把历史资产旧路径和候选新路径做成可查询、可校验的长期解析层。 |
| old-path-authoritative | `references/legacy-asset-migration-alias-resolver.json` | 旧 `compass/docs/**` 仍是权威路径；新路径不能冒充已经迁移完成。 |
| planned-not-applied | resolver target state | 候选新路径还没有在主工作树里创建 copy target。 |
| applied-copy-present | resolver target state | 未来 copy target 真实存在且 hash 与旧源文件一致时，才允许进入的状态。 |
| docs catalog pointer | `compass/docs/catalog.json` 的 `legacy_alias_resolver` | 给人类和 Agent 一个轻量入口，知道 resolver 存在而不用默认读完整 manifest。 |

### 3.3 关联变更

本轮因为新增任务报告和 lessons，会影响历史资产 dry-run 的文件统计；这类生成型清单需要在最终回归前重新检查并按门禁要求同步。父任务聚合策略同步更新 P4-1 的未完成原因，避免 durable resolver 被误解为真实 apply 已完成。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 暂无必须人工介入项 | 本轮仍未进入真实资产搬迁、公共库导出或 release 发布；所有设计选择均在已批准主线边界内。 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 入口门禁 | `redcap-pm-gate-check / intent-coverage / change-intake / drift reanchor` | ✅ |
| 语法检查 | `bash -n compass/tools/redcap-legacy-asset-alias-resolver.sh compass/tools/redcap-multi-session-acceptance.sh compass/tools/redcap-spec-check.sh compass/tools/redcap-diagnose.sh` | ✅ |
| Python 编译 | `python3 -m py_compile compass/tools/redcap-legacy-asset-alias-resolver.py compass/tools/redcap-docs-catalog.py` | ✅ |
| resolver 自检 | `bash compass/tools/redcap-legacy-asset-alias-resolver.sh --write-result --check-result` | ✅ |
| docs catalog 自检 | `bash compass/tools/redcap-docs-catalog.sh generate && bash compass/tools/redcap-docs-catalog.sh check` | ✅ |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh legacy-asset-alias-resolver` | ✅ |
| spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | ✅ |
| diagnose | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | ✅ |
| full acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh all` | ✅ |
| Prism review | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | ✅ resource-limited-pass |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 无本轮必须人工验证项；真实 main-tree apply 前需要单独风险窗口。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 6/6 已完成，等待 closeout runtime 同步为 receipt |
| 棱镜验收 | resource-limited-pass；Claude Code 独立评审无 blocker，Kimi/Gemini timeout，Copilot frozen |
| closeout summary | closeout runtime 完成后生成 |
| closeout receipt | closeout runtime 完成后生成 |
| rescue audit（如有） | closeout runtime 判定 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，Prism resource-limited-pass |
| 已正式完成 | 否，receipt 是唯一正式完工凭证 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| main-tree apply | 真实创建 copy target 仍属于更高风险窗口，需要 resolver 通过后另立任务并复审 rollback、receipt anchor 和 Prism verdict。 | P1 |
| 旧 docs anchor 删除 | 删除旧路径会影响 receipt 和考古，必须等真实 apply、catalog、resolver 和本地链接全部复验后再讨论。 | P1 |

### 6.2 触发的新问题

本轮自检发现 `--resolve` 查询如果只做结构校验，理论上可能读取陈旧 result 后给出旧答案。已修复为查询前也要与 live resolver 结果比对，并在 acceptance 中加入 stale resolve 失败用例。

Claude Code 独立评审没有 blocker，但提出 3 个 action：第一，`LAM-0051` 不在 alias map。复核后确认它是 apply plan 中的 `docs-catalog` preserve 项，不属于 copy-first alias；本轮把 resolver policy 和 follow-up 改成显式说明“alias entries 只覆盖 copy-first，非 copy-first item id 可以缺席”。第二，`source_git_head` 来自 worktree rehearsal 基线而不是当前 HEAD；本轮补充 `source_git_head_scope`，并把“apply 后重新生成 resolver”保留为风险窗口前置动作。第三，`catalog-exact` 的 `old_path_authoritative: false` 可能被误读；本轮补充 `migration_scope: outside-alias-map` 与 `authority_note`，并加入 acceptance。

### 6.3 推荐的下一步行动

1. 完成本轮 Prism review、full regression、commit 与 closeout receipt。
2. 下一任务再开启 main-tree apply 风险窗口，不要在 resolver 任务中顺手搬迁历史资产。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-145 | 迁移 resolver 必须把“候选新路径”和“权威旧锚点”分开 | resolver 可工作不等于资产已迁移；旧路径仍是 receipt/catalog 权威锚点，新路径只能作为候选目标。 |

### 7.2 流程改进建议

暂无新增流程改动；本轮沿用“任务卡 → 机器门禁 → targeted acceptance → Prism → 全量回归 → closeout receipt”的 Layer B 主链，并额外把 `--resolve` 查询也纳入 freshness 校验。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| durable alias resolver freshness guard | 自检发现 stale resolve 风险 | no-promote；已直接补进 resolver acceptance，暂不升格为 skill 或独立候选 | `compass/tools/redcap-multi-session-acceptance.sh` |
| resolver copy-first-only provenance | Prism action | no-promote；已直接写入 resolver policy、follow-up 和任务报告，作为 main-tree apply 风险窗口前置核查点 | `references/legacy-asset-migration-alias-resolver.json` |

---

## 八、附录

### 附录 A：Commits

```
尚未提交
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| test/review | Historical asset migration durable alias resolver review | resource-limited-pass；Claude 无 blocker，3 个 action 已修正或登记到 apply 前置门禁 | `prism/runs/20260430-historical-asset-migration-alias-resolver/collect/claude-reviewer/parsed.json` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- resolver 结果：`references/legacy-asset-migration-alias-resolver.json`
- 上一步 worktree 结果：`references/legacy-asset-migration-worktree-rehearsal.json`
- 父任务账本：`references/redcap-parent-task-ledger.md`
