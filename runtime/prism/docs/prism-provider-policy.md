# Prism Provider Policy

## Current Provider

Prism has one active provider: Claude Code.

Kimi is retired from live dispatch. Current Gate, Loom, revival loop, complete
E2E, OL-11, provider health, retry, fallback, and release paths must not invoke,
wait for, or count Kimi. The machine-readable authority is
`assets/contracts/prism-provider-policy.json`.

## Historical Compatibility

Historical Kimi raw output, metadata, reviews, session manifests, and fixtures
may still be parsed read-only. This compatibility exists so old evidence remains
auditable. It never creates a current quota, fallback, session, or dispatch
right.

The dispatcher must reject a live Kimi request before process launch. Its
self-check places a marker-writing fake `kimi` executable on `PATH` and proves
the marker is not created.

## Review Meaning

The current mode is `single-provider-strong-review`. It is not heterogeneous
red-team review and must not be described as multi-provider consensus.

Claude Code provides external opposition. Cap remains responsible for the
decision and implementation. A review `pass` is evidence, not authority.

## Concern Resolution

A Claude Code `concern` or `block` cannot be erased merely by asking the same
provider again. A later `pass` may add evidence, but closure also requires a
machine-checkable Cap resolution trace with:

- provider review references
- decision and rationale
- source-code references
- contract references
- test-run references
- the relevant Norven decision reference

Cap may accept and fix the concern, reject it with independent evidence, or
escalate an irreducible value decision to Norven.

## Policy Changes

No automatic fallback provider is allowed. Adding or replacing a provider is a
human-approved policy change and must update the authority contract, runtime,
package, negative dispatch tests, and documentation together.
