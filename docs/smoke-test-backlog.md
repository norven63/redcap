# 烟雾测试 Backlog

> **来源**：2026-03-28 AI-Coding-Museum 烟雾测试（轻量路径：DEV→QA→回退→修复→回归→ALL_DONE）  
> **状态标记**：🔴 待修复 | 🟡 待优化 | ✅ 已完成

---

## P0 — 阻塞性问题（已修复）

### ✅ #1 claude-code 发送 thinking 参数导致 Kimi-K2.5 返回 400

- **现象**：`claude -p "回复OK"` → `API Error: 400 thinking type should be enabled or disabled`
- **根因**：`~/.claude/settings.json` 中 `"model": "opus[1m]"` 触发 Extended Thinking 模式，claude-code 在 API 请求中附带 `thinking` 参数，SiliconFlow 的 Kimi-K2.5 不支持该参数
- **修复**：`settings.json` 加入 `"alwaysThinkingEnabled": false`
- **框架影响**：适配器文档需注明第三方代理 API 的兼容性约束

### ✅ #2 Gemini CLI 频控导致 Programmer Agent 中断

- **现象**：Gemini 连续返回 `You have exhausted your capacity on this model`，10 次重试后仍失败
- **根因**：Google 近期调整流量优先级策略，Pro 用户在高峰期也会受频控
- **修复**：升级 Gemini CLI 0.35.2 → 0.35.3；内建重试机制（10次指数退避 5s→30s）已够用
- **框架影响**：需设计 Agent Fallback 策略（见 #9）

---

## P1 — 框架设计缺陷（已修复）

### ✅ #3 Agent 中断时交付物缺失无检测

- **现象**：Gemini Programmer 因频控中断，代码已修改但 `programmer/outbox/`、`last-result.json`、`__redcap_status` 全部缺失，Dispatcher 无感知直接推进到 QA
- **优化方案**：Dispatcher 在 `*_WORKING → *_DONE` 转移前增加**交付物完整性检查**：
  1. 检测 outbox 目录是否非空
  2. 检测 `last-result.json` 是否存在且可解析
  3. 检测 `__redcap_status` JSON 是否包含必填字段（status、summary、deliverables）
  4. 任一缺失 → **必须重试该 Agent**（优先同一 Agent，频控时切 fallback Agent），不得由 Dispatcher 代为生成任何交付内容
- **涉及文件**：SKILL.md §5.2（事件循环）、dispatcher/state-machine.md

### ✅ #4 outbox 协议未被 Agent 遵守

- **现象**：Programmer 和 QA 均未写入各自的 `outbox/` 目录，直接写 `shared/开发进度日志.md`
- **优化方案**：
  1. Prompt 模板中增加**硬性输出清单**（checklist），明确列出必须写入的文件路径和格式
  2. Dispatcher 在解析返回后，逐一校验 `deliverables` 列表中的文件是否实际存在于磁盘
  3. 不存在 → 要求 Agent 补写（重试）
- **涉及文件**：dispatcher/prompt-templates/*.md、SKILL.md §5.2

### ✅ #5 last-result.json 写入路径错乱

- **现象**：QA Agent 在项目根目录写了 `/.workflow/last-result.json` 和 `/last-result.json` 两个残留文件，正确路径应为 `开发手册/.workflow/last-result.json`
- **优化方案**：
  - 方案 A（推荐）：**由 Dispatcher 统一管理** `last-result.json` 的写入——Agent 只需在回复中输出 `__redcap_status` JSON，Dispatcher 从 response 中提取后写入正确路径，Agent 不再自行写文件
  - 方案 B：Prompt 中用**绝对路径**指定写入目标，而非相对路径
- **涉及文件**：dispatcher/prompt-templates/*.md、SKILL.md §5.3、references/communication-protocol.md

### ✅ #6 Session 管理未生效

- **现象**：`sessions.yaml` 全程为空，未记录任何 Agent session ID，断点恢复能力 = 0
- **优化方案**：
  1. Dispatcher 在每次 CLI 调用后，从返回 JSON 中提取 `session_id`
  2. 写入 `sessions.yaml`，格式：`{role}_{step}: {session_id}`
  3. 同一角色的重试/回退调用应尝试 `--resume` 传入已有 session，利用上下文延续
  4. Session 过期或不可用时 fallback 到新建 session
- **涉及文件**：SKILL.md §5.2、dispatcher/agent-adapters.md

---

## P2 — 工程体验问题（已修复）

### ✅ #7 Shell 中文 Prompt 传参截断/引号问题

- **现象**：直接用 shell 变量传递中文 Prompt 时出现截断、引号残留导致终端进入 `quote>` 模式
- **优化方案**：
  - 固化**文件传参模式**为适配器标准：Dispatcher 始终先将 prompt 写入 `.workflow/{role}-prompt-step{N}.txt`，再用 `$(cat ...)` 读取传入 CLI
  - 适配器命令模板中明确使用此模式
- **涉及文件**：dispatcher/agent-adapters.md §2.2、§3.2

### ✅ #8 Gemini CLI 交互模式污染终端

- **现象**：`gemini` 命令未加 `-p` 时进入交互模式，后续所有终端命令被 Gemini 吞掉，终端不可用
- **优化方案**：
  1. 适配器命令模板中**强制包含 `-p`**，Dispatcher 在组装命令时校验
  2. 增加 `--sandbox false` 避免 sandbox 相关交互
  3. 设计超时机制：Agent CLI 执行超过阈值后 kill 进程并重试
- **涉及文件**：dispatcher/agent-adapters.md §3.2

### ✅ #9 Dispatcher 违反“不写代码”原则做了 fallback

- **现象**：Gemini Programmer 频控失败后，Dispatcher 直接修改了 `src/main.ts`（删除 `now` 变量）
- **优化方案**：
  1. 设计正式的 **Agent Fallback 路由**：当首选 Agent 不可用时，自动切换到备选 Agent
  2. 在 `agent-adapters.md` 增加 fallback 配置：
     ```yaml
     fallback_routing:
       programmer: ["gemini", "claude-code"]  # 优先 gemini，不可用时切 claude-code
       qa: ["claude-code", "gemini"]          # 优先 claude-code，不可用时切 gemini
     ```
  3. **铁律**：Dispatcher 在任何情况下都不得直接修改项目代码或生成交付物
- **涉及文件**：dispatcher/agent-adapters.md（新增 §6 Fallback 策略）、SKILL.md §1（Dispatcher 职责声明）

---

## P3 — 可改进项（已修复）

### ✅ #10 Prompt 模板变量替换全靠手工

- **现象**：Dispatcher 手动读模板、手动拼接上下文、手动创建 prompt 文件，流程繁琐且易出错
- **优化方案**：
  1. 在 SKILL.md §5.2 事件循环中增加明确的"Prompt 组装伪代码"
  2. 定义标准化的变量映射表：
     ```
     {{handbook_content}}       → 读取 roles/{role}/handbook.md
     {{pm_requirement_summary}} → 读取 pm/需求文档.md 摘要
     {{project_dir}}            → 项目根目录绝对路径
     {{current_step}}           → state.yaml.current_step
     {{step_name}}              → 从进度日志解析
     {{dev_manual_dir}}         → 开发手册/ 绝对路径
     ```
  3. 确保 Dispatcher 按此映射表机械执行，减少遗漏
- **涉及文件**：SKILL.md §5.2、dispatcher/prompt-templates/*.md

---

## 实施优先级建议

| 批次 | 编号 | 状态 |
|------|------|------|
| 已完成 | #1, #2 | ✅ 环境级修复 |
| 已完成 | #3, #4, #5, #9 | ✅ 交付物完整性 + Dispatcher 职责边界 |
| 已完成 | #6, #7, #8 | ✅ Session 恢复 + CLI 调用鲁棒性 |
| 已完成 | #10 | ✅ Prompt 变量映射表 |
