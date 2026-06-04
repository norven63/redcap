# Runtime Boundary Kernel

The runtime boundary kernel resolves the three physical roots RedCap must keep
separate:

- RedCap runtime root
- Managed project workspace
- User-private state root

It inherits the old RedCap workspace-boundary guarantees through the bounded
extraction at `assets/archaeology/extractions/runtime-workspace-boundary-v1.json`.
The kernel allows self-development only when the caller is inside the RedCap
runtime root. External project state must not default into the RedCap runtime
repository or into the managed project workspace.

Commands:

```bash
runtime/bin/redcap boundary resolve
runtime/bin/redcap boundary check
runtime/bin/redcap boundary self-check
```
