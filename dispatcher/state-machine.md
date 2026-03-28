# Dispatcher 状态机定义

> **用途**：定义 Dispatcher 的有限状态机（FSM），驱动多 Agent 协同流转。  
> **依赖**：[通信协议](../references/communication-protocol.md)

---

## 1. 状态枚举

| 状态 | 说明 |
|------|------|
| `INIT` | 初始状态，项目刚创建 |
| `PM_WORKING` | 产品经理正在工作 |
| `PM_DONE` | 产品经理完成，需求文档就绪 |
| `ARCH_WORKING` | 架构师正在工作 |
| `ARCH_DONE` | 架构师完成，设计文档就绪 |
| `DEV_WORKING` | 程序员正在工作 |
| `DEV_DONE` | 程序员完成，代码+自测就绪 |
| `QA_WORKING` | 测试QA 正在工作 |
| `QA_PASS` | QA 通过 |
| `QA_FAIL` | QA 未通过 |
| `ESCALATE_L1` | 升级到产品经理决策 |
| `ESCALATE_L2` | 升级到用户决策 |
| `PAUSED` | 等待用户响应 |
| `STEP_DONE` | 当前步骤完成 |
| `ALL_DONE` | 所有步骤完成 |

---

## 2. 事件枚举

来源于 Agent 返回的 `__redcap_status.status` 字段：

| 事件 | 说明 |
|------|------|
| `completed` | 正常完成 |
| `failed` | 执行失败 |
| `blocked` | 遇到无法决策的问题，需要升级 |
| `need_user` | 需要用户提供信息 |
| `need_revision` | 需要上游角色修订（附带 root_cause） |

---

## 3. 状态转移表

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
ESCALATE_L2       (用户回复)           (回到发起方状态)      将用户决策注入流程
PAUSED            (用户回复)           (回到暂停前状态)      将用户信息注入当前 Session
```

---

## 4. state.yaml 格式

```yaml
project: "项目名称"
current_state: "DEV_WORKING"
current_step: 2
current_step_name: "支付模块"
total_steps: 5

current_role:
  name: "programmer"
  agent: "gemini"
  session_id: "abc-123-def-456"
  started_at: "2026-03-28T10:00:00Z"
  retry_count: 0

history:
  - role: "product-manager"
    agent: "claude-code"
    session_id: "aaa-111"
    status: "completed"
    finished_at: "2026-03-28T09:00:00Z"
  - role: "architect"
    agent: "gemini"
    session_id: "bbb-222"
    status: "completed"
    finished_at: "2026-03-28T09:30:00Z"

paused_from: null
escalation_stack: []
blocked_on_user: false
```

---

## 5. sessions.yaml 格式

```yaml
sessions:
  pm-step0:
    agent: "claude-code"
    session_id: "e89c526a-68ac-4e74-a6dd-645d3abc7e74"
    status: "completed"
    created_at: "2026-03-28T09:00:00Z"

  architect-step1:
    agent: "gemini"
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

**Session 粒度**：`{角色}-{步骤}`，同角色同步骤内的迭代复用同一 Session。

---

## 6. 同步事件循环（伪代码）

```
function dispatch_loop(project_dir):
    while true:
        state = read_yaml(project_dir/.workflow/state.yaml)

        if state.current_state == "ALL_DONE":
            output_final_summary()
            break

        if state.current_state == "PAUSED":
            question = state.escalation_stack.last.question
            user_answer = ask_user(question)
            inject_answer_to_session(state, user_answer)
            state.current_state = state.paused_from
            continue

        if state.current_state ends with "_DONE" or is auto-transition:
            next = lookup_transition_table(state.current_state)
            state.current_state = next.target_state

        if state.current_state ends with "_WORKING":
            role = extract_role(state.current_state)
            agent = lookup_agent_routing(role)          # 含 Fallback 路由
            prompt = assemble_prompt(role, state)        # 按变量映射表填充模板
            write_file(".workflow/{role}-prompt-step{N}.txt", prompt)  # 文件传参

            session = get_or_create_session(role, state.current_step, agent)
            result = execute_agent_cli(agent, prompt_file, session)

            # 状态解析
            event = parse_redcap_status(result)          # A 为主，B 为 Fallback
            write_json(".workflow/last-result.json", event)  # Dispatcher 写入

            # 交付物完整性校验（status=="completed" 时）
            if event.status == "completed":
                if not validate_deliverables(event, role):
                    retry_or_fallback(agent, role)       # 重试/切换 Agent，不代劳
                    continue

            update_state(state, event)
            update_sessions(session, event)
            continue
```

**关键特征**：
- 每轮循环只做一件事：读状态 → 决定下一步 → 执行 → 校验 → 更新状态
- Dispatcher 不理解交付物内容，只关心 status 字段 + 文件是否存在
- `last-result.json` 由 Dispatcher 写入，非 Agent
- 交付物校验失败 → 重试 Agent 或 Fallback，Dispatcher 不代为生成
- 同步阻塞执行，不需要轮询
- 状态持久化到 YAML，即使中断也可从断点恢复
- Prompt 始终通过文件传参（`.workflow/{role}-prompt-step{N}.txt`）
