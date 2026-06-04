# Bootstrap Layer

Purpose: first-start and pre-task entrypoints.

Belongs here:

- installation and revive plans
- pre-task intake wrappers
- environment checks
- minimal workspace health checks

Does not belong here:

- runtime implementation internals
- host-specific rule forks
- long-running task state

Rule: bootstrap starts RedCap; it must not become the runtime.
