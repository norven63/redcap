# 长任务父目标合同

长任务父目标合同用于决定一个任务是否需要进入重型持续推进模式。策略模板本身不是任务执行器，也不替代 Loom（角色化工程工作流）、E2E（端到端验收）、生命周期包或最终棱镜（异构 AI 评审助手）复核；真实入口由 `long-task start`（启动长任务运行）创建 `active_run`（真实运行合同）。

## 设计结论

Codex（当前宿主工具）的目标状态如果是 blocked（受阻），不自动等于 RedCap 工程失败，也不要求先清除状态才能开启新任务。它只说明这个外部目标不能继续被当作可靠的活跃父目标。RedCap 需要在 1 轮内触发 Cap（当前会话承载的执行主体）仲裁，说明继续、停止或改用 RedCap 内部合同的理由。

## 进入条件

长任务模式默认关闭。只有出现以下任一情况才允许启用：

- 用户明确要求长时间持续推进。
- RedCap 自开发达到中风险或更高。
- 外部 E2E、发布验收或真实交付验证。
- Loom 多角色协作。
- 连续 3 次或更多同类失败需要修复。
- 涉及 2 个或更多独立运行时目录、仓库边界或项目边界。

低风险回答、一步小修、纯状态盘点、纯解释、没有跨角色和没有 E2E 的任务应走 fast-path（轻量路径）。

## 停止条件

长任务模式不是无限循环。出现以下情况必须停止自动推进或交给 Cap 仲裁：

- 达到默认 5 轮上限。
- 同一阻塞连续 2 轮重复。
- 连续 2 轮没有父目标推进差量。
- 源码签名和证据签名都没有变化，却继续重跑。
- 收敛诊断设置 `auto_rerun_allowed=false`。
- 涉及产品取舍、密钥、账号、发布、破坏性操作或其他需要 Norven 决策的问题。

## 机器检查

命令：

```bash
runtime/bin/redcap long-task decide --task "修复 RedCap 长任务入口" --risk-level medium
runtime/bin/redcap long-task check --packet assets/contracts/long-task-contract.json
runtime/bin/redcap long-task start --task "持续推进 RedCap 自开发 E2E 巡检" --risk-level medium --run-dir /tmp/redcap-long-task-run
runtime/bin/redcap long-task record --packet /tmp/redcap-long-task-run/redcap-long-task-active-run.json --status failed --objective-delta "本轮发现结构性问题并进入失败回流" --action-evidence /tmp/redcap-long-task-run/evidence.txt --blocker-signature structural-gap
runtime/bin/redcap long-task complete --packet /tmp/redcap-long-task-run/redcap-long-task-active-run.json --outcome completed --final-objective-delta "终止验收证据通过，当前 active_run 可以关闭" --completion-evidence /tmp/redcap-long-task-run/final-receipt.json --final-summary "当前 active_run 完成；不代表 RedCap 完整复活"
runtime/bin/redcap long-task self-check
```

总检查会调用合同检查，防止该能力停留在文档层。

## 模板和真实运行

`contract_kind`（合同种类）必须显式写出：

- `policy_template`（策略模板）：允许 `iteration_ledger`（迭代账本）为空，只能说明规则，不能证明任务已经运行完成。
- `active_run`（真实运行）：必须有非空 `iteration_ledger`、`failure_backlog`（失败回流账本）、每轮 `action_evidence`（动作证据）、`objective_delta`（父目标推进差量）、`source_signature`（源码签名）和 `evidence_signature`（证据签名）。

`long-task start` 先运行 `decide`（入口判断）。如果任务属于 fast-path（轻量路径），只写决策收据，不创建重型运行包；如果任务进入 enabled（长任务模式），必须写出 `active_run` 并立即运行 `long-task check`，否则入口失败。`start` 只证明长任务入口已经接通，不证明父任务已经完成。

`long-task record`（记录长任务迭代）用于把入口继续推进到至少一轮行为迭代。它必须追加 `iteration_ledger`，写入非空 `action_evidence`、`objective_delta`、`source_signature` 和 `evidence_signature`，并根据状态更新 `failure_backlog`。`action_evidence` 必须指向真实存在的文件，文件不能过短，也不能只是重复填充字符；否则会被拒绝。因此能力覆盖不能只看“start 创建了文件”，还要看入口能否驱动后续迭代并保持合同有效。

`long-task complete`（完成长任务运行）是唯一允许把 `active_run` 切入终止态的命令。它必须写入 `completion_boundary`（完成边界），要求 `completion_evidence` 指向真实证据文件，并且证据不能是低置信的随机填充。`record` 永远不能替代 `complete`；没有 `complete` 的 `active_run` 只能被视为仍在运行、受阻或等待仲裁，不能被描述成父任务完成。

## 完成边界

`capability_coverage`（能力覆盖）不能由执行者手填“已完成层”。检查器会根据源码、命令入口、总检查接入、证据白名单和棱镜评审文件实际存在性推导覆盖层。只有所有必需层都由工具推导存在时，才允许把当前能力声明为可完成；否则只能汇报阶段状态和未覆盖边界。
