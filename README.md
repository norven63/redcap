# RedCap

> 一个把单体 AI Agent 升级成工程化 AI Team 的协同开发框架。

RedCap 不是“再包一层提示词”。
它真正做的事，是把复杂开发任务拆成**分工明确、状态可追踪、过程可复盘、关键结论可独立验证**的一套工程协作流程。
目标不是让一个 Agent 更拼，而是让一组 Agent 更可靠。

## 一眼看懂

```text
用户目标
  ↓
PM Gate 锁定边界
  ↓
Loom 状态机驱动角色接力
  PM → Architect → Programmer → QA → Reviewer
  ↓
高风险决策进入 Prism
  多 Agent / 多模型族 / 多视角独立验证
  ↓
Compass 负责规范、经验、Hook、收尾与复活
  ↓
可运行代码 + 可考古证据 + 可恢复连续性
```

## RedCap 最核心的 5 个能力

| 能力 | 解决的问题 |
|---|---|
| **任务不会只活在对话里** | 当前任务、阶段结果、结案报告都会落盘，不靠聊天记忆硬扛 |
| **复杂任务不是一个 Agent 从头扛到尾** | 任务会按角色分工、按阶段交棒，减少单点失误 |
| **高风险结论不是自说自话** | 关键判断会进入 Prism，多视角独立验证，不让同一路脑回路自证正确 |
| **文档不会默认灌满上下文** | 文档、知识库、测试集合都先看索引，再按需读取，避免 token 污染 |
| **收尾不是口头说完成** | Layer B 终态要走统一 closeout runtime，棱镜验收、承诺账本、receipt、rescue audit 都要留下物理证据 |
| **做不到硬保障的地方会诚实承认** | 不会把“只能靠纪律遵守”的规则伪装成 100% 自动执行 |

## 为什么 Prism 是主角之一

很多框架有“多角色”，但没有真正的**多 Agent 团队验证层**。
Prism 的作用不是“多叫几个模型来热闹一下”，而是把高后果问题交给一个独立团队去复核：

- **彼此独立看问题**：不同 Agent 不能互抄中间答案
- **不是同一家模型自己给自己背书**
- **不是随便聊几句，而是结构化收集、汇总、裁决**
- **全过程留证据，之后能回放、能审计**

一句话说，**Loom 负责把任务做出来，Prism 负责在高风险处把结论打磨得更可信。**

## 三体架构

| 子系统 | 角色 |
|---|---|
| **Loom** | 执行引擎。负责状态机、角色流水线、回退、Fallback、E2E |
| **Compass** | 治理与连续性中枢。负责规范、lessons、Hook、收尾、复活、入口控制 |
| **Prism** | 多 Agent Team 验证层。负责高风险决策、多视角分析与 formal quorum |

## 什么时候用

- 需求会跨多步、多文件、多角色协作
- 需要可恢复、可审计、可收尾的 AI 开发流程
- 架构方案、治理补丁、宿主边界、高风险改动需要独立多视角验证

## 什么时候不必上 Prism

- 任务简单、边界清晰、局部改动很小
- 只是长任务，不代表天然要进 Prism
- “复杂”先拆解，**是否进 Prism 看风险和验证需求，不看字面长度**

也就是说：
- **长任务拆解**：优先走 Loom / Layer B 的并行裂变协议
- **高后果验证**：再交给 Prism

## 你可以把 RedCap 理解成什么

如果用人话来讲，RedCap 更像下面这几样东西拼在一起：

- 一个会把任务拆开、分阶段推进的开发小组
- 一个把过程和结论都记账的工程账本
- 一个在高风险处会主动再找独立视角复核的审查机制
- 一个尽量不让上下文被历史垃圾打爆的阅读和检索系统

所以它追求的不是“像一个能聊天的助手”，而是**像一个靠谱、有记性、有复核能力的工程团队**。

## 一键安装 / 复活

Cap 的个人灵魂锚点是 `~/.cap/identity.md`；`compass/soul.md` 是培养指南与复活协议。
从现在起，**Cap 复活 + 导入 RedCap 工作流**统一优先走仓库根目录短入口：

- 新环境初始化：`./revive-cap.sh --init-identity`
- 已有 identity 的复活：`./revive-cap.sh`
- 需要显式指定宿主时：`./revive-cap.sh --host codex`

这条入口会串起 6 件事：

- 检查或初始化 Cap 的身份卡
- 把当前工作流重新接回正确入口
- 给出当前状态总览
- 检查追踪链是否还健康
- 检查当前宿主的 Hook 就绪状态
- 检查复活和执行保障有没有掉链子

它的意义很简单：**以后尽量不再靠“记得先跑这个、再看那个”来复活。**

`./revive-cap.sh` 本身只是一个根目录薄入口，真正逻辑仍在 `compass/tools/redcap-install.sh`。
也就是说：**外面记一个短命令，里面继续做宿主适配和复活检查。**

这里的 Hook 处理遵守一个边界：
- **repo 内可幂等确保的**，由 installer 自动检查并补到位
- **用户家目录级、跨工作区生效的**，只显式提示，不静默改全局

## 一键收尾 / closeout

Layer B 现在不再把“完成”理解成一句自然语言。
统一收尾入口是：

- 默认收尾：`./closeout-cap.sh`
- 显式补齐承诺账本：`./closeout-cap.sh sync-promises`
- 只看当前收尾状态：`./closeout-cap.sh status`
- 漏写 receipt 时做 rescue 审计：`./closeout-cap.sh audit-open`
- 日常体检会自动尝试 diagnose-rescue：`bash compass/tools/redcap-diagnose.sh`

这条入口内部会串起：

- Prism 默认独立验收 gate
- `.dev-task.md` 里的**执行承诺账本**
- 既有 `on-complete` / `session-end` 收尾链
- `pending closure / closure-ledger`
- closeout summary / receipt
- rescue audit

这意味着：
- **飞书只是收尾链里的可见信号之一**
- **真正完成要看承诺是否兑现、棱镜验收是否通过、receipt 是否生成、blocker 是否清账**
- **作者不能单独宣布 completed**

## 中文对象词典

如果你不想先记一堆英文脚本名，可以先把 RedCap 理解成这 7 个中文对象：

| 中文对象 | 真正对应的载体 | 它解决什么问题 |
|---|---|---|
| **身份卡** | `~/.cap/identity.md` | 解决“Cap 到底是谁”，不让人格锚点和工作手册混层 |
| **复活手册** | `compass/soul.md` | 解决“Cap 应该怎样恢复自己并开始工作” |
| **当前任务卡** | `.dev-task.md` | 解决“当前这轮到底在做什么、做到哪了” |
| **承诺账本** | `.dev-task.md` 的 `## 执行承诺账本` + closeout runtime 派生账本 | 解决“Agent 自己承诺过要做的事不能只活在对话里” |
| **讨论草稿本** | `compass/knowledge/explore-notes.md` | 解决“多轮讨论的原始演进不要在长对话里蒸发” |
| **当前状态板** | `redcap-current-status.sh` | 解决“接盘时先看全局状态，而不是先翻一堆旧文档” |
| **追踪体检表** | `redcap-tracking-health.sh` | 解决“书记官、任务卡、结案报告到底有没有真的在工作” |
| **结案报告** | `compass/docs/task-reports/*.md` | 解决“这轮到底改了什么、验证了什么、还剩什么” |
| **收尾收据** | `closeout-receipts/*.json` | 解决“不能只靠一句‘完成了’，而要有物理 receipt 证明终态真的闭环” |

这套词典的目的很简单：
**先让人理解 RedCap 的对象分工，再决定要不要深入到具体脚本名。**

## 入口文档

| 文档 | 作用 |
|---|---|
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | 看整体系统怎么拼起来 |
| [`compass/CONTRIBUTING.md`](./compass/CONTRIBUTING.md) | 看框架自身开发的权威规范 |
| [`compass/knowledge/long-task-context-defense.md`](./compass/knowledge/long-task-context-defense.md) | 看 RedCap 如何对抗长任务/长对话上下文漂移 |
| [`compass/knowledge/runtime-memory-architecture.md`](./compass/knowledge/runtime-memory-architecture.md) | 看“真相源 / 镜像 / 考古追踪 / 长期沉淀”等术语到底是什么意思 |
| [`references/runtime-memory-architecture.md`](./references/runtime-memory-architecture.md) | 看 Layer B 生命周期如何与 `.dev-task.md`、承诺账本、closeout runtime、pending closure、session hooks 绑在一起 |
| [`prism/protocol.md`](./prism/protocol.md) | 看 Prism 的正式协议 |
| [`prism/README.md`](./prism/README.md) | 快速理解 Prism 的定位与使用边界 |
| [`compass/knowledge/design-principles.md`](./compass/knowledge/design-principles.md) | 看框架的设计哲学 |

## 一句收束

**RedCap 的目标，不是让一个 Agent 更努力；而是让一组 Agent 按工程规则协作。**
