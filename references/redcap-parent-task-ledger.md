# RedCap Parent Task Ledger

> 目的：给 R0-R22 及其后续中插任务一个稳定的父任务视图。它不是历史报告的替代品，而是后续继续开发前的“先看这里”入口。

## 读取规则

- 先看本文件判断父任务、子任务、延期项与阻塞项，再按证据路径打开具体报告或 receipt。
- 子任务 receipt 只证明子任务完成；除非存在专门父任务 receipt 聚合 gate，否则不能自动证明父任务全部完成。
- 本文件只维护可继续执行的父任务真相，不把历史报告全文复制进来。

## 当前父任务定位

RedCap 的长期父任务不是“继续补一个 skill”，而是把当前 skill-root 承载形态逐步演进为可安装、可复活、可调度、可审计的 Agent runtime / CLI / 多层系统。

当前已完成的是若干控制面、路线图子任务、package readiness、Prism quorum 复验、shared-knowledge 远端模板绑定、首次启动身份/通知策略链路，以及父任务 completed child 的 runtime receipt 内容对应强门；尚未完成的是历史资产真实迁移 apply、正式公开发布、跨机器安装 E2E 与 P3-1 检索阈值研究。

## 已完成子任务

| 子任务 | 完成边界 | receipt / 证据 | 不能冒充的范围 |
|---|---|---|---|
| Evolution-grade 控制面可靠性与自我进化治理 | R0-R8 repo-owned 第一轮机制落地：baseline、候选池、旧资产、skill lifecycle、token 治理、Evolution closeout gate | `redcap-evolution-grade-control-plane-hardening-*` receipt；报告 `2026-04-25-redcap-evolution-grade-control-plane-hardening.md` | 不等于所有保障节点都变成宿主级 100% 强制 |
| 产品形态重定位与系统架构解耦 | 明确 RedCap 应从 skill-root 走向 runtime / CLI / 多层系统；完成路线图、provider freeze、文件字典、Feishu owner 收敛 | `redcap-runtime-productization-and-architecture-decoupling-*` receipt；报告 `2026-04-25-redcap-runtime-productization-and-architecture-decoupling.md` | 不等于完成物理目录拆分或正式 CLI/package |
| 原始意图覆盖审计硬门 | PM Gate/diagnose 接入 scope coverage，防止任务卡范围缩水后自证完成 | `redcap-original-intent-coverage-gate-*` receipt；报告 `2026-04-26-original-intent-coverage-gate.md` | 不等于自动语义理解所有复杂需求 |
| 执行层重构与公共知识库治理 | R0-R22 本地控制面落地：Prism availability、File Lookup Dictionary coverage、shared-knowledge 模板、`bin/redcap` 薄 facade | `redcap-execution-layer-and-shared-knowledge-governance-*` receipt；报告 `2026-04-26-execution-layer-and-shared-knowledge-governance.md` | 不等于远端 Gitee 绑定、历史资产物理迁移、正式 npm/pip/brew 分发完成 |
| 发布/打包前安全 gate | 未来 package / runtime 发布前的候选文件安全审计已接入 spec/diagnose/acceptance | `redcap-package-publish-safety-gate-*` receipt；报告 `2026-04-26-package-publish-safety-gate.md` | 不等于已经发布 package |
| Layer B 中插需求重计划强门 | 新增 U<n> 中插账本、CHANGE_INTAKE / REPLAN_REVIEW、父子完成边界和机器检查 | `layerb-change-intake-replan-gate-*` receipt；报告 `2026-04-26-layerb-change-intake-replan-gate.md` | 不等于 R0-R22 父任务全部完成 |
| Layer B 中插需求重排决策可见化 | 中插需求账本新增 `## 中插需求重排决策摘要` 强门，要求每个 U<n> 都写出处置、决策理由、全景影响和用户可见表达 | 报告 `2026-04-27-layerb-change-intake-replan-visibility-gate.md` | 不等于宿主层能 100% 物理拦截主 Agent 所有实时行为 |
| shared-knowledge Gitee 远端绑定 | 公共知识库最小模板已安全推送到 `https://gitee.com/norven63/redcap-arsenal.git`，并有 remote binding policy + live head proof | `redcap-shared-knowledge-gitee-remote-binding-*` receipt；报告 `2026-04-26-shared-knowledge-gitee-remote-binding.md` | 不等于历史 reports/lessons/identity 已迁移到公共库 |
| redcap-arsenal 本地实体仓库与 Norven 命名空间 | 已建立 `/Users/norven/.claude/skills/redcap-arsenal` 耐久本地 Git 工作区，Gitee 远端 head 为 `2e3b954338a4c397d299da88f460c6edf5a312d6`，模板/实体/远端均含 `users/Norven/.gitkeep` | 报告 `2026-04-27-redcap-arsenal-local-worktree-and-user-namespace.md`；外部公共库 commit `2e3b954` | 不等于历史知识内容已迁移或公共库已有实质条目 |
| 首次启动身份初始化与飞书策略收敛 | installer/revive 已初始化本地用户/Agent 状态面，确保 Norven 命名空间存在，并把 RedCap 官方飞书通知收敛到 `cli_a9579f5b12219bb5` + 节点汇报/人工介入两类触发 | 报告 `2026-04-27-first-start-identity-and-feishu-policy.md`；产物：`references/user-agent-identity-policy.json`、`references/feishu-notification-policy.json` | 本机目标 profile 已在 2026-04-28 用用户补充的正确 secret 重新注册，并通过 setup / node-report 真实发送验证 |
| Runtime receipt evidence correspondence hardening | 父任务 completed child 聚合已从 `receipt_glob` 字符串形态升级为真实 runtime receipt 内容核对，覆盖 task_id、report_path、completed、promise_pending、acceptance_status 与 git head | 报告 `2026-04-28-runtime-receipt-evidence-correspondence-hardening.md`；产物：`references/parent-receipt-aggregation-policy.json`、`redcap-parent-receipt-aggregation-check.py` | 不等于父任务整体 complete；P3-1 仍 deferred |

## 父任务待执行清单

| id | 来源 | 任务 | 状态 | 优先级 | 推荐下一步 | 依赖 / 边界 |
|---|---|---|---|---|---|---|
| P0-1 | U2 | Prism availability cache provenance/path 污染修复 | completed | P0 | 已增加 cache provenance、probe/policy 内容摘要和污染回归 | receipt: `prism-availability-cache-provenance-guard-*`；报告 `2026-04-26-prism-availability-cache-provenance-guard.md` |
| P0-2 | R0-R22 audit | R0-R22 原始编号可追溯化 | completed | P0 | 已新增机器可读 registry 和 checker，登记编号来源、状态、证据、置信度与延期边界 | receipt: `redcap-r0-r22-registry-*`；产物：`references/redcap-r0-r22-registry.json` |
| P1-1 | R0-R22 deferred | 执行层物理拆分 dry-run | completed | P1 | 已生成 dry-run manifest、checker、spec/diagnose/acceptance 接线和 Kimi Prism review；下一步进入 P1-2 历史资产迁移 dry-run | receipt: `redcap-execution-layer-split-dry-run-*`；产物：`references/execution-layer-split-dry-run.json` |
| P1-2 | R0-R22 deferred | 历史资产迁移 dry-run/apply | completed | P1 | 已生成 collection-level dry-run manifest、checker、spec/diagnose/acceptance 接线；真实 move/delete 另开 apply 任务 | receipt: `redcap-legacy-asset-migration-dry-run-*`；产物：`references/legacy-asset-migration-dry-run.json` |
| P1-3 | R0-R22 deferred | shared-knowledge 远端 Gitee 绑定 | completed | P1 | 已绑定 Gitee remote 并推送最小安全模板；后续真实知识条目写入另走 append-only 流程 | receipt: `redcap-shared-knowledge-gitee-remote-binding-*`；remote head: `a43c8ab543eff42a288e23ecc4eeb5bc6e954b78` |
| P1-4 | user inserted follow-up | redcap-arsenal 本地实体仓库与 Norven 命名空间 | completed | P1 | 已建立外部本地 worktree、推送 `users/Norven/.gitkeep`，并补模板/实体/远端三层口径和验收 | report: `2026-04-27-redcap-arsenal-local-worktree-and-user-namespace.md`；remote head: `2e3b954338a4c397d299da88f460c6edf5a312d6` |
| P2-1 | R0-R22 deferred | 正式 runtime / CLI / package 发布设计与实现 | completed | P2 | 已建立 npm/package-style readiness：`package.json private=true`、runtime package policy、candidate list generator、package safety gate、npm pack dry-run 对账和 CLI facade；真实公网发布仍另开 release 任务 | receipt: `redcap-runtime-cli-package-readiness-*`；产物：`references/runtime-package-readiness-policy.json` |
| P2-2 | change-intake report | 父任务 receipt 聚合 gate | completed | P2 | 已新增 parent receipt aggregation policy 与 checker，父任务仍因 P3-1 deferred 而不可 complete | receipt: `redcap-parent-receipt-aggregation-gate-*`；产物：`references/parent-receipt-aggregation-policy.json` |
| P2-3 | Prism review limits | Formal Prism quorum 恢复复验 | completed | P2 | 已复验 Kimi + Claude Code 可形成当前非 Codex 双路 Prism quorum；Codex CLI 被策略降为 last-resort fallback；Gemini timeout、Copilot frozen 继续诚实记录 | receipt: `redcap-prism-formal-quorum-provider-revalidation-*`；产物：`references/prism-provider-policy.json`、`compass/.workflow/prism-agent-availability.json` |
| P3-1 | retrieval roadmap | GraphRAG / 向量检索阈值研究 | deferred | P3 | 先继续 catalog + rg + metadata；当共享库规模越过阈值再引入 RAG/GraphRAG | 不能过早引入重型系统复杂度 |
| P3-2 | P2-2 reviewer risk | runtime receipt evidence correspondence hardening | completed | P3 | 已在 parent receipt aggregation checker 中校验真实 runtime receipt 内容对应关系，并补 acceptance 覆盖缺 receipt、错 report、当前 child pre-receipt 例外 | 父任务仍因 P3-1 deferred 保持 incomplete |
| P2-4 | user inserted follow-up | 首次启动初始化用户与 AI Agent 信息 | completed | P2 | 已新增 policy、init/check 脚本、installer/revive 接线、spec/diagnose/acceptance；并合并飞书唯一账号与低频触发策略 | report: `2026-04-27-first-start-identity-and-feishu-policy.md`；runtime: 本机 `cli_a9579f5b12219bb5` profile 已验证可发 |
| P2-5 | user trust gap | Layer B 中插需求重排决策可见化 | completed | P2 | 已将“为什么中插需求这样排”升级为 `.dev-task.md` 必填摘要和 change-intake checker 强门 | report: `2026-04-27-layerb-change-intake-replan-visibility-gate.md` |

## 推荐执行顺序

1. `P0-1`：先修 Prism availability cache 污染，因为它会影响后续所有 Prism 审查质量。
2. `P0-2`：建立父任务 registry，把 R0-R22 编号变成可机器检查的持续真相源。
3. `P1-1`：执行层物理拆分 dry-run，确认 RedCap 如何从 skill-root 迁出。（已完成）
4. `P1-2`：历史资产迁移 dry-run/apply，解决 docs / reports 长期淤积。（已完成 dry-run；真实 apply 另开任务）
5. `P1-3`：绑定 shared-knowledge 远端仓库。（已完成）
6. `P1-4`：实体化 redcap-arsenal 本地仓库与 Norven 命名空间。（已完成）
7. `P2-1`：正式 runtime / CLI / package readiness。（已完成 readiness；真实 public release 另开任务）
8. `P2-2`：父任务 receipt 聚合 gate。（已完成 gate；父任务仍 incomplete）
9. `P2-3`：formal Prism quorum 恢复复验。（已完成）
10. `P2-4`：首次启动初始化用户与 AI Agent 信息。（已完成 repo-owned 链路；本机目标 Feishu profile 已在 2026-04-28 验证可发）
11. `P2-5`：中插需求重排决策可见化。（已完成）
12. `P3-2`：runtime receipt evidence correspondence hardening。（已完成）
13. `P3-1`：GraphRAG / 向量检索阈值研究。（继续 deferred，等共享知识库规模触发）

## 当前不可声明

- 不可声明 RedCap 已经完成真实公网发布、跨机器安装 E2E 或全部目录物理迁移。
- 不可声明 RedCap 已经 npm publish 或完成跨机器公开分发；P2-1 只完成 package readiness 和候选包安全审计链。
- 不可声明历史报告和研究材料已经物理迁出执行层。
- 不可声明 shared-knowledge 历史 reports/lessons/identity 已经迁移到远端公共库；本轮只绑定并初始化公共库模板。
- 不可声明 `redcap-arsenal` 已有实质历史知识内容；当前只有安全模板、索引占位和 `users/Norven/` 命名空间占位。
- 当前机器已能通过 `cli_a9579f5b12219bb5` 真实发送飞书；后续若 profile/token 再次失效，RedCap 仍必须 fail-closed，不得回退旧账号或 webhook。
- 不可声明 P1-1 dry-run 已经执行真实 move/copy/link；它只证明迁移边界和风险已可审计。
- 不可声明 P1-2 dry-run 已经执行真实历史资产搬迁或删除；它只证明分类、断链计划、catalog 计划和回滚边界已可审计。
- 不可声明父任务已经 complete；aggregation gate 当前输出为 not-eligible，因为 P3-1 后续治理项仍 deferred。
- 不可声明 P3-2 已经完成 P3-1 的 RAG/GraphRAG 阈值研究；P3-2 只完成父任务 completed child receipt 内容对应强门。
