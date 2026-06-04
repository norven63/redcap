# Prism CLI Helper

`runtime/prism/bin/prism` is a local helper for using Prism without turning it into an
automatic governance system.

It does not call Kimi or Claude Code. It prepares copyable briefs, validates the
local examples, and merges provider reviews by preserving the strictest verdict.

## Commands

```bash
runtime/prism/bin/prism check
runtime/prism/bin/prism gate --task "Design a migration" --risk-level high
runtime/prism/bin/prism brief --provider kimi --request runtime/prism/examples/prism-request.example.json
runtime/prism/bin/prism brief --provider claude-code --request runtime/prism/examples/prism-request.example.json
runtime/prism/bin/prism merge kimi-review.json claude-code-review.json
```

## Rules

- The only valid providers are `kimi` and `claude-code`.
- `merge` never averages disagreement away.
- If any review is `block`, the merged verdict is `block`.
- If any review is `concern` and none is `block`, the merged verdict is
  `concern`.
- The main AI must respond to any merged `concern` or `block`.
