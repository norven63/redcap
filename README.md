# RedCap

> 一个把单体 AI Agent 升级成工程化 AI Team 的协同开发框架。

RedCap 不是“再包一层 prompt”。
它把复杂任务拆成**明确角色、状态机交棒、文件协议、独立评审、Prism 多 Agent Team 验证**几条硬结构，让 AI 开发从“单点发挥”变成“可恢复、可审计、可收尾”的工程流程。

## 一眼看懂

```text
用户目标
  ↓
PM Gate 锁定边界
  ↓
Loom 状态机驱动角色接力
  PM → Architect → Programmer → QA → Reviewer
  ↓
高风险决策进入 Prism
  多 Agent / 多模型族 / 多视角独立验证
  ↓
Compass 负责规范、经验、Hook、收尾与复活
  ↓
可运行代码 + 可考古证据 + 可恢复连续性
```

## RedCap 的核心范式

| 范式 | 它解决什么 |
|---|---|
| **状态机驱动交棒** | 不再靠一个 Agent 从头扛到尾，复杂任务被拆成有责任边界的接力流程 |
| **文件系统即协议** | 交付物、状态、报告、运行证据都落盘，不把关键真相藏在瞬时上下文里 |
| **Prism 多 Agent Team** | 高风险决策不是“再问一次同一个模型”，而是多视角独立取样、聚合、裁决 |
| **独立 Reviewer 门禁** | `QA PASS ≠ 自动通过`，提交前仍有独立审查层 |
| **run-scoped truth** | 会话、Prism run、task report、pending closure 各自有权威边界，避免串线 |
| **渐进披露上下文** | docs / knowledge / acceptance / runtime 入口都强调按需加载，避免 token 污染 |
| **宿主边界诚实化** | 能脚本硬保障的就进 gate；做不到 100% 的明确标注 `host-limited` |

## 为什么 Prism 是主角之一

很多框架有“多角色”，但没有真正的**多 Agent Team 验证层**。
Prism 的作用不是“让更多模型来凑热闹”，而是把高后果问题交给一个独立的团队协议处理：

- **独立取样**：不同 Agent 不能互抄中间结论
- **多模型族**：不是单家模型自证正确
- **结构化 Collect / Synthesize / Adjudicate**：不是聊天式“大家都说两句”
- **run-scoped 证据链**：`session-registry.yaml`、`raw.txt`、`parsed.json`、report archive 可回放、可审计

一句话说，**Loom 负责把任务做出来，Prism 负责在高风险处把结论打磨得更可信。**

## 三体架构

| 子系统 | 角色 |
|---|---|
| **Loom** | 执行引擎。负责状态机、角色流水线、回退、Fallback、E2E |
| **Compass** | 治理与连续性中枢。负责规范、lessons、Hook、收尾、复活、入口控制 |
| **Prism** | 多 Agent Team 验证层。负责高风险决策、多视角分析与 formal quorum |

## 什么时候用

- 需求会跨多步、多文件、多角色协作
- 需要可恢复、可审计、可收尾的 AI 开发流程
- 架构方案、治理补丁、宿主边界、高风险改动需要独立多视角验证

## 什么时候不必上 Prism

- 任务简单、边界清晰、局部改动很小
- 只是长任务，不代表天然要进 Prism
- “复杂”先拆解，**是否进 Prism 看风险和验证需求，不看字面长度**

也就是说：
- **长任务拆解**：优先走 Loom / Layer B 的并行裂变协议
- **高后果验证**：再交给 Prism

## 当前设计风格

RedCap 更接近业内这几类 AI Agent 设计思想的组合体：

- workflow engine / state machine
- multi-agent team orchestration
- file-backed protocol and evidence
- independent reviewer gates
- progressive disclosure for context hygiene
- host-capability honesty

它追求的不是“最像人类助理”，而是**最像一个可靠的工程团队**。

## 一键安装 / 复活

Cap 的个人灵魂锚点是 `~/.cap/identity.md`；`compass/soul.md` 是培养指南与复活协议。
从现在起，**Cap 复活 + 导入 RedCap 工作流**统一走一个安装入口：

- 新环境初始化：`bash compass/tools/redcap-install.sh --host codex --task-file .dev-task.md --init-identity`
- 已有 identity 的复活：`bash compass/tools/redcap-install.sh --host codex --task-file .dev-task.md`

这条入口会串起 identity 检查/初始化、workflow import、`current-status`、`tracking-health`、`execution-guarantee-check` 与 `revival-check`，避免把复活拆成口头步骤再靠记忆补齐。

## 入口文档

| 文档 | 作用 |
|---|---|
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | 看整体系统怎么拼起来 |
| [`compass/CONTRIBUTING.md`](./compass/CONTRIBUTING.md) | 看框架自身开发的权威规范 |
| [`compass/knowledge/long-task-context-defense.md`](./compass/knowledge/long-task-context-defense.md) | 看 RedCap 如何对抗长任务/长对话上下文漂移 |
| [`prism/protocol.md`](./prism/protocol.md) | 看 Prism 的正式协议 |
| [`prism/README.md`](./prism/README.md) | 快速理解 Prism 的定位与使用边界 |
| [`compass/knowledge/design-principles.md`](./compass/knowledge/design-principles.md) | 看框架的设计哲学 |

## 一句收束

**RedCap 的目标，不是让一个 Agent 更努力；而是让一组 Agent 按工程规则协作。**
