# Prism

> RedCap 的多 Agent Team 验证层。

Prism 不是普通“多问几个模型”。
它是一套把**独立取样、结构化收集、聚合裁决、run-scoped 证据**组合起来的团队协议，用来处理高后果问题。

## 它负责什么

- 架构方案需要多视角验证
- 核心治理补丁需要跨模型族审查
- 重要争议需要独立视角而不是单 Agent 自证
- 高风险结论需要 formal quorum，而不是单路 reviewer 口头背书

## 它不负责什么

- 任何长任务的默认拆解
- 一切复杂任务的默认并行器
- 取代 Loom 状态机去做日常开发编排

原则很简单：
- **复杂/长任务先拆解**
- **高风险/高后果问题再进 Prism**

## Prism 的 4 种模式

| 模式 | 用途 |
|---|---|
| `explore` | 架构探索、方向未定，但还没到强对抗阶段 |
| `redteam` | 高风险方案、关键治理改动、需要挑战者视角 |
| `council` | 连续分歧、需要多轮议事收敛 |
| `test` | 对框架关键能力做结构化验证 |

## 它为什么像一个 Team

Prism 的关键不是“数量多”，而是**协议硬**：

- **独立取样**：不同 Agent 不共享中间答案
- **多模型族**：避免单家模型闭环自证
- **角色分工**：挑战者、审查员、旧错者、探索者等各自承担不同视角
- **结构化 Collect / Synthesize / Adjudicate**：不是聊天记录堆积
- **run-scoped truth**：每次运行有自己的 `session-registry.yaml`、`raw.txt`、`parsed.json`

## 默认选型口径

Prism 候选 roster 的默认排序，现在和 stop-review 保持一致：

1. **先看模型能力画像与适用场景**
2. **再看本机该 CLI 的本地稳定性**
3. **最后再看真实 headless 健康**

需要特别注意：

- `registry cache` 只说明安装/配置可见
- 不代表登录态、限流、MCP/Hook 噪声或真实可完成审计
- 所以正式 Prism 前，必须把“可见”与“可健康运行”分开记录

## 运行证据长什么样

Prism 不是只留一份报告。
formal 运行至少有两层证据：

- `prism/runs/<run_id>/...`
  - `session-registry.yaml`
  - `collect/*/raw.txt`
  - `collect/*/parsed.json`
- `prism/reports/*.md` + `prism/reports/index.yaml`

只有**报告归档 + index 登记 + archive-check 通过**，才算 formal Prism 完成。

本地 `prism/runs` 目录里的运行夹具，不再默认一律永久保留：

- `formal-run` 默认保留
- `acceptance-fixture` 可进入安全清理集
- `named-local-evidence` 会进入“保留期 + 审查后清理”的生命周期，而不是无限堆积

入口在：
- `bash prism/tools/prism-runs-lifecycle.sh summary`
- `bash prism/tools/prism-runs-lifecycle.sh inventory`
- `bash prism/tools/prism-runs-lifecycle.sh prune-local`（dry-run）

## 什么时候不要滥用它

- 小改动、低风险、边界清晰的问题
- 已有 Loom / Reviewer 就足够闭环的场景
- 只是想“多叫几个模型来看看”但没有清晰的验证目标

Prism 是**验证系统**，不是“豪华群聊”。

## 先读哪里

- 正式协议：[`protocol.md`](./protocol.md)
- 模式说明：[`modes/README.md`](./modes/README.md)
- 角色目录：[`roles/README.md`](./roles/README.md)

## 一句收束

**Prism 的价值，不在于多模型本身，而在于把多模型协作升级成可审计的团队协议。**
