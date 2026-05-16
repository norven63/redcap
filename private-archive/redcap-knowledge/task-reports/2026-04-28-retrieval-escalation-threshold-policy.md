# 任务完成报告：Retrieval escalation threshold policy

**报告日期**：2026-04-28
**执行者**：Cap（Codex.app）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P3-1 已把“GraphRAG / 向量检索阈值研究”从口头 deferred 升级为机器可审计的检索升级策略。
- 详情：当前 RedCap 仍保持 `catalog + rg + metadata` 路线；只有 `shared-knowledge` / `redcap-arsenal` 规模、语义召回失败观测或关系型问题观测跨过策略阈值后，才允许另开任务评估 FTS/RAG/GraphRAG。

### 0.2 上一步完成的是

- 上一步完成的是：P3-2 已把父任务 completed child 从 `receipt_glob` 字符串升级为真实 runtime receipt 内容对应强门，并完成 closeout receipt 收口。

### 0.3 下一步计划做的是

- 下一步计划做的是：提交本轮实现并运行 closeout runtime 生成 receipt；若后续 `redcap-arsenal` 真正积累大量条目，再按本策略触发新的检索升级任务。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：父任务聚合 gate → receipt 内容对应强门 → 检索升级阈值策略 → Prism review → closeout receipt。
- 当前所在位置：`redcap-system-migration-parent / P3-1 / retrieval-escalation-threshold-policy`。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 好的，那么请继续推进，务必要和棱镜团队之间配合好，稳步迭代、谨慎评审与验收

### 1.2 触发背景

P3-1 长期被标记为 deferred，因为公共知识库尚未增长到需要 GraphRAG / 向量检索的规模。继续推进时不能为了“完成任务”硬上重型系统；真正需要的是把 deferred 的判断标准固化为可复验策略，让未来是否升级由证据触发，而不是由流行趋势或 Agent 主观冲动触发。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 继续父任务主线，并与棱镜团队配合，谨慎评审验收 |
| 已覆盖 | P3-1 检索升级策略、checker、acceptance、spec/diagnose 接线、父任务账本更新和 closeout 收口 |
| 未覆盖/延期 | 真实 GraphRAG 系统、embedding 模型、向量数据库、跨机器知识库同步、历史资产真实迁移 apply |
| 用户可见边界 | P3-1 完成不等于 RedCap 已启用 GraphRAG；它证明“何时才允许评估升级”已经有机器门禁 |

---

## 二、方案讨论

### 2.1 问题分析

当前 `redcap-arsenal` 只有模板文件和 `users/Norven` 命名空间占位，真实共享知识条目数为 0。此时引入向量库或 GraphRAG 会把系统复杂度、隐私风险、索引维护和证据链维护都提前拉高，而收益不足。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|---|---|---|---|
| Q1 | A | 继续口头 deferred | 不改代码 | 后续 Agent 仍可能忘记或误读 |
| Q1 | B | 立即接入 RAG/GraphRAG | 看起来完成“高级检索” | 当前规模下过度设计，且增加隐私和维护面 |
| Q1 | C | 建立检索升级策略与 checker | 把“不升级”的理由变成机器门禁，未来跨阈值自动暴露 | 需要维护阈值和观测字段 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---|---|---|
| Q1 | C | 当前数据规模不支持重型检索，但父任务需要结束“口头 deferred”状态；策略 + checker 是最小可审计推进 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|---|---|---|
| `references/retrieval-escalation-policy.json` | 新增 | 定义当前路线、FTS/RAG/GraphRAG 触发阈值、禁止默认全文加载和未来升级动作 |
| `compass/tools/redcap-retrieval-escalation-check.py` / `.sh` | 新增 | 动态读取 docs catalog 与 shared-knowledge / redcap-arsenal 规模，判断当前路线是否仍有效 |
| `compass/tools/redcap-spec-check.sh` / `redcap-diagnose.sh` | 修改 | 将检索升级 checker 接入 spec 与诊断门禁 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 增加当前不触发、过早启用 RAG 失败、默认全文加载失败、阈值跨越失败的 targeted acceptance |
| `references/redcap-system-layers.md` / `shared-knowledge-policy.json` | 修改 | 将 Retrieval Layer 的升级口径指向机器策略 |
| `references/execution-guarantees.json` / `file-lookup-dictionary.*` | 修改 | 登记检索升级门禁与查找入口 |

### 3.2 技术实现要点

- checker 只统计元数据和文件大小，不读取正文，避免检索治理本身成为 token 污染源。
- 当前实测规模：docs catalog `files=64 / lines=15927`，shared-knowledge + redcap-arsenal authored entries 为 `0`。
- 当前路线：`index-rg-metadata`；若 FTS/RAG/GraphRAG 任一阈值跨越而路线仍未升级，checker 会 fail-closed。
- 人工观察型阈值（语义召回失败、关系型问题、跨实体追踪失败）已有 `observation_update_rule`：只有从任务报告、棱镜审查或共享知识导入批次中获得证据时才更新，避免凭感觉调阈值。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|---|---|---|
| `active_route` | `references/retrieval-escalation-policy.json` | RedCap 当前允许使用的检索路线；本轮是 `index-rg-metadata` |
| `index-rg-metadata` | docs catalog、knowledge index、file lookup dictionary、`rg` | 先看索引、摘要和精确路径，再按需打开正文，不把资料库全文塞进上下文 |
| RAG | 未来可能的 chunk + embedding + rerank | 语义召回方案，只有关键词/元数据失效且失败有观测时才评估 |
| GraphRAG | 未来可能的实体/关系图谱 | 关系型问题频繁出现且普通检索明显不足时才评估，不在小规模知识库里默认启用 |
| `redcap-arsenal` | `/Users/norven/.claude/skills/redcap-arsenal` | 公共知识库本体；当前只有模板与 Norven 命名空间，没有大量真实条目 |

### 3.3 当前阈值口径

| 层级 | 触发条件摘要 | 当前结论 |
|---|---|---|
| FTS | docs 文件数或行数显著增长，或 shared-knowledge 条目达到 200 | 未触发 |
| RAG | shared-knowledge 条目达到 500、体量达到 5MB，或 30 天内语义召回失败达到 10 次 | 未触发 |
| GraphRAG | shared-knowledge 条目达到 1000，或 30 天内关系型问题/跨实体追踪失败达到阈值 | 未触发 |

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|---|---|---|---|
| 1 | 阈值是否过严或过松 | 本轮阈值是工程默认值，后续真实知识规模增长后可用任务数据校准 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|---|---|---|
| PM Gate | `bash compass/tools/redcap-pm-gate-check.sh strict codex .dev-task.md` | 通过 |
| 原始意图覆盖 | `bash compass/tools/redcap-intent-coverage-check.sh .dev-task.md` | 通过 |
| 中插需求检查 | `bash compass/tools/redcap-change-intake-check.sh .dev-task.md` | 通过 |
| Python 编译 | `python3 -m py_compile compass/tools/redcap-retrieval-escalation-check.py` | 通过 |
| retrieval escalation | `bash compass/tools/redcap-retrieval-escalation-check.sh` | 通过，输出 `active_route=index-rg-metadata ... shared_entries=0` |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh retrieval-escalation-check` | 通过 |
| spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| diagnose | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 通过 |
| Prism review | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过：2 agents / 2 families / 0 blockers |
| full acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh all` | 通过：第四轮完整通过 `ACCEPTANCE_OK` |

### 5.1.1 执行中发现并修复的问题

| 问题 | 根因 | 处理 |
|---|---|---|
| P3-1 deferred 只有口头边界 | 父任务账本说等待共享库规模，但没有机器门禁说明何时“等待结束” | 新增 retrieval escalation policy/checker，并接入 spec/diagnose/acceptance |
| 过早上 RAG 的诱惑无法被脚本阻断 | 原先只有文档描述 GraphRAG 不应过早引入 | checker 校验 active route 与阈值，过早启用 `rag` 或默认全文加载会 fail-closed |
| 观察型阈值缺少更新规则 | Kimi review 指出语义召回失败/关系型失败等字段如果没人更新，只能依赖规模阈值 | 新增 `observation_update_rule`，规定证据来源、写入目标和必须更新的任务节点 |
| stop-review acceptance 受当前 `.dev-task.md` scope 污染 | 多个 stop-review fixture 未设置隔离 task file，full acceptance 会被当前真实任务的 drift-check 抢跑 | 在 `redcap_acceptance_on_stop_review` helper 中为未显式指定的用例自动注入 permissive task file |
| macOS `mktemp` 后缀模板不稳定 | `XXXXXX.md` 在 BSD/macOS `mktemp` 下可能失败，导致 fallback task path 为空 | 改为无后缀 `mktemp "$ACCEPT_ROOT/on-stop-review-task.XXXXXX"`，定点与 full acceptance 均通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- 暂无。阈值本身后续可由真实使用数据校准，但本轮无需人工决策。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|---|---|
| 执行承诺账本 | 待 closeout 核对 |
| 棱镜验收 | 已通过，见附录 B |
| closeout summary | 待本报告提交后生成 |
| closeout receipt | 待本报告提交后由 closeout runtime 生成 |
| rescue audit（如有） | 待生成 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|---|---|
| 已实现 | 是 |
| 已自检 | 是，targeted/spec/diagnose 通过 |
| 已独立验收 | 是，Kimi + Claude Code 棱镜双路无 blocker |
| 已正式完成 | 提交前仍为否；本报告提交后以 closeout runtime receipt 作为唯一正式完工凭证 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|---|---|---|
| 真实 FTS/RAG/GraphRAG 实现 | 当前知识库规模未触发阈值，过早实现会增加复杂度 | P3，触发后另开任务 |
| 历史资产真实迁移 apply | 本轮只处理检索升级阈值，不搬迁历史资产 | P1，需单独风险窗口 |
| 真实公网发布 / 跨机器安装 E2E | 本轮不属于发布任务 | P2 |

### 6.2 触发的新问题

暂无。

### 6.3 推荐的下一步行动

1. 本报告提交后运行 closeout runtime 生成正式 receipt。
2. 后续如果 `redcap-arsenal` 开始产生大量真实条目，先跑 `redcap-retrieval-escalation-check.sh`；若失败，再按策略开启检索升级任务。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|---|---|---|
| L-pending | 不升级也要有门禁 | 当正确决策是“暂不引入重型系统”时，不能只写 deferred；应把不升级的条件和未来升级阈值写成机器可验策略 |

### 7.2 流程改进建议

对所有 “deferred until scale” 项，后续优先问：规模阈值在哪里？谁统计？阈值跨越后如何 fail-closed？如果答不上来，就不是合格 deferred，而只是口头延期。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|---|---|---|---|
| 检索升级阈值门禁 | P3-1 GraphRAG / 向量检索阈值研究 | no-promote 不适用：已直接落成 policy/checker/acceptance，不进入候选池等待 | `references/retrieval-escalation-policy.json`、`redcap-retrieval-escalation-check.py` |

---

## 八、附录

### 附录 A：Commits

```
本报告随本轮实现提交；最终 commit hash 以 closeout runtime receipt 为准。
```

### 附录 B：棱镜调用记录（如有）

- run_id: `20260428-retrieval-escalation-threshold-policy`
- Kimi reviewer：`pass_with_notes`，0 blocker；主要 notes 已处理为 observation update rule 与断点备注刷新。
- Claude Code challenger：`pass`，0 blocker。
- Prism acceptance：`pass`，responded=2，family_count=2，blocker_roles=0。

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- 检索升级策略：`references/retrieval-escalation-policy.json`
- 系统分层路线图：`references/redcap-system-layers.md`
