# 任务完成报告：Runtime receipt evidence correspondence hardening

**报告日期**：2026-04-28
**执行者**：Cap（Codex.app）
**报告版本**：v0.2

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P3-2 已把父任务聚合从“有报告 + receipt_glob 字符串”升级为“必须找到真实 runtime receipt，并核对 receipt 内容与 child 身份、报告、完成态、承诺账本、验收态、repo_path、confirmed_hash 和 git head 对应”。
- 详情：本轮修改 `references/parent-receipt-aggregation-policy.json` 与 `redcap-parent-receipt-aggregation-check.py`，让父任务 completed child 不再只靠元数据形态自证。当前 child 在 closeout 前允许被 `.dev-task.md` 明确锚定为 pre-receipt 例外，历史 child 缺 receipt 或 receipt 内容错配会 fail-closed。

### 0.2 上一步完成的是

- 上一步完成的是：P2-4 已完成首次启动身份初始化与飞书通知策略收敛，并用真实飞书 profile 完成 setup / node-report 验证。
- P2-4 之后父任务账本推荐继续 P3-2，因为父任务聚合虽然已经能防止“父任务误报完成”，但对子任务 receipt 的内容对应关系仍不够深。

### 0.3 下一步计划做的是

- 下一步计划做的是：提交、在提交后重跑 full acceptance（避免 stop-review fixture 被 dirty working tree 误伤），然后 closeout receipt 收口；随后父任务只剩 P3-1 GraphRAG / 向量检索阈值研究继续 deferred。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：父任务聚合 gate → receipt 内容对应强门 → targeted acceptance → Prism review → closeout receipt。
- 当前所在位置：`redcap-system-migration-parent / P3-2 / receipt-correspondence-hardening`。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 好的，了解，我不中断你和棱镜团队的计划节奏，你们配合好，稳步推进主线任务，务必做好符合工程规范的实现落地。

### 1.2 触发背景

P2-2 已经建立父任务 receipt 聚合 gate，但它主要验证父任务仍然 fail-closed、completed child 报告存在、receipt_glob 形态合理、not-complete child 有边界。后续复查发现这还不够：`receipt_glob` 本身只是一个字符串，不等于真实 receipt，也不证明 receipt 内容确实对应这个 child。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 继续 RedCap 父任务主线，稳步推进 P3-2 |
| 已覆盖 | receipt 内容对应强门、P3-2 父任务账本更新、targeted acceptance、独立复评与 closeout 收口 |
| 未覆盖/延期 | P3-1 GraphRAG / 向量检索阈值研究继续 deferred；真实 public release、跨机器安装 E2E、历史资产真实迁移 apply 不在本轮 |
| 用户可见边界 | P3-2 完成不等于父任务整体完成；父任务仍因 P3-1 deferred 保持 incomplete |
| 后续路径 | 当共享知识库规模越过 catalog + rg + metadata 的舒适区后，再启动 P3-1 |

---

## 二、方案讨论

### 2.1 问题分析

父任务聚合不能只检查“报告文件存在”和“receipt_glob 看起来像 receipt 文件名”。如果没有打开 runtime receipt 并核对内容，未来可能出现三类假阳性：glob 没有匹配任何文件、receipt 对应的是别的 task、receipt 指向了过时或错误报告。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|---|---|---|---|
| Q1 | A | 继续只检查 receipt_glob 字符串 | 改动小 | 仍然可能被空 glob 或错 receipt 误导 |
| Q1 | B | 每个 child 手写 receipt 绝对路径 | 直接 | receipt 文件名与 runtime hash 变化会让维护成本变高 |
| Q1 | C | checker 根据 repo root 推导 runtime receipt 目录，再用 glob 找真实 receipt 并核对内容 | 保留现有 policy 简洁性，同时补上真实证据强门 | 需要给当前 child 设计 pre-receipt 例外避免 closeout 自锁 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---|---|---|
| Q1 | C | 能最小侵入地补强证据深度，并保持父任务账本渐进可维护 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|---|---|---|
| `references/parent-receipt-aggregation-policy.json` | 修改 | 新增 `receipt_correspondence` 策略，并把 P3-2 纳入 completed children；父任务仍 incomplete |
| `compass/tools/redcap-parent-receipt-aggregation-check.py` | 修改 | 根据 repo hash 定位 runtime receipt 目录，核对 receipt 内容对应关系 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 补 missing receipt、wrong report path、current child pre-receipt 例外等 targeted acceptance |
| `references/redcap-parent-task-ledger.md` | 修改 | 更新 P3-2 状态与父任务不可声明边界 |
| `references/execution-guarantees.json` | 修改 | 把父任务聚合保障描述从元数据校验升级为 receipt 内容对应强门 |
| `references/file-lookup-dictionary.md` / `references/file-lookup-dictionary-policy.json` | 修改 | 更新文件索引中的父任务聚合 checker 含义 |
| `compass/knowledge/lessons.md` | 修改 | 沉淀“receipt_glob 不是证据，receipt 内容对应才是证据”的经验 |

### 3.2 技术实现要点

- checker 用 repo root 的 md5 hash 推导 `/tmp/redcap/project/<hash>/governance/closeout-runtime/receipts`，与 closeout runtime 的项目隔离口径一致。
- 每个 completed child 至少要有一个匹配 receipt 通过内容核对：`task_id`、`confirmed_hash`、`repo_path`、`status=completed`、`promise_pending=0`、`acceptance_status`、`report_path` 和 `current_head` 都必须对得上。
- 当前正在执行的 P3-2 在 closeout 前没有本轮 receipt，因此只允许 `.dev-task.md` 同时满足 `parent_child_id=P3-2` 与同一 `task_report` 时走 pre-receipt 例外；这不是历史 child 的豁免。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|---|---|---|
| receipt_glob | `parent-receipt-aggregation-policy.json` | 用来寻找某个 child 的 receipt 文件名模式；它本身不是完成证据 |
| runtime receipt | `/tmp/redcap/project/<hash>/governance/closeout-runtime/receipts/*.json` | closeout runtime 生成的机器凭证，记录任务身份、完成状态、承诺账本、验收状态和 git head |
| pre-receipt 例外 | `.dev-task.md` + checker | 当前任务在 closeout 之前的短暂自锁豁免，只能用于当前被任务卡锚定的 child |
| confirmed_hash / repo_path | runtime receipt 字段 | `confirmed_hash` 证明 receipt 绑定了任务卡确认需求摘要，`repo_path` 证明 receipt 绑定当前 repo；两者都不是索引字段，而是内容对应证据 |

### 3.3 关联变更

父任务账本、执行保障登记、文件查找字典和 lessons 会同步更新，避免用户或后续 Agent 仍以为父任务聚合只验证 receipt_glob 形态。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|---|---|---|---|
| 1 | P3-1 是否启动 | P3-1 是检索/RAG 阈值研究，当前仍建议等共享知识库真实规模上来后再做 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|---|---|---|
| PM Gate | `bash compass/tools/redcap-pm-gate-check.sh strict codex .dev-task.md` | 通过 |
| 原始意图覆盖 | `bash compass/tools/redcap-intent-coverage-check.sh .dev-task.md` | 通过 |
| 中插需求检查 | `bash compass/tools/redcap-change-intake-check.sh .dev-task.md` | 通过 |
| Python 编译 | `python3 -m py_compile compass/tools/redcap-parent-receipt-aggregation-check.py` | 通过 |
| parent receipt aggregation | `bash compass/tools/redcap-parent-receipt-aggregation-check.sh` | 通过，输出 `receipt_correspondence=verified current_pre_receipt=1` |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh parent-receipt-aggregation-check` | 通过 |
| spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| diagnose | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 通过 |
| Prism review | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过，Kimi + Claude Code 双路 responded，blockers=0 |
| full acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh all` | 提交后重跑；提交前尝试命中 dirty working tree 下 stop-review fixture 的已知误伤，不作为功能失败结论 |

### 5.1.1 执行中发现并修复的问题

| 问题 | 根因 | 处理 |
|---|---|---|
| 新增 task report / lesson 后 `legacy-asset-migration-dry-run` 计数失真 | 历史资产 dry-run manifest 会核对 `task-reports` 和 `knowledge` 当前物理计数 | 同步更新 `references/legacy-asset-migration-dry-run.json` 的 task-reports 与 knowledge-lessons 计数 |
| 新增 Prism run 后 `prism-runs` 计数与 acceptance residue 失真 | 本轮真实 Prism run 让 formal-run +1；一次提交前 full acceptance 尝试留下 2 个 purgeable acceptance fixture | 执行 `prism-runs-lifecycle.sh prune-acceptance --apply` 清理 fixture，并把 `prism-runs.current_count` 更新为 33 |
| Prism 复评建议继续核对 repo_path / confirmed_hash | 第一版已核对 task_id/report/status/promise/acceptance/head，但 repo 绑定还可加强 | checker 新增 `confirmed_hash` 64 位 hex 与 `repo_path` 当前 repo 校验，acceptance 新增 task_id mismatch 失败用例 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- 无。本轮应由自动化检查、Prism review 和 closeout receipt 收口。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|---|---|
| 执行承诺账本 | 待 closeout 核对 |
| 棱镜验收 | 已通过 |
| closeout summary | 待生成 |
| closeout receipt | 待生成 |
| rescue audit（如有） | 待生成 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|---|---|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，Kimi + Claude Code Prism acceptance pass |
| 已正式完成 | 否；receipt 是唯一正式完工凭证 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|---|---|---|
| P3-1 GraphRAG / 向量检索阈值研究 | 当前共享知识库规模尚不足以证明需要重型 RAG/GraphRAG | P3 |
| 历史资产真实迁移 apply | P1-2 只完成 dry-run，真实 move/delete 需要单独任务和风险窗口 | P1 |

### 6.2 触发的新问题

暂无。

### 6.3 推荐的下一步行动

1. 本轮收口后继续保持父任务 incomplete，只保留 P3-1 deferred。
2. 当 `redcap-arsenal` 开始积累实质知识条目后，再启动 P3-1。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|---|---|---|
| L-pending | receipt_glob 不是证据 | 父任务聚合必须打开真实 receipt 并核对内容对应关系，不能把文件名模式当成完成凭证 |

### 7.2 流程改进建议

父任务聚合类机制以后应默认区分“索引字段”和“证据字段”：索引字段只能帮助定位证据，不能替代证据本身。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|---|---|---|---|
| receipt 内容对应强门 | P3-2 父任务证据深度治理 | no-promote：直接晋升为 policy/checker/acceptance | `references/parent-receipt-aggregation-policy.json`、`redcap-parent-receipt-aggregation-check.py` |

---

## 八、附录

### 附录 A：Commits

```
待提交
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|---|---|---|---|
| test | P3-2 receipt correspondence review | Kimi 初评无 blocker，并指出低风险字段错配覆盖缺口 | `prism/runs/20260428-runtime-receipt-evidence-correspondence-hardening/collect/reviewer/raw.txt` |
| test | P3-2 receipt correspondence review | Claude Code 初评无 blocker，并建议补 repo_path / confirmed_hash | `prism/runs/20260428-runtime-receipt-evidence-correspondence-hardening/collect/challenger/raw.txt` |
| test-delta | repo_path / confirmed_hash / task_id mismatch delta | Kimi + Claude Code 复评无 blocker，接受旧 receipt 严格失效属于 design intent | `prism/runs/20260428-runtime-receipt-evidence-correspondence-hardening/session-registry.yaml` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- 父任务账本：`references/redcap-parent-task-ledger.md`
- 父任务聚合策略：`references/parent-receipt-aggregation-policy.json`
