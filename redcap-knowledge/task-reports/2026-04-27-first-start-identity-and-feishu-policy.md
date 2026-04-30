# 任务完成报告：首次启动身份初始化与飞书通知策略收敛

**报告日期**：2026-04-27
**执行者**：Cap（Codex.app）
**报告版本**：v1.2（2026-04-28 飞书 profile 修复后收口复验）

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P2-4 的 repo-owned 链路已经落地：`revive/install` 会初始化本地用户/Agent 状态面，并且 RedCap 官方飞书通知路径被收敛到单一账号策略。
- 详情：新增 `references/user-agent-identity-policy.json` 与 `redcap-user-agent-identity.sh`，把 Norven 用户命名空间、Cap agent 摘要、ignored 本地状态和 `shared-knowledge/users/Norven` 串进 installer。新增 `references/feishu-notification-policy.json` 与检查器，阻止 webhook、旧 profile、followup watcher 和重复 success 通知回退。

### 0.2 上一步完成的是

- 上一步完成的是：P2-5 把“中插需求重排决策可见化”做成强门，要求当前这类中插约束先入账、再重排、再执行。
- 本轮遵守该机制：飞书账号约束被合并进 P2-4，而不是单独抢占后误报全局完成。

### 0.3 下一步计划做的是

- 下一步计划做的是：继续父任务中未完成的 P3-1 / P3-2 等后续治理；飞书真实发送在用户补充正确 secret 后已恢复。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：任务卡重锚定 → 身份初始化 policy/script → 飞书单通道 policy/checker → install/spec/diagnose/acceptance 接线 → Prism review → targeted/full acceptance 复验 → closeout receipt。
- 当前所在位置：`redcap-system-migration-parent / P2-4 / first-start-identity-feishu-policy`，repo-owned 实现与回归已完成，等待最终 receipt/提交收口。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 好的，了解，我不中断你和棱镜团队的计划节奏，你们配合好，稳步推进，务必做好符合工程规范的实现落地。
>
> 另外，中插一个小问题：现在飞书通知用的app id是不是非cli_a9579f5b12219bb5这个账号，我只能通过通过这个账号才能获取通知，其他的都不行。所以后续飞书通知的逻辑都按照围绕“cli_a9579f5b12219bb5”来实现的逻辑，其余通知实现逻辑全部删除，以后顶多是增加或者变更app id，但实现逻辑不变。还有，飞书通知只有在“节点汇报”、“需要寻求我人工介入”时而引发的中断操作才执行，其余节点无需反复发送通知

### 1.2 触发背景

P2-4 原本是“首次启动初始化用户与 AI Agent 信息”。用户中插的飞书要求本质上也是首次启动/本地安装状态面的一部分：如果本地通知账号仍然漂移，`revive/install` 即使跑过，也不能保证后续通知走到用户能收到的账号。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 继续主线 P2-4，并吸收飞书唯一账号与低频触发约束 |
| 已覆盖 | 用户/Agent 本地状态初始化、Norven 命名空间、飞书单通道策略、低频触发策略、spec/diagnose/acceptance 接线 |
| 未覆盖/延期 | 不做目录物理大迁移、公共库历史内容迁移、GraphRAG/RAG 研究、正式 npm/CLI 发布 |
| 用户可见边界 | RedCap 已禁止走旧账号或 webhook；2026-04-28 用户补充正确 secret 后，本机 `cli_a9579f5b12219bb5` profile 已注册并通过 node-report 真实发送验证 |

---

## 二、方案讨论

### 2.1 方案选项

| 方案 | 描述 | 优点 | 缺点 | 结论 |
|---|---|---|---|---|
| A | 只改本地 ignored `feishu-config.json` | 快 | 仓库机制仍会回退，其他机器不受保障 | 拒绝 |
| B | 只在文档写“记得用 cli_a957...” | 低成本 | 仍依赖 Agent 记忆，不能拦旧 webhook/profile | 拒绝 |
| C | 建 policy + checker + notifier 改造 + install/spec/diagnose 接线 | 可复验、可回归、可迁移 | 改动面更大，需要更新 acceptance | 采纳 |

### 2.2 决策结果

| 需求 | 采纳方案 | 决策理由 | 决策方 |
|---|---|---|---|
| 首启身份初始化 | policy + init/check script + installer 接线 | 私人 identity 不能入仓，但本地状态面必须可复验 | CAP_DECIDE |
| 飞书唯一账号 | 单一 lark-cli DM profile policy | 未来换账号只改策略/配置，不再并存多套发送实现 | NORVEN_DECIDE + CAP_IMPLEMENT |
| 通知频率 | node-report / manual-intervention 两类事件 | 保留关键可见性，避免每个内部节点刷屏 | NORVEN_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|---|---|---|
| `references/user-agent-identity-policy.json` | 新建 | 首次启动用户/Agent 身份状态策略 |
| `compass/tools/redcap-user-agent-identity.py/.sh` | 新建 | 初始化/校验 ignored 本地状态与 `users/Norven` 命名空间 |
| `compass/tools/redcap-install.sh` | 修改 | `revive-cap.sh` 链路中新增 user-agent-identity 初始化 |
| `references/feishu-notification-policy.json` | 新建 | 飞书唯一 profile 与低频触发策略 |
| `compass/tools/redcap-feishu-notification-policy-check.py/.sh` | 新建 | 检查旧 profile、webhook、followup、重复成功通知回退 |
| `compass/tools/feishu-notifier.py` | 修改 | 删除 webhook 生产发送分支，`notify` 只允许 `node-report` / `manual-intervention` |
| `compass/tools/redcap-on-complete.sh` | 修改 | 成功收口只发送一次 `node-report` |
| `compass/tools/redcap-layerB-session-end.sh` | 修改 | SessionEnd 默认不重复发 success；blocker 告警默认为 `manual-intervention` |
| `compass/tools/redcap-explore-notes-check.sh` | 修改 | 未归档探索笔记只做本地提醒，不再发飞书 |
| `compass/tools/redcap-spec-check.sh` / `redcap-diagnose.sh` | 修改 | 接入身份与飞书策略检查 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 新增/改造身份初始化、node-report 去重、人工介入窗口、webhook/旧 profile 拒绝用例；同步修复 full acceptance 中因通知默认策略变化暴露的 SessionEnd 成功通知、超时锁释放与 spec fixture 偏差 |
| `references/file-lookup-dictionary.*` / `execution-guarantees.json` / `runtime-memory-architecture.md` / `redcap-parent-task-ledger.md` | 修改 | 更新索引、执行保障、父任务状态与架构说明 |

### 3.2 技术实现要点

- 身份初始化不提交私人身份全文。`redcap-user-agent-identity.py init` 读取 `~/.cap/identity.md` 是否存在，只写 ignored 的 `compass/.workflow/user-agent-identity.json`，并确保 `shared-knowledge/users/Norven/.gitkeep` 与外部 `../redcap-arsenal/users/Norven/.gitkeep` 存在。
- 飞书通知改成策略驱动。`feishu-notifier.py` 读取 `references/feishu-notification-policy.json`，只接受 `lark_cli_dm`、`cli_a9579f5b12219bb5`、`node-report` / `manual-intervention`；旧 webhook 或旧 profile 直接失败。
- 通知去噪落到调用点。`on-complete` 负责最终节点汇报；`session-end` 只负责清账或 blocker 告警；`explore-notes` 不再发非阻塞飞书提醒。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|---|---|---|
| 用户/Agent 本地状态面 | `compass/.workflow/user-agent-identity.json` | 机器可读地记录“当前用户是谁、当前 Agent 是谁、共享库用户目录在哪里”，但不把私人 identity 内容入仓 |
| 单一生产路径 | `references/feishu-notification-policy.json` | RedCap 只允许一套飞书发送通道，避免多个 app/profile/webhook 并存导致通知跑错账号 |
| node-report | `feishu-notifier.py notify --window-type node-report` | 节点汇报类通知，例如最终 closeout 摘要 |
| manual-intervention | `feishu-notifier.py notify --window-type manual-intervention` / `ask` | 需要用户决策、授权或解除 blocker 时才触发的人工介入通知 |
| runtime limitation | task report / parent ledger | repo 能阻止 RedCap 走错账号，但不能凭空给本机 lark-cli 创建缺失的 app secret/profile |

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|---|---|---|---|
| 1 | 飞书真实发送 profile | 已在 2026-04-28 用用户补充的正确 secret 重新注册目标 profile，并通过 `feishu-notifier.py setup` 与 node-report notify 验证 | closed |
| 2 | 通知频率口径 | 本轮定义节点汇报 + 人工介入两类事件；若 Norven 认为某些事件也应通知，需要新增到 policy，而不是另写发送路径 | P1 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|---|---|---|
| 任务卡 PM Gate | `bash compass/tools/redcap-pm-gate-check.sh strict codex .dev-task.md` | 通过 |
| 意图覆盖 | `bash compass/tools/redcap-intent-coverage-check.sh .dev-task.md` | 通过 |
| 中插需求账本 | `bash compass/tools/redcap-change-intake-check.sh .dev-task.md` | 通过 |
| 身份初始化 | `bash compass/tools/redcap-user-agent-identity.sh init --host codex && bash compass/tools/redcap-user-agent-identity.sh check --local` | 通过 |
| 飞书策略检查 | `bash compass/tools/redcap-feishu-notification-policy-check.sh` | 通过 |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh user-agent-identity-init && bash compass/tools/redcap-multi-session-acceptance.sh feishu-duplex-window-queue && bash compass/tools/redcap-multi-session-acceptance.sh feishu-webhook-notify` | 通过 |
| Python 编译 | `python3 -m py_compile compass/tools/feishu-notifier.py compass/tools/redcap-user-agent-identity.py compass/tools/redcap-feishu-notification-policy-check.py` | 通过 |
| 复活/安装链路 | `./revive-cap.sh --host codex` | 通过 |
| spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| diagnose | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 通过 |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过 |
| 全量 acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh all` | 通过（最终第三轮全绿） |
| docs catalog | `bash compass/tools/redcap-docs-catalog.sh generate compass/docs/catalog.json && bash compass/tools/redcap-docs-catalog.sh check` | 通过 |
| legacy migration dry-run | `bash compass/tools/redcap-legacy-asset-migration-check.sh` | 通过 |
| 飞书 profile setup | `python3 compass/tools/feishu-notifier.py setup` | 通过 |
| 飞书真实 node-report | `python3 compass/tools/feishu-notifier.py notify ... --window-type node-report --no-background-watch` | 通过 |

### 5.1.1 全量 acceptance 期间发现并修复的问题

| 问题 | 根因 | 处理 |
|---|---|---|
| SessionEnd 成功通知用例仍期待默认发送 | 新策略要求普通 success 默认不重复发飞书，旧 acceptance 没显式打开节点汇报 | 用例改成显式 `REDCAP_SKIP_SESSION_END_SUCCESS_NOTIFY=0` 时验证 node-report，默认/closeout runtime 仍验证不发重复通知 |
| 通知超时锁释放用例等待 notifier 启动超时 | 同上，默认不发 success，测试探针等不到 notifier | 用例显式开启节点汇报后再验证超时释放 pending closure lock |
| spec-check fixture 缺少新强门 stub | `redcap-spec-check.sh` 新增 user/agent identity 与 Feishu policy 必备检查，旧 spec 生命周期 fixture 未同步 | spec fixture 补无关 stub，让 spec 生命周期测试继续专注验证 spec 规则，同时主仓真实 spec-check 仍跑真实检查 |
| install/revive 链路未直接跑飞书策略检查 | 最终 Kimi 复评发现文档承诺与 `redcap-install.sh` 实际链路不一致 | `redcap-install.sh` 新增 `feishu-notification-policy` run_check，`./revive-cap.sh --host codex` 已复验输出 `[ok] feishu-notification-policy` |
| spec-check 新强门失败传播覆盖不足 | 最终 Kimi 复评发现 fixture 有无关 stub，但 propagation 用例未覆盖 user/agent identity 与 Feishu policy | `spec-check-propagates-control-gate-failures` 新增 user-agent-identity、feishu-notification-policy、runtime-package 三类失败传播用例，Kimi follow-up 复评 PASS |

### 5.2 人工验证项（Cap 无法自动化完成的）

- [x] 用户补充正确 secret 后，Cap 已重新注册本机 `cli_a9579f5b12219bb5` profile，并完成 setup 与真实 node-report 验证。

### 5.3 已发现并已解除的运行态边界

初始收口时，`python3 compass/tools/feishu-notifier.py setup` 曾失败，原因是本机 lark-cli 缺少目标 profile：

```text
profile "cli_a9579f5b12219bb5" not found
available profiles: cli_a96647831a78dbd3
```

随后用户在 2026-04-28 补充正确 secret。Cap 重新注册目标 profile 后，`setup` 输出 `DRY_RUN_OK=ok`，真实 `node-report` 发送返回 `OK`。本轮仍保留 fail-closed 策略：未来如果该 profile 再次失效，RedCap 仍不得悄悄回退旧账号或 webhook。

### 5.4 完成等级（禁止混报）

| 项 | 结论 |
|---|---|
| 已实现 | 是：身份初始化、飞书单通道策略、安装/诊断/acceptance 接线均已落地 |
| 已自检 | 是：已完成 targeted acceptance、Python 编译、spec-check 与 diagnose；最终结果以本报告更新时的验证表为准 |
| 已独立验收 | 是：Kimi + Claude Code 双路 Prism test-mode 复验通过，blockers=0 |
| 已正式完成 | repo-owned 实现与回归完成；待提交与 closeout receipt 盖章后完成本 child 任务 |
| 外部运行边界 | 初始缺失已解除；当前机器已通过 `cli_a9579f5b12219bb5` 完成 setup 与真实 node-report 验证 |

---

## 六、遗留问题与下一步

| 问题 | 状态 |
|---|---|
| `cli_a9579f5b12219bb5` lark-cli profile 注册 | 已完成；用户补充正确 secret 后 setup 与真实发送均通过 |
| P3-1 GraphRAG / 向量检索阈值研究 | deferred |
| P3-2 runtime receipt evidence correspondence hardening | deferred |
| 父任务整体完成 | 仍 incomplete，不能因 P2-4 完成而冒充全部完成 |

---

## 七、经验沉淀

| 经验 | 问题源 | 解决方案 | 最后效果 |
|---|---|---|---|
| 通知通道要区分“实现收敛”和“外部 profile 可用” | 旧实现同时保留 webhook、旧 profile、followup，且真实 lark-cli profile 状态可能漂移 | 建单一策略 + checker + acceptance；真实 profile 缺失时 fail-closed；用户补 secret 后重新注册并验证真实发送 | RedCap 不再悄悄走旧账号；外部 profile 失效会被暴露，恢复后可立即收口 |
| 首启身份不能只靠读 identity | 复活协议知道 `~/.cap/identity.md`，但没有机器可读的用户/Agent 本地状态面 | installer 写 ignored state，并初始化 `users/Norven` 命名空间 | 新会话/新安装可通过脚本复验身份状态，而不用全文导入私人 identity |

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|---|---|---|---|
| 飞书唯一账号与低频触发策略 | 用户中插约束 | no-promote：已直接晋升为 policy/checker/acceptance/docs | `references/feishu-notification-policy.json`、`redcap-feishu-notification-policy-check.py` |
| 首启用户/Agent 状态面 | P2-4 父任务 | no-promote：已直接落地为 install/revive 链路 | `references/user-agent-identity-policy.json`、`redcap-user-agent-identity.py` |

---

## 八、附录

### 附录 A：棱镜调用结果

| 模式 | Agent | 结论 | blockers |
|---|---|---|
| test | Kimi CLI | 修复已落地，repo-owned 实现与文档无阻塞项，仅待 closeout receipt | 0 |
| test | Claude Code | 仓库代码与文档已就绪可合入/收口；当时唯一未完成项是 closeout receipt 与本地 lark-cli profile 注册，后者已在 2026-04-28 解除 | 0 |
| final follow-up | Kimi CLI | 复查 install 飞书策略接线与 spec-check propagation 覆盖，blockers 已解除 | 0 |
| final review | Claude Code | 最终差异复评通过；仅提示兼容占位与外部 profile 边界 | 0 |

运行证据：
- run: `prism/runs/20260427-first-start-identity-and-feishu-policy/session-registry.yaml`
- collect: `prism/runs/20260427-first-start-identity-and-feishu-policy/collect/kimi-reviewer/parsed.json`
- collect: `prism/runs/20260427-first-start-identity-and-feishu-policy/collect/claude-reviewer/parsed.json`
- final-followup: `prism/runs/20260427-first-start-identity-and-feishu-policy/artifacts/final-review/kimi-followup.parsed.json`
