# RedCap 框架升级 Backlog 设计

> **定位**：将 2026-04-11 至 2026-04-13 这整段长任务暴露出的优化点，整理成一份可 review、可切 tranche、可持续实施的完整升级 backlog。
> 
> **设计结论先行**：
> 1. 本 backlog 采用 **5 个能力模块 + 1 个独立治理主线** 的结构。
> 2. 优先级规则以 **authority / closure / session isolation 是否失真** 为第一判断标准。
> 3. 真正保障 RedCap 运行的，应当是 **hook、gate、runtime state、脚本、校验器、closure chain**；`specs/docs` 只承担说明、设计冻结与证据职责，不承担 runtime authority。

---

## 一、背景与目标

本轮 backlog 不是只回顾最近几轮关于会话隔离的追问，而是把整段长任务自开始以来的演化重新拉通：

1. docs 架构与 artifact lifecycle 混层  
2. autonomy / ask_user / overlay skill 越界  
3. Gemini-first but capability-aware 路由治理  
4. 收尾链（task report / notify / final reply）信息吞没  
5. continuity assets、session isolation、explicit import、host adapter 边界  
6. specs/docs/knowledge 的定位漂移  
7. runtime helper / 文件数量 / authority 证据散落  
8. 工程治理与业内权威规范如何进入 RedCap 的可执行保障链

本设计的目标不是“列一堆 TODO”，而是给出一份：

- **能 review 的结构**
- **能切 tranche 的顺序**
- **能落成 hook/gate/runtime/validator 的升级路线**

---

## 二、Backlog 组织方式

### 2.1 总结构

完整 backlog 分成 **5 个能力模块 + 1 个独立治理主线**：

1. **Authority / Closure 收口**
2. **会话隔离与连续性**
3. **宿主适配与交互面**
4. **文档信息架构与证据分层**
5. **运行时资产与文件收敛**
6. **工程治理 / 权威规范升级（独立主线）**

### 2.2 每个 backlog 项的统一字段

每个 backlog 项统一包含：

1. **问题**
2. **目标状态**
3. **现有基础**
4. **未落地项**
5. **风险**
6. **验收方式**

### 2.3 优先级定义

| 级别 | 定义 |
|---|---|
| **P0** | 会破坏 authority、closure、session isolation，或导致错误完成态 / 错误升级 / 状态串扰 |
| **P1** | 不立即破坏真相链，但会持续侵蚀可靠性、宿主一致性、可审计性 |
| **P2** | 结构优化、文件收敛、归档/索引、长期可维护性项 |

---

## 三、模块 A：Authority / Closure 收口

### A1. Closure authority ledger 与 obligation 生命周期统一

- **问题**：closure 目前由 `on-complete`、`session-end`、`pending closure`、task report gate 等多脚本协作完成，但仍缺一个单一的 closure authority ledger。
- **目标状态**：任何“这次任务是否真的闭环”的判断，都能落回同一条 closure transaction / obligation lifecycle。
- **现有基础**：
  - `redcap-on-complete.sh`
  - `redcap-layerB-session-end.sh`
  - `redcap-task-report-check.sh`
  - pending closure 机制已存在
- **未落地项**：
  - 建立 closure transaction ledger
  - obligation 自动核销 / stale obligation 管理
  - task report mandatory audit fail-closed
- **优先级**：**P0**
- **来源合并**：BL-CL-001、BL-CL-002、BL-CL-003

### A2. PM Gate + confirmed hash + validator chain 的硬化

- **问题**：PM Gate、drift-check、task-report-check 等 validator 已存在，但顺序、依赖和 fail-closed 语义还未统一编排。
- **目标状态**：session-start / stop-review / on-complete 都通过统一 validator chain 驱动，confirmed hash 变化无法被静默绕过。
- **现有基础**：
  - `redcap-pm-gate-check.sh`
  - `redcap-drift-check.sh`
  - `redcap-task-report-check.sh`
- **未落地项**：
  - `redcap-validator-chain.sh`
  - strict 模式下的 hash/re-anchor 硬门禁
  - validator 输出结构化结果供下游消费
- **优先级**：**P0**
- **来源合并**：BL-AU-001、BL-AU-005

### A3. Governance / contract / architecture 三轨 review

- **问题**：当前 review 更偏 code / logic，authority、contract、lifecycle 类缺口仍可能漏过。
- **目标状态**：stop-review 至少分成 architecture、governance、contracts 三条审计轨。
- **现有基础**：
  - `redcap-on-stop-review.sh`
  - 独立评审模式
  - 任务报告自动化验证段
- **未落地项**：
  - `redcap-review-governance.sh`
  - `redcap-review-contracts.sh`
  - 统一 review gate 汇总
- **优先级**：**P1**
- **来源合并**：GOV-008、BL-OBS-002

---

## 四、模块 B：会话隔离与连续性

### B1. RedCap-owned continuity manifest

- **问题**：当前 continuity authority 仍散在宿主 session folder、mirror、import metadata、runtime helper 等多处。
- **目标状态**：RedCap 自己维护唯一 continuity authority；宿主只读取 mirror。
- **现有基础**：
  - `redcap-session-continuity.sh`
  - `Session Mirror`
  - explicit import protocol
- **未落地项**：
  - `compass/.runtime/sessions/<runtime_session_id>/manifest.yaml`
  - import registry / continuity audit log
  - continuity asset provenance manifest
- **优先级**：**P0**
- **来源合并**：SESSION-001、SESSION-005、SESSION-008、SESSION-012

### B2. Session resume gate 与跨宿主能力矩阵

- **问题**：不同宿主 session id / binding 能力差异很大，resume / degraded mode 仍缺统一恢复门。
- **目标状态**：所有宿主都通过 capability matrix + session-resume-gate 进入对应隔离模式（full / degraded / unsupported）。
- **现有基础**：
  - `redcap-layerB-session-start.sh`
  - `loom/dispatcher/agent-adapters.md`
  - 现有 session matrix 文档
- **未落地项**：
  - `redcap-session-resume-gate.sh`
  - host capability check
  - isolation mode 明确落盘与展示
- **优先级**：**P1**
- **来源合并**：SESSION-004、SESSION-011、BL-MS-001

### B3. Explicit import 的 operator feedback 与 E2E 验收

- **问题**：explicit import 目前可用，但 suggestion/acceptance 的用户反馈和端到端验收仍不完整。
- **目标状态**：import-ready signal、import success summary、跨宿主/跨 agent 的 E2E 验证都可执行。
- **现有基础**：
  - `redcap-session-continuity.sh import`
  - 当前 `import-suggested` / `imported` 状态
- **未落地项**：
  - import-ready signal
  - multi-session import acceptance
  - 跨宿主兼容性矩阵
- **优先级**：**P1**
- **来源合并**：SESSION-006、BL-MS-002

---

## 五、模块 C：宿主适配与交互面

### C1. Host mirror-only enforcement 与统一 mirror generator

- **问题**：workboard mirror 由多个工具写入，且 mirror-only 原则目前主要靠文档约束。
- **目标状态**：镜像块由单一生成器负责，宿主不可反向推动 canonical truth。
- **现有基础**：
  - `redcap-host-workboard-sync.sh`
  - `redcap-session-continuity.sh`
  - Session Mirror 约定
- **未落地项**：
  - `redcap-mirror-gen.sh`
  - host workboard read+validate
  - mirror drift audit
- **优先级**：**P1**
- **来源合并**：BL-AU-002、SESSION-003

### C2. `cli_console.md` 降格为 mirror-only display

- **问题**：`cli_console.md` 曾被当成第二份答案，破坏单一阅读面。
- **目标状态**：它只镜像当前长回复，不承担 authority，不累积为历史日志。
- **现有基础**：
  - 用户偏好已明确
  - 当前已手工纠偏
- **未落地项**：
  - mirror-only 规则写入治理
  - 如有需要，自动生成/覆盖而非追加堆积
- **优先级**：**P1**
- **来源合并**：SESSION-002

### C3. 宿主 overlay / shared skill / ask_user 的诚实降级

- **问题**：共享宿主 skill 所有权、overlay ask_user 违规、host event orchestration 仍分散。
- **目标状态**：shared skill ownership、unsupported overlay、host event emission 都有可执行标记与审计。
- **现有基础**：
  - autonomy-escalation-p0 已收口 shared skill 资产边界
  - ask_user 规则已进入 SKILL / CONTRIBUTING
- **未落地项**：
  - `.skill-ownership.yaml`
  - ask_user honest degradation 标记
  - host event orchestrator
- **优先级**：**P1**
- **来源合并**：BL-AU-003、BL-AU-006、SESSION-010

---

## 六、模块 D：文档信息架构与证据分层

### D1. Specs 生命周期收紧

- **问题**：`specs/` 已出现“冻结契约、调查笔记、临时设计、过程材料”混装。
- **目标状态**：spec 只承载长期冻结设计契约；运行保障必须落在 hook/gate/runtime/validator，不得靠 spec 文案兜底。
- **现有基础**：
  - `compass/docs/index.yaml`
  - docs 治理 tranche 已完成第一轮分层
- **未落地项**：
  - spec registry / approval status
  - specs 准入门与迁移门
  - specs → archive / research / task-reports 的归位规则
- **优先级**：**P0**
- **来源合并**：GOV-001、SESSION-007

### D2. Knowledge / lessons / docs 的边界导航

- **问题**：`compass/knowledge/` 中 principles、lessons、host behavior、notes 仍偏散；新贡献者不易判断该改哪里。
- **目标状态**：knowledge 有清晰 INDEX，docs / knowledge / continuity 各归其位。
- **现有基础**：
  - 目录哲学已在 ARCHITECTURE 落下
  - `lessons.md`、`design-principles.md` 已存在
- **未落地项**：
  - `compass/knowledge/INDEX.md`
  - 各 knowledge 文件头信息
  - 引用导航规则
- **优先级**：**P2**
- **来源合并**：GOV-009

### D3. Docs retention / archive enforcement

- **问题**：retention policy 已有文档化规则，但还没有自动 enforcement。
- **目标状态**：archive 不是“将来再说”，而是有检查脚本与 archive log 的机制。
- **现有基础**：
  - `compass/docs/index.yaml`
  - archive 目录约定
- **未落地项**：
  - `redcap-docs-retention-audit.sh`
  - `ARCHIVE_LOG.md`
  - CI check-only 审计
- **优先级**：**P2**
- **来源合并**：GOV-010

---

## 七、模块 E：运行时资产与文件收敛

### E1. Artifact lifecycle enforcement

- **问题**：生命周期分类已文档化，但还缺物理门禁，仍可能把 session/cache/local-only 文件带进 git。
- **目标状态**：pre-commit / classifier 在提交前就阻断错误 artifact。
- **现有基础**：
  - `.gitignore`
  - `compass/docs/index.yaml`
  - artifact lifecycle 口径已落入 ARCHITECTURE / CONTRIBUTING
- **未落地项**：
  - artifact classifier
  - pre-commit lifecycle enforcement
  - mixed-lifecycle commit 阻断
- **优先级**：**P0**
- **来源合并**：GOV-002

### E2. Session/runtime helper 收敛

- **问题**：session/runtime helper 脚本数量偏多，状态读写逻辑重复。
- **目标状态**：把高频 state read/write、CAS、continuity helpers 抽到共享库，减少分散脚本体积。
- **现有基础**：
  - `redcap-runtime-state.sh`
  - 已有多脚本共享模式
- **未落地项**：
  - `compass/lib/redcap-session.sh`
  - runtime/continuity 统一 API
  - duplicated logic shrink
- **优先级**：**P2**
- **来源合并**：SESSION-009

### E3. 统一诊断与 authority/continuity 可观测性

- **问题**：当前要理解 session / closure / drift / hook / debt 状态，需要手工查多个脚本与文件。
- **目标状态**：一条 diagnose 命令能给出当前运行态和治理态。
- **现有基础**：
  - 现有 runtime helpers 与各类 gate
- **未落地项**：
  - `redcap-diagnose.sh`
  - authority chain trace / audit visualization
- **优先级**：**P1**
- **来源合并**：BL-OBS-001、BL-OBS-002

---

## 八、模块 F：工程治理 / 权威规范升级（独立主线）

### F1. Governance tranche 制度化 + debt register

- **问题**：治理项经常在实现后半段才被想起，缺少作为 1st-class 主线的追踪机制。
- **目标状态**：治理 tranche、治理 review checklist、governance debt register 都成为显式机制。
- **现有基础**：
  - 最近多轮 tranche 已产出大量治理经验
  - 你已明确要求把这条单列为独立主线
- **未落地项**：
  - governance_tranche 标记
  - governance review checklist
  - governance debt register
- **优先级**：**P0**
- **来源合并**：BL-GOV-001、BL-GOV-003

### F2. Specs-to-gates translation / executable norms

- **问题**：设计与规范常常停留在文档层，没有转成可执行 gate / validator / script。
- **目标状态**：能落地的规范都必须进入 RedCap 的可执行保障链；不能落地的只能算研究/说明，不算 runtime 约束。
- **现有基础**：
  - 设计文档与脚本雏形很多
  - 但映射关系还没正式化
- **未落地项**：
  - spec compliance audit
  - executable tag / validator linkage
  - 业内规范引入与映射规则
- **优先级**：**P1**
- **来源合并**：GOV-003、BL-GOV-002

### F3. Hook / lesson / contract / FSM 的治理硬化

- **问题**：hook chain completeness、lessons 作为 guard rail、outbox schema、FSM canonical source 等都已有口头或文档规则，但执行面仍不够硬。
- **目标状态**：这些“真正保障运行的机制”全部具备脚本化、校验化、可审计化表达。
- **现有基础**：
  - hook-standards
  - lessons
  - role handbooks
  - state machine 文档
- **未落地项**：
  - hook phase reporter + hook chain audit
  - lesson injector / lesson compliance audit
  - outbox schemas / role contract validator
  - canonical FSM YAML
- **优先级**：**P1**
- **来源合并**：GOV-004、GOV-005、GOV-006、GOV-007、BL-AU-004

---

## 九、建议的 tranche 顺序

### Tranche 1 — Authority Core Hardening

优先做：

1. A1 Closure authority ledger
2. A2 Validator chain + PM Gate/hash hardening
3. E1 Artifact lifecycle enforcement
4. F1 Governance tranche + debt register

**理由**：先把 authority / closure / lifecycle 三条底座收紧，后面其它改造才不会继续建立在散落 authority 上。

### Tranche 2 — Continuity Authority Centralization

优先做：

1. B1 RedCap-owned continuity manifest
2. B2 Session resume gate + host capability matrix
3. C1 Mirror generator + host mirror-only enforcement

**理由**：先把 continuity authority 和 host mirror 切开，再做 import 反馈、文件收敛才不会反复返工。

### Tranche 3 — Governance Executability

优先做：

1. F2 Specs-to-gates translation
2. F3 Hook / lesson / contract / FSM hardening
3. A3 三轨 review gate

**理由**：把“规范不能只停在文档层”这件事真正变成 RedCap 的可执行能力。

### Tranche 4 — Host UX & Operator Feedback

优先做：

1. B3 Explicit import feedback + E2E
2. C2 `cli_console.md` mirror-only
3. C3 shared skill / ask_user honest degradation

**理由**：这一层主要收口宿主体验和诚实降级，不应该早于 authority core。

### Tranche 5 — IA Cleanup & Tool Consolidation

优先做：

1. D1 Specs lifecycle收紧
2. D2 Knowledge index
3. D3 Docs retention enforcement
4. E2 Runtime helper收敛
5. E3 Diagnose / observability

**理由**：这是结构优化与长期维护层，重要但不应先于 authority/closure/continuity 核心。

---

## 十、非目标

本 backlog **不**包含：

1. 重新推翻 `.dev-task.md` 作为 Layer B canonical truth 的地位  
2. 默认自动 takeover 最近会话  
3. 通过修改共享宿主 skill 原件来让 RedCap 自身能力成立  
4. 把 `specs` 文档重新提升为 runtime authority  
5. 在用户无感知时静默启用 `git worktree`

---

## 十一、评审输入来源

本设计综合了 3 路独立 backlog review：

1. `authority-backlog-review`：authority / closure / autonomy / runtime guarantees
2. `continuity-backlog-review`：session isolation / host adapter / file consolidation
3. `governance-norms-review`：governance / specs / docs / executable norms

这些 review 的原始输出不会直接成为 backlog 权威；它们只是本设计的输入证据。

---

## 十二、一句话总结

这份 backlog 的核心不是“再补几篇文档”或“再多加几个脚本”，而是把 RedCap 下一阶段的升级方向明确成：

> **先收 authority，再收 continuity，再把治理与规范翻译成 hook / gate / runtime state / 脚本 / 校验器 / closure chain 的可执行保障。**
