# RedCap 残留待完善项最终解决方案书

> 历史方案状态：其中关于 Kimi 实时调用、双提供方配额和分歧合并的方案已被
> 2026-07-18 的 Claude Code-only 权威策略取代，只用于追溯旧问题，不再作为
> 当前实施依据。当前策略见 `assets/contracts/prism-provider-policy.json`。

> 本文件只编写方案，不执行开发实现。
> 本文件完成只表示“解决方案已经被汇总、评审并形成后续实施依据”，不表示任何 RSP 问题已经被实现解决。
> 本文件不能作为 RedCap 完整复活终局完成证明；它只定义后续如何正面解决尚未完全成熟、仍需长期验证或仍有残余风险的问题。

## 1. 范围与判定口径

### 1.1 本轮目标

本轮目标是把当前尚未解决、残留 todo、有待完善的问题汇总成一份可执行方案书，并逐项给出最终解决方案。每个方案必须满足四个保证项：

1. 不引入新问题。
2. 不采用降级、绕过、放宽标准等有损方案。
3. 问题最终要被真实解决，不能只留下说明、记录或阶段性状态。
4. 必须经过 Prism（棱镜，异构 AI 评审助手）深度评审，并在 Cap 与 Prism 达成一致后才可作为后续实施依据。

### 1.2 当前事实边界

当前已有证据显示：

- `assets/contracts/open-loop-closure-queue.json` 的 P0/P1 开放队列已进入 `verified`。
- `runtime/bin/redcap revival-followthrough open-loop-check` 当前通过，开放 P0/P1 数量为 0。
- `runtime/bin/redcap complete-revival-check` 当前通过。
- 最新样本 E2E（端到端验收）已覆盖 9 个开放项。

但这些事实不等于以下声明：

- 不等于 RedCap 在所有真实项目中永久稳定。
- 不等于跨机器、跨模型版本、跨宿主 Hook（钩子，宿主自动触发脚本）环境已经全部验证。
- 不等于 Loom（角色化工程工作流）在长期真实开发中不会发生角色漂移。
- 不等于自我净化、知识召回、缓存治理、Stop（停止前检查钩子）误伤治理已经达到长期零缺陷。

因此，本方案书把“已验收项”视为阶段基线，把“残留待完善项”定义为成熟度、长期运行和跨场景可靠性问题。

### 1.3 方案书完成边界

本文件自身必须遵守 RSP-12：文档不能替代实现。因此本文件的完成口径只有一个：

- 可以声明：残留问题的最终解决方案书已完成、已评审、已形成后续实施依据。
- 不可以声明：这些残留问题已经解决。
- 不可以声明：RedCap 已经完整复活、可发布、可投入生产。
- 不可以用本文件关闭任何运行时问题、开放队列、终局目标或 E2E（端到端验收）失败项。

后续每个 RSP 条目只有在对应实现、正向验收、负向探针和证据包全部完成后，才能按该条目的实际范围关闭。

## 2. 残留问题总表

| 编号 | 问题 | 当前阶段 | 最终解决方向 |
|---|---|---|---|
| RSP-00 | 全方案不变量：完成口径与文档替代实现防线 | 前置约束 | 所有后续条目必须证明不会制造完成口径污染，也不能把方案书当实现 |
| RSP-01 | Stop 建议型检查仍可能误伤或影响回答主轴 | 阶段缓解 | 建立非侵入、可仲裁、可回放的收口建议治理 |
| RSP-02 | Hook 语义判断仍有硬规则残留 | 阶段缓解 | 形成脚本裁决 + 语义评审 + 可解释协议的统一链路 |
| RSP-03 | Kimi 调用路径、超时和文件访问仍需长期稳定性证明 | 阶段修复 | 建立 provider 健康巡检、调用矩阵和异常分类 |
| RSP-04 | Prism 通信在大任务下仍需压测上下文边界 | 阶段可用 | 固化“文件承载细节、摘要承载结论”的协议与测试 |
| RSP-05 | Loom 角色链在更多真实项目中的质量仍需验证 | 阶段验收 | 用多项目、多角色、失败回流样本验证角色协作质量 |
| RSP-06 | Loom 会话接续和独立 AI 承载仍需长期验证 | 阶段验收 | 建立 session_id 丢失、复用、漂移的强失败机制 |
| RSP-07 | 自我净化自然触发率仍需证明 | 阶段验收 | 将任务前检索、任务后候选、晋升/不晋升决策纳入常规闭环 |
| RSP-08 | 知识召回影响决策仍需更多证据 | 阶段验收 | 要求计划、实现、验收显式说明知识如何改变决策 |
| RSP-09 | 项目级 `.redcap/` 安装需要跨项目、跨路径验证 | 阶段自检 | 建立可迁移安装矩阵和项目级隔离验收 |
| RSP-10 | 长任务循环机制存在死循环和过度触发风险 | 阶段机制 | 明确进入条件、停止条件、同根因失败升级规则 |
| RSP-11 | 完成口径仍可能被阶段成果污染 | 阶段约束 | 完成声明必须绑定任务事实、终局目标和证据范围 |
| RSP-12 | 文档、账本、报告替代实际完成的旧疾可能复发 | 阶段约束 | 每个完成声明必须指向真实行为变化和运行检查 |
| RSP-13 | E2E 缓存仍有历史 unknown 目录保守保留 | 阶段治理 | 为 unknown 目录建立分类、老化、人工保留和安全删除路径 |
| RSP-14 | E2E 报告仍需提升可读性和验收价值 | 阶段改善 | 输出按能力项拆分的通过/失败/未触发矩阵 |
| RSP-15 | Forge 和 redcap-arsenal 公共/私有边界需长期守住 | 阶段可用 | 公共晋升必须脱敏、去重、索引、追加，不写私有人格 |
| RSP-16 | Cap 复活手册需要迁移和多用户路径验证 | 阶段纳入 | 用 `$CAP_HOME` 和路径无关引用完成迁移验收 |
| RSP-17 | 旧 RedCap 15 项优秀设计“覆盖”不等于“成熟” | 阶段覆盖 | 对每项建立运行成熟度矩阵，而不是只看合同命中 |
| RSP-18 | 当前完整验收仍是自举场景，缺少外部长期生产样本 | 阶段通过 | 用真实外部项目批次验证 RedCap 是“渔”而非“鱼” |
| RSP-19 | `runtime/bin/redcap` 命令面可能随新增能力漂移 | 待完善 | 建立命令面兼容、帮助文本、参数别名和回归检查 |
| RSP-20 | Codex CLI（命令行工具）插件/配置噪声可能污染外部 E2E | 待完善 | 建立隔离 Codex HOME、插件禁用和跨机器配置审计 |
| RSP-21 | advisory-stop degraded 状态缺少健康巡检升级路径 | 待完善 | 建立 degraded 检测、上报、阻断边界和恢复验收 |
| RSP-22 | E2E 报告与验收设计合同之间映射不够显式 | 待完善 | 建立报告字段到验收条款的一一映射 |
| RSP-23 | Prism 多评审方一致性与差异处理仍需固化 | 待完善 | 建立 Kimi、Claude Code 差异合并、反驳和仲裁协议 |
| RSP-24 | Cap 运行时稳定性缺少独立健康维度 | 待完善 | 建立运行入口、异常恢复和关键命令稳定性巡检 |
| RSP-25 | Hook 误伤率缺少持续度量 | 待完善 | 建立误伤样本、误杀率、漏检率和趋势阈值 |
| RSP-26 | 知识正确性可能随时间退化 | 待完善 | 建立知识陈旧、错误召回和冲突知识处理机制 |
| RSP-27 | 配置契约版本兼容性需要迁移策略 | 待完善 | 建立配置版本、向前兼容、迁移和拒绝旧配置规则 |

## 2.1 全方案不变量

RSP-00 是所有后续条目的前置不变量，不作为普通排期项处理。

1. 每个条目实施时必须证明真实行为改变；方案、文档、账本、评审回执不能单独关闭问题。
2. 每个条目必须有至少一个正向验收和一个负向探针；如果某条确实无法设置负向探针，必须写明原因并由 Prism 复核。
3. 每个完成声明必须写明完成范围：方案完成、代码实现、样本通过、外部项目通过、长期成熟，不能混用。
4. 每个条目必须说明如何避免引入新问题；如果新问题风险不可消除，必须进入新队列而不是隐藏在“注意事项”里。
5. 涉及不可逆删除、公开发布、私人人格、公共知识晋升和跨机器迁移的条目，必须保留 Norven 人工决策点。

RSP-00 的执行机制如下：

| 机制 | 规则 |
|---|---|
| 检查者 | Cap 先做自检，Prism 对中高风险条目复核，Norven 只处理价值判断或不可逆决策 |
| 检查时机 | 每个 RSP 进入实施前、声明完成前、发现新问题入队前都检查一次 |
| 检查材料 | 任务说明、实现差异、正向验收、负向探针、证据包、完成声明草稿 |
| 违反后果 | 不能关闭该 RSP；若已经写出完成声明，必须收窄为阶段状态并追加修复任务 |
| 防绕过规则 | 不允许把“不变量不适用”写成普通说明；若确实不适用，必须写明理由并重新触发 Prism 评审 |

RSP-00 的最小机器防线：

- 后续实施 RSP-00 时，必须新增或复用一个本地可运行检查：`runtime/bin/redcap rsp-contract check --plan assets/docs/residual-todo-final-solution-plan.md`。
- 该检查至少验证三件事：每个 RSP 有正向验收、负向探针和完成证据路径；完成声明引用了对应证据路径；新增问题已入队或归入已有 RSP。
- 本地开发阶段：每个 RSP 声明完成前必须运行该检查。
- CI（持续集成，自动化检查流水线）阶段：仓库具备 CI 后，该检查必须加入默认验证；在 CI 未建立前，不能把“CI 已覆盖”作为完成证据。
- 若该检查失败，对应 RSP 只能处于 `draft`、`blocked` 或 `partially_verified`，不能进入 `verified`。
- `rsp-contract check` 的接口和输出格式是待验证的设计假设，不是当前已存在能力。后续实施阶段必须先做 RSP-00 spike（最小可行验证）：实现占位命令、跑通参数解析、输出固定结构的失败结果，再把它升级为后续 RSP 完成门槛。
- RSP-00、RSP-11、RSP-12 是实施阶段前三条，不允许跳过它们先关闭其他 RSP。

`rsp-contract check` 的最小接口规格：

```text
runtime/bin/redcap rsp-contract check \
  --plan assets/docs/residual-todo-final-solution-plan.md \
  --rsp RSP-03 \
  --claim-file path/to/completion-claim.json \
  --evidence-file .redcap/evidence/rsp/rsp-03-provider-health.json
```

最小输出 JSON（结构化数据）：

```json
{
  "ok": false,
  "rsp": "RSP-03",
  "plan_path": "assets/docs/residual-todo-final-solution-plan.md",
  "claim_file": "path/to/completion-claim.json",
  "evidence_file": ".redcap/evidence/rsp/rsp-03-provider-health.json",
  "checks": {
    "has_positive_acceptance": true,
    "has_negative_probe": true,
    "claim_references_evidence": false,
    "new_issue_is_queued": true
  },
  "failures": [
    "completion claim does not reference required evidence file"
  ]
}
```

最小通过条件：

- `ok` 必须为 true。
- `failures` 必须为空数组。
- `claim_references_evidence` 必须为 true。
- 若存在新问题，必须满足 `new_issue_is_queued=true`。
- 若 `--rsp` 指向未知 RSP，必须失败，不能静默通过。

最小检查语义：

| 检查项 | 通过条件 | 失败条件 |
|---|---|---|
| `has_positive_acceptance` | 方案书对应 RSP 存在正向验收，且 `evidence_file.acceptance.positive.status=pass` | 缺少正向验收，或证据文件没有 positive pass |
| `has_negative_probe` | 方案书对应 RSP 存在负向探针，且 `evidence_file.acceptance.negative.status=pass` | 缺少负向探针，或负向探针未执行/未通过 |
| `claim_references_evidence` | `claim_file.evidence_file` 与命令传入的 `--evidence-file` 一致 | 完成声明未引用证据，或引用路径不一致 |
| `new_issue_is_queued` | 若 `claim_file.new_issues` 非空，每个新问题都包含 `queue_target`，且指向已有 RSP 或 `plan-change-control` | 新问题只写在说明里，没有进入队列或变更控制 |

`claim_file` 最小 JSON schema（结构约束）：

```json
{
  "rsp": "RSP-03",
  "claim_scope": "current-machine-current-version",
  "completion_level": "sample_passed",
  "evidence_file": ".redcap/evidence/rsp/rsp-03-provider-health.json",
  "new_issues": []
}
```

`claim_file` 必填字段：`rsp`、`claim_scope`、`completion_level`、`evidence_file`、`new_issues`。

`evidence_file` 最小 JSON schema：

```json
{
  "rsp": "RSP-03",
  "acceptance": {
    "positive": {"status": "pass", "checks": []},
    "negative": {"status": "pass", "checks": []}
  },
  "changed_reality": [],
  "artifacts": []
}
```

`evidence_file` 必填字段：`rsp`、`acceptance.positive.status`、`acceptance.negative.status`、`changed_reality`、`artifacts`。

### 2.1.1 计划变更控制

本方案书后续若发生以下任一变更，必须重新触发 Prism 评审，不能以“文档小修”“措辞优化”绕过：

- 新增、删除、合并或拆分 RSP 条目。
- 修改任何 RSP 的完成口径、正向验收、负向探针、证据路径或实施顺序。
- 修改 Norven 人工决策点、超时默认处置或私有/公共边界。
- 修改 RSP-00、RSP-11、RSP-12 的不变量。
- 实施中发现某个验收标准不可行，需要换成新标准。

变更流程：

1. 先写明变更原因、影响范围和是否降低标准。
2. 更新方案书和对应任务队列。
3. 重新提交 Prism 评审。
4. 只有 Prism concerns 被解决，或 Cap 给出有证据的仲裁理由，变更才可生效。

任何未走上述流程的方案变更，不能作为后续实施依据。

### 2.1.2 新问题入队规则

后续实施或测试中发现新的残留问题时，必须按以下规则处理：

1. 先判断它是已有 RSP 的子问题，还是需要新增 RSP。
2. 若是子问题，必须补充到对应 RSP 的验收、负向探针或证据路径中。
3. 若是新增 RSP，必须写明根因、最终方案、不降级保证、正向验收、负向探针、证据路径和实施顺序。
4. 若新问题会改变既有 RSP 的优先级或验收标准，必须触发计划变更控制。
5. 新问题不得只写进会议记录、复盘报告或“注意事项”；未入队的问题不能被视为已处理。

## 2.2 可执行验收矩阵

| 编号 | 最低正向验收 | 最低负向探针 | 证据位置 |
|---|---|---|---|
| RSP-01 | `runtime/bin/redcap advisory-stop self-check` | 原问题主轴偏移样本必须失败 | check-receipts 下的 advisory-stop 回执 |
| RSP-02 | `runtime/bin/redcap gate ... --semantic-policy auto-on-ambiguous` | 纯问题、反问、无授权执行样本不得通过 implementation | host-hooks 事件与语义裁决记录 |
| RSP-03 | Kimi 基础调用、续接、限定文件读取通过 | 路径错误、权限阻塞、超时必须分类失败 | Prism raw-meta 与 provider 健康报告 |
| RSP-04 | Prism 请求只把摘要进入 Cap 上下文 | raw 大输出不得进入最终回答主上下文 | Prism review JSON 与 brief |
| RSP-05 | 外部项目角色链完整通过 | 单 AI 伪装多角色必须失败 | 外部项目 `.redcap/evidence/e2e/loom-role-session-manifest.json` |
| RSP-06 | 同角色多轮续接 session_id 稳定 | session_id 缺失、重复、漂移必须失败 | `.redcap/state/loom/session-manifest.json` |
| RSP-07 | 真实任务后生成候选或充分 no-candidate 理由 | 私人人格候选进入公共仓库必须失败 | self-purification 证据目录 |
| RSP-08 | 命中知识被计划/实现/验收引用 | 无关命中或 0 命中无理由必须失败 | knowledge-retrieval-evidence.json |
| RSP-09 | 外部项目安装、运行、卸载、重装通过 | 运行时污染 RedCap 源仓库必须失败 | 外部项目 `.redcap/` 与源仓库 `git status` |
| RSP-10 | 长任务进入、推进、停止条件均可触发 | 同根因三轮失败继续重跑必须失败 | long-task 运行证据目录 |
| RSP-11 | 阶段完成不会通过终局完成声明 | 文档完成冒充终局完成必须失败 | `runtime/bin/redcap terminal-goal check` |
| RSP-12 | 完成项指向真实行为变化 | 只有文档/账本/报告时不得关闭运行问题 | 生命周期包和 final-claim 检查 |
| RSP-13 | unknown 目录分类、dry-run、执行清单完整 | 未分类 unknown 静默删除必须失败 | e2e-prune 回执 |
| RSP-14 | E2E 报告按能力项输出 | 只报告页面可访问不得通过 | 外部项目 open-loop-e2e-item-results.json |
| RSP-15 | 公共晋升脱敏、去重、追加写入 | 私人人格、凭据、未脱敏路径进入公共库必须失败 | `assets/knowledge/arsenal/index.json` 与 Forge 检查 |
| RSP-16 | `$CAP_HOME` 与 `~/.cap` 两种路径可加载 | 公共仓库读取私人人格正文必须失败 | `runtime/bin/redcap soul-load check` |
| RSP-17 | 15 项设计成熟度矩阵生成 | 合同覆盖冒充长期成熟必须失败 | `assets/contracts/full-revival-amendment.json` 派生矩阵 |
| RSP-18 | 三类真实外部项目均产出 RedCap 能力改进证据 | 只交付目标应用不沉淀 RedCap 能力必须失败 | redcap-e2e-runs 下的项目证据包 |
| RSP-19 | `runtime/bin/redcap --help` 与子命令回归通过 | 删除旧参数或破坏别名必须失败 | cli-surface 回执 |
| RSP-20 | 隔离 Codex HOME 和禁用插件样本通过 | 宿主插件噪声污染 E2E 必须失败 | carrier/preflight 证据 |
| RSP-21 | degraded 状态触发健康告警和升级 | degraded 被当成正常通过必须失败 | advisory-stop-health 回执 |
| RSP-22 | E2E 报告字段映射验收合同 | 报告字段缺少合同映射必须失败 | complete-revival-e2e 合同对照报告 |
| RSP-23 | Kimi 与 Claude Code 分歧能合并、反驳或仲裁 | 单方 pass 覆盖另一方 block 必须失败 | Prism merge 与 resolution-check 记录 |
| RSP-24 | Cap 关键运行入口健康巡检通过 | 关键入口失败仍允许继续必须失败 | runtime-health 回执 |
| RSP-25 | Hook 误伤率和漏检率有趋势记录 | 误伤回放失败仍显示健康必须失败 | hook-quality-metrics 报告 |
| RSP-26 | 陈旧或冲突知识被标记、降权或阻断 | 错误知识命中无解释影响决策必须失败 | knowledge-quality 报告 |
| RSP-27 | 配置版本迁移和拒绝旧配置均可验证 | 静默接受未知配置版本必须失败 | config-contract-compat 回执 |

### 2.2.1 完成声明证据路径

每个 RSP 的未来完成声明必须至少引用下表中的证据文件或同名证据包；只有方案文字、摘要或 digest（摘要包）不能关闭对应 RSP。

| 编号 | 完成声明必须引用的证据 |
|---|---|
| RSP-00 | `.redcap/evidence/rsp/rsp-00-invariant-check.json` |
| RSP-01 | `.redcap/evidence/rsp/rsp-01-advisory-stop-replay.json` |
| RSP-02 | `.redcap/evidence/rsp/rsp-02-intent-judge-matrix.json` |
| RSP-03 | `.redcap/evidence/rsp/rsp-03-provider-health.json` |
| RSP-04 | `.redcap/evidence/rsp/rsp-04-prism-context-boundary.json` |
| RSP-05 | `.redcap/evidence/rsp/rsp-05-loom-role-chain-e2e.json` |
| RSP-06 | `.redcap/evidence/rsp/rsp-06-loom-session-continuity.json` |
| RSP-07 | `.redcap/evidence/rsp/rsp-07-self-purification-loop.json` |
| RSP-08 | `.redcap/evidence/rsp/rsp-08-knowledge-impact-trace.json` |
| RSP-09 | `.redcap/evidence/rsp/rsp-09-project-install-matrix.json` |
| RSP-10 | `.redcap/evidence/rsp/rsp-10-long-task-loop-boundary.json` |
| RSP-11 | `.redcap/evidence/rsp/rsp-11-completion-scope-guard.json` |
| RSP-12 | `.redcap/evidence/rsp/rsp-12-reality-change-proof.json` |
| RSP-13 | `.redcap/evidence/rsp/rsp-13-e2e-cache-prune.json` |
| RSP-14 | `.redcap/evidence/rsp/rsp-14-e2e-human-report.json` |
| RSP-15 | `.redcap/evidence/rsp/rsp-15-forge-private-boundary.json` |
| RSP-16 | `.redcap/evidence/rsp/rsp-16-cap-revival-portability.json` |
| RSP-17 | `.redcap/evidence/rsp/rsp-17-design-maturity-matrix.json` |
| RSP-18 | `.redcap/evidence/rsp/rsp-18-fixture-external-project-samples.json` |
| RSP-19 | `.redcap/evidence/rsp/rsp-19-cli-surface-compat.json` |
| RSP-20 | `.redcap/evidence/rsp/rsp-20-codex-home-isolation.json` |
| RSP-21 | `.redcap/evidence/rsp/rsp-21-advisory-stop-health.json` |
| RSP-22 | `.redcap/evidence/rsp/rsp-22-e2e-contract-mapping.json` |
| RSP-23 | `.redcap/evidence/rsp/rsp-23-prism-provider-consensus.json` |
| RSP-24 | `.redcap/evidence/rsp/rsp-24-cap-runtime-health.json` |
| RSP-25 | `.redcap/evidence/rsp/rsp-25-hook-quality-metrics.json` |
| RSP-26 | `.redcap/evidence/rsp/rsp-26-knowledge-quality.json` |
| RSP-27 | `.redcap/evidence/rsp/rsp-27-config-contract-compat.json` |

### 2.2.2 完整证据闭环示例

以下示例只定义后续实施如何验收，不表示该问题现在已经解决。

以 RSP-03 为例，不能用“已优化 provider 调用”关闭问题。当前提供方策略已经冻结 Kimi 实时调度，正确关闭路径必须同时满足：

| 要素 | 必须内容 |
|---|---|
| 真实行为改变 | provider 调度器能区分基础调用、会话续接、限定文件读取、路径错误、权限阻塞、本地超时和远端慢响应 |
| 正向验收 | Claude Code 基础调用通过；同一会话续接通过；限定文件清单读取通过 |
| 负向探针 | 故意传入错误路径、无权限文件和超短超时，必须分别归类失败，不能统一写成 provider 超时 |
| 证据文件 | `.redcap/evidence/rsp/rsp-03-provider-health.json` |
| 完成声明允许范围 | 只能声明“RSP-03 Claude Code 调用稳定性已在当前机器和当前版本验证通过”，不能声明 Prism 长期稳定或跨机器长期成熟 |
| 不允许的关闭方式 | 只有文档说明、只有一次成功问答、只有 raw 输出、只有人工口头判断 |

其他 RSP 必须按同样结构提供证据，否则不能关闭。

### 2.2.3 当前状态基线

本基线用于后续实施排序和状态复核，不替代任何 RSP 的验收。状态判断必须同时看三类材料：

1. 方案书中的正向验收、负向探针和证据路径。
2. `.redcap/evidence/rsp/` 下对应 RSP 的证据文件与完成声明。
3. 生命周期、门禁、Prism（棱镜，异构 AI 评审助手）评审或仲裁记录是否把完成范围限定清楚。

不能只因为存在脚本、文档、清单、报告、证据目录或 claim（完成声明）文件，就判定问题已经解决。若证据只覆盖当前机器、当前版本、当前样本，状态必须保持为“当前范围闭环”，不能扩写成“长期成熟”或“完整复活”。

截至 2026-06-21，本方案书对应的阶段状态如下：

| 状态 | RSP | 判定口径 |
|---|---|---|
| 当前范围闭环 | RSP-00、RSP-01、RSP-02、RSP-03、RSP-04、RSP-11、RSP-12、RSP-21、RSP-25 | 已存在对应证据文件和完成声明；只能按各自 claim_scope（完成范围）理解，不代表 RedCap 完整复活 |
| 正在进入下一优先级 | RSP-20、RSP-23、RSP-24、RSP-27 | 属于 Prism 可用性、provider（外部模型提供方）稳定性、Codex CLI（命令行工具）隔离、运行健康和配置兼容的第二批核心前置项 |
| 尚未闭环 | RSP-05、RSP-06、RSP-07、RSP-08、RSP-09、RSP-10、RSP-13、RSP-14、RSP-15、RSP-16、RSP-17、RSP-18、RSP-19、RSP-22、RSP-26 | 仍缺对应证据文件、完成声明、完整验收或长期样本；不能以设计存在、方案存在或局部实现存在关闭 |

状态更新规则：

- 新增证据后，必须先更新对应 `rsp-XX-claim.json` 和证据文件，再通过 `rsp-contract check` 或同等级检查。
- 若某条 RSP 只完成了当前机器或当前样本验证，必须写入 `claim_scope`，不得把范围扩大到跨机器、跨版本、长期生产或完整复活。
- 若测试中发现新问题，必须归入已有 RSP 或通过计划变更控制新增 RSP，不能只写进复盘或最终回复。
- 若 RSP 完成声明与当前基线冲突，以更严格的未闭环状态为准，直到补齐证据并通过检查。

### 2.2.4 未闭环项执行映射

本映射用于避免“知道问题存在，但后续重新推导实现入口”的空转。表中的“拟新增”表示当前方案确定的未来落点，不表示该文件或命令当前已经存在；后续实施该 RSP 时，必须先创建或接入对应落点，再生成证据。

| RSP | 契约文件 | 检查入口 | 运行时代码路径 | 说明 |
|---|---|---|---|---|
| RSP-05 | 拟新增 `assets/contracts/loom-role-chain-e2e.json` | 拟新增 `runtime/bin/redcap loom role-chain-check` | `runtime/core/loom_runtime.py`、外部项目 `.redcap/state/loom/` | 验证真实项目中角色链是否按产品、架构、开发、测试流转 |
| RSP-06 | 拟新增 `assets/contracts/loom-session-continuity.json` | 拟新增 `runtime/bin/redcap loom session-check` | `runtime/core/loom_runtime.py`、`runtime/core/provider_health.py` | 验证独立 AI 角色的 session_id 稳定、丢失报警和漂移失败 |
| RSP-07 | 拟新增 `assets/contracts/self-purification-loop.json` | 复用并扩展 `runtime/bin/redcap self-purification ...` | `runtime/core/self_purification.py` | 把任务后候选、评审、晋升或 no_promote 纳入常规闭环 |
| RSP-08 | 拟新增 `assets/contracts/knowledge-impact-trace.json` | 拟新增 `runtime/bin/redcap knowledge impact-check` | `runtime/core/knowledge_gateway.py`、`assets/knowledge/index.json` | 证明知识召回如何改变计划、实现或验收 |
| RSP-09 | 拟新增 `assets/contracts/project-install-matrix.json` | 拟新增 `runtime/bin/redcap install matrix-check` | 项目级 `.redcap/` 安装脚本、`runtime/core/project_runtime.py` | 验证外部项目安装、重装、卸载和源仓库隔离 |
| RSP-10 | 拟新增 `assets/contracts/long-task-loop-boundary.json` | 拟新增 `runtime/bin/redcap long-task boundary-check` | `runtime/core/revival_followthrough.py`、Loom 回流调度入口 | 明确长任务进入、推进、停止、同根因失败升级 |
| RSP-13 | 拟新增 `assets/contracts/e2e-cache-prune.json` | 拟新增 `runtime/bin/redcap e2e-cache prune-check` | `runtime/core/complete_revival_e2e.py` | 控制 E2E 缓存膨胀，unknown 目录只允许分类和 dry-run，删除需人工边界 |
| RSP-14 | 拟新增 `assets/contracts/e2e-human-report.json` | 拟新增 `runtime/bin/redcap e2e report-check` | `runtime/core/complete_revival_e2e.py` | 让报告按能力项输出通过、失败、未触发和证据链接 |
| RSP-15 | 拟新增 `assets/contracts/forge-private-boundary.json` | 拟新增 `runtime/bin/redcap forge boundary-check` | Forge/redcap-arsenal 晋升入口、`assets/knowledge/` | 防止私人人格、凭据、未脱敏路径进入公共能力库 |
| RSP-16 | 拟新增 `assets/contracts/cap-revival-portability.json` | 拟新增 `runtime/bin/redcap soul-load check` | Cap 加载入口、`$CAP_HOME`、`~/.cap` | 验证 Cap 复活手册路径无关、私有正文不进入公共仓库 |
| RSP-17 | 拟新增 `assets/contracts/design-maturity-matrix.json` | 拟新增 `runtime/bin/redcap design-maturity check` | `assets/contracts/full-revival-amendment.json` 派生成熟度矩阵 | 把旧 RedCap 15 项优秀设计从“覆盖”拆到“成熟度” |
| RSP-18 | 拟新增 `assets/contracts/fixture-external-project-samples.json` | 拟新增 `runtime/bin/redcap external-sample check` | fixture 外部项目运行器、`.redcap/evidence/e2e/` | 先用 fixture 样本阻断“只交付目标应用”的错误验收；真实长期生产项目批次仍不得被本项冒充 |
| RSP-19 | 拟新增 `assets/contracts/cli-surface-compat.json` | 拟新增 `runtime/bin/redcap cli-surface check` | `runtime/bin/redcap`、各子命令帮助文本 | 防止命令面随新增能力漂移、破坏别名或帮助文本 |
| RSP-20 | 拟新增 `assets/contracts/codex-cli-isolation.json` | 拟新增或扩展 `runtime/bin/redcap complete-revival-e2e carrier-probe` | `runtime/core/complete_revival_e2e.py` | 隔离 Codex CLI HOME、记录插件/配置摘要，防止宿主噪声污染 E2E |
| RSP-22 | 拟新增 `assets/contracts/e2e-contract-mapping.json` | 拟新增 `runtime/bin/redcap e2e contract-map-check` | `runtime/core/complete_revival_e2e.py` | 把 E2E 报告字段逐项映射到验收合同 |
| RSP-23 | 拟新增 `assets/contracts/prism-provider-consensus.json` | 扩展 `runtime/prism/bin/prism merge` 与 `resolution-check` | `runtime/prism/bin/prism`、`runtime/prism/bin/prism-dispatch` | 固化 Kimi 与 Claude Code 分歧合并、反驳、仲裁和 schema 归一化 |
| RSP-24 | 拟新增 `assets/contracts/cap-runtime-health.json` | 拟新增 `runtime/bin/redcap runtime-health check` | `runtime/bin/redcap`、关键 runtime/core 入口 | 建立 Cap 运行入口、异常恢复和关键命令稳定性巡检 |
| RSP-26 | 拟新增 `assets/contracts/knowledge-quality.json` | 拟新增 `runtime/bin/redcap knowledge quality-check` | `runtime/core/knowledge_gateway.py`、`assets/knowledge/entries/` | 标记陈旧、错误、冲突知识，并阻止错误召回无解释影响决策 |
| RSP-27 | 拟新增 `assets/contracts/config-contract-compat.json` | 拟新增 `runtime/bin/redcap config compat-check` | 配置加载入口、项目级 `.redcap/config*` | 验证配置版本迁移、向前兼容和未知版本拒绝 |

执行约束：

- 若某个拟新增落点在实施时被证明不适合，必须走计划变更控制，说明替代落点为何更直接、更可验证，而不是默默换路径。
- 后续每个 RSP 的证据文件必须引用本表中至少一个契约、检查入口或运行时代码路径；否则该 RSP 只能保持 `planned` 或 `blocked`。
- 若某个检查入口只能依赖 E2E（端到端验收）观察，必须补充一个更小的静态或单元级负向探针，避免所有问题都堆到重型 E2E 才暴露。
- 本节通过 Prism 评审后，后续不得继续以“再补一轮方案书”作为主要推进方式；除非发现无法归入 RSP-00 至 RSP-27 的新问题，否则下一步必须至少创建一个契约文件、接入一个检查入口或修复一个运行时代码路径。

## 2.3 Norven 人工决策点

以下条目不能由 Cap 自动替 Norven 做价值判断：

- RSP-13：unknown 历史目录是否允许删除、保留多久、哪些目录标记为永久排障样本。
- RSP-15：哪些经验可以进入公共 Forge 或 redcap-arsenal，哪些必须 keep_private。
- RSP-16：Cap 私人人格材料是否迁移、复制或纳入 `$CAP_HOME` 版本控制。
- RSP-18：真实外部项目样本选择、是否对外发布、是否涉及真实用户或真实业务数据。

人工决策时间模型：

| 条目 | 需要 Norven 决策的问题 | 等待边界 | 超时默认处置 |
|---|---|---|---|
| RSP-13 | 删除或长期保留 unknown 历史目录 | 当前任务轮次内明确询问一次；无答复则不删除 | 只做分类和 dry-run，不执行删除；将删除动作标为 blocked |
| RSP-15 | 公共晋升边界 | 涉及公开写入前必须明确询问 | 默认 keep_private，不进入公共 Forge 或 redcap-arsenal |
| RSP-16 | 私人人格迁移或复制 | 涉及读取、复制、迁移私有正文前必须明确询问 | 只检查路径和哈希，不读取正文，不复制内容 |
| RSP-18 | 外部真实项目样本和真实数据使用 | 涉及真实业务、真实用户或外发前必须明确询问 | 使用合成样本或本地沙盒，不对外发布 |

超时默认处置只能保证安全，不能把对应条目标为已解决。若默认处置导致验收覆盖不足，该 RSP 必须保持 blocked 或 partially_verified。

## 3. 逐项最终解决方案

### RSP-01 Stop 建议型检查仍可能误伤或影响回答主轴

根因：Stop 设计初衷是收口评审，但如果建议文本成为新的回答主轴，就会偏离用户原问题。

最终方案：

- Stop 只输出结构化建议，不输出新任务口吻。
- Cap 必须先判断建议是否成立；误伤可记录并覆盖。
- 二次回答必须保留原用户问题为主轴，Stop 只能作为修正约束。
- 建立 Stop 误伤回放集，覆盖扫描结论误插入、终局目标误伤、中文术语过敏、动作证据误判四类样本。

“原用户问题主轴”的操作定义：

- 回答开头必须直接回应用户原问题，而不是先解释 Stop 或其他内部检查。
- 若用户问状态，就先给状态；若用户要求执行，就先说明执行动作和结果；若用户问原因，就先给原因。
- Stop 建议只允许改变错误表述、收窄完成口径或补充缺失证据，不允许把回答主题改成 Stop 本身。
- 负向样本：用户问“哪些任务没完成”，回答却主要解释“为什么 Stop 拦截我”，判定失败。

不降级保证：

- 不删除 Stop 的收口质量检查能力。
- 不把 Stop 从强检查降级为无记录提醒。
- 不允许 Stop 直接驱动任务改写。

验收证据：

- `advisory-stop` 正向样本：有问题时给出建议。
- `advisory-stop` 负向样本：误伤时不改变原问题主轴。
- 回放集显示同一误伤不再重复。

### RSP-02 Hook 语义判断仍有硬规则残留

根因：脚本硬规则无法枚举自然语言意图；纯大模型判断又缺少稳定、可审计协议。

最终方案：

- 使用三层链路：确定性规则先做低风险快速判定；疑难或高风险场景调用语义评审；最终由脚本按结构化结果裁决。
- 每次语义评审必须输出固定字段：任务类型、是否授权执行、是否需要工具动作、是否存在完成声明、是否疑似误伤。
- 对所有被调整的决策记录原始规则结果、语义结果和最终裁决。

不降级保证：

- 不关闭确定性安全规则。
- 不把所有判断无条件交给大模型。
- 不允许语义失败时静默放行高风险操作。

验收证据：

- 中英文、问题式授权、反问式授权、纯问题、命令式执行、完成声明六类样本通过。
- 语义服务超时时，高风险请求进入保守阻断或人工决策，不进入静默通过。

### RSP-03 Kimi 调用路径、超时和文件访问稳定性

根因：Kimi CLI（命令行工具）升级、路径变化、交互模式和文件访问策略都会影响 Prism 可用性。

最终方案：

- 建立 provider 健康巡检：版本、路径、基础问答、会话续接、文件读取、长任务超时、失败分类。
- 文件读取不禁用，但必须限定文件清单、总字节上限和任务目的。
- 超时后必须区分：本地进程超时、远端响应慢、权限阻塞、路径错误、会话恢复失败。

不降级保证：

- 不用“禁止 provider 读文件”规避超时。
- 不把 provider 超时简单标记为整体不可用。
- 不把所有内容塞进 stdout（标准输出，命令行返回文本）导致上下文膨胀。

验收证据：

- Claude Code 基础调用通过。
- Claude Code 同一会话续接通过。
- 限定文件清单读取通过。
- 超时分类报告能指出具体失败层。

### RSP-04 Prism 通信上下文边界

根因：Prism 需要看到足够上下文，但过多正文进入对话会打爆上下文。

最终方案：

- 细节落文件，stdout 只传摘要、路径、结论和必须响应项。
- Prism 请求必须带文件访问边界：允许路径、单文件大小、总大小、阅读目的。
- Provider 回答保存 raw、brief、structured review 三层；Cap 默认读 structured review 和 brief。

不降级保证：

- 不禁止 Prism 读取必要本地文件。
- 不把上下文控制变成信息不足。
- 不把 raw 输出直接灌入 Cap 上下文。

验收证据：

- 大文件审查任务中，Cap 最终上下文只消费摘要和结构化结论。
- Prism raw 文件仍可回放审计。

### RSP-05 Loom 角色链真实项目质量

根因：单次样本通过不能证明多项目、多类型需求下角色链都可靠。

最终方案：

- 建立三类外部项目验收：前端工具、后端服务、全栈应用。
- 每类项目都必须经过产品经理、架构师、开发者、测试者、评审者角色链。
- 每个角色只消费上游协议包，不读取全量上下文。

不降级保证：

- 不允许一个 AI 冒充多个角色。
- 不允许 Cap 直接替 Loom 角色开发目标项目。
- 不允许只用目标应用能打开证明 Loom 通过。

验收证据：

- 每个项目有角色 session_id、输入、输出、交付物、消费证据。
- 至少一次失败回流被目标角色消费并重新交付。

### RSP-06 Loom 会话接续和独立 AI 承载

根因：角色上下文丢失会让 Loom 退化成无状态填表。

最终方案：

- 每个角色绑定 project_id + task_id + role + session_id。
- session_id 缺失、重复、变化必须报警并阻断验收。
- 支持 Codex CLI、Kimi、Claude Code 三类承载方，但每类必须声明 Hook 可用性和能力边界。

不降级保证：

- 不允许新开会话冒充续接。
- 不允许无 session_id 的角色产物进入正式验收。
- 不因非 Codex 承载方缺 Hook 就假装 Hook 生效。

验收证据：

- 正向：同角色多轮会话保持同一 session_id。
- 负向：丢失、重复、漂移都会失败。

### RSP-07 自我净化自然触发

根因：机制存在不等于真实任务后自然触发。

最终方案：

- 所有中高风险 RedCap 自开发任务都必须执行任务前知识检索。
- 任务后必须执行候选抽取；没有候选时必须写明具体 no-candidate 理由。
- 候选必须进入 promote_public、keep_private、no_promote 或 defer_with_owner。

不降级保证：

- 不允许长期使用 no_candidate_reason 逃避沉淀。
- 不允许把候选文件存在当作沉淀完成。
- 不允许私人人格正文写入公共仓库。

验收证据：

- 真实修复任务后产出候选或有充分 no-candidate 理由。
- 至少一个 no_promote 和一个 keep_private 样本通过边界检查。

### RSP-08 知识召回影响决策

根因：检索命中不代表影响行动。

最终方案：

- 计划阶段必须列出命中知识和采用方式。
- 实现阶段必须说明哪些决策因知识命中而改变。
- 验收阶段必须检查“检索记录”和“决策变化”是否一致。

“有效理由”的操作定义：

- 有命中但未采用：必须说明命中内容与当前任务不相关、已过期、证据不足或被更高优先级事实推翻。
- 0 命中继续推进：必须说明检索词、检索范围、为什么当前任务仍可在无命中下安全继续。
- 命中影响决策：必须指出至少一个具体行动变化，例如新增检查、调整实现顺序、降低外发风险或改变验收标准。
- 负向样本：只写“已检索，无相关结果”但不给检索范围和继续理由，判定失败。

不降级保证：

- 不允许只写“已检索”。
- 不允许 0 命中且无理由继续通过。
- 不允许用无关命中填充证据。

验收证据：

- 知识命中到计划、实现、验收三处均可追踪。

### RSP-09 项目级 `.redcap/` 安装迁移

根因：自检通过不等于跨项目、跨路径、跨机器迁移可靠。

最终方案：

- 建立安装矩阵：空项目、已有前端项目、已有后端项目、含空格路径项目、迁移后路径项目。
- 每次安装必须生成项目级 `.redcap/`、Hook 配置、运行目录、状态目录和卸载/回滚说明。
- RedCap 源仓库不得被项目运行时污染。

不降级保证：

- 不把运行时产物写回 RedCap 源仓库。
- 不要求用户手工搬运内部文件来补安装缺口。

验收证据：

- 每类项目安装、运行、卸载、重装均通过。
- 源仓库 `git status` 不受外部项目运行污染。

### RSP-10 长任务循环机制

根因：持续推进能力有价值，但缺少边界会变成死循环。

最终方案：

- 进入条件：任务跨多阶段、多角色、多轮验证，或用户明确要求循环直到目标达成。
- 停止条件：目标达成、同根因连续三轮失败、出现不可逆/外发/私密风险、棱镜与 Cap 达到最大分歧轮次。
- 同根因连续失败时进入架构评审，不继续重跑。

不降级保证：

- 不对小任务强制开启长任务模式。
- 不把失败循环包装成进展。
- 不因循环机制存在而跳过每轮验收。

验收证据：

- 短任务不触发长任务模式。
- 长任务能持续推进。
- 同根因三轮失败会升级而不是继续空转。

### RSP-11 完成口径污染

根因：阶段成果、检查器通过、文档完成容易被误说成终局完成。

最终方案：

- 完成声明必须同时绑定任务事实、证据范围和终局目标状态。
- 最终回复必须区分：阶段通过、样本通过、当前工作区通过、生产级通过。
- 所有“完整复活”“可发布”“可投入生产”类表述必须走终局目标守卫。

不降级保证：

- 不删除终局目标守卫。
- 不把完成口径交给单一文档或单条命令。

验收证据：

- 阶段成果不会通过终局完成声明检查。
- 专用验收通过时仍保留 not_claimed 边界。

### RSP-12 文档即完成旧疾复发

根因：方案、报告、账本容易替代真实行为变化。

最终方案：

- 每个后续实施项必须写明 target reality，即用户现实中什么发生改变。
- 文档、账本、报告只能作为辅助证据。
- 若只有文档变化，完成口径只能是“方案已编写”，不能说问题已解决。

不降级保证：

- 不用登记、声明、清单替代工程行为。
- 不允许治理文件自动关闭运行时问题。

验收证据：

- 每个完成项都有运行命令、负向探针、外部项目证据或真实文件行为变化。

### RSP-13 E2E 缓存 unknown 目录治理

根因：未知目录可能是排障证据，也可能是长期垃圾；静默删除和永久保留都不合理。

最终方案：

- unknown 目录进入二级分类：可识别探针、无状态历史、疑似活跃、需人工保留。
- 老化策略只对可证明非活跃、非关键证据目录生效。
- 删除前输出 dry-run 报告；执行后输出删除清单和保留理由。

不降级保证：

- 不静默删除未知证据。
- 不因保守策略导致无限磁盘膨胀。

验收证据：

- 当前 unknown 目录能被分类。
- 删除候选为 0 时报告保留原因，而不是假装全部清理。

### RSP-14 E2E 报告可读性

根因：只说“通过”无法支持人工判断 RedCap 能力质量。

最终方案：

- E2E 报告按能力项输出：触发、产物、消费、失败回流、证据路径、通过/失败/未触发。
- 报告必须区分目标项目质量和 RedCap 工作流质量。
- 关键证据提供入口路径，不要求用户阅读全量证据目录。

不降级保证：

- 不用可访问页面证明 RedCap 通过。
- 不把大量原始日志堆给用户。

验收证据：

- 人类可在 3 分钟内判断本轮 E2E 验证了哪些 RedCap 能力。

### RSP-15 Forge 与 redcap-arsenal 边界

根因：公共能力沉淀和私人人格沉淀一旦混用，会产生隐私和治理污染。

最终方案：

- Forge 公共晋升必须脱敏、去重、索引优先、追加写入。
- redcap-arsenal 只承载公共能力模板，不承载原始运行证据、私人人格或用户敏感路径。
- 私人人格沉淀进入 `$CAP_HOME`，公共仓库只保存边界规则和哈希化证据。

不降级保证：

- 不为了复用经验泄露私有内容。
- 不让公共知识库依赖本机绝对路径。

验收证据：

- 公共晋升样本不含私密正文、凭据、未脱敏路径。

### RSP-16 Cap 复活手册迁移验证

根因：手册存在不等于在新机器、多用户、路径变化后仍可复活。

最终方案：

- 手册只引用 `$CAP_HOME`、`~/.cap`、相对路径和环境变量，不写死个人机器路径作为唯一来源。
- 复活流程分为公共步骤和私有步骤。
- 私有步骤只检查文件存在、哈希和边界，不自动读取或写入私人人格正文。

不降级保证：

- 不把私人人格搬进 RedCap 公共仓库。
- 不要求用户在迁移时手工猜路径。

验收证据：

- 设置不同 `$CAP_HOME` 时，复活检查能找到身份锚点。
- 未设置时回退到 `~/.cap`。

### RSP-17 旧 RedCap 15 项设计成熟度

根因：设计覆盖矩阵证明“被纳入”，不证明“成熟可靠”。

最终方案：

- 为 15 项设计建立成熟度层级：合同覆盖、运行入口、正向自检、负向探针、外部项目触发、长期样本。
- 每项必须明确当前层级和下一层验收条件。
- 未达到长期样本层的项不得被称为生产成熟。
- 后续实施必须新增或复用统一入口 `runtime/bin/redcap design-maturity check --design <id>`；该入口未实现前，RSP-17 只能处于方案状态。

十五项设计清单和最低验收如下：

| 设计编号 | 优秀设计 | 最低正向验收 | 最低负向探针 | 完成证据 |
|---|---|---|---|---|
| D01 | 运行时、项目工作区、用户私有状态三层分离 | 外部项目运行不污染 RedCap 源仓库 | 运行时写回源仓库必须失败 | `.redcap/evidence/rsp/rsp-17-d01-boundary.json` |
| D02 | 自开发例外必须显式化 | 自开发模式能显示边界例外原因 | 外部项目伪装自开发必须失败 | `.redcap/evidence/rsp/rsp-17-d02-self-development.json` |
| D03 | 工作区相关命令共享解析器 | 相关命令解析同一路径边界 | 子命令自行解析出不同边界必须失败 | `.redcap/evidence/rsp/rsp-17-d03-cli-parser.json` |
| D04 | 身份和私有状态不进入项目资产 | 公共仓库只保存边界和哈希 | 私人人格正文进入公共仓库必须失败 | `.redcap/evidence/rsp/rsp-17-d04-private-state.json` |
| D05 | 需求、架构、治理三轨评审门 | 三类评审均可独立触发 | 单一评审冒充三轨通过必须失败 | `.redcap/evidence/rsp/rsp-17-d05-review-gates.json` |
| D06 | 原始意图覆盖审计 | 计划和验收均引用原始意图 | 改写用户目标仍通过必须失败 | `.redcap/evidence/rsp/rsp-17-d06-intent-audit.json` |
| D07 | 完成等级禁止混报 | 阶段、样本、生产成熟分级明确 | 阶段通过冒充终局通过必须失败 | `.redcap/evidence/rsp/rsp-17-d07-completion-level.json` |
| D08 | 人工介入显性化 | 不可替代决策进入人工决策点 | 悄悄代替 Norven 价值判断必须失败 | `.redcap/evidence/rsp/rsp-17-d08-human-decision.json` |
| D09 | 始终给出可见下一步 | 阻塞、失败、部分通过都有下一步 | 只报告状态无下一步必须失败 | `.redcap/evidence/rsp/rsp-17-d09-next-step.json` |
| D10 | 外置任务真相源 | 长任务状态由外置账目承载 | 只靠上下文记忆推进必须失败 | `.redcap/evidence/rsp/rsp-17-d10-truth-source.json` |
| D11 | 索引优先读取 | 大材料先走索引或摘要 | 全量吞入上下文必须失败 | `.redcap/evidence/rsp/rsp-17-d11-index-first.json` |
| D12 | 分片账目降低上下文漂移 | 长任务可拆分、合并、验收 | 分片无合并验收必须失败 | `.redcap/evidence/rsp/rsp-17-d12-shard-ledger.json` |
| D13 | Cap 验收与评审输出分离 | Cap 仲裁和 Prism 评审分开记录 | Prism pass 被当成 Cap 完成必须失败 | `.redcap/evidence/rsp/rsp-17-d13-cap-vs-review.json` |
| D14 | 运行健康状态显性化 | degraded、blocked、healthy 可区分 | degraded 当 healthy 必须失败 | `.redcap/evidence/rsp/rsp-17-d14-health-state.json` |
| D15 | 宿主边界诚实声明 | Hook 能力声明绑定宿主与事件 | 声称跨宿主 100% 生效必须失败 | `.redcap/evidence/rsp/rsp-17-d15-host-boundary.json` |

不降级保证：

- 不把合同覆盖冒充运行成熟。
- 不因某项难测就降低成熟度标准。

验收证据：

- 15 项设计均有独立成熟度状态和证据路径。

### RSP-18 外部真实项目长期样本

根因：当前 E2E 仍偏自举验收，真实工程复杂度不足。

最终方案：

- 选择至少三类真实项目方向：前端工具、后端服务、全栈产品。
- 每类项目都由 Loom 角色链承接，Cap 只做需求方和验收方。
- 每个项目结束后必须沉淀 RedCap 能力改进，不只交付目标应用。

不降级保证：

- 不把目标应用做出来当成唯一成功标准。
- 不让 Cap 替代 Loom 执行实现。
- 不因项目小就跳过自我净化和知识召回。

验收证据：

- 每个项目都有 RedCap 能力改进报告、角色链证据、失败回流证据和知识沉淀裁决。

### RSP-19 `runtime/bin/redcap` 命令面漂移

根因：新增能力不断进入运行入口，若命令帮助、参数别名、旧命令兼容没有回归检查，外部项目和 E2E 会被命令面漂移破坏。

最终方案：

- 建立命令面清单，覆盖一级命令、关键子命令、必需参数、兼容别名、弃用策略。
- 每次新增或修改命令时，必须跑帮助文本、参数解析、旧别名兼容和错误消息回归。
- 弃用命令必须有明确迁移提示，不能静默删除。

不降级保证：

- 不允许通过删除旧命令来简化实现。
- 不允许只更新文档而不更新命令回归检查。

验收证据：

- `runtime/bin/redcap --help` 和关键子命令帮助均通过。
- 删除旧参数、破坏别名、错误消息缺迁移提示的负向样本必须失败。

### RSP-20 Codex CLI 插件和配置噪声隔离

根因：外部 E2E 若继承宿主 Codex CLI（命令行 Codex）的插件、配置或个人状态，测试结果可能不是 RedCap 能力，而是本机环境偶然能力。

最终方案：

- E2E 执行方使用隔离 `CODEX_HOME`，默认禁用非必需插件。
- 每次 E2E 记录 Codex 版本、配置摘要、启用插件清单和 Hook 可用性。
- 建立跨机器配置审计：缺插件、插件噪声、配置缺失三类场景都要可区分。

不降级保证：

- 不用“禁用所有能力”规避环境噪声；RedCap 必需 Hook 仍必须可验证。
- 不把本机特殊配置当作通用发布能力。

验收证据：

- 隔离环境能运行 RedCap 项目级安装和 Loom 基础链路。
- 宿主插件噪声注入时，E2E 能识别并失败，而不是把污染结果当通过。

### RSP-21 advisory-stop degraded 健康路径

根因：Stop 建议型检查进入 degraded（降级健康状态）时，若没有巡检和升级策略，系统会在“看似可用”状态下丢失收口质量保障。

最终方案：

- 建立 advisory-stop health check，输出 healthy、degraded、blocked 三种状态。
- degraded 必须记录原因：语义评审不可用、规则冲突、回放失败、证据缺失。
- 连续 degraded 或命中关键完成声明场景时升级为阻断或人工确认。

不降级保证：

- 不把 degraded 当作通过。
- 不因 Stop 误伤历史而关闭 Stop 的核心检查职责。

验收证据：

- degraded 样本会出现在健康报告中。
- degraded 被当作 healthy 的负向样本必须失败。

### RSP-22 E2E 报告与验收合同映射

根因：E2E 报告如果只描述结果，不映射验收合同，用户无法判断到底验证了哪些 RedCap 能力。

最终方案：

- 每个 E2E 报告字段必须映射到验收合同条款、能力项、证据文件和通过/失败/未触发状态。
- 报告同时区分目标应用质量、RedCap 工作流质量、Loom 角色质量、知识沉淀质量。
- 报告必须列出未触发能力，不能只展示通过项。

不降级保证：

- 不允许“页面可访问”“接口正常”替代 RedCap 工作流验收。
- 不允许把未触发项隐藏在原始日志里。

验收证据：

- E2E 报告能逐项追踪到验收合同。
- 缺合同映射字段的报告必须失败。

### RSP-23 Prism 多评审方一致性与差异处理

根因：Prism 的价值来自异构反对意见；如果单方通过覆盖另一方阻断，Prism 会退化成批准章。

最终方案：

- Kimi 与 Claude Code 的 verdict 必须进入 merge，保留更严格结论。
- concern 或 block 必须进入 resolution-check，记录 Cap 采纳、反驳或请求 Norven 决策。
- 同一问题超过最大讨论轮次仍无共识时，由 Cap 强制仲裁，但仲裁理由必须引用证据而非偏好。

不降级保证：

- 不允许只取更宽松的一方结论。
- 不允许 Cap 无理由否决 Prism concern。

验收证据：

- 一方 pass、一方 block 的样本最终保持阻断或有明确仲裁理由。
- resolution-check 记录每条 concern 的处理状态。

### RSP-24 Cap 运行时稳定性

根因：RedCap 能力分散在多个入口、脚本和合同中，单项通过不代表 Cap 运行时整体稳定。

最终方案：

- 建立 Cap runtime health 巡检，覆盖 gate、Prism dispatch、Loom runtime、self-purification、knowledge gateway、project install、E2E report 七类入口。
- 区分命令缺失、配置错误、权限错误、外部 provider 不可用、证据缺失五类故障。
- 巡检失败不能被 E2E 单项成功覆盖。

不降级保证：

- 不用“关键链路可用”掩盖其他入口损坏。
- 不把 provider 临时不可用写成 RedCap 能力缺失。

验收证据：

- 七类入口健康状态均可枚举。
- 任一关键入口失败时，整体健康报告不能显示 healthy。

### RSP-25 Hook 误伤率持续度量

根因：只靠个案修复无法证明 Hook 误伤问题不会复发，需要长期度量趋势。

最终方案：

- 建立 Hook 质量样本集，分为误伤、漏检、正确阻断、正确放行四类。
- 每次 Hook 逻辑变更必须跑回放，输出误伤率、漏检率、变化原因。
- 超过阈值时阻断 Hook 变更；阈值本身变更也必须走 Prism 评审。

不降级保证：

- 不用降低阈值换取通过。
- 不只修当前用户说出的样本。

验收证据：

- 误伤回放失败时，健康报告失败。
- 漏检高风险写入时，质量报告失败。

### RSP-26 知识正确性退化

根因：知识库命中可能过期、互相冲突或被旧结论污染；如果只追求命中率，会把错误经验注入新决策。

最终方案：

- 每条可复用知识必须有来源、时间、适用边界和过期条件。
- 检索命中后，必须检查是否存在更新知识、冲突知识或 no-promote 记录。
- 低置信或冲突知识只能作为提示，不能直接驱动实现决策。

不降级保证：

- 不用“知识命中”替代事实验证。
- 不把私人人格经验公共化为通用知识。

验收证据：

- 陈旧知识被降权或提示复核。
- 错误知识无解释影响实现决策的负向样本必须失败。

### RSP-27 配置契约版本兼容性

根因：项目级 `.redcap/`、Hook 配置、合同文件和运行状态会随版本演进；静默接受未知旧配置会制造隐性故障。

最终方案：

- 所有项目级配置和合同都带 schema_version。
- 新版本运行时必须提供兼容矩阵：可直接读取、需迁移、需拒绝。
- 迁移必须 dry-run 预览，执行后保留备份和迁移回执。

不降级保证：

- 不静默忽略未知字段。
- 不要求用户手工修改内部配置才能继续使用。

验收证据：

- 旧版本配置可迁移或被明确拒绝。
- 未知版本静默通过的负向样本必须失败。

## 4. 后续实施顺序

0. 先固化 RSP-00，并把 RSP-11、RSP-12 提升为所有后续条目的完成口径不变量：这些不变量不完成，不允许任何后续条目宣称解决。
1. 再修 RSP-01、RSP-02、RSP-21、RSP-25：这些是 Stop/Hook 判断系统和误伤度量风险，会污染后续所有自动化运行。
2. 再修 RSP-03、RSP-04、RSP-20、RSP-23、RSP-24、RSP-27：这些影响 Prism 可用性、provider 稳定性、Codex CLI 隔离、运行健康、配置兼容和异构评审质量。
3. 再修 RSP-16、RSP-15、RSP-26：先守住私人人格、公共晋升和知识正确性边界，避免自我净化和 Forge 引入隐私或错误知识问题。
4. 再修 RSP-05、RSP-06、RSP-10、RSP-19：这些是 Loom、长任务和 RedCap 命令面主干能力。
5. 再修 RSP-07、RSP-08：在边界和主干稳定后接入自我净化与知识召回闭环。
6. 再修 RSP-09、RSP-13、RSP-14、RSP-22、RSP-17、RSP-18：这些是迁移、缓存、报告、合同映射、成熟度和真实项目长期验证。

排序理由：

- 先治理判断系统，再治理执行系统。
- 先保证不会错报完成，再执行长期验证。
- 先保证 Prism 和 Loom 不失真，再扩大外部项目样本。
- 先解决 provider 和 Codex CLI 隔离，再扩大 Loom/E2E 规模，避免后续证据本身不可信。
- RSP-16 必须早于 RSP-07、RSP-15、RSP-26，否则自我净化、公共晋升和知识质量都可能误碰私人人格边界。
- RSP-22 是 RSP-14 的合同映射层：RSP-14 负责人类可读报告，RSP-22 负责报告字段与验收合同逐项对应，二者不合并。

## 5. 方案自检清单

| 检查项 | 结果 |
|---|---|
| 是否覆盖当前已知残留问题 | 已补齐到 RSP-00 至 RSP-27，并完成 Prism 最终复核与 concern resolution |
| 是否存在降级、绕过或放宽标准 | 已加入 RSP-00、RSP-11、RSP-12、计划变更控制和证据路径约束，并完成 Prism 最终复核与 concern resolution |
| 是否有“只写文档就算解决”的表述 | 已明确禁止，并要求每项后续实施绑定真实行为改变 |
| 是否每项都有真实验收证据方向 | 已在可执行验收矩阵中列出正向验收、负向探针和证据位置 |
| 是否区分阶段基线与终局完成 | 已区分，且禁止本方案作为终局完成证明 |
| 是否标记需要 Norven 决策的条目 | 已标记 RSP-13、RSP-15、RSP-16、RSP-18 |
| 是否需要实际开发动作 | 本轮不执行，仅作为后续实施依据 |

## 6. Prism 评审要求

Prism 需要重点审查：

1. 是否遗漏近 30 轮中已经讨论过但仍未完全成熟的问题。
2. 是否有方案实质上是降级、绕过、放宽标准。
3. 是否有方案只留下文档或账本，没有真实解决路径。
4. 是否有方案会引入新问题，例如死循环、上下文膨胀、证据污染、隐私泄漏。
5. 是否有实施顺序错误，导致后续修复被前置风险污染。

只有 Prism concerns 被接受并修正，或由 Cap 给出有证据的仲裁理由后，本方案书才能作为后续实施计划的依据。

## 7. 方案冻结与进入实施边界

为避免方案书继续膨胀，本文件通过 Prism 评审后进入方案冻结状态：

1. 不再因为普通措辞优化新增 RSP。
2. 不再通过继续扩写方案替代 RSP 实施。
3. 后续推进必须从实施顺序第 0 步开始，即先实现 RSP-00、RSP-11、RSP-12 的完成口径防线。
4. 只有发现无法归入 RSP-00 至 RSP-27 的新问题时，才允许触发计划变更控制新增 RSP。
5. 若新问题能归入已有 RSP，只能补充该 RSP 的验收或探针，不能新建平行治理项。
6. 冻结后任何方案书修改必须带可审计依据：要么引用 `rsp-contract check` 的失败输出，要么在提交信息和变更说明中标注 `plan-change-control` 并说明为什么无法归入 RSP-00 至 RSP-27。
7. 在 `rsp-contract check` 尚未实现前，冻结期方案修改必须由另一评审方复核：优先 Prism；若 Prism 不可用，则至少由另一个独立 AI 评审并留下结构化意见。

`plan-change-control` 标注格式：

```text
plan-change-control:
  reason: <为什么必须修改方案>
  affected_rsp: <RSP 编号或 new-rsp>
  cannot_fit_existing_rsp: <true|false>
  evidence: <rsp-contract check 失败输出路径，或独立评审记录路径>
  standard_change: <none|tighten|loosen>
  prism_required: <true|false>
```

审计规则：

- `standard_change=loosen` 默认失败，除非 Norven 明确授权并经过 Prism 复核。
- `cannot_fit_existing_rsp=true` 时必须给出最小复现或影响证据。
- `prism_required=false` 时必须说明为什么属于纯措辞修正，且不得改变验收、探针、证据路径、优先级或人工决策点。
- 提交信息中必须包含 `plan-change-control`，正文必须包含上述字段；缺字段则视为无效方案变更。

放宽标准的例外流程：

1. 默认拒绝 `standard_change=loosen`。
2. 若确实需要放宽，必须先说明原标准为何不可执行、会造成什么误伤或死锁。
3. 必须给出替代标准，且替代标准不能低于用户原始目标。
4. 必须经过 Norven 明确授权和 Prism 复核。
5. 复核通过后，该变更仍只能标记为 `loosen_with_approval`，不能伪装成 `none` 或 `tighten`。

`plan-change-control` 标注示例：

```text
plan-change-control:
  reason: RSP-25 的误伤率阈值需要从固定数值改为样本集相对阈值，否则小样本阶段会误杀所有 Hook 调整。
  affected_rsp: RSP-25
  cannot_fit_existing_rsp: false
  evidence: .redcap/evidence/rsp/rsp-25-hook-quality-metrics.json
  standard_change: tighten
  prism_required: true
```

因此，本方案书的终止条件不是“所有 RSP 已解决”，而是“后续如何解决所有 RSP 的方案已经足够明确、可执行、可评审，并且不再需要通过继续扩写方案来获得安全性”。

## 附录 A：第六轮最低修复对照表

本附录只用于审计追溯，不新增方案范围。

| 第六轮 minimum_fix 原文要求 | 对应方案书段落 | 满足状态 |
|---|---|---|
| 为每个 check 定义至少一条具体通过/失败判定规则 | `RSP-00 的最小机器防线` 中的 `最小检查语义` 表 | 已补齐 |
| 定义 `claim_file` 的最小 JSON schema | `RSP-00 的最小机器防线` 中的 `claim_file 最小 JSON schema` | 已补齐 |
| 定义 `evidence_file` 的最小 JSON schema | `RSP-00 的最小机器防线` 中的 `evidence_file 最小 JSON schema` | 已补齐 |
| 为 `standard_change=loosen` 增加例外机制 | `方案冻结与进入实施边界` 中的 `放宽标准的例外流程` | 已补齐 |
| 给出完整的 `plan-change-control` 标注实例 | `方案冻结与进入实施边界` 中的 `plan-change-control 标注示例` | 已补齐 |

若后续发现本对照表与正文不一致，以正文为准，并按计划变更控制修正本附录。
