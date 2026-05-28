# 任务完成报告：RASG-028 公共武器库实质扩容

## 零、先看懂当前局面

这轮要解决的问题很朴素：RedCap 不能再只说“我有自我升级机制、我有公共武器库规则”，而要真的把已经审查过的高价值经验放进公共武器库里，并证明它们可检索、可复用、不会泄漏私密材料。

本轮采用小批量推进：只从已经结构化的 Evolution 候选中挑选安全条目，不做大规模历史搬迁，不读取私密原文，也不把少量增长夸大成“公共武器库已经成熟”。

### 0.1 当前已完成

- 当前已完成：redcap-arsenal 已新增第二批 4 条 reviewed append-only public entries，公共条目数量从 4 条增加到 8 条；RedCap 侧的公共库状态、远端绑定、边界声明、父任务账本、棱镜验收记录和发布前架构事实都已同步到同一个提交。

### 0.2 上一步完成的是

- 上一步完成的是：RASG-027 把“经验是否值得沉淀”从报告里的口头判断升级成主动 harvest 账本，避免高价值经验在任务收尾后静默丢失。

### 0.3 下一步计划做的是

- 下一步计划做的是：生成 RASG-028 的最终 closeout receipt 后，父任务线自动进入 RASG-029，继续处理工程目录最终收敛；不会等待 Norven 机械回复“继续”。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：先修外部工作区边界，再补强主动经验收割，然后让公共武器库真实增长，再做工程目录最终收敛，最后才进入正式发布授权。
- 当前所在位置：正式发布前历史债务治理中的“公共武器库实质扩容”。

整体进度用人话概括如下：

- 已完成：revive 外部工作区边界热修、自我升级主动 harvest 产线、公共武器库第二批实质条目。
- 本轮完成：公共武器库不再只有种子样本，已经有第二批可检索、可审查、可复用的方法条目。
- 后续继续：工程目录最终收敛、剩余历史债务收口、正式发布前安全边界确认。
- 仍未触碰：正式发布授权、版本发布开关、registry 发布动作。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮没有触发 secret、不可恢复删除、正式发布授权、license、registry 或用户保留产品决策。

## 一、需求背景

Norven 指出过一个非常关键的问题：RedCap 过去很容易把“机制已经建立”包装成“能力已经真正运转”。公共武器库就是典型例子：如果没有真实新增条目、没有 catalog、没有远端绑定、没有隐私和重复审查，那么“公共知识库”仍然只是设计图。

RASG-028 的目标因此被限定得很具体：

- 必须真实增加 redcap-arsenal 的公共条目数量。
- 必须保留 append-only 的公共库增长方式。
- 必须证明新增条目不是已有内容的重复改写。
- 必须证明没有把私密原文、identity、secret、本机路径或 Prism raw 证据发布出去。
- 必须防止过度声明：本轮只能说“完成第二批安全扩容”，不能说“全部历史知识都迁移完毕”。

## 二、方案讨论

本轮没有做“全量迁移”，而是采用更安全的 Forge 批次策略：

- 来源只选已经 promoted 的 Evolution 候选，不打开私密原始报告。
- 批次只选 4 个互补主题，先证明链路真的跑通。
- 每条公共 entry 都包含问题源、解决方案、最终效果、适用边界、证据锚点、隐私审查、重复审查和公开声明边界。
- Kimi 与 Claude Code 做独立复核，重点看公开安全、重复风险、过度声明风险和候选质量。

棱镜结论是 `pass_with_nits`，无 blocker。已吸收的提醒包括：区分候选捕获和信号门控，避免把 provider roster gate 写成内部脚本流水账，不复制私密路径，并让每条公共 entry 都写清 public claim boundary。

## 三、落地结果

本轮新增 4 条公共条目：

| 新条目 | 类型 | 对外价值 |
|---|---|---|
| `20260528T200617Z-methodology-candidate-first-experience-sedimentation.md` | methodology | 高价值经验先进入候选池，防止任务结束后遗忘 |
| `20260528T200617Z-lesson-ttl-roster-gate-for-multi-agent-dispatch.md` | lesson | 长任务委托前先确认 Agent 可用性，避免把时间浪费在不可用工具上 |
| `20260528T200617Z-methodology-fail-closed-signal-gate-for-experience-harvest.md` | methodology | 高信号任务必须明确晋升、不晋升或延期，不能静默丢失经验 |
| `20260528T200617Z-methodology-facade-first-rule-before-physical-tool-migration.md` | methodology | 路径敏感迁移先稳定入口，再做物理迁移，降低大改动风险 |

外部 redcap-arsenal 已推送到 Gitee，当前绑定提交为 `95f0783dd6d304c340d3209a2ba44da0f187cbdf`。公共库 catalog 当前能发现 8 条公共条目。

RedCap 侧同步完成：

- 公共武器库远端绑定已指向新的 Gitee 提交。
- 公共声明边界已从“首批种子条目”更新为“两批 reviewed append-only public entries”。
- 发布前架构审查事实已更新为 8 条 substantive entries。
- 父任务账本和 RASG backlog 已标记 RASG-028 完成，并把下一项指向 RASG-029。
- 新增的 RASG 批次 manifest 已被排除出公开包候选面，因为它是任务证据，不是外部用户运行 RedCap 所需的产品文件。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 人话解释 | 本轮作用 |
|---|---|---|
| redcap-arsenal | RedCap 的公共武器库 | 存放可复用、可公开、经过审查的方法条目 |
| Forge batch | 一次小批量公共晋升 | 先选候选，再做隐私、重复和声明边界审查，最后追加到公共库 |
| append-only public entry | 只新增不覆盖的公共条目 | 保护历史可追溯性，避免后续修改抹掉原始版本 |
| public claim boundary | 公开声明边界 | 规定本轮能说什么、不能夸大说什么 |
| manifest | 批次清单 | 记录选择来源、拒绝来源、审查结论和验证状态 |

## 四、人工审核要点

Norven 需要重点看三个结论：

- 第一，本轮不是“又写了一份规则”，而是公共库真实新增了 4 条内容，并已推送到外部仓库。
- 第二，本轮没有把私密原始材料公开出去；公共条目只引用候选 ID 和可公开的策略锚点。
- 第三，本轮仍然不等于正式发布准备完成，也不等于全部历史经验迁移完成。

如果后续要继续扩大公共库，应继续按小批次、可审查、append-only 的方式推进，而不是一次性把历史私有资产整包搬进 public arsenal。

## 五、验证结果

已通过的验证：

- `python3 compass/tools/redcap-shared-knowledge.py "$PWD" check --root /Users/norven/.claude/skills/redcap-arsenal`
- `bash compass/tools/redcap-shared-knowledge-remote-check.sh --live --require-worktree`
- `bash compass/tools/redcap-arsenal-version-binding-check.sh`
- `bash compass/tools/redcap-public-arsenal-claim-boundary.sh`
- `bash compass/tools/redcap-public-distillation-preflight.sh`
- `bash compass/tools/redcap-pre-release-product-architecture-check.sh`
- `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md`
- `bash compass/tools/redcap-runtime-package-manifest.sh --check --npm-pack-dry-run`
- `bash compass/tools/redcap-package-publish-safety-check.sh`
- `bash compass/tools/redcap-public-package-surface.sh`
- `bash compass/tools/redcap-multi-session-acceptance.sh public-arsenal-claim-boundary-check`
- `bash compass/tools/redcap-multi-session-acceptance.sh shared-knowledge-remote-binding-check`
- `bash compass/tools/redcap-multi-session-acceptance.sh prism-acceptance-binding-required`

验证过程中抓到一个真实问题：新增 RASG 批次 manifest 一度进入 npm 候选包，导致公开包面检查失败。处理方式是把 `assets/references/rasg-*.json` 明确归为任务证据并排除出公开包候选范围。复验后包面检查通过。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|---|---|
| closeout receipt | 无 |
| 当前状态 | 已完成实现、审查和大部分验证，仍需最终 closeout runtime 生成 receipt |

### 5.4 完成等级（禁止混报）

| 完成层级 | 结论 |
|---|---|
| 已实现 | 是，redcap-arsenal 第二批公共条目已新增、提交并推送，RedCap 侧状态面已同步。 |
| 已自检 | 是，公共库、远端绑定、声明边界、公共蒸馏预检、包公开面和 targeted acceptance 已通过。 |
| 已独立验收 | 是，Kimi 与 Claude Code 均完成 targeted review，结论为 pass_with_nits、无 blocker。 |
| 已正式完成 | 否，仍待最终 closeout receipt。 |

## 六、遗留问题与下一步

本轮不覆盖以下事项：

- RASG-029：工程目录最终收敛。
- 正式 npm 发布、发布授权、版本号、registry 和 license 决策。
- full LLM-wiki、后台蒸馏 worker、RAG、GraphRAG 或向量库。
- 全部历史私有知识的大规模公开迁移。

下一步是完成 RASG-028 的最终回归和 closeout receipt，然后自动进入 RASG-029。

## 七、经验沉淀

### 7.1 问题源

只建立公共知识库机制，不等于公共知识库真的有内容。RedCap 曾经长期把规则、报告、绑定检查和计划当成“武器库已运转”的证据，这会造成能力假象。

### 7.2 解决方案

用小批次 Forge 扩容替代口头承诺：候选来源先受控，公共条目只新增不覆盖，隐私审查、重复审查、公开声明边界和远端绑定都必须一起完成。

### 7.3 Evolution Factory 候选处理

- 处理结论：no-promote。
- 理由：本轮产物已经直接晋升为 4 条 public arsenal entries，并有 manifest、远端绑定、棱镜结论和 claim boundary 作为证据；不需要再把同一完成态包装成新的普通候选。
- 后续触发：如果继续扩大公共武器库，应另开新的 Forge batch；如果建设 full LLM-wiki 或 RAG，再按长期演进专项立项。

### 7.4 最后效果

RedCap 现在可以证明公共武器库完成了一次真实增长：不是只有模板和规则，而是有 8 条当前可检索的公共条目、外部提交绑定和独立审查记录。

## 八、附录

关键证据：

- redcap-arsenal 提交：`95f0783dd6d304c340d3209a2ba44da0f187cbdf`
- 批次 manifest：`assets/references/rasg-028-forge-batch-public-arsenal-manifest.json`
- 棱镜运行：`prism/runs/20260528-rasg-028-forge-batch-public-arsenal/`
- 任务账本：`.dev-task.md`

关键边界：

- 不读取或发布私密原文。
- 不修改 identity 原文。
- 不执行正式发布。
- 不做不可恢复删除。
- 不把 RASG-028 冒充 RASG-029 或 release readiness 已完成。
