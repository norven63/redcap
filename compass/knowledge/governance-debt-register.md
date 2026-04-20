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
- **implementation_status**: `done`
- **owner_slice**: `会话隔离与连续性`
- **source**: `compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md` §四 B2
- **gap**: `redcap-session-resume-gate.sh` 已接入 `redcap-layerB-session-start.sh`，并以 `references/host-session-capability-matrix.json` 统一发布 `full / degraded / unsupported`

### GD-005：Specs lifecycle authority
- **design_status**: `design-complete`
- **implementation_status**: `done`
- **owner_slice**: `文档信息架构与证据分层`
- **source**: `compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md` §六 D1
- **gap**: 已收口：`references/spec-lifecycle-policy.json` + `references/spec-contribution-standard.md` + `redcap-spec-check.sh` 已把 spec 的命名、角色、状态、归档根目录与 `replaced_by` 关系补成可执行门；`superseded` spec 不再允许留在 active specs 根目录里

### GD-006：Artifact lifecycle enforcement
- **design_status**: `design-complete`
- **implementation_status**: `done`
- **owner_slice**: `Authority Core Hardening`
- **source**: `compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md` §七 E1
- **gap**: 已收口：`redcap-artifact-classifier.sh` 负责统一分类，`.githooks/pre-commit` + `redcap-ensure-git-hooks.sh` 负责 repo-owned 的提交前阻断与 mixed-lifecycle 提示，`stop-review / on-complete / session-end` 继续保留 commit-range 审计作为收尾兜底

### GD-007：Governance executable norms
- **design_status**: `design-complete`
- **implementation_status**: `done`
- **owner_slice**: `工程治理 / 权威规范升级`
- **source**: `compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md` §八 F2-F3
- **gap**: 已收口：`spec-registry + spec-lifecycle-policy + spec-check` 承接 spec 维度；`docs catalog + knowledge index + execution guarantees + revival check` 承接 docs/knowledge/复活执行纪律；`acceptance index + token-risk audit` 承接巨型脚本、入口自动导入与 ignored 运行残留；`review-tracks + hook-contract + runtime-helper + cli-console-mirror` checks 承接三轨评审、hook 契约、runtime helper 收敛与宿主展示镜像边界。`cli_console.md` 的 repo-owned 边界已完成；宿主最终回复 UI 不由仓库脚本强控，不再作为本债务残留。

### GD-008：主 Agent 实时行为约束仍属 host-limited
- **design_status**: `identified`
- **implementation_status**: `in-progress`
- **owner_slice**: `宿主能力画像 / 行为保障诚实建模`
- **source**: `references/execution-guarantees.json`（host-behavior 类别）+ `references/host-session-capability-matrix.json`
- **gap**: 入口恢复、docs/knowledge 渐进披露、validator 与 diagnose 已有较强机械保障，但“主 Agent 不应无必要中断用户 / 不应把 commit 犹豫升级成人工确认”这类回复时行为，目前在 Codex.app 等宿主上仍缺少 repo-owned pre-reply veto。现阶段已把该边界登记为 host-limited / manual-only，并把 Codex 宿主正式纳入 capability matrix；同时通过 `references/execution-guarantee-tiers.md` 明确它属于“人工/宿主边界保障”而非物理强保障。真正的 100% 物理约束仍依赖未来宿主暴露更强 Hook 或 veto 接口。
