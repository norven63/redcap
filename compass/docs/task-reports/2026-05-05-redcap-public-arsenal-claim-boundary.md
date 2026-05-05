# 任务完成报告：P4-2e public redcap-arsenal 内容策略与 claim 边界

**报告日期**：2026-05-05
**执行者**：Cap（Codex.app + Prism: Claude Code / Copilot）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 已把公共 `redcap-arsenal` 的 template-only 状态和宣传边界变成机器可检查规则。
- 详情：本轮解决的是“公共库已经初始化，但不能被误说成已有实质知识库”的问题。现在 `redcap-arsenal` 只能被描述为模板、schema、索引目录和用户命名空间已初始化；不能宣传为已迁移历史知识、已填充公共知识库或成熟 skill arsenal。未来只有经过 RedCap Forge 的脱敏、去重、append-only 条目写入和索引刷新后，才允许进入 populated claim 评估。

### 0.2 上一步完成的是

- 上一步完成的是：P4-2d 已准备 `@norven63/redcap` 包身份、包面和发布安全边界。
- 详情：P4-2d 解决“未来 CLI 包叫什么、哪些内容能进包、发布仍如何锁住”；P4-2e 接着解决“公共知识库现在能不能被当作已有内容宣传”。

### 0.3 下一步计划做的是

- 下一步计划做的是：P4-2h 历史资产公共蒸馏与 RedCap Forge export triage 仍保持 deferred；正式 npm 发布仍另开 release task。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P4-2a 产品架构审判 -> P4-2b workspace 边界 -> P4-2c CLI 产品面 -> P4-2d 包身份/包面 -> P4-2e 公共 arsenal claim 边界 -> P4-2h 历史资产公共蒸馏 -> P4-2 正式发布。
- 当前所在位置：P4-2e 已完成实现与棱镜修补；P4-2 正式发布仍未完成，也不能声明 public-release-ready。

### 0.5 是否需要 Norven 人工介入

- 人工介入：当前不需要。
- 说明：P4-2e 已按授权范围完成，正式 npm 发布、历史知识公共蒸馏和 public-release-ready 声明仍属于后续独立任务。
- 说明：本轮没有迁移私有历史知识、没有执行 npm publish、没有改变许可证或发布开关。后续只有进入真实发布、许可证选择、或公开蒸馏具体历史资产时才需要 Norven 决策。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 好的，那么请你和棱镜团队继续稳步推进下面的任务，可以吗？还是说，你有更加建议的事情要做？

> 另外，RedCap通过“任务账本、门禁、receipt 和 closeout 结论”这一些列的机制，让宿主Agent加载和运行的skill产物无法越权，只能作为参考，对吗？

### 1.2 触发背景

P4-2d 之后，公共包身份已经准备好，但公共 `redcap-arsenal` 仍只有模板、schema 和用户目录占位。如果不把这条边界显性化，后续 README、release review 或汇报很容易把“仓库已初始化”误讲成“公共知识库已填充”。

用户同时追问宿主 skill 产物是否会越权。这个问题和本轮 claim 边界同源：RedCap 不能物理控制宿主加载什么 skill，但可以规定哪些证据能成为 RedCap 的正式任务结论。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 继续推进 RedCap 主线，并确认 overlay/skill 产物不能越过 RedCap 任务账本和收口结论。 |
| 已覆盖 | 已完成 public arsenal claim boundary policy/checker、README 口径修正、pre-release review 对账、diagnose/spec-check/execution guarantees/acceptance 接入、Prism 审查与修补。 |
| 未覆盖/延期 | 不迁移历史知识到公共库；不执行 npm publish；不把 template-only 仓库宣传为已填充公共知识库。 |
| 用户可见边界 | 可以声明“公共库 template-only claim 边界已被机器化保护”；不能声明“公共库已有实质知识内容”。 |
| 后续路径 | P4-2h 可在未来通过 RedCap Forge 选择性蒸馏历史资产；正式发布仍是独立 release task。 |

---

## 二、方案讨论

### 2.1 问题分析

本轮的核心风险不是代码能不能跑，而是产品口径会不会越界。一个空模板库如果被说成“团队共享知识库已经建立”，会让发布材料、README 和后续任务计划都产生误导。

更安全的做法是先建立 claim boundary：明确现在只能说模板已初始化，不能说知识已迁移；未来要升级口径，必须先有可审计的公开条目和 RedCap Forge 证据。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| 公共库内容 | 现在就迁移历史知识 | 把历史报告/lessons 蒸馏成公共条目 | 看起来更“有内容” | 高隐私风险，且会把 P4-2e 变成 P4-2h |
| 公共库内容 | 只锁 template-only claim 边界 | 不迁移私有内容，只让当前状态诚实可验 | 安全、符合当前主线 | 公共库仍没有实质知识条目 |
| overlay 边界 | 宣称能阻止宿主 skill 加载 | 把 RedCap 描述为权限沙箱 | 表面强控制 | 技术上不成立 |
| overlay 边界 | 只控制 RedCap 正式结论 | 外部 skill 只能给建议，不能覆盖任务真相 | 真实可执行 | 无 hook 宿主仍无法 100% 物理拦截 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| 公共库内容 | 只锁 template-only claim 边界 | 当前目标是诚实口径，不是公开迁移历史知识。 | Cap + Prism |
| 未来 populated claim | 强制 RedCap Forge + privacy + dedupe + append-only + index | 避免未来只因出现文件就宣传为成熟知识库。 | Cap + Prism |
| overlay 权限 | advisory-only 结论边界 | RedCap 不控制宿主权限，只控制 RedCap 自己承认什么是完成结论。 | Cap |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `references/public-arsenal-claim-boundary-policy.json` | 新建 | 定义 template-only 阶段允许/禁止 claim、未来 populated claim 的必备门禁和 release 关系。 |
| `compass/tools/redcap-public-arsenal-claim-boundary.py` / `.sh` | 新建 | 对账外部 `redcap-arsenal` 实质条目数量、README 口径、pre-release review facts 和 future claim gates。 |
| `shared-knowledge/README.md` | 修改 | 明确当前状态是 template-only，不能宣传为已填充公共知识库。 |
| `../redcap-arsenal/README.md` | 修改并推送 | 移除本机绝对路径，补充 RedCap Forge 与 template-only 边界。 |
| `references/shared-knowledge-remote-binding.json` | 修改 | 更新 Gitee live head 证据，确认远端 README 已同步。 |
| `references/pre-release-product-architecture-review.json` | 修改 | 增加 claim boundary pass 事实，并保留 public arsenal 仍 template-only 的 should-fix 口径。 |
| `compass/tools/redcap-diagnose.sh` / `redcap-spec-check.sh` | 修改 | 将 claim boundary gate 接入诊断和总门禁。 |
| `references/execution-guarantees.json` / `references/file-lookup-dictionary.md` | 修改 | 将新 gate 纳入执行保障和文件查找字典。 |
| `compass/tools/redcap-overlay-governance-check.sh` | 修改 | 明确检查 overlay 不能覆盖任务卡、账本、门禁、receipt、closeout 结论。 |
| `prism/reports/2026-05-05-public-arsenal-claim-boundary-review.md` | 新建 | 归档本轮 Prism 审查结论和修补事项。 |

### 3.2 技术实现要点

claim boundary checker 现在不是只看“有没有政策文件”，而是会实测外部公共库 worktree：当前实质条目数必须是 0，且 pre-release review 的事实也必须写 0。这样报告、review 和真实文件系统不会各说各话。

棱镜审查指出初版 checker 还不够硬：未来 populated claim 的门禁不能只检查列表非空，实质条目也不能把索引文件算进去。修补后，checker 会逐项要求 RedCap Forge、隐私扫描、去重、append-only schema、索引刷新和远端绑定检查，并且只把 `users/<user>/` 下的条目算作实质公共知识。

overlay 规则也被补强为“结论权威链”而不是泛泛 advisory：宿主 skill 可以提供建议，但不能覆盖 `.dev-task.md`、任务账本、门禁结果、runtime receipt 或 closeout 结论。

完整回归期间额外暴露了两个和 P4-2e 主逻辑无关、但会影响长任务可靠性的收尾问题：stop-review reviewer 调用与 Prism/agent 健康嗅探在 CLI 超时 fallback 后，极端情况下可能留下 descendant 进程或等待后台子进程自然结束；同时 Prism availability cache 只记录 shell wrapper hash，未记录实际 Python probe 实现 hash。前者已在 `redcap-on-stop-review.sh` 与 `redcap-agent-health-probe.py` 的 timeout runner 中修复为“进程树/进程组 TERM -> 等待 -> 必要时 KILL -> 再等待”；后者已在 `prism-availability.py` 中补充底层实现 hash，避免 probe 实现变化后误用旧缓存。提交前安全扫描还发现一个历史报告把飞书 secret 前缀写进了扫描正则示例，本轮已改成通用占位词，避免历史材料留下发布前安全坏味。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| template-only | `public-arsenal-claim-boundary-policy.json` | 公共库只有模板、schema、索引目录和用户命名空间，占位不等于已有知识。 |
| substantive entries | `redcap-public-arsenal-claim-boundary.py` | 真正的公共知识条目，只能算 `users/<user>/` 下经过流程写入的内容。 |
| RedCap Forge | `references/redcap-forge-policy.json` | 把私有经验蒸馏、脱敏、去重、结构化后，再决定是否公开的流水线。 |
| claim boundary | 本轮新 gate | 规定现在能说什么、不能说什么，以及未来升级宣传口径需要什么证据。 |
| advisory overlay | overlay governance | 宿主 skill 产物只能做参考，不能成为 RedCap 的正式完成结论。 |

### 3.3 关联变更

公共 `redcap-arsenal` 仓库已单独提交并推送 README 修复，提交为 `2dbec75 docs: 明确公共库模板边界`。RedCap 的远端绑定证据已更新到这个 head，并通过 live check。

---

## 四、人工审核要点

当前没有需要 Norven 立即确认的事项。

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 未来是否公开蒸馏历史资产 | 这属于 P4-2h，不在本轮执行；如果要公开具体内容，需要 Norven 对隐私和公开范围给战略授权。 | P1 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| claim boundary gate | `bash compass/tools/redcap-public-arsenal-claim-boundary.sh` | ✅ |
| public arsenal acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh public-arsenal-claim-boundary-check` | ✅ |
| overlay governance | `bash compass/tools/redcap-overlay-governance-check.sh` | ✅ |
| overlay acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh overlay-governance-check` | ✅ |
| pre-release review | `bash compass/tools/redcap-pre-release-product-architecture-check.sh` | ✅ |
| spec gate propagation | `bash compass/tools/redcap-multi-session-acceptance.sh spec-check-propagates-control-gate-failures` | ✅ |
| Prism evidence | `bash prism/tools/prism-evidence-check.sh` | ✅ |
| shared knowledge remote live | `bash compass/tools/redcap-shared-knowledge-remote-check.sh --live --require-worktree` | ✅ |
| umbrella spec | `bash compass/tools/redcap-spec-check.sh "$PWD"` | ✅ |
| full acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh all` | ✅，第一次回归暴露 stop-review timeout descendant 清理竞态；修复后重新通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

当前没有必须由 Norven 立即手动完成的验证项。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 已同步为 0 个未兑现承诺，等待 closeout runtime 最终写入 receipt |
| 棱镜验收 | Claude Code + Copilot 已审查；Copilot 提出的 3 个问题和 follow-up 精确门禁问题均已修复 |
| closeout summary | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/summaries/redcap-public-arsenal-claim-boundary-abf96614847a49278da2b2d0202b6d887acf558ffd3e7bfa6fd321c059795609.md` |
| closeout receipt | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/redcap-public-arsenal-claim-boundary-abf96614847a49278da2b2d0202b6d887acf558ffd3e7bfa6fd321c059795609.json` |
| rescue audit（如有） | closeout 失败时才生成；当前目标是无 rescue audit 成功收口 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，Prism 已提出并复核关键修补点 |
| 已正式完成 | 待 closeout receipt 生成后确认；不得在 receipt 生成前对外宣称父任务完成 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 公共库实质知识条目 | 需要 RedCap Forge 对具体历史资产做脱敏、去重和公开价值判断，属于 P4-2h。 | P1 |
| 正式 npm 发布 | 仍需要许可证、registry、发布授权和 release readiness；不属于 P4-2e。 | P0-before-release |

### 6.2 触发的新问题

本轮没有新增必须立刻展开的新父任务。棱镜指出的 3 个实现问题已经在本轮修复。

### 6.3 推荐的下一步行动

1. 若继续推进公共知识库内容，进入 P4-2h：历史资产公共蒸馏与 RedCap Forge export triage。
2. 若推进 npm 发布，另开正式 release task，先处理许可证和发布授权。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| 无新增 | 本轮经验已被转化为 policy/checker/acceptance | “模板库不能冒充已填充知识库”直接进入机器门禁。 |

### 7.2 流程改进建议

Prism 的价值在本轮非常明确：单 Agent 初版会漏掉“列表非空不等于强门”和“索引不等于实质知识”这类边界问题。后续涉及公开声明、权限边界、发布口径时，应继续用 Prism 或等价独立审查。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选 | Prism verdict | 直接转成 policy/checker/acceptance，未进入单独候选池 | `references/public-arsenal-claim-boundary-policy.json` |

---

## 八、附录

### 附录 A：Commits

本报告编写时 RedCap 主仓库提交尚待完成。

公共 `redcap-arsenal` 仓库已完成：

```text
2dbec75 docs: 明确公共库模板边界
```

### 附录 B：棱镜调用记录

| 模式 | 问题 | 结论 | 报告路径 |
|---|---|---|---|
| test | P4-2e public arsenal claim boundary | pass-after-fixes | `prism/reports/2026-05-05-public-arsenal-claim-boundary-review.md` |
