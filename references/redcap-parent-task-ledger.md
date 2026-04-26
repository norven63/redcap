# RedCap Parent Task Ledger

> 目的：给 R0-R22 及其后续中插任务一个稳定的父任务视图。它不是历史报告的替代品，而是后续继续开发前的“先看这里”入口。

## 读取规则

- 先看本文件判断父任务、子任务、延期项与阻塞项，再按证据路径打开具体报告或 receipt。
- 子任务 receipt 只证明子任务完成；除非存在专门父任务 receipt 聚合 gate，否则不能自动证明父任务全部完成。
- 本文件只维护可继续执行的父任务真相，不把历史报告全文复制进来。

## 当前父任务定位

RedCap 的长期父任务不是“继续补一个 skill”，而是把当前 skill-root 承载形态逐步演进为可安装、可复活、可调度、可审计的 Agent runtime / CLI / 多层系统。

当前已完成的是若干控制面与路线图子任务；尚未完成的是物理迁移、远端共享库绑定、正式发布打包与历史资产迁移。

## 已完成子任务

| 子任务 | 完成边界 | receipt / 证据 | 不能冒充的范围 |
|---|---|---|---|
| Evolution-grade 控制面可靠性与自我进化治理 | R0-R8 repo-owned 第一轮机制落地：baseline、候选池、旧资产、skill lifecycle、token 治理、Evolution closeout gate | `redcap-evolution-grade-control-plane-hardening-*` receipt；报告 `2026-04-25-redcap-evolution-grade-control-plane-hardening.md` | 不等于所有保障节点都变成宿主级 100% 强制 |
| 产品形态重定位与系统架构解耦 | 明确 RedCap 应从 skill-root 走向 runtime / CLI / 多层系统；完成路线图、provider freeze、文件字典、Feishu owner 收敛 | `redcap-runtime-productization-and-architecture-decoupling-*` receipt；报告 `2026-04-25-redcap-runtime-productization-and-architecture-decoupling.md` | 不等于完成物理目录拆分或正式 CLI/package |
| 原始意图覆盖审计硬门 | PM Gate/diagnose 接入 scope coverage，防止任务卡范围缩水后自证完成 | `redcap-original-intent-coverage-gate-*` receipt；报告 `2026-04-26-original-intent-coverage-gate.md` | 不等于自动语义理解所有复杂需求 |
| 执行层重构与公共知识库治理 | R0-R22 本地控制面落地：Prism availability、File Lookup Dictionary coverage、shared-knowledge 模板、`bin/redcap` 薄 facade | `redcap-execution-layer-and-shared-knowledge-governance-*` receipt；报告 `2026-04-26-execution-layer-and-shared-knowledge-governance.md` | 不等于远端 Gitee 绑定、历史资产物理迁移、正式 npm/pip/brew 分发完成 |
| 发布/打包前安全 gate | 未来 package / runtime 发布前的候选文件安全审计已接入 spec/diagnose/acceptance | `redcap-package-publish-safety-gate-*` receipt；报告 `2026-04-26-package-publish-safety-gate.md` | 不等于已经发布 package |
| Layer B 中插需求重计划强门 | 新增 U<n> 中插账本、CHANGE_INTAKE / REPLAN_REVIEW、父子完成边界和机器检查 | `layerb-change-intake-replan-gate-*` receipt；报告 `2026-04-26-layerb-change-intake-replan-gate.md` | 不等于 R0-R22 父任务全部完成 |

## 父任务待执行清单

| id | 来源 | 任务 | 状态 | 优先级 | 推荐下一步 | 依赖 / 边界 |
|---|---|---|---|---|---|---|
| P0-1 | U2 | Prism availability cache provenance/path 污染修复 | completed | P0 | 已增加 cache provenance、probe/policy 内容摘要和污染回归 | receipt: `prism-availability-cache-provenance-guard-*`；报告 `2026-04-26-prism-availability-cache-provenance-guard.md` |
| P0-2 | R0-R22 audit | R0-R22 原始编号可追溯化 | completed | P0 | 已新增机器可读 registry 和 checker，登记编号来源、状态、证据、置信度与延期边界 | receipt: `redcap-r0-r22-registry-*`；产物：`references/redcap-r0-r22-registry.json` |
| P1-1 | R0-R22 deferred | 执行层物理拆分 dry-run | completed | P1 | 已生成 dry-run manifest、checker、spec/diagnose/acceptance 接线和 Kimi Prism review；下一步进入 P1-2 历史资产迁移 dry-run | receipt: `redcap-execution-layer-split-dry-run-*`；产物：`references/execution-layer-split-dry-run.json` |
| P1-2 | R0-R22 deferred | 历史资产迁移 dry-run/apply | completed | P1 | 已生成 collection-level dry-run manifest、checker、spec/diagnose/acceptance 接线；真实 move/delete 另开 apply 任务 | receipt: `redcap-legacy-asset-migration-dry-run-*`；产物：`references/legacy-asset-migration-dry-run.json` |
| P1-3 | R0-R22 deferred | shared-knowledge 远端 Gitee 绑定 | blocked-external | P1 | 用户提供 remote / 权限后绑定；绑定前本地模板继续工作 | 需要外部仓库和权限，Cap 不能凭空创建最终远端 |
| P2-1 | R0-R22 deferred | 正式 runtime / CLI / package 发布设计与实现 | open | P2 | 先确定 package 形态，再跑 package safety gate；发布前阻断 `.env`、runtime evidence、私密入口 | 依赖 P1-1 的边界清晰化 |
| P2-2 | change-intake report | 父任务 receipt 聚合 gate | open | P2 | 设计 parent receipt aggregator，允许多个子任务 receipt 聚合成父任务完成证明 | 当前只能 fail-closed，不能自动宣称父任务完成 |
| P2-3 | Prism review limits | Formal Prism quorum 恢复复验 | resource-limited | P2 | 当第二个非 Copilot provider headless 稳定后，重跑 formal quorum | 当前 Kimi 可用；Gemini/Claude 超时，Codex unsupported，Copilot frozen |
| P3-1 | retrieval roadmap | GraphRAG / 向量检索阈值研究 | deferred | P3 | 先继续 catalog + rg + metadata；当共享库规模越过阈值再引入 RAG/GraphRAG | 不能过早引入重型系统复杂度 |

## 推荐执行顺序

1. `P0-1`：先修 Prism availability cache 污染，因为它会影响后续所有 Prism 审查质量。
2. `P0-2`：建立父任务 registry，把 R0-R22 编号变成可机器检查的持续真相源。
3. `P1-1`：执行层物理拆分 dry-run，确认 RedCap 如何从 skill-root 迁出。（已完成）
4. `P1-2`：历史资产迁移 dry-run/apply，解决 docs / reports 长期淤积。（已完成 dry-run；真实 apply 另开任务）
5. `P1-3`：绑定 shared-knowledge 远端仓库。
6. `P2-1`：正式 runtime / CLI / package 发布。
7. `P2-2`：父任务 receipt 聚合 gate。
8. `P2-3`：formal Prism quorum 恢复复验。

## 当前不可声明

- 不可声明 RedCap 已经完成独立 runtime / CLI / package 化。
- 不可声明历史报告和研究材料已经物理迁出执行层。
- 不可声明 shared-knowledge 已经绑定远端团队仓库。
- 不可声明 P1-1 dry-run 已经执行真实 move/copy/link；它只证明迁移边界和风险已可审计。
- 不可声明 P1-2 dry-run 已经执行真实历史资产搬迁或删除；它只证明分类、断链计划、catalog 计划和回滚边界已可审计。
