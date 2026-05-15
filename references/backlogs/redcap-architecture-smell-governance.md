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
- 当前焦点：`RASG-022 Apply root-level information architecture physical consolidation through safe semantic tranches`
- 当前焦点说明：RASG-022 当前阶段已收口：shared-knowledge 模板根目录迁移已完成；剩余高风险根目录已用显式延期收据锁定后续触发条件。

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

### 术语对照
| 术语 | 人话解释 |
|---|---|
| RASG（Architecture smell governance item） | RedCap 架构坏味治理条目，用来记录仍会影响工程健康、发布准备或长期演进的设计债务。 |
| tranche（Small safe implementation slice） | 一次只处理一个可验证的小切片，避免大规模重构同时破坏多个真相源。 |
| current focus（Active debt item） | 当前正在执行或刚完成收口的 backlog 项，必须和 .dev-task.md 的 backlog_item 对齐。 |
<!-- REDCAP_ARCHITECTURE_SMELL_GOVERNANCE:END -->
