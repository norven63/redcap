# Prism Session Protocol

This contract is consumed by `runtime/prism/bin/prism`.

Prism is an opposition system, not an authority system. RedCap must not blindly
obey Prism, and it must not average provider disagreement into a vague
consensus.

## Communication Boundary

Prism uses a hybrid channel model:

- stdout is for bounded command results, status JSON, and short summaries.
- files are the canonical carrier for formal requests, provider reviews,
  merged decisions, and session metadata.
- full request JSON may be sent through stdout only by explicit operator choice,
  using `runtime/prism/bin/prism brief --inline-request`.

The default `brief` command prints the request path and a compact summary, not
the full request body.

## Task Session

A full Prism task owns one run directory:

```text
assets/evidence/prism/<task-id>/
```

The run directory contains:

- `request.json`
- `session.json`
- `<provider>.brief.md`
- `<provider>.review.json`
- `merge.json`

The session manifest uses `runtime/prism/schemas/prism-session.schema.json`.
The active Claude Code provider has one task-scoped session handle: the
explicit `--session-id` used for the first task call. Historical Kimi session
records remain readable, but they cannot be resumed or dispatched.

All follow-up rounds for the same Prism task must use those same handles until
the task reaches `converged`, `main-decided`, `escalated`, `expired`, or
`closed`.

Provider calls should go through:

```bash
runtime/prism/bin/prism-dispatch --provider claude-code --manifest assets/evidence/prism/<task-id>/session.json --request assets/evidence/prism/<task-id>/request.json --review-out assets/evidence/prism/<task-id>/claude-code.review.json
```

Before dispatching a follow-up provider round, the dispatcher runs:

```bash
runtime/prism/bin/prism session-check --manifest assets/evidence/prism/<task-id>/session.json --require-existing-session
```

If this command exits non-zero, the dispatcher must not call the provider again.
RedCap must either make a documented main-agent decision or escalate to Norven.

Provider runtime calls default to `--timeout-seconds 300` and
`--max-retries 5`. Retries are only for provider timeout exits; after the final
timeout, the dispatcher writes the raw attempt ledger and reports
`provider-timeout` instead of treating the missing review as acceptance.
The fast self-check uses synthetic subprocess timeouts rather than deliberately
hanging a real provider network call.

## Disagreement Handling

RedCap owns the final action. Prism owns opposition.

For each `concern` or `block`, RedCap must choose one of:

- accept: the concern is valid and changes the plan or claim; this requires
  implementation and verification evidence.
- reject: the concern is invalid, with concrete evidence. A bounded
  same-provider rebuttal may be collected, but a later Claude Code `pass`
  cannot close the concern by itself; the Cap resolution trace remains
  mandatory.
- escalate: the concern is a value tradeoff, ambiguous requirement, or unresolved
  provider conflict that needs Norven.

The executable record for this choice is `prism-concern-resolution`. A
`merge` with `must_respond=true` cannot authorize FSM movement to
`IMPLEMENTING`, `VERIFYING`, or `TEMPORARY_USABLE` unless
`runtime/bin/redcap prism-resolution` accepts that record. If the record is
`escalated`, RedCap must stop and ask Norven instead of treating the escalation
as implementation clearance.

Provider concern handling is bounded:

1. Round 1: Claude Code reviews the request.
2. RedCap may send one focused rebuttal or changed-plan request in the existing
   Claude Code session.
3. Claude Code may revise, hold, or narrow its conclusion.
4. The default maximum is 3 rounds.
5. `prism-dispatch` must pass `session-check` before every follow-up provider
   call.
6. If concern remains after the round cap, RedCap must either make a documented
   main-agent decision or escalate to Norven.

The phrase "discuss until agreement" is invalid without this round cap.

## Convergence

A Prism task is converged when at least one of these is true:

- Claude Code returns `pass` and no earlier unresolved concern remains;
- a concern is accepted and implemented or reflected in the claim;
- RedCap rejects a concern with independent source, contract and test evidence
  and records the Cap resolution trace;
- RedCap escalates the unresolved conflict to Norven.

Convergence does not mean completion. It only means Prism opposition for this
task has been handled.

## Restart Recovery

After a main-agent restart, RedCap recovers an unfinished Prism task by reading:

```text
assets/evidence/prism/<task-id>/session.json
```

If a provider session handle is missing or expired, RedCap must mark that
provider `expired` and either restart the Prism task from the original request
or escalate if continuity is essential.
