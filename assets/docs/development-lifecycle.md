# Development Lifecycle

The development lifecycle gate is not a second task state machine. It validates
requirements and technical review evidence against the existing FSM transition
model.

Completion claims require implementation and verification evidence. Documents,
ledgers, reports, and governance records cannot satisfy completion alone.

Commands:

```bash
runtime/bin/redcap lifecycle check --packet path/to/lifecycle.json
runtime/bin/redcap lifecycle self-check
```
