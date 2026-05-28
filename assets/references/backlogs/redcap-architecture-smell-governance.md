# RedCap Architecture Smell Governance Backlog

## 使用说明

这份文档是 RASG 架构坏味治理 backlog 的人类导读。机器权威仍是 `references/backlogs/redcap-architecture-smell-governance.json`；这里负责让人快速看懂当前焦点、阶段顺序和术语。

## 当前状态总览（自动同步）

下面的自动同步块由 `redcap-backlog-check.sh sync .dev-task.md` 生成。

<!-- REDCAP_ARCHITECTURE_SMELL_GOVERNANCE:START -->
## 当前状态总览（自动同步）

### 这份机制对应哪里
- 机器权威：`references/backlogs/redcap-architecture-smell-governance.json`
- 人类说明：`references/backlogs/redcap-architecture-smell-governance.md`
- 当前焦点：`RASG-028 Execute RedCap Forge batch distillation into redcap-arsenal`
- 当前焦点说明：RASG-030 反空转方法论已完成；下一步执行 RedCap Forge 批量公共蒸馏，让 redcap-arsenal 从小规模种子样本走向更实质的公共武器库。

### 进入当前焦点前的前置热修
| 阻塞项 | 状态 | 阻塞对象 | 为什么必须先做 |
|---|---|---|---|
| HOTFIX-REVIVE-WORKSPACE-BOUNDARY 前置热修：修复 redcap revive 外部工作区边界盲区 | 已完成 | RASG-027 | External projects running redcap revive can mix the managed project's state with RedCap self-development state, corrupting the foundation that self-evolution and public arsenal work would depend on. |

### 阶段顺序
| 阶段 | 状态 | 主要条目 | 说明 |
|---|---|---|---|
| Fast consistency and truth-surface repairs | 已完成 | RASG-003 / RASG-007 / RASG-009 | Fix low-cost drift that misleads humans or agents even when runtime checks pass. |
| Knowledge architecture foundations | 已完成 | RASG-001 / RASG-002 / RASG-004 / RASG-014 | Turn the current multi-root knowledge layout into a deliberate federated retrieval system instead of a loose pile of knowledge directories. |
| Policy, evidence, and legacy-asset hygiene | 已完成 | RASG-005 / RASG-008 / RASG-013 | Reduce policy sprawl, evidence accumulation, and old/new transition ambiguity without damaging archaeology. |
| Runtime and host-adapter productization | 已完成 | RASG-006 / RASG-012 / RASG-016 | Move from skill-root compatibility to a cleaner installable runtime and host-adapter shape. |
| Advanced memory and shared arsenal evolution | 已完成 | RASG-010 / RASG-011 / RASG-015 | Keep full LLM-wiki, retrieval escalation, and public arsenal maturity visible without prematurely enabling heavyweight memory systems. |
| Root product-shape consolidation | 已完成 | RASG-017 / RASG-022 | Root product-shape consolidation is closed for the current pre-release pass: RASG-017 produced the target model, and RASG-022 completed one safe physical tranche plus explicit deferral of high-risk root groups. |
| Senior holistic smell audit | 已完成 | RASG-018 | Prevent user examples from being narrowed into single-point fixes by requiring a Prism-reviewed, senior-engineering review across RedCap's product shape, workflow guarantees, truth sources, knowledge/evidence lifecycle, package surface, and human-facing status model. |
| Holistic audit follow-up before release readiness | 已完成 | RASG-019 / RASG-020 / RASG-021 | Track the P1 issues discovered by RASG-018 that should be closed before RedCap is treated as a polished public runtime or CLI product. |
| Plan-only closure and Prism follow-up hardening | 已完成 | RASG-023 | Prevent design-only, plan-only, or route-only work from being treated as fully closed when a later physical apply or governance hardening task was explicitly required. |
| Workflow latency and gate stratification | 已完成 | RASG-024 | Workflow gate stratification is implemented: low-risk report/index drift no longer automatically invalidates release-grade E2E, while release, package, validator, secret and destructive-migration work remains fail-closed. |
| Pre-release freeze and artifact churn control | 已完成 | RASG-025 | Release-convergence cleanup has a hard boundary: normal evidence is archived or indexed, while only concrete first-release blockers may expand scope. |
| Completion semantics hardening | 已完成 | RASG-026 | Completion claims now fail when must-complete work is satisfied only by proof, preserve, defer, disabled, proposal-only, or human-decision boundary language; closeout runtime now checks this before receipt generation. |
| Self-evolution and public arsenal completion | 待推进 | RASG-027 / RASG-028 | Evolution Factory and RedCap Forge must become real recurring production systems, not policy/check/report surfaces. |
| Engineering directory final convergence | 已完成 | RASG-029 | The physical directory foundation must be made clean enough to support self-evolution, public arsenal growth and public release. |
| Anti-edge-ball drift methodology | 已完成 | RASG-030 | The recent mechanism-completion drift must be turned into a reusable lesson, Forge candidate and completion-regression pattern. |

### 条目状态
| 条目 | 所属能力 | 状态 | 优先级 | 一句话说明 |
|---|---|---|---|---|
| RASG-003 Fix shared-knowledge template README drift against external redcap-arsenal state | Fast consistency and truth-surface repairs | 已完成 | P0 | The template README clearly distinguishes the template source from the external arsenal worktree and states that the external worktree may contain reviewed entries. |
| RASG-007 Make package surface include/exclude rules single-source generated | Fast consistency and truth-surface repairs | 已完成 | P1 | One machine-readable source generates or validates all package include/exclude surfaces. |
| RASG-009 Improve closeout final-state observability when earlier retries failed | Fast consistency and truth-surface repairs | 已完成 | P2 | Status surfaces clearly show final state, previous failed attempts, and the successful repair/closure sequence. |
| RASG-001 Split the giant lessons.md into indexed topic modules | Knowledge architecture foundations | 已完成 | P0 | Lessons become a topic-indexed, small-file knowledge set with stable IDs, source anchors, and a human-readable index. No lesson should be lost or silently rewritten. |
| RASG-002 Create a federated knowledge lookup route across active knowledge, LLM-wiki-lite, cold archive, and public arsenal | Knowledge architecture foundations | 已完成 | P0 | A single knowledge gateway policy and command explain where to search first, when to fall back, and when exact-body reads are allowed. |
| RASG-004 Triage redcap-knowledge cold archive into preserve, translate, or prune classes | Knowledge architecture foundations | 已完成 | P1 | Each cold archive asset has a lifecycle class: preserve for archaeology, translate into active/public knowledge through Forge, or prune when safe. |
| RASG-014 Automate active task-report rotation from compass/docs to private archive | Knowledge architecture foundations | 已完成 | P2 | Recent reports stay visible; older reports move to redcap-knowledge with catalog and alias preservation. |
| RASG-005 De-sprawl references into authority policy, active configuration, and historical migration evidence | Policy, evidence, and legacy-asset hygiene | 已完成 | P1 | References have explicit classes and retrieval routes; one-off migration evidence is not confused with active policy. |
| RASG-008 Add stronger prism/runs evidence rotation, compression, and lookup policy | Policy, evidence, and legacy-asset hygiene | 已完成 | P2 | Formal evidence remains replayable while raw bulky output is timeboxed, compressed, or summarized through indexes. |
| RASG-013 Review Layer A loom legacy assets against modern Layer B and Prism architecture | Policy, evidence, and legacy-asset hygiene | 已完成 | P2 | Layer A assets are either clearly retained for external user-project workflows, migrated, or archived with compatibility notes. |
| RASG-006 Complete or explicitly block full runtime physical split before public release | Runtime and host-adapter productization | 已完成 | P1 | Either complete a real runtime-core split, or make the wrapper-based shape an explicit alpha contract with clear non-stability boundaries. |
| RASG-012 Unify host-adapter entry generation and avoid copied rule drift | Runtime and host-adapter productization | 已完成 | P2 | Host adapters are generated or verified from a single source and remain thin entry points. |
| RASG-016 Expand clean workspace E2E from same-machine clone to release-grade environment matrix | Runtime and host-adapter productization | 已完成 | P2 | Release readiness can distinguish local clean clone confidence from multi-environment product confidence. |
| RASG-010 Promote full LLM-wiki from sleeping future item to a thresholded active roadmap | Advanced memory and shared arsenal evolution | 已完成 | P1 | Full LLM-wiki has explicit activation criteria, owner gates, non-goals, and a first implementation tranche that does not prematurely enable heavy RAG. |
| RASG-011 Enforce retrieval observation metrics for FTS, RAG, and GraphRAG escalation | Advanced memory and shared arsenal evolution | 已完成 | P2 | Real retrieval misses and noisy lookup events are recorded in a structured place and checked before route escalation. |
| RASG-015 Define version coupling between RedCap runtime and external redcap-arsenal | Advanced memory and shared arsenal evolution | 已完成 | P2 | RedCap records which arsenal commit/head was validated and how runtime releases reference compatible arsenal states. |
| RASG-017 Consolidate root-level information architecture before product release | Root product-shape consolidation | 已完成 | P1 | Produce a Prism-reviewed root-level information architecture consolidation plan that inventories every root-level asset root, classifies it, defines a target parent model, maps aliases and consumers, and only then opens  |
| RASG-022 Apply root-level information architecture physical consolidation through safe semantic tranches | Root product-shape consolidation | 已完成 | P1 | Closed for the current pre-release pass by completing the shared-knowledge template physical tranche and explicitly deferring high-risk root groups before release readiness. |
| RASG-018 Run a senior holistic RedCap architecture smell audit instead of closing user examples one by one | Senior holistic smell audit | 已完成 | P1 | Produce a Prism-reviewed senior holistic architecture smell audit that explicitly reviews multiple domains, records 'found / not found / deferred' conclusions per domain, and gives every finding a durable disposition ins |
| RASG-019 Make human-facing CLI, status, and notification output understandable without RedCap internal jargon | Holistic audit follow-up before release readiness | 已完成 | P1 | Human-facing output is framed by problem, action, result, current task panorama, next step, and whether human intervention is needed. Internal mechanism names may appear only as secondary evidence links or glossary-backe |
| RASG-020 Separate public runtime contract from maintainer-only governance validators before npm or CLI release | Holistic audit follow-up before release readiness | 已完成 | P1 | Release readiness distinguishes the public runtime contract from maintainer/developer governance tools. The package manifest, runtime package readiness policy, and publish safety check agree on that boundary from a singl |
| RASG-021 Track Prism degradation frequency and keep conclusion gates resilient when providers are flaky | Holistic audit follow-up before release readiness | 已完成 | P1 | Prism status surfaces show the recent degradation rate, provider families involved, and whether the current task used full quorum or resource-limited evidence. Degradation above a defined threshold opens a governance act |
| RASG-023 Strengthen Prism and conclusion gates to catch plan-only closure follow-up gaps | Plan-only closure and Prism follow-up hardening | 已完成 | P1 | Prism prompts, conclusion policy, and closeout-facing validators require reviewers to check whether every deferred capability or future apply requirement has a durable task, backlog item, owner surface, or explicit no-fo |
| RASG-024 Stratify workflow gates by task risk to reduce avoidable multi-hour task latency | Workflow latency and gate stratification | 已完成 | P1 | Risk-based validation matrix implemented and wired into spec-check, diagnose, progress meter, clean workspace E2E post-result drift handling, and acceptance regression. |
| RASG-025 Stop pre-release governance cleanup from spawning endless cleanup work | Pre-release freeze and artifact churn control | 已完成 | P0 | Done: release-convergence cleanup now has a hard boundary that prevents normal reports, receipts, indexes and Prism evidence from automatically becoming fresh cleanup scope. |
| RASG-026 Harden completion semantics against proof/defer false closure | Completion semantics hardening | 已完成 | P0 | Done: completion claims now fail when must-complete work is satisfied only by preserve, defer, disabled, proposal-only, or human-decision boundary language; spec-check, diagnose, closeout runtime, Prism review, and full acceptance have passed. |
| RASG-027 Make Evolution Factory an active harvest pipeline instead of report-section compliance | Self-evolution and public arsenal completion | 已完成 | P0 | Done: self-upgrade now has an active harvest ledger, producer, stale-record gate, real hotfix sample, closeout/spec/diagnose/progress integrations, and targeted Kimi + Claude Code Prism pass. |
| RASG-028 Execute RedCap Forge batch distillation into redcap-arsenal | Self-evolution and public arsenal completion | 待推进 | P0 | Grow redcap-arsenal beyond the current reviewed seed entries through a safe, deduplicated, append-only Forge batch. |
| RASG-029 Finish engineering directory convergence as the foundation for self-evolution and arsenal growth | Engineering directory final convergence | 待推进 | P0 | Close the remaining root-directory, compatibility-anchor and prism/runs lifecycle confusion before public release. |
| RASG-030 Promote anti-edge-ball drift methodology into lessons and public arsenal candidates | Anti-edge-ball drift methodology | 已完成 | P0 | Done: outcome-first anti-drift methodology is now in lessons, policy checks, Evolution harvest, Prism conclusion rules, and a reviewed public arsenal entry. |

### 术语对照
| 术语 | 人话解释 |
|---|---|
| RASG（Architecture smell governance item） | RedCap 架构坏味治理条目，用来记录仍会影响工程健康、发布准备或长期演进的设计债务。 |
| tranche（Small safe implementation slice） | 一次只处理一个可验证的小切片，避免大规模重构同时破坏多个真相源。 |
| current focus（Active debt item） | 当前正在执行或刚完成收口的 backlog 项，必须和 .dev-task.md 的 backlog_item 对齐。 |
| gate stratification（Risk-based validation matrix） | 按任务风险选择验证强度：小改动走轻量门，普通实现走标准门，发布/迁移类任务才走完整发布级门禁。 |
<!-- REDCAP_ARCHITECTURE_SMELL_GOVERNANCE:END -->
