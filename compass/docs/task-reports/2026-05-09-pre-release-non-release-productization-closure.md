# 任务完成报告：P4-2k 发布前非发布产品化治理收束

**报告日期**：2026-05-09  
**执行者**：Cap（Codex.app）  
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 已把正式发布任务之前还能由工程自动推进的产品化治理收束完成。
- 详情：本轮把 npm 候选包面从偏宽的内部工具集合，收窄为 150 个文件以内的 runtime-readiness surface；同时补上了未来正式发布任务需要看的交接说明、运行时入口边界和诊断分层。RedCap 现在更接近一个“可以进入 release task 审核的 CLI/runtime 产品候选”，但仍没有进入正式 npm 发布。

### 0.2 上一步完成的是

- 上一步完成的是：P4-2j 已完成发布前最终收束审判，确认本地打包和安全预检基础成立，但正式公开发布仍被许可证、发布开关和 npm 权限等人工决策拦住。

### 0.3 下一步计划做的是

- 下一步计划做的是：如果 Norven 决定启动正式 release task，先做 release readiness 全量复验，再处理许可证、发布开关、npm scope 权限、版本号和回滚策略；如果暂不发布，RedCap 父任务线可以转入正式发布之外的后续产品化治理。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：工作流重构 → 信息架构/历史资产治理 → CLI 产品面 → package readiness → clean workspace E2E → Codex hooks 候选增强 → 发布前最终审判 → P4-2k 非发布产品化收束 → 等待正式 release task。
- 当前所在位置：P4-2k。它是正式发布任务之前的工程收束，不是 P4-2 正式 npm 发布。

### 0.5 是否需要 Norven 人工介入

- 人工介入：现在不需要。
- 说明：本轮没有执行 `npm publish`，没有改 `private` / `publish_allowed` / `license`，也没有替 Norven 选择 registry、凭据或发布时间。只有进入正式 release task 时才需要 Norven 决策这些事项。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> “可以，我赞同。那接下来你们继续配合好，把后续的任务开发落地完毕吧，直至准备执行“发布任务”为止。”

### 1.2 触发背景

前序任务已经证明 RedCap 可以做本地打包 dry-run 和安全预检，但当时仍有三个不适合直接带进正式发布任务的坏味：包面偏宽、运行时边界说明不够产品化、正式发布前还差哪些人工决策不够直观。本轮专门处理这些“非发布类、但发布前必须收束”的问题。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 继续推进 RedCap 父任务线，直到准备进入正式发布任务。 |
| 已覆盖 | 已覆盖 package surface 收窄、runtime import map、public release handoff、诊断分层、父任务账本同步、棱镜评审和回归验证。 |
| 未覆盖/延期 | 不执行 npm 发布；不选择许可证；不改发布开关；不操作 registry 或凭据；不做完整 LLM-wiki/RAG/GraphRAG；不做大规模物理工具树迁移。 |
| 用户可见边界 | 本轮完成后可以说“正式发布任务前的工程前置收束已完成”，不能说“RedCap 已经公开发布”或“已经 public-release-ready”。 |

---

## 二、方案讨论

### 2.1 问题分析

本轮核心问题不是“能不能把包发出去”，而是“进入正式发布任务之前，工程侧还能不能把明显不干净的边界先收掉”。如果把所有 RedCap 自维护工具、历史迁移工具、研究工具和 E2E 夹具都塞进候选包，未来发布审核会被内部资产淹没；如果不说明打包后哪些诊断属于用户运行时，哪些属于源码维护，用户安装后也可能被内部治理检查误导。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 直接进入正式发布 | 修改发布开关并准备 npm publish | 最快 | 会绕过许可证、凭据和最终授权，不可接受 |
| Q1 | 非发布产品化收束 | 只处理包面、运行时边界、交接说明和诊断分层 | 安全、可回归、不会误发布 | 仍不能宣称已发布 |
| Q1 | 大规模物理拆分 | 现在就迁移完整工具树和历史资产 | 架构更理想 | 风险过大，会把发布前收束变成另一轮深水区重构 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 非发布产品化收束 | 它能最大化减少正式 release task 前的噪音，同时不触碰 Norven 保留决策。 | CAP_DECIDE + Prism review |

---

## 三、落地结果

### 3.1 做了什么

- 包候选面已收窄到 150 个文件以内：保留运行、复活、状态、诊断、收尾、Prism 可用性、发布安全预检和交接文档；排除历史迁移、E2E 夹具、完整 LLM-wiki/RAG 研究工具、公开蒸馏维护工具和一次性重建资产。
- 新增正式发布任务交接说明：把“未来真要发布时还缺什么”讲清楚，包括许可证、发布开关、npm scope 权限、版本、发布窗口和回滚策略。
- 新增运行时入口地图：说明 CLI 入口分别依赖哪些运行时能力，哪些源码维护工具不属于公开包面。
- 诊断面分层：未来 CLI 用户默认运行 runtime profile；源码仓库维护者仍可显式运行 source profile，保留完整治理强度。
- 发布前审判措辞已校正：剩余 release blocker 被明确表述为“人工发布决策”，不是 Cap 可以自动修掉的工程缺陷。

### 3.2 解决后的效果

现在 RedCap 的状态更清楚：工程侧已经把正式发布任务之前能自动处理的产品化问题收了一轮；剩下的阻塞主要是 Norven 必须亲自决定的发布事项。这避免了两种误判：一是把“npm dry-run 通过”误解成“已经适合公开发布”；二是把“发布开关没开、许可证未选”误解成工程缺陷。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应载体 | 人话解释 |
|------|----------|---------|
| package surface | `package.json` / package checks | 未来 npm 包里会带出去的文件集合；本轮把它收窄到运行时和发布安全所需的 150 个文件以内。 |
| runtime profile | `redcap diagnose` | CLI 用户默认看到的诊断模式，只检查运行时和发布安全相关事项。 |
| source profile | `redcap-diagnose.sh` | 源码仓库维护者使用的完整诊断模式，会覆盖历史资产、Forge、LLM-wiki、Hook、任务追踪等治理链。 |
| release blocker | 发布前审判 | 正式公开发布前必须解决的问题；本轮剩下的是许可证和发布授权，不是 Cap 可以自动决定的工程改动。 |
| public release handoff | 发布交接说明 | 正式进入 release task 前给人看的交接清单，说明工程侧准备好了什么、还需要 Norven 决定什么。 |

### 3.3 未做什么

本轮没有发布 npm 包，没有改变私有发布姿态，没有删除历史证据，没有移动完整工具树，也没有把 redcap-arsenal 或 LLM-wiki/RAG 宣称为成熟公共能力。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 许可证 | 正式公开发布前必须由 Norven 决定；当前仍是 `UNLICENSED`。 | P0 |
| 2 | 是否公开发布 | 需要明确是否把 `private` 改为 `false`，以及是否允许 `publish_allowed=true`。 | P0 |
| 3 | npm 权限与登录态 | 需要确认 `@norven63/redcap` 的 npm scope 权限、账号状态和发布窗口。 | P0 |
| 4 | 发布回滚策略 | 正式 release task 前需要约定版本号、失败撤回或 deprecate 策略。 | P1 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 发布前架构审判 | `bash compass/tools/redcap-pre-release-product-architecture-check.sh` | 通过；剩余 2 个 release blocker 均为人工发布决策 |
| 结构任务树 | `bash compass/tools/redcap-pre-release-structure-task-tree-check.sh` | 通过 |
| runtime 包清单 + npm dry-run | `bash compass/tools/redcap-runtime-package-manifest.sh --check --npm-pack-dry-run --json` | 通过；candidate_count=150 |
| public package surface | `bash compass/tools/redcap-public-package-surface.sh --json` | 通过；surface_mode=curated-runtime-readiness-surface |
| 发布安全扫描 | `bash compass/tools/redcap-package-publish-safety-check.sh` | 通过；files_scanned=150 |
| CLI runtime 诊断 | `bin/redcap diagnose --workspace "$PWD"` | 通过；runtime profile 生效 |
| 源码维护诊断 | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 通过；source profile 仍覆盖完整治理链 |
| spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| targeted acceptance | `pre-release-product-architecture-check`、`pre-release-structure-task-tree-check`、`clean-workspace-e2e-check`、`prism-acceptance-binding-required` | 通过 |
| full acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh all` | 通过 |
| clean workspace E2E 刷新 | `bash compass/tools/redcap-clean-workspace-e2e.sh --write-result --result references/clean-workspace-install-e2e.json --timeout 240` | 通过；head=8ef6ebac87d4 |

### 5.2 棱镜评审

| 角色 | Agent | 结论 | 处理 |
|------|-------|------|------|
| reviewer | Claude Code | PASS，无 blocker | 采纳 warning，补诊断分层和 live check 证据 |
| challenger | Kimi | PASS，无 blocker | 采纳 warning，补发布审判措辞和诊断边界说明 |

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 待最终 closeout runtime 核对 |
| 棱镜验收 | 已通过并登记 |
| closeout summary | 待生成 |
| closeout receipt | 待生成 |
| rescue audit（如有） | 无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是；targeted checks、CLI runtime diagnose、source diagnose、spec-check、full acceptance 均通过 |
| 已独立验收 | 是；Claude Code + Kimi 均通过 |
| 已正式完成 | 否；receipt 生成后才算正式完成 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 正式 npm 发布 | 需要 Norven 决策许可证、发布开关、npm 权限、版本和回滚策略 | P0 |
| 完整物理执行层拆分 | 影响大量路径、hook 与兼容层，不适合混入本轮收束 | P1 |
| package exclude globs 单一信源化 | 当前有机器检查兜底，但仍存在多处同步维护成本 | P1 |
| 完整 LLM-wiki/RAG/GraphRAG | 已登记为长期阈值化能力，不是发布前硬阻塞 | P3 |

### 6.2 触发的新问题

没有新增需要 Norven 立即决策的问题。棱镜提出的 warning 已转化为本轮修复：诊断分层、发布审判措辞和 live check 证据。

### 6.3 推荐的下一步行动

1. 如果 Norven 准备进入正式 release task，先明确许可证、npm 权限、版本、发布窗口和回滚策略。
2. 如果暂不发布，继续做正式发布之外的产品化治理，例如 package exclude globs 单一信源化、完整执行层拆分评估、多 OS 外部验证设计。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-pending | 发布前治理要区分“运行时用户检查”和“源码维护检查” | CLI 用户安装后需要的是可理解的运行时体检；源码仓库维护者需要的是完整治理链。两者混在一起会制造误报和信任损耗。 |

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 理由 |
|------|------|----------|------|
| 诊断分层模式 | 本轮 Prism warning | no-promote-now | 已落地到代码和报告；后续如果正式 release task 复用并验证稳定，再考虑晋升为 release/diagnose 流程经验。 |

---

## 八、附录

### 附录 A：Commits

```text
8ef6ebac87d4 refactor(release): 收束发布前非发布治理
后续 clean workspace E2E 结果刷新将单独提交。
```

### 附录 B：棱镜调用记录

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|----------|
| acceptance-review | P4-2k 非发布产品化收束是否安全、诚实、不会误发布 | 通过；warning 已修复 | `prism/reports/2026-05-09-pre-release-non-release-productization-closure.md` |
