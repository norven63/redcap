# Host Adapters Layer

Purpose: thin bridges from Codex, Claude Code, Kimi, or other approved hosts
into RedCap-owned commands.

Belongs here:

- host hook shims
- host capability probes
- adapter manifests
- live-marker verification assets

Does not belong here:

- RedCap business rules
- completion semantics
- duplicated Prism policy
- runtime state

Rule: host adapters forward into RedCap; they do not become RedCap authority.

Current adapters:

- `codex/`: project-local Codex `SessionStart`, `UserPromptSubmit`,
  `PreToolUse`, `PostToolUse`, and advisory `Stop` hooks. These hooks record live markers, run
  the deterministic prompt gate, block known destructive commands, and collect
  action evidence. `Stop` performs closeout review through original-task-anchored
  correction constraints so hook feedback does not become a new reply topic.
- `host-hook-audit.py`: verifies the deployed Codex hook surface and the
  provider-call interception boundary. Provider calls are intercepted at the
  RedCap Prism dispatcher layer for Kimi and Claude Code.

The current audit deliberately records unsupported host events such as
`PermissionRequest`, `PreCompact`, and `PostCompact` instead of pretending they
are covered by this workspace.
