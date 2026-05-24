# 任务完成报告：Copilot completion 主链硬化

**报告日期**：2026-04-16
**执行者**：Cap（Copilot CLI / GPT-5.4）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：Copilot 这条线已经补上 `task-complete -> on-complete` 的 repo-owned 物理触发器，并修掉了旧 pending closure 会跨 confirmed hash 卡死新收尾的问题。
- 详情：`.github/hooks/redcap-layerB.json` 现已注册 `postToolUse`，它会通过 `.github/hooks/scripts/redcap-layerB-post-tool.sh` 进入 `compass/tools/redcap-layerB-task-complete-guard.sh`。当 `.dev-task.md` 进入 `task-complete` 时，guard 会自动尝试登记当前报告并触发 `redcap-on-complete.sh`；同时，`redcap-interop-governance.sh` / `redcap-pending-closure-reconcile.sh` / `redcap-task-report-register.sh` 已支持 stale closure 重锚与当前报告替换，不再被旧 identity 永久拦死。

### 0.2 上一步完成的是

- 上一步完成的是：Copilot 会话身份锚点已经收口，当前真实会话也已从 `degraded-no-runtime-manifest` 切到 `full`；这为本轮 completion 主链硬化提供了可附着的 runtime 基座。

### 0.3 下一步计划做的是

- 下一步计划做的是：回到主线 `F2 规范到 gate 的翻译链`，继续推进治理规范到执行门的翻译；本轮 completion 缺口已从主链上摘除。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：backlog / D1 / 汇报模板链收口 → 飞书双向链路与 overlay P0 收口 → Copilot 会话身份锚点收口 → Copilot completion 主链硬化 → 回到 `F2 / A3 / F3` 主线。
- 当前所在位置：completion 主链硬化已完成，`task-complete` 不再只靠 Agent 记得手动执行 `redcap-on-complete.sh`；下一焦点回到主线 `F2`。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 1. 为什么这次又没有发飞书通知？ 2. 我要的不是你发飞书，而是要你发现和解决“不发飞书的原因”，因为和飞书一起的还有很多个必执行任务和逻辑，飞书只是比较容易发现没执行的，其他的任务现在根本不清楚是否也遗漏了，如果是的话，那么可以宣判redcap开发到现在的所谓100%保障hook机制，是彻底失败的，它完全对抗不了长任务、长对话

### 1.2 触发背景

这次问题的关键不是“飞书单点坏了”，而是**任务已经宣称完成，但 `redcap-on-complete.sh` 根本没有被触发**。  
进一步排查后还发现第二个结构性问题：更早期的 pending closure 仍然锚在旧 confirmed hash 上，正在阻断新的任务报告登记。  
因此，本轮必须同时修两层：**task-complete 自动触发**，以及 **stale pending closure identity 演化**。

---

## 二、方案讨论

### 2.1 问题分析

此前 Copilot Layer B 虽然已有 `sessionStart / sessionEnd`，但 `task-complete` 时刻仍然没有 repo-owned 物理触发器。  
这意味着只要长对话里没有立即关会话，completion 主链就仍依赖 Agent 自己记得手动跑 `redcap-on-complete.sh`。  
同时，旧 pending closure 的阻断逻辑只要看到 `task_id` 对应的旧 state 就直接拦住，既不重锚，也不允许当前报告替换旧 artifact，自然会把长任务越拖越死。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| task-complete 触发器 | 选项 A | 继续靠 Agent 在完成时手动执行 `redcap-on-complete.sh` | 实现最少 | 仍是软约束，长对话继续会漏 |
| task-complete 触发器 | 选项 B | 只依赖 `sessionEnd` 兜底 | 不新增 Hook | 用户不关会话时依旧没有即时收尾 |
| task-complete 触发器 | 选项 C | 新增 Copilot `postToolUse`，在 `.dev-task.md active_slice=task-complete` 时自动触发 guard | 有 repo-owned 物理触发器，且能做去重 | 需要补 guard 和回归 |
| stale closure | 选项 A | 继续沿用“看到旧 pending closure 就一律阻断” | 逻辑简单 | 会把长任务永久卡死 |
| stale closure | 选项 B | 允许当前 identity 重写 / 重锚 pending closure，并允许当前报告替换旧 artifact | 不丢 closure 治理，又不让旧 identity 永生阻断 | 需要补治理与回归 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| task-complete 触发器 | 选项 C | 只有 `postToolUse` 能在“不关会话”的真实长任务里为 `task-complete` 提供 repo-owned 物理触发器 | NORVEN_DECIDE + CAP_DECIDE |
| stale closure | 选项 B | 旧 closure 不能无限期拦住新收尾；必须保留审计线索，但要允许当前 identity 继续推进 | NORVEN_DECIDE + CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `.github/hooks/redcap-layerB.json` | 修改 | 新增 `postToolUse`，把 Copilot `task-complete` 自动收尾纳入 repo-owned Hook |
| `.github/hooks/scripts/redcap-layerB-post-tool.sh` | 新建 | 注入 Copilot session context 后，路由到 task-complete guard |
| `compass/tools/redcap-layerB-task-complete-guard.sh` | 新建 | 在 `task-complete` 时自动尝试登记当前报告、触发 `redcap-on-complete.sh`，并做 fingerprint 去重 |
| `compass/tools/redcap-interop-governance.sh` | 修改 | pending closure 现在优先当前 identity，并清理 stale state；old confirmed hash 不再永久锚死新收尾 |
| `compass/tools/redcap-task-report-register.sh` | 修改 | 允许当前报告替换旧 artifact，不再因 unresolved pending closure 直接硬拦 |
| `compass/tools/redcap-pending-closure-reconcile.sh` | 修改 | confirmed hash mismatch 不再直接退出，而是允许重锚 / 重写当前 blocker 集 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 新增/更新 completion 主链相关回归 |
| `compass/knowledge/hooks-copilot-cli.md` | 修改 | 把 `postToolUse -> task-complete guard` 写成正式部署现状 |
| `compass/knowledge/lessons.md` | 修改 | 新增 L-69，沉淀 completion 主链硬化经验 |
| `.dev-task.md` | 修改 | 追加 U39 / Q24 / Q25，并把当前切片切到 completion 主链 follow-up |
| `plan.md` | 修改 | 宿主工作面板同步切到 completion 主链 hardening |
| `compass/docs/task-reports/2026-04-16-completion-hook-hardening.md` | 新建 | 归档本轮任务报告 |

### 3.2 技术实现要点

第一，Copilot 现在终于有了 `task-complete` 的 repo-owned 物理触发器。  
`postToolUse` 每次工具调用后都会经过 `redcap-layerB-post-tool.sh`；只要 `.dev-task.md active_slice=task-complete`，guard 就会附着当前 runtime，并以 `confirmed_hash + current_head + current_report + pending_updated_at` 作为 fingerprint 去重。

第二，guard 不只“硬跑 on-complete”，还会先尝试补当前报告 marker。  
如果 runtime 里还没有 `layerB/current-report-path`，guard 会优先扫描本轮最新任务报告，再调用 `redcap-task-report-register.sh`。这样修掉的是“completion 主链根本没触发”和“current report marker 没补上”这两个容易一起漏掉的缺口。

第三，stale pending closure 不再因为旧 confirmed hash 永久挡路。  
`redcap-interop-governance.sh` 现在优先读取当前 identity 的 state，并允许在写 pending closure 时把旧 confirmed hash 重锚到当前 identity；旧 stale state 会被清理，不再永远挂着。  
与此同时，`redcap-task-report-register.sh` 也改成允许当前报告替换旧 artifact 路径，而不是一看到 pending closure 就直接 block。

第四，`sessionStart` 的 auto-reconcile 现在会在 hash mismatch 时继续推进，而不是原地认输。  
`redcap-pending-closure-reconcile.sh` 过去在 `pending_confirmed_hash != current_confirmed_hash` 时直接 `identity-mismatch` 后退出；现在它会把 mismatch 当作可重锚条件，必要时重写 blocker 集或直接清理旧债。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| task-complete guard | `compass/tools/redcap-layerB-task-complete-guard.sh` | 指当任务进入完成态时，自动补收尾的守门脚本 |
| `postToolUse` 自动收尾 | `.github/hooks/redcap-layerB.json` + wrapper | 指工具一跑完就检查“任务是不是已经进入完成态”，如果是就自动接上 on-complete |
| stale pending closure | `compass/tools/redcap-interop-governance.sh` | 指还挂在旧 confirmed hash 上、继续挡住当前任务收尾的老义务 |
| artifact replace | `compass/tools/redcap-task-report-register.sh` | 指当前这次任务的新报告可以替换 pending closure 里旧的报告路径，而不是被旧路径卡死 |

### 3.3 关联变更

这次没有改 Copilot 的 identity 锚点策略：`session-state + inuse.<pid>.lock` 仍然是 Copilot 这条线的 repo-owned 会话上下文来源。  
本轮补的是它之上的 completion 层：即便当前会话一直不关闭，也不会再因为缺少 `task-complete` 触发器而漏跑 `redcap-on-complete.sh`。

---

## 四、人工审核要点

> ⚠️ 以下是 Norven 需要重点确认的内容，其他部分 Cap 已自行验证。

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 无必须人工裁决项；若要抽查，优先看 `redcap-layerB-task-complete-guard.sh` 的触发边界与你对“task-complete 自动收尾”预期是否一致 | 本轮已通过 repo-owned acceptance 收口，无额外人工决策 blocker | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 壳脚本语法检查 | `bash -n compass/tools/redcap-interop-governance.sh compass/tools/redcap-task-report-register.sh compass/tools/redcap-pending-closure-reconcile.sh compass/tools/redcap-layerB-task-complete-guard.sh .github/hooks/scripts/redcap-layerB-post-tool.sh compass/tools/redcap-multi-session-acceptance.sh` | ✅ |
| Hook 配置语法检查 | `python3 -m json.tool .github/hooks/redcap-layerB.json >/dev/null` | ✅ |
| 当前报告替换旧 artifact 回归 | `bash compass/tools/redcap-multi-session-acceptance.sh report-register-replaces-pending-artifact` | ✅ |
| stale hash mismatch 回归 | `bash compass/tools/redcap-multi-session-acceptance.sh sessionstart-auto-reconcile-hash-mismatch` | ✅ |
| task-complete 自动收尾回归 | `bash compass/tools/redcap-multi-session-acceptance.sh task-complete-guard-triggers-on-complete` | ✅ |
| 全量 acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh all` | ✅ |
| 当前真实 Copilot runtime 触发 | `bash .github/hooks/scripts/redcap-layerB-post-tool.sh` | ✅ 已自动写入 `layerB/current-report-path=compass/docs/task-reports/2026-04-16-completion-hook-hardening.md`；当前返回 `retry-needed` 的根因是 `commit-proof-check` 检测到工作区仍有未提交改动，而不是触发器失效 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [x] 无必须人工验证项；本轮关键路径已通过 targeted acceptance + full acceptance 同时验证。

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 当前这次 live runtime 仍未形成 `on-complete success` | completion 主链已经修好并实际触发，但 RedCap 自己的 `commit-proof-check` 仍要求本轮改动先形成 commit；这是当前工作区状态约束，不是触发器缺口 | P1 |
| Copilot 若未来改变 Hook payload、`session-state` 目录或 `postToolUse` 语义，当前 wrapper / guard 可能需要跟着调整 | 这属于宿主演进边界，不是当前 repo 可静态消灭的问题 | P1 |

### 6.2 触发的新问题

本轮没有新增 blocker。  
相反，它把“最终回复已发出，但 completion 主链没跑”的结构性缺口补成了 repo-owned 机制。

### 6.3 推荐的下一步行动

1. 回到 `F2` 主线，继续把 hook / lesson / contract / 状态机等治理规范翻译成 gate。
2. 后续如再升级 completion 主链，优先延续“物理触发器 + pending closure identity 演化 + acceptance 回归”三件套，而不是回到手动补脚本。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-69 | `sessionStart / sessionEnd` 已经落地，不等于 `task-complete` 自动收尾也已经落地 | 只要任务完成态没有 repo-owned 物理触发器，长对话里就仍会漏跑 `redcap-on-complete.sh`；同时 stale pending closure 也不能继续永远卡死新收尾 |

### 7.2 流程改进建议

以后凡是用户质疑“为什么又没发飞书”，都不要先把它理解成 notifier 单点问题。  
应优先按物理证据检查：`task-complete` 是否真的触发了 `on-complete`、runtime marker 是否存在、pending closure 是否还锚在旧 identity。  
也就是说，completion 可靠性的排查顺序应从**触发器 → marker / ledger → 下游通知**，而不是反过来。

---

## 八、附录

### 附录 A：Commits

```text
（本轮改动当前仍在工作区，尚未形成新的 commit）
```

### 附录 B：棱镜调用记录（如有）

本轮没有新增独立 Prism 报告；主要依赖 repo-owned acceptance 与当前真实 runtime 路径收口。

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md` 中的 `U39 / Q24 / Q25`
- 设计/说明文档：`compass/knowledge/hooks-copilot-cli.md`
- 终局账本：`.dev-task.md`
