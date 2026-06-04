# Prism Review Modes

## `strategy_review`

Use before major direction is chosen.

Primary questions:

- Is the plan solving the user's actual problem?
- Is the scope honest?
- Is the main AI avoiding hard work through framing?

## `design_review`

Use before implementation.

Primary questions:

- Are the boundaries understandable?
- Is this smaller than the old system it replaces?
- What will fail first?

## `implementation_review`

Use after code or file changes.

Primary questions:

- What bug or regression is most likely?
- Are tests aligned with the risk?
- Did the implementation touch more than the task required?

## `completion_review`

Use before saying done.

Primary questions:

- What changed in reality?
- What is only evidence?
- What remains open?
- Would the user recognize this as completion?

## `anti_loop_review`

Use when work starts producing repeated reports, receipts, ledgers, or
verification refreshes.

Primary questions:

- Is the system proving work instead of doing work?
- Did the last iteration change anything meaningful?
- What is the smallest action that exits the loop?

## `migration_review`

Use before moving, deleting, archiving, or splitting assets.

Primary questions:

- What references break?
- What is the rollback path?
- What must remain discoverable for archaeology?

## `release_review`

Use before publication, registry, package, credential, or public-surface changes.

Primary questions:

- Is this authorized by the user?
- Are secrets and private history excluded?
- Can the action be reversed?

