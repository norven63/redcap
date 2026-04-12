# RedCap — 多 Agent 协同工程开发框架

> 你说需求，AI 团队完成交付。

---

## 它是什么

RedCap 是运行在 AI 宿主工具（Claude Code / Gemini CLI / Copilot CLI 等）之上的**多角色协同工程框架**。你描述需求，RedCap 自动编排五个专职 AI 角色完成从需求到代码的全流程——每个角色只负责自己的职责，完成后自动交棒。

```
你的一句需求
      │
      ▼
┌────────────────────────────────────────────────────────┐
│                   RedCap Dispatcher                     │
│                                                        │
│  ① PM Gate ──需求锁定──▶ ② 产品经理                    │
│                              │ 需求文档                 │
│                              ▼                          │
│                         ③ 架构师 ──▶ 高风险? ──▶ 棱镜   │
│                              │ 分步设计                 │
│                              ▼                          │
│                         ④ 程序员                        │
│                              │ 代码 + 自测报告           │
│                              ▼                          │
│                         ⑤ QA ──FAIL──▶ 回退对应角色     │
│                              │ PASS                     │
│                              ▼                          │
│                         ⑥ 独立 Reviewer ──▶ git commit  │
│                                                        │
│  全程：Session 续接 · Fallback 路由 · 多层质量门禁       │
└────────────────────────────────────────────────────────┘
      │
      ▼
可运行的代码 + 完整文档
```

**RedCap 的设计哲学**：单个 Agent 独自完成复杂任务容易跑偏、遗漏、无法自我验证。RedCap 让每个 AI 角色职责单一，通过**状态机驱动交棒、独立角色互相审查、多层防护门禁**，把不可靠的单点放大成可靠的流水线。

---

## 核心设计亮点

### 可靠性：多层质量防护

RedCap 不依赖单次 AI 输出的质量，而是通过**结构性机制**兜底：

- **角色隔离**：每个角色只读取上游 outbox，不跨层访问，防止信息污染
- **交付物校验**：Dispatcher 在每步 Agent 完成后验证文件实际写入磁盘，校验不通过不推进
- **独立 Reviewer**：QA 通过后，由独立评审角色再次 Review，commit 是门禁而非默认动作
- **防退化机制**：长任务中 reload-rules 在关键节点重载规范，`pending_actions` 双保险防遗漏

### 鲁棒性：自愈与恢复

- **Session 续接**：每个 Agent 运行记录 session ID，中断后可从断点恢复，不丢失上下文
- **Fallback 路由**：Agent 失败自动切换候选，路由算法动态计算适配分，不硬编码优先级
- **三级决策升级**：Agent 自主 → PM Agent → 用户，大多数阻塞在 L0/L1 自动消化

### 高风险决策：棱镜多模型验证

重要变更触发**棱镜（Prism）**：跨模型家族（Claude/GPT/Gemini）多 Agent 并行分析，结果经 Synthesize 聚合、Adjudicate 裁决。对抗角色（挑战者/审查员/旧错者/探索者）各持独立视角，在注入分层隔离下防止 prompt injection 污染评审结论。

### 自演化：框架自身持续进化

- **Compass 独立管理框架演化**：框架自身的开发遵守与用户项目相同的严格流程
- **Lessons 积累防坑**：经验教训沉淀为 `lessons.md`，每次新任务自动注入防护
- **模型矩阵**：`model-capability-matrix.yaml` 按角色能力权重路由，并在“能力相当”时优先低成本候选（优先 Gemini，保留动态 fallback）；30天过期触发更新
- **书记官协议**：多轮讨论自动落盘 `explore-notes.md`，防止决策上下文在压缩中丢失

---

## 三体架构

RedCap 内部由三个子系统构成，各司其职、边界清晰：

```
redcap/
├── loom/      ← 织机（Layer A）  为用户项目编织代码的执行引擎
├── compass/   ← 璇玑（Layer B）  Cap 的指挥所，管理框架自身的演化
└── prism/     ← 棱镜            多视角分析引擎，高风险决策前的并行评审
```

### 织机（Loom）— Layer A

执行引擎。Dispatcher 状态机驱动五角色流水线（PM → 架构师 → 程序员 → QA → Reviewer），处理回退、Session 恢复、Hook 触发、Fallback 路由等所有工程流程。支持迭代开发、旧项目纳管、多步并行裂变。

### 璇玑（Compass）— Layer B

Cap 的指挥所。管理框架自身的知识（lessons.md）、开发规范（CONTRIBUTING.md）、Hook 基础设施（飞书通知、会话级自动 Review）以及 Cap 的人格（soul.md）。提供指挥棒工具（baton-launcher / baton-collect / baton-delegate）作为跨层调度原语。

### 棱镜（Prism）

多模型并行评审引擎。支持两种协议族：**独立取样**（多模型各自分析后汇聚）和**议事**（多模型多轮讨论）。棱镜内置对抗角色（挑战者、审查员、旧错者、探索者），在架构决策和高风险变更前提供跨家族模型的对抗性验证。

---

## 目录结构

```
redcap/
├── SKILL.md          ← Copilot CLI skill 入口（Dispatcher 完整执行协议）
├── CLAUDE.md / GEMINI.md / .github/copilot-instructions.md  ← 各宿主配置索引
├── README.md / ARCHITECTURE.md
├── references/       ← 跨层公约（security-rules, code-standards, commit-standards,
│                        hook-standards, communication-protocol, agent-constraints）
│
├── loom/             ← 织机（Layer A）
│   ├── dispatcher/   ← state-machine.md, agent-adapters.md, prompt-templates/, reload-rules.yaml
│   ├── roles/        ← 五角色手册（architect, programmer, qa, reviewer, product-manager）
│   ├── tools/        ← Layer A 脚本（redcap-layerA-*.sh, redcap-e2e-postcheck.sh）
│   └── test-reports/ ← E2E 测试报告
│
├── compass/          ← 璇玑（Layer B）
│   ├── soul.md       ← Cap 人格与复活协议
│   ├── CONTRIBUTING.md ← 框架自身开发的唯一权威规范
│   ├── CHANGELOG.md
│   ├── knowledge/    ← lessons.md, design-principles.md, host-reliability.md,
│   │                    hooks-*.md, model-capability-matrix.yaml, …
│   ├── tools/        ← Layer B 脚本（飞书通知、Claude/Gemini/Kimi Hook 处理器）
│   ├── docs/         ← 设计文档和技术调研
│   └── .workflow/    ← 运行时状态（agent-registry.yaml 等）
│
└── prism/            ← 棱镜
    ├── protocol.md   ← 棱镜协议（独立取样 + 议事两族）
    ├── modes/        ← 运行模式配置
    ├── roles/        ← 分析角色（挑战者、审查员、旧错者、运筹者等）
    ├── reports/      ← 历史运行报告
    └── tools/        ← prism-dispatch-check.sh, prism-archive-check.sh
```

---

## 快速开始

### 前提

- 安装至少一个 AI CLI（[Claude Code](https://docs.anthropic.com/en/docs/claude-code)、[Gemini CLI](https://github.com/google-gemini/gemini-cli)、[Kimi CLI](https://github.com/MoonshotAI/kimi-cli) 之一）
- 宿主环境：VS Code Copilot CLI / Claude Code / Gemini CLI / Kimi CLI

### 触发

在宿主 AI Agent 中直接描述需求即可：

```
@redcap 帮我开发一个任务管理系统
@redcap 给现有项目增加支付功能
@redcap 修复用户登录超时的 bug
```

Skill 自动触发，Dispatcher 接管后续全流程。框架运行中途如需介入，直接在对话中说即可。

### 飞书集成（可选）

```bash
python3 compass/tools/feishu-notifier.py setup
```

配置后，用户项目流程完成会自动发飞书通知；RedCap 自身开发则按 `compass/CONTRIBUTING.md` 的收尾协议执行，并由宿主 SessionEnd Hook 做兜底。

---

## 为什么用它

| 痛点 | RedCap 的解法 |
|------|-------------|
| 单个 Agent 上下文有限，复杂任务容易跑偏 | 多 Agent 接力，每个角色只关注自己的职责 |
| 每次都要重复描述规范、格式、约束 | 角色手册 + 元原则一次写入，自动注入每个 Agent |
| AI 给了结果但没有 Review | 独立评审角色兜底，可靠性机制多层防护 |
| 换了工具就要重新适配 | 适配器层屏蔽差异，多宿主工具开箱即用 |
| 框架自身越改越乱 | 璇玑（Compass）独立管理框架演化，lessons 积累防坑 |

---

## 深入了解

| 文档 | 内容 |
|------|------|
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | 三体架构详解、Dispatcher 状态机、Hook 基础设施、棱镜机制 |
| [`compass/CONTRIBUTING.md`](./compass/CONTRIBUTING.md) | 框架自身开发的唯一权威规范（Commit 格式、PM Gate、Red Teaming） |
| [`SKILL.md`](./SKILL.md) | Dispatcher 完整执行协议（面向 AI Agent） |
| [`compass/knowledge/design-principles.md`](./compass/knowledge/design-principles.md) | 五项元原则（框架灵魂） |
| [`compass/soul.md`](./compass/soul.md) | Cap 的人格与复活协议 |
| [`prism/protocol.md`](./prism/protocol.md) | 棱镜协议（多视角并行评审） |
