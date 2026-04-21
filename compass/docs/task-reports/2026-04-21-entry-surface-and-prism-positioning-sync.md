# 任务完成报告：入口展示与棱镜定位收敛

**报告日期**：2026-04-21
**执行者**：Cap（Codex / GPT-5.4）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：根 README、`prism/README.md`、`prism/protocol.md` 与 `redcap-current-status.sh` 已同步到最新真实口径。
- 详情：README 现在更短、更聚焦，明确把 Prism 提升为 RedCap 的核心范式之一；Prism 展示层与协议层已写明“模型能力画像 + 本地 CLI 稳定性 + 真实 headless 健康”的默认选型规则，同时明确“复杂/长任务 ≠ 必然 Prism”；`current-status` 则默认轻量刷新 agent registry，避免继续误报 `kimi/copilot=false` 这类旧 cache 状态。

### 0.2 上一步完成的是

- 上一步完成的是：先确认 `kimi -y -p 你好` 与 `copilot -p 你好` 在本机可真实启动，再重跑 `redcap-detect-agents.sh` 证明先前 `current-status` 的 `false` 来源于过时 cache，而不是 CLI 真不可用。

### 0.3 下一步计划做的是

- 下一步计划做的是：如果继续治理入口层，优先处理 README / Prism README / ARCHITECTURE 等“对外展示面”的进一步统一，以及 GD-009 的 read-only-safe 诊断链改造。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：识别 README / Prism / current-status 的口径断层 → 收敛入口展示面 → 同步协议层 → 修复状态入口 stale cache → 回填报告与索引。
- 当前所在位置：本轮已完成，处于“入口展示层与状态入口已同步、无当前 blocker”的终局态。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 1. 你例举要突出的redcap核心优秀范式里，居然没有棱镜的多Agent Team框架？这令我很诧异，这个不足以写上一笔吗？  
> 2. README不是不可以框架图、工作流，但是要注重：言简意骇、表达redcap核心优势。不能因为平铺细节而无节制展开  
> 3. 我觉得根据上面你的回答，你能制定的计划和todo绝对不止这2个吧？你可以把所有你看到的、规划的、想做的任务都列为todo，然后全部完成

### 1.2 本轮锁定的 todo

| 序号 | todo | 目标 |
|---|---|---|
| 1 | 重写根 README | 变成更短、更强的框架名片，并明确突出 Prism |
| 2 | 重写 `prism/README.md` | 明确 Prism 是多 Agent Team 验证层，而不是附属功能 |
| 3 | 同步 `prism/protocol.md` | 把默认 roster 选型与“长任务 ≠ 必然 Prism”的边界写进正式协议 |
| 4 | 修 `redcap-current-status.sh` | 默认轻量刷新 registry，减少 stale cache 误报 |
| 5 | 回填 task report / docs catalog | 让账面与入口同步收口 |

---

## 二、方案讨论

### 2.1 核心判断

这轮问题的本质不是“README 写得不好看”，而是**入口展示层与执行层已经开始漂移**：

- README 仍在用“优先 Gemini”这类过时口径
- Prism 虽然在执行体系中已是核心验证层，但展示层强调度不足
- `current-status` 只读 cache，不主动轻量刷新，导致用户刚刚实测可用的 CLI 仍被显示为 `false`

### 2.2 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---|---|---|
| Q1 | README 改成“范式优先”的短入口 | 入口文档首先要表达 RedCap 的设计艺术，而不是目录展开 | CAP_DECIDE |
| Q2 | Prism README / protocol 双同步 | 只改 README 不够，必须把正式协议层也同步到最新真实规则 | CAP_DECIDE |
| Q3 | `current-status` 默认轻量刷新 registry | 这是最小、最稳、最直接的修复，不需要动 probe 模式或重度健康探测 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|---|---|---|
| `README.md` | 重写 | 聚焦 RedCap 核心范式，明确把 Prism 作为主角之一，并删除过时的“优先 Gemini”口径 |
| `prism/README.md` | 重写 | 重新定义 Prism 的定位、边界、模式与 run-scoped 证据价值 |
| `prism/protocol.md` | 修改 | 新增默认 roster 选型规则，并明确“长任务拆解”与“Prism 验证”的职责边界 |
| `compass/tools/redcap-current-status.sh` | 修改 | 默认轻量刷新 agent registry，并在输出里说明 refresh 状态 |
| `compass/docs/task-reports/2026-04-21-entry-surface-and-prism-positioning-sync.md` | 新建 | 本轮任务报告 |
| `compass/docs/catalog.json` | 修改 | 重新生成 docs catalog，纳入本轮报告 |

### 3.2 这轮真正修掉的误导

| 问题 | 修复结果 |
|---|---|
| README 没把 Prism 当成 RedCap 的核心能力 | 已修正，Prism 现在是 README 的核心范式之一 |
| README 仍保留过时的“优先 Gemini”口径 | 已删除，统一回到“模型能力画像 + 本地 CLI 稳定性” |
| Prism 展示层没清楚表达“多 Agent Team 验证层” | 已修正 |
| `current-status` 被旧 registry cache 误导 | 已默认在入口层做轻量 refresh |

---

## 四、人工审核要点

本轮没有当前任务级必须人工 gate 的事项。  
如果要继续下一 tranche，真正需要人工拍板的是：是否继续投入 README / ARCHITECTURE / Prism 展示层的更系统品牌化重构，而不是这轮口径同步本身。

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|---|---|---|
| registry 轻量刷新 | `bash compass/tools/redcap-detect-agents.sh compass/.workflow/agent-registry.yaml` | ✅ |
| current-status | `bash compass/tools/redcap-current-status.sh .dev-task.md` | ✅ |
| spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | ✅ |
| diagnose | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | ✅ |
| diff 格式检查 | `git diff --check` | ✅ |

### 5.2 手工交叉核对

- `kimi -y -p 你好`：可正常返回
- `copilot -p 你好`：可真实启动
- `current-status` 在 refresh 后显示 `kimi=true`、`copilot=true`

---

## 六、遗留问题与下一步

### 6.1 当前剩余项

| 分类 | 条目 | 是否阻断本轮 |
|---|---|---|
| 治理债务 | `GD-008` 主 Agent 实时行为约束仍属 host-limited | 否 |
| 治理债务 | `GD-009` 首读/诊断链尚未 read-only-safe | 否 |
| 历史证据残留 | `prism/runs` 仍保留 19 个目录 | 否 |

### 6.2 推荐的下一步

1. 若继续治理入口面，可进一步收敛 `ARCHITECTURE.md` / `prism/modes/README.md` / 对外介绍层。
2. 若继续治理宿主能力边界，优先把 `GD-009` 提升为显式 todo。

---

## 七、经验沉淀

### 7.1 本轮经验

| 编号 | 标题 | 核心内容 |
|---|---|---|
| 本轮复用已有经验 | 入口展示层不能落后于执行层 | 当执行层已升级规则后，README / Prism README / current-status 若不及时同步，就会把用户重新带回旧口径 |

---

## 八、附录

### 附录 A：Commits

```text
尚未提交；当前为工作区内治理补丁。
```

### 附录 B：相关文档索引

- 根入口：`README.md`
- 棱镜入口：`prism/README.md`
- 正式协议：`prism/protocol.md`
- 状态入口：`compass/tools/redcap-current-status.sh`
