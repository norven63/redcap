# Prism Review: Copilot Protected Fallback Policy

## Scope

This run reviewed `P2-6 Prism Copilot protected fallback policy`.

The reviewed rule is narrow and explicit: Copilot CLI must not be used as a normal Prism, stop-review, live-health, baton or direct RedCap CLI provider. It is allowed only when both Claude Code and Kimi are unavailable.

## Roster

- Claude Code / Claude family: reviewer
- Kimi / Moonshot family: challenger attempt, resource-limited after post-fix rerun

Copilot was not used for this Prism review.

## Verdict

Resource-limited pass.

Claude Code's first review found a real blocker in `redcap-reviewer-order.py`: protected fallback had been grouped with last-resort filtering, which would wrongly suppress Copilot after it had already passed its own Claude Code/Kimi unavailable gate. The fix separated protected-fallback gating from Codex last-resort suppression.

Claude Code post-fix review passed with no blockers. Kimi independently found the same original blocker before the fix; its post-fix rerun reached provider usage limits before producing final JSON, so this run is intentionally bound as resource-limited rather than full quorum.

## Accepted Result

- Copilot is policy-marked as `protected-fallback`.
- Live health probing reports Copilot as `policy-suppressed` when Claude Code or Kimi is available, without executing Copilot.
- Prism roster checks reject Copilot while Claude Code or Kimi is available.
- stop-review ordering suppresses Copilot even if manual order tries to put Copilot first, as long as Claude Code or Kimi is available.
- When Claude Code and Kimi are both unavailable, Copilot remains available as fallback and suppresses Codex last-resort.
- Codex remains last-resort only.

## Evidence

- `prism/runs/20260507-prism-copilot-protected-fallback-review/collect/reviewer/raw.txt`
- `prism/runs/20260507-prism-copilot-protected-fallback-review/collect/reviewer/postfix-raw.txt`
- `prism/runs/20260507-prism-copilot-protected-fallback-review/collect/reviewer/parsed.json`
- `prism/runs/20260507-prism-copilot-protected-fallback-review/collect/challenger/raw.txt`
- `prism/runs/20260507-prism-copilot-protected-fallback-review/collect/challenger/postfix2-raw.txt`
- `prism/runs/20260507-prism-copilot-protected-fallback-review/artifacts/resource-limited.json`
- `references/prism-provider-policy.json`
- `compass/tools/redcap-agent-health-probe.py`
- `prism/tools/prism-availability.py`
- `compass/tools/redcap-reviewer-order.py`
- `compass/tools/redcap-multi-session-acceptance.sh`
