# 任务完成报告：修复 redcap revive 外部工作区边界盲区

**报告日期**：2026-05-28
**执行者**：Cap（Codex.app 主执行）
**报告版本**：v0.2

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：已复现并修复 `redcap revive` 在外部项目中可能回落到 RedCap 自身任务卡的问题；外部 workspace 的默认、`--workspace`、`--task-file` 三种 revive 路径已经进入边界检查。

### 0.2 上一步完成的是

- 上一步完成的是：完成语义硬门已经收口；本轮承接父任务线，在进入 `RASG-027` 之前先处理棱镜确认的 runtime/workspace 边界缺陷。

### 0.3 下一步计划做的是

- 下一步计划做的是：完成 targeted Prism 复核和总回归后，把 `HOTFIX-REVIVE-WORKSPACE-BOUNDARY` 标记为已完成，并回到 `RASG-027` 自我升级实体化。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：完成语义硬门 -> 前置热修 `redcap revive` 边界 -> `RASG-027` Evolution Factory 主动候选生产线 -> `RASG-030` 反空转方法论 -> `RASG-028` 公共武器库批量蒸馏 -> `RASG-029` 工程目录最终收敛。
- 当前所在位置：前置热修已经实现，棱镜复核和总回归已通过；仍在等待 closeout receipt。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮不涉及 secret、不可恢复删除、正式发布或产品授权决策；如果后续回归发现超出 revive 边界的真实阻塞，会单独升级。

## 一、需求背景

另一个会话指出：`bin/redcap` 在执行 `revive` 时虽然算出了外部 workspace 的 `.dev-task.md`，但没有把它传给 `revive-cap.sh`。`revive-cap.sh` 没收到任务卡时，会默认使用 RedCap 自己仓库里的 `.dev-task.md`。

这会让一个外部项目执行 `redcap revive` 时，看起来是在复活外部项目，实际却可能读取 RedCap 自己的任务状态。对用户来说，后果是“我要接管 A 项目，工具却把 RedCap 自己的开发现场混进来了”。

## 二、方案讨论

本轮采用最小修复，不扩大成 CLI 重构：

- `redcap revive` 现在复用统一的 workspace/task-file 解析逻辑。
- `redcap revive` 会显式把解析后的任务卡传给 `revive-cap.sh`。
- runtime/workspace 边界政策把 `revive` 和 `summary` 都列入 workspace-aware 命令，并同步公开契约镜像。
- 边界检查新增外部项目冒烟测试，覆盖默认 revive、`--workspace`、`--task-file`、`REDCAP_WORKSPACE`、`REDCAP_TASK_FILE`。
- 棱镜复核指出测试里有旧任务 id 硬编码风险；已改为动态读取 runtime 任务卡，避免未来主线变更后漏报。

## 三、落地结果

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 人话解释 | 本轮作用 |
|---|---|---|
| runtime/workspace 边界 | RedCap 工具自身所在目录和被管理项目目录之间的分界线 | 防止外部项目任务状态被 RedCap 自身任务卡污染 |
| revive | RedCap 的复活/初始化入口 | 本轮修复对象 |
| task file | 当前任务卡 `.dev-task.md` | 必须来自被管理项目，而不是误用 runtime 仓库 |
| boundary check | 边界回归检查 | 用临时外部项目证明 CLI 没有读错任务卡 |

### 3.2 变更摘要

| 变更 | 目的 | 状态 |
|---|---|---|
| `bin/redcap` revive 分支复用统一解析 | 让 revive 支持外部 workspace/task-file | 已实现 |
| runtime/workspace 边界政策更新 | 让政策覆盖 revive 和 summary | 已实现 |
| boundary checker 冒烟测试扩展 | 用外部临时项目证明 revive/summary 不读错任务卡 | 已实现 |
| 公开契约镜像同步 | 让 `assets/references/**` 与 `contracts/public/**` 的 runtime/workspace 边界一致 | 已实现 |
| 任务树登记与人类导读同步 | 确保热修不会被误认为 RASG-027 本体完成 | 已实现 |

## 四、人工审核要点

当前不需要 Norven 人工介入。本轮没有触发 secret、不可恢复删除、正式发布、包名、registry、license 或产品授权决策。

## 五、验证结果

| 验收项 | 命令或证据 | 结果 |
|---|---|---|
| bug 复现 | 外部临时项目执行旧 `redcap --trace revive`，实际 current-status 读取 `completion-semantics-hard-gate` | 已复现 |
| targeted boundary check | `bash compass/tools/redcap-runtime-workspace-boundary-check.sh` | 通过 |
| acceptance 单项 | `bash compass/tools/redcap-multi-session-acceptance.sh runtime-workspace-boundary-check` | 通过 |
| 公开契约镜像 | `bash compass/tools/redcap-r1-contract-mirror-apply-preflight-subset-check.sh` 与 `bash compass/tools/redcap-r1-contract-mirror-bounded-copy-first-apply-check.sh` | 通过 |
| 全量 spec | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| 深入诊断 | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 通过 |
| 棱镜验收 | `prism/runs/20260528-hotfix-revive-workspace-boundary`，Kimi + Claude Code | 通过，无 blocker |
| 任务树检查 | `bash compass/tools/redcap-backlog-check.sh strict .dev-task.md` 与 `bash compass/tools/redcap-architecture-smell-governance-check.sh` | 通过 |

### 5.3 closeout runtime / receipt

| 项目 | 状态 |
|---|---|
| closeout receipt | 无 |
| 说明 | 本报告先作为实现与验收底稿；正式 receipt 正在由 closeout runtime 生成。 |

### 5.4 完成等级（禁止混报）

| 层级 | 状态 | 说明 |
|---|---|---|
| 已实现 | 是 | revive 参数传递与边界检查已实现。 |
| 已自检 | 是 | targeted boundary check 与 acceptance 单项已通过。 |
| 已独立验收 | 是 | Kimi 与 Claude Code 均给出 pass；Kimi 指出的测试缺口已修复并重跑。 |
| 已正式完成 | 否 | closeout receipt 尚未生成，不能声明正式完成。 |

## 六、遗留问题与下一步

### 6.1 不宣称的内容

- 不宣称 `RASG-027` 自我升级实体化已完成。
- 不宣称 `RASG-028` 公共武器库扩容已完成。
- 不宣称 `RASG-029` 工程目录最终收敛已完成。
- 不宣称 `RASG-030` 反空转方法论已完成。
- 不宣称 RedCap 已可正式发布。

### 6.2 后续动作

- 生成 closeout receipt。
- 将 `HOTFIX-REVIVE-WORKSPACE-BOUNDARY` 标记为完成。
- 自动回到 `RASG-027`，不等待 Norven 机械回复“继续”。

## 七、经验沉淀

无新增候选：本轮本身会成为 `RASG-027` 的早期真实 harvest 样本；在 `RASG-027` 生产线尚未实现前，不手写新的 Evolution candidate 冒充自动候选。reason=hotfix evidence preserved for later active harvest.

## 八、附录

- 棱镜运行：`prism/runs/20260528-hotfix-revive-workspace-boundary`
- 任务报告：`assets/docs/task-reports/2026-05-28-hotfix-revive-workspace-boundary.md`
- 当前任务卡：`.dev-task.md`
