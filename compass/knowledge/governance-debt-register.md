# Governance Debt Register

> **定位**：记录“治理设计已明确，但尚未完全落地”的框架债务。
> 它不是 backlog 全量镜像，而是治理维度的欠账表。

## 状态说明

| 字段 | 含义 |
|---|---|
| `design_status` | `identified` / `design-complete` / `partially-implemented` |
| `implementation_status` | `pending` / `in-progress` / `done` |
| `owner_slice` | 当前优先承接它的 tranche 或模块 |

## 当前治理债务

### GD-001：Closure authority ledger 与 obligation lifecycle
- **design_status**: `design-complete`
- **implementation_status**: `pending`
- **owner_slice**: `Authority / Closure 收口`
- **source**: `compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md` §三 A1
- **gap**: closure transaction ledger、pending closure obligation lifecycle、task report mandatory audit 仍未统一到单一 authority chain

### GD-002：Validator chain hardening
- **design_status**: `design-complete`
- **implementation_status**: `pending`
- **owner_slice**: `Authority Core Hardening`
- **source**: `compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md` §三 A2
- **gap**: PM Gate / drift / report 等 validator 还没有统一 orchestrator 和结构化输出

### GD-003：RedCap-owned continuity manifest
- **design_status**: `design-complete`
- **implementation_status**: `pending`
- **owner_slice**: `会话隔离与连续性`
- **source**: `compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md` §四 B1
- **gap**: continuity authority 仍散在宿主 session 资产与本地 runtime 辅助文件之间

### GD-004：Session resume gate 与 capability matrix
- **design_status**: `design-complete`
- **implementation_status**: `pending`
- **owner_slice**: `会话隔离与连续性`
- **source**: `compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md` §四 B2
- **gap**: 跨宿主隔离模式、resume decision、degraded mode 还没有统一 gate

### GD-005：Specs lifecycle authority
- **design_status**: `design-complete`
- **implementation_status**: `pending`
- **owner_slice**: `文档信息架构与证据分层`
- **source**: `compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md` §六 D1
- **gap**: specs 仍缺 registry、准入门、迁移门与 archive enforcement

### GD-006：Artifact lifecycle enforcement
- **design_status**: `design-complete`
- **implementation_status**: `pending`
- **owner_slice**: `Authority Core Hardening`
- **source**: `compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md` §七 E1
- **gap**: repo-tracked / session-isolated / local-only / temporary 的分类已有规则，但还没有物理门禁

### GD-007：Governance executable norms
- **design_status**: `design-complete`
- **implementation_status**: `pending`
- **owner_slice**: `工程治理 / 权威规范升级`
- **source**: `compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md` §八 F2-F3
- **gap**: specs-to-gates translation、hook audit、lesson injection、contract validator、FSM canonical source 尚未完整落地
