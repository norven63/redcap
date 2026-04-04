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
- [作为 AI Agent 设计参考](#作为-ai-agent-设计参考)

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
└───────────────────────────────────────────────────────────────┘
```

**关键文件**：

| 文件 | 角色 |
|------|------|
| `CONTRIBUTING.md` | 唯一权威规范（commit 格式、飞书通知、影响范围） |
| `CLAUDE.md` / `GEMINI.md` / `.github/copilot-instructions.md` | 索引文件，`@` 导入 CONTRIBUTING.md |
| `knowledge/lessons.md` | 12 条已知陷阱，变更前必读 |

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
│   ├── lessons.md                 ← 12 条框架级经验（L-1 ~ L-12）
│   ├── lessons-archive.md         ← 归档的低活跃经验
│   ├── host-reliability.md        ← 宿主可靠性调研总览
│   ├── hooks-vscode-copilot.md    ← VS Code Copilot hooks 详情
│   ├── hooks-claude-code.md       ← Claude Code hooks 详情
│   ├── hooks-gemini-cli.md        ← Gemini CLI hooks 详情
│   └── hooks-kimi-cli.md          ← Kimi CLI hooks + Dispatcher 协议
│
└── tools/                         ← 可执行脚本
    ├── feishu-notifier.py         ← 飞书通知（notify/ask/resume/confirm）
    ├── redcap-on-complete.sh      ← on_ALL_DONE 收尾脚本
    ├── redcap-on-qa-pass.sh       ← on_QA_PASS 提交脚本
    ├── kimi-hook-handler.sh       ← Kimi CLI 宿主 Hook 处理器
    ├── redcap-claude-hook-init.sh ← Claude Code InstructionsLoaded Hook
    └── redcap-claude-hook-stop.sh ← Claude Code Stop Hook
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

### 2. 状态机驱动（可复用）

- 用 YAML 定义状态 + 转移规则，不硬编码在代码中
- 状态持久化到文件，支持中断恢复
- Hooks 与状态转移分离 — 转移决定"去哪"，Hooks 决定"还要做什么"

### 3. 可靠性三件套（核心创新）

| 层 | 机制 | 适用场景 |
|----|------|---------|
| 确定性执行 | 宿主 Hooks + shell 脚本封装 | 任何不能遗漏的关键步骤 |
| 规则防退化 | 检查点重载（`read_file` 刷新上下文） | LLM 长对话场景 |
| 动作防遗忘 | Pending Actions（待办写入持久化存储） | 多步骤任务的跨轮次连续性 |

### 4. 经验库模式（可复用）

```
发现问题 → 格式化为 Lesson（场景/根因/规则）
         → 归档到 lessons.md
         → 下次启动时自动注入上下文
         → 评分+容量管理防止膨胀
```

### 5. 通信协议设计（可复用）

Agent 返回固定 JSON schema（`__redcap_status`），包含：
- `status` — 事件类型（completed/failed/blocked/need_user/need_revision）
- `summary` — 一句话摘要
- `deliverables` — 产出文件列表（可校验）
- `lesson` — 可选经验沉淀
- `revision` — 回退信息（root_cause + description）

这种"结构化返回 + Dispatcher 解析"的模式可以应用于任何多 Agent 系统。

---

> **RedCap 本身也是由 AI Agent 开发和维护的** — 它使用自己定义的工作流 B 来迭代自身，是一个自举系统。
