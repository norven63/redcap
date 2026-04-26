# RedCap 探索笔记（Scribe Protocol）

> **用途**：记录 PM Gate 前的方向探讨过程，防止讨论演进因上下文压缩而丢失。
> **维护者**：Cap 在每次多Q讨论中自动维护（书记模式触发）。
> **消费时机**：PM Gate Phase 1 前直接引用；Stop Hook 检查是否有未归档条目。
> **归档规则**：每个 Q 决策落定后，将对应条目标记 `[ARCHIVED]`，同时沉淀到 `.dev-task.md` 或 `knowledge/lessons.md`。

---

## 格式模板

```
## [YYYY-MM-DD HH:MM] Q<N>: <问题标题>

**原始问题**（用户原文，禁止改写）：
> ...

**演进过程**：
- 轮次 1：...
- 轮次 2：...

**关键分歧 / 选项**：
- 选项 A：...（支持理由）
- 选项 B：...（支持理由）

**当前共识**：...

**待决策**：[NORVEN_DECIDE] / [CAP_DECIDE] / 已决定：...

**状态**：exploring / aligned / decided / [ARCHIVED]
```

---

## 活跃探索记录

<!-- Cap 在书记模式触发时在此追加条目 -->
<!-- 已归档条目移至下方"归档区"，保留索引引用 -->

### [2026-04-12 12:12] Q8: 主线恢复后的治理补充（skill 外包 / Gemini / 飞书 / 记录机制 / 文件生命周期）

**原始问题**（用户原文，禁止改写）：
> 1. 好的，关于skill的问题，我想补充一下自己的想法：之前做skill外包的能力时就提过，而且似乎还落地了，只是我不知道是否现在还留着这个落地实现，而我当时说的是，可以启动一个棱镜雇佣兵，然后你直接把skill的绝对路径给他，让他通过这个skill来完成你分配的任务，并把产出结果给你。你可以看看这个方案存在于skill外包的功能实现中，并且评估是否对你刚才处理无法支持的skill有帮助，尤其在曲线救国这个点上。
> 2. gemini标记为在能力相当的情况下，最高优先级使用，除非他通信不畅、能力无法满足任务难度。因为它目前是我们成本较低的方案，不能无节制的使用copilot cli这个Agent，要有所克制，只有必须是它的时候才会用。当然，也不要因为这条约束导致清一色又去使用gemini cli了，而忽视copilot cli中的优质模型，要根据实际情况而动态精准的做出路由决策。
> 3. 我发现飞书通知的可读性好像变差了，目前的内容类似是这样的“RedCap 流程完成: redcap\n\nCommits:\n6032a26 fix(框架): 修正宿主 shared skill 资产边界”，感觉符号问题、内容质量都不符合人类可读。
> 4. 主线任务信息的保存完好我很欣慰，希望这是我们的跟踪机制真正生效导致的，而不是因为还没触发生长任务上下文稀释导致的。
> 5. 现在“记录我原始对话内容”的机制还在生效吗？就是在讨论阶段，也要记录和更新我们对话内容，防止在PM Gate阶段丢失，以及后续任务完成时做考古时也丢失了。这个能力很重要。
> 6. 你在做主线任务时，再追加一条要求：“判断哪些文件是需要放在会话隔离中的，哪些文件是临时的，哪些文件只允许放在本地而不应该跟随git一起提交的”。因为我发现很多临时性的、会话级别的、跟踪性质的文件，也会被git提交，这些文件并不是“记录当前开发项目的项目区进度”（Layer A的state机制）用的，不应该被共享甚至上传到git。关于这个逻辑，你是否认可呢？可以深度评估和公正的评判我的这条要求，不用盲目执行。
> 5. 你评估一下我这次的回复内容，是否还有我要介入人工支持的地方。如果没有，是否可以继续任务，并且直到全部完成为止？

**演进过程**：
- 轮次 1：回读 `.dev-task.md`、blocked todos 与最近提交，确认主线细节并未丢失，但 canonical truth 仍停留在 P0，未吸收最近两轮用户原话。
- 轮次 2：检索到 `baton-delegate.sh` / `baton-launcher.sh` 的 `--skill-path` 实现仍在，可通过绝对路径把 skill 外包给独立雇佣兵。
- 轮次 3：确认 `gemini` CLI 在宿主可用，0% 使用率的主因不是不可用，而是当前路由治理没有把“能力相当时优先 Gemini”硬编码到规则。
- 轮次 4：定位飞书可读性退化根因：`redcap-on-complete.sh` 与 SessionEnd/Hook 路径把原始 commit dump 直接塞给 `feishu-notifier.py notify()`，且通知标题固定为“📢 RedCap 通知”。
- 轮次 5：确认“原始输入/书记链”机制是存在的，但执行上出现漏记，最近两轮新增要求没有及时写入 `.dev-task.md` / `explore-notes.md`。

**关键分歧 / 选项**：
- 选项 A：unsupported skill 彻底禁用，不再通过外包/雇佣兵使用。
- 选项 B：unsupported skill 允许作为 leaf worker / evidence-only / advisory outsourced path 使用，但不得进入 RedCap 控制面。
- 选项 C：继续容忍当前跟踪/讨论文件直接进 git，不做生命周期分类。
- 选项 D：按 authority / 生命周期 / 共享必要性 重新分类 repo-tracked / session-isolated / local-only / temporary 文件。

**当前共识**：
- B 更合理：skill 外包能力仍可服务于“曲线救国”，但前提是该 skill 只产生结果，不拥有 ask_user / state / lifecycle / authority。
- Gemini 应被提升为“能力相当时优先”的低成本首选，但必须保留通信质量、任务难度和高质量 Copilot 模型的动态路由余地。
- 飞书通知需要系统级修复，主路径与兜底路径统一结构化格式。
- `.dev-task.md` 与书记链需要立即补写当前两轮原话，避免再出现“机制存在但执行漏记”。
- 文件生命周期分类应纳入当前主线，不宜盲目执行“一刀切不进 git”，而要做公正分层判断。

**待决策**：已决定（相关路由、通知、生命周期与 docs 审计收口已在后续治理 tranche 中实际落地）

**状态**：[ARCHIVED] → `compass/docs/task-reports/2026-04-17-live-closeout-final-blockers.md` / `compass/docs/task-reports/2026-04-22-install-revival-and-context-hardening.md`

---

### [2026-04-11] Q1: 指挥棒归属（Dispatch 架构）

**原始问题**：
> 干脆把loom弱化成一个基础能力，和棱镜平级，然后你把Dispatch的能力挪进compass来，抽象为"指挥棒"，这个指挥棒以后就是你调度任何任务时的利器（当然，可能要和当前已经存在调度逻辑做融合，其实就是Layer A和B在调度逻辑上的融合）。还是说，指挥棒放在loom里更合适些，你需要用的时候直接拿来指挥即可？

**关键分歧**：
- 选项 A：挪进 compass（指挥官随身工具）
- 选项 B：留在 loom（借用工具）

**当前共识**：compass 获得独立指挥棒能力 + loom/dispatcher 原地不动 + 提取共享调度原语作为"父类"，两者独立派生、按需通信

**待决策**：已决定（Norven 确认）

**状态**：[ARCHIVED] → 见 `.dev-task.md` / `discussion_log`

---

### [2026-04-11] Q2: loom 角色召唤棱镜意识

**原始问题**：
> 目前loom中的每个role有写入"调用棱镜"的指令吗？他们有意识在合适的时机，去召唤棱镜雇佣兵来协助自己完成复杂而长的任务吗？

**当前共识**：四个 handbook 确认无棱镜调用指令（真实缺口），补"何时召唤棱镜"节，纯 CAP_DECIDE

**状态**：[ARCHIVED] → P1 落地中

---

### [2026-04-11] Q3: Skill-within-skill 外包能力

**原始问题**：
> 能否实现一个能力，就是在你这个skill中套用另一个skill的能力，类似于把一个节点的活外包给一个其他更加优秀和专业的某个skill...

**关键分歧**：
- Skill 加载方式：路径传入 vs prompt 注入（路径传入更优雅）
- 多轮对话：实时通道 vs 文件接力（文件接力天然兼容棱镜现有通信模型）

**当前共识**：告知路径 → Agent 读 SKILL.md；BLOCKED 信号 → 文件接力 → Norven 透传

**状态**：[ARCHIVED] → P3 落地中

---

### [2026-04-11] Q4: 棱镜多轮 session 兼容机制

**原始问题**：
> 多轮对话的session保存机制，而且不同的Agent工具有不同的session机制，需要有专门的兼容机制来保障棱镜这块的工作运行

**当前共识**：在 agent-adapters.md 补"多轮接力协议"：各工具续接参数标准化 + BLOCKED 接力 context 携带方式

**状态**：[ARCHIVED] → P2 落地中

---

### [2026-04-11] Q5: 模型能力矩阵定期更新

**原始问题**：
> 把你目前掌握的模型特点、擅长做的事情、评分等分析一下，将合适的任务各司其职的分配给指定Agent&模型，这份决策参考可以考虑定期更新（15天或者1个月不等）

**当前共识**：矩阵已存在（model-capability-matrix.yaml），补 Gemini/GPT 实测数据；prism Frame 阶段加读矩阵选型步骤；30天更新频率

**状态**：[ARCHIVED] → P4 落地中

---

### [2026-04-11] Q6: 探索笔记秘书官设计

**原始问题**：
> 把"探索笔记"直接上升到一个高优先级的Q来设计和落地吧...是从棱镜中直接抽出来的一个临时独立Agent，还是说从你这直接出一个类似"子线程"的工作队列呢？

**关键分歧**：
- 选项 A：独立 Agent（有自己的上下文，但管理复杂）
- 选项 B：Cap 内置书记模式（写入动作 = 可靠性保障核心，无需额外 Agent）

**当前共识**：内置书记模式。触发条件：≥2个未解决问题 or >3轮未记录。写入本文件。PM Gate 时直接消费。Stop Hook 检查未归档。

**状态**：[ARCHIVED] → P0 已落地（本文件 + `soul.md` + `CONTRIBUTING.md §12`）

---

### [2026-04-11 16:07] Q7: Prism run-state producer 缺口

**原始问题**（用户原文摘录）：
> 我们要专注于多会话隔离的问题了，这个问题很复杂，因为不仅仅Layer A、B要进行隔离，A和B的通信、A和B调度的棱镜团队之间的通信，这些情况都要考虑和兼容。

**演进过程**：
- 轮次 1：确认 Layer A / Layer B 的 runtime session、capability、safe degraded、owner claim 已基本落地。
- 轮次 2：重读 `prism/protocol.md`、`prism/tools/prism-archive-check.sh`、`prism/tools/prism-dispatch-check.sh`，发现 protocol 与 consumer 已明确依赖 `session_registry`，但仓库内仍未找到清晰的 scripted writer / coordinator helper。
- 轮次 3：对照 `compass/docs/specs/multi-session-isolation-design.md`，确认目标形态应为 `prism/runs/<prism_run_id>/session-registry.yaml`，且必须遵守 run-scoped 单主写者（Prism coordinator）原则。
- 轮次 4：补充环境背景——此前 distill 曾并发调用 redcap，但本轮中途 review 未发现 tracked tree 中存在冲突标记、异常提交内容或被写入仓库的跨会话产物。
- 轮次 5：已落地 `prism/tools/prism-run-state.sh`，把 run dir / registry / owner / legacy resolve 统一收口到 helper；`prism-archive-check.sh` 也已切到按报告 `run_id` 解析 run-scoped registry，并保留 deterministic read-only legacy bridge。
- 轮次 6：同步修正 `prism/protocol.md` 与 `prism/modes/council.md` 的 run path / quorum 语义，使 archive gate 与 protocol 文档不再漂移。

**关键分歧 / 选项**：
- 选项 A：先补一个 `prism-run-state` helper，集中承载 `prism_run_id`、registry path、owner/lease、dispatch/collect 回填，再让现有 consumer 切过去。
- 选项 B：先在现有调用点零散补写 `.session-registry.yaml`，等跑通后再回收成 helper。

**当前共识**：
- A 更符合既有多会话隔离设计：Prism 需要 **run-scoped 真相层**，不适合沿着当前全局 `prism/reports/.session-registry.yaml` 继续打补丁。
- 当前仓库中 `prism-archive-check.sh` / `prism-dispatch-check.sh` 是 consumer / gate，不是 producer；下一步应先补 coordinator helper，再迁移 consumer。
- 当前阶段的最小落地已完成：helper + archive consumer + deterministic legacy bridge 已到位，后续剩余的是 scripted coordinator 真正接入 dispatch / collect / council 的写回链路。

**待决策**：已决定（Cap 已按批准边界完成 Phase A 接线，并将 Dispatch Firewall 的当前口径显式收口为 prompt-level hard limitation + dispatch gate）

**状态**：[ARCHIVED] → `prism/tools/prism-run-state.sh` / `prism/tools/prism-coordinator.sh` / `prism/protocol.md` / `compass/docs/task-reports/2026-04-12-host-agent-interop-governance.md`

---

### [2026-04-26] Q8: Shared Knowledge 远端绑定与公开仓库安全边界

**原始问题**：
> 继续，另外，公共库的git仓库是：https://gitee.com/norven63/redcap-arsenal.git

**演进过程**：
- 轮次 1：确认 `redcap-arsenal` 远端可访问但初始无 head，任务边界限定为 P1-3 子任务，不能冒充父任务完成。
- 轮次 2：建立 `shared-knowledge-remote-binding.json`，把 remote URL、默认分支、最小候选清单、禁止路径与 last_verified 变成机器可读事实。
- 轮次 3：只把 `.gitignore`、`README.md`、schema、`indexes/.gitkeep`、`users/.gitkeep` 推送到 Gitee `main`，并记录 head `a43c8ab543eff42a288e23ecc4eeb5bc6e954b78`。
- 轮次 4：Prism review 提醒 `--live` 不应只验 head；已升级为 head + tree + 文件内容对账，并补 acceptance 覆盖额外文件与内容漂移。
- 轮次 5：closeout 暴露旧 stop-review 控制面 `FAIL` 会污染当前 Prism pass；已补 session-end 旧证据覆盖规则与回归，要求清理过期 review artifact 后再给 receipt。

**当前共识**：
- 公共库绑定必须先用最小白名单保护“能推什么”，再用 `--live` 证明“远端实际是什么”。
- P1-3 完成不等于历史 reports/lessons/identity 已迁移，也不等于父任务全部完成。
- closeout 证据必须按当前任务状态重算；旧 validator FAIL 只能作为历史证据，不能在当前 Prism pass 后继续阻塞 session-end。

**状态**：[ACTIVE] → P1-3 closeout 中；正式证据见 `2026-04-26-shared-knowledge-gitee-remote-binding.md`

---

## 归档区

> 已决策且已沉淀到正式文档的条目索引（保留追溯链路，不删除原文）

| Q | 决策时间 | 最终方向 | 沉淀位置 |
|---|---------|---------|---------|
| Q1 指挥棒 | 2026-04-11 | compass独立指挥棒+loom保持+共享原语 | P3 baton-design.md |
| Q2 角色棱镜 | 2026-04-11 | 四个handbook补召唤棱镜节 | P1 各role handbook |
| Q3 外包能力 | 2026-04-11 | 路径传入+文件接力BLOCKED | P3 prism/protocol.md |
| Q4 Session兼容 | 2026-04-11 | agent-adapters多轮接力协议 | P2 agent-adapters.md |
| Q5 模型矩阵 | 2026-04-11 | 实测数据+Frame选型+30天更新 | P4 model-capability-matrix.yaml |
| Q6 秘书官 | 2026-04-11 | 内置书记模式（本文件） | 本文件+soul.md+CONTRIBUTING.md §12 |
| Q7 Prism run-state | 2026-04-12 | run-scoped truth + coordinator Phase A + Dispatch Firewall 当前口径显式收口 | prism-run-state.sh / prism-coordinator.sh / prism/protocol.md / task report |

---

### [2026-04-11] 授权规则：Cap 自主执行条件

**原始授权（Norven 原文）**：
> 后续只要你认为优先级很高，且必要性也高，可以直接与棱镜团队商量，如果多有人一致通过，那么可以自主执行，不用阻塞等待我给出指令。只要最后按照模版做整理并同步给我就行了。

**触发条件**（三条同时满足）：
1. Cap 自评优先级高（延迟有实质代价）
2. Cap 自评必要性高（不做有明确缺口/风险）
3. 棱镜团队 ≥2 个独立视角一致通过，无 blocking 反对

**不适用范围**：架构方向性变更、外部依赖引入、Norven 明确要求介入的决策

**沉淀位置**：CONTRIBUTING.md §10 自主执行授权段

**状态**：[ARCHIVED] → `CONTRIBUTING.md §10`
