# Codex Host Adapter Boundary

Codex still imports root `AGENTS.md` from the managed workspace.

As of 2026-05-09, Codex also documents official lifecycle hooks behind the
`codex_hooks` feature flag. RedCap now carries a repo-local candidate
configuration in `.codex/`, but this directory remains a package-visible adapter
boundary only:

- `AGENTS.md` is still the thin startup import.
- `.codex/hooks.json` is a Codex-specific host wiring candidate.
- RedCap must not claim full host parity until a real trusted Codex session
  proves SessionStart / Stop firing with marker evidence.
- `compass/tools/redcap-codex-live-marker-e2e.sh --run` is the safe local
  marker probe for Codex CLI; a passing CLI probe does not automatically prove
  Codex.app interactive hook readiness.
- Codex PreToolUse / PostToolUse coverage is a guardrail, not a complete
  sandbox or reply-time veto boundary.
