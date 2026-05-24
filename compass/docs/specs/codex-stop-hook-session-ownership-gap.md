# Codex Stop Hook Session Ownership Gap

> 定位：给负责开发的会话阅读的缺陷交接文档。本文记录一次真实 Codex hook 交互暴露出的会话归属问题，供后续修复 RedCap Codex hook 策略时使用。
>
> 本文不是 runtime authority；真正的实现权威仍应落在 `.codex/hooks.json`、hook wrapper、session runtime state、acceptance 和相关 checker 中。

## 1. 背景

RedCap 已经接入 Codex 官方 lifecycle hooks candidate，并在本仓库中配置了 `SessionStart`、`PreToolUse` 和 `Stop` 相关 wrapper。这个方向是合理的：RedCap 需要在 Codex 生命周期节点里恢复任务锚点、执行安全护栏，并避免任务在 closeout 未完成时被口头宣称完成。

但一次真实使用暴露出一个边界：`Stop` hook 本身会在每轮结束时触发，而 RedCap 当前的 Stop handler 会查看 workspace 中是否存在 pending closeout。只要同一 RedCap 工作区里还有未收尾任务，即使当前会话只是和用户做机制探讨，也可能被 hook continuation 拉回 closeout 流程。

这说明当前 Codex hook 策略还停留在 workspace-level guard，缺少 session/thread-level ownership 判断。

## 2. 真实现象

当时同一工作区里存在两个会话：

- 会话 A：正在推进 `redcap-human-chat-summary-surface-hardening`，并留下 pending closeout。
- 会话 B：只是在和用户探讨 RedCap Codex hook 的会话隔离问题。

会话 B 每次普通回复结束后，Codex Stop hook 都注入类似提示：

```text
RedCap still has pending closeout work. Continue one more pass:
resolve the pending closure or explicitly record why it remains blocked.
```

结果是，会话 B 被迫解释或尝试处理会话 A 的 pending closeout。用户明确指出这不合理：探讨性交流不应该触发另一个会话的工作流收尾。

后续另一个会话完成 closeout 后，`pending_closure_exists=false`、`receipt_exists=true`，该现象才停止。这进一步证明触发原因不是当前讨论内容，而是 workspace-level pending closure 被误认为当前会话义务。

## 3. 根因

根因不是 Codex 官方 Stop hook 错误。官方 Stop hook 的语义就是回合结束时触发，而且 Stop matcher 当前不能按任务意图过滤。因此 RedCap 必须在自己的 hook handler 里做归属判断。

当前缺口可以概括为：

> RedCap 共享了 workspace 事实，但没有隔离 session 驱动权。

需要区分三层状态：

| 层级 | 应共享吗 | 作用 | 当前问题 |
|---|---:|---|---|
| workspace-level | 是 | 仓库里是否存在 pending closeout、当前 `.dev-task.md` 是什么 | 被直接当成当前会话义务 |
| task-level | 有条件共享 | `task_id + confirmed_hash` 的 closeout 是否完成 | 没有检查当前会话是否绑定该任务 |
| session/thread-level | 必须隔离 | 当前 Codex thread 是否拥有该任务的执行/收尾权 | Stop hook 缺少这一层判断 |

因此，会话 B 看到会话 A 的 pending closeout 是合理的；但会话 B 被要求继续处理它，是不合理的。

## 4. 应有行为

### 4.1 当前 session 绑定该任务

如果当前 Codex session/thread 明确绑定了 pending closeout 对应的 `task_id + confirmed_hash`，并且当前 intent 处于 execution / closeout 模式，Stop hook 可以返回 continuation。

允许行为：

- 要求补 spec-check、diagnose、receipt。
- 阻止口头 completed。
- 触发 closeout audit 或 closeout runtime。

### 4.2 当前 session 是探讨或问答

如果当前回合只是讨论、解释、状态询问、方案草拟，Stop hook 不应驱动 closeout。

允许行为：

- 静默通过。
- 或记录 advisory：workspace has unrelated pending closure。

禁止行为：

- 返回 continuation。
- 修改 `.dev-task.md` 或 closeout runtime。
- stage / commit / 生成 receipt。
- 干扰另一个正在开发的会话。

### 4.3 无法证明归属

如果 hook 无法证明当前 session/thread 拥有 pending closeout 对应任务，默认不得 continuation。最多写入轻量 advisory 日志，提示存在 workspace-level pending closeout。

默认策略应为：

```text
unknown ownership -> do not drive closeout
```

这条规则比“看见 pending 就继续”更安全，因为它避免跨会话劫持。

## 5. 建议改造方向

### 5.1 增加 session ownership 记录

在 RedCap runtime state 中记录：

- session/thread id。
- host name。
- task id。
- confirmed hash。
- active slice。
- intent mode：`execution`、`closeout`、`discussion`、`question`、`unknown`。
- owner state：`claimed`、`advisory-only`、`unowned`。

Codex.app 能拿到的 thread/session 标识可能有限；若拿不到稳定 ID，应使用保守降级：只允许 advisory，不允许 continuation。

### 5.2 Stop hook 先做 ownership gate

Stop handler 的顺序应调整为：

1. 读取 workspace pending closeout。
2. 读取当前 session ownership。
3. 判断当前 session 是否绑定该 `task_id + confirmed_hash`。
4. 判断当前 intent 是否允许执行收尾。
5. 只有同时满足绑定和 intent，才允许 continuation。

伪代码：

```text
if no pending closeout:
    pass

if current_session owns pending task and intent in execution/closeout:
    continuation

else:
    advisory only
```

### 5.3 区分“提醒”和“驱动”

RedCap 可以提醒当前 workspace 有未收尾任务，但提醒不是驱动。提醒不应该造成当前会话进入执行流，也不应该要求用户机械回复“继续”。

建议输出分级：

- `pass`：无事发生。
- `advisory`：记录存在非本会话 pending closeout，但不打断用户。
- `continue`：当前会话拥有任务，且必须继续完成收尾。
- `blocked`：当前会话拥有任务，但缺少必要人工决策。

### 5.4 防止同一 workspace 多会话相互污染

同一 RedCap workspace 允许多个会话存在，但同一 task closeout 只能由 owner session 驱动。其他会话只能读取状态，不能接管，除非显式执行 rescue / reassign。

建议新增两类动作：

- `claim-current-task`：当前 session 显式接管任务。
- `release-current-task`：当前 session 完成或放弃任务归属。

rescue 场景必须留下可审计记录，不能静默抢占。

## 6. 建议验收用例

### 6.1 同会话 pending closeout

场景：当前 session 创建任务、执行修改、留下 pending closeout。

期望：Stop hook 可以 continuation，要求继续完成收尾。

### 6.2 跨会话 pending closeout

场景：会话 A 留下 pending closeout；会话 B 只做问答或机制讨论。

期望：会话 B 不被 continuation 劫持；最多写 advisory。

### 6.3 无 session id

场景：Codex.app 或某宿主无法提供稳定 session id。

期望：默认 advisory-only，不允许驱动 closeout。

### 6.4 显式 rescue

场景：用户明确要求当前会话接管另一个会话的未收尾任务。

期望：只有显式 rescue / reassign 成功后，当前会话才可以 continuation。

### 6.5 当前会话只是状态查询

场景：用户问“现在任务到哪了”“还有什么没完成”。

期望：只回答状态，不自动进入 closeout。

## 7. 风险边界

这项修复不应削弱 RedCap 的未完成任务保护能力。目标不是关闭 Stop hook，而是让 Stop hook 只驱动它真正拥有的任务。

必须避免两个极端：

- 过强：任何 pending closeout 都打断所有会话。
- 过弱：真实执行会话可以绕过 pending closeout。

正确目标是：

> 严格保护当前任务，温和提示其他任务，禁止跨会话劫持。

## 8. 建议落地点

优先检查这些位置：

- `.codex/hooks.json`
- Codex Stop hook wrapper。
- `compass/tools/redcap-layerb-task-complete-guard.sh`
- `compass/tools/redcap-layerb-closeout-runtime.sh`
- `compass/tools/redcap-current-status.sh`
- `compass/tools/redcap-diagnose.sh`
- closeout runtime state 目录。
- Codex live marker E2E / acceptance 用例。

实现时应新增一个独立任务，不要把它混进“聊天汇报人类可读性修复”任务里。

## 9. 建议任务名

建议新增任务：

```text
redcap-codex-stop-hook-session-ownership-gate
```

建议目标：

```text
修复 Codex Stop hook 只按 workspace pending closeout 触发 continuation 的问题；
让 Stop hook 在驱动 closeout 前先证明当前 session/thread 拥有该 task_id + confirmed_hash；
跨会话或探讨型会话只能 advisory，不得 continuation。
```
