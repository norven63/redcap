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
- `PostToolUse`: writes same-turn supported tool-use fingerprints so `Stop` can
  distinguish action-backed work from explanation-only closure.
- `Stop`: writes a live-marker record and runs `runtime/bin/redcap check` before
  a turn closes cleanly. If the matching prompt was RedCap-required and no
  `PostToolUse` action evidence exists for the same turn, `Stop` asks Codex to
  continue instead of closing with explanation/status only.

Not currently claimed:

- Events not exposed as verified project hooks in this workspace:
  `PermissionRequest`, `PreCompact`, and `PostCompact`.
- Complete cross-host hook parity. Kimi and Claude Code provider calls are
  controlled through the Prism dispatcher instead of through provider-native
  lifecycle hooks.
