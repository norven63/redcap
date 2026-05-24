# Layer B 状态机工作模式重构

## 1. 目标

把 RedCap Layer B 从“协议上有状态机、实现上只有 closeout 尾段较像统一 runtime”的状态，重构成：

1. 状态、转移、gate、证据都能被机器检查。
2. 作者不能再单独宣布 completed。
3. 棱镜成为 completed 的默认独立验收前置门。
4. receipt 成为唯一正式完工凭证。

## 2. 这次要解决的病灶

### 2.1 表面问题

- 作者在 live 任务尚未 formal closeout 时提前汇报完成。
- 用户必须靠嗅探、盘问和直觉才能发现任务其实没真正闭环。
- 状态面多处为绿，但 receipt 仍缺失。

### 2.2 底层暗疾

- Layer B 的工作模式并未被单一 FSM 真正接管。
- 执行中新增承诺会被记录，但完成判定没有把独立验收与 receipt 绑成硬门。
- 作者、自检、独立验收、正式完成这 4 个层级没有强制拆开。

## 3. 新工作模式

Layer B 的主骨架仍然使用：

- `REANCHORED`
- `TASK_LOCKED`
- `EXECUTING`
- `REVIEW_PENDING`
- `CLOSEOUT_PENDING`
- `CLOSED`
- `BLOCKED`

但本次重构要求：

1. `REVIEW_PENDING` 必须真实包含“棱镜默认独立验收”。
2. `CLOSEOUT_PENDING` 必须被统一 closeout runtime 接管。
3. `CLOSED` 只能由“Prism acceptance + receipt + pending closure clear”共同达成。
4. Prism acceptance 必须绑定到当前 `task_id + confirmed_hash + run_id`，不得复用旧 run。
5. rescue / audit-open 写回 blocker 时必须保留既有 redlines，不得覆盖成泛化 blocker。

## 4. 核心机制

### 4.1 Layer B FSM 状态面

新增 machine-readable FSM 状态面，由 `redcap-layerb-fsm.sh/.py` 输出：

- 当前生命周期状态
- 独立验收状态
- 正式完成状态（receipt / pending closure / 承诺账本）

### 4.2 Prism acceptance gate

新增 `redcap-prism-acceptance-check.sh/.py`：

- 读取 `.dev-task.md` 的 `acceptance_policy` 与 `prism_acceptance_run`
- 校验 `session-registry.yaml`
- 校验 `acceptance-binding.json` 中的 `task_id + confirmed_hash + run_id`
- 校验至少 2 个 responded/schema_ok reviewer
- 校验至少 2 个模型家族
- 校验 `parsed.json` 中无真实 blockers

没有通过 Prism acceptance，不得 completed。

### 4.3 Closeout runtime 改造

`redcap-layerb-closeout-runtime.py` 在 `complete` 阶段新增硬门：

1. 承诺账本必须清零
2. Prism acceptance 必须通过
3. `on-complete` / `session-end` 必须成功
4. 才允许写 receipt
5. 若 audit-open / pending 重写发生，只能追加新 blocker，不得抹掉旧 blocker

### 4.4 Diagnose / current-status 改造

- `current-status` 新增 `## Layer B FSM`
- `diagnose` 新增 `layerb-fsm-check`

## 5. 旧资产处理

### 保留

- 历史 task reports
- 旧 pending closure / closure-ledger
- Prism 历史运行和报告证据

### 翻译

- README
- ARCHITECTURE
- CONTRIBUTING / CONTRIBUTING.core
- runtime-memory / task-report-template
- execution-guarantees

### 不做

- 不批量删除历史证据
- 不把旧报告重写成新格式

## 6. 验收

本 tranche 的验收分 3 层：

1. 机器检查：`spec-check / diagnose / layerb-fsm-check / hook-contract`
2. acceptance：新增 FSM / Prism acceptance 相关 case
3. 棱镜独立审视：至少一轮 lightweight independent review
4. acceptance binding 缺失必须失败；binding 存在且 blocker-free 才允许 acceptance pass
5. audit-open preserve-blockers 必须覆盖 `review,task-report -> review,task-report,closeout-runtime`

## 7. 完成定义

只有同时满足下面 4 条，当前任务才允许汇报 completed：

1. 承诺账本清零
2. Prism acceptance 通过
3. pending closure 清零
4. receipt 已生成
