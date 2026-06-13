# Codex Host Adapter

Purpose: project-local Codex lifecycle hooks for the revived RedCap workspace.

This adapter is a host bridge. RedCap rules stay in `runtime/` and
`assets/contracts/`; Codex hook files only forward host events into RedCap-owned
commands.

Current deployed surface:

- `SessionStart`: writes a live-marker record and injects a short RedCap context
  reminder.
- `UserPromptSubmit`: writes a live-marker record, runs the deterministic
  RedCap/Prism prompt gate, and injects the resulting gate context without
  storing the raw prompt.
- `PreToolUse`: writes a live-marker record, blocks known destructive commands
  before execution, and claims session ownership for mutating supported tool
  calls when Codex supplies a real session id.
- `PostToolUse`: writes same-turn supported tool-use fingerprints so explicit
  closeout commands can distinguish action-backed work from explanation-only
  closure.
- `Stop`: runs an advisory closeout review. It can block a flawed closeout, but
  its payload is constrained to original-task-anchored correction requirements,
  Cap arbitration, bounded correction rounds, and structured health markers.
  Full Prism provider review is not run in this hot path. If Cap has concrete
  evidence that a Stop finding is a false positive, it can create a bounded
  override marker with `runtime/bin/redcap advisory-stop override`; the next
  matching Stop event records the reason and continues. Full `runtime/bin/redcap
  check` remains an explicit verification command, not the default Stop hot
  path.

Not currently claimed:

- Events not exposed as verified project hooks in this workspace:
  `PermissionRequest`, `PreCompact`, and `PostCompact`.
- Complete cross-host hook parity. Kimi and Claude Code provider calls are
  controlled through the Prism dispatcher instead of through provider-native
  lifecycle hooks.
