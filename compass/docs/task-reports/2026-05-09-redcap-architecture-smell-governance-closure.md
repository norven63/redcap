# 任务完成报告：RedCap 架构坏味治理收束

**报告日期**：2026-05-09  
**执行者**：Cap（Codex.app + RedCap 本地工具链）  
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RASG-001..RASG-016 已全部从“坏味清单”落成可检查的工程边界或实体治理，非发布类主线已收束到只剩正式发布决策前的 release task。
- 详情：本轮重点解决了知识库单体膨胀、公共库状态口径分叉、冷归档不可查、reference 资产无生命周期、release package 清单多口径、Prism 运行残留、Layer A/B 边界不直观、full LLM-wiki 容易被遗忘等问题。解决方式不是只写说明，而是把每个问题绑定到索引、策略、脚本或状态面检查里，让后续会话能按需加载和机器复验。正式 npm 发布仍未启动，也没有改动许可证、发布开关或 registry 状态。

### 0.2 上一步完成的是

- 上一步完成的是：P4-2k 已经把非发布类产品化治理推进到 package readiness / hook / 通知 / clean workspace 等边界，本轮是在这个基础上做“架构坏味清仓”，把之前评审发现但尚未落地的 RASG-001..016 全部收口。

### 0.3 下一步计划做的是

- 下一步计划做的是：无新的非发布类主线任务；下一步如果继续推进，应进入“正式发布前 release readiness”专项，由 Norven 提供许可证、npm registry、发布窗口和回滚策略等人工发布决策后再启动。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：工作流重构 -> 信息架构治理 -> release package readiness -> 架构坏味治理收束 -> 正式发布专项。
- 当前所在位置：架构坏味治理收束已实现，Prism resource-limited acceptance 与全量回归已通过，等待 closeout receipt 作为正式完工凭证。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮没有触及正式发布、许可证、registry 凭据、npm publish 或不可恢复删除。正式发布专项仍需要 Norven 后续单独授权。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> “好，那么你们是否可以开始推进和落地了？把所有坏味（包括改造中新发现、新增加的坏味）都解决和落地，直至最后只剩“正式发布”相关的任务为止。”

### 1.2 触发背景

前序任务已经把 RedCap 推到 release readiness 前夜，但多轮全局审查暴露出一个更深层问题：仓库里仍有不少“有规则、有报告、但资产生命周期不够干净”的坏味。它们不会立刻阻塞本地使用，却会在正式 CLI/runtime 发布前放大成可维护性、上下文污染和发布口径风险。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 完成所有已知和改造中新发现的非发布类坏味，直到只剩正式发布相关任务。 |
| 已覆盖 | RASG-001..016 均已落地；新增的 lessons 模块化、知识网关、冷归档清单、reference 生命周期、Layer A/B 边界、full LLM-wiki 路线、release E2E matrix、arsenal head 绑定均进入机器检查。 |
| 未覆盖/延期 | 正式 npm 发布、许可证选择、registry/npm 凭据、`private=false`、`publish_allowed=true`、外部多机器发布验证。 |
| 用户可见边界 | 只能声明“非发布类架构坏味已收束”；不能声明 RedCap 已正式发布或 public-release-ready。 |
| 后续路径 | 如继续，应另开正式 release task，并先重跑 release E2E matrix、package safety、Prism review 和 clean workspace E2E。 |

---

## 二、方案讨论

### 2.1 问题分析

本轮坏味不是单点 bug，而是系统性“信息架构压力”：一部分文件太大，一部分目录承担了多种角色，一部分状态靠人记，一部分 release 边界容易被报告话术带偏。修复策略因此采用“按层治理”：活跃知识拆小、冷知识建清单、公共库加版本绑定、release 只做 readiness 不做 publish、Prism 运行证据按生命周期清理。

### 2.2 方案选项

| 选项 | 描述 | 优点 | 缺点 |
|---|---|---|---|
| 只写总结报告 | 把坏味列清楚，后续再做 | 快 | 会再次变成“登记即完成”的老问题 |
| 大规模目录重排 | 一次性物理迁移所有知识和历史资产 | 干净 | 容易伤害 receipt、旧链接、考古能力 |
| 分层治理 + 机器检查 | 对关键坏味逐个建立索引、策略、清单、检查器和小规模安全迁移 | 可回归、可渐进、风险低 | 文件数量增加，需要字典和检查器维护 |

### 2.3 决策结果

| 采纳方案 | 决策理由 | 决策方 |
|---|---|---|
| 分层治理 + 机器检查 | 它最符合 RedCap 的渐进披露原则：不牺牲考古能力，也不让大文件和旧资产继续污染新会话。 | CAP_DECIDE（基于 Norven 授权） |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|---|---|---|
| `compass/knowledge/lessons.md` + `compass/knowledge/lessons/*.md` | 修改 / 新建 | 将巨型 lessons 单体拆为轻量索引和 152 个小模块，旧 L-编号锚点保留。 |
| `references/knowledge-gateway-policy.json` + `redcap-knowledge-gateway.*` | 新建 | 定义活跃知识、LLM-wiki-lite、公共 arsenal、冷归档、raw evidence 的单一检索顺序。 |
| `references/redcap-knowledge-cold-archive-inventory.json` + `redcap-cold-archive-inventory.*` | 新建 | 给私有冷归档建立机器清单，避免默认扫 `redcap-knowledge/**`。 |
| `references/reference-asset-lifecycle.json` + `redcap-reference-asset-lifecycle.*` | 新建 | 给大型 reference 资产标明类别、生命周期和消费者。 |
| `shared-knowledge/README.md` + `public-arsenal-claim-boundary-policy.json` | 修改 | 区分模板源与外部 `redcap-arsenal` reviewed-substantive 状态。 |
| `redcap-runtime-package-manifest.py` + `package.json` | 修改 | 强制 package.json、runtime policy、publish safety policy 三者清单等价。 |
| `redcap-layerb-closeout-runtime.py` | 修改 | closeout status 增加失败尝试摘要，让最终成功和历史失败同时可见。 |
| `references/layera-layerb-boundary-policy.json` + `redcap-layer-boundary-check.*` | 新建 | 显性化 Layer A 外部项目流程与 Layer B 自身开发 runtime 的边界。 |
| `references/full-llm-wiki-roadmap.json` + `redcap-full-llm-wiki-roadmap-check.*` | 新建 | 把 full LLM-wiki / 后台 worker / RAG / GraphRAG 保持为可见但未启用路线。 |
| `references/release-readiness-e2e-matrix.json` + `redcap-release-e2e-matrix-check.*` | 新建 | 定义正式发布前需要覆盖的测试环境矩阵。 |
| `references/shared-knowledge-remote-binding.json` + `redcap-arsenal-version-binding-check.*` | 修改 / 新建 | 绑定外部 `redcap-arsenal` 当前验证 head，防止公共库状态漂移。 |
| `prism/runs/*` | 清理 | 通过生命周期工具删除 1 个过期、未引用的本地命名运行残留。 |
| `redcap-knowledge/task-reports/*` | 移动 | 将非当前、非硬锚点的旧报告移入私有冷归档，恢复历史硬锚点报告并保持 active report 上限。 |
| `redcap-spec-check.sh` / `redcap-diagnose.sh` / `file-lookup-dictionary*` | 修改 | 把新增治理入口纳入全局检查与查阅字典。 |

### 3.2 技术实现要点

本轮没有把 RedCap 直接发布成 npm CLI，而是先清掉发布前会误导 release readiness 的结构坏味。经验库从“单个大文件”变成“索引 + 小模块”，公共知识库从“模板口径”变成“模板源 + 外部实体工作区状态”，冷归档从“目录里有很多旧材料”变成“有机器清单和 exact-read 路由”。

发布相关部分只做 readiness 安全边界：package surface 三口径等价、release E2E matrix 明确外部机器仍延期、arsenal head 绑定可查。这样后续正式发布任务不会被历史资产、私有信息、公共库夸大叙述或测试范围不清误导。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|---|---|---|
| 知识网关 | `redcap-knowledge-gateway.*` | 告诉 Agent 先查哪个索引，再按需打开哪一类内容，避免到处扫目录。 |
| 冷归档清单 | `redcap-knowledge-cold-archive-inventory.json` | 私有历史材料的目录表，只用于考古，不默认进上下文。 |
| reference 生命周期 | `reference-asset-lifecycle.json` | 给大政策、大账本、大证据文件贴“它是谁、谁消费、什么时候重访”的标签。 |
| release E2E matrix | `release-readiness-e2e-matrix.json` | 正式发布前要跑哪些环境验证，哪些必须等 release task。 |
| arsenal version binding | `shared-knowledge-remote-binding.json` | 记录公共库当前已验证 commit，避免拿陈旧公共库状态做发布声明。 |

### 3.3 关联变更

新增治理脚本已接入 `redcap-spec-check.sh` 与 `redcap-diagnose.sh`。查阅字典也同步补齐，避免这些新入口变成“只有作者知道”的隐形机制。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|---|---|---|---|
| 1 | 正式发布决策 | 本轮不处理许可证、npm scope 权限、发布窗口、回滚策略，这些仍必须由 Norven 明确授权。 | P0 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|---|---|---|
| 知识索引 | `bash compass/tools/redcap-knowledge-index-check.sh` | PASS |
| 知识网关 | `bash compass/tools/redcap-knowledge-gateway.sh check` | PASS |
| 冷归档清单 | `bash compass/tools/redcap-cold-archive-inventory.sh check` | PASS |
| reference 生命周期 | `bash compass/tools/redcap-reference-asset-lifecycle.sh check` | PASS |
| Layer A/B 边界 | `bash compass/tools/redcap-layer-boundary-check.sh` | PASS |
| package manifest | `bash compass/tools/redcap-runtime-package-manifest.sh --check --npm-pack-dry-run` | PASS |
| public arsenal 边界 | `bash compass/tools/redcap-public-arsenal-claim-boundary.sh` | PASS |
| release E2E matrix | `bash compass/tools/redcap-release-e2e-matrix-check.sh` | PASS |
| arsenal 版本绑定 | `bash compass/tools/redcap-arsenal-version-binding-check.sh` | PASS |
| token 风险审计 | `bash compass/tools/redcap-token-risk-audit.sh "$PWD"` | PASS |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | PASS（resource-limited-pass） |
| 全量 spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | PASS |
| 全量 diagnose | `bash compass/tools/redcap-diagnose.sh` | PASS |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 正式发布时的许可证选择。
- [ ] npm registry 登录、发布权限、版本号和回滚策略。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|---|---|
| 执行承诺账本 | 7/7 已勾兑；等待 closeout runtime 最终核对 |
| 棱镜验收 | 通过；Claude Code 返回 blocker-free verdict，Kimi/Gemini 记录为资源受限证据，Copilot 未调用 |
| closeout summary | 待生成 |
| closeout receipt | 待生成 |
| rescue audit（如有） | 无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|---|---|
| 已实现 | 是 |
| 已自检 | 是；targeted checks、spec-check、diagnose 均通过 |
| 已独立验收 | 是；Prism acceptance 为 resource-limited-pass，无 blocker |
| 已正式完成 | 否；receipt 是唯一正式完工凭证 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|---|---|---|
| 正式 npm/public 发布 | 属于人工保留决策，需要许可证、registry、发布窗口、回滚策略。 | P0（下一专项） |
| full LLM-wiki / RAG / GraphRAG 实现 | 当前阈值未触发，且 lite 已满足当前规模；已建路线图防遗忘。 | P2 |

### 6.2 触发的新问题

本轮新增发现并已处理：`lessons.md` 单体过大、public arsenal 模板源与实体库状态容易混淆、reference 大文件无生命周期、closeout 成功态掩盖历史失败尝试、release E2E 环境边界不够显性。

### 6.3 推荐的下一步行动

1. 完成本报告后的 closeout receipt。
2. 若 Norven 决定推进，另开正式 release task。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons）

| 编号 | 标题 | 核心内容 |
|---|---|---|
| L-156 | 架构坏味治理不能只靠报告，必须绑定到索引、生命周期和检查器 | 目录结构、知识库、公共库、发布面这类坏味如果只写在报告里，很快会再次漂移；至少要有一个可执行入口持续复验。 |

### 7.2 流程改进建议

后续大型治理任务应先建立“总账本 + 每项 evidence + 机器检查”，再逐项改造。否则容易再次出现“做了新增两项，却误以为父任务全部完成”的漂移。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|---|---|---|---|
| 无新增候选 | 架构坏味治理 | no-promote；本轮已直接落地 L-156，暂不新增 Evolution Factory 候选 | `compass/knowledge/lessons/l-156.md` |

---

## 八、附录

### 附录 A：Commits

```
40c5be7 test(release): 对齐最终报告后的 clean workspace 证据
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|---|---|---|---|
| Claude Code | RASG 全量治理验收 | PASS，无 blocker | `prism/runs/20260509-redcap-architecture-smell-governance-closure/collect/architecture-review/parsed.json` |
| Kimi | RASG 全量治理验收 | 实测 review prompt 超时，记录为 resource-limited evidence；未冒充通过 | `prism/runs/20260509-redcap-architecture-smell-governance-closure/collect/risk-review/raw.txt` |
