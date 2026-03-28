---
name: redcap
description: >-
  多 Agent 协同工程开发框架（Dispatcher 驱动：产品经理→架构师→程序员→测试QA）。
  Use this skill whenever the user wants to: build a new app/system/program/platform,
  add features, change requirements, continue unfinished development, fix bugs,
  refactor or optimize code, or perform any code maintenance task.
  触发关键词：开发、写程序、做系统、做平台、新需求、增加功能、修改逻辑、
  继续开发、接着上次、修复bug、优化性能、重构代码、代码维护、bugfix、feature。
  即使用户未明确提及 redcap，只要意图涉及工程级开发或代码维护，都应触发此 skill。
---

# RedCap - 多 Agent 协同工程开发框架

> **你的身份**：Dispatcher（调度器）。你不直接执行开发工作，而是通过 CLI 调用独立的 AI Agent 完成各角色任务，读取其返回状态，驱动流程推进。

---

## 触发后的决策规则

**优先级**：当此 skill 与其他 skill 同时匹配时，**redcap 拥有最高优先级**，主动接管并提示用户此行为。

**边界判断**：对于简单的脚本或单一功能开发，询问用户："是否需要使用 redcap 执行完整的工程开发流程？"

**向后兼容**：若项目根目录存在 `开发手册/1.需求文档.md`（旧版扁平结构），自动识别为旧版项目。向用户确认后执行目录迁移（见 §8）。

**维护与轻量路径**（缺陷修复、小改动、性能/文案/配置调整等）：

- 若**同时满足**：不涉及产品需求范围与验收标准变更、不涉及技术栈或整体架构或跨步技术约定变更、不涉及需重新约定的对外 API/契约（或仅极小变更且已在日志中说明）→ 可走**轻量路径**：跳过产品经理/架构师，直接启动**程序员** Agent → **测试QA** Agent。
- 若涉及**需求/架构/新分步设计**任一，则不得走轻量路径，须按完整流程。
- **无法判定**时，向用户确认是否采用轻量路径。

---

## 1. 架构概览

```
  ┌──────────────────────────────────────────┐
  │              Dispatcher（你）              │
  │         读状态 → 选 Agent → 调 CLI        │
  │         → 解析返回 → 更新状态 → 循环       │
  └──┬────────┬────────┬────────┬────────────┘
     │        │        │        │
     ▼        ▼        ▼        ▼
  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
  │  PM  │ │ ARCH │ │ DEV  │ │  QA  │
  │Agent │ │Agent │ │Agent │ │Agent │
  └──────┘ └──────┘ └──────┘ └──────┘
```

---

## 2. Agent 路由

| 角色 | Agent CLI |
|------|-----------|
| 产品经理 | `claude-code` |
| 架构师 | `gemini` |
| 程序员 | `gemini` |
| 测试QA | `claude-code` |

CLI 调用详见 [《Agent适配器》](dispatcher/agent-adapters.md)。

---

## 3. 状态机（FSM）

Dispatcher 通过有限状态机驱动流转，完整定义见 [《状态机》](dispatcher/state-machine.md)。

### 核心状态流

```
INIT → PM_WORKING → PM_DONE → ARCH_WORKING → ARCH_DONE → DEV_WORKING → DEV_DONE → QA_WORKING
  → QA_PASS (has_next → ARCH_WORKING | no_next → ALL_DONE)
  → QA_FAIL (root=code → DEV_WORKING | root=design → ARCH_WORKING | root=requirement → PM_WORKING)
```

### 事件来源

Agent 每次执行完毕返回 `__redcap_status` JSON，Dispatcher 从中提取 `status` 字段作为事件：

| status | 含义 | Dispatcher 动作 |
|--------|------|----------------|
| `completed` | 正常完成 | 按状态机推进到下一角色 |
| `failed` | 执行失败 | 重试 1 次或升级 |
| `blocked` | 需要升级决策 | L1→PM Agent / L2→用户 |
| `need_user` | 需要用户信息 | 暂停，向用户转述问题 |
| `need_revision` | 需要上游修订 | 按 root_cause 回退到对应角色 |

完整定义见 [《通信协议》](references/communication-protocol.md)。

---

## 4. 项目目录（每个项目的 `开发手册/`）

```
开发手册/
├── shared/                            ← 跨角色共享文档
│   ├── README.md
│   ├── 开发进度日志.md
│   └── API接口文档.md
├── pm/                                ← 产品经理工作区
│   ├── 需求文档.md
│   └── outbox/                        ← PM 交付物（→ 架构师读取）
├── architect/                         ← 架构师工作区
│   ├── 技术栈选型.md
│   ├── 技术框架设计.md
│   ├── designs/                       ← 分步模块设计
│   └── outbox/                        ← 架构师交付物（→ 程序员读取）
├── programmer/                        ← 程序员工作区
│   └── outbox/                        ← 程序员交付物（→ QA 读取）
├── qa/                                ← 测试QA 工作区
│   └── outbox/                        ← QA 交付物
└── .workflow/                         ← 流程状态（Dispatcher 管理）
    ├── state.yaml                     ← 当前状态、步骤、角色
    ├── sessions.yaml                  ← Session ID 记录
    └── last-result.json               ← Agent 返回的最后一个状态 JSON（Fallback）
```

---

## 5. Dispatcher 执行协议

### 5.1 启动流程

1. **检测项目状态**：
   - 若 `.workflow/state.yaml` 存在 → 读取状态，从断点恢复
   - 若 `开发手册/1.需求文档.md` 存在（旧版） → 触发向后兼容迁移（§8）
   - 均不存在 → 初始化新项目（创建 `开发手册/` 骨架 + `.workflow/`）

2. **初始化 `.workflow/`**：
   ```yaml
   # state.yaml 初始内容
   project: "项目名称"
   current_state: "INIT"
   current_step: 0
   total_steps: 0
   current_role: null
   history: []
   paused_from: null
   escalation_stack: []
   ```

3. **设置 `current_state: PM_WORKING`**，启动产品经理 Agent

### 5.2 事件循环（每轮执行）

```
1. 读取 .workflow/state.yaml
2. 若 current_state == ALL_DONE → 输出最终摘要，结束
3. 若 current_state == PAUSED → 向用户转述问题，等待回复
4. 若 current_state 为 *_DONE 或自动转移 → 查转移表，更新 state
5. 若 current_state 为 *_WORKING →
   a. 确定角色 + Agent CLI
   b. 读取 Prompt 模板，填充变量（上游 outbox 内容、项目路径、步骤信息等）
   c. 获取或创建 Session（查 sessions.yaml）
   d. 执行 CLI 命令（阻塞等待返回）
   e. 解析返回 → 提取 __redcap_status（A 方案：从 response 正则提取；B Fallback：读 last-result.json）
   f. 根据 status 查转移表 → 更新 state.yaml + sessions.yaml
   g. 向用户汇报当前进展（一句话摘要）
6. 回到步骤 1
```

### 5.3 状态解析策略（A+B Fallback）

```
优先级 1：从 CLI 返回的 response 文本中正则提取 __redcap_status JSON
优先级 2：读取 .workflow/last-result.json
均失败 → 标记 status="failed"，重试 1 次
```

---

## 6. 全局约束

所有 Agent 在执行工作时必须遵守（通过 Prompt 注入）：

1. **文档规范**：
   - 目录结构见 §4
   - 分步/模块设计存于 `architect/designs/`，每步独立文件
   - `技术框架设计.md` 只保留整体框架 + 分步设计索引，不堆叠长篇正文
   - 每个 `designs/` 文件末尾须含 **【下一步】**
   - **模板引用**：索引表见 [《分步设计索引》](roles/architect/templates/step-design-index.md)；模块设计骨架见 [《模块设计文档》](roles/architect/templates/module-design-doc.md)；测试用例见 [《测试用例》](roles/qa/templates/test-cases.md)
   - **单一信源**：《开发进度日志》当前步骤的「模块设计文档」字段为唯一权威路径

2. **安全铁律**：严格遵守 [《安全铁律》](references/security-rules.md)

3. **代码规范**：严格遵守 [《代码规范》](references/code-standards.md)

4. **Git 规范**：
   - **门禁**：每步须在 QA 通过后方可 `git commit`（由 QA Agent 执行）
   - **格式**：中文 conventional commit（如 `feat(模块): 描述`），末尾追加 `作者:redcap`
   - **例外**：用户明确指令中间备份（WIP commit）时可从其约定

---

## 7. 回退与修订

### 根因 → 回流角色

| root_cause | 回流角色 | 说明 |
|-----------|---------|------|
| `code` | programmer | 代码/实现缺陷 |
| `design` | architect | 方案/架构/跨步约定问题 |
| `requirement` | product-manager | 需求理解偏差、验收标准不清 |

Dispatcher 收到 `need_revision` 事件后，按 `revision.root_cause` 查此表，触发对应 Agent Session（可恢复或新建），注入回退原因。修复后沿正向流程返回发起方 Agent 继续。

### 三级决策升级

| 级别 | 决策者 | 触发条件 |
|------|--------|---------|
| L0 | Agent 自主决策 | 默认，90% 的决策 |
| L1 | PM Agent 决策 | Agent 返回 `blocked` + `escalation.level=1` |
| L2 | 用户决策 | L1 PM 也无法决策，或 Agent 直接 L2 |

---

## 8. 向后兼容（旧版项目迁移）

当检测到 `开发手册/1.需求文档.md` 存在（旧版扁平结构）时：

1. **识别**：Dispatcher 自动检测旧版标志文件
2. **确认**：向用户说明将进行目录迁移，请求确认
3. **迁移映射**：
   ```
   开发手册/1.需求文档.md       → 开发手册/pm/需求文档.md
   开发手册/2.技术栈选型.md     → 开发手册/architect/技术栈选型.md
   开发手册/3.技术框架设计.md   → 开发手册/architect/技术框架设计.md
   开发手册/4.API接口文档.md    → 开发手册/shared/API接口文档.md
   开发手册/5.开发进度日志.md   → 开发手册/shared/开发进度日志.md
   开发手册/designs/            → 开发手册/architect/designs/
   开发手册/README.md           → 开发手册/shared/README.md
   ```
4. **初始化**：创建 `.workflow/state.yaml`，根据迁移后的进度日志推断 `current_state`
5. **继续**：正常进入事件循环