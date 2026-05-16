# 任务完成报告：P4-2a 发布前产品架构审判

**报告日期**：2026-05-04
**执行者**：Cap（Codex + Prism: Kimi, Claude Code）
**报告版本**：v1.3

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 现在有了一个发布前产品架构审判 gate，用来阻止“能打包”被冒充成“值得作为优秀 CLI/runtime 产品发布”。
- 详情：本轮把发布前评估拆成安全性、机器独立性、CLI 产品性、源码可见模型、公共知识边界、Agent 容器契约和分发合规几个维度，并用机器检查器对当前真实仓库状态做复验。结论不是“RedCap 可以发布”，而是“P4-2a 审判完成，当前 public release 仍有 5 个必须先处理的 release blocker”。第一轮 Prism 抓到的本机路径泄漏、checker 自证循环、本机路径硬依赖已经修复；第二轮 Prism 复审通过；完整 multi-session acceptance 又抓到缺 npm PATH、spec-check fixture 漏接新门和 stop-review 控制面失败默认飞书通知的问题，也已修复并全量回归通过；closeout runtime 已生成 receipt。

### 0.2 上一步完成的是

- 上一步完成的是：父任务线已经收口到 P4-2 正式 public release 之前，但用户指出发布前更重要的是判断 RedCap 是否已经足够优秀、独立和安全，而不是只问能不能 npm pack。

### 0.3 下一步计划做的是

- 下一步计划做的是：若继续推进 public release，应先做 P4-2b/P4-2c/P4-2d 这类发布前整改，而不是直接 npm publish。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P4-3 clean workspace E2E → parent 状态面对账 → P4-2a 产品架构审判 → P4-2b/c/d 发布前整改 → P4-2 release readiness → npm publish。
- 当前所在位置：P4-2a 已完成审判；父任务仍未 complete，P4-2 public release 仍未启动。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 我有一个疑问，后续我们本地也使用CLI吗？还是继续沿用当前的redcap/目录下的方式呢？

> 如果使用CLI的话，调试起来会不会不太方便？

> 你的意思是，可以用CLI作为入口，直接调度redcap目录下的脚本，并且这种映射调用和CLI中的普通工具调用是一个逻辑（只是一个调用的是CLI里封装的脚本，一个是直接调用redcap源码目录下的）

> 好的，透过脚本的调度，我还想和你再深入请教一下CLI的运行原理和机制，以此才能协助你从人工介入的角度一起衡量redcap的CLI化的评估：
> 1. 刚才已经聊到脚本的运行，那么其他的诸如.md工作流文件、定义文件，以及一些工作缓存目录等，这些在CLI里怎么运作呢？因为已经没有一个redcap/的运行时工作目录（还有被开发的工作区目录）给redcap运行时使用了
> 2. 我想知道npm的CLI有反编译防御能力吗？别人会看到内部的源码细节吗？
> 3. 还有一个很重要的，CLI后续怎么配合Agent容器工作呢？打开Agent容器，进入到一个，然后执行CLI吗？而且每个步骤都要执行CLI来激发？

> 好的，我已经向你基本学习和理解了CLI的一些工作机制和知识点了。那么接下来，我们是不是要 回到开发的流程中了？

> 好的，工程实现细节我无法给予帮助，请和棱镜团毒好好配合和把关

### 1.2 触发背景

用户已经理解 CLI/runtime 的基本模型后，进一步指出发布前真正担心的是两件事：不要把 Norven 本机工程现场打包出去，也不要发布一个离开本机就无法作为独立工具工作的半成品。因此，本轮不进入 npm publish，而先建立一个更高标准的产品架构审判关口。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 在 P4-2 发布前审判 RedCap 是否安全、独立、优秀，而不是只验证能不能打包。 |
| 已覆盖 | 已建立 policy、review result、checker、diagnose/spec/acceptance 接线；已用 npm pack、package safety、runtime manifest 和 Prism 两轮复审验证。 |
| 未覆盖/延期 | 未执行 npm publish；未完成 runtime 物理拆分、CLI doctor/debug/trace、package identity/license 切换、公共库实质内容填充、多 OS 发布矩阵。 |
| 用户可见边界 | 可以说 P4-2a 审判完成；不能说 RedCap 已 public-release-ready。 |
| 后续路径 | 先处理 P4-2b/c/d 发布前整改，再进入 release readiness。 |

---

## 二、方案讨论

### 2.1 问题分析

普通 release readiness 主要回答“候选包能否安全生成和安装”。但用户的核心问题更高一层：RedCap 是否已经像一个独立产品，而不是 Norven 本机路径、skill-root 结构和历史工程现场的包装物。因此，本轮新增的 gate 需要允许输出 blocker，而不是强行把结果写成 pass。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 只跑 npm pack / package safety | 继续沿用已有发布安全 gate | 成本低 | 只能证明能打包，不能证明产品优秀 |
| Q1 | 建立产品架构审判 gate | 单独审安全、独立、产品性、调试、知识边界 | 能阻止过度发布声明 | 会产出 release blocker，需要后续整改 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 建立产品架构审判 gate | 这更符合用户“好不好、优不优”的真实问题，也更适合发布前工程红线。 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `.dev-task.md` | 修改 | 重锚为 P4-2a 任务卡，锁定不 publish、只做产品架构审判。 |
| `references/pre-release-product-architecture-policy.json` | 新建 | 定义发布前产品架构审判维度、可接受状态、动态 blocker 规则和人工发布边界。 |
| `references/pre-release-product-architecture-review.json` | 新建 | 记录当前审判结论：not-ready-before-product-architecture-remediation，5 个 release blocker、2 个 should-fix、1 个 deferred。 |
| `compass/tools/redcap-pre-release-product-architecture-check.py` / `.sh` | 新建 | 用真实 package、CLI、execution split、arsenal 状态复核 review JSON 是否诚实。 |
| `references/package-publish-safety-policy.json` | 修改 | 增加本地用户 home path 内容扫描，防止包内文档泄漏本机路径。 |
| `README.md` / `references/redcap-system-layers.md` / `references/file-lookup-dictionary.md` / `shared-knowledge/README.md` | 修改 | 移除包面文档中的 Norven 绝对路径，并补充发布前产品架构 gate 解释。 |
| `bin/redcap` | 修改 | 增加 `pre-release-review` 和 `--version` 入口。 |
| `compass/tools/redcap-diagnose.sh` / `redcap-spec-check.sh` / `redcap-multi-session-acceptance.sh` | 修改 | 将 P4-2a gate 接入诊断、总体验证和 targeted acceptance。 |
| `references/file-lookup-dictionary.md` / `references/file-lookup-dictionary-policy.json` / `references/execution-guarantees.json` | 修改 | 将新 gate 加入文件查找字典和执行保障体系。 |
| `prism/runs/20260504-pre-release-product-architecture-review/**` | 新建 | 记录两轮 Prism 审查与最终 acceptance binding。 |

### 3.2 技术实现要点

这次的关键不是把 release blocker 修完，而是让 RedCap 能诚实地识别这些 blocker。checker 会从真实文件读取 package name、private 状态、license、npm pack 文件数、CLI 命令面、execution split 状态和 redcap-arsenal 内容状态，再反推哪些 finding 必须存在；如果 review JSON 漏写，就 fail。

第一轮 Prism 抓到两个机制问题：包内文档泄漏本地 home 绝对路径，以及 checker 通过“必须永远有 blocker”自证。修复后，安全 gate 会扫描本地 home path，review 不再写绝对路径，checker 改为按当前事实动态要求 blocker；未来如果 blocker 被真实修复，checker 不会因为“没有 blocker”而失败。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| pre-release product architecture gate | `redcap-pre-release-product-architecture-check.sh` | 发布前先审“像不像一个好产品”，不只审“能不能打包”。 |
| release blocker | `references/pre-release-product-architecture-review.json` | 不解决就不应 public release 的问题。 |
| should-fix | 同上 | 发布前最好处理，但可以通过明确缩小发布口径延期。 |
| runtime/project/user boundary | `references/redcap-system-layers.md` | npm 包是工具箱，项目目录是被管理现场，用户 home 是个人配置；三者不能混成 Norven 本机工程目录。 |
| redcap-arsenal template-only | `references/shared-knowledge-remote-binding.json` | 公共库目前只是骨架和命名空间，不是已经有真实知识内容。 |

### 3.3 关联变更

新增 gate 后，同步更新了文件查找字典、执行保障、README、system layers 和 CLI facade，确保后续 Agent 能从固定入口找到这套审判机制。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 是否进入 P4-2b/c/d 整改 | 这不是阻塞本轮 P4-2a 完成，但会决定下一步是否继续向 public release 推进。 | P1 |
| 2 | 未来 public package license | 当前 `UNLICENSED` 是 public release blocker；具体 license 需要产品/法律/发布策略决策。 | P1 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 新 checker 语法 | `python3 -m py_compile compass/tools/redcap-pre-release-product-architecture-check.py` | 通过 |
| 新 policy/review JSON | `python3 -m json.tool references/pre-release-product-architecture-*.json` | 通过 |
| 包面安全 | `bash compass/tools/redcap-package-publish-safety-check.sh` | 通过，195 files |
| 产品架构审判 | `bash compass/tools/redcap-pre-release-product-architecture-check.sh` | 通过，release_blockers=5 |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh pre-release-product-architecture-check` | 通过 |
| runtime package manifest | `bash compass/tools/redcap-runtime-package-manifest.sh --check --npm-pack-dry-run` | 通过 |
| 文件字典 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过 |
| 执行保障 | `bash compass/tools/redcap-execution-guarantee-check.sh` | 通过 |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过，Kimi + Claude Code |
| 人类输出质量 | `bash compass/tools/redcap-human-output-quality-check.sh --task-file .dev-task.md` | 通过 |
| Evolution harvest | `bash compass/tools/redcap-evolution-harvest-check.sh .dev-task.md` | 通过，候选已登记并 promoted |
| 父任务聚合 | `bash compass/tools/redcap-parent-receipt-aggregation-check.sh` | 通过，P4-2a 作为 durable child 登记 |
| 缺 npm PATH 兼容 | `PATH=/usr/bin:/bin bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| 总体验证 | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| 诊断总览 | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 通过，closeout receipt 仍待生成 |
| 完整 acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh all` | 通过 |
| 飞书策略 | `bash compass/tools/redcap-feishu-notification-policy-check.sh` | 通过，stop-review 控制面失败默认不发飞书 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 是否选择某个 public license。
- [ ] 是否现在进入 P4-2b/c/d 发布前整改。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 已清，7/7 完成 |
| 棱镜验收 | Kimi + Claude Code 两轮复审；最终 acceptance binding 已通过 |
| closeout summary | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/summaries/pre-release-product-architecture-review-a6f45bc977dbf60dedda31a9bacd401887fb71267e5dc16695d0e47f60a31483.md` |
| closeout receipt | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/pre-release-product-architecture-review-a6f45bc977dbf60dedda31a9bacd401887fb71267e5dc16695d0e47f60a31483.json` |
| rescue audit（如有） | 无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是，P4-2a gate 已实现 |
| 已自检 | 是 |
| 已独立验收 | 是，Prism acceptance pass |
| 已正式完成 | 是，closeout receipt 已生成；P4-2 public release 仍未完成 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| P4-2b runtime/project/user boundary 物理拆分与 CLI workspace context | 属于发布前整改，不是审判 gate 本身 | P0-before-public-release |
| P4-2c CLI doctor/debug/trace/error/help 产品面 | 属于发布前整改 | P0-before-public-release |
| P4-2d public package identity/license/surface | 需要发布策略与包名/license 决策 | P0-before-public-release |
| P4-2e public arsenal content strategy | 当前公共库 template-only，是否发布时强调该能力取决于产品口径 | P1-before-broad-marketing |

### 6.2 触发的新问题

本轮确认：RedCap 不能再被描述为“除 npm 发布外都好了”。更准确的父任务状态是：本地 runtime 主线已收口，但 public release 前还有产品架构整改 tranche。

完整 acceptance 还额外暴露三个工程问题：P4-2a checker 第一版在受限 hook PATH 缺少 npm 时会误炸；spec-check 的最小仓库 fixture 没同步新增的 pre-release gate；stop-review 控制面失败路径默认发送飞书通知，违背“内部 audit gap 默认只落账、不飞书”的通知降噪原则。三项都已修复：checker 在缺 npm 时只接受已登记且此前验证过的 `npm_pack_dry_run_checked=true` 与候选数事实，fixture 也新增 pre-release gate stub 和失败传播用例，stop-review 控制面失败通知改为显式 opt-in 且只允许 `manual-intervention`。

### 6.3 推荐的下一步行动

1. 若继续 public release 主线，先做 P4-2b：让 CLI 默认操作被管理项目工作区，而不是 package root。
2. 然后做 P4-2c：补 `doctor/debug/trace` 和外部用户错误提示。
3. 最后做 P4-2d：切换 `@norven63/redcap`、license、package surface 与 release readiness。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-149 | 发布前要审产品形态，不只审打包能力 | npm pack 只回答“能不能打包”，不能回答“是否安全、独立、优秀”。 |

### 7.2 流程改进建议

P4-2 正式发布前必须固定先经过 P4-2a gate；如果 gate 输出 release blocker，不能直接进入 release readiness。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| EVO-2026-05-04-001 | Prism 抓到本机路径泄漏和 checker 自证循环 | promoted-to-lesson | `compass/knowledge/lessons.md` |

---

## 八、附录

### 附录 A：Commits

```
见 `git log --oneline` 中本任务相关提交。
```

### 附录 B：棱镜调用记录

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| test / Kimi first round | 是否漏掉产品架构 blocker | 抓到 CLI workspace context、checker 自证循环、本机 arsenal 路径硬依赖等问题 | `prism/runs/20260504-pre-release-product-architecture-review/collect/kimi-reviewer/raw.txt` |
| test / Claude first round | 是否漏掉产品架构 blocker | 抓到包内文档泄漏本地 home 绝对路径、checker 自证循环、license 等问题 | `prism/runs/20260504-pre-release-product-architecture-review/collect/claude-reviewer/raw.txt` |
| test / Kimi final | 修复后是否还有 blocker | pass；只剩轻微 evidence 冗余，已修复 | `prism/runs/20260504-pre-release-product-architecture-review/collect/kimi-final/raw.txt` |
| test / Claude final | 修复后是否还有 blocker | pass-after-addressed-findings；指出的质量问题已修复 | `prism/runs/20260504-pre-release-product-architecture-review/collect/claude-final/raw.txt` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- 审判策略：`references/pre-release-product-architecture-policy.json`
- 审判结果：`references/pre-release-product-architecture-review.json`
- 检查入口：`bash compass/tools/redcap-pre-release-product-architecture-check.sh`
