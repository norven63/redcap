# RedCap 引擎升级方案 · 第二篇：执行框架

> **文档性质**：可执行的技术框架规范  
> **前置依赖**：[第一篇：设计思路](engine-upgrade-part1-design-philosophy.md)  
> **版本**：v1.0 Draft  
> **日期**：2026-03-28  

---

## 1. 目录结构

升级涉及两个层面的目录重构：RedCap 框架层（操作手册）和开发项目层（工作空间）。

### 1.1 RedCap 框架层

```
redcap/
├── SKILL.md                          # 入口：触发规则、Dispatcher 状态机、全局约束
│
├── references/                       # 所有角色共享的规范（只读引用，保持 Agent Skill 命名规范）
│   ├── security-rules.md              # 安全铁律
│   ├── code-standards.md              # 代码规范
│   └── communication-protocol.md      # 新增：交付物格式、状态码、升级信号定义
│
├── roles/                            # 各角色独立操作手册
│   ├── product-manager/
│   │   └── handbook.md                # 产品经理工作手册
│   │
│   ├── architect/
│   │   ├── handbook.md                # 架构师工作手册
│   │   └── templates/                 # 架构师专用模板（技术选型、分步设计等）
│   │
│   ├── programmer/
│   │   ├── handbook.md                # 程序员工作手册
│   │   └── templates/                 # 程序员专用模板（开发日志、README 等）
│   │
│   └── qa/
│       ├── handbook.md                # 测试QA 工作手册
│       └── templates/                 # QA 专用模板（测试用例等）
│
├── dispatcher/                       # Dispatcher 规则集（不是角色手册）
│   ├── state-machine.md              # 状态转移表完整定义
│   ├── agent-adapters.md             # 各 Agent CLI 的适配参数
│   └── prompt-templates/             # 启动各角色 Agent 时的 Prompt 模板
│       ├── pm-prompt.md
│       ├── architect-prompt.md
│       ├── programmer-prompt.md
│       └── qa-prompt.md
│
└── docs/                             # 方案文档（本文所在目录）
    ├── engine-upgrade-part1-design-philosophy.md
    └── engine-upgrade-part2-execution-framework.md
```

**与现有结构的变更要点**：

| 变更 | 旧结构 | 新结构 | 原因 |
|------|--------|--------|------|
| 角色手册目录化 | `roles/产品经理.md`（单文件） | `roles/product-manager/handbook.md` + `templates/` | 每个角色需要独立的模板空间 |
| 新增 Dispatcher 目录 | 无 | `dispatcher/` | 状态机规则、Agent 适配参数、Prompt 模板独立管理 |
| 新增通信协议 | 无 | `references/communication-protocol.md` | 定义角色间交付物格式和状态码标准 |

### 1.2 开发项目层

当 RedCap 被触发以为某个实际项目执行开发时，项目目录按以下结构组织：

```
project/                               # 实际开发项目根目录
├── src/                               # 源代码（程序员写，所有人可读）
├── tests/                             # 测试代码（QA 写，所有人可读）
├── ...                                # 项目自有的其他目录
│
├── .workflow/                         # 工作流状态（Dispatcher 管理）
│   ├── state.yaml                     # 当前流程状态
│   ├── sessions.yaml                  # Session ID 映射表
│   └── last-result.json               # Agent 最近一次返回的状态（Fallback 通道）
│
└── 开发手册/                           # 按角色隔离的工作空间
    ├── shared/                        # 共享交付物（所有角色可读）
    │   ├── README.md                  # 项目总览与当前进度
    │   ├── 开发进度日志.md             # 开发日志与自测记录
    │   └── API接口文档.md
    │
    ├── pm/                            # 产品经理工作空间
    │   ├── 需求文档.md                 # 正式交付物
    │   └── outbox/                    # 交给下游的交付物落盘区
    │
    ├── architect/                     # 架构师工作空间
    │   ├── 技术栈选型.md
    │   ├── 技术框架设计.md
    │   ├── designs/                   # 分步设计文档
    │   └── outbox/                    # 交给下游的交付物落盘区
    │
    ├── programmer/                    # 程序员工作空间
    │   └── outbox/                    # 交给下游的自测报告落盘区
    │
    └── qa/                            # 测试QA 工作空间
        └── outbox/                    # 交给上游/产品经理的验收报告
```

### 1.3 权限矩阵

每个角色在启动时通过 Agent CLI 参数限定文件访问范围：

```
                 pm/    architect/  programmer/  qa/     src/   shared/  .workflow/
产品经理(PM)     RW     R(outbox)   R(outbox)   R(outbox) —      RW       R
架构师(Arch)     R      RW          R(outbox)   R(outbox) R      R        R
程序员(Dev)      R      R           RW          R(outbox) RW     R        R
测试QA           R      R           R           RW        R      R        R
Dispatcher       R      R           R           R         —      R        RW
```

`R(outbox)` = 只能读取该角色 outbox/ 子目录下的文件，不能读草稿和工作区。

---

## 2. 状态机定义

Dispatcher 的核心是一张有限状态机（FSM）转移表。

### 2.1 状态枚举

```
INIT              # 初始状态，项目刚创建
PM_WORKING        # 产品经理正在工作
PM_DONE           # 产品经理完成，需求文档就绪
ARCH_WORKING      # 架构师正在工作
ARCH_DONE         # 架构师完成，设计文档就绪
DEV_WORKING       # 程序员正在工作
DEV_DONE          # 程序员完成，代码+自测就绪
QA_WORKING        # 测试QA 正在工作
QA_PASS           # QA 通过
QA_FAIL           # QA 未通过
ESCALATE_L1       # 升级到产品经理决策
ESCALATE_L2       # 升级到用户决策
PAUSED            # 等待用户响应
STEP_DONE         # 当前步骤完成
ALL_DONE          # 所有步骤完成
```

### 2.2 事件枚举

Agent 返回结果中的 status 字段值：

```
completed         # 正常完成
failed            # 执行失败
blocked           # 遇到无法决策的问题，需要升级
need_user         # 需要用户提供信息
need_revision     # 需要上游角色修订（附带根因类型）
```

### 2.3 状态转移表

```
当前状态          事件                  下一状态              Dispatcher 动作
─────────────────────────────────────────────────────────────────────────────
INIT              (启动)               PM_WORKING           启动产品经理 Session
PM_WORKING        completed            PM_DONE              读取 PM outbox，准备启动架构师
PM_WORKING        need_user            PAUSED               向用户转述问题
PM_DONE           (自动)               ARCH_WORKING         启动架构师 Session
ARCH_WORKING      completed            ARCH_DONE            读取架构 outbox
ARCH_WORKING      blocked(L1)          ESCALATE_L1          启动 PM Session 做决策
ARCH_WORKING      need_user            PAUSED               向用户转述问题
ARCH_DONE         (自动)               DEV_WORKING          启动程序员 Session
DEV_WORKING       completed            DEV_DONE             读取程序员 outbox
DEV_WORKING       blocked(L1)          ESCALATE_L1          启动 PM Session 做决策
DEV_WORKING       need_revision(arch)  ARCH_WORKING         启动架构师 Session 修订
DEV_WORKING       need_user            PAUSED               向用户转述问题
DEV_DONE          (自动)               QA_WORKING           启动 QA Session
QA_WORKING        completed(pass)      QA_PASS              检查是否有下一步
QA_WORKING        completed(fail)      QA_FAIL              按根因路由
QA_WORKING        need_user            PAUSED               向用户转述问题
QA_FAIL           root=code            DEV_WORKING          启动程序员 Session（同步骤）
QA_FAIL           root=design          ARCH_WORKING         启动架构师 Session（修订设计）
QA_FAIL           root=requirement     PM_WORKING           启动 PM Session（澄清需求）
QA_PASS           has_next_step        ARCH_WORKING         启动架构师 Session（下一步设计）
QA_PASS           no_next_step         ALL_DONE             输出最终交付摘要
ESCALATE_L1       pm_decided           (回到发起方状态)      将决策注入发起方 Session
ESCALATE_L1       pm_cannot_decide     ESCALATE_L2          暂停，向用户提问
ESCALATE_L2       (用户回复)            (回到发起方状态)      将用户决策注入流程
PAUSED            (用户回复)            (回到暂停前状态)      将用户信息注入当前 Session
```

### 2.4 state.yaml 文件格式

```yaml
project: "项目名称"
current_state: "DEV_WORKING"
current_step: 2
current_step_name: "支付模块"
total_steps: 5                        # 由架构师规划确定

current_role:
  name: "programmer"
  agent: "claude-code"                # 或 "gemini"
  session_id: "abc-123-def-456"
  started_at: "2026-03-28T10:00:00Z"
  retry_count: 0

history:                              # 本步骤内的角色流转记录
  - role: "product-manager"
    agent: "gemini"
    session_id: "aaa-111"
    status: "completed"
    finished_at: "2026-03-28T09:00:00Z"
  - role: "architect"
    agent: "claude-code"
    session_id: "bbb-222"
    status: "completed"
    finished_at: "2026-03-28T09:30:00Z"

escalation_stack: []                  # 当前挂起的升级请求
blocked_on_user: false
```

---

## 3. 通信协议

### 3.1 Dispatcher → Agent：启动指令

Dispatcher 通过 Agent CLI 的组合参数来启动一个角色。启动指令由四部分组成：

```
┌─────────────────────────────────────────────────────────┐
│  ① 角色身份（System Prompt）                             │
│     "你是 RedCap 框架中的架构师角色。"                     │
│     + handbook.md 的核心摘要                              │
│                                                          │
│  ② 任务上下文                                            │
│     "当前步骤：步骤2-支付模块"                             │
│     "上游交付物位于：pm/outbox/需求文档.md"                │
│     "你的工作目录：architect/"                             │
│     "你的交付物放入：architect/outbox/"                    │
│                                                          │
│  ③ 行为约束                                              │
│     "遵守 references/security-rules.md"                           │
│     "完成后在 outbox/ 中写入交付物"                        │
│     "在最后一行输出 JSON 状态摘要"                         │
│                                                          │
│  ④ 输出格式要求                                           │
│     JSON Schema 定义                                      │
└─────────────────────────────────────────────────────────┘
```

具体的 CLI 命令组装模式：

**Claude Code**：
```bash
claude -p "<prompt>" \
  --system-prompt "<角色手册摘要>" \
  --output-format json \
  --add-dir "<项目根目录>" \
  --permission-mode acceptEdits \
  --allowedTools "Read,Write,Bash(test:*)"
```

**Gemini CLI**：
```bash
gemini -p "<prompt>" \
  --output-format json \
  --include-directories "<项目根目录>" \
  --approval-mode auto_edit
```

### 3.2 Agent → Dispatcher：返回结果

Agent 执行完毕后，返回 JSON 中的关键字段：

```json
{
  "session_id": "由 Agent CLI 自动返回",
  "response": "Agent 的文本回复（包含工作摘要）",

  "__redcap_status": {
    "status": "completed | failed | blocked | need_user | need_revision",
    "summary": "本次工作的一句话摘要",
    "deliverables": [
      "architect/outbox/步骤2-支付模块.md",
      "architect/技术框架设计.md（已更新索引）"
    ],
    "escalation": {
      "level": 1,
      "target_role": "product-manager",
      "question": "...",
      "recommendation": "..."
    },
    "revision": {
      "target_role": "architect",
      "root_cause": "design",
      "description": "..."
    },
    "next_suggestion": "根据我的判断，下一步应该..."
  }
}
```

**传递策略（A 为主，B 为 Fallback）**：

- **方案 A（主）**：通过 Prompt 约定 Agent 必须在回复文本中包含 `__redcap_status` JSON 块。Dispatcher 从 Agent 返回的 `response` 字段中正则提取。优势：一次 CLI 调用即获得结果，无额外文件 I/O。
- **方案 B（Fallback）**：若 Dispatcher 无法从 response 中解析出合法的 `__redcap_status`，则检查 `.workflow/last-result.json` 文件——Prompt 中同时约定 Agent 在工作结束时将状态写入此文件作为备份。
- **解析顺序**：先尝试 A → A 失败则读 B → 均失败则标记 `status: "failed"`，记录原始 response 供人工排查，并触发同角色重试（最多 1 次）或升级至 L1。

### 3.3 角色 → 角色：交付物协议

角色之间不直接通信，而是通过文件系统中的 outbox 传递交付物。

**交付物命名约定**：
```
{角色}/outbox/{步骤号}-{交付物名称}.md
```

**各角色的标准交付物**：

| 源角色 | 交付物 | 消费角色 |
|--------|--------|---------|
| 产品经理 | `pm/outbox/需求文档.md` | 架构师、测试QA |
| 架构师 | `architect/outbox/步骤X-{模块名}.md` | 程序员 |
| 架构师 | `architect/技术框架设计.md`（更新索引） | 程序员、测试QA |
| 程序员 | `programmer/outbox/步骤X-自测报告.md` | 测试QA |
| 程序员 | `shared/API接口文档.md` | 测试QA |
| 测试QA | `qa/outbox/步骤X-测试报告.md` | 产品经理（验收） |

---

## 4. Session 管理策略

### 4.1 Session 粒度

```
Session ID = {角色} × {步骤} × {Agent工具}

示例：
  pm-step0-gemini          # 产品经理，初始需求阶段
  architect-step1-claude    # 架构师，步骤1设计
  programmer-step1-gemini   # 程序员，步骤1实现
  qa-step1-claude           # QA，步骤1测试
  architect-step2-claude    # 架构师，步骤2设计（新 Session）
```

### 4.2 首次调用 vs 继续调用

| 场景 | 操作 |
|------|------|
| 角色首次接手某步骤 | 创建新 Session（新的 `session_id`） |
| 同角色同步骤内的后续迭代（如 QA 返回了 bug，程序员继续修） | 恢复同一 Session（`--resume`）以保持上下文 |
| 角色接手新的步骤 | 创建新 Session（旧步骤的上下文不需要了） |
| 升级决策后回到发起角色 | 恢复原 Session，注入决策结果 |

### 4.3 sessions.yaml 文件格式

```yaml
sessions:
  pm-step0:
    agent: "gemini"
    session_id: "e89c526a-68ac-4e74-a6dd-645d3abc7e74"
    status: "completed"
    created_at: "2026-03-28T09:00:00Z"

  architect-step1:
    agent: "claude-code"
    session_id: "abc-123-def-456"
    status: "completed"
    created_at: "2026-03-28T09:30:00Z"

  programmer-step1:
    agent: "gemini"
    session_id: "def-456-ghi-789"
    status: "in-progress"
    created_at: "2026-03-28T10:00:00Z"
    resume_count: 1
```

---

## 5. Agent 路由策略

### 5.1 ~~初始方案：静态绑定~~（已废弃）

> **已被动态路由取代**。静态绑定在 Phase 4 E2E 验证中暴露严重局限性——3/4 个 Agent CLI 在 headless 模式下出现挂起/超时/权限阻塞（详见 L-4、L-7、L-11），静态绑定无法自动降级。
> 
> 当前路由算法：`tools/redcap-detect-agents.sh` 嗅探 + `knowledge/model-capability-matrix.yaml` 能力矩阵 → 动态适配分计算（见 [agent-adapters.md §1.3](../dispatcher/agent-adapters.md)）。

### 5.2 ~~远期方案：~~动态路由（已实现）

路由算法已在 SKILL.md §2 和 agent-adapters.md §1.3 中实现。核心因素：

```
路由因素：
  · 模型能力评分 × 角色需求权重（能力矩阵驱动）
  · Agent 可用性（嗅探脚本实时检测）
  · Reviewer 跨模型族奖励分（确保独立审视视角）
  · Fallback 序列：首选 → 备选1 → 备选2 → Dispatcher 代劳（需用户授权）
```

**E2E 验证结论**（trpg-web, 2026-04）：动态路由的嗅探检测有效，但 CLI headless 稳定性是实际瓶颈。Dispatcher 代劳作为最终降级路径在实战中被证明可行且高效，前提是 Dispatcher 模型能力足够（reasoning ≥ 4）。

---

## 6. Dispatcher 同步事件循环

Dispatcher 的运行逻辑如下（伪代码表示，实际由输入 AI 按此逻辑执行）：

```
function dispatch_loop(project_dir):
    while true:
        state = read_yaml(project_dir/.workflow/state.yaml)
        
        if state.current_state == "ALL_DONE":
            output_final_summary()
            break
        
        if state.current_state == "PAUSED":
            question = state.escalation_stack.last.question
            user_answer = ask_user(question)          # 输入 AI 转述给用户
            inject_answer_to_session(state, user_answer)
            state.current_state = state.paused_from    # 恢复暂停前状态
            continue
        
        if state.current_state ends with "_DONE" or is auto-transition:
            next = lookup_transition_table(state.current_state)
            state.current_state = next.target_state
        
        if state.current_state ends with "_WORKING":
            role = extract_role(state.current_state)   # 如 "architect"
            agent = lookup_agent_routing(role)          # 如 "claude-code"
            prompt = assemble_prompt(role, state)       # 组装启动指令
            session = get_or_create_session(role, state.current_step, agent)
            
            result = execute_agent_cli(agent, prompt, session)  # 同步阻塞
            
            event = parse_redcap_status(result)         # 解析 __redcap_status
            update_state(state, event)                  # 更新 state.yaml
            update_sessions(session, event)             # 更新 sessions.yaml
            
            continue                                    # 进入下一轮循环
```

**关键特征**：
- 每一轮循环只做一件事：读状态 → 决定下一步 → 执行 → 更新状态
- Dispatcher 不理解交付物的内容，只关心 status 字段
- 同步阻塞执行，不需要轮询
- 状态持久化到 YAML 文件，即使 Dispatcher 意外中断也可恢复

---

## 7. 实施计划

### 7.1 阶段划分

```
Phase 0: 准备工作                                              ✅ 已完成
  · 从 master 建立 feature 分支
  · 确认 Claude Code / Gemini CLI 的 API 可用性
  · 确认两个工具的非交互模式 + JSON 输出在当前环境下可正常工作

Phase 1: 框架骨架                                              ✅ 已完成
  · 重构 redcap/ 目录结构（roles/ 目录化、新增 dispatcher/、references/ 下增补通信协议）
  · 编写 references/communication-protocol.md
  · 编写 dispatcher/state-machine.md（状态转移表正式版）
  · 编写 dispatcher/agent-adapters.md（CLI 参数映射）

Phase 2: 角色手册改造                                          ✅ 已完成（2026-04-07）
  · 将现有 4 个 roles/*.md 迁移到新的 roles/{name}/handbook.md 格式
  · 适配变更：
    - 移除硬编码 Agent 名称，改为「由 Dispatcher 动态路由分配」
    - 新增"降级说明"：当所有候选 Agent 不可用时，Dispatcher 可在用户授权后代劳
    - 新增"交付物输入/输出路径"的明确指引
    - 新增"状态报告格式"（__redcap_status JSON 块）的输出要求
    - 保持业务逻辑不变（验收标准、质量门禁等）

Phase 3: Dispatcher 协议实现                                    ✅ 已完成（da3308b）
  · 编写 dispatcher/prompt-templates/（4 个角色的启动 Prompt 模板）
  · 改写 SKILL.md 的"执行指令"部分为 Dispatcher 协议
  · 编写 .workflow/ 目录的初始化逻辑
  · 编写 state.yaml / sessions.yaml 的格式规范

Phase 4: 端到端验证                                             ✅ 已完成（2026-04-07）
  · 验证项目：trpg-web（5步完整开发 + 迭代v2）
  · 正向流转路径覆盖率：100%（6/6）
  · 回退/异常路径覆盖率：0%（QA全部首次通过，未触发回退）
  · 交付物传递完整性：100%
  · __redcap_status 协议：未验证（Agent 遗忘输出，代劳模式跳过）
  · 详细报告：docs/phase4-e2e-validation-report.md

Phase 5: 合并与文档收尾                                         ✅ 已完成（2026-04-07）
  · 更新 SKILL.md 铁律（代劳条款）
  · 更新各角色 handbook 和 prompt-templates
  · 新增 L-19、L-20 经验沉淀
  · 修复 trpg-web state.yaml 滞后问题
```

### 7.2 最小可行验证（Phase 4 前的快速 Smoke Test）

在 Phase 3 完成后、进入完整端到端验证前，先做一个最小闭环验证：

```
1. Dispatcher 启动一个 Agent CLI（如 Gemini），角色=架构师
2. Agent 读取一个预设的需求文档
3. Agent 写出一个设计文档到 architect/outbox/
4. Agent 返回 JSON，包含 __redcap_status.status = "completed"
5. Dispatcher 解析返回值，更新 state.yaml
6. Dispatcher 据此决定启动程序员的 Agent CLI（如 Claude Code）
7. 程序员 Agent 读取架构师的 outbox，开始编码

如果这个 7 步闭环跑通 → Phase 4 的完整验证可以展开
如果跑不通 → 在此收集问题并逐项解决
```

---

## 8. 项目层初始化流程

当 Dispatcher 首次在一个项目中被触发时，执行以下初始化：

```
1. 检测项目根目录下是否存在 .workflow/state.yaml
   · 存在 → 读取并从上次中断处恢复（断点续传）
   · 不存在 → 执行初始化

2. 初始化步骤：
   a. 创建 .workflow/ 目录
   b. 创建 .workflow/state.yaml（initial state = INIT）
   c. 创建 .workflow/sessions.yaml（空）
   d. 创建 开发手册/ 目录结构：
      · shared/README.md
      · pm/、pm/outbox/
      · architect/、architect/outbox/、architect/designs/
      · programmer/、programmer/outbox/
      · qa/、qa/outbox/
   e. 将 state 设为 PM_WORKING
   f. 启动产品经理 Session → 开始与用户需求对话
```

---

## 9. 与现有 RedCap 的兼容性

### 9.1 文档映射

现有 RedCap 的 `/开发手册/` 固定文件与新结构的映射：

| 现有路径 | 新路径 | 说明 |
|---------|--------|------|
| `开发手册/README.md` | `开发手册/shared/README.md` | 移入 shared/ |
| `开发手册/1.需求文档.md` | `开发手册/pm/需求文档.md` | 移入 PM 空间 |
| `开发手册/2.技术栈选型.md` | `开发手册/architect/技术栈选型.md` | 移入架构师空间 |
| `开发手册/3.技术框架设计.md` | `开发手册/architect/技术框架设计.md` | 移入架构师空间 |
| `开发手册/4.API接口文档.md` | `开发手册/shared/API接口文档.md` | 移入 shared/ |
| `开发手册/5.开发进度日志.md` | `开发手册/shared/开发进度日志.md` | 移入 shared/ |
| `开发手册/designs/` | `开发手册/architect/designs/` | 移入架构师空间 |

### 9.2 向前兼容

新引擎需要兼容已有旧版 RedCap 项目。采用**自动检测 + 用户确认迁移**策略：

1. **检测**：Dispatcher 启动时检查 `开发手册/` 目录结构，识别旧版（扁平结构，如 `1.需求文档.md`）vs 新版（角色隔离结构，如 `pm/需求文档.md`）
2. **提示**：检测到旧版结构时，向用户说明差异并询问是否迁移
3. **迁移**：用户确认后，按 §9.1 映射表自动移动文件到新路径，保留原始内容不变
4. **兼容运行**：若用户选择暂不迁移，Dispatcher 以兼容模式运行——读写路径按旧结构映射，功能不受影响
5. **渐进迁移**：允许部分迁移（如先迁移目录结构，后续再切换 Agent 路由）

---

## 10. 演进方向：从 0→1 到 1→100

本次引擎升级的状态机主要围绕 **0→1（新项目全流程）** 设计。但 RedCap 更高频的实际场景是 **1→100（存量项目的需求变更、功能迭代、Bug 修复）**。以下能力在本次升级中预留接口，后续迭代中优先实现：

| 场景 | 当前支持度 | 需要增强的能力 |
|------|-----------|---------------|
| 需求变更（改已有功能） | 部分（可重新进入 PM_WORKING） | 变更影响分析：自动识别受影响的步骤和文件，只重跑受影响的链路 |
| 新增功能（现有项目加功能） | 支持（新增步骤） | 增量步骤插入：不中断已完成步骤，只追加新步骤 |
| Bug 修复 | 部分（QA_FAIL → DEV_WORKING） | 短路流程：跳过 PM/Architect 直接进入 Dev→QA 循环 |
| 重构/优化 | 不支持 | 技术驱动流程：由 Architect 或 Dev 发起，无需 PM 介入 |
| 紧急热修复 | 不支持 | 快速通道：Dev→QA 双人模式，跳过完整流程 |

这些能力的共同点是需要**非线性的状态机入口**——允许从中间状态启动，而非必须从 INIT 开始。架构上已为此预留空间（state.yaml 的断点续传机制天然支持从任意状态恢复），具体的状态转移扩展将作为引擎升级的 **Phase 6** 规划。

---

## 11. 本文小结

本篇定义了引擎升级的**可执行技术框架**：目录结构、状态机、通信协议、Session 管理、Agent 路由、实施计划。全部设计遵循第一篇中确立的五个原则——进程隔离、去中心化责任链、文件系统即通信、Dispatcher 作为基础设施、工作空间隔离。

两篇文档共同构成本次 RedCap 引擎升级的完整方案。待用户确认后，按 Phase 0 → Phase 5 的顺序在独立分支上逐步施工。1→100 场景的增强能力将作为 Phase 6 在引擎基础稳定后启动。

---

## 附录：框架文件索引

> 以下索引列出 RedCap 技能包中所有文件及其用途，供人工查阅。SKILL.md 正文中已在对应上下文处内联引用了这些路径，因此 Dispatcher 执行时无需依赖本索引。

### 框架规范

| 文件 | 说明 |
|------|------|
| dispatcher/state-machine.md | FSM 完整定义（状态、事件、转移表） |
| dispatcher/agent-adapters.md | CLI 命令模板与参数映射 |
| references/communication-protocol.md | `__redcap_status` JSON Schema |
| references/security-rules.md | 安全工程约束 |
| references/code-standards.md | 代码质量规范 |

### 角色手册与 Prompt 模板

| 角色 | 手册路径 | Prompt 模板 |
|------|---------|------------|
| 产品经理 | roles/product-manager/handbook.md | dispatcher/prompt-templates/pm-prompt.md |
| 架构师 | roles/architect/handbook.md | dispatcher/prompt-templates/architect-prompt.md |
| 程序员 | roles/programmer/handbook.md | dispatcher/prompt-templates/programmer-prompt.md |
| 测试QA | roles/qa/handbook.md | dispatcher/prompt-templates/qa-prompt.md |

### 文档模板

| 模板 | 路径 |
|------|------|
| 分步设计索引 | roles/architect/templates/step-design-index.md |
| 模块设计文档 | roles/architect/templates/module-design-doc.md |
| API接口文档 | roles/architect/templates/api-doc.md |
| 需您准备 | roles/architect/templates/preparation-checklist.md |
| 开发进度日志 | roles/programmer/templates/dev-progress-log.md |
| README | roles/programmer/templates/readme-template.md |
| 测试用例与验证记录 | roles/qa/templates/test-cases.md |
