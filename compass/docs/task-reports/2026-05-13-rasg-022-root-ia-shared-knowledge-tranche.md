# 任务完成报告：RASG-022 shared-knowledge 模板迁移切片

**报告日期**：2026-05-13  
**执行者**：Cap（Codex 主执行，Claude Code + Kimi 棱镜验收）  
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 已完成 RASG-022 的第一批低风险物理合并，把公共库模板源从根目录散点迁到更清晰的模板区。
- 详情：这次解决的是“根目录里还放着模板资产，容易让人误以为 RedCap 执行层、公共知识库和发布候选面混在一起”的问题。现在模板源统一位于 `templates/shared-knowledge`，活跃脚本、包候选面、公共库安全边界和检查器都已同步到新位置。棱镜发现的两个真实问题也已处理：legacy asset 脚本已识别新模板路径，RASG-022 backlog 已从计划态改为进行态。

### 0.2 上一步完成的是

- 上一步完成的是：RASG-021 已完成 Prism degradation 治理，本轮接续 current-status 暴露出的 RASG-022，开始把“只规划未物理迁移”的目录结构债务变成真实可验证的物理迁移。

### 0.3 下一步计划做的是

- 下一步计划做的是：继续评估 RASG-022 的下一批高风险根目录，是继续小切片迁移，还是在正式发布前显式延期。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：历史债务与坏味治理 → 当前主推进任务集 → 正式发布准备 → 长期演进专项。
- 当前所在位置：历史债务与坏味治理中的 RASG-022，当前切片是 `shared-knowledge` 模板源迁移，不是 RASG-022 全部结束。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要
- 说明：本切片没有触及发布、许可证、凭据、公开远端写入、大规模删除或不可逆历史改写。下一步可由 Cap 自主完成 closeout，并在后续任务中继续评估 RASG-022 剩余高风险根目录。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> “好的，赞同，你们继续按照自己评估的优先级来稳步推进吧”

### 1.2 触发背景

上一轮收口后，RedCap 的状态面显示 RASG-022 仍开放：此前 RASG-017 只完成了根目录信息架构的目标模型和登记，没有真正移动任何目录。为了避免“规划完成”被误读为“工程结构已经干净”，本轮选择风险最低、语义最明确的模板源作为第一刀。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | partial-with-explicit-defer |
| 原始意图 | 继续推进发布前历史债务治理，不再停留在计划层。 |
| 已覆盖 | 完成 `shared-knowledge` 模板源的真实物理迁移，并同步活跃消费者、包候选面、安全边界、验收和 backlog 状态。 |
| 未覆盖/延期 | `compass`、`references`、`prism`、`redcap-knowledge`、`loom` 等高风险根目录没有移动；正式 npm 发布没有开始。 |
| 用户可见边界 | 本轮只能声明 RASG-022 的一个低风险切片完成，不能声明根目录信息架构全部完成，也不能声明 release-ready。 |
| 后续路径 | 继续评估 RASG-022 的下一批高风险根目录，或在发布准备前显式记录延期理由。 |

---

## 二、方案讨论

### 2.1 问题分析

`shared-knowledge` 的历史定位是公共知识库模板源，但它直接位于 RedCap 根目录，和执行层、包根控制文件、私有知识归档同级。这会造成三类坏味：人类难以判断它是真实公共库还是模板，包候选面容易混入旧路径，后续根目录治理容易被“旧散点还在”反复打断。

本轮没有选择大规模迁移，是因为当前 RedCap 已经进入发布前结构治理深水区。直接移动高风险根目录会同时影响 closeout、Prism、历史报告、包候选面和宿主入口，风险大于收益。更稳妥的方式是先完成一个低风险切片，用它验证迁移、兼容、棱镜复核和 closeout 链路。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 保持原状 | 只在文档里解释根目录 `shared-knowledge` 是模板 | 不动代码，风险最低 | RASG-022 仍停留在计划层，无法回应“真实物理合并”问题 |
| Q1 | 小切片迁移 | 只把模板源迁到 `templates/shared-knowledge`，同步活跃消费者 | 真实减少根目录散点，风险可控，可验证 | RASG-022 仍有其他根目录债务 |
| Q1 | 大规模重排 | 一次性移动多个根目录 | 结构变化明显 | 极易破坏历史锚点、closeout、包候选面和宿主入口 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 小切片迁移 | 它既能真实推进 RASG-022，又不会把高风险根目录一次性改坏；更符合“边开飞机边换轮子”的安全策略。 | CAP_DECIDE + Prism Review |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `templates/shared-knowledge/**` | 移动 | 承接原根目录公共知识库模板源。 |
| `shared-knowledge/**` | 删除旧根 | 根目录模板散点不再作为 canonical source。 |
| `package.json` 与发布安全策略 | 修改 | 包候选面改读 `templates/shared-knowledge`，仍保持私有和禁止发布。 |
| `compass/tools/redcap-shared-knowledge*.py/sh` | 修改 | 默认模板根迁到新位置，并保留必要兼容判断。 |
| `compass/tools/redcap-legacy-asset-*.py` | 修改 | 让历史资产治理脚本识别 `templates/shared-knowledge` 这一公共模板前缀。 |
| `references/*shared-knowledge*` 与 root IA 计划 | 修改 | 同步模板路径、迁移状态、外部 arsenal 边界和回滚计划。 |
| `references/backlogs/redcap-architecture-smell-governance.json` | 修改 | RASG-022 从计划态推进为进行态，并登记本切片已应用。 |
| `references/token-structural-governance.json` | 修改 | 将膨胀后的 RASG backlog 纳入 token 风险结构治理。 |
| `prism/runs/20260513-rasg022-root-ia-shared-knowledge-tranche/**` | 新建 | 保存棱镜验收原始输出、解析结果和 acceptance binding。 |
| `prism/reports/2026-05-13-rasg-022-root-ia-shared-knowledge-tranche.md` | 新建 | 保存棱镜验收结论。 |
| `compass/docs/task-reports/2026-05-13-rasg-022-root-ia-shared-knowledge-tranche.md` | 新建 | 保存本任务完成报告。 |

### 3.2 技术实现要点

本轮的核心不是“换一个文件夹名字”，而是把模板源从根目录散点变成一个明确的模板层资产。这样人类和 Agent 都能更容易区分三件事：RedCap 执行层、RedCap 仓库内模板源、外部真实公共库 `redcap-arsenal`。

路径迁移后，同步更新了脚本、策略、包候选面和验收 fixture，防止出现“代码走新路径、发布检查还看旧路径”的分裂。棱镜指出 legacy asset 脚本仍只识别旧公共前缀后，本轮也把这类历史资产治理脚本补上，避免后续迁移时误判 `templates/shared-knowledge` 的公开属性。

另一个重要修正是 backlog 和 token 风险治理。迁移完成后，RASG-022 不再是纯计划项，所以状态被改成进行态；同时这个 backlog 文件超过了大文件审计阈值，已纳入结构治理计划，要求后续继续增长时考虑拆分关闭项归档，而不是让默认上下文被大文件拖垮。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| RASG-022 | `references/backlogs/redcap-architecture-smell-governance.json` | RedCap 架构坏味治理清单里“根目录信息架构真实物理合并”的债务项。 |
| shared-knowledge template tranche | `templates/shared-knowledge/**` | 本轮只迁移公共知识库模板源这一小片，不等于整个根目录重构完成。 |
| acceptance binding | `prism/runs/.../artifacts/acceptance-binding.json` | 把本任务和棱镜验收结果绑定起来，证明 review 不是另一个任务的旧结果。 |
| closeout receipt | `/tmp/redcap/project/.../receipts/*.json` | RedCap 收尾 runtime 生成的正式完成凭证；它存在后，任务才算正式完成。 |
| token 结构治理 | `references/token-structural-governance.json` | 大文件不能只靠“别读全文”的口头约定，要登记它的读取策略、拆分阈值和后续治理条件。 |

### 3.3 关联变更

迁移触发了三类次级修改。第一类是包候选面和安全策略同步，确保未来 npm 打包准备不会把旧路径当成真相源。第二类是历史资产治理脚本同步，确保后续旧资产迁移仍能识别公共模板路径。第三类是 token 风险登记，因为 RASG backlog 在本轮更新后进入大文件治理范围，必须被索引化而不是默认全文加载。

---

## 四、人工审核要点

> 以下是 Norven 需要重点确认的内容，其他部分 Cap 已自行验证。

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 后续是否继续迁移高风险根目录 | 本轮建议不立即移动 `compass`、`references`、`prism`、`redcap-knowledge` 等根目录；后续每一刀都应单独评估收益和破坏面。 | P1 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 公共模板检查 | `bash compass/tools/redcap-shared-knowledge-check.sh` | 通过 |
| 远端绑定检查 | `bash compass/tools/redcap-shared-knowledge-remote-check.sh` | 通过 |
| 根目录信息架构检查 | `bash compass/tools/redcap-root-information-architecture-check.sh` | 通过 |
| 包候选面与安全检查 | `bash compass/tools/redcap-runtime-package-manifest.sh --check --npm-pack-dry-run --json` | 通过 |
| 文件查阅字典检查 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过 |
| 执行保障检查 | `bash compass/tools/redcap-execution-guarantee-check.sh` | 通过 |
| public arsenal 边界检查 | `bash compass/tools/redcap-public-arsenal-claim-boundary.sh` | 通过 |
| Forge 检查 | `bash compass/tools/redcap-forge-check.sh` | 通过 |
| 用户与 Agent 身份检查 | `bash compass/tools/redcap-user-agent-identity.sh check --local` | 通过 |
| 检索升级策略检查 | `bash compass/tools/redcap-retrieval-escalation-check.sh` | 通过 |
| LLM-wiki 资产分层检查 | `bash compass/tools/redcap-llm-wiki-asset-stratification-check.sh` | 通过 |
| legacy asset 生命周期检查 | `bash compass/tools/redcap-legacy-asset-lifecycle-check.sh` | 通过 |
| legacy asset apply 预检 | `bash compass/tools/redcap-multi-session-acceptance.sh legacy-asset-migration-apply-preflight` | 通过 |
| legacy asset main-tree apply | `bash compass/tools/redcap-multi-session-acceptance.sh legacy-asset-main-tree-apply` | 通过 |
| legacy asset delete-last apply | `bash compass/tools/redcap-multi-session-acceptance.sh legacy-asset-delete-last-apply` | 通过 |
| legacy asset rehearsal | `bash compass/tools/redcap-multi-session-acceptance.sh legacy-asset-migration-rehearsal` | 通过 |
| shared-knowledge acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh shared-knowledge-check` | 通过 |
| remote binding acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh shared-knowledge-remote-binding-check` | 通过 |
| package manifest acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh runtime-package-manifest-check` | 通过 |
| public arsenal boundary acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh public-arsenal-claim-boundary-check` | 通过 |
| clean workspace E2E | `bash compass/tools/redcap-multi-session-acceptance.sh clean-workspace-e2e-check` | 通过 |
| token 风险审计 | `bash compass/tools/redcap-token-risk-audit.sh` | 通过 |
| 全局规范检查 | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] Norven 可按需要确认：后续是否继续迁移高风险根目录，还是在正式发布前显式延期。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 已清 |
| 棱镜验收 | 已通过，Claude Code 与 Kimi 均无 blocker |
| closeout summary | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/summaries/redcap-root-information-architecture-physical-consolidation-9e04f59c518e37da963824820e1145cd855bb7695f3bfd639e53e9181c74f60f.md` |
| closeout receipt | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/redcap-root-information-architecture-physical-consolidation-9e04f59c518e37da963824820e1145cd855bb7695f3bfd639e53e9181c74f60f.json` |
| rescue audit（如有） | 无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是 |
| 已正式完成 | 是，以 closeout receipt 路径实际存在为准 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| RASG-022 的高风险根目录是否继续物理迁移 | 高风险根目录牵涉 closeout、Prism、历史锚点、宿主入口和包发布面，需要单独 tranche 评估。 | P1 |
| 正式 npm 发布 | 本轮是发布前历史债务治理，不涉及许可证、registry、凭据、scope、发布开关和真实 publish。 | P1 |

### 6.2 触发的新问题

本轮触发并已处理一个新治理项：RASG backlog 进入大文件阈值后，必须被登记到 token 结构治理中。后续如果它继续膨胀，应拆出关闭项归档，而不是把 active backlog 变成新的 token 黑洞。

### 6.3 推荐的下一步行动

1. 用 current-status 查看 RASG-022 的剩余切片。
2. 决定下一刀继续做高风险根目录评估，还是将剩余高风险迁移显式延期到发布后。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| 无 | 无新增 lesson | 本轮主要是既有架构债务的第一批物理迁移，未形成需要新编号沉淀的通用经验。 |

### 7.2 流程改进建议

后续类似目录治理应继续坚持小切片迁移。每一刀都要先列消费者矩阵、兼容窗口、回滚计划和包候选面影响，再交给棱镜复核；不要把“目录结构变干净”的愿望转化成大爆炸式移动。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选 | 本轮执行与棱镜反馈 | no-promote | `compass/docs/task-reports/2026-05-13-rasg-022-root-ia-shared-knowledge-tranche.md` |

---

## 八、附录

### 附录 A：Commits

```text
尚未提交。本报告将在 closeout 通过后随本轮变更一并提交。
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| acceptance-review | `shared-knowledge` 模板迁移是否安全且未夸大完成范围 | 无 blocker；两个 P2 关注点已修复或进入 closeout | `prism/reports/2026-05-13-rasg-022-root-ia-shared-knowledge-tranche.md` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- dry-run 与消费者矩阵：`references/root-ia-shared-knowledge-tranche-manifest.json`
- 棱镜验收绑定：`prism/runs/20260513-rasg022-root-ia-shared-knowledge-tranche/artifacts/acceptance-binding.json`
- 架构坏味 backlog：`references/backlogs/redcap-architecture-smell-governance.json`
