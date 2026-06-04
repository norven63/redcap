# RedCap Workspace Instructions

Before starting any RedCap development task, run the deterministic Prism gate:

```bash
runtime/bin/redcap gate --task "<task summary>" --risk-level medium
```

If the gate returns `required`, do not implement or claim completion until full
Prism has reviewed the task, or until Norven explicitly overrides the gate.

This instruction is a workspace convention. It does not claim host-level
automatic interception.

Read order for this clean workspace:

1. `README.md`
2. `assets/docs/redcap-revival-doctrine.md`
3. `assets/docs/redcap-revival-map.md`
4. `assets/contracts/gate-protocol.md`

Do not bulk-read the old RedCap repository. Use `assets/archaeology/` source
maps and exact paths only.
