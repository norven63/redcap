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
- **implementation_status**: `done`
- **owner_slice**: `Authority / Closure 收口`
- **source**: `compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md` §三 A1
- **gap**: 已收口：`redcap-interop-governance.sh` 已统一承接 pending closure / closure-ledger；`session-end` 负责 authority rewrite 与 fail-closed persistence；`session-start` 现通过独立 `redcap-pending-closure-reconcile.sh` 以 advisory 方式自动核销/收缩可证明 blocker，并在 `task_id + confirmed_hash` mismatch 时拒绝静默清账

### GD-002：Validator chain hardening
- **design_status**: `design-complete`
- **implementation_status**: `done`
- **owner_slice**: `Authority Core Hardening`
- **source**: `compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md` §三 A2
- **gap**: 已收口：`redcap-validator-chain.sh` 现已覆盖 session-start / stop-review / on-complete / session-end，并把 session-end 的 review proof / reanchor / PM Gate / drift / task report / artifact lifecycle 收进统一编排链

### GD-003：RedCap-owned continuity manifest
- **design_status**: `design-complete`
- **implementation_status**: `done`
- **owner_slice**: `会话隔离与连续性`
- **source**: `compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md` §四 B1
- **gap**: continuity authority 已收口到 `compass/.runtime/sessions/<runtime_session_id>/manifest.yaml`；宿主 Session Mirror 改为只读镜像

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
- **implementation_status**: `in-progress`
- **owner_slice**: `Authority Core Hardening`
- **source**: `compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md` §七 E1
- **gap**: 已完成 stop-review / on-complete 阶段的 commit-range 检测与收尾阻断，但 source design 中的 artifact classifier、pre-commit lifecycle enforcement、mixed-lifecycle commit blocking 仍未落地，因此当前只能记为第一阶段 in-progress

### GD-007：Governance executable norms
- **design_status**: `design-complete`
- **implementation_status**: `pending`
- **owner_slice**: `工程治理 / 权威规范升级`
- **source**: `compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md` §八 F2-F3
- **gap**: specs-to-gates translation、hook audit、lesson injection、contract validator、FSM canonical source 尚未完整落地
