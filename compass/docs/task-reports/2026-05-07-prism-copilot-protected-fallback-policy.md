# 任务完成报告：Copilot protected fallback 策略收紧

**报告日期**：2026-05-07
**执行者**：Cap（Codex.app 主执行，Prism 使用 Claude Code；Kimi 复审因配额 resource-limited）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：Copilot CLI 已从 RedCap 的普通棱镜/评审/健康嗅探资源中移出，改为“受保护兜底”。
- 详情：以后 RedCap 在 Prism、stop-review、live-health、baton/direct-cli 这些自动化路径里，只有在 Claude Code 与 Kimi 都不可用时，才允许探测或调用 Copilot。Claude Code 或 Kimi 任一可用时，Copilot 会被策略压制，且不会执行真实 CLI 命令。

### 0.2 上一步完成的是

- 上一步完成的是：父任务线完成了 `P4-2h-3` LLM-wiki-lite 最小私有语义记忆生命周期。
- 本轮不是继续发布或公共知识库迁移，而是处理用户插入的 provider 配额保护缺口。

### 0.3 下一步计划做的是

- 下一步计划做的是：本轮收口后回到父任务线状态面。当前除 `P4-2h` deferred 与 `P4-2` blocked-external 外，没有新的可自动推进父任务。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：父任务继续推进 → 用户发现 Copilot 配额保护风险 → 立项 `P2-6` → 策略、探测、排序、验收一起收紧 → Prism resource-limited 复审 → closeout。
- 当前所在位置：`P2-6` 已实现、已通过 targeted checks 与 Prism resource-limited acceptance，等待 closeout runtime receipt。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮不涉及 npm 发布、凭据、许可证、公共知识库写入或是否禁用 Copilot 的保留决策。Copilot 没有被永久禁用，只是被自动路径降级为保护性 fallback。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 现在请你和棱镜继续稳步推进未完成的任务，完成时序和优先级由你们内部讨论评审和决策即可。
>
> 另外，请确认刚才棱镜的调用中是否触发了copilot cli的调用？如果是的话，需要讲copilot cli明确定为“当claude code与kimi不可用时才允许降级调用”

### 1.2 事实核查

- 上一轮正式 Prism 证据只登记了 Kimi + Claude Code，没有登记 Copilot。
- 但本轮我为了核查 Prism availability 状态，在策略加固前运行了一次 live health probe；旧策略没有保护 Copilot，因此实际触碰了 Copilot 并发生超时。
- 这说明缺口不只在“棱镜报告口径”，而是在 live-health / availability / stop-review 的自动路径上都需要物理收紧。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 继续推进未完成任务，并确认/收紧 Copilot CLI 在 RedCap 棱镜体系中的调用边界。 |
| 已覆盖 | 已确认上一轮正式 Prism 未调用 Copilot；已承认本轮旧 live-health probe 触碰 Copilot；已将 Copilot protected fallback 规则落到 provider policy、live health probe、Prism availability、stop-review reviewer order、acceptance、执行保障和 README/protocol 口径。 |
| 未覆盖/延期 | 不禁用用户手动直接使用 Copilot；不删除 Copilot 宿主适配；不改变 npm release、公共知识库或 LLM-wiki 后续任务。 |

---

## 二、方案讨论

### 2.1 问题分析

只在文档里写“少用 Copilot”没有用，因为真正消耗配额的是自动探测和自动评审路径。安全方案必须让机器路径自己识别：如果 Claude Code 或 Kimi 已经可用，Copilot 就不该被探测；如果两者都不可用，Copilot 才能作为降级兜底，且优先于 Codex last-resort。

### 2.2 决策结果

| 问题 | 采纳方案 | 原因 |
|---|---|---|
| Copilot 是否永久禁用 | 不永久禁用 | 用户只是要求保护配额，不是删除能力。 |
| 保护条件 | Claude Code 与 Kimi 都不可用时才允许 Copilot | 这是用户明确边界，也保留了真正降级时的可用性。 |
| 覆盖范围 | policy + live-health + Prism availability + stop-review + acceptance | 缺一层都可能再次触碰 Copilot。 |
| Prism 复审 | 只用 Claude Code / Kimi；Kimi 不可用则 resource-limited | 不用 Copilot 补 quorum，避免用被保护对象验证保护策略。 |

---

## 三、落地结果

### 3.1 人话版结果

这次修复后，RedCap 会先看 Claude Code 和 Kimi 是否可用。只要其中任意一个可用，Copilot 在自动棱镜、自动评审和健康探测里都会被标记为 `policy-suppressed`，不会真的执行。只有两者都不可用时，Copilot 才重新进入降级链路。

同时，Copilot 和 Codex 的关系也被理顺：Copilot 是“受保护 fallback”，Codex 是“最后兜底”。所以当 Copilot 合法通过自己的门禁时，它应该压制 Codex；不能因为 Codex 是 last-resort 而反过来抢先。

### 3.2 关键工程效果

| 能力 | 解决后的效果 |
|---|---|
| provider policy | Copilot 有明确的 `protected-fallback` 规则，条件是 Claude Code + Kimi 均不可用。 |
| live health probe | Claude Code 或 Kimi 可用时，不执行 Copilot，只写 `policy-suppressed` 结果。 |
| Prism availability | roster / dispatch 检查会拒绝普通 Copilot 阵容，并说明是 protected fallback 被压制。 |
| stop-review | 即使手工排序把 Copilot 放在前面，只要 Claude Code 或 Kimi 可用，也不会选择 Copilot。 |
| fallback 保留 | fake 环境证明 Claude Code + Kimi 都不可用时，Copilot 可以被选择，且不会误落到 Codex。 |

### 3.3 棱镜复审

本轮 Prism 使用 Claude Code 与 Kimi，不使用 Copilot。

Claude Code 首轮抓到一个真实 blocker：我最初把 `protected-fallback` 和 `last-resort` 混在同一个过滤逻辑里，导致 Copilot 合法通过门禁后仍可能被 Gemini 等普通 provider 误压掉，同时也可能让 Codex 没被 Copilot 正确压掉。这个问题已经修正。

修正后 Claude Code 复审通过。Kimi 首轮也独立指出了同一 blocker；修正后复跑时触发 provider 429 配额限制，未产出最终 JSON，因此本轮 Prism 按 RedCap 规则绑定为 resource-limited pass，而不是冒充完整双路 quorum。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 人话解释 | 本轮作用 |
|---|---|---|
| protected fallback | 受保护兜底资源 | Copilot 只有在 Claude Code 与 Kimi 都不可用时才能被 RedCap 自动调用。 |
| live health probe | 真实可用性嗅探 | 用来判断 CLI 是否能在 headless 环境工作；本轮让它在 primary 可用时不再执行 Copilot。 |
| Prism availability | 棱镜可用性清单 | Prism 使用前先查可用清单；本轮让清单拒绝普通 Copilot roster。 |
| stop-review | 收尾独立评审 | 任务收尾时选择独立 CLI 审查 diff；本轮让它不能因为手工排序而绕过 Copilot 保护。 |
| last-resort | 最后兜底 | Codex 仍是最后兜底；Copilot 合法通过 protected fallback 门禁后，应优先于 Codex。 |
| resource-limited pass | 资源受限通过 | 至少一个独立审查无 blocker，另一模型因配额/资源无法完成，并有证据记录；不能冒充完整双路 quorum。 |

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|---|---|---|---|
| 1 | 当前无必须人工介入项 | Copilot 降级边界来自用户明确授权，且没有删除手动使用能力。 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|---|---|---|
| 语法与 Python 编译 | `bash -n ... && python3 -m py_compile ...` | 通过 |
| Prism availability | `bash compass/tools/redcap-multi-session-acceptance.sh prism-availability` | 通过 |
| stop-review 压制 Copilot | `bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-suppresses-copilot-when-primary-available` | 通过 |
| stop-review 允许 Copilot 降级 | `bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-allows-copilot-after-primary-unavailable` | 通过 |
| 旧 timeout fallback 回归 | `bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-falls-back-after-timeout` | 通过 |
| 旧 auth fallback 回归 | `bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-falls-back-after-auth-failure` | 通过 |
| spec-check 传播回归 | `bash compass/tools/redcap-multi-session-acceptance.sh spec-check-propagates-control-gate-failures` | 通过 |
| live status 抽样 | `bash prism/tools/prism-availability.sh status ...` | 通过，`copilot=policy-suppressed` |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | resource-limited-pass |

### 5.2 仍需最终收口的验证

closeout 前还会运行 umbrella `spec-check`、`diagnose`、人类输出质量检查和 closeout runtime。若其中任何一项失败，本报告不得升级为正式完成。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|---|---|
| 执行承诺账本 | 已同步，等待最终 closeout 核对 |
| 棱镜验收 | `20260507-prism-copilot-protected-fallback-review`，resource-limited-pass |
| closeout summary | 待 closeout runtime 生成 |
| closeout receipt | 待 closeout runtime 生成 |
| rescue audit（如有） | 当前无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|---|---|
| 已实现 | 是 |
| 已自检 | 是，targeted checks 和 umbrella spec-check 已通过 |
| 已独立验收 | 是，Claude Code 复审 PASS；Kimi 因配额 resource-limited，按规则绑定为 resource-limited-pass |
| 已正式完成 | 否，等待 closeout runtime receipt |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 状态 |
|---|---|---|
| `P4-2` 正式 public release | 需要发布边界、凭据、许可证等单独 release task | blocked-external |
| `P4-2h` 公共蒸馏 | 需要 RedCap Forge 公共晋升任务 | deferred |

### 6.2 触发的新经验

| 问题源 | 解决方案 | 最后效果 |
|---|---|---|
| provider 配额保护不能只靠文档声明 | 把 provider policy 接入 live-health、availability、stop-review 和 acceptance | 自动路径不再在 primary provider 可用时触碰 Copilot |
| protected fallback 和 last-resort 容易被混成一类 | protected fallback 先过自己的 provider 门禁，之后才作为非 last-resort 压制 Codex | Copilot 合法降级时仍可用，Codex 仍保持最后兜底 |

---

## 七、经验沉淀

### 7.3 Evolution Factory 候选处理

本轮产生 2 条可沉淀经验，先作为 `no-promote` 候选记录在本报告中，不直接写入公共 arsenal，也不把 provider raw output 原文公开化。

| 候选 | 问题源 | 解决方案 | 最后效果 | 建议处理 |
|---|---|---|---|---|
| provider-policy-physical-coverage | provider 配额保护若只写文档，会被 live-health 或 stop-review 自动路径绕过 | provider policy 必须接入实际执行点和 acceptance | Copilot 在 Claude Code/Kimi 可用时被机器压制且不执行 | 后续由 RedCap Forge / lessons 流程判断是否晋升为通用 provider policy lesson |
| fallback-vs-last-resort-separation | protected fallback 与 last-resort 很容易被同一过滤器误合并 | fallback 先过专属门禁，通过后作为非 last-resort 参与排序 | Copilot 合法降级时保留，Codex 仍最后兜底 | 后续沉淀为 reviewer-order 设计经验候选 |
