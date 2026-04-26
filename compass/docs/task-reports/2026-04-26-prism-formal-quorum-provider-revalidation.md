# 任务完成报告：Formal Prism quorum 恢复复验

**报告日期**：2026-04-26
**执行者**：Cap（Codex.app 主执行，Kimi + Claude Code Prism reviewers）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P2-3 已实现并通过 Kimi + Claude Code Prism acceptance；Kimi 与 Claude Code 已被真实 live probe 证明可用，Codex CLI 已被策略降为 last-resort 兜底。
- 详情：`prism-availability` 现在会读取 provider policy，把 Codex 标记为 `last-resort`，并在任一非 Codex provider 可用时拒绝 Codex 进入普通 roster。

### 0.2 上一步完成的是

- 上一步完成的是：P2-1 runtime / CLI / package readiness 已 closeout，父任务聚合 gate 仍保持父任务不可整体完成。

### 0.3 下一步计划做的是

- 下一步计划做的是：提交后运行 closeout runtime，生成本轮 receipt；父任务后续只剩 P1-3 shared-knowledge 外部远端绑定等非本轮项。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P2-1 package readiness → P2-2 父任务聚合 gate → P2-3 Prism provider quorum 复验 → P1-3 shared-knowledge 外部远端绑定。
- 当前所在位置：P2-3 已完成独立验收；父任务仍因 P1-3 外部 remote / 权限未绑定而不能声明全部完成。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 继续，另外补充一个点：棱镜中的Claude Code已经恢复可用了，后续的任务中可以加入进来，而Codex CLI的优先级保持降低1档，只有当所有CLI都不可用时作为兜底，目前kimi cli、Claude Code都是可用的

### 1.2 触发背景

父任务账本中的 P2-3 原本标记为 resource-limited，因为当时只有 Kimi 稳定，Claude/Gemini 超时，Copilot 冻结，Codex 不适合作为常规外部 reviewer。用户补充 Claude Code 已恢复可用后，需要把这个事实转成机器可执行的 provider 策略，而不是只写在聊天里。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 继续父任务，并吸收 Claude Code 恢复、Kimi 可用、Codex CLI 降为兜底的 provider 策略变化。 |
| 已覆盖 | live health probe、provider policy、availability roster gate、Codex last-resort suppression、Claude Code alias、targeted acceptance、父任务账本、经验沉淀。 |
| 未覆盖/延期 | 不解除 Copilot 冻结；不把 Gemini timeout 写成可用；不把 Codex CLI 纳入常规 quorum。 |
| 用户可见边界 | P2-3 完成只代表当前 Prism quorum 有 Kimi + Claude Code 的可审计路径，不代表所有 provider 永久可用。 |

---

## 二、方案讨论

### 2.1 决策

| Q | 采纳方案 | 决策理由 |
|---|---|---|
| Claude Code 是否入队 | 入队，但以 live probe 为准 | 用户补充恢复可用后，机器探测确认 60 秒窗口内 pass。 |
| Codex CLI 如何降级 | `last-resort` 策略 | 不是禁用 Codex，而是防止它在 Kimi/Claude 可用时抢占普通 Prism roster。 |
| 健康探测 timeout | provider-aware timeout | Claude Code 慢启动和 SessionEnd hook 噪声会让 20 秒误判；统一短 timeout 不够诚实。 |
| Copilot 状态 | 继续 frozen | 用户此前明确要求保留 Copilot 配额，恢复可用不等于解除冻结。 |

### 2.2 关键边界

本轮把“能力可见”和“调度可用”分开：CLI installed 只说明命令存在，live probe pass 才说明当前 headless 可用；provider policy 还可以因为 quota、资源保护或 last-resort 边界继续禁止普通入队。这样可以避免“看到命令就调”“旧 cache 没过期就调”“Codex 很强所以优先调”三种常见误判。

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `references/prism-provider-policy.json` | 修改 | 新增 `routing_overrides`，把 Codex CLI 标记为 `last-resort`。 |
| `prism/tools/prism-availability.py` | 修改 | 读取 provider routing policy；当非 last-resort provider 可用时拒绝 last-resort provider 普通入队。 |
| `compass/tools/redcap-agent-health-probe.py` | 修改 | Codex live probe 改为显式 opt-in；Claude Code 增加最小 60 秒探测窗口。 |
| `compass/tools/redcap-reviewer-order.py` | 修改 | stop-review 排序消费 last-resort policy，常规候选存在时过滤 Codex。 |
| `compass/knowledge/model-capability-matrix.yaml` | 修改 | 更新 Claude Code 恢复可用和 Codex fallback-only 的本地稳定性画像。 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 增加 Codex last-resort suppression、fallback-only 例外、Claude alias 与 Codex opt-in 回归。 |
| `README.md` / `prism/protocol.md` | 修改 | 用人话说明 Prism 先看可用性清单，Codex 是 last-resort 兜底。 |
| `references/redcap-parent-task-ledger.md` / parent aggregation policy | 修改 | 将 P2-3 从 resource-limited 更新为 completed child；父任务仍因 P1-3 未完成而 incomplete。 |
| `compass/knowledge/lessons.md` | 修改 | 新增 L-131，沉淀 provider-aware timeout 与 Codex fallback-only 经验。 |

### 3.2 技术实现要点

`prism-availability` 的判断顺序现在是：先用 live probe 生成 1 小时 TTL 可用性清单，再应用 provider policy。若 roster 里包含 Codex，而清单里存在任一非 last-resort provider 为 available，则 Codex 会被标成 `last-resort-suppressed` 并拒绝 dispatch。若未来所有非 Codex provider 都不可用，Codex 可以在显式 opt-in 探测后作为兜底。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| live probe | `redcap-agent-health-probe.py --live` | 真正调用 CLI，验证当前 headless 能不能跑。 |
| availability cache | `compass/.workflow/prism-agent-availability.json` | 1 小时有效的“当前哪些 CLI 真可用”清单。 |
| provider policy | `references/prism-provider-policy.json` | 资源冻结、兜底策略和 provider 调度边界。 |
| last-resort | `routing_overrides[].priority_tier` | 只有其他 provider 都不可用时才允许使用的兜底。 |
| quorum | `redcap-prism-acceptance-check.py` | 至少两路响应、至少两个模型家族、且没有 blocker 的独立验收门。 |

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | Copilot 冻结窗口 | 本轮没有解除 Copilot freeze；若用户后续要恢复 Copilot，需要明确调整 policy。 | P2 |
| 2 | Gemini 登录态/超时 | Gemini 当前仍 timeout；这不阻塞 Kimi + Claude quorum，但会影响三家族 redteam。 | P2 |
| 3 | Codex 兜底启用 | Codex live probe 需要显式 opt-in，避免健康嗅探自己制造 nested session。 | P2 |

---

## 五、验证结果

| 验证项 | 命令 | 结果 |
|--------|------|------|
| live provider probe | `bash prism/tools/prism-availability.sh status --refresh --timeout 20 --ttl-seconds 3600` | Kimi pass；Claude Code pass；Gemini timeout；Copilot frozen；Codex unsupported + last-resort。 |
| Kimi + Claude roster | `bash prism/tools/prism-availability.sh check-roster --agents "kimi&kimi-for-coding:reviewer,claude&claude-sonnet-4.6:challenger"` | 通过，2 agents。 |
| Codex 普通 roster | `bash prism/tools/prism-availability.sh check-roster --agents "codex&gpt-5.4:reviewer"` | 拒绝；真实状态为 unsupported，fixture 覆盖 last-resort-suppressed。 |
| targeted acceptance | `agent-health-probe`、`prism-availability` | 通过。 |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过，Kimi + Claude Code，2 families，0 blocker。 |
| Claude reviewer | `baton-launcher --cli claude` | pass；提出 alias / opt-in env / 命名差异说明建议，已补。 |
| Kimi reviewer | `baton-launcher --cli kimi` | 长 prompt 超时；短 prompt pass，0 blocker。 |
| spec-check / diagnose | 待最终回归 | 待提交和 closeout 前后执行。 |

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 待 closeout runtime 同步 |
| 棱镜验收 | `20260426-prism-formal-quorum-provider-revalidation` pass（Kimi + Claude Code，2 families） |
| closeout summary | 待提交后生成 |
| closeout receipt | 待提交后生成 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是，targeted acceptance 已通过 |
| 已独立验收 | 是，Kimi + Claude Code 双 reviewer 通过 |
| 已正式完成 | 否，待提交后 closeout runtime receipt |

---

## 六、遗留问题与下一步

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| P1-3 shared-knowledge 远端绑定 | 需要外部仓库与权限。 | P1 |
| Gemini provider timeout | 当前 headless 仍超时；不影响本轮双路 quorum，但影响更宽 Prism roster。 | P2 |
| 真实 public release / 跨机器安装 | P2-1 只完成 readiness，真实发布仍需独立 release 任务。 | P1/P2 |

---

## 七、经验沉淀

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-131 | Prism provider 可用性要区分“慢启动”和“不可用”，Codex 只能做兜底 | Claude Code 需要 provider-aware timeout；Codex 要 last-resort suppression + opt-in probe。 |

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选 | 本轮 provider 策略修复 | no-promote；已沉淀为 L-131，不新增 Evolution candidate | `compass/knowledge/lessons.md` |

---

## 八、附录

### 附录 A：Commits

```text
本报告随 P2-3 实现提交一起进入 git；closeout receipt 将记录最终 HEAD。
```

### 附录 B：棱镜调用记录

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| reviewer / moonshot | provider routing 是否仍有 blocker | Kimi 短问题包 pass；长问题包曾超时，说明 Prism prompt 也要控上下文 | `prism/runs/20260426-prism-formal-quorum-provider-revalidation/collect/kimi_review/parsed.json` |
| reviewer / anthropic | provider routing 是否仍有 blocker | Claude Code pass；3 条非阻塞建议已补 | `prism/runs/20260426-prism-formal-quorum-provider-revalidation/collect/claude_review/parsed.json` |
