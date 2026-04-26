# RedCap File Lookup Dictionary

> 目的：给人类和 Agent 一个“先看这里”的文件地图。具体文件只保留短注解和反链，长解释集中在本字典，避免每个脚本头部都膨胀成 token 污染源。

## How To Read

- 先按“你想理解的对象”找到条目，再跳到对应文件。
- 机器可读文件优先看 `meaning` / `owner` / `check` 三列，不要默认打开全文历史报告。
- 文件头里的 `Dictionary:` 注解只负责反链，不复制本字典的大段解释。

## Control Plane Assurance

| 文件 | 定位 | 含义 | owner | check |
|---|---|---|---|---|
| [`references/evolution-grade-baseline.json`](../references/evolution-grade-baseline.json) | control-plane assurance registry 兼容路径 | 用统一维度审计 RedCap 各保障节点是否达到、降级或受宿主限制；文件名保留 `evolution-grade` 是兼容历史，语义上不是只服务自升级 | Compass governance | `bash compass/tools/redcap-evolution-grade-check.sh` |
| [`compass/tools/redcap-evolution-grade-check.sh`](../compass/tools/redcap-evolution-grade-check.sh) | assurance registry shell entry | 轻量入口；默认校验上面的 registry | Compass validator | `bash compass/tools/redcap-evolution-grade-check.sh` |
| [`compass/tools/redcap-evolution-grade-check.py`](../compass/tools/redcap-evolution-grade-check.py) | assurance registry validator | 校验节点、路径、降级理由、remediation 是否完整 | Compass validator | 由 `.sh` 包装调用 |

## Runtime And Closeout

| 文件 | 定位 | 含义 | owner | check |
|---|---|---|---|---|
| [`closeout-cap.sh`](../closeout-cap.sh) | root closeout facade | 人类/Agent 记一个短入口；内部转调 Layer B closeout runtime | Layer B runtime | `./closeout-cap.sh status` |
| [`compass/tools/redcap-layerb-closeout-runtime.py`](../compass/tools/redcap-layerb-closeout-runtime.py) | unified closeout runtime | 串起承诺账本、Prism acceptance、on-complete、session-end、receipt 和 rescue audit | Layer B runtime | `bash compass/tools/redcap-layerb-closeout-runtime-check.sh` |
| [`compass/tools/redcap-intent-coverage-check.sh`](../compass/tools/redcap-intent-coverage-check.sh) | original intent coverage gate | PM Gate 的原始意图覆盖审计，防止把用户战略目标降级成只完成路线图的小账本 | Layer B PM Gate | `bash compass/tools/redcap-intent-coverage-check.sh .dev-task.md` |
| [`compass/tools/redcap-on-complete.sh`](../compass/tools/redcap-on-complete.sh) | on-complete gate | closeout 前置校验、摘要和主成功通知 owner；被 closeout runtime 编排 | Layer B runtime | acceptance cases with `on-complete-*` |
| [`compass/tools/redcap-layerB-session-end.sh`](../compass/tools/redcap-layerB-session-end.sh) | session-end reconcile gate | 会话结束兜底审计、pending closure 清账、blocker 告警；在 closeout runtime 中不再重复发送成功通知 | Layer B runtime | acceptance cases with `session-end-*` |

## Prism And Providers

| 文件 | 定位 | 含义 | owner | check |
|---|---|---|---|---|
| [`references/prism-provider-policy.json`](../references/prism-provider-policy.json) | provider policy | 记录 provider 选择、冻结窗口和 evidence 口径；当前包含 Copilot CLI 临时冻结 | Prism governance | `bash compass/tools/redcap-agent-health-probe.sh --stdout --live ...` |
| [`compass/tools/redcap-provider-policy.sh`](../compass/tools/redcap-provider-policy.sh) | provider freeze gate | RedCap-owned CLI launcher 的冻结期硬门，调用前判断 provider 是否可启动 | Prism governance | `bash compass/tools/redcap-provider-policy.sh assert-not-frozen <agent> <scope>` |
| [`compass/tools/redcap-agent-health-probe.py`](../compass/tools/redcap-agent-health-probe.py) | live health probe | 区分“已安装”与“真实 headless 可用”；遇到冻结 provider 时返回 `frozen` 且不执行 CLI | Prism governance | `bash compass/tools/redcap-agent-health-probe.sh --stdout` |
| [`compass/tools/redcap-detect-agents.sh`](../compass/tools/redcap-detect-agents.sh) | registry refresh | 轻量刷新本地 CLI 可见性；冻结 provider 只记录 frozen，不调用其 version/probe | Prism governance | `bash compass/tools/redcap-detect-agents.sh /tmp/registry.yaml --agent <agent>` |
| [`compass/tools/baton-launcher.sh`](../compass/tools/baton-launcher.sh) | direct CLI launcher | Loom / baton 的通用 Agent 启动器；启动前必须通过 provider freeze gate | Loom + Prism governance | baton acceptance / provider policy check |
| [`compass/tools/redcap-reviewer-order.py`](../compass/tools/redcap-reviewer-order.py) | reviewer router | 按模型能力画像、本地稳定性、冻结策略生成 stop-review fallback 顺序 | Prism governance | stop-review acceptance |
| [`prism/protocol.md`](../prism/protocol.md) | Prism protocol | 定义独立取样、council、evidence、provider 选择与 `prism/runs` 生命周期 | Prism | `bash prism/tools/prism-evidence-check.sh` |

## Skill And Host Distribution

| 文件 | 定位 | 含义 | owner | check |
|---|---|---|---|---|
| [`references/skill-lifecycle-policy.json`](../references/skill-lifecycle-policy.json) | skill lifecycle source | 定义 RedCap-native capability、host-exported skill、portable package 的状态、门禁、回滚和弃用规则 | Host adapters | `bash compass/tools/redcap-skill-lifecycle-check.sh` |
| [`compass/tools/redcap-skill-lifecycle-check.py`](../compass/tools/redcap-skill-lifecycle-check.py) | skill lifecycle validator | 防止宿主入口复制分叉规则，并校验 lifecycle fields | Host adapters | 由 `.sh` 包装调用 |
| [`AGENTS.md`](../AGENTS.md) / [`CLAUDE.md`](../CLAUDE.md) / [`GEMINI.md`](../GEMINI.md) / [`.github/copilot-instructions.md`](../.github/copilot-instructions.md) | host thin entries | 宿主入口只做轻量索引和复活，不承载权威规则正文 | Host adapters | revival / skill lifecycle checks |

## Product Shape And Retrieval

| 文件 | 定位 | 含义 | owner | check |
|---|---|---|---|---|
| [`references/redcap-system-layers.md`](../references/redcap-system-layers.md) | productization roadmap | 把 RedCap 从 skill repo 演进为 Agent Runtime / CLI / 多层系统的边界和迁移路线讲清楚；不是已完成迁移声明 | Architecture | task report + Prism review |
| [`references/redcap-parent-task-ledger.md`](../references/redcap-parent-task-ledger.md) | parent task ledger | R0-R22 与后续中插任务的父任务视图，区分已完成子任务、延期项、待执行迁移和阻塞项 | PM Gate + Architecture | task report + PM Gate |
| [`references/redcap-r0-r22-registry.json`](../references/redcap-r0-r22-registry.json) | parent task registry | R0-R22 机器可读登记表，标明恢复来源、置信度、完成状态和延期边界 | PM Gate + Architecture | `bash compass/tools/redcap-r0-r22-registry-check.sh` |
| [`references/execution-layer-split-dry-run.json`](../references/execution-layer-split-dry-run.json) | execution-layer split dry-run | 物理拆分前的可审计迁移蓝图；只说明哪些路径可 copy/link、哪些必须阻塞或延期，不执行真实搬迁 | Architecture + PM Gate | `bash compass/tools/redcap-execution-layer-split-check.sh` |
| [`references/legacy-asset-migration-dry-run.json`](../references/legacy-asset-migration-dry-run.json) | legacy asset migration dry-run | 历史资产迁移前的分类账；说明 reports/research/specs/knowledge/prism runs 应保留、复制、归档还是等待后续 apply | Architecture + Legacy governance | `bash compass/tools/redcap-legacy-asset-migration-check.sh` |
| [`references/parent-receipt-aggregation-policy.json`](../references/parent-receipt-aggregation-policy.json) | parent receipt aggregation | 父任务完成证明策略；只有子任务 receipt 与未完成边界全部登记后，才允许讨论父任务完成 | PM Gate + Closeout governance | `bash compass/tools/redcap-parent-receipt-aggregation-check.sh` |
| [`README.md`](../README.md) | public landing page | 面向人类的一眼看懂入口，只讲核心优势和导航，不承载细则 | Product narrative | human-output review |
| [`compass/docs/catalog.json`](../compass/docs/catalog.json) | docs catalog | docs 首读索引，防止任务一开始 bulk-read 历史报告 | Docs governance | `bash compass/tools/redcap-docs-catalog.sh summary` |
| [`compass/knowledge/index.md`](../compass/knowledge/index.md) | knowledge index | lessons/knowledge 首读索引，防止默认打开知识库全文 | Knowledge governance | `bash compass/tools/redcap-knowledge-index-check.sh` |

## Package Publish Safety

| 文件 | 定位 | 含义 | owner | check |
|---|---|---|---|---|
| [`references/package-publish-safety-policy.json`](../references/package-publish-safety-policy.json) | package safety policy | 未来 npm / 独立 runtime 发布前的包面安全策略：默认候选、禁止路径、密钥模式和人工边界 | Release safety | `bash compass/tools/redcap-package-publish-safety-check.sh` |
| [`compass/tools/redcap-package-publish-safety-check.sh`](../compass/tools/redcap-package-publish-safety-check.sh) | package safety shell entry | 发布/打包前安全审计入口，可检查默认候选包或显式候选文件清单 | Release safety | `bash compass/tools/redcap-package-publish-safety-check.sh` |
| [`compass/tools/redcap-package-publish-safety-check.py`](../compass/tools/redcap-package-publish-safety-check.py) | package safety validator | fail-closed 检查候选文件是否包含 `.env`、宿主私密入口、runtime evidence 或 credential-like 内容 | Release safety | `bash compass/tools/redcap-package-publish-safety-check.sh --candidate-list <files>` |

## Machine-Covered Critical Paths

> 这不是鼓励默认全读的清单，而是 `references/file-lookup-dictionary-policy.json` 的人类可读镜像：凡是这里登记的关键文件，都必须能通过 `bash compass/tools/redcap-file-lookup-dictionary-check.sh` 被机器检查到。新增关键 runtime / Prism / knowledge / host-adapter 文件时，要同步补 policy 与本字典。

| 文件 | 定位 | 含义 | owner | check |
|---|---|---|---|---|
| [`ARCHITECTURE.md`](../ARCHITECTURE.md) | Product Shape And Retrieval | deep architecture map for RedCap layers and truth surfaces | Architecture | `bash compass/tools/redcap-mechanism-vitality-check.sh` |
| [`references/runtime-memory-architecture.md`](../references/runtime-memory-architecture.md) | Runtime And Closeout | Layer B memory, FSM, ledger, closeout and tracking architecture | Layer B runtime | `bash compass/tools/redcap-layerb-fsm-check.sh` |
| [`references/layerb-change-intake-policy.json`](../references/layerb-change-intake-policy.json) | Runtime And Closeout | policy for mid-task inserted requirements, replan review, and parent/child completion boundaries | Layer B FSM | `bash compass/tools/redcap-change-intake-check.sh .dev-task.md` |
| [`references/redcap-parent-task-ledger.md`](../references/redcap-parent-task-ledger.md) | Product Shape And Retrieval | parent task ledger for R0-R22 and follow-up migration batches | PM Gate + Architecture | `task report + PM Gate` |
| [`references/redcap-r0-r22-registry.json`](../references/redcap-r0-r22-registry.json) | Product Shape And Retrieval | machine-readable R0-R22 parent-task registry with recovery confidence and deferred boundaries | PM Gate + Architecture | `bash compass/tools/redcap-r0-r22-registry-check.sh` |
| [`references/execution-layer-split-dry-run.json`](../references/execution-layer-split-dry-run.json) | Product Shape And Retrieval | dry-run manifest for moving RedCap toward an independent execution layer without applying physical migration yet | Architecture + PM Gate | `bash compass/tools/redcap-execution-layer-split-check.sh` |
| [`references/legacy-asset-migration-dry-run.json`](../references/legacy-asset-migration-dry-run.json) | Product Shape And Retrieval | dry-run manifest for classifying docs, reports, knowledge and runtime evidence before historical asset migration | Architecture + Legacy governance | `bash compass/tools/redcap-legacy-asset-migration-check.sh` |
| [`references/parent-receipt-aggregation-policy.json`](../references/parent-receipt-aggregation-policy.json) | Product Shape And Retrieval | policy for aggregating child receipts and not-complete boundaries before parent task completion can be claimed | PM Gate + Closeout governance | `bash compass/tools/redcap-parent-receipt-aggregation-check.sh` |
| [`references/task-report-template.md`](../references/task-report-template.md) | Runtime And Closeout | task report completion and evidence template | Layer B closure | `bash compass/tools/redcap-task-report-check.sh` |
| [`references/file-lookup-dictionary.md`](../references/file-lookup-dictionary.md) | Product Shape And Retrieval | human-readable file map and term locator | Compass governance | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` |
| [`references/file-lookup-dictionary-policy.json`](../references/file-lookup-dictionary-policy.json) | Product Shape And Retrieval | machine-readable coverage list for the lookup dictionary | Compass governance | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` |
| [`compass/tools/redcap-file-lookup-dictionary-check.sh`](../compass/tools/redcap-file-lookup-dictionary-check.sh) | Product Shape And Retrieval | shell entry for dictionary coverage validation | Compass validator | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` |
| [`compass/tools/redcap-file-lookup-dictionary-check.py`](../compass/tools/redcap-file-lookup-dictionary-check.py) | Product Shape And Retrieval | dictionary coverage validator and missing-entry planner | Compass validator | `bash compass/tools/redcap-file-lookup-dictionary-check.sh --plan` |
| [`bin/redcap`](../bin/redcap) | Product Shape And Retrieval | thin CLI facade for revive, status, diagnose, closeout, Prism availability, dictionary and shared knowledge commands | Runtime facade | `bin/redcap help` |
| [`references/package-publish-safety-policy.json`](../references/package-publish-safety-policy.json) | Package Publish Safety | fail-closed policy for future npm/runtime package candidate audits | Release safety | `bash compass/tools/redcap-package-publish-safety-check.sh` |
| [`compass/tools/redcap-package-publish-safety-check.sh`](../compass/tools/redcap-package-publish-safety-check.sh) | Package Publish Safety | shell entry for package publish safety audit | Release safety | `bash compass/tools/redcap-package-publish-safety-check.sh` |
| [`compass/tools/redcap-package-publish-safety-check.py`](../compass/tools/redcap-package-publish-safety-check.py) | Package Publish Safety | package candidate path and secret-pattern validator | Release safety | `bash compass/tools/redcap-package-publish-safety-check.sh` |
| [`revive-cap.sh`](../revive-cap.sh) | Runtime And Closeout | root one-shot revival/install facade | Runtime facade | `./revive-cap.sh` |
| [`compass/tools/redcap-install.sh`](../compass/tools/redcap-install.sh) | Runtime And Closeout | revival/install chain for identity, workflow import and readiness checks | Runtime facade | `bash compass/tools/redcap-install.sh --check-only` |
| [`compass/tools/redcap-current-status.sh`](../compass/tools/redcap-current-status.sh) | Runtime And Closeout | human-readable current task/status surface | Layer B status | `bash compass/tools/redcap-current-status.sh` |
| [`compass/tools/redcap-tracking-health.sh`](../compass/tools/redcap-tracking-health.sh) | Runtime And Closeout | tracking health surface for task cards, reports and explore notes | Layer B tracking | `bash compass/tools/redcap-tracking-health.sh .dev-task.md` |
| [`compass/tools/redcap-diagnose.sh`](../compass/tools/redcap-diagnose.sh) | Runtime And Closeout | single diagnostic entry that runs governance checks | Diagnostics | `bash compass/tools/redcap-diagnose.sh` |
| [`compass/tools/redcap-spec-check.sh`](../compass/tools/redcap-spec-check.sh) | Runtime And Closeout | umbrella repository validator consumed by regression gates | Diagnostics | `bash compass/tools/redcap-spec-check.sh "$PWD"` |
| [`compass/tools/redcap-multi-session-acceptance.sh`](../compass/tools/redcap-multi-session-acceptance.sh) | Runtime And Closeout | multi-session acceptance regression suite | QA | `bash compass/tools/redcap-multi-session-acceptance.sh <case|all>` |
| [`compass/tools/redcap-layerb-closeout-runtime.sh`](../compass/tools/redcap-layerb-closeout-runtime.sh) | Runtime And Closeout | shell wrapper for unified closeout runtime | Layer B runtime | `bash compass/tools/redcap-layerb-closeout-runtime-check.sh` |
| [`compass/tools/redcap-layerb-fsm.sh`](../compass/tools/redcap-layerb-fsm.sh) | Runtime And Closeout | Layer B FSM shell entry | Layer B FSM | `bash compass/tools/redcap-layerb-fsm-check.sh` |
| [`compass/tools/redcap-layerb-fsm.py`](../compass/tools/redcap-layerb-fsm.py) | Runtime And Closeout | Layer B FSM contract data and rendering logic | Layer B FSM | `bash compass/tools/redcap-layerb-fsm-check.sh` |
| [`compass/tools/redcap-layerb-fsm-check.sh`](../compass/tools/redcap-layerb-fsm-check.sh) | Runtime And Closeout | Layer B FSM contract validator | Layer B FSM | `bash compass/tools/redcap-layerb-fsm-check.sh` |
| [`compass/tools/redcap-change-intake-check.sh`](../compass/tools/redcap-change-intake-check.sh) | Runtime And Closeout | shell entry for mid-task inserted requirement and replan gate validation | Layer B FSM | `bash compass/tools/redcap-change-intake-check.sh .dev-task.md` |
| [`compass/tools/redcap-change-intake-check.py`](../compass/tools/redcap-change-intake-check.py) | Runtime And Closeout | validates the U<n> change ledger, replan updates, unresolved inserted requirements, and parent completion claims | Layer B FSM | `bash compass/tools/redcap-change-intake-check.sh .dev-task.md` |
| [`compass/tools/redcap-layerB-session-start.sh`](../compass/tools/redcap-layerB-session-start.sh) | Runtime And Closeout | Layer B session-start revival and state initialization hook | Host hooks | `acceptance sessionstart-* cases` |
| [`compass/tools/redcap-layerB-task-complete-guard.sh`](../compass/tools/redcap-layerB-task-complete-guard.sh) | Runtime And Closeout | task completion guard that routes terminal state into closeout runtime | Layer B runtime | `acceptance task-complete-guard-* cases` |
| [`compass/tools/redcap-prism-acceptance-check.sh`](../compass/tools/redcap-prism-acceptance-check.sh) | Runtime And Closeout | closeout gate for required Prism acceptance evidence | Layer B runtime | `bash compass/tools/redcap-prism-acceptance-check.sh` |
| [`compass/tools/redcap-prism-acceptance-bind.sh`](../compass/tools/redcap-prism-acceptance-bind.sh) | Runtime And Closeout | binds Prism acceptance evidence to a task/report before closeout | Layer B runtime | `acceptance prism-acceptance-binding-required` |
| [`references/execution-guarantees.json`](../references/execution-guarantees.json) | Control Plane Assurance | registry of rules that must have revival, hook, validator or manual-only safeguards | Compass governance | `bash compass/tools/redcap-execution-guarantee-check.sh` |
| [`compass/tools/redcap-execution-guarantee-check.sh`](../compass/tools/redcap-execution-guarantee-check.sh) | Control Plane Assurance | execution guarantee registry shell entry | Compass validator | `bash compass/tools/redcap-execution-guarantee-check.sh` |
| [`compass/tools/redcap-execution-guarantee-check.py`](../compass/tools/redcap-execution-guarantee-check.py) | Control Plane Assurance | execution guarantee registry validator | Compass validator | `bash compass/tools/redcap-execution-guarantee-check.sh` |
| [`compass/tools/redcap-pm-gate-check.sh`](../compass/tools/redcap-pm-gate-check.sh) | Control Plane Assurance | PM Gate task-card validation and scope anchoring | PM Gate | `bash compass/tools/redcap-pm-gate-check.sh strict codex .dev-task.md` |
| [`compass/tools/redcap-mechanism-vitality-check.sh`](../compass/tools/redcap-mechanism-vitality-check.sh) | Control Plane Assurance | visible mechanism vitality shell entry | Compass validator | `bash compass/tools/redcap-mechanism-vitality-check.sh` |
| [`compass/tools/redcap-mechanism-vitality-check.py`](../compass/tools/redcap-mechanism-vitality-check.py) | Control Plane Assurance | checks that key mechanisms are surfaced to humans | Compass validator | `bash compass/tools/redcap-mechanism-vitality-check.sh` |
| [`compass/tools/redcap-r0-r22-registry-check.sh`](../compass/tools/redcap-r0-r22-registry-check.sh) | Control Plane Assurance | R0-R22 registry validation shell entry | Compass validator | `bash compass/tools/redcap-r0-r22-registry-check.sh` |
| [`compass/tools/redcap-r0-r22-registry-check.py`](../compass/tools/redcap-r0-r22-registry-check.py) | Control Plane Assurance | validates R0-R22 registry coverage, provenance and evidence paths | Compass validator | `bash compass/tools/redcap-r0-r22-registry-check.sh` |
| [`compass/tools/redcap-execution-layer-split-check.sh`](../compass/tools/redcap-execution-layer-split-check.sh) | Control Plane Assurance | execution-layer split dry-run validation shell entry | Compass validator | `bash compass/tools/redcap-execution-layer-split-check.sh` |
| [`compass/tools/redcap-execution-layer-split-check.py`](../compass/tools/redcap-execution-layer-split-check.py) | Control Plane Assurance | validates dry-run migration manifest safety, impact coverage, blocker status and rollback plans | Compass validator | `bash compass/tools/redcap-execution-layer-split-check.sh` |
| [`compass/tools/redcap-legacy-asset-migration-check.sh`](../compass/tools/redcap-legacy-asset-migration-check.sh) | Control Plane Assurance | legacy asset migration dry-run validation shell entry | Compass validator | `bash compass/tools/redcap-legacy-asset-migration-check.sh` |
| [`compass/tools/redcap-legacy-asset-migration-check.py`](../compass/tools/redcap-legacy-asset-migration-check.py) | Control Plane Assurance | validates historical asset migration classification, counts, catalog/link plans, retention boundaries and rollback | Compass validator | `bash compass/tools/redcap-legacy-asset-migration-check.sh` |
| [`compass/tools/redcap-parent-receipt-aggregation-check.sh`](../compass/tools/redcap-parent-receipt-aggregation-check.sh) | Control Plane Assurance | parent receipt aggregation validation shell entry | Compass validator | `bash compass/tools/redcap-parent-receipt-aggregation-check.sh` |
| [`compass/tools/redcap-parent-receipt-aggregation-check.py`](../compass/tools/redcap-parent-receipt-aggregation-check.py) | Control Plane Assurance | validates child receipt evidence entries and keeps parent completion ineligible while open boundaries remain | Compass validator | `bash compass/tools/redcap-parent-receipt-aggregation-check.sh` |
| [`prism/README.md`](../prism/README.md) | Prism And Providers | Prism Team overview and routing guidance | Prism | `human review + prism evidence check` |
| [`prism/tools/prism-availability.sh`](../prism/tools/prism-availability.sh) | Prism And Providers | provenance-aware 1-hour availability cache shell entry for Prism rosters | Prism governance | `bash prism/tools/prism-availability.sh status` |
| [`prism/tools/prism-availability.py`](../prism/tools/prism-availability.py) | Prism And Providers | Prism roster availability cache, provenance, filter and check logic | Prism governance | `bash prism/tools/prism-availability.sh check-roster --agents <provider&model:role>` |
| [`prism/tools/prism-dispatch-check.sh`](../prism/tools/prism-dispatch-check.sh) | Prism And Providers | Prism pre-dispatch hard gate including availability, freeze, roles and diversity | Prism governance | `bash prism/tools/prism-dispatch-check.sh --mode test --agents ...` |
| [`prism/tools/prism-coordinator.sh`](../prism/tools/prism-coordinator.sh) | Prism And Providers | run-scoped Prism registry and evidence coordinator | Prism | `acceptance prism-concurrency` |
| [`prism/tools/prism-runs-lifecycle.sh`](../prism/tools/prism-runs-lifecycle.sh) | Prism And Providers | prism/runs retention and residue lifecycle shell entry | Prism | `bash prism/tools/prism-runs-lifecycle.sh check` |
| [`prism/tools/prism-runs-lifecycle.py`](../prism/tools/prism-runs-lifecycle.py) | Prism And Providers | prism/runs residue lifecycle classifier | Prism | `bash prism/tools/prism-runs-lifecycle.sh check` |
| [`references/review-tracks.json`](../references/review-tracks.json) | Prism And Providers | review/red-team track definitions | Review governance | `bash compass/tools/redcap-review-tracks-check.sh` |
| [`compass/CONTRIBUTING.core.md`](../compass/CONTRIBUTING.core.md) | Skill And Host Distribution | startup-safe core RedCap contract | Compass governance | `bash compass/tools/redcap-contributing-ia-check.sh` |
| [`compass/CONTRIBUTING.md`](../compass/CONTRIBUTING.md) | Skill And Host Distribution | full authoritative development contract | Compass governance | `bash compass/tools/redcap-contributing-ia-check.sh` |
| [`compass/soul.md`](../compass/soul.md) | Skill And Host Distribution | Cap revival and growth guide; identity anchor remains external | Identity layer | `bash compass/tools/redcap-revival-check.sh "$PWD"` |
| [`SKILL.md`](../SKILL.md) | Skill And Host Distribution | Claude skill entry for RedCap | Host adapters | `bash compass/tools/redcap-skill-lifecycle-check.sh` |
| [`references/host-session-capability-matrix.json`](../references/host-session-capability-matrix.json) | Skill And Host Distribution | host hook/session capability matrix | Host adapters | `bash compass/tools/redcap-host-hook-readiness.sh` |
| [`compass/tools/redcap-host-hook-readiness.sh`](../compass/tools/redcap-host-hook-readiness.sh) | Skill And Host Distribution | host hook readiness checker | Host adapters | `bash compass/tools/redcap-host-hook-readiness.sh` |
| [`compass/tools/redcap-hook-contract-check.sh`](../compass/tools/redcap-hook-contract-check.sh) | Skill And Host Distribution | hook contract validator | Host adapters | `bash compass/tools/redcap-hook-contract-check.sh` |
| [`compass/tools/redcap-docs-catalog.py`](../compass/tools/redcap-docs-catalog.py) | Docs Knowledge And Evolution | docs catalog generator and read-budget auditor | Docs governance | `bash compass/tools/redcap-docs-catalog.sh check` |
| [`compass/knowledge/lessons.md`](../compass/knowledge/lessons.md) | Docs Knowledge And Evolution | active lessons store | Knowledge governance | `bash compass/tools/redcap-knowledge-index-check.sh` |
| [`compass/evolution/README.md`](../compass/evolution/README.md) | Docs Knowledge And Evolution | Evolution Factory workflow guide | Evolution Factory | `bash compass/tools/redcap-evolution-candidate-check.sh` |
| [`compass/evolution/candidates.json`](../compass/evolution/candidates.json) | Docs Knowledge And Evolution | active Evolution candidate pool | Evolution Factory | `bash compass/tools/redcap-evolution-candidate-check.sh` |
| [`references/evolution-candidate-schema.json`](../references/evolution-candidate-schema.json) | Docs Knowledge And Evolution | candidate pool schema contract | Evolution Factory | `bash compass/tools/redcap-evolution-candidate-check.sh` |
| [`compass/tools/redcap-evolution-candidate-check.sh`](../compass/tools/redcap-evolution-candidate-check.sh) | Docs Knowledge And Evolution | candidate pool shell validator | Evolution Factory | `bash compass/tools/redcap-evolution-candidate-check.sh` |
| [`compass/tools/redcap-evolution-candidate-check.py`](../compass/tools/redcap-evolution-candidate-check.py) | Docs Knowledge And Evolution | candidate pool validator | Evolution Factory | `bash compass/tools/redcap-evolution-candidate-check.sh` |
| [`compass/tools/redcap-evolution-harvest-check.sh`](../compass/tools/redcap-evolution-harvest-check.sh) | Docs Knowledge And Evolution | task-report Evolution candidate handling gate | Evolution Factory | `bash compass/tools/redcap-evolution-harvest-check.sh .dev-task.md` |
| [`compass/tools/redcap-evolution-harvest-check.py`](../compass/tools/redcap-evolution-harvest-check.py) | Docs Knowledge And Evolution | task-report candidate handling validator | Evolution Factory | `bash compass/tools/redcap-evolution-harvest-check.sh .dev-task.md` |
| [`references/token-structural-governance.json`](../references/token-structural-governance.json) | Product Shape And Retrieval | token-risk governance registry | Token governance | `bash compass/tools/redcap-token-risk-audit.sh` |
| [`compass/tools/redcap-token-risk-audit.sh`](../compass/tools/redcap-token-risk-audit.sh) | Product Shape And Retrieval | token-risk audit shell entry | Token governance | `bash compass/tools/redcap-token-risk-audit.sh` |
| [`compass/tools/redcap-token-risk-audit.py`](../compass/tools/redcap-token-risk-audit.py) | Product Shape And Retrieval | token-risk audit validator | Token governance | `bash compass/tools/redcap-token-risk-audit.sh` |
| [`references/legacy-asset-lifecycle.json`](../references/legacy-asset-lifecycle.json) | Product Shape And Retrieval | legacy asset retain/archive/prune policy | Legacy governance | `bash compass/tools/redcap-legacy-asset-lifecycle-check.sh` |
| [`compass/tools/redcap-legacy-asset-lifecycle-check.sh`](../compass/tools/redcap-legacy-asset-lifecycle-check.sh) | Product Shape And Retrieval | legacy asset lifecycle shell entry | Legacy governance | `bash compass/tools/redcap-legacy-asset-lifecycle-check.sh` |
| [`compass/tools/redcap-legacy-asset-lifecycle-check.py`](../compass/tools/redcap-legacy-asset-lifecycle-check.py) | Product Shape And Retrieval | legacy asset lifecycle validator | Legacy governance | `bash compass/tools/redcap-legacy-asset-lifecycle-check.sh` |
| [`shared-knowledge/README.md`](../shared-knowledge/README.md) | Shared Knowledge Layer | local template for future independent shared knowledge repository | Knowledge gateway | `bash compass/tools/redcap-shared-knowledge-check.sh` |
| [`shared-knowledge/schemas/entry.schema.json`](../shared-knowledge/schemas/entry.schema.json) | Shared Knowledge Layer | append-only shared knowledge entry contract | Knowledge gateway | `bash compass/tools/redcap-shared-knowledge-check.sh` |
| [`references/shared-knowledge-policy.json`](../references/shared-knowledge-policy.json) | Shared Knowledge Layer | shared knowledge repository policy and append-only rules | Knowledge gateway | `bash compass/tools/redcap-shared-knowledge-check.sh` |
| [`compass/tools/redcap-shared-knowledge.sh`](../compass/tools/redcap-shared-knowledge.sh) | Shared Knowledge Layer | shared knowledge CLI shell entry | Knowledge gateway | `bash compass/tools/redcap-shared-knowledge-check.sh` |
| [`compass/tools/redcap-shared-knowledge.py`](../compass/tools/redcap-shared-knowledge.py) | Shared Knowledge Layer | shared knowledge init, append, index, duplicate detection and check logic | Knowledge gateway | `bash compass/tools/redcap-shared-knowledge.sh check` |
