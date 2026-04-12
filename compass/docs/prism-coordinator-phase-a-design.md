# Prism Coordinator Phase A Design

**日期**：2026-04-11  
**状态**：已完成设计讨论，待 Norven 审阅书面 spec  
**范围级别**：中段安全接线（非完整协议拉通）

---

## 1. 背景与目标

RedCap 的多会话隔离基础已经落到 Layer A / Layer B runtime session、capability、binding、process claim 和 Prism run-scoped registry helper 上，但 Prism 仍缺少一个真实的 coordinator 入口，把这些 foundation 接到 Dispatch / Collect / Council 主链路。

当前缺口主要有三类：

1. Prism 启动后，缺少统一入口把 `run_id`、registry 初始化和 agent roster 写入 `prism/runs/<run_id>/session-registry.yaml`
2. Collect 的解析结果、追问结果、schema 判定还没有统一落到 run-scoped 目录并再回写 registry
3. Council 多轮续接虽然协议上要求复用原 handle，但仓库里还没有统一的 run-scoped handle resolve 入口

本设计的目标是以**最小可安全推进**的顺序补齐这些链路，同时顺手修复飞书通知项目名不可读的问题。

---

## 2. 本轮范围

### 2.1 In Scope

本轮只实现以下四步：

1. **Dispatch 接线**
   - 引入 `prism/tools/prism-coordinator.sh`
   - 让真实 Dispatch 在 agent 启动成功后调用 coordinator 完成 run 初始化与 roster 写入

2. **Collect 接线**
   - 让原始输出、提取结果、追问元数据落到 `prism/runs/<run_id>/collect/<role>/`
   - 再通过 coordinator 回写 registry 的 `status` / `schema_ok`

3. **Council handle 复用接线**
   - Round 2+ 统一从 run-scoped registry 解析 handle
   - 不再允许临时猜测、latest fallback、或重新 Dispatch 新 Agent

4. **飞书通知项目名修复**
   - `redcap-on-complete.sh` 的项目名解析改为稳定链路，避免 `tmpxxxx` 标题

### 2.2 Out of Scope

本轮明确不做：

- Prism Dispatch Firewall 的物理强制化
- owner/lease 完整接管机制
- legacy `.session-registry.yaml` 的移除
- synthesize / audit 的复杂状态机
- 与本任务无关的文档重构或通用重构

---

## 3. 架构边界

本轮采用“两层职责”模型：

### 3.1 低层真相层：`prism/tools/prism-run-state.sh`

继续只负责：

- run 目录路径
- `session-registry.yaml` 初始化 / upsert / resolve
- `owner.json` 写入
- legacy read bridge

它**不**负责理解高层业务动作，不负责发起 Dispatch / Collect / Council。

### 3.2 高层协调层：`prism/tools/prism-coordinator.sh`

新增的 coordinator 只负责高层动作编排：

- 启动 run
- 注册 agent
- 记录 collect 结果
- 解析 council handle
- 落盘 synthesize / audit 摘要

所有对 registry 的真实写入仍通过 `prism-run-state.sh` 完成，避免状态逻辑与底层文件协议混杂。

---

## 4. 数据模型

### 4.1 唯一真相文件

`prism/runs/<run_id>/session-registry.yaml`

保持为唯一 run 级真相文件，只记录：

- `run_id`
- `mode`
- agent roster
- `handle_type`
- `handle`
- `role`
- `model`
- `family`
- `injection_mode`
- `status`
- `schema_ok`

Coordinator 是唯一写者。任何角色产物不得直接修改此文件。

### 4.2 Collect 目录

每个角色单独目录：

`prism/runs/<run_id>/collect/<role>/`

建议文件：

- `raw.txt`：原始输出
- `parsed.json`：高容错提取后的 JSON 载荷（`responded` / `followed_up` 必填）
- `meta.json`：收集元数据，例如：
  - `follow_up_count`
  - `backend_limitation`
  - `collected_at`
  - `source_handle`

### 4.3 Synthesize / Audit 目录

- `synthesize/round-<n>-summary.md`
- `audit/summary-audit.json`

本轮只要求基础落盘，不把它们提升为额外真相文件。

---

## 5. 状态流转

### 5.1 Dispatch

每个 agent 启动成功后：

- 写入 registry
- `status=dispatched`
- `schema_ok=null`

### 5.2 Collect

Collect 结果只允许以下终态：

- `responded + schema_ok=true`
  - 首次解析即合格

- `followed_up + schema_ok=true`
  - 经 1~2 次追问后合格

- `absent + schema_ok=false`
  - 超时
  - 无法提取合法 JSON
  - 追问上限耗尽后仍缺字段

关键原则：

1. 先落 collect 证据文件
2. 再更新 registry

禁止出现“registry 已说 responded，但 collect 目录没有证据”的倒挂状态。

### 5.3 Council

Round 2+：

- 不新增 registry 条目
- 只复用既有 roster 与 handle
- 同一 role 允许把终态从 `responded` 推进到 `followed_up`；若续接失败，可推进到 `absent`
- 把轮次摘要和审计写进 run 目录

---

## 6. Coordinator CLI 接口

新增 `prism/tools/prism-coordinator.sh`，本轮只提供以下命令：

### 6.1 `start-run`

```bash
bash prism/tools/prism-coordinator.sh start-run \
  --mode <mode> \
  --run-id <run_id>
```

职责：

- 调 `prism-run-state.sh init-registry`
- 若当前存在可信 runtime attach，则追加 `write-owner`

### 6.2 `register-agent`

```bash
bash prism/tools/prism-coordinator.sh register-agent \
  --run-id <run_id> \
  --mode <mode> \
  --role <role> \
  --handle-type <task_agent|cli_session|shell> \
  --handle <id> \
  --model <model> \
  --family <family> \
  --injection-mode <native|prefixed>
```

职责：

- 统一登记 roster
- 状态固定写为 `dispatched`

### 6.3 `record-collect`

```bash
bash prism/tools/prism-coordinator.sh record-collect \
  --run-id <run_id> \
  --mode <mode> \
  --role <role> \
  --status <responded|followed_up|absent> \
  --schema-ok <true|false> \
  [--round <n>] \
  [--raw-file <path>] \
  [--parsed-file <path>] \
  [--meta-file <path>]
```

职责：

- 先把证据文件写入标准 collect 目录
- `responded` / `followed_up` 必须留下 `parsed.json`；`raw.txt` 可选
- `--round` 默认 `1`；只有 council Round 2+ 才允许用 `--round > 1` 推进 `responded -> followed_up|absent`
- collect 重试必须整体替换该角色目录，不能残留旧 `raw.txt` / `parsed.json`
- 再回写 registry

### 6.4 `resolve-handle`

```bash
bash prism/tools/prism-coordinator.sh resolve-handle \
  --run-id <run_id> \
  --role <role>
```

职责：

- 输出本 run 指定 role 的 handle
- 若 role 缺失、handle 为空、状态非法，则非零退出

### 6.5 `write-summary`

```bash
bash prism/tools/prism-coordinator.sh write-summary \
  --run-id <run_id> \
  --round <n> \
  --type <synthesize|audit> \
  --input <file>
```

职责：

- 只做标准路径落盘
- 不引入额外状态机

---

## 7. 兼容与错误处理

### 7.1 Fail-fast

以下动作一律硬失败，不做 silent fallback：

- run 初始化失败
- registry upsert 失败
- collect 证据文件落盘失败
- council handle resolve 失败

### 7.2 Legacy Bridge

保留现有规则：

- run-scoped registry 是唯一新写路径
- legacy `.session-registry.yaml` 只允许在 `run_id` 精确匹配时只读桥接
- coordinator 永远不写 legacy path
- 禁止 latest fallback、模糊报告名推断、跨 run 推断

### 7.3 Council 续接保护

如果 `resolve-handle` 失败：

- 当前轮直接失败
- 由调用方决定是否进入 `absent` 或 deadlock 路径
- 禁止“偷偷重新 Dispatch 一个新 Agent”

---

## 8. 飞书通知可读性修复

`redcap-on-complete.sh` 的项目名解析顺序改为：

1. 显式传入的 `project_name`
2. 当前 git 仓库根目录名
3. 固定值 `redcap`

这样在临时目录、测试目录、或路径 basename 不可读时，不会再把 `tmpxxxx` 发到飞书里。

---

## 9. 分刀实施顺序

### 第 1 刀：Dispatch 接线

- 新增 `prism-coordinator.sh`
- 接入 `start-run + register-agent`
- 验收：run-scoped registry 正确写入 roster / handle / dispatched

### 第 2 刀：Collect 接线

- 接入 `record-collect`
- 验收：collect 目录和 registry 状态同步一致

### 第 3 刀：Council 接线

- 接入 `resolve-handle`
- 验收：Round 2+ 句柄只从本 run registry 解析

### 第 4 刀：飞书修复

- 修正 `redcap-on-complete.sh`
- 验收：不会再出现 `tmpxxxx` 项目名

每一刀结束后必须做：

1. 定向 smoke
2. 独立 code-review
3. 通过后才进入下一刀

---

## 10. 验收标准

本 spec 完成后的实现必须满足：

1. Dispatch 成功后，run-scoped registry 能完整记录 roster / handle / injection_mode / dispatched
2. Collect 不再依赖手工拼 registry，证据文件与 registry 状态保持一致
3. Council Round 2+ 只复用本 run 原句柄，不会跨 run 串号
4. Archive gate 继续按 report `run_id` 解析 registry，并保持 deterministic legacy bridge
5. 飞书标题不再出现不可读的临时目录 basename

---

## 11. 暂不解决的问题

- Prism 物理级隔离仍是后续阶段任务
- owner/lease 完整接管仍需单独设计
- legacy bridge 的最终移除时机，要等 scripted coordinator 全量接线并完成并发 acceptance 后再定
