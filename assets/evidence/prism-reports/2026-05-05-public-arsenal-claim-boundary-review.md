# Prism Review: Public Arsenal Claim Boundary

## Scope

P4-2e asks RedCap to keep `redcap-arsenal` honest while it is still template-only: initialized, but not yet populated with public knowledge entries.

## Roster

- Claude Code / Claude family: reviewer
- Copilot / GPT family: security reviewer

Kimi was unavailable because the CLI returned quota 403. Gemini timed out. Codex CLI remained last-resort and was not used because non-Codex providers were available.

## Verdict

The boundary-only tranche is appropriate. It should not migrate historical knowledge just to make the public arsenal look populated.

Copilot found three enforcement gaps before closeout:

- Populated-claim future gates were only checked for list presence.
- Substantive-entry counting included non-user support files.
- Overlay advisory-only authority did not explicitly protect task truth surfaces.

All three findings were fixed before this report was written.

## Resulting Boundary

Current public claim:

- `redcap-arsenal` is initialized as a template, schema and user-namespace surface.
- RedCap Forge defines the future promotion path.

Forbidden claim:

- The public arsenal contains migrated historical knowledge.
- The public arsenal is already a populated shared knowledge base or skill arsenal.
- P4-2e completion means RedCap is public-release-ready.

## Evidence

- `prism/runs/20260505-public-arsenal-claim-boundary-review/collect/reviewer/parsed.json`
- `prism/runs/20260505-public-arsenal-claim-boundary-review/collect/security-reviewer/parsed.json`
- `prism/runs/20260505-public-arsenal-claim-boundary-review/synthesize/summary.md`
- `references/public-arsenal-claim-boundary-policy.json`
- `compass/tools/redcap-public-arsenal-claim-boundary.py`
- `compass/tools/redcap-overlay-governance-check.sh`
