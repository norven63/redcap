# RedCap Revival Map

> Status: draft hypothesis, not validated architecture authority and not a
> completion claim.
>
> Use rule: keep/redesign/discard decisions in this map can guide questions,
> but cannot authorize or block implementation until challenged by Prism and
> backed by bounded extraction evidence for the component being built.
>
> Goal: recover the RedCap that was trying to exist: an engineering-grade AI
> team runtime. Do not revive the old repository's report spiral, closeout
> inflation, root sprawl, or evidence flood.

## Extraction Method

This pass used bounded archaeology. It read old RedCap authority and index
surfaces first, then asked Prism for opposition.

Primary old sources sampled:

- `README.md`
- `ARCHITECTURE.md`
- `assets/knowledge/design-principles.md`
- `assets/references/hook-standards.md`
- `assets/references/host-session-capability-matrix.json`
- `assets/references/runtime-memory-architecture.md`
- `assets/references/workflow-gate-stratification-policy.json`
- `loom/dispatcher/state-machine.md`
- `assets/references/layera-layerb-boundary-policy.json`
- `assets/references/completion-semantics-policy.json`
- `assets/references/conclusion-prism-policy.json`
- `assets/references/review-tracks.json`
- `assets/references/redcap-system-layers.md`
- `assets/references/knowledge-gateway-policy.json`
- `assets/references/retrieval-escalation-policy.json`
- `assets/references/llm-wiki-lite-policy.json`
- `assets/references/full-llm-wiki-policy.json`
- `assets/references/full-llm-wiki-roadmap.json`
- `assets/references/redcap-forge-policy.json`
- `assets/references/backlogs/*.json`
- `assets/references/redcap-parent-task-ledger.md`
- `compass/evolution/README.md`
- `compass/evolution/candidates.json`

Intentionally avoided as default context:

- old `task-reports` bodies
- raw `prism/runs`
- closeout receipts
- local `.dev-task.md`
- local `.env`, prompt dumps, runtime caches

Those may be opened later only by exact path and exact question.

## Prism Opposition Summary

Kimi verdict: revive with amputations.

Main pressure: the new RedCap must not mistake documentation/report apparatus
for runtime. Rebuild core execution, session ownership, hooks, and completion
semantics before importing evidence machinery.

Claude Code verdict: keep the North Star, shrink the machinery.

Main pressure: old RedCap had strong engineering instincts, but closure and
knowledge mechanisms became too many artifacts. New RedCap should keep the
mechanisms as concepts, then redesign them smaller.

Shared Prism warnings:

- Closeout must not reproduce itself.
- Knowledge routing must not become a six-layer maze before the runtime works.
- Hook claims must stay honest about host limits.
- Public release, provider policy, secrets, destructive migration, and identity
  changes remain human-gated.
- "Documented" is not "implemented."

## Ideal RedCap Shape

RedCap should be a small, installable, recoverable, auditable AI engineering
runtime with these layers:

| Layer | Keep | Redesign Smaller |
| --- | --- | --- |
| Runtime / Loom | Task execution, FSM, role handoff, recovery, closeout | Minimum kernel is only a bootstrap layer; full role orchestration is required before complete revival |
| Prism | Heterogeneous opposition for high-risk decisions | Keep current new Prism small: Kimi + Claude Code only |
| References / Contracts | Machine-readable policies and boundaries | Only promote a policy when a component consumes it |
| Knowledge | Lessons, design philosophy, stable concepts | Three-tier gateway first; advanced wiki later |
| Evolution / Forge | Candidate capture, promotion, no-promote decisions | Capture high-signal learnings without blocking every tiny task |
| Evidence | Proof of changed reality | Evidence supports claims; it does not become the product |
| Host Adapters | Thin Codex / Claude / Gemini / other host bridges | One adapter at a time, with live verification |
| Identity | Private Cap identity and proposal boundary | Never auto-edit active identity from background tasks |
| Human Reading | README, doctrine, map, dictionaries | First-read material, not machine authority |

## What Old RedCap Got Right

### 1. Hook System

The hook design was valuable because it separated "things an LLM might forget"
from "things the system must physically check."

Carry forward:

- Hook invariants first, implementation second.
- Host configuration must be a thin adapter.
- RedCap-native scripts are the single source of hook behavior.
- SessionStart is a re-anchor point.
- Stop / SessionEnd is a review, closeout, and cleanup point.
- PreToolUse can be an ownership-claim point for mutating actions.
- Hook claims require live markers; config presence is not proof.
- Hooks are host-limited; they must not claim universal reply veto unless the
  host actually exposes and verifies it.

Redesign:

- Do not start by recreating every old hook.
- Start with one host adapter and two events: `SessionStart` and `Stop`.
- Add `PreToolUse` only when session ownership needs a physical claim point.
- Treat notification hooks as secondary, not core runtime truth.

Discard:

- Hook business rules duplicated across host config files.
- Hook success language that hides degraded or unverified host behavior.
- Hook chains that generate more audit artifacts than decisions.

### 2. Session Isolation

The session isolation design was one of old RedCap's strongest ideas.

Carry forward:

- Workspace-level pending closure is not ownership.
- Only the owning session may drive closeout.
- Ownership should bind to `task_id + confirmed_hash + active_slice`.
- Non-owning sessions may observe and advise, but must not clear blockers or
  complete closeout.
- Runtime root, project workspace, and user-private state must be separate.
- Revive must pass the resolved task file and workspace context through every
  layer; falling back to repo-local `.dev-task.md` is a leak.

Redesign:

- Use one explicit session manifest per active runtime session.
- Use one ownership claim/check interface, not scattered checks.
- Keep advisory reconcile separate from authoritative closeout.
- Make ownership checks cheap enough to run before every mutating action.

Discard:

- Global workspace state as proof of current-session authority.
- Any fallback that silently writes external project state into the RedCap repo.
- Session cleanup that destroys evidence before ownership or closeout is known.

### 3. FSM And Workflow Gates

Old RedCap had two different state-machine ideas, both worth keeping but not
copying wholesale.

Layer A carry forward:

- Explicit FSM for external project work.
- Roles are phases, not vibes: PM, Architect, Developer, QA, Reviewer.
- QA and Review failures route by root cause: code, design, requirement.
- Paused and degraded states are first-class.
- Pending actions are persisted before state transitions.
- Role/session identity belongs in state, not chat memory.

Layer B carry forward:

- Layer B does have a state machine, but it is distributed:
  `.dev-task.md + promise ledger + pending closure + closure ledger +
  closeout runtime + session hooks`.
- Important states: `REANCHORED`, `TASK_LOCKED`, `PLANNING`, `EXECUTING`,
  `CHANGE_INTAKE`, `REPLAN_REVIEW`, `REVIEW_PENDING`, `CLOSEOUT_PENDING`,
  `CLOSED`, `BLOCKED`.
- PM Gate and change-intake are not bureaucracy; they protect the original
  user intent from being silently narrowed.
- Prism review must bind to current task identity; old reviews cannot be reused
  as current acceptance.

Redesign:

- New RedCap may use the FSM kernel as a bootstrap layer, but complete revival
  requires the full role workflow machine.
- Gate strength should be risk-based, but the first version can use two tiers:
  `standard` and `structural`.
- A closeout record should be one structured object before it becomes a
  directory of ledgers, receipts, and audits.
- Acceptance should test transitions, ownership, and forbidden completion
  claims before it tests report formatting.

Discard:

- Closing a task by proving that a future task exists.
- Multi-hour validation cost for low-risk text/index changes.
- Validator chains that cannot explain which reality changed.

### 4. Completion Semantics

This is the core immune system.

Carry forward:

- Done means real implementation changed the target reality.
- `proof-only`, `mechanism-only`, `plan-only`, `preflight-only`,
  `preserve-with-proof`, `implemented-proposal-only`, `disabled-by-default`,
  and `blocked-by-human-decision` are not completion.
- A strategic task must separate physical target, mechanism target, evidence
  target, and non-completion labels.
- Completion claims need stronger review than ordinary progress summaries.

Redesign:

- Make completion semantics a small validator and a writing discipline.
- Avoid making every task generate a full closeout bundle.

Discard:

- Receipt worship.
- "Not blocking this task" language that hides unfinished root outcomes.
- Reports that turn blocked human decisions into done states.

### 5. Knowledge And Experience System

Old RedCap's knowledge ambitions were genuinely good, but over-layered.

Carry forward:

- Progressive disclosure: index first, exact source second, raw archive last.
- Lessons should be small, indexed, source-anchored modules.
- LLM-wiki entries must be private, source-anchored, reviewed, and
  non-authoritative.
- Full wiki and background distillation are proposal/review workflows, not
  automatic source mutation.
- RedCap Forge is the public-promotion pipeline: capture, distill, privacy
  review, dedupe, structure, index, promote or no-promote.
- Public arsenal entries must be append-only, user-namespaced, deduplicated, and
  indexed before body reading.
- Retrieval upgrades must be threshold-driven.

Redesign:

- Collapse the first rebuild to three tiers:
  1. working knowledge index
  2. reviewed private wiki
  3. public arsenal after Forge
- Keep cold archive and raw evidence outside default retrieval.
- Add FTS only when catalog/metadata/rg becomes noisy.
- Add RAG only after measured semantic retrieval misses.
- Add GraphRAG only after relationship-heavy questions repeatedly fail simpler
  retrieval.

Discard:

- Default full-corpus loading.
- Treating LLM-wiki as source of truth.
- Public writeback from private wiki without Forge.
- Raw private reports, identity text, runtime evidence, or Prism raw output as
  knowledge entries.

### 6. Prism

Carry forward:

- Prism exists to oppose, not approve.
- Disagreement should be preserved, not averaged away.
- Full Prism requires both Kimi and Claude Code under current new policy.
- Resource-limited Prism must be labeled honestly.
- Prism is mandatory for architecture, governance, completion,
  release-readiness, long-term roadmap, migration, deletion, secrets, provider
  policy, and irreversible choices.

Redesign:

- Keep new Prism as the smallest useful pair.
- Use Prism to challenge claims before writing long reports.
- Store review outputs only when they change a decision or prove a high-risk
  gate.

Discard:

- Provider inflation.
- Self-review masquerading as Prism.
- Raw run hoarding.
- Prism pass as completion.

### 7. Productization And Release

Carry forward:

- RedCap's North Star is independent runtime / CLI / multi-layer system.
- Host skills are adapters, not the product.
- Runtime, project workspace, and user/private state must be physically
  separated.
- Public release requires human choices: license, registry, package name,
  version, credentials, rollback, distribution boundary.
- Copy-first, alias-first, delete-last is the right migration posture.

Redesign:

- One installable bootstrap before full package ambition.
- One host adapter before host matrix parity.
- Public package surface should distinguish runtime contract from maintainer
  tools.

Discard:

- Claiming package-readiness as public-release-readiness.
- Shipping historical evidence or local state as product surface.
- Moving or deleting old anchors before references and rollback are proven.

## What Should Be Rebuilt First

1. **Runtime Boundary Kernel**
   - Defines runtime root, project workspace, user-private state.
   - Provides a current task identity object.
   - No reports, no closeout pile.

2. **Session Ownership Kernel**
   - Claim/check interface.
   - Binds ownership to task identity and workspace.
   - Non-owner sessions become advisory-only.

3. **Minimal FSM Kernel**
   - Layer A: explicit state machine.
   - Layer B: full role workflow machine rebuilt without the old report and
     receipt pathologies.
   - Tests cover transition legality and blocked states.

4. **Hook Adapter Contract**
   - Host adapter API.
   - SessionStart and Stop first.
   - Live marker verification before capability claims.

5. **Completion Semantics Validator**
   - Rejects proof-only, plan-only, proposal-only, disabled, deferred, and
     human-blocked completion claims.
   - Keeps root outcome open when reality did not change.

6. **Knowledge Gateway v1**
   - Working index.
   - Reviewed private entries.
   - Public Forge candidates.
   - No RAG/GraphRAG until threshold evidence exists.

7. **Prism Integration**
   - Generate request briefs.
   - Run Kimi and Claude Code when available.
   - Merge by strictest verdict.
   - Force accepted/rejected/changed-plan response.

## Explicitly Not Rebuilt Yet

- Full old closeout runtime.
- Feishu notification chain.
- Full provider matrix.
- Full LLM-wiki product.
- RAG, GraphRAG, vector stores.
- Public release machinery.
- Raw evidence lifecycle automation.
- Historical report migration.
- Multi-host hook parity.

These may return later only when a bounded component needs them.

## Current Gaps In This Map

- It is still a synthesis, not a line-by-line old RedCap audit.
- It has not replayed old task reports or raw Prism runs.
- It has not verified old script behavior in the moved old repository.
- It has not chosen the exact new runtime file layout.
- It has not implemented the kernels listed above.

That is intentional. The next correct move is not more archaeology by default;
it is to build the first small runtime boundary and let future extraction serve
that component.

## Decontamination Index

This section prevents the map from importing old RedCap pathology under cleaner
names.

### Omission Traceability

| Prior omission | Covered by | Pass criterion |
| --- | --- | --- |
| Hook mechanism | `Hook System`, `Hook Adapter Contract` | New hook work starts from invariant + host adapter contract, not copied host config |
| Session isolation | `Session Isolation`, `Session Ownership Kernel` | Only owner session can mutate closeout; non-owner sessions are advisory-only |
| FSM gates | `FSM And Workflow Gates`, `Minimal FSM Kernel` | Transitions are explicit and tested; blocked states cannot become done by prose |
| Knowledge / experience system | `Knowledge And Experience System`, `Knowledge Gateway v1` | Index-first, source-anchored, non-authoritative, no raw private/public writeback |
| Retrieval algorithm upgrades | `Knowledge And Experience System` | FTS/RAG/GraphRAG require measured threshold evidence and Prism-reviewed activation |
| Completion semantics | `Completion Semantics`, `Completion Semantics Validator` | Proof-only, plan-only, proposal-only, disabled, deferred, and human-blocked states fail completion |
| Prism usage | `Prism`, `Prism Integration` | Prism opposes claims and preserves stricter verdicts; it is not an approval stamp |

### Legacy Prohibition Register

Do not reintroduce these as first-class mechanisms:

- report-as-progress
- receipt-as-completion
- closeout that creates more closeout work before changing reality
- raw evidence as default context
- provider count as quality
- host config as rule authority
- workspace-level pending closure as ownership proof
- public release readiness without human release authorization
- wiki or RAG output as source of truth
- migration by deletion before copy/alias/rollback proof

### Extraction Pass Gate

This pass is complete only as an extraction blueprint:

- It corrects the previous omission by explicitly covering hooks, session
  isolation, FSM gates, knowledge systems, and retrieval escalation.
- It does not claim those mechanisms are implemented.
- It does not authorize old code migration.
- It does not claim old RedCap has been fully audited.
- It sets the next verification target: an end-to-end trace test chaining
  Hook Adapter Contract -> Session Ownership Kernel -> Minimal FSM Kernel ->
  Completion Semantics Validator, using only new workspace artifacts and
  asserting that no old module path is imported.

## Decision Rule

When deciding whether to import an old RedCap idea, ask:

1. Does it make user-intended reality change more reliably?
2. Does it reduce reliance on chat memory?
3. Does it have a bounded owner and lifecycle?
4. Can it be checked without reading a pile of reports?
5. Does it avoid creating a new artifact whose only job is to explain another
   artifact?

Import only if the answer is yes, or if the risk is high enough that Norven
explicitly wants the heavier mechanism.
