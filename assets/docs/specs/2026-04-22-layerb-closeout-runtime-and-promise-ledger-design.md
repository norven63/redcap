# Layer B 统一 Closeout Runtime / 承诺账本 / Receipt / Rescue 设计

**日期**：2026-04-22  
**主题**：把 RedCap Layer B 的终态收口从“多脚本分散执行”升级为“统一 runtime 驱动的可审计闭环”  
**状态**：设计已锁定，进入实现

---

## 1. 问题定义

当前 Layer B 已经有：

- `.dev-task.md` 作为当前任务真相源
- `pending-closure` 作为未清义务真相源
- `closure-ledger` 作为闭环事务日志
- `task report` 作为闭环证据
- `on-complete / session-end` 作为收尾脚本

但它们还没有被一个**统一的终态 runtime** 串起来。结果是：

1. 任务可以在“协议定义清楚、检查器也绿”的情况下，仍然发生**部分兑现 + 过早收口**。
2. Agent 在执行中自己追加的承诺，仍可能只活在对话里，不进入控制面。
3. 即使 `notify` 已经是 closure transaction 的一部分，也可能因为没有统一 runtime 触发而漏掉。
4. 缺少 Distill 那种 receipt / audit-open 风格的终态收据与补救审计。

---

## 2. 设计目标

本次设计只解决 Layer B 的**终态收口控制面**，不再平行发明第二套状态机。

### 2.1 必须做到

1. 提供一个统一的 Layer B closeout runtime 入口。
2. 把 Agent 自己追加的承诺落成**承诺账本**，closeout 时强制核对。
3. 任务终态必须留下**summary + receipt + audit record**。
4. stop / session-end / diagnose 至少要有一条路径能执行 **rescue audit**。
5. 旧资产必须按“真相源 / 证据 / 镜像 / 视图”分层处理，而不是一刀切。

### 2.2 明确不做

1. 不删除 `.dev-task.md`、`pending-closure`、`closure-ledger`、task report 这几类已有资产。
2. 不把 Layer B 重构成 Layer A 式单一 `state.yaml` FSM。
3. 不对宿主 reply path 做虚假的 100% 承诺；Codex 等弱 Hook 宿主仍需诚实标边界。

---

## 3. 核心方案

### 3.1 新增统一入口：Layer B Closeout Runtime

新增一套统一 runtime：

- `compass/tools/redcap-layerb-closeout-runtime.py`
- `compass/tools/redcap-layerb-closeout-runtime.sh`（shell 薄入口）
- `closeout-cap.sh`（仓库根目录短命令）

其中：

- `.py` 负责状态、receipt、summary、promise ledger、audit-open 的确定性逻辑
- `.sh` 负责兼容 shell / hook / host 场景
- 根目录短命令负责给人类和 Agent 一个统一、可记忆的 closeout 入口

### 3.2 runtime 管理的资产

统一 runtime 不替代旧账本，而是新增一层 closeout 运行态资产：

- `closeout-state/`：当前任务 closeout runtime 状态
- `closeout-receipts/`：终态 receipt
- `closeout-summaries/`：终态摘要
- `closeout-audits/`：audit-open / rescue 审计记录
- `promise-ledger/`：承诺账本

这些资产与现有治理账本的关系如下：

| 资产 | 类型 | 角色 |
| --- | --- | --- |
| `.dev-task.md` | 当前任务真相源 | 记录当前任务边界与承诺源文本 |
| `promise-ledger` | 运行时派生账本 | 把 `.dev-task.md` 中的承诺转成可核对状态 |
| `pending-closure` | 未清义务真相源 | 记录当前 confirmed hash 下仍欠什么 |
| `closure-ledger` | append-only 事务日志 | 记录历史上发生过什么 |
| `closeout-receipt` | 终态收据 | 证明这次 closeout 真的形成闭环 |
| `closeout-summary` | 用户可读摘要 | 给人/通知系统消费的终态摘要 |
| `closeout-audit` | rescue 证据 | 证明漏收尾已被显性化或补救 |

### 3.3 承诺账本来源

承诺账本不从对话抓取，而从 `.dev-task.md` 的固定段读取：

- `## 执行承诺账本`

规则：

1. 这里专门记录 **Agent 自己追加的执行承诺**
2. 用户原始需求与已确认需求仍留在原段，不混用
3. closeout runtime 每次执行前都先把该段同步到 `promise-ledger`
4. 任一承诺仍未完成时，receipt 不得标记为 `completed`

### 3.4 closeout runtime 的完成路径

`complete` 的标准路径：

1. 解析 `.dev-task.md` 的 task identity
2. 同步承诺账本
3. 解析 baseline / current head / report anchor
4. 调用现有 `redcap-on-complete.sh`
5. 调用现有 `redcap-layerB-session-end.sh`
6. 判断：
   - `pending closure` 是否已清
   - 承诺账本是否全部完成
   - report / ledger / notify 是否可证明发生
7. 若全部满足：
   - 生成 closeout summary
   - 生成 closeout receipt
   - runtime state 标记 completed
8. 若任一步失败：
   - 保留/重写 pending closure
   - 记录 audit / receipt failure
   - runtime state 标记 blocked 或 incomplete

### 3.5 rescue audit 的职责

`audit-open` 不负责“偷偷帮你算完成”，它负责两类事情：

1. **repair-receipt**
   - 当前任务其实已经完成了 `on-complete + session-end`
   - `pending closure` 已清
   - 只是 receipt / summary 缺失  
   这时允许补写 receipt / summary

2. **block-and-alert**
   - 终态已经开始，但仍有未清 redline / promise / notify / report gap  
   这时不得伪造 receipt，而要：
   - 重写 pending closure
   - 追加 closure ledger / audit 证据
   - 必要时发出补偿告警

也就是说，rescue audit 的职责不是“自动完成”，而是：

- **能补收据时补收据**
- **不能补收据时补 blocker**

本 tranche 选择的强入口是：

- `redcap-diagnose.sh` → `redcap-layerb-closeout-runtime.sh audit-open --mode diagnose`

原因：

- diagnose 已经是接盘与终局前的高频体检面
- 相比直接塞进 `session-end`，不会和正常 `complete -> session-end -> write receipt` 路径互相踩踏
- 一旦用户或宿主忘记显式执行 `./closeout-cap.sh complete`，后续 diagnose 仍能补收据或补 blocker

---

## 4. 旧资产处理策略

### 4.1 保留为历史证据

这些资产继续保留，不做批量迁移：

- 历史 task report
- 既有 `pending-closure/*.state`
- 既有 `closure-ledger/*.log`
- 既有 Prism report / run evidence

原因：它们是历史证据，不应为了新机制“看起来更统一”而重写。

### 4.2 翻译到新机制的权威入口

这些地方必须改口径：

- `README.md`
- `ARCHITECTURE.md`
- `compass/CONTRIBUTING.md`
- `references/runtime-memory-architecture.md`

改法不是删旧说明，而是明确：

- 旧脚本仍然存在
- 但终态收口现在以统一 closeout runtime 为主入口
- `on-complete / session-end` 退居为 runtime 内部阶段，而不是用户/Agent 自己拼接的主入口

### 4.3 可删除或降级的对象

本 tranche 不做大规模删除，只允许两种动作：

1. 将旧说明降级成“内部阶段 / legacy path / historical note”
2. 删除明确重复、且已被新入口完全覆盖的单薄文档说明

删除不是默认目标，**口径收口才是目标**。

---

## 5. 与 Distill 的关系

这次不是“照抄 Distill”，而是吸收它最关键的两点：

1. **终态必须有 receipt**
2. **漏收尾必须有 audit-open rescue**

RedCap 与 Distill 的分工差异仍保留：

- Distill：统一 closeout lifecycle 更强
- RedCap：当前任务控制面与多宿主治理更强

本次设计的目标，就是把 Distill 的终态收口思想嫁接到 RedCap 的 Layer B 控制面上。

---

## 6. 验收标准

实现完成后，至少要能证明：

1. 若承诺账本未清，closeout receipt 不能被写成 completed
2. 若 `notify` 或 report 未闭合，runtime 会保留 blocker 而不是假完成
3. 若只是 receipt 缺失，`audit-open` 能补写 receipt
4. 若终态链未真正完成，`audit-open` 会补 blocker / audit，而不是补假收据
5. `closeout-cap.sh` 能成为统一的 Layer B 人类/Agent 收尾入口

---

## 7. 下一步实现顺序

1. 新增 closeout runtime 与 promise ledger
2. 把 `closeout-cap.sh` 接到 runtime
3. 将 diagnose / current-status / 文档入口接入 runtime 状态面
   - 其中 diagnose 负责当前 tranche 的 rescue 强入口
4. 执行回归与棱镜独立审视
5. 最后再收口 task report / lessons / 入口口径
