# RedCap System Layers And Productization Roadmap

> 本文件描述 RedCap 的目标产品形态：从“某个宿主的 skill 仓库”演进为独立 Agent Runtime / CLI / 多层协作系统。它是架构路线图，不是宣称迁移已经完成。

## North Star

RedCap 的长期形态应是一个可安装、可复活、可调度、可审计的 Agent Runtime。宿主 skill 只是其中一种适配层，不应该继续充当整个系统的唯一外壳。

## Layer Map

| 层 | 中文名 | 负责什么 | 不负责什么 |
|---|---|---|---|
| Runtime Layer | 执行层 | 当前任务卡、FSM、承诺账本、closeout、validator、receipt | 长期知识沉淀和人类阅读材料的无限堆积 |
| Prism Layer | 多 Agent 验证层 | 高风险决策的独立外部审查、evidence、provider health | 普通并行提效或无风险长任务拆分 |
| Knowledge Layer | 知识层 | lessons、经验、设计原则、可复用方法论 | 每轮任务的完整流水账 |
| Evolution Layer | 进化工厂层 | 从失败、纠偏、报告和审查中生成候选，并晋升为 lessons、identity proposal、skill、rule、validator 或 no-promote | 直接后台改写 active identity 或核心规则 |
| Evidence Layer | 证据层 | task reports、Prism reports、runtime receipts、closure ledger、历史考古 | 默认灌入新会话上下文 |
| Human Reading Layer | 人类阅读层 | README、panorama、解释字典、报告索引 | 充当机器真相源 |
| Identity Layer | 人格层 | `~/.cap/identity.md` 及 proposal 边界 | 被宿主入口或自动脚本随意覆盖 |
| Host Adapter Layer | 宿主适配层 | Codex / Claude / Gemini / Copilot 等入口导入、hook、link、capability matrix | 复制 RedCap 权威规则正文 |
| Retrieval Layer | 检索层 | catalog、metadata、FTS、未来 RAG/GraphRAG | 把所有历史材料预加载给主 Agent |

## Target Shape

```text
redcap-runtime / redcap CLI
  ├─ runtime engine        当前任务、FSM、closeout、receipt
  ├─ prism coordinator     多 Agent 审查、provider policy、evidence schema
  ├─ knowledge gateway     索引优先读取、FTS/RAG 路由
  ├─ evolution factory     候选提取、晋升、no-promote、skill 化
  ├─ host adapters         Codex / Claude / Gemini / Copilot 等薄入口
  └─ human docs            README / panorama / file dictionary
```

当前仓库仍是 skill-root 形态，因此本轮采取“边界明确 + 低风险治理 + 可逆迁移支撑”的路线。已经落地的本地控制面包括：`bin/redcap` 薄 CLI facade、Prism 可用性 TTL 清单、File Lookup Dictionary coverage gate、shared-knowledge 本地模板与 append-only 工具。真正拆成独立 CLI/package，以及绑定远端 Gitee 共享库，需要后续专门迁移任务。

## Pre-release Product Architecture Gate

RedCap 进入正式 public release 之前，不只要回答“能不能打包”，还要回答“好不好、优不优、能不能离开 Norven 本机独立工作”。这一步由 `references/pre-release-product-architecture-policy.json` 定义标准，由 `references/pre-release-product-architecture-review.json` 记录当前结论，并由 `redcap-pre-release-product-architecture-check.sh` 复验真实 package / CLI / execution split / redcap-arsenal 状态。

当前 P4-2a 结论是：RedCap 已经是成熟的本地 skill-root runtime + CLI facade，但还不是优秀 public CLI/runtime 产品。P4-2b/c/d 已补齐 workspace context、doctor/debug/trace/help/error 与包名准备；剩余 public release blocker 仍包括 runtime layout 成熟度、许可证选择与发布开关/凭据边界。`redcap-arsenal` 已有首批 reviewed-substantive 公共方法论样本，但只能诚实声明“首批样本已通过 Forge 晋升”，不能冒充成熟公共知识库或历史知识已批量迁移。

## Migration Tranches

| tranche | 目标 | 可验收结果 |
|---|---|---|
| T0: Narrative and dictionary | 把 RedCap 的产品定位、文件地图、命名误导先校准 | README、file dictionary、system layers 文档存在且不增加启动上下文 |
| T1: Runtime facade | 把 `revive-cap.sh` / `closeout-cap.sh` / current-status 收敛成 CLI 形态的 facade | `bin/redcap revive/status/diagnose/closeout` 已等价调用现有入口 |
| T2: Host adapter package | 宿主入口从手写镜像变为生成或 symlink 管理 | host entries 不再手工分叉，adapter check 可阻断漂移 |
| T3: Evidence boundary | task reports、Prism runs、human reports 与 runtime receipts 分层存放 | 新会话只读索引，历史证据按需读取；大规模物理迁移必须另走 dry-run/apply |
| T4: Knowledge gateway | lessons / docs / reports 从文件索引升级到 metadata/FTS；必要时接入 RAG | `templates/shared-knowledge` 模板、外部 `redcap-arsenal` 本地工作区、append-only 写入、索引和 exact dedupe 已可运行 |
| T5: Distribution | 从 skill 仓库演进为 npm/pip/brew 或独立 CLI 包 | 新工作区可安装 runtime，而不是复制整个 skill 仓库 |

## Shared Knowledge Boundary

`templates/shared-knowledge/` 是 RedCap 仓库内模板源，不是新的上下文大包，也不是公共库本体。实体公共库工作区由 `references/shared-knowledge-remote-binding.json` 的 `preferred_local_worktree` 指向，默认应在 RedCap 仓库外；远端是 `https://gitee.com/norven63/redcap-arsenal.git`。它的规则是：

- `users/<user>/` 按用户隔离沉淀内容；本安装已初始化 `users/Norven/`
- 条目文件以 UTC 时间戳开头，只新增不改旧文件
- `redcap-shared-knowledge.sh append` 写入前先计算 fingerprint，发现 exact duplicate 就拒绝
- `redcap-shared-knowledge.sh index` 先生成 metadata/catalog，真实任务需要时再读条目正文
- 远端 Gitee remote 已绑定并可 live 对账；历史资产迁移、团队权限和跨机器同步仍必须另开任务，不在模板绑定中伪装完成

## Retrieval Route

| 阶段 | 适用条件 | 技术路线 | 不做什么 |
|---|---|---|---|
| Index + rg | 当前仓库规模、精确路径/关键词可定位 | catalog、knowledge index、`rg`、budget check | 不引入向量库复杂度 |
| Metadata / FTS | 文档数增长、标题/标签/摘要可满足多数召回 | SQLite FTS、frontmatter、summary cache | 不把全文塞 prompt |
| RAG | 需要语义召回、跨项目经验复用、关键词不稳定 | chunk + embedding + rerank + evidence path | 不替代 source-of-truth 文件 |
| GraphRAG | 需要跨实体关系、因果链、团队共享知识图谱 | entity extraction + graph communities + source links | 不在小规模知识库中过早上马 |

GraphRAG 的触发阈值应该是“关系型问题频繁出现且文件检索召回明显不足”，不是因为它流行就引入。当前权威阈值策略见 `references/retrieval-escalation-policy.json`，并由 `redcap-retrieval-escalation-check.sh` 进入 spec/diagnose/acceptance。只要 shared-knowledge / redcap-arsenal 仍处在模板与少量条目阶段，默认路线就必须保持 `index-rg-metadata`；一旦条目数、体量或失败观测跨过策略阈值，checker 会要求开启新的检索升级任务，而不是静默启用 RAG/GraphRAG。

## Guardrails

- 不把路线图冒充迁移完成。
- 不把 Evolution Factory 写成整个 RedCap 的唯一主语；它是进化层，不是 runtime 全体。
- 不把人类阅读层塞进启动上下文；人类材料也要走索引和按需读取。
- 不让宿主入口复制 RedCap 规则正文；它们只做 thin entry。
- 不因清理证据层而损坏考古能力；清理必须先分类、再 dry-run、再显式 apply。
