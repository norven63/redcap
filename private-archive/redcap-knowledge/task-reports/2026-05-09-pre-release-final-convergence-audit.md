# 任务完成报告：P4-2 发布前最终收束审判

**报告日期**：2026-05-09  
**执行者**：Cap（Codex.app）  
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 已完成一次面向公开 CLI/npm 发布前的最终收束审判；结论是“工程安全网和本地打包预检通过，但仍不应直接公开发布”。
- 详情：本轮重新跑了发布安全、包面、runtime 包清单、发布前架构审判、结构任务树和 clean workspace E2E。现在可以明确说：RedCap 已具备本地 package readiness 和安全预检基础，但发布前架构审判仍明确保留 2 个 release blocker：许可证未定、发布开关/凭据/registry 权限未授权；此外，包面瘦身、完整执行层拆分和公开产品说明仍是发布质量层面的后续治理项。

### 0.2 上一步完成的是

- 上一步完成的是：P2-16 已把 Codex lifecycle hooks 纳入 RedCap 宿主适配，并用本机 Codex CLI live marker E2E 证明 `codex exec` 会触发 SessionStart / Stop；但 Codex.app interactive 和完整 reply-veto 仍未证明。

### 0.3 下一步计划做的是

- 下一步计划做的是：如果 Norven 不进入正式 release task，就继续做非发布类产品化治理；如果要进入正式发布，则必须先由 Norven 决定许可证、发布窗口、npm 登录/权限和是否开启发布开关。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：RedCap 工作流重构 → 信息架构/历史资产治理 → CLI 产品面与 package readiness → clean workspace E2E → Codex hooks 候选增强 → 发布前最终收束审判 → 等待正式 release task 或继续非发布治理。
- 当前所在位置：P4-2j `pre-release-final-convergence-audit`，这是发布前判断与收束审判，不是正式 npm 发布。

### 0.5 是否需要 Norven 人工介入

- 人工介入：暂时不需要。
- 说明：本轮不会执行发布，也不会碰凭据、license 或 `private/publish_allowed` 开关。真正进入公开发布时，才需要 Norven 提供许可证选择、npm 权限/登录态、发布目标和发布窗口。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> “好的，你们继续稳步推进吧”

### 1.2 触发背景

上一轮已经完成 Codex hooks candidate 接线，父任务线自然回到 P4-2：公开 CLI/npm 发布前到底还差什么。用户此前多次强调，不能只问“能不能打包”，还要审“好不好、优不优、会不会泄漏、是不是已经从 Norven 本机历史现场解耦”。因此本轮不做发布动作，而是做一次最新状态的收束审判。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 继续推进 RedCap 父任务线，当前合理下一步是确认正式发布前还剩哪些真实阻塞。 |
| 已覆盖 | 最新机器检查复核、release blocker / should-fix / deferred 分级、父任务账本同步、棱镜验收和回归。 |
| 未覆盖/延期 | 不执行 `npm publish`；不替 Norven 选择许可证；不打开发布开关；不做完整 LLM-wiki/RAG/GraphRAG；不做多 OS 外部发布矩阵。 |
| 用户可见边界 | 本轮回答“离发布还差什么”，不能冒充“已经发布”或“已经 public-release-ready”。 |
| 后续路径 | 进入正式 release task 前，Norven 需要给出许可证、发布目标、npm 权限/登录态和发布时间窗口。 |

---

## 二、方案讨论

### 2.1 问题分析

公开 CLI/npm 发布前有两层问题。第一层是硬安全：包里不能带本机路径、密钥、私有知识库、运行残留；这一层目前由机器检查覆盖，并且本轮复核通过。第二层是产品质量：一个新用户安装后能否把 RedCap 当作正经工具使用，而不是被迫理解 Norven 这台机器上的历史工程现场；这一层已经完成最小 readiness，但仍有 package surface 偏宽、完整执行层拆分未完成、公开产品说明仍可继续增强的治理空间。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 直接进入 release | 改发布开关并发布 npm | 速度最快 | 会绕过许可证、凭据、发布目标和最终授权，风险不可接受 |
| Q1 | 只做收束审判 | 复核最新事实，区分工程可修与人工边界 | 安全、诚实、不会误发布 | 不能给出“已发布”结论 |
| Q1 | 继续大规模重构 | 先做完整执行层拆分、RAG/GraphRAG、多 OS 矩阵 | 产品形态更理想 | 会把 release readiness 无限延期，且超出当前授权 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 只做收束审判 | 当前最重要的是防止把 readiness 冒充为 release；人工边界必须先被看见，而不是被自动任务吞掉。 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `.dev-task.md` | 修改 | 将当前任务锚定为 P4-2j 发布前最终收束审判。 |
| `compass/docs/task-reports/2026-05-09-pre-release-final-convergence-audit.md` | 新建 | 记录本轮人类可读结论、边界、验证和后续动作。 |
| `references/redcap-parent-task-ledger.md` | 修改 | 登记 P4-2j，并明确 P4-2 正式公开发布仍未完成。 |
| `compass/docs/catalog.json` | 修改 | 刷新任务报告索引，避免新报告无法按需检索。 |
| `redcap-knowledge/task-reports/2026-05-06-agent-reading-absorption.md` | 移入私有冷归档 | 让 active task-report inbox 回到 12 份上限内，避免近期报告入口再次淤积。 |
| `compass/tools/redcap-clean-workspace-e2e.py` | 修改 | 同步 clean workspace E2E 的允许漂移清单，承认这次报告归档迁移是受控治理动作。 |
| `prism/reports/2026-05-09-pre-release-final-convergence-audit.md` | 新建 | 记录 Claude Code + Kimi 的独立验收结论。 |
| `prism/reports/index.yaml` | 修改 | 将本轮棱镜报告登记到索引。 |

### 3.2 技术实现要点

本轮没有新增发布能力，也没有改变 npm 包的发布开关。真正做的是把“发布前还差什么”从口头判断变成可追溯的状态：机器检查证明当前包面安全和本地 readiness 仍成立；任务报告和父任务账本把人工边界、质量治理项和延期项分开，避免后续又把“dry-run 可打包”误读成“已经适合公开发布”。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| package readiness | `references/runtime-package-readiness-policy.json` / package manifest check | 本地已经能列出候选文件、跑安全检查、做 npm dry-run；不等于已经发布。 |
| release blocker | `references/pre-release-product-architecture-review.json` | 公开发布前必须解决的阻塞；当前主要是许可证和发布开关/凭据。 |
| should-fix | 同上 | 最好在广泛公开推广前继续治理的问题，例如包面太宽、产品说明还可增强。 |
| deferred | 同上 | 明确不在当前发布路径内完成的长期能力，例如完整 LLM-wiki/RAG/GraphRAG。 |
| clean workspace E2E | `references/clean-workspace-install-e2e.json` | 用干净 clone 和隔离 HOME 验证本机“像新机器一样安装/复活/预检”能跑通；不等于多 OS 外部发布矩阵。 |

### 3.3 关联变更

本轮关联更新父任务账本和 docs catalog，是为了让后续新会话或新 Agent 先看到“P4-2j 已完成的是审判，不是发布”。全局回归发现新增报告后 active task-report inbox 超过 12 份上限，因此把较早且不再是当前入口的 `2026-05-06-agent-reading-absorption.md` 移入私有冷归档；这不是删除证据，只是把低频考古材料移出默认近期入口。full acceptance 还抓到任务卡缺少 `host_surface_policy`，已补回 `mirror_only`，确保 stop-review 能把当前任务识别为“不改宿主表面”的常规 RedCap 自身开发任务。没有修改 package.json、license、publish policy 或任何凭据文件。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 许可证选择 | 当前 `license=UNLICENSED` 可以保护私有开发期，但公开 npm 发布前必须由 Norven 决定具体许可证。 | P0 |
| 2 | 是否打开发布开关 | `private=true` 与 `publish_allowed=false` 是防误发布保险；只有正式 release task 才能改变。 | P0 |
| 3 | npm 凭据 / registry 权限 | Cap 不能替 Norven注册、授权或决定发布身份；只能在授权后做本地检查。 | P0 |
| 4 | 是否继续做包面瘦身 | 当前包面安全但偏宽；是否先瘦身再发布属于产品质量取舍。 | P1 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 发布安全检查 | `bash compass/tools/redcap-package-publish-safety-check.sh` | 通过 |
| runtime 包清单 + npm dry-run | `bash compass/tools/redcap-runtime-package-manifest.sh --check --npm-pack-dry-run` | 通过 |
| public package surface | `bash compass/tools/redcap-public-package-surface.sh` | 通过 |
| 发布前架构审判 | `bash compass/tools/redcap-pre-release-product-architecture-check.sh` | 通过；检查器当前明确给出 2 个 release blocker、2 个 should-fix、1 个 deferred |
| 结构任务树检查 | `bash compass/tools/redcap-pre-release-structure-task-tree-check.sh` | 通过 |
| clean workspace E2E 结果复核 | `bash compass/tools/redcap-clean-workspace-e2e.sh --check-result` | 通过 |
| 信息架构检查 | `bash compass/tools/redcap-information-architecture-check.sh` | 通过；报告 inbox 已回到 12 份上限内 |
| stop-review fallback 回归 | `bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-falls-back-after-timeout` | 修复任务卡元数据后通过 |
| spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh pre-release-product-architecture-check && bash compass/tools/redcap-multi-session-acceptance.sh pre-release-structure-task-tree-check && bash compass/tools/redcap-multi-session-acceptance.sh clean-workspace-e2e-check` | 通过 |
| full acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh all` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 许可证选择。
- [ ] 是否进入正式 npm 发布任务。
- [ ] npm 账号、scope 权限和发布窗口。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 待 closeout runtime 核对 |
| 棱镜验收 | 通过；Claude Code + Kimi 均无 blocker |
| closeout summary | 待生成 |
| closeout receipt | 待生成 |
| rescue audit（如有） | 无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是；diagnose、spec-check、full acceptance 均通过 |
| 已独立验收 | 是；Claude Code + Kimi 均通过 |
| 已正式完成 | 否；receipt 生成后才算正式完成 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 正式 npm 发布 | 需要许可证、发布开关、凭据/权限和发布窗口，属于人工保留决策 | P0 |
| package surface 进一步瘦身 | 当前安全检查通过，但从公开产品角度仍可更薄 | P1 |
| 完整执行层拆分 | P4-2i 只完成最小兼容 runtime 布局；完整工具树迁移会影响大量路径和 hook 适配 | P1 |
| 完整 LLM-wiki / RAG / GraphRAG | 已登记为长期阈值化能力，不是发布前硬阻塞 | P3 |
| 外部多 OS 发布矩阵 | 当前 clean workspace E2E 是本机隔离验证；外部矩阵属于正式发布后/发布前扩展验证 | P2 |

### 6.2 触发的新问题

无新增必须立即修复的问题。本轮发现的关键不是新 bug，而是需要继续保持口径：RedCap 可以本地安全预检，不代表已经 public-release-ready。

### 6.3 推荐的下一步行动

1. 若 Norven 决定进入正式发布，先开 release task，明确许可证、发布开关、npm 权限和发布窗口。
2. 若暂不发布，继续沿父任务线做包面瘦身、公开产品说明和完整执行层拆分评估。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-pending | 发布前审判要把 readiness、release blocker 和产品 should-fix 分开 | 能 dry-run 打包只证明本地 readiness；公开发布还要看许可证、凭据、开关、产品独立性和用户体验。 |

### 7.2 流程改进建议

后续 release 类任务的最终汇报必须先给 Norven 看“需要他做什么决策”，再列机器证据。否则用户会误以为所有阻塞都可以由 Cap 自动完成。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选 | 本轮发布前收束审判 | no-promote | 本轮经验直接落在任务报告、父任务账本和回归口径中；后续若正式 release task 复用该模式，再考虑晋升为 release skill/流程模式 |

---

## 八、附录

### 附录 A：Commits

```text
待本轮提交后补入最终 commit。
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|----------|
| test | P4-2j 发布前最终收束审判是否诚实区分 readiness / release blocker / deferred | 通过，无 blocker | `prism/reports/2026-05-09-pre-release-final-convergence-audit.md` |
