# RedCap Revival Doctrine

> Purpose: revive the RedCap that should have existed, not the RedCap that
> learned to prove itself complete while becoming harder to use.

## Authority

- Norven is the human strategic owner. He may void or amend this doctrine at any
  time.
- Until Norven explicitly ratifies it, this file is a working constraint, not a
  constitution.
- This file cannot prove that any RedCap capability is complete. Only working,
  bounded components plus proportionate verification can do that.
- This file must not spawn nested doctrine, reports, receipts, ledgers, or
  follow-up governance unless Norven explicitly asks for them.

## Source Boundary

This doctrine was extracted from a small source set in the old RedCap reference
workspace:

- `README.md`: RedCap as an engineering AI team/runtime, not a harder single
  agent.
- `ARCHITECTURE.md`: Loom / Compass / Prism / References, authority chains,
  externalized state, and proof surfaces.
- `assets/knowledge/design-principles.md`: P-1 through P-5.
- `assets/references/backlogs/*.json`: long-route truths and unfinished target
  shape.
- `assets/references/redcap-parent-task-ledger.md`: completed boundaries,
  blocked release edges, and "must not claim" language.
- `compass/evolution/README.md` and `compass/evolution/candidates.json`:
  controlled experience harvest, promotion, and no-promote boundaries.

The extraction intentionally did not bulk-read old task reports, raw Prism runs,
closeout receipts, or runtime evidence piles. Those are archaeology sources,
not first-read doctrine sources.

## Carry Forward

### 1. Outcome before proof

If a task claims completion, it must name the user's intended reality and show
what changed there. A document, receipt, report, ledger update, or plan can
support the claim; it cannot replace the changed reality.

Trigger: if a future component only creates evidence, then mark the component
as evidence-only and keep the root outcome open.

### 2. Explicit authority chains

Every state surface must say whether it is canonical truth, derived state,
mirror state, or evidence. A mirror cannot promote itself into truth, and a
validator cannot become the thing it validates.

Trigger: if a file stores state, then its owner, lifecycle, and write authority
must be visible before another component depends on it.

### 3. State externalization without state sprawl

Important task state must not live only in chat memory, but external state must
stay small, indexed, and bounded. State exists to let work resume and be checked,
not to manufacture a new reading burden.

Trigger: if a state artifact needs another state artifact to explain whether it
matters, then reduce or index it before adding more process.

### 4. Prism opposes; it does not approve

Prism is a source of heterogeneous resistance. It may find blockers, concerns,
or missing evidence, but it does not complete work for RedCap and it does not
launder a completion claim.

Trigger: if a task is high-risk, irreversible, release-facing, migration-facing,
or likely to self-approve, then Prism must challenge the claim before completion
is asserted.

### 5. Human judgment is strategic; AI closure is operational

Norven supplies direction, values, vetoes, and final judgment on value-laden
questions. AI agents must handle detailed review, consistency checks, and
verification loops instead of dumping detail burden back onto the human.

Trigger: if a decision is value-laden, irreversible, identity-affecting,
license/release-facing, or beyond available evidence, then stop and ask Norven.
Otherwise continue autonomously.

### 6. Documentation is inheritance, not completion

Design must be recorded so future agents can inherit intent, but recording a
design is not implementation. Good docs lower cognitive load; bad docs create
ceremony.

Trigger: if a document would be used as the only evidence that behavior changed,
then narrow the claim to "documented" and keep implementation open.

### 7. Copy-first, delete-last

Migrations must preserve discoverability and rollback. Old anchors can be
bridged, mirrored, or retired only after new anchors are proven and references
are accounted for.

Trigger: if an action moves, deletes, renames, archives, releases, or changes
credentials, then require a rollback path and explicit human or Prism gate
appropriate to the risk.

### 8. Evolution is a harvest pipeline, not a memory dump

Lessons, identity growth, public arsenal entries, and governance improvements
must pass through candidate, review, promotion, no-promote, or deferred-with-
owner states. Raw reports and private traces do not become public knowledge.

Trigger: if a high-value user correction, Prism verdict, bug, process storm, or
closeout blocker appears, then record the candidate decision; do not silently
assume "nothing to promote."

### 9. Progressive disclosure beats archaeology flood

Agents should start from indexes, source maps, and small canonical docs, then
open exact sources only when needed. Long archives are evidence reservoirs, not
default context.

Trigger: if an agent wants to read an entire old directory, then it must first
state the question, candidate files, and stop condition.

### 10. Bounded components before grand systems

The revived RedCap should grow as small components with clear interfaces. Loom,
Compass, Prism, References, Forge, memory, release gates, and runtime facades
are concepts to recover only when a bounded component needs them.

Trigger: if a design introduces a subsystem name, then it must also name the
first bounded component, its owner, and what is explicitly out of scope.

## Do Not Carry Forward

- Old `.dev-task.md` state, raw `prism/runs`, closeout receipts, prompt dumps,
  local `.env`, or task-report piles as default context.
- Provider inflation. New Prism actively dispatches only Claude Code unless
  Norven approves a provider-policy change; Kimi is historical-read-only.
- Completion laundering: "a receipt says complete" is never enough.
- Report spirals: a concern should produce a small correction, narrowed claim,
  missing evidence, or human decision, not another governance stack.
- Root sprawl: compatibility anchors may exist, but every visible entry needs an
  owner and lifecycle.
- Release claims without human release authorization.

## Unfinished Philosophy Worth Preserving

- RedCap should become an installable, recoverable, auditable runtime / CLI /
  multi-layer system, not remain a host-specific skill folder.
- Runtime root, project workspace, and user/private state must be separated.
- Public knowledge must go through Forge-style distillation: source anchor,
  privacy review, dedupe, index-first retrieval, and append-only promotion.
- Full LLM-wiki, RAG, GraphRAG, and vector memory are thresholded future work,
  not default architecture.
- Public release remains human-gated: license, credentials, registry, version,
  rollback, and distribution boundary are not AI-autonomous decisions.
- Control-plane migration should remain copy-first / alias-first / delete-last,
  with old anchors preserved until references and rollback are proven.

## Acceptance For This File

This file is valid only as a revival constraint if:

- It stays short enough to be first-read material.
- It points to old RedCap source classes without copying old evidence piles.
- It names triggers, not just aspirations.
- It cannot be cited as proof that RedCap itself is rebuilt.
- It can be replaced by a better ratified doctrine without preserving its own
  process history.
