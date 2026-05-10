# 任务完成报告：结论性输出 Prism 强制协作与固化保障优先级加固

**报告日期**：2026-05-10  
**执行者**：Cap（Codex.app + Claude Code / Kimi Prism reviewer）  
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 已把“评估/结论性质输出必须由棱镜参与”和“新增能力优先进入固化保障”从口头约定升级为可检查机制。
- 详情：这次解决的是一个很危险的协作坏味：主 Agent 很容易先给出看似完整的架构结论，但它本质仍是单视角判断。现在 RedCap 把会指导后续工程的官方结论定义为 conclusion-class 输出，要求进入 Prism 协作、复核或验收；同时，新增能力默认先寻找脚本、validator、hook、acceptance、receipt、diagnose/spec-check 等固化落点。没有 Prism 的即时观点只能叫建议稿/初判，不能再写成“我们共同评审结论”。

### 0.2 上一步完成的是

- 上一步完成的是：RASG 架构坏味治理已经把非发布类坏味收束到 closeout，本轮是在这个干净基线上补强“评估性结论不能单人自证”的制度缺口。

### 0.3 下一步计划做的是

- 下一步计划做的是：本轮完成后无新的非发布类阻塞任务；如继续推进，应进入正式发布专项或后续长期演进专项，并按本轮新规则让结论先经 Prism-backed gate。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：历史坏味治理 -> 结论/保障机制补强 -> 正式发布专项 / 长期演进专项。
- 当前所在位置：结论/保障机制补强已实现并通过 Claude Code + Kimi Prism 验收，等待 closeout receipt 作为正式完工凭证。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮没有触及 npm 发布、许可证、registry 凭据、公开发布开关、不可恢复删除或公共仓库写入。后续正式发布仍需要 Norven 单独授权。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> “我需要你们一起完成，因为一个人的视角是有限的，需要多人共同“结伴编排”才能利用多视角来击溃单视角的局限性。这个也要固化到棱镜的调度准则中（注意是固化，不是口头协议），即“后续但凡涉及到评估、结论性质的回复内容时，必须100%通过棱镜配合的方式来生成和产出”。
>
> 另外，再外追加一个需求：后续redcap追加能力的时候，优先考虑“100%固化保障，而非口头协议”这个力度，只有在评估“该能力不需要这么严格保障”时才允许突破。”

### 1.2 触发背景

这次需求来自一次现实纠偏：Cap 先给出了“三分法 / 前进刻度表”的架构建议，随后才说明那只是主 Agent 建议稿，不是“我们一起评审”的结论。这个暴露的问题不是某一句话错了，而是 RedCap 还缺一条明确机制：哪些输出一旦变成工程结论，就不能再由单 Agent 自证。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 用棱镜多视角击溃单视角局限，并把“结论必须共同评审”和“新增能力优先固化保障”写成机制，而不是口头协议。 |
| 已覆盖 | 新增 conclusion policy、checker、执行保障条目；同步核心契约、完整贡献规范、Prism 协议、Prism README、review tracks、治理 checklist、文件字典、lessons；接入 spec-check / diagnose。 |
| 未覆盖/延期 | 不宣称 Codex.app 每一句即时回复都被 RedCap 物理拦截；这个仍取决于宿主是否提供并证明 pre-send hook。 |
| 用户可见边界 | 可以声明“RedCap 官方结论面已进入 Prism-backed gate”；不能声明“任何宿主任何即时句子都被 100% 物理拦截”。 |
| 后续路径 | 后续若有正式发布、长期路线、完成性、风险分类等结论，都要先按本机制进入 Prism 或明确 resource-limited 证据链。 |

---

## 二、方案讨论

### 2.1 问题分析

这不是简单加一句“以后记得找棱镜”。真正的问题是：RedCap 需要区分“解释已有事实”和“产出工程结论”。解释已有 receipt、命令输出或 tracked policy，可以由主 Agent 直接说明；但一旦结论会改变后续任务、路线、发布姿态或治理规则，它就必须进入多人视角。

### 2.2 方案选项

| 选项 | 描述 | 优点 | 缺点 |
|---|---|---|---|
| 只写聊天约定 | 在对话里承诺以后都叫棱镜 | 快 | 最容易在长任务中失效 |
| 只改 Prism 文档 | 把规则写进 `prism/protocol.md` | 能指导调用 | 仍可能不被 spec/diagnose 发现 |
| policy + checker + execution guarantee | 定义结论类别、允许例外、降级边界，并接入 spec/diagnose | 可检查、可回归、可 closeout | 需要维护少量规则文件和短语检查 |

### 2.3 决策结果

| 采纳方案 | 决策理由 | 决策方 |
|---|---|---|
| policy + checker + execution guarantee | 只有这条路径能把“共同评审”从口头纪律变成 RedCap 的执行保障；它也保留了低风险解释和 host-limited 边界，不会过度承诺。 | CAP_DECIDE + Prism 验收 |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|---|---|---|
| `references/conclusion-prism-policy.json` | 新建 | 定义 RedCap 官方结论、Prism-backed 要求、资源受限降级和新增能力固化保障优先级。 |
| `compass/tools/redcap-conclusion-prism-check.py` / `.sh` | 新建 | 校验 policy、核心契约、Prism 协议、执行保障、字典覆盖和 host-limited 边界。 |
| `compass/CONTRIBUTING.core.md` | 修改 | 把结论 Prism-backed 和新增能力固化保障优先级加入启动必守红线。 |
| `compass/CONTRIBUTING.md` | 修改 | 在 Prism 章节新增“结论性输出 Prism Gate”和“新增能力的固化保障优先级”。 |
| `prism/protocol.md` / `prism/README.md` | 修改 | 把 official conclusion、proposal/first-pass、resource-limited 边界写入 Prism 协议。 |
| `references/execution-guarantees.json` / `redcap-execution-guarantee-check.py` | 修改 | 新增 P0 保障项 `prism-backed-conclusion-gate` 和 `guarantee-first-capability-gate`。 |
| `compass/tools/redcap-spec-check.sh` / `redcap-diagnose.sh` | 修改 | 将新检查器接入全量规格检查和诊断链。 |
| `references/review-tracks.json` / `governance-review-checklist.md` | 修改 | 将结论 gate 和固化保障优先级纳入治理评审轨。 |
| `references/file-lookup-dictionary.md` / `.json` | 修改 | 为新增关键文件补人类/Agent 查阅入口。 |
| `compass/knowledge/lessons.md` / `lessons/l-157.md` | 修改 / 新建 | 沉淀“结论性输出不能单人自证”的经验。 |

### 3.2 技术实现要点

本轮把“结论”重新定义成一个可治理对象。普通解释不需要每次都召集棱镜，但凡会影响工程路线、完成性、发布姿态、风险分类或治理规则的官方结论，都必须进入 Prism-backed gate。

固化保障优先级也被写成默认工作方式：新增能力时先找可执行落点，找不到才允许降级，而且要说明为什么不能自动化。这样后续不会再出现“说得很好，但没有任何机制能发现它失效”的空心规则。

这套机制也诚实保留了宿主边界：RedCap 现在能 fail-close repo-owned 官方结论、任务报告和 closeout，但不能宣称已经物理拦截 Codex.app 每一句即时回复。未落盘、未过 Prism 的主 Agent 判断只能叫建议稿。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|---|---|---|
| RedCap 官方结论 | `references/conclusion-prism-policy.json` | 会影响后续工程行动的结论，比如“是否完成”“是否可发布”“属于历史债务还是长期演进”。 |
| Prism-backed | `prism/protocol.md` | 不是 Cap 自己说了算，而是经过棱镜多视角复核、验收或有资源受限证据链。 |
| proposal / first-pass | `references/conclusion-prism-policy.json` | 主 Agent 未经 Prism 的初步建议，可以讨论，但不能当工程决议。 |
| 固化保障优先级 | `references/execution-guarantees.json` | 新规则默认先找脚本、validator、hook、acceptance、receipt 等可执行落点。 |

### 3.3 关联变更

- 新增 L-157 经验，防止后续再次把单人建议误写成共同结论。
- review tracks 与治理 checklist 也同步更新，避免 Prism/治理评审遗漏这条新规则。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|---|---|---|---|
| 1 | 无必须人工审核项 | 本轮没有触及发布、凭据、许可证、删除历史资产或外部账号操作。 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|---|---|---|
| 结论 gate 自检 | `bash compass/tools/redcap-conclusion-prism-check.sh` | 通过 |
| 执行保障自检 | `bash compass/tools/redcap-execution-guarantee-check.sh` | 通过 |
| 字典覆盖 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过 |
| review tracks | `bash compass/tools/redcap-review-tracks-check.sh` | 通过 |
| Prism dispatch 预检 | `bash prism/tools/prism-dispatch-check.sh --mode test --agents "claude&claude-sonnet-4.6:reviewer,kimi&kimi-k2:reviewer"` | 通过 |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过：2 responded / 2 families / 0 blockers |
| spec-check | 待 closeout 前执行 | 待执行 |
| diagnose | 待 closeout 前执行 | 待执行 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 后续真实 closeout 周期中观察 resource-limited 是否被滥用为跳过 Prism 的捷径。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|---|---|
| 执行承诺账本 | 待 closeout 核对 |
| 棱镜验收 | 已通过：Claude Code + Kimi 双路，无 blocker |
| closeout summary | 待生成 |
| closeout receipt | 待生成 |
| rescue audit（如有） | 待 closeout 后确认 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|---|---|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，Prism acceptance 已通过 |
| 已正式完成 | 否；receipt 是唯一正式完工凭证 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|---|---|---|
| Codex.app 每一句即时回复的物理 pre-send veto | 当前宿主未证明提供可用拦截点；RedCap 只能约束 tracked official conclusion / closeout / report。 | 长期演进 |
| resource-limited 降级滥用风险 | 需要通过后续真实任务观察和 closeout 审计发现，不适合本轮伪造场景。 | P2 |

### 6.2 触发的新问题

无新的阻塞问题。Kimi 指出的两个小风险已在本轮直接修复；Claude Code 提醒的完整 spec/diagnose 将在 closeout 前执行。

### 6.3 推荐的下一步行动

1. 运行 spec-check、diagnose 与 closeout runtime。
2. 后续每次涉及架构/风险/完成性/发布/路线的结论，先判断是否是 official conclusion；若是，走 Prism-backed gate。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|---|---|---|
| L-157 | 结论性输出不能单人自证，新增规则默认先找固化保障 | 评估性和结论性输出必须 Prism-backed；新增机制默认先找可执行保障，不能只靠口头协议。 |

### 7.2 流程改进建议

后续对话中的架构性归纳，若只是主 Agent 即时建议，应主动标“建议稿”；若要作为 RedCap 的正式路线或分类，就必须进入 Prism-backed gate。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|---|---|---|---|
| 无新增候选 | 用户纠偏 + Prism verdict | 已直接 promoted 为 policy / checker / lesson | `references/conclusion-prism-policy.json`、`compass/knowledge/lessons/l-157.md` |

---

## 八、附录

### 附录 A：Commits

```
待提交
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|---|---|---|---|
| test | 审查 conclusion Prism gate 与 guarantee-first gate 是否真正固化 | Claude Code pass、Kimi pass、0 blocker；Kimi 风险已修复 | `prism/runs/20260510-prism-conclusion-guarantee-hardening/` |
