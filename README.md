# RedCap — 多 Agent 协同工程开发框架

> 你说需求，AI 团队完成交付。

---

## 它是什么

RedCap 是一个运行在 AI Agent 宿主工具（Claude Code / Gemini CLI / Copilot CLI 等）之上的**多角色协同框架**。触发后，它自动编排产品经理、架构师、程序员、测试、评审五个 AI 角色，完成从需求到代码的完整开发流程。

```
你的一句需求
      │
      ▼
┌─────────────────────────────────────┐
│           RedCap Dispatcher          │
│                                     │
│  产品经理 → 架构师 → 程序员 → QA → 评审  │
│                                     │
│  每步完成后自动流转，直到交付        │
└─────────────────────────────────────┘
      │
      ▼
可运行的代码 + 完整文档
```

---

## 为什么用它

| 痛点 | RedCap 的解法 |
|------|-------------|
| 单个 Agent 上下文有限，复杂任务容易跑偏 | 多 Agent 接力，每个角色只关注自己的职责 |
| 每次都要重复描述规范、格式、约束 | 角色手册 + 元原则一次写入，自动注入每个 Agent |
| AI 给了结果但没有 Review | 独立评审角色兜底，可靠性机制多层防护 |
| 换了工具就要重新适配 | 适配器层屏蔽差异，五种宿主工具开箱即用 |

---

## 快速开始

在任意支持 Skill 的 AI 宿主中触发：

```
@redcap 帮我做一个用户登录模块，支持手机号+验证码
```

框架自动运行，中途如需介入直接在对话中说即可。

---

## 深入了解

| 文档 | 内容 |
|------|------|
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | 完整架构设计、状态机、通信协议、可靠性工程 |
| [`CONTRIBUTING.md`](./CONTRIBUTING.md) | 框架自身开发规范（Commit 格式、PM Gate、Red Teaming） |
| [`SKILL.md`](./SKILL.md) | Dispatcher 完整执行协议（面向 AI Agent） |
| [`knowledge/design-principles.md`](./knowledge/design-principles.md) | 五项元原则（框架灵魂） |
