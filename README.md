# RedCap — 多 Agent 协同工程开发框架

> **一句话定义**：RedCap 是一个由 Dispatcher 驱动、多 AI Agent 分角色协作的软件工程开发框架。它不直接写代码，而是**调度独立的 AI Agent 完成产品→架构→编码→测试的完整工程流程**。

---

## 目录

- [为什么需要 RedCap？](#为什么需要-redcap)
- [核心架构](#核心架构)
- [两条工作流](#两条工作流)
  - [工作流 A：RedCap 开发用户项目](#工作流-a-redcap-开发用户项目)
  - [工作流 B：开发 RedCap 自身](#工作流-b-开发-redcap-自身)
- [系统设计详解](#系统设计详解)
  - [状态机](#状态机fsm)
  - [Dispatcher 执行协议](#dispatcher-执行协议)
  - [可靠性工程](#可靠性工程)
- [项目结构](#项目结构)
- [文件职责矩阵](#文件职责矩阵)
- [快速上手](#快速上手)
- [设计哲学](#设计哲学)
  - [常见架构疑问](#常见架构疑问)
- [作为 AI Agent 设计参考](#作为-ai-agent-设计参考)
  - [架构模式：Dispatcher + Worker Agents](#1-架构模式dispatcher--worker-agents)
  - [状态机驱动](#2-状态机驱动)
  - [可靠性三件套](#3-可靠性三件套核心创新)
    - [Hook 机制深度解读](#31-hook-机制深度解读)
    - [规则防退化](#32-规则防退化检查点重载)
    - [Pending Actions](#33-pending-actions待办持久化)
  - [经验库模式](#4-经验库模式可复用)
  - [通信协议设计](#5-通信协议设计)
  - [角色系统 + Prompt 模板](#6-角色系统--prompt-模板)
  - [完整阅读路径](#总览完整阅读路径)

---

## 为什么需要 RedCap？

单一 AI Agent 写代码的问题：

| 问题 | 表现 |
|------|------|
| **上下文溢出** | 长对话后遗忘需求、跳过测试、丢失架构约束 |
| **角色混淆** | 同时做需求分析、写代码、跑测试，互相干扰 |
| **无流程保障** | 没有 QA 门禁，代码质量取决于模型心情 |
| **不可恢复** | 对话中断后无法从断点恢复 |

RedCap 的解法：**将一个大任务拆解为多角色流水线，每个角色由独立 AI Agent 执行，由 Dispatcher 状态机驱动流转。**

---

## 核心架构

```
                          ┌─────────────────────────────────────────────┐
                          │           Dispatcher（调度器/你）             │
                          │                                             │
                          │  ┌─────────┐  ┌──────────┐  ┌───────────┐  │
                          │  │读 state │→│选 Agent  │→│调 CLI    │  │
                          │  │.yaml    │  │+ Prompt  │  │等待返回  │  │
                          │  └─────────┘  └──────────┘  └─────┬─────┘  │
                          │       ▲                           │        │
                          │       │    ┌──────────────────────┘        │
                          │       │    ▼                               │
                          │  ┌────┴────────┐  ┌───────────┐           │
                          │  │更新 state   │←│解析返回  │           │
                          │  │触发 Hooks   │  │校验交付物│           │
                          │  └─────────────┘  └───────────┘           │
                          └─────────────────────────────────────────────┘
                               │         │         │         │
                         ┌─────┘   ┌─────┘   ┌─────┘   ┌─────┘
                         ▼         ▼         ▼         ▼
                      ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
                      │  PM  │ │ ARCH │ │ DEV  │ │  QA  │
                      │Agent │ │Agent │ │Agent │ │Agent │
                      └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘
                         │        │        │        │
                      kimi     gemini    gemini    kimi
                      claude   kimi      kimi      claude
                      gemini   claude    claude    gemini
                      (Fallback 路由)
```

**核心理念**：Dispatcher 是**纯调度器**，不写代码、不做设计。它只做三件事：
1. **读状态** — 从 `state.yaml` 知道"现在到哪了"
2. **选 Agent + 组 Prompt** — 按路由表选 CLI，按模板填 Prompt
3. **解析返回 + 推进** — 校验交付物，触发 Hooks，更新状态

---

## 两条工作流

RedCap 有两条完全不同的工作流：

### 工作流 A：RedCap 开发用户项目

这是 RedCap 的**核心用途** — 用多 Agent 协作来开发一个软件项目。

```
用户需求
   │
   ▼
┌─────────────────────────── Dispatcher 事件循环 ───────────────────────────┐
│                                                                           │
│  ┌───────┐     ┌───────┐     ┌─────────┐     ┌──────┐     ┌──────────┐  │
│  │  PM   │────→│ ARCH  │────→│  DEV    │────→│  QA  │────→│ REVIEW   │  │
│  │需求分析│     │架构设计│     │编码实现  │     │验证测试│    │最终审查   │  │
│  └───┬───┘     └───┬───┘     └────┬────┘     └───┬──┘     └────┬─────┘  │
│      │             │              │              │              │        │
│      ▼             ▼              ▼              ▼              ▼        │
│   需求文档    分步设计文档     代码+自测报告   测试报告      审查报告     │
│              技术框架设计                                                 │
│                                                                           │
│  ◄──── QA 失败：按 root_cause 回退到 DEV/ARCH/PM ─────                  │
│                                                                           │
│  on_QA_PASS → git commit     on_ALL_DONE → 清理 + 飞书通知              │
└───────────────────────────────────────────────────────────────────────────┘
   │
   ▼
完成（飞书通知用户）
```

**关键规则**：
- Dispatcher **不写代码** — 所有代码由 Agent 生成（铁律）
- 每步 QA 通过才能 commit — 自动由 `on_QA_PASS` hook 执行
- QA 失败按根因回退 — `code` → DEV、`design` → ARCH、`requirement` → PM
- 架构师按步骤拆分 — 每步一个模块设计文档，DEV 和 QA 按步骤逐个推进
- 支持迭代开发 — 完成后可增量迭代（`iteration: N+1`）

**五种启动场景**：

| 场景 | 条件 | 入口 |
|------|------|------|
| S0: 全新项目 | 无 `开发手册/` | 初始化 → PM |
| S1: 迭代开发 | `state.yaml` + `ALL_DONE` | 代码库扫描 → PM（增量模式） |
| S2: 中断恢复 | `state.yaml` + 非 `ALL_DONE` | 从断点恢复 |
| S3: 旧版项目 | 有 `1.需求文档.md`（旧版） | 目录迁移 → S1 |
| S4: 纳管已有项目 | 有代码无 `开发手册/` | 代码库扫描 → 初始化 → PM |

### 工作流 B：开发 RedCap 自身

这是 RedCap 框架的**自身维护流程** — 不走 Dispatcher，由 AI Agent 直接编辑框架文件。

```
开发者/AI Agent 提出变更
   │
   ▼
┌────────────────────── 框架自身变更流程 ──────────────────────┐
│                                                               │
│  1. 读 CONTRIBUTING.md — 获取完整规范                         │
│  2. 读 knowledge/lessons.md — 检查已知陷阱                    │
│  3. 执行变更                                                  │
│  4. 检查影响范围 — CONTRIBUTING.md §5 联动表                  │
│  5. 经验沉淀自检 — 是否有新 Lesson？                         │
│  6. git commit（Conventional Commit 中文格式）                │
│  7. 飞书通知（自动/宿主 Hook）                                │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ 宿主 Hook（Layer 0）自动保障                             │  │
│  │ • Kimi CLI: SessionStart 捕获 HEAD → Stop 飞书通知      │  │
│  │ • Claude Code: InstructionsLoaded → Stop 飞书通知        │  │
│  │ • VS Code / Gemini: 无 Hook，依赖 Agent 自觉 + 启动审计 │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                               │
│  ⚠ 此处为 Layer B（开发 RedCap 自身）的 Hook。               │
│    Layer A（RedCap 开发用户项目）已实现用户级 Stop hook  │
│    （三重过滤防误触发），部署详见 knowledge/layerA-hook-deploy.md。│
│    两层架构详见 knowledge/host-reliability.md §0。            │
└───────────────────────────────────────────────────────────────┘
```

**关键文件**：

| 文件 | 角色 |
|------|------|
| `CONTRIBUTING.md` | 唯一权威规范（commit 格式、飞书通知、影响范围） |
| `CLAUDE.md` / `GEMINI.md` / `.github/copilot-instructions.md` | 索引文件，`@` 导入 CONTRIBUTING.md |
| `knowledge/lessons.md` | 13 条已知陷阱，变更前必读 |

---

## 系统设计详解

### 状态机（FSM）

```
                              ┌──────────────────────────────────────────────┐
                              │                正向流程                        │
                              │                                              │
  INIT ──→ PM_WORKING ──→ PM_DONE ──→ ARCH_WORKING ──→ ARCH_DONE           │
                                                                    │        │
           ┌────────────────────────────────────────────────────────┘        │
           │                                                                 │
           ▼                                                                 │
  DEV_WORKING ──→ DEV_DONE ──→ QA_WORKING                                  │
                                     │                                       │
                      ┌──────────────┼──────────────┐                        │
                      │              │              │                        │
                      ▼              ▼              ▼                        │
                  QA_PASS       QA_FAIL        QA_FAIL                      │
                      │              │              │                        │
                      │       ┌──────┘              │                        │
                      │       │                     │                        │
                      │       ▼                     ▼                        │
                      │  root=code         root=design                      │
                      │  → DEV_WORKING    → ARCH_WORKING                    │
                      │                                                      │
                      │  root=requirement → PM_WORKING                      │
                      │                                                      │
              ┌───────┴───────┐                                              │
              │               │                                              │
       has_next_step   no_next_step                                          │
              │               │                                              │
              ▼               ▼                                              │
       ARCH_WORKING    REVIEW_WORKING ──→ REVIEW_PASS ──→ ALL_DONE         │
                              │                                              │
                        REVIEW_FAIL                                          │
                       root=code → DEV_WORKING                              │
                       root=design → ARCH_WORKING                           │
                              │                                              │
                              └──────────────────────────────────────────────┘

  特殊状态：
  ┌──────────────────────────────────────────┐
  │ PAUSED — 等待用户（飞书/终端）            │
  │ SCAN_WORKING/SCAN_DONE — 迭代代码库扫描  │
  └──────────────────────────────────────────┘
```

**事件来源**：Agent 返回 `__redcap_status` JSON，Dispatcher 提取 `status` 字段驱动状态转移。

| status | 含义 |
|--------|------|
| `completed` | 正常完成 → 推进到下一角色 |
| `failed` | 执行失败 → 重试或升级 |
| `blocked` | 需要升级决策 → L1(PM Agent) / L2(用户) |
| `need_user` | 需要用户信息 → PAUSED |
| `need_revision` | 需要上游修订 → 按 root_cause 回退 |

### Dispatcher 执行协议

Dispatcher 的核心是一个**事件循环**，每轮执行：

```
┌──────────────────────────────────────────────────────────────────┐
│  0. 防退化重载（按 reload-rules.yaml 刷新关键规范到上下文）        │
│  1. 读 state.yaml + 执行 pending_actions                        │
│  2. ALL_DONE? → 触发 on_ALL_DONE → 结束                         │
│  3. PAUSED?   → 飞书 ask / 终端等待 → 注入回复 → 恢复           │
│  4. *_DONE?   → 查转移表 → 更新 state                           │
│  5. *_WORKING? →                                                 │
│     a. 选 Agent CLI（首选 → Fallback）                           │
│     b. 组装 Prompt（模板 + 变量映射 → 写入文件）                  │
│     c. 获取/创建 Session                                         │
│     d. 执行 CLI（阻塞等待）                                      │
│     e. 解析 __redcap_status                                      │
│     f. 写入 last-result.json                                     │
│     g. 交付物完整性校验                                           │
│     h. 触发 Hooks（on_QA_PASS / on_need_revision / ...）         │
│     i. 更新 state.yaml（+ pending_actions 原子写入）             │
│     j. 向用户汇报进展                                            │
│  6. → 回到 0                                                     │
└──────────────────────────────────────────────────────────────────┘
```

### 可靠性工程

RedCap 面对的核心挑战：**LLM 在长对话中的 attention 衰减导致指令遵从率下降**。

```
指令遵从率                       RedCap 四层防御
   ↑                             ┌─────────────────────────────────────┐
95%│████                         │ Layer 0: 宿主 Hooks（100%确定性）    │
   │   ████                      │   绕过 LLM，OS 级 shell 执行         │
85%│       ████                  │                                     │
   │          ████               │ Layer 1: 系统级指令（每轮重注入）     │
70%│             ████            │   copilot-instructions.md / CLAUDE   │
   │                ████         │                                     │
60%│                   ████      │ Layer 2: SKILL.md hooks（概率性）     │
   │                      ████  │   受 attention 衰减影响               │
   └─────────────────────────→  │                                     │
   1   5   10   15   20   30    │ Layer 3: 下次启动审计（~100%）        │
       对话轮数                  │   新会话 attention 最强               │
                                 └─────────────────────────────────────┘
```

**三大防护机制**：

| 机制 | 解决什么 | 实现 |
|------|---------|------|
| **常驻规范重载**（§5.12） | 规则退化 | 角色切换时 `read_file` 刷新关键段落 |
| **Pending Actions**（§5.13） | 动作遗忘 | 状态转移时原子写入待办清单到 state.yaml |
| **宿主 Hooks**（Layer 0） | 关键动作（飞书通知等） | 绕过 LLM，由宿主程序确定性执行 shell 脚本 |

详见 [knowledge/host-reliability.md](knowledge/host-reliability.md) 及 4 个宿主工具独立文档。

---

## 项目结构

```
redcap/
├── SKILL.md                       ← 核心：触发入口 + Dispatcher 完整执行协议
├── CONTRIBUTING.md                ← 框架自身开发的唯一权威规范
├── CLAUDE.md                      ← Claude Code 索引（@import CONTRIBUTING.md）
├── GEMINI.md                      ← Gemini CLI 索引（@import CONTRIBUTING.md）
├── .github/copilot-instructions.md← VS Code Copilot 索引
├── .claude/settings.json          ← Claude Code Hooks 配置
│
├── dispatcher/                    ← Dispatcher 详细规范
│   ├── state-machine.md           ← 状态机完整定义 + 伪代码
│   ├── agent-adapters.md          ← Agent CLI 调用规范（参数、超时、环境）
│   ├── reload-rules.yaml          ← 防退化重载检查点配置
│   └── prompt-templates/          ← 各角色 Prompt 模板
│       ├── pm-prompt.md
│       ├── architect-prompt.md
│       ├── programmer-prompt.md
│       ├── qa-prompt.md
│       └── reviewer-prompt.md
│
├── roles/                         ← 角色手册 + 文档模板
│   ├── product-manager/
│   │   └── handbook.md            ← PM 角色行为手册
│   ├── architect/
│   │   ├── handbook.md
│   │   └── templates/             ← 设计文档模板
│   ├── programmer/
│   │   └── templates/             ← README、代码等模板
│   ├── qa/
│   │   └── templates/             ← 测试用例模板
│   └── reviewer/
│
├── references/                    ← 全局规范（Agent 通过 Prompt 注入）
│   ├── security-rules.md          ← 安全铁律
│   ├── code-standards.md          ← 代码规范
│   ├── commit-standards.md        ← Git commit 规范
│   ├── communication-protocol.md  ← __redcap_status 通信协议
│   └── agent-constraints.md       ← 子 Agent 共享约束（防退化等）
│
├── knowledge/                     ← 经验库 + 调研报告
│   ├── lessons.md                 ← 13 条框架级经验（L-1 ~ L-13）
│   ├── lessons-archive.md         ← 归档的低活跃经验
│   ├── host-reliability.md        ← 宿主可靠性调研总览
│   ├── hooks-vscode-copilot.md    ← VS Code Copilot hooks 详情
│   ├── hooks-claude-code.md       ← Claude Code hooks 详情
│   ├── hooks-gemini-cli.md        ← Gemini CLI hooks 详情
│   ├── hooks-kimi-cli.md          ← Kimi CLI hooks + Dispatcher 协议
│   └── layerA-hook-deploy.md      ← Layer A 用户级 Hook 部署指南
│
└── tools/                         ← 可执行脚本
    ├── feishu-notifier.py         ← 飞书通知（notify/ask/resume/confirm）
    ├── redcap-on-complete.sh      ← on_ALL_DONE 收尾脚本
    ├── redcap-on-qa-pass.sh       ← on_QA_PASS 提交脚本
    ├── kimi-hook-handler.sh       ← Kimi CLI 宿主 Hook 处理器
    ├── redcap-claude-hook-init.sh ← Claude Code InstructionsLoaded Hook
    ├── redcap-claude-hook-stop.sh ← Claude Code Stop Hook（Layer B）
    ├── redcap-layerA-session-start.sh ← Layer A SessionStart Hook
    ├── redcap-layerA-stop.sh      ← Layer A Stop Hook（三重过滤）
    └── redcap-layerA-session-end.sh   ← Layer A SessionEnd Hook
```

---

## 文件职责矩阵

| 文件 | 读者 | 写者 | 何时读 |
|------|------|------|--------|
| `SKILL.md` | Dispatcher（宿主 LLM） | 人/AI 框架开发者 | Skill 触发时一次性加载 |
| `CONTRIBUTING.md` | 编辑 RedCap 的 AI Agent | 人 | 每次框架变更前 |
| `dispatcher/state-machine.md` | Dispatcher | 人/AI 框架开发者 | 需要状态转移细节时 |
| `dispatcher/agent-adapters.md` | Dispatcher | 人/AI 框架开发者 | 调用 Agent CLI 时 |
| `dispatcher/prompt-templates/*.md` | Dispatcher | 人/AI 框架开发者 | 组装 Prompt 时 |
| `roles/*/handbook.md` | 各角色 Agent（通过 Prompt 注入） | 人/AI 框架开发者 | Agent 启动时 |
| `references/*.md` | 所有 Agent（通过 Prompt 注入） | 人/AI 框架开发者 | Agent 启动时 |
| `knowledge/lessons.md` | Dispatcher + 框架开发者 | Dispatcher（自动沉淀） | 每次启动 + 变更前 |
| `tools/*.sh` | 宿主程序 / Dispatcher | 人/AI 框架开发者 | Hook 触发时 / 状态转移时 |

---

## 快速上手

### 前提

- 至少安装一个 AI CLI 工具（[Kimi CLI](https://github.com/MoonshotAI/kimi-cli)、[Claude Code](https://docs.anthropic.com/en/docs/claude-code)、[Gemini CLI](https://github.com/google-gemini/gemini-cli) 之一）
- 宿主 AI Agent 环境（VS Code Copilot / Claude Code / Gemini CLI / Kimi CLI）

### 触发方式

在宿主 AI Agent 中直接说开发需求即可：

```
"帮我开发一个任务管理系统"
"给现有项目增加支付功能"
"修复用户登录超时的 bug"
```

RedCap 作为 Skill 自动触发，接管后续全流程。

### 飞书集成（可选）

```bash
# 在项目根目录执行
python3 tools/feishu-notifier.py setup
```

配置后，流程完成自动发飞书通知，需要用户决策时飞书提问并等待回复。

### 典型成本参考

| 项目规模 | 轮次 | Token 消耗 | 预估成本 |
|---------|------|-----------|----------|
| 小型（Todo List） | ~15 轮 | ~150K tokens | ~$0.5-1.5 |
| 中型（带认证的 REST API） | ~30 轮 | ~400K tokens | ~$2-5 |
| 大型（多模块全栈） | ~60 轮 | ~800K tokens | ~$5-15 |

> 以上为经验估算，实际成本取决于 Agent CLI 选择（Claude Code 较贵、Gemini/Kimi 较便宜）、模型版本、项目复杂度和 QA 回退次数。每次 Agent 调用的 token 消耗可通过 `cost_usd`（Claude）或 `total_tokens`（Gemini）字段追踪。

---

## 设计哲学

| 原则 | 实践 |
|------|------|
| **Dispatcher 不代劳** | 铁律：未经用户授权不修改项目源代码，所有 Agent 不可用时暂停而非代劳 |
| **状态持久化** | 所有流程状态写入 `state.yaml`，中断后可从断点恢复 |
| **单一信源** | 一个事实只在一个地方维护（如 CONTRIBUTING.md 是唯一规范，其他文件 @import） |
| **确定性优于概率性** | 关键动作封装为 shell 脚本 + 宿主 Hooks，不依赖 LLM 记忆 |
| **经验沉淀** | 每次遇到新坑自动归档到 lessons.md，防止踩同样的坑 |
| **渐进式降级** | 3 级 Fallback 路由 + 用户授权降级，而非硬失败 |

### 常见架构疑问

**Q: DEV/QA Agent 真的会执行测试吗？会不会"幻觉自测"？**

Agent 通过宿主 Shell **真实执行**命令（curl、pytest、npm test 等），不是模拟或想象。具体机制：
- Gemini 配置 `--sandbox false`，Claude Code 配置 `--permission-mode bypassPermissions`，均直接操作宿主环境
- QA 手册要求记录**完整请求命令 + 实际返回值**作为测试证据（非自述式"测试通过"）
- GUI 等无法自动化的场景通过 `need_user` 升级给用户人工验证
- ⚠️ **非沙箱隔离**：Agent 在用户本地终端执行，与 AutoGPT、Claude Code 等 CLI 工具的安全模型一致

**Q: 面对大项目，上下文不会爆吗？为什么不用 RAG？**

RedCap 通过**架构层面**而非基础设施解决上下文问题，这是有意的设计选择：
- **分步设计**：架构师将需求拆为 N 步，每步只处理一个模块，天然限制单次上下文需求
- **按需读取**：Agent 通过 `read_file` 按需加载文件，不全量注入代码库
- **Agent CLI 自身能力**：Claude Code 内置 codebase indexing、Gemini 有 repo map，代码检索是 Agent 层的职责
- **检查点重载**（§3.2）：对抗规范退化，仅重读关键段落（~500 tokens/次）

不在 Dispatcher 层引入 RAG/AST，是因为这与 Agent CLI 自身的代码索引能力重复，且违反"高内聚低耦合"——Dispatcher 管状态流转，Agent 管代码理解。

---

## 作为 AI Agent 设计参考

RedCap 的设计模式可以作为小型多 Agent 系统的参考蓝图。以下是可复用的设计要素：

### 1. 架构模式：Dispatcher + Worker Agents

```
┌──────────┐      CLI 调用       ┌──────────┐
│Dispatcher│ ──────────────────→ │  Agent   │
│(编排层)  │ ←────────────────── │(执行层)  │
│          │   __redcap_status   │          │
└──────────┘      JSON 返回      └──────────┘
```

- Dispatcher 不执行业务逻辑，只做**调度、校验、状态管理**
- Agent 通过标准化 JSON 协议返回结果，与 Dispatcher 解耦
- 可复用模式：任何需要多步骤、多角色协作的 AI 任务

#### 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 通信方式 | CLI 调用（非 API/消息队列） | Agent CLI 是最普遍的交互形式，零部署成本。消息队列引入额外基础设施 |
| Agent 状态 | 无状态（每次调用独立） | 降低耦合。状态由 Dispatcher 的 `state.yaml` 统一管理，Agent 不持有流程状态 |
| Agent 标识 | `{cli}&{model}` 双维度 | CLI 与模型独立演进（如 claude-code 底层可换 Kimi/Claude），路由基于能力而非工具名 |
| Fallback 策略 | 3 级深度 + 新步骤重置 | 连续 2 次失败才切换（防偶发），新步骤自动重置失败计数（允许恢复） |

#### 架构阅读路径

| 顺序 | 文件 | 内容 | 阅读时间 |
|------|------|------|---------|
| 1 | 本 README "核心架构" 章节 | 总览图 + 三件事 | 已读 |
| 2 | `dispatcher/agent-adapters.md` | CLI 调用规范、路由表、Fallback 策略、模型检测 | ~8 min |
| 3 | `SKILL.md` §5.4-5.5 | 路由逻辑 + Fallback 伪代码 | ~5 min |
| 4 | `knowledge/lessons.md` L-4, L-5, L-6 | Agent 路由相关经验教训 | ~3 min |

---

### 2. 状态机驱动

#### 核心设计

```
21 个状态  ×  5 种事件  →  状态转移表

状态: INIT, PM_WORKING, PM_DONE, ARCH_WORKING, ARCH_DONE,
      DEV_WORKING, DEV_DONE, QA_WORKING, QA_PASS, QA_FAIL,
      REVIEW_WORKING, REVIEW_PASS, ALL_DONE, PAUSED,
      SCAN_WORKING, SCAN_DONE, ESCALATE_L1, ESCALATE_L2 ...

事件: completed | failed | blocked | need_user | need_revision
```

- **YAML 定义**：状态 + 转移规则存储在文件中，不硬编码 → 流程变更只改配置
- **文件持久化**：所有状态写入 `state.yaml`，进程崩溃/会话中断后可从断点恢复
- **Hooks 与转移分离**：状态转移决定"去哪"，Hooks 决定"还要做什么"（如 git commit、飞书通知）
- **QA 回退三分法**：`root_cause=code` → DEV、`design` → ARCH、`requirement` → PM，精准回退而非盲目重启
- **级联升级**：Agent blocked → L1（PM 决策） → L2（用户决策），分层避免不必要的用户打扰

#### 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 持久化方式 | YAML 文件（非数据库） | 单文件部署、零依赖、Git 可追踪、Agent 可直接读写 |
| 回退策略 | 按 root_cause 三分类 | 不同根因需不同角色修复，盲目回退浪费资源 |
| 升级机制 | L1(PM) → L2(用户) 分级 | L1 由 PM Agent 自主决策（业务范围），L2 需用户介入（超出 PM 权限） |

#### 状态机阅读路径

| 顺序 | 文件 | 内容 | 阅读时间 |
|------|------|------|---------|
| 1 | 本 README "状态机（FSM）" 章节 | 完整 ASCII 状态图 + 事件表 | 已读 |
| 2 | `dispatcher/state-machine.md` | 完整状态转移表 + 伪代码 + pending_actions 映射 | ~10 min |
| 3 | `references/communication-protocol.md` | `__redcap_status` JSON schema + 事件定义 | ~5 min |
| 4 | `SKILL.md` §5.2-5.3 | 事件循环中的状态解析逻辑 | ~5 min |

---

### 3. 可靠性三件套（核心创新）

RedCap 面对的核心挑战：**LLM 在长对话中的 attention 衰减导致指令遵从率下降**。三件套分别解决三个不同维度的遗忘问题。

| 机制 | 解决什么 | 核心原理 | 详见 |
|----|---------|---------|------|
| **宿主 Hooks** | 关键动作遗漏 | 绕过 LLM，OS 级确定性执行 | §3.1 |
| **规则防退化** | 约束规则被压缩遗忘 | 检查点 `read_file` 强制刷新上下文 | §3.2 |
| **Pending Actions** | 待办动作被遗忘 | 原子写入 state.yaml，外部持久化 | §3.3 |

### 3.1 Hook 机制深度解读

RedCap 的 Hook 体系是整个可靠性工程的核心。**核心洞察**：LLM 指令注入 ≠ 执行保证（详见 L-12），唯一 100% 确定性的是绕过 LLM 的宿主 Hooks。

#### 问题模型

```
指令遵从率
   ↑
95%│████
   │   ████
85%│       ████          ← RedCap 完整流程通常 20-40 轮
   │          ████         恰好在遵从率显著下降的区间
70%│             ████
   │                ████
60%│                   ████
   └─────────────────────────→
   1   5   10   15   20   30
       对话轮数
```

#### 四层防御架构

| 层 | 机制 | 可靠性 | 实现方式 |
|----|------|--------|---------|
| **Layer 0** | 宿主 Hooks（OS 级 shell） | **100%** | 绕过 LLM，宿主程序直接执行 |
| **Layer 1** | 系统级指令（每轮重注入） | ~30-50% 补救 | copilot-instructions.md / CLAUDE.md |
| **Layer 2** | SKILL.md hooks 表 | ~60-70% | 依赖 LLM attention（会衰减） |
| **Layer 3** | 下次启动审计 | ~95-100% | 新会话 attention 最强 |

#### 两层 Hook 架构（Layer A / Layer B）

RedCap 既是开发工具，也是被开发的对象，因此 Hook 分两层：

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer A — RedCap 开发用户项目                                     │
│                                                                   │
│ 部署位置: ~/.claude/settings.json（用户级，所有项目生效）          │
│ 核心挑战: cwd 在目标项目，但脚本在 RedCap repo                    │
│ 解决方案: 用户级全局 Hook + state.yaml 存在性检测 + 三重过滤       │
│                                                                   │
│ SessionStart → 捕获 HEAD + 清理僵尸标记                           │
│ Stop         → state.yaml存在? → ALL_DONE? → 未通知? → on-complete│
│ SessionEnd   → 清理 session 标记                                  │
│                                                                   │
│ 三重过滤（防误触发）:                                              │
│  1. 开发手册/.workflow/state.yaml 存在 → 确认是 RedCap 项目       │
│  2. current_state == ALL_DONE → 确认流程已完成                    │
│  3. /tmp 标记文件去重 → 确认本 session 未通知过                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Layer B — 开发 RedCap 自身                                        │
│                                                                   │
│ 部署位置: .claude/settings.json（项目级，仅 RedCap repo 生效）    │
│ InstructionsLoaded → 捕获初始 HEAD                                │
│ Stop               → 检测新 commit → 飞书通知                     │
└─────────────────────────────────────────────────────────────────┘
```

#### 关键设计决策：脚本封装

将多步副作用封装为单一 shell 脚本（如 `redcap-on-complete.sh`），LLM 只需记住"调一个脚本"而非"记住 N 个步骤"。这降低了 LLM 记忆负担，是 Layer 0 + Layer 2 共用的提升手段。

#### Hook 阅读路径（推荐顺序）

| 顺序 | 文件 | 内容 | 阅读时间 |
|------|------|------|---------|
| 1 | `knowledge/host-reliability.md` §0-§3 | 总览：问题模型 + 四层防御 + 宿主对比 | ~5 min |
| 2 | `knowledge/hooks-claude-code.md` §2-§3 | Hook 能力详情 + RedCap 部署现状 | ~5 min |
| 3 | `tools/redcap-on-complete.sh` | 关键脚本封装示例（on_ALL_DONE） | ~3 min |
| 4 | `tools/redcap-layerA-stop.sh` | Layer A 三重过滤实现 | ~3 min |
| 5 | `knowledge/layerA-hook-deploy.md` | Layer A 部署指南 | ~3 min |
| 6 | `knowledge/lessons.md` L-9, L-12, L-14 | 相关经验教训 | ~3 min |

> 其他宿主工具的 Hook 详情：`hooks-kimi-cli.md`（Kimi CLI）、`hooks-vscode-copilot.md`、`hooks-gemini-cli.md`

### 3.2 规则防退化（检查点重载）

#### 问题模型

LLM 的上下文压缩（compact）会保留"有 hooks 机制"的**概念**但丢失**具体触发条件和动作细节**。结果：Dispatcher 知道"应该做收尾"但遗忘"具体做哪几步"。

```
   LLM 上下文                       压缩后
┌─────────────────┐           ┌─────────────────┐
│ §5.10 Hooks 表  │           │ "有 hooks 机制"  │
│ 12 行具体规则   │  compact  │  （概要 1 行）    │
│ §5.7 校验步骤   │ ────────→ │ "有校验步骤"     │
│ 8 行检查清单    │           │  （概要 1 行）    │
│ §5.5 路由表     │           │ "有路由表"       │
│ 优先级+Fallback │           │  （概要 1 行）    │
└─────────────────┘           └─────────────────┘
   ~28 行具体规则                ~3 行概要
```

#### 解决方案：检查点 `read_file`

在关键时刻通过 `read_file` 重新加载规范段落到上下文，强制刷新被压缩的规则。

```yaml
# dispatcher/reload-rules.yaml（配置式，可扩展）
checkpoints:
  on_role_switch:        # 角色切换时 — 主检查点
    - SKILL.md §5.10     # Hooks 表
    - SKILL.md §5.7      # 交付物校验
    - SKILL.md §5.5      # Fallback 路由
  before_commit:         # 提交前
    - references/commit-standards.md
  before_task_complete:  # 任务完成前
    - SKILL.md §5.10     # 确保不遗漏收尾
  on_paused:             # 暂停时
    - SKILL.md §5.11     # 飞书通知细节
```

**成本分析**：单次重读 ~500-1000 tokens。完整项目（10-20 轮）重载成本 ~2000-4000 tokens（约 $0.02），远低于规则退化导致的返工成本。

#### 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 重载频率 | 按检查点（非每轮） | 每轮重读累积成本过高；角色切换时规则最易失效，频率适中 |
| 重载范围 | 关键段落（非全文） | SKILL.md 800+ 行，仅重读约 200 行核心规则，省 token |
| 配置方式 | YAML 文件（非硬编码） | 新发现的退化风险点只需 YAML 新增条目，无需改代码 |

### 3.3 Pending Actions（待办持久化）

#### 问题模型

即使规则没退化（§3.2 保障），Dispatcher 仍可能在状态转移后遗忘后续动作。例如：更新了 `state=QA_PASS` 但忘了执行 git commit。这是**递归遗忘问题**——"防止遗忘的机制本身被遗忘"。

#### 解决方案：原子写入

```
状态转移发生时（步骤 5i）:
┌──────────────────────────────────────────────────────┐
│  state.yaml 单次写入（原子操作）:                      │
│                                                        │
│  current_state: QA_PASS          ← 状态更新           │
│  pending_actions:                 ← 待办清单           │
│    - type: run_script                                  │
│      command: bash tools/redcap-on-qa-pass.sh ...      │
│    - type: check_lesson                                │
│      hint: QA 通过，检查是否有新经验                     │
└──────────────────────────────────────────────────────┘
         │
         │  下轮事件循环步骤 1
         ▼
┌──────────────────────────────────────────────────────┐
│  遍历 pending_actions → 逐项执行 → 清空              │
│  （即使 Dispatcher 遗忘了"应该做什么"，               │
│    state.yaml 中的 pending_actions 强制提醒）          │
└──────────────────────────────────────────────────────┘
```

**⚠️ 原子写入铁律**：`pending_actions` 必须与 `current_state` 在**同一次 state.yaml 写入操作**中完成。禁止先写 state 再"记得"补写 pending_actions——这正是递归遗忘的根源。

#### 转移 → Actions 映射表

| 转移目标 / 事件 | 自动填充的 pending_actions |
|----------------|---------------------------|
| → `QA_PASS` | `run_script`（git commit） |
| → `ALL_DONE` | `run_script`（清理 + 摘要 + 飞书通知） |
| → `PAUSED` | `feishu_ask`（前台阻塞等待用户回复） |
| 事件 `need_revision` | `check_lesson`（经验检查） |
| → `ALL_AGENT_FAIL` | `feishu_ask`（降级确认） |
| QA 失败 > 3 次 | `feishu_ask`（循环失败警报） |

#### §3.2 与 §3.3 的互补关系

```
§3.2 防退化（规则层）         §3.3 Pending Actions（动作层）
┌─────────────────┐          ┌─────────────────────┐
│ 保护：静态约束   │          │ 保护：动态任务        │
│ "Dispatcher 应该 │          │ "Dispatcher 下一步    │
│  遵守什么规则"   │          │  具体要执行什么动作"  │
│                  │          │                      │
│ 机制：read_file  │          │ 机制：state.yaml      │
│  刷新上下文      │          │  外部持久化           │
└─────────────────┘          └─────────────────────┘
         │                            │
         └──── 互补，非替代 ──────────┘
```

#### 防退化阅读路径

| 顺序 | 文件 | 内容 | 阅读时间 |
|------|------|------|---------|
| 1 | `dispatcher/reload-rules.yaml` | 检查点配置（4 个检查点 × 重载段落） | ~3 min |
| 2 | `SKILL.md` §5.12 | 防退化机制执行逻辑 | ~3 min |
| 3 | `SKILL.md` §5.13 | Pending Actions 机制 + 映射表 | ~5 min |
| 4 | `dispatcher/state-machine.md` "populate_pending_actions" | 状态转移时的填充逻辑 | ~3 min |
| 5 | `knowledge/lessons.md` L-9 | 经验：长任务上下文压缩导致框架规则退化 | ~2 min |

### 4. 经验库模式（可复用）

#### 问题模型

AI Agent 在开发过程中不断踩坑，但**坑只在当前对话中存活**。新会话启动时，同样的坑会被再次踩中。RedCap 将经验持久化为结构化 Lesson，自动注入后续会话上下文。

#### 三层存储架构

```
lessons.md（活跃层，< 300 行）      ← 常驻 LLM 上下文，每次启动自动加载
       │
       │  score < 1.0 时自动归档
       ▼
lessons-archive.md（归档层）         ← 不自动加载，按需手动查阅
       │
       │  复现时复活
       ▼
lessons.md
```

**为什么三层而非一个文件？** 长期运营下 Lesson 会积累到百条级别。全部加载挤占上下文空间。活跃层始终精简（< 300 行），归档层保留但不占上下文。

#### 评分公式（自动化归档决策）

```
score = impact_weight × recency_decay × frequency_boost

impact_weight:   high=4, medium=2, low=1
recency_decay:   <6mo=1.0, 6-12mo=0.6, >12mo=0.3
frequency_boost: min(复现次数, 5) / 5 → [0.2, 1.0]

score ≥ 1.0 → 保留活跃层 | score < 1.0 → 归档
豁免：impact=high 永不自动归档（框架底线必须持续可见）
```

#### Lesson 标准格式

```markdown
### L-{序号}: {一句话标题}
- **场景**：触发场景描述
- **根因**：问题的根本原因
- **经验规则**：可复用的规范（什么情况下应/不应做什么）
- **影响度**：high / medium / low
- **复现次数**：整数（独立触发累计）
- **最后命中**：YYYY-MM
```

#### 消费方式

Dispatcher 组装 Prompt 时，将近期 5 条高相关 Lesson 注入 Agent 上下文。Agent 通过 `__redcap_status.lesson` 字段提交新发现的经验，Dispatcher 自动归档。

#### 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 归档决策 | 评分公式（非人工标记） | 量化决策降低维护负担；人工标记容易遗漏或过时 |
| 容量上限 | 300 行 | ~15-20 条 Lesson，在 LLM 上下文中成本可控且不挤占任务空间 |
| 分级 | 框架级 vs 项目级 | 框架级（跨项目通用）存 RedCap；项目级（特定业务）存各项目 `开发手册/` |
| high 豁免 | 永不自动归档 | 如 L-4（Fallback 深度不足导致铁律违反）是框架底线，必须始终可见 |

#### 经验库阅读路径

| 顺序 | 文件 | 内容 | 阅读时间 |
|------|------|------|---------|
| 1 | `knowledge/lessons.md` 前 40 行 | 归档策略 + 评分公式 + 字段说明 | ~3 min |
| 2 | `knowledge/lessons.md` L-4, L-9, L-12 | 高影响度经验示例 | ~5 min |
| 3 | `knowledge/lessons-archive.md` | 归档层格式参考 | ~2 min |
| 4 | `SKILL.md` §5.8 | 经验沉淀触发逻辑 | ~2 min |

---

### 5. 通信协议设计

#### 请求-响应序列

```
Dispatcher                              Agent (CLI)
    │                                       │
    │──── CLI 调用 + Prompt 文件 ──────────→│
    │                                       │
    │     （Agent 执行任务、写文件...）       │
    │                                       │
    │←── 自然语言回复 + __redcap_status ────│
    │                                       │
    │  提取 JSON ──→ 写入 last-result.json  │
    │  校验交付物 ──→ 触发 Hooks            │
    │  更新 state.yaml                      │
```

#### `__redcap_status` JSON Schema

```jsonc
{
  "status": "completed",           // 必填：completed|failed|blocked|need_user|need_revision
  "summary": "用户管理模块完成",    // 必填：一句话摘要
  "deliverables": [                // 必填：产出文件列表（Dispatcher 据此校验完整性）
    "dev/outbox/用户管理模块.md"
  ],
  "lesson": {                      // 可选：新发现的经验
    "title": "...", "scenario": "...", "rule": "..."
  },
  "escalation": {                  // 仅 blocked 时必填
    "level": "L1", "target_role": "pm", "question": "..."
  },
  "revision": {                    // 仅 need_revision 时必填
    "root_cause": "design",        // code→DEV | design→ARCH | requirement→PM
    "description": "接口设计缺少分页字段"
  }
}
```

#### 双轨传递策略

| 通道 | 机制 | 何时用 |
|------|------|--------|
| **方案 A（主通道）** | Agent 在回复末尾输出 `__redcap_status` JSON | 正常情况 |
| **方案 B（Fallback）** | Dispatcher 正则提取失败 → 读 `last-result.json` | Agent 输出格式异常 / 断点恢复 |

**为什么双轨？** 部分 Agent 难以稳定输出结构化 JSON。Fallback 通道确保即使 JSON 解析失败，Dispatcher 仍可从上次成功状态恢复。

#### 交付物协议

```
命名：{角色目录}/outbox/{步骤号}-{交付物名称}.md
规则：
  ✅ 必须自包含（下游无需回溯源角色草稿）
  ✅ 写入后锁定（除非被回退，源角色不应修改 outbox 文件）
  ✅ 文件头含步骤编号 + 生成时间 + 源角色标识
```

#### 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 协议嵌入方式 | 内嵌在自然语言回复中 | 无需修改 Agent CLI 传输层；`__redcap_status` 前缀避免与正文冲突 |
| last-result.json 写入方 | 仅 Dispatcher | 单一写入方防止状态错乱（Agent vs Dispatcher 概念不一致） |
| 交付物自包含 | 强制 | 分工制下下游无法回溯上游工作区，交付物必须完全独立 |
| 5 种 status | 最小完备集 | completed/failed 覆盖正常流；blocked/need_user 覆盖阻塞流；need_revision 覆盖回退流 |

#### 通信协议阅读路径

| 顺序 | 文件 | 内容 | 阅读时间 |
|------|------|------|---------|
| 1 | `references/communication-protocol.md` | 完整 JSON schema + 所有字段说明 + 交付物规范 | ~8 min |
| 2 | `dispatcher/agent-adapters.md` §返回值 | 各 CLI 的返回值提取差异 | ~3 min |
| 3 | `SKILL.md` §5.7 | 交付物完整性校验逻辑 | ~3 min |

---

### 6. 角色系统 + Prompt 模板

#### 设计理念

RedCap 将"什么角色做什么事"和"如何调度角色"完全分离：

```
┌─────────────────┐      ┌──────────────────┐      ┌────────────────┐
│ roles/           │      │ dispatcher/       │      │ references/     │
│ */handbook.md    │      │ prompt-templates/  │      │ *.md            │
│ 角色行为手册      │      │ *-prompt.md        │      │ 全局规范         │
│ "Agent 读什么"   │      │ "Dispatcher 怎么组" │      │ "所有人守什么"   │
└────────┬────────┘      └────────┬───────────┘      └────────┬───────┘
         │                        │                           │
         └──── Prompt 组装 ───────┘                           │
                    │                                         │
                    ▼                                         │
         ┌────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────┐
│ 最终 Prompt = System(角色身份 + 手册 + 规范)      │
│            + Task(场景模板 + 变量替换)            │
└──────────────────────────────────────────────────┘
```

#### 五个角色及其职责

| 角色 | 目录 | 核心职责 | 交付物 |
|------|------|---------|--------|
| **产品经理（PM）** | `roles/产品经理.md` | 意图澄清（苏格拉底提问法）→ 需求文档 | `pm/outbox/需求文档.md` |
| **架构师（ARCH）** | `roles/架构师.md` | 技术框架设计 → 分步模块设计 | `arch/outbox/分步设计索引.md` + 各步模块设计 |
| **程序员（DEV）** | `roles/程序员.md` | 按模块设计编码 + 自测 | 代码文件 + `dev/outbox/自测报告.md` |
| **测试 QA** | `roles/测试QA.md` | 验证代码 vs 设计 vs 需求 | `qa/outbox/测试报告.md` |
| **审查员（REVIEW）** | — | 最终交叉审查 | 审查报告 |

**为什么 5 个角色而非 3 个？** PM 和 ARCH 分离确保需求分析不被技术实现干扰；DEV 和 QA 分离确保测试独立性（自己测自己的代码发现不了设计层面的问题）；REVIEW 作为最终门禁交叉检查。

#### Prompt 组装流程

```
Dispatcher 事件循环 步骤 5b:
                                                     ┌─────────────────────┐
                                                     │ dispatcher/          │
state.yaml ──→ 确定角色 ──→ 选择模板 ──→ 填充变量 ──→│ prompt-templates/    │
                                                     │ {role}-prompt.md     │
                                                     └─────────┬───────────┘
                                                               │
                              变量映射表                        │
                  ┌─────────────────────────────┐              │
                  │ {{handbook_content}}         │              │
                  │   → roles/{role}/handbook.md │              │
                  │ {{user_intent}}              │              │
                  │   → state.yaml.user_intent   │              │
                  │ {{project_dir}}              │              │
                  │   → 项目绝对路径              │              │
                  │ {{iteration_mode}}           │              │
                  │   → new / iterate / onboard  │              │
                  │ {{existing_context}}         │              │
                  │   → 已有代码/文档上下文       │              │
                  │ {{revision_description}}     │              │
                  │   → 回退时的修订说明          │              │
                  └─────────────────────────────┘              │
                                                               ▼
                                                     最终 Prompt 文件
                                                     写入 .workflow/
```

#### 多场景模板变种

每个角色的 Prompt 模板包含多个场景变种（而非一个通用模板）：

| 场景 | PM | ARCH | DEV | QA |
|------|-----|------|-----|-----|
| 新需求 | ✅ | ✅ | ✅ | ✅ |
| 恢复 Session | ✅ | ✅ | ✅ | ✅ |
| 回退修订 | ✅ | ✅ | ✅ | — |
| 迭代增量 | ✅ | ✅ | — | — |

**为什么分场景而非通用？** 新需求、恢复、回退的约束完全不同。通用模板导致指示模糊，Agent 容易混淆场景边界。

#### 角色手册 vs Prompt 模板

| 维度 | 角色手册（`roles/*/handbook.md`） | Prompt 模板（`dispatcher/prompt-templates/`） |
|------|----------------------------------|----------------------------------------------|
| **读者** | Agent（作为 System Prompt 注入） | Dispatcher（组装时参考） |
| **内容** | 工作流程、检查点、交付物格式 | 变量占位符、场景路由、必写文件清单 |
| **修改频率** | 低（角色行为稳定） | 中（随流程优化调整） |
| **职责** | 定义"做什么" | 定义"怎么组装 + 怎么校验" |

#### 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 手册注入方式 | System Prompt 注入（非 Task） | 全对话周期生效，中断恢复时继承。Task 中放场景相关内容 |
| 必写文件 checklist | 硬写在模板末尾 | L-2 经验：Agent 容易遗漏文件。Prompt 末尾 checklist 确保校验依据 |
| 交付物双份 | 正本（角色目录）+ 副本（outbox） | 正本可迭代修改，副本锁定供下游消费。分离工作区和交付区 |

#### 角色系统阅读路径

| 顺序 | 文件 | 内容 | 阅读时间 |
|------|------|------|---------|
| 1 | `roles/产品经理.md` | PM 手册示例（苏格拉底澄清 + 双模式需求文档） | ~5 min |
| 2 | `dispatcher/prompt-templates/pm-prompt.md` | PM 模板示例（变量映射 + 3 场景变种） | ~5 min |
| 3 | `roles/架构师.md` | ARCH 手册（分步设计 + 逐步推进策略） | ~5 min |
| 4 | `references/agent-constraints.md` | 所有 Agent 共享的行为约束 | ~3 min |
| 5 | `references/security-rules.md` | 安全铁律（注入 Agent Prompt 的硬性规则） | ~3 min |
| 6 | `SKILL.md` §5.6 | Session 管理 + Prompt 组装伪代码 | ~3 min |

---

### 总览：完整阅读路径

如果你想**复刻一个类似 RedCap 的多 Agent 系统**，推荐按以下顺序阅读：

| 阶段 | 目标 | 推荐阅读 | 预估时间 |
|------|------|---------|---------|
| **1. 理解全貌** | 知道 RedCap 是什么、为什么 | 本 README（全文） | ~15 min |
| **2. 状态机骨架** | 理解流程如何流转 | `dispatcher/state-machine.md` | ~10 min |
| **3. 通信协议** | 理解 Agent 如何与 Dispatcher 交互 | `references/communication-protocol.md` | ~8 min |
| **4. 角色设计** | 理解角色如何分工 | `roles/产品经理.md` + `roles/架构师.md` | ~10 min |
| **5. Prompt 工程** | 理解如何组装 Agent Prompt | 任一 `prompt-templates/*.md` | ~5 min |
| **6. 可靠性工程** | 理解防遗忘三件套 | `knowledge/host-reliability.md` + `dispatcher/reload-rules.yaml` | ~10 min |
| **7. Agent 适配** | 理解多 CLI 适配 + Fallback | `dispatcher/agent-adapters.md` | ~8 min |
| **8. 经验库** | 理解经验沉淀机制 | `knowledge/lessons.md` | ~5 min |
| **9. 完整执行协议** | 理解 Dispatcher 事件循环全貌 | `SKILL.md` §5（核心） | ~20 min |

> 总计约 **90 分钟**可完整理解 RedCap 全貌，足以复刻一个同等水平的多 Agent 协同系统。

---

> **RedCap 本身也是由 AI Agent 开发和维护的** — 它使用自己定义的工作流 B 来迭代自身，是一个自举系统。
