# Prism Review: Prism Runs Lifecycle Status Surface Hardening

## Scope

This run reviewed `P2-8 Prism runs 生命周期状态面与清理边界加固`.

The review focused on whether RedCap's status surface now clearly distinguishes safe inspection of `prism/runs` evidence from destructive physical cleanup.

## Roster

- Claude Code / Claude family: reviewer
- Kimi / Kimi family: challenger

Copilot was not used because it remains a protected fallback while Claude Code and Kimi are available. Codex CLI remained last-resort and was not used.

## Verdict

Pass.

Both reviewers found no blockers. They agreed the patch makes the lifecycle path executable, keeps `inventory` and `prune-local` in the inspection/dry-run lane, and makes `prune-local --apply` explicitly require user approval.

## Accepted Result

- `current-status` now prints the correct `bash prism/tools/prism-runs-lifecycle.sh ...` commands.
- `inventory` is labeled read-only and `prune-local` is labeled dry-run.
- The status surface explicitly forbids `prune-local --apply` without explicit approval.
- The token-risk governance policy now carries the same boundary.
- No `prism/runs` evidence was physically deleted.

## Evidence

- `prism/runs/20260508-prism-runs-lifecycle-status-surface-hardening/collect/reviewer/raw.txt`
- `prism/runs/20260508-prism-runs-lifecycle-status-surface-hardening/collect/reviewer/parsed.json`
- `prism/runs/20260508-prism-runs-lifecycle-status-surface-hardening/collect/challenger/raw.txt`
- `prism/runs/20260508-prism-runs-lifecycle-status-surface-hardening/collect/challenger/parsed.json`
- `prism/runs/20260508-prism-runs-lifecycle-status-surface-hardening/artifacts/acceptance-binding.json`
- `compass/tools/redcap-current-status.py`
- `references/token-structural-governance.json`
