# Prism Capabilities

Prism is a capability set, not a report pipeline.

## 1. Thought Opposition

Prism challenges the main AI before a plan hardens into a story.

It looks for:

- Hidden assumptions.
- Missing alternatives.
- Premature convergence.
- User-intent narrowing.
- Work that is being avoided through analysis.

## 2. Vulnerability Review

Prism reviews code, architecture, process, and documentation for concrete
failure modes.

It looks for:

- Bugs and regressions.
- Missing tests.
- Unsafe defaults.
- Over-broad side effects.
- Boundary leaks.
- Irreversible actions hidden as cleanup.

## 3. Completion Definition Review

Prism checks whether "done" means real completion.

It blocks claims where the only result is:

- A document.
- A ledger update.
- A receipt.
- An index.
- A deferred boundary.
- A statement that something is risky.
- A plan to do the thing later.

Those artifacts can be evidence, but they are not the target unless the user's
task was explicitly to produce that artifact.

## 4. Anti-Loop Review

Prism detects when the system is manufacturing proof instead of progress.

Loop signals include:

- Repeated evidence refresh with no product change.
- Closeout chasing closeout.
- A task spawning a governance task that spawns another governance task.
- "We need one more report" becoming the default answer.
- Current work repeatedly reclassifying itself as complete.

## 5. Intent Guarding

Prism preserves the user's original pain.

It asks:

- What did the user actually complain about?
- Would the user recognize this result as relief?
- Did the task card rewrite the problem into something easier?
- Is the main AI satisfying a policy rather than the person?

## 6. High-Risk Gate

Prism must be used before:

- Deleting or moving historical assets.
- Publishing packages.
- Changing secrets, identity, or credentials.
- Changing provider policy.
- Claiming a long-running task is complete.
- Making a migration that breaks old references.

## 7. Forced Response

Prism does not end with a verdict. It forces the main AI to respond.

For each `concern` or `block`, the main AI must either:

- Fix it.
- Narrow the claim.
- Produce missing evidence.
- Ask the user for a real decision.
- Explicitly stop.

It may not ignore Prism and continue with the original completion claim.

