# 任务完成报告：P4-16 Prism 报告归档 live copy-first apply

**报告日期**：2026-05-22
**执行者**：Cap（Codex.app 主执行，Prism 使用 Claude Code + Kimi）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：冻结的 55 份 Prism 报告已经复制到私有归档区，旧报告位置仍保留，发布和证据边界没有越界。
- 详情：本轮解决的是“可以先复制归档，但不能误删旧锚点、不能吸收新报告、不能冒充已发布就绪”的问题。现在 `private-archive/prism-reports` 有 55 份副本和一个索引，`prism/reports` 仍保留旧锚点，新产生的 P4-16 Prism 报告被登记为 post-freeze，不进入这批冻结归档。包面检查继续排除私有归档、旧报告和 raw run evidence。

### 0.2 上一步完成的是

- 上一步完成的是：P4-15 已把报告归档集合冻结，防止评审报告自增导致迁移计划反复漂移。
- 详情：P4-15 只建立“不要漂移”的守卫，没有创建真实归档副本。P4-16 接在这个守卫之后，把冻结集合安全复制出来，同时补了 P4-15 与 P4-16 之间的桥接字段，避免人读 JSON 时误以为 guard 和 live apply 互相冲突。

### 0.3 下一步计划做的是

- 下一步计划做的是：本轮收口后进入下一条 release-readiness 子任务选择；旧锚点退休、raw evidence cleanup、Layer A 产品范围裁决和正式公开发布动作仍然不能在本轮声明完成。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P4-12 规划归档集合 → P4-13 临时演练 → P4-15 冻结集合防漂移 → P4-16 真实 copy-first 副本 → 后续另行评审 delete-last / raw evidence / release readiness。
- 当前所在位置：framework-upgrade / P4-16，处在 release-structural 任务的 closeout 前阶段；实现、自检和 Prism 独立评审已完成，receipt 尚需在最终 closeout 中生成。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要
- 说明：本轮没有触及许可证、发布开关、registry、secret、raw evidence 删除或 Layer A 产品裁决。下一步可由 Cap 继续完成 backlog 更新、acceptance binding、clean workspace E2E 和 closeout receipt。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 好的，那你们按照自己的规划去继续稳步推进吧

### 1.2 触发背景

P4-15 已经证明 report archive 迁移集合不能再随着新 Prism 报告自动变动。当前需要推进的是下一刀：把冻结集合复制到私有归档区，但继续保留旧路径作为权威锚点。这个顺序可以先降低 `prism/reports` 作为长期运行资产的压力，同时避免“还没建立 alias/delete-last 证明就删除历史证据”的风险。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 继续推进 RedCap 主线，不中断等待人工决策 |
| 已覆盖 | 完成 P4-16 的 copy-first 归档实施、检查器接线、派生快照刷新、Prism 独立评审和报告归档 |
| 未覆盖/延期 | 未执行旧锚点退休、raw evidence cleanup、Layer A 产品裁决、许可证选择、registry 操作或正式公开发布动作 |
| 用户可见边界 | 只能声明“冻结集合已有私有归档副本”；不能声明“旧报告路径已下线”“证据已清理”“blocker 已完全关闭”或“已可正式公开发布” |
| 后续路径 | 由下一条 framework-upgrade backlog 切片继续选择 delete-last、raw evidence 或 release readiness 的安全推进顺序 |

---

## 二、方案讨论

### 2.1 问题分析

P4-16 的难点不是复制文件，而是复制后不能破坏 P4-12/P4-13/P4-15 的旧门禁。原有 plan/readiness/guard 检查都曾经把“真实归档副本出现”视为越界；如果直接复制，会让旧检查器和新现实打架。正确做法是把 P4-16 写成后续阶段合同：只有存在合法 live apply manifest，且副本集合、hash、post-freeze 边界和包面排除全都能核对时，旧检查器才允许这些副本存在。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 只复制文件 | 直接把报告复制到私有归档 | 快 | 会让旧检查器失效，无法证明边界 |
| Q1 | 复制 + manifest + 检查器桥接 | 复制副本，同时让旧门禁只接受 P4-16 合法状态 | 可审计、可回归、不会口头绕过旧规则 | 需要同步多个派生快照 |
| Q1 | 等 delete-last 一起做 | 不做中间副本，等未来一次性搬迁 | 表面简单 | 风险集中，无法渐进验证 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 复制 + manifest + 检查器桥接 | 这是唯一既能真实推进归档，又不破坏旧锚点和证据边界的做法 | CAP_DECIDE + Prism review |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `private-archive/prism-reports/*.md` | 新建 | 复制 P4-12/P4-15 冻结的 55 份 Prism 报告副本 |
| `private-archive/prism-reports/index.yaml` | 新建 | 记录私有归档副本索引，仍不替代旧 `prism/reports` 锚点 |
| `references/r1-prism-report-archive-live-copy-first-apply.json` | 新建 | 记录 P4-16 copy-first 实施结果、边界和副本 hash |
| `compass/tools/redcap-r1-prism-report-archive-live-copy-first-apply-check.*` | 新建 | 校验 P4-16 副本、索引、hash、post-freeze、包面和 raw evidence 边界 |
| `compass/tools/redcap-r1-prism-report-archive-*.py` | 修改 | 让 P4-12/P4-13/P4-15 检查器在 P4-16 合法 manifest 存在时接受真实归档副本 |
| `references/*preflight*.json` / `references/*surface*.json` | 修改 | 刷新 package candidate 与控制面候选计数，防止新检查器加入后快照过期 |
| `references/file-lookup-dictionary.*` | 修改 | 把 P4-16 manifest、检查器与私有归档索引纳入查阅字典 |
| `prism/reports/2026-05-22-r1-prism-report-archive-live-copy-first-apply.md` | 新建 | Prism 独立评审报告 |
| `prism/runs/20260522-r1-prism-report-archive-live-copy-first-apply/**` | 新建 | Claude Code 与 Kimi 的评审证据、parsed verdict 和 registry |

### 3.2 技术实现要点

本轮把“复制文件”升级为“带合同的状态转移”。P4-16 manifest 是新状态的事实源：它声明哪些报告被复制、每份副本 hash 是什么、旧锚点是否保留、post-freeze 报告是否排除、哪些声明仍然禁止。旧检查器不再简单地看到 `private-archive/prism-reports` 就失败，而是要求 P4-16 manifest 与真实文件完全一致。

包面快照也同步刷新到 294 个候选文件。增加的 3 个候选都是 P4-16 的控制面资产：一个 manifest、一个 shell 检查入口、一个 Python 检查器；55 份历史报告副本和归档索引仍通过 `.npmignore` 与 package surface policy 排除在公开包之外。

Prism 评审给出 pass-with-nits。Claude Code 建议补清 P4-15 guard 与 P4-16 live apply 的语义桥接，这一点已落实；Kimi 建议把 `private-archive/prism-reports` 加入 `.gitignore`，本轮没有采纳，因为 `private-archive` 已经包含受管历史资产，不能在 P4-16 里改变整个私有归档目录的版本控制策略。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| copy-first | `references/r1-prism-report-archive-live-copy-first-apply.json` | 先复制新位置，旧位置继续可用；只有未来 delete-last 任务才可能考虑移除旧锚点 |
| post-freeze report | `references/r1-prism-report-archive-churn-freeze-guard.json` | P4-15 冻结后新增的正式 Prism 报告；它们不能自动进入这批 55 份归档集合 |
| private archive | `private-archive/prism-reports/index.yaml` | 私有历史证据归档区；保留考古价值，但不进入公开包，也不替代旧锚点 |
| package candidates | `references/public-package-surface-policy.json` | 当前可能进入包的文件清单；本轮新增 3 个控制面文件，但排除了历史报告副本 |
| Prism acceptance | `prism/runs/20260522-r1-prism-report-archive-live-copy-first-apply/session-registry.yaml` | 外部 Agent 独立评审证据，防止 Cap 自己开发、自己单方面验收 |

### 3.3 关联变更

新增 P4-16 检查器后，控制面包候选数量从 291 增加到 294，因此多个 release-readiness 快照必须同步更新。新增 Prism 报告后，P4-15 guard 的 post-freeze 报告清单从 1 份增加到 2 份，确保评审报告本身不会再次污染冻结归档集合。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 无必须人工审核项 | 本轮没有触及 Norven 保留决策；如要进入旧锚点退休、raw evidence 删除或正式公开发布，才需要人工授权 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| P4-16 主检查 | `bash compass/tools/redcap-r1-prism-report-archive-live-copy-first-apply-check.sh` | 通过 |
| P4-15 冻结守卫 | `bash compass/tools/redcap-r1-prism-report-archive-churn-freeze-guard-check.sh` | 通过 |
| 包面安全 | `bash compass/tools/redcap-public-package-surface.sh` | 通过，candidate_count=294 |
| 控制面派生快照 | `bash compass/tools/redcap-r1-control-plane-contract-split-check.sh` | 通过 |
| Prism evidence 派生快照 | `bash compass/tools/redcap-r1-prism-evidence-retention-split-check.sh` | 通过 |
| Prism archive 报告归档 | `bash prism/tools/prism-archive-check.sh --report prism/reports/2026-05-22-r1-prism-report-archive-live-copy-first-apply.md` | 通过 |
| 全量 spec | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- 无必须人工验证项；后续涉及旧锚点删除、证据删除、许可证或正式公开发布动作时再进入人工决策。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 收口前：已准备，待最终 closeout 核对 |
| 棱镜验收 | Claude Code + Kimi pass-with-nits，无 blocker |
| closeout summary | 收口前：尚未生成 |
| closeout receipt | 收口前：尚未生成 |
| rescue audit（如有） | 收口前：无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，Prism pass-with-nits 且无 blocker |
| 已正式完成 | 否，receipt 将由最终 closeout 生成后才可改为是 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 旧 `prism/reports` 锚点退休 | 需要 alias/delete-last 证明，不能和 copy-first 混做 | P0 |
| `prism/runs` raw evidence cleanup | 涉及证据保全与可能的人类授权边界，不能在本轮执行 | P0 |
| Layer A 产品范围裁决 | 属于产品边界，不由本轮技术切片决定 | P1 |
| 正式公开发布动作 | 仍需许可证、发布开关、registry 等人工保留决策 | P0 |

### 6.2 触发的新问题

P4-16 让 P4-15 guard 进入“冻结守卫 + 下游 live apply 已发生”的组合状态。已通过 `downstream_live_apply_bridge` 修正这个语义张力，后续如果继续推进 delete-last，也必须采用同样的显式桥接，不允许只靠人类解释。

### 6.3 推荐的下一步行动

1. 运行 closeout runtime，生成 P4-16 receipt。
2. 在 framework-upgrade backlog 中登记下一条任务；建议先做 P4-17 路线评审，决定是进入旧锚点 delete-last、raw evidence 保全/清理，还是先做 release readiness 收束。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| 无新增 Lesson | 本轮是既有 copy-first/delete-last 方法论的执行，不新增通用规则 | 需要沉淀的具体提醒已写入 6.2，后续 delete-last 任务复用 |

### 7.2 流程改进建议

对于会改变旧门禁前提的后续阶段，manifest 里必须同时写“本阶段做了什么”和“上一阶段仍禁止什么”。这样旧检查器可以升级为阶段感知，而不是被粗暴关闭。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| no-promote | Prism pass-with-nits / copy-first 实施 | 本轮不新增 Evolution candidate；相关方法论属于既有 copy-first/delete-last 规则的局部应用 | `prism/reports/2026-05-22-r1-prism-report-archive-live-copy-first-apply.md` |

---

## 八、附录

### 附录 A：Commits

```
本报告生成时尚未提交；最终 commit 会在 closeout 后记录。
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| review | P4-16 是否安全执行 live copy-first apply | pass-with-nits，无 blocker | `prism/reports/2026-05-22-r1-prism-report-archive-live-copy-first-apply.md` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- P4-16 manifest：`references/r1-prism-report-archive-live-copy-first-apply.json`
- Prism run：`prism/runs/20260522-r1-prism-report-archive-live-copy-first-apply/session-registry.yaml`
