# 任务完成报告：Copilot 会话身份锚点收口

**报告日期**：2026-04-16
**执行者**：Cap（Copilot CLI / GPT-5.4）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：Copilot 这条线已经补上 repo-owned 的会话身份锚点，`sessionStart / sessionEnd` 不再只能停在 `degraded-no-runtime-manifest`。
- 详情：新增的 `.github/hooks/scripts/redcap-copilot-session-context.sh` 会从 `~/.copilot/session-state/<handle>/inuse.<pid>.lock` 和当前宿主进程链反推出 `session_handle`，再注入显式 `session_binding_key` 与宿主 `plan.md` 路径。当前这次 Copilot 会话已经实机补跑成功，宿主 Session Mirror 现为 `isolation_mode: full`、`continuity_authority: redcap-owned-manifest`、`continuity_state: self-recorded`。

### 0.2 上一步完成的是

- 上一步完成的是：飞书双向链路、最小待处理入口、overlay downstream handoff P0 与“发送人：Cap”已经收口；这让当前遗留缺口收敛到 Copilot 连续性本身，而不再是飞书或 overlay 控制面问题。

### 0.3 下一步计划做的是

- 下一步计划做的是：回到主线 `F2 规范到 gate 的翻译链`，继续推进治理规范到执行门的翻译。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：backlog / D1 / 汇报模板链收口 → 飞书双向链路与 overlay P0 收口 → Copilot 会话身份锚点收口 → 回到 `F2 / A3 / F3` 主线。
- 当前所在位置：Copilot 身份锚点 follow-up 已完成，当前会话也已从 degraded 手动补同步到 full；下一焦点重新回到 `F2`。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 为什么“当前这次 Copilot 会话仍是 degraded-no-runtime-manifest”呢？需要重启会话吗？还是要开启什么功能？

> 当关闭copilot cli会话时，会提示session id，这个id是否可用？

> 我记得虽然hook输入没有sessionId，但是你可以读到它本地缓存目录的path，并且ptah其中还附带了sessionId的部分，只不过当时你不能确定这个就是id而不敢使用。如果稍后我退出会话并拿到提示的sessionId，之后我提供给你，让你和path的部分对比，如果一致的话，是不是后续copilot cli的sessionId就可以拿path这个部分使用？

> 其实我想说的是，即是sessionId发现不与session_handle一致，也没关系，我们的会话隔离本质上是要识别当前所处的会话是否本地有过历史记录，是否需要接续。而至于判断依据不是非要强求为sessionId，只不过这个id刚好符合我们逻辑，但如果有其他类似符合逻辑的标识信息（比如session_handle），那我们也依然可以使用。你认为正确吗

> 既然讨论到这里了，就完成这个任务吧，之后我们开始专心回归主线任务

### 1.2 触发背景

此前 Copilot 线虽然已经有 `.github/hooks/redcap-layerB.json`，但 `sessionStart / sessionEnd` 输入天然没有 `sessionId`，而 wrapper 也没有补宿主身份上下文。  
结果是：当前会话即使能运行 Hook，也拿不到 verified runtime binding，只能诚实停在 `degraded-no-runtime-manifest`。  
用户进一步明确了关键原则：目标不是教条地追逐官方 `sessionId`，而是稳定识别“当前是不是同一个宿主会话、是否该接续历史”，因此只要有稳定、可验证的宿主身份锚点，就可以使用。

---

## 二、方案讨论

### 2.1 问题分析

这个问题的难点不在“怎么拼一个字符串”，而在“如何不串台”。  
如果只是把 `session-state` 目录名当作 `sessionId` 盲用，的确可能误认领别的会话；但如果一味坚持“没有官方 `sessionId` 就什么都不能做”，又会把 Copilot 永久卡在 degraded。  
真正要找的是介于两者之间的方案：它不声称自己拿到了官方 `sessionId`，但能依靠本地可观测证据稳定识别当前会话，并且在证据缺失时诚实回退。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Copilot 身份锚点 | 选项 A | 等宿主未来原生给 `sessionId` | 语义最直观 | 当前无法解决问题 |
| Copilot 身份锚点 | 选项 B | 直接把 `session-state` 目录名硬当官方 `sessionId` | 实现最省事 | 语义不诚实，也缺少“当前活跃进程真的对应它”的验证 |
| Copilot 身份锚点 | 选项 C | 用 `session-state/<handle>/inuse.<pid>.lock` + 宿主进程链定位 `session_handle`，再生成显式 binding key | 证据链完整、兼容当前宿主边界、失败时可安全降级 | 依赖 Copilot 当前本地目录/锁语义稳定 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Copilot 身份锚点 | 选项 C | 它满足“稳定可验证的宿主身份锚点”要求，又不谎称官方 Hook 已提供 `sessionId`；同时还能保持 safe degraded 作为失败边界 | NORVEN_DECIDE + CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `.github/hooks/scripts/redcap-copilot-session-context.sh` | 新建 | 根据 `session-state` 与 `inuse.<pid>.lock` 推导当前 Copilot `session_handle / plan.md / binding key` |
| `.github/hooks/scripts/redcap-layerB-session-start.sh` | 修改 | 先注入 Copilot session context，再进入统一 `sessionStart` 主链 |
| `.github/hooks/scripts/redcap-layerB-session-end.sh` | 修改 | 先注入 Copilot session context，再进入统一 `sessionEnd` 分发器 |
| `loom/tools/redcap-layerA-session-end.sh` | 修改 | 当 Hook 输入缺失 `session_id` 时，保留 wrapper 已解析出的 `REDCAP_HOST_SESSION_ID` |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 新增 `copilot-wrapper-identity-anchor` 回归，并纳入全量 acceptance |
| `compass/knowledge/hooks-copilot-cli.md` | 修改 | 说明 Copilot wrapper 现在如何补出 repo-owned 身份锚点 |
| `compass/docs/specs/session-isolation-continuity-guide.md` | 修改 | 说明 `session_handle` 为何可以成为合法宿主身份锚点，以及它与官方 `sessionId` 的边界 |
| `compass/knowledge/lessons.md` | 修改 | 新增 L-68，沉淀 Copilot 身份锚点经验 |
| `.dev-task.md` | 修改 | 追加 U34-U38 / Q22-Q23，并把当前切片切到 Copilot identity follow-up |
| `plan.md` | 修改 | 宿主工作面板切到 Copilot identity follow-up，并在实机同步后反映 full continuity |
| `compass/docs/task-reports/2026-04-16-copilot-session-anchor.md` | 新建 | 归档本轮任务报告 |

### 3.2 技术实现要点

第一，Copilot 的身份锚点不再依赖官方 Hook 给 `sessionId`。  
新 helper 会遍历当前 hook 进程可见的父进程链，再去匹配 `~/.copilot/session-state/*/inuse.<pid>.lock`。一旦找到，就拿到当前 `session_handle`，并生成 `host/copilot/session/<session_handle>` 这样的显式 `session_binding_key`。

第二，wrapper 负责把宿主身份翻译成 RedCap 已有主链能理解的输入。  
`redcap-layerB-session-start.sh` 和 `redcap-layerB-session-end.sh` 现在都会先加载这层 Copilot session context，再去调用现有统一脚本。这样，Copilot 线不需要改写 continuity 核心逻辑，而是复用已经存在的 explicit binding key / host workboard path 能力。

第三，`sessionEnd` 也补上了“别把 wrapper 给的身份又清空掉”。  
`loom/tools/redcap-layerA-session-end.sh` 之前会无条件以 Hook 输入里的 `session_id` 为准；对于 Copilot，这个字段本来就没有，等于把 wrapper 已解析出的 `REDCAP_HOST_SESSION_ID` 覆盖成空。现在它在 payload 没有 `session_id` 时会保留 wrapper 的已解析身份，因此 `sessionEnd` 同样能附着到正确 runtime。

第四，验证不是只靠 acceptance。  
除了新增 `copilot-wrapper-identity-anchor` 回归，我还在当前这次真实 Copilot 会话里手动补跑了一次 wrapper 的 `sessionStart`。结果当前宿主 `plan.md` 已从 `degraded-no-runtime-manifest` 切到 `isolation_mode: full`、`resume_gate_reason: explicit-binding-key`、`continuity_state: self-recorded`，证明这条链路在当前实机环境也成立。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| Copilot 身份锚点 | `.github/hooks/scripts/redcap-copilot-session-context.sh` | 指 RedCap 用来识别“当前这个 Hook 到底属于哪个 Copilot 会话”的本地证据链 |
| `session_handle` | `~/.copilot/session-state/<handle>/` | 指宿主会话目录的可读标识，方便定位当前会话，不等于官方 `sessionId` |
| `session_binding_key` | `compass/tools/redcap-runtime-state.sh` + wrapper | 指 RedCap 自己用来附着/恢复 runtime 的稳定定位键；这里会被翻译成 `host/copilot/session/<handle>` |
| safe degraded | `compass/tools/redcap-layerB-session-start.sh` / `redcap-session-resume-gate.sh` | 指证据不足时诚实停在降级路径，只做 mirror，不伪造 continuity authority |

### 3.3 关联变更

这次没有改 capability matrix 的宿主定义：Copilot 仍然是 `copilot-sessionstart-wrapper-required`。  
真正变化的是：wrapper 现在终于履行了“wrapper required”这件事，给主链喂进显式 binding key / host workboard path。  
同时，文档也同步改口，避免后续再把“session_handle 可用”误说成“官方 Hook 已给 `sessionId`”。

---

## 四、人工审核要点

> ⚠️ 以下是 Norven 需要重点确认的内容，其他部分 Cap 已自行验证。

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 无必须人工裁决项；若要抽查，优先看 `.github/hooks/scripts/redcap-copilot-session-context.sh` 的证据链是否符合你对“稳定可验证锚点”的预期 | 本轮方案和边界已经收敛，不需要额外人工决定才能继续 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 壳脚本语法检查 | `bash -n .github/hooks/scripts/redcap-copilot-session-context.sh .github/hooks/scripts/redcap-layerB-session-start.sh .github/hooks/scripts/redcap-layerB-session-end.sh loom/tools/redcap-layerA-session-end.sh compass/tools/redcap-multi-session-acceptance.sh` | ✅ |
| Copilot wrapper 新回归 | `bash compass/tools/redcap-multi-session-acceptance.sh copilot-wrapper-identity-anchor` | ✅ |
| Copilot 原有 safe degraded 回归 | `bash compass/tools/redcap-multi-session-acceptance.sh copilot-safe-degraded` | ✅ |
| Layer A 旧链路回归 | `bash compass/tools/redcap-multi-session-acceptance.sh layera-legacy-quarantine` | ✅ |
| Copilot 显式 binding 旧回归 | `bash compass/tools/redcap-multi-session-acceptance.sh session-resume-gate-copilot-full` | ✅ |
| 全量 acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh all` | ✅ |
| 当前会话实机补同步 | `printf '{\"cwd\":\"$PWD\"}\\n' | REDCAP_SKIP_FEISHU=1 bash .github/hooks/scripts/redcap-layerB-session-start.sh` | ✅ |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [x] 无必须人工验证项；当前 repo-owned 变更已在 acceptance 与当前实机会话里同时验证通过。

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| Copilot 若未来修改 `session-state` 目录结构或 `inuse.<pid>.lock` 语义，当前 wrapper 需要跟着调整 | 这属于宿主演进边界，不是当前 repo 可静态消灭的问题 | P1 |

### 6.2 触发的新问题

本轮没有新增 blocker。  
相反，它把当前会话本来卡住的 `degraded-no-runtime-manifest` 真实收口成了 full continuity。

### 6.3 推荐的下一步行动

1. 回到 `F2` 主线，继续把 hook / lesson / contract / 状态机等治理规范翻译成 gate。
2. 后续关注 Copilot 新版本是否改变 `session-state` / `inuse` 语义；如果变了，就让 wrapper 诚实回退，不要静默假装仍然 full。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-68 | Copilot hook 没有 sessionId 时，可用 `session-state + inuse.<pid>.lock` 补出 repo-owned 身份锚点 | 关键不是冒充官方 `sessionId`，而是用本地可验证证据定位当前会话，并在证据缺失时诚实回退 |

### 7.2 流程改进建议

以后凡是宿主 Hook 不直接暴露官方会话标识，不要先把它归类成“只能 degraded”。  
应先审计：宿主本地是否还存在 `session folder / active lock / process chain / workboard path` 这类可验证证据；只有这条证据链也断掉时，才应该把结论收成“无法 full mode”。

---

## 八、附录

### 附录 A：Commits

```text
（本轮改动当前仍在工作区，尚未形成新的 commit）
```

### 附录 B：棱镜调用记录（如有）

本轮没有新增独立 Prism 报告；主要依赖 repo-owned acceptance 与当前实机会话补同步收口。

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md` 中的 `U34-U38`
- 设计/说明文档：`compass/knowledge/hooks-copilot-cli.md`、`compass/docs/specs/session-isolation-continuity-guide.md`
- 终局账本：`.dev-task.md`
