# 任务完成报告：根级项目资产信息架构物理收敛

**报告日期**：2026-05-24
**执行者**：Cap（Codex.app 主执行，Claude Code + Kimi 棱镜复验）
**报告版本**：v1.3

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 的长期项目资产已经收敛到统一的 `assets/` 父级，旧的分散路径保留为兼容入口，不再作为真实内容主位置；活跃首读入口也已经改为 `assets/` 优先。
- 详情：docs、knowledge、references、formal Prism reports、private archive 的真实内容已迁移到 `assets/` 下；host 入口、runtime 源码、工具源码、包控制文件、本地状态和 Prism raw runs 没有迁移。
- 追加校正：上一版只证明了“真实内容主位置已迁移”，但没有充分证明“人类首读入口不会继续被旧路径误导”。本版已补齐 R7：README、ARCHITECTURE、宿主入口、CONTRIBUTING 和检查器一起收口。

### 0.2 上一步完成的是

- 上一步完成的是：修正迁移后的检查器口径，让结构检查、包面检查、索引检查能识别 `assets/` 是新的资产父级，而不是继续按旧根目录判断。

### 0.3 下一步计划做的是

- 下一步计划做的是：生成 closeout receipt，并确认 pending closure 清零。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：历史目录坏味识别 -> 统一资产父级设计 -> 真实迁移与兼容入口 -> 首读入口去旧路径化 -> 检查器和索引同步 -> 棱镜评审与回归 -> closeout receipt。
- 当前所在位置：资产迁移、首读入口收敛、本地回归、包面验证和棱镜复验已通过；正在执行最终 closeout。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮没有触及许可证、registry、凭据、正式发布开关、私密文件读取或破坏性删除。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> “关于项目资产的结构设计，我觉得是要做一个完整的合理设计了，然后敲定并直接落地，否则这个需求又要被无限期消耗下去”

### 1.2 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 不再停留在讨论和规划，而是把分散的项目资产结构真实收敛，避免目录治理无限期拖延。 |
| 已覆盖 | 统一资产父级、真实文件迁移、旧路径兼容、包面边界、结构检查、索引更新、历史债务口径修正、首读入口去旧路径化、棱镜复验绑定。 |
| 未覆盖/延期 | 正式发布动作、许可证选择、registry 凭据、破坏性删除、GraphRAG、full LLM-wiki、Prism raw runs 迁移。 |
| 用户可见边界 | 可以说“根级项目资产已完成本轮物理收敛并保留兼容入口”；不能说“所有未来知识治理都完成”。 |

## 二、方案讨论

本轮采用“统一父级 + 兼容入口”的方案，而不是直接删除旧目录。原因很朴素：RedCap 的旧报告、receipt、棱镜证据和脚本仍可能引用旧路径，如果直接删除，会让考古链断裂；如果什么都不搬，又会继续让工程目录显得像堆积物。

因此，本轮把真实内容搬到 `assets/`，同时用兼容入口维持旧路径可读。这样既改善工程结构，又不牺牲历史追踪能力。

## 三、落地结果

### 3.1 资产结构

问题：docs、knowledge、references、reports、private archive 分散在多个根级父目录下，人和 Agent 都很难判断哪些是产品入口、哪些是运行证据、哪些是历史资产。

修复：新增 `assets/` 作为长期项目资产父级，并把真实内容分别迁入 `assets/docs`、`assets/knowledge`、`assets/references`、`assets/evidence/prism-reports`、`assets/private-archive`。

效果：根目录更像产品/runtime 入口，长期资产有了统一归属；未来索引、包面、安全检查和人类阅读入口都可以围绕 `assets/` 展开。

### 3.2 兼容入口

问题：旧路径如果立刻消失，历史报告、脚本和证据链会断。

修复：保留 `compass/docs`、`compass/knowledge`、`references`、`prism/reports`、`private-archive` 作为兼容入口，指向 `assets/` 下的新真实位置。复验时确认这五个入口已作为 symlink 进入 git 索引，而不是未跟踪的本地临时状态。

效果：旧锚点继续可访问，新内容有明确主位置；这不是“把旧体系删除了”，而是“新旧路径完成过渡”。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 人话解释 | 本轮用途 |
|---|---|---|
| assets | RedCap 的长期项目资产总目录 | 收纳文档、知识、规则、正式评审报告和私有归档 |
| 兼容入口 | 旧路径仍可访问，但不再是真实主位置 | 保护旧报告、脚本和考古链接不失效 |
| 包面边界 | 将来工具被安装时允许带出去的文件范围 | 防止私有归档和运行证据误进入公开安装包 |
| Prism raw runs | 棱镜运行过程产生的原始证据 | 本轮不迁移，避免破坏证据生命周期 |

### 3.3 包面与安全边界

问题：包工具不会自动把符号链接目录里的内容当作真实包内容，如果继续依赖旧 `references` 路径，会造成检查结果和真实打包候选不一致。

修复：包候选和安全策略改为读取 `assets/references`，同时继续排除 `assets/private-archive` 和 `assets/evidence`。

效果：检查结果更接近真实包行为；私有归档、运行证据、对话草稿和本机状态仍不进入公开候选。

### 3.4 首读入口去旧路径化

问题：旧路径保留为兼容入口是必要的，但如果 README、ARCHITECTURE、宿主入口和索引说明仍把旧路径写成默认阅读路线，人类会继续看到“工程目录依旧杂乱”，Agent 也会继续沿旧路径建立心智模型。

修复：把首读叙事改成 `assets/` 优先：默认阅读、定位、报告和知识入口都指向 `assets/docs`、`assets/knowledge`、`assets/references`、`assets/evidence/prism-reports`、`assets/private-archive`。旧路径只作为“兼容入口/历史锚点”出现。

效果：这次收敛不再只是包面和脚本层成立，也在人类第一眼看到的产品说明里成立。兼容入口仍能保护旧报告和 receipt，但不再被当作新主线。

## 四、人工审核要点

本轮不需要 Norven 人工介入。它没有触及需要人工保留决策的事项：许可证、registry、凭据、正式发布开关、私密文件处理或破坏性删除。

需要注意的是，旧路径仍存在，但它们现在是兼容入口。这个状态是本轮设计的一部分，不是遗漏。

## 五、验证结果

### 5.1 机器验收

- `bash compass/tools/redcap-root-information-architecture-check.sh`
- `bash compass/tools/redcap-root-ia-deferral-check.sh`
- `bash compass/tools/redcap-formal-release-r1-root-group-disposition-check.sh`
- `bash compass/tools/redcap-file-lookup-dictionary-check.sh`
- `bash compass/tools/redcap-docs-catalog.sh generate && bash compass/tools/redcap-docs-catalog.sh check && bash compass/tools/redcap-docs-catalog.sh summary`
- `bash compass/tools/redcap-runtime-package-manifest.sh --check --npm-pack-dry-run`
- `bash compass/tools/redcap-package-publish-safety-check.sh`
- `bash compass/tools/redcap-public-package-surface.sh`
- `bash compass/tools/redcap-runtime-contract-surface-check.sh`
- `bash compass/tools/redcap-spec-check.sh "$PWD"`
- `bash compass/tools/redcap-diagnose.sh .dev-task.md`
- `bash compass/tools/redcap-clean-workspace-e2e.sh --check-result --timeout 180`

### 5.2 棱镜独立评审

- 评审 run：`20260524-root-asset-ia-physical-convergence`
- Claude Code 初审发现：需要证明 5 个兼容入口不是本地未跟踪状态，并确保 symlink / 包面变更进入 git 索引。
- Kimi 初审发现：同样要求暂存 symlink、新资产文件、`package.json`、`.npmignore` 和迁移后的元数据更新。
- 修复动作：执行 `git add -A` 后复验，确认 5 个兼容入口在 git 索引中均为 mode `120000` symlink。
- 复验结论：Claude Code 与 Kimi 均 approve，`safe_to_close_task=true`，无剩余 blocker。Kimi 曾指出 `CONTRIBUTING.md` 与 `CONTRIBUTING.core.md` 仍可能作为首读面遗漏；本版已修复并由 root IA 检查器覆盖。
- acceptance 绑定：`bash compass/tools/redcap-prism-acceptance-bind.sh --run-id 20260524-root-asset-ia-physical-convergence --task-file .dev-task.md`
- acceptance 结果：`bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` 通过，responded=2，family_count=2，blocker_roles=0。

### 5.3 closeout runtime / receipt

| 项目 | 当前值 |
|---|---|
| closeout receipt | 待生成 |
| 当前状态 | 迁移、核心检查、完整回归、首读入口去旧路径化和棱镜复验已通过；正在生成最终 closeout receipt |
| 人工介入 | 不需要 |

### 5.4 完成等级（禁止混报）

| 等级 | 结论 | 说明 |
|---|---|---|
| 已实现 | 是 | 统一资产父级、真实迁移、兼容入口、检查器同步和首读入口去旧路径化已落地 |
| 已自检 | 是 | 结构、包面、索引、安全、spec-check、diagnose 和 clean workspace E2E 已通过 |
| 已独立验收 | 是 | Claude Code + Kimi 棱镜复验通过，acceptance 已绑定当前任务 |
| 已正式完成 | 待 closeout | closeout receipt 尚未生成前，不能冒充正式完成 |

## 六、遗留问题与下一步

本轮剩余动作是 closeout receipt。正式发布本身仍是单独任务，不在本轮执行。

仍未迁移的根级内容属于有意保留边界：host 入口、runtime 源码、工具源码、包控制文件、本地状态、Prism raw runs。这些不应该被无脑搬进 `assets/`。

## 七、经验沉淀

本轮经验是：资产治理不能只靠“包排除”和“索引缓解”。如果目录结构本身持续误导人和 Agent，就应该建立清晰的物理父级；但迁移历史资产时必须保留兼容入口，先让考古链不断，再逐步收敛旧锚点。

### 7.3 Evolution Factory 候选处理

本轮命中高价值经验信号，因为它同时涉及目录结构治理、包面安全、索引迁移和回归失败修复。

处理结论：deferred-with-owner owner=RedCap-Forge trigger=post-closeout-evolution-harvest。

原因：本轮经验值得沉淀，但应在 closeout 后由 Forge 判断是否晋升为长期模式；当前先避免在未正式收口前新增额外候选干扰主任务。

## 八、附录

### 8.1 未执行边界

- 未执行正式发布。
- 未改许可证、registry、凭据、发布开关或 package privacy。
- 未读取 `.env`、identity 原文、飞书 secret 或其他私密文件。
- 未做破坏性删除。
- 未迁移 `prism/runs` raw evidence。
