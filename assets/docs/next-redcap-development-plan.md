# 下一步 RedCap 开发方案

本方案只定义下一步要落地的开发目标，不作为完成证据。完成证据必须来自运行时能力、检查命令、失败回流和端到端验收。

## 背景判断

首次 E2E（端到端验收）暴露的问题不是“TRPG 示例项目不够好”，而是 RedCap（当前复活工程）还没有充分证明自己能稳定帮助一个独立执行方完成真实工程开发。目标是补“渔”：让 RedCap 更会组织需求、架构、实现、测试、评审、知识沉淀和失败回流，而不是只补一个更漂亮的示例应用。

当前工作区已有几个重要基础：

- Loom（角色化工程工作流）合同已经声明角色、阶段、会话、失败回流和独立 Codex CLI（命令行 Codex）承接要求。
- E2E 运行器已经在局部场景中尝试启动独立 Codex CLI 角色，并要求角色写入会话和证据。
- 自我净化合同已经声明任务前知识检索、任务后候选抽取、晋升或不晋升决策、Cap 私有人格边界。
- 知识网关已经支持检索、草稿、评审和晋升。

但这些能力仍有明显落差：

- Loom 的通用运行机不足。当前更像“合同 + E2E 专用实现”，普通项目任务还缺可复用的角色会话注册、续接、丢失报警和角色交付检查入口。
- 自我净化没有成为普通任务的闭环。它能检查合同，却不能稳定执行“检索 -> 候选 -> 决策 -> 公共晋升或不晋升 -> 下次召回”。
- 知识检索还没有证明会影响后续工作。仅有检索命令或空命中记录，不等于经验真的进入任务决策。
- E2E 过重，不能作为唯一验证手段。需要先补轻量但真实的运行检查，再跑第二轮 E2E。

## 任务队列

### R2-01：Loom 通用角色运行机

目标：把 Loom 从合同检查推进到普通项目也能使用的运行能力。

必须实现：

- 项目级 `.redcap/state/loom/session-manifest.json` 会话清单。
- 每个角色绑定 `project_id + task_id + role`，同一角色必须续接同一 `session_id`。
- session_id 缺失、变化、重复或上下文降级时，写入报警并阻止角色阶段被视为通过。
- 角色交付物必须写入独立目录，并记录上游输入、下游输出、执行回执和可审计证据。
- 棱镜（异构 AI 评审助手）只作为评审协助，不替代 Loom 角色，也不能成为实际执行大脑。

验收命令：

- `runtime/bin/redcap loom-runtime self-check`
- `runtime/bin/redcap loom-runtime manifest-check --project-root <project> --task-id <task>`
- `runtime/bin/redcap loom-workflow check`

### R2-02：自我净化运行闭环

目标：把自我净化从合同检查推进到可执行任务后闭环。

必须实现：

- 任务前检索入口：按任务摘要查询知识库，写入结构化证据。
- 任务后候选入口：从用户纠错、棱镜 concern、E2E 失败、工作流漂移、完成声明纠正等触发源抽取候选。
- 候选决策入口：支持 `promote_public`、`keep_private`、`no_promote`、`defer_with_owner`，且必须写明理由。
- 公共晋升必须经过知识网关、Forge（公共能力锻造）和 Arsenal（公共能力库）边界检查。
- Cap 私有人格沉淀只能写边界证据和摘要哈希，不得把私有正文写入公共仓库。

验收命令：

- `runtime/bin/redcap self-purification self-check`
- `runtime/bin/redcap self-purification run-loop --task-summary <text> --evidence-root <dir>`
- `runtime/bin/redcap knowledge-gateway search <query> --require-hit`

### R2-03：知识召回影响任务决策

目标：证明知识库不是摆设，而是能影响后续任务。

必须实现：

- 对 RedCap 自开发和 E2E 任务，任务前必须检索知识库或写明不可执行理由。
- 检索命中时，后续任务计划必须引用命中的知识条目和采用方式。
- 检索无命中时，不能静默通过；必须记录为什么仍可继续，以及任务后是否产生候选。
- 至少新增一条来自本轮复盘的公共知识条目，并在后续检查中被命中。

验收命令：

- `runtime/bin/redcap knowledge-gateway check`
- `runtime/bin/redcap knowledge-gateway search self-purification --require-hit`
- `runtime/bin/redcap knowledge-gateway search loom --require-hit`

### R2-04：E2E 轻重分层验收

目标：第二轮 E2E 前先用轻量真实检查过滤明显问题，避免无限循环重跑。

必须实现：

- 先跑 Loom 会话检查、自我净化闭环检查、知识召回检查、发布安装检查。
- 只有这些检查通过，才允许进入完整 E2E。
- E2E 的通过标准必须关注 RedCap 工作流质量，不只关注目标项目是否能运行。
- 同一根因连续失败达到上限时，停止普通修复循环，进入架构评审，不继续无意义重跑。
- OL-11（长期第三方生产项目样本）后续执行必须优先采用 `assets/docs/ol11-trpg-longrun-e2e-plan.md`，由 Cap 扮演需求方、验收方和运行观察者，独立开发 AI 使用外部项目 `.redcap/` 承接实现；不得每次临时重新拟题，也不得在方案评审前实际执行。

验收命令：

- `runtime/bin/redcap revival-followthrough check`
- `runtime/bin/redcap complete-revival-e2e design-check`
- 第二轮完整 E2E 只在前置检查通过后执行。

## 暂不作为本轮主线的事项

- 大规模重构 `complete_revival_e2e.py`。它体积偏大，但本轮优先补通用运行能力；只在必要位置做小范围接入。
- 声明 RedCap 完整复活或生产可发布。本轮目标是补齐二次 E2E 前的关键运行能力。
