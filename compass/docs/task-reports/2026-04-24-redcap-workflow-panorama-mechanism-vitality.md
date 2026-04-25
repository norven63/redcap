# 任务完成报告：RedCap 全景图与机制活性硬化

**报告日期**：2026-04-24
**执行者**：Cap（Codex.app 主 Agent；Kimi CLI 参与只读独立审查）
**报告版本**：v1.1

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：Layer B 已补入 `PLANNING / PLANNING_REVIEW` 状态，书记官/机制活性检查已进入 `diagnose / spec-check / execution-guarantees`，RedCap 全景图 Markdown/HTML 已纳入 README 与 docs catalog，`sync-promises` 不再把已有 receipt 的 completed 状态打回 prepared；追加复验又修掉 docs catalog 隐藏文件污染、full acceptance 夹具老化，以及正式任务报告“只有模板、没有人话质量强门”的问题。
- 详情：本轮把“计划也要被审核”“优秀机制不能 zero-work”“全景学习材料要人话可读”“三表对账发现的状态漂移要回归覆盖”四条主线落成了脚本、文档、索引和验收用例；追加修复确保 `.DS_Store` 等隐藏杂物不会进入渐进披露索引，且 `redcap-multi-session-acceptance.sh all` 可完整跑通。

### 0.2 上一步完成的是

- 上一步完成的是：前一轮 Layer B FSM 重构已建立 closeout runtime、Prism acceptance、receipt 与 pending closure 的终态控制面。本轮是在那条主线之上，把计划审核、机制活性和全景学习面补回到工作流前中段。

### 0.3 下一步计划做的是

- 下一步计划做的是：无当前收尾动作；本轮 closeout receipt 已生成，后续只剩 Prism provider 稳定性等独立治理项，不能倒灌为本轮未完成。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：PM Gate 可见化 → `PLANNING` → `PLANNING_REVIEW` → 机制活性门 → 全景图按需披露 → 状态漂移回归 → 外部审查与 closeout。
- 当前所在位置：`planning-review-and-mechanism-vitality-hardening` 已实现、自检、Prism acceptance 与 closeout receipt 全部完成。

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 我认为PLANNING有必要独立存在，而且还需要再加一个“PLANNING审核”阶段。为什么这样说，因为有时候plan的制定可能就会出岔子，目前的兜底方案是如果你通过中断方式，把方案给我review，我可能会从人工角度去给你审核。但是人类已经无法胜任细致的plan流程评审，人类目前只能负责战略性的方向评审，所以最合理的应该是设立“PLANNING审核”阶段，让棱镜来负责这个工作。

> “书记官/底稿层不在 FSM 主链里，它是 FSM 的上游喂料层，触发规则还在 CONTRIBUTING.md 里“，我怎么感觉这么说的话，这2个功能运作几乎没什么保障，CONTRIBUTING.md的协议约束在目前的Redcap复杂度来看，几乎等同于0了。这是不是我为什么总觉它们好久没有工作过的原因？

> 是否可以出一个LayerB的工作流全景图？把涉及到的各个细节节点和任务流向，等等设计思路都涵盖进去？Codex.app有可以生成网页（类似Canvas）的能力吗？我希望同时产出md文件和网页（人类阅读友好）文件。

> 其实，除了“书记官/底稿层”外，还有好多好多机制都已经“zero work”了，比如，沉淀经验、沉淀Cap的灵魂等等，应该还有好几个连我都忘记了的优秀设计，都是这样的。需要给他们都补回来、加上runtime强门。

> LayerB的新机制、三表对账、lifecycle / closeout / receipt / pending closure 等术语需要人话解释；全景图材料不要仅局限于 LayerB，而是整个 RedCap，因为我要透过研究 RedCap 学习整个“AI Agent框架设计”的技术知识。

### 1.2 触发背景

前一轮 FSM 重构解决了终态 closeout，但用户继续指出：计划阶段、书记官、经验沉淀、人格沉淀和全局理解入口仍可能只剩自然语言规则。这暴露的核心问题是 RedCap 不能只在尾段强硬，前中段也必须有可见状态面和机器检查面。

## 二、方案讨论

### 2.1 问题分析

问题不是“再写一份说明文档”，而是把计划、底稿、经验、人格、全景学习面这些机制从自然语言约束提升为至少会被诊断链看见的 runtime 可见面。完全 100% 拦截仍受 Codex.app 等宿主 pre-reply veto 能力限制，但 RedCap 可以做到：新机制不再完全 zero-work，且状态漂移会在 `diagnose / spec-check` 中暴露。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| 计划审核 | A | 继续把 plan 当执行说明 | 改动小 | 仍会让作者自证 plan 正确 |
| 计划审核 | B | 增加 `PLANNING / PLANNING_REVIEW` 状态 | 可把计划质量独立验收 | 需要补 FSM、文档、保障清单 |
| 机制活性 | A | 只在 CONTRIBUTING.md 继续强调 | 简单 | 仍是 zero-work 风险 |
| 机制活性 | B | 新增 mechanism vitality check 并接入 diagnose/spec-check | 能被机器状态面看见 | 只能证明最低可见性，不能替代宿主 pre-reply veto |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| 计划审核 | B | 复杂任务的 plan 本身必须被审核，不能继续靠用户做细节审稿 | NORVEN_DECIDE / CAP_IMPLEMENT |
| 机制活性 | B | 先做到机制不再 zero-work，再逐步增强为更强 runtime gate | CAP_DECIDE |
| 全景图 | Markdown + HTML | 同时满足机器索引和人类学习阅读 | NORVEN_DECIDE / CAP_IMPLEMENT |

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `.dev-task.md` | 修改 | 重新锚定本轮真实任务，避免复用上一轮完成态 |
| `README.md` | 修改 | 增加 RedCap 全景图 Markdown/HTML 入口 |
| `compass/CONTRIBUTING.md` | 修改 | 补入 `PLANNING / PLANNING_REVIEW` 与 mechanism vitality check 说明 |
| `compass/tools/redcap-layerb-fsm.py` | 修改 | 从 active slice 派生 `PLANNING / PLANNING_REVIEW` 状态 |
| `compass/tools/redcap-layerb-fsm-check.sh` | 修改 | 将计划状态加入 FSM 契约检查 |
| `compass/tools/redcap-mechanism-vitality-check.py` | 新建 | 检查书记官、经验沉淀、灵魂锚点、计划审核和全景图的最低 runtime 可见性 |
| `compass/tools/redcap-mechanism-vitality-check.sh` | 新建 | mechanism vitality shell 入口 |
| `compass/tools/redcap-diagnose.sh` | 修改 | 接入 mechanism vitality check |
| `compass/tools/redcap-drift-check.sh` | 修改 | 让任务卡允许范围审计覆盖 untracked 文件，并新增显式 `reanchor` 模式刷新宿主控制面指纹 |
| `compass/tools/redcap-spec-check.sh` | 修改 | 接入 mechanism vitality check |
| `compass/tools/redcap-execution-guarantee-check.py` | 修改 | 将新保障 ID 纳入必需清单 |
| `references/execution-guarantees.json` | 修改 | 新增 `workflow-panorama-surface`、`scribe-runtime-vitality`、`planning-review-gate` |
| `references/runtime-memory-architecture.md` | 修改 | 补入 `PLANNING / PLANNING_REVIEW` 状态与转移 |
| `compass/docs/research/2026-04-24-redcap-workflow-panorama.md` | 新建 | RedCap 全景图 Markdown 版 |
| `compass/docs/research/2026-04-24-redcap-workflow-panorama.html` | 新建 | RedCap 全景图 HTML 版 |
| `compass/docs/catalog.json` | 修改 | 将全景图纳入按需披露索引 |
| `compass/knowledge/lessons.md` | 修改 | 沉淀当前任务卡重锚定与机制活性经验 |
| `compass/tools/redcap-layerb-closeout-runtime.py` | 修改 | 修复 `sync-promises` 降级 completed 的状态漂移 |
| `compass/tools/redcap-layerb-closeout-runtime.py` | 修改 | 让 `complete` 在调用 `on-complete` / `session-end` 前确保 runtime binding，并把 binding/env 传入子流程 |
| `compass/tools/redcap-layerb-closeout-runtime-bridge.sh` | 修改 | 新增 `ensure-runtime-binding`，供 Python runtime 复用 shell runtime claim 能力 |
| `compass/tools/redcap-layerB-session-end.sh` | 修改 | 允许后续成功的 commit-proof gate 清掉旧 pending closure 中的 `commit-proof` 红线 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 新增状态保持与 session-end binding acceptance 用例 |
| `compass/tools/redcap-docs-catalog.py` | 修改 | docs catalog 排除隐藏路径和非文档后缀，防止 `.DS_Store` 等杂物进入索引 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 修复 full acceptance 暴露的旧入口、旧断言、fixture 漏依赖和 runtime 污染问题 |
| `compass/tools/redcap-human-output-quality-check.py` | 新建 | 对正式任务报告执行人话质量审计，检查四句摘要、术语对照、完成等级和 receipt 证据是否自洽 |
| `compass/tools/redcap-human-output-quality-check.sh` | 新建 | 人话质量审计 shell 入口，供 task report、diagnose 与 acceptance 复用 |
| `compass/tools/redcap-task-report-check.sh` | 修改 | 在已有报告模板审计后调用人话质量强门，避免只靠章节标题通过 |
| `references/task-report-template.md` | 修改 | 明确任务报告会被人话质量检查器审计 |

### 3.2 技术实现要点

Layer B FSM 现在把计划阶段拆成两个状态：`PLANNING` 负责方案、切片、承诺和验证路径，`PLANNING_REVIEW` 负责让棱镜审核计划本身。机制活性检查不是假装 100% 物理强门，而是作为诊断门：只要书记官、经验、人格、计划审核、全景图这些机制从关键入口消失，`diagnose / spec-check` 就会失败或暴露漂移。

全景材料采用 Markdown + HTML 双形态。Markdown 适合 catalog、搜索和版本控制；HTML 适合人类快速浏览。它们都通过 `compass/docs/catalog.json` 以 `read-on-demand-after-catalog` 策略暴露，不会成为新会话自动注入的大文件。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| `PLANNING` | `redcap-layerb-fsm.py` / `runtime-memory-architecture.md` | 方案制定阶段，不再把 plan 当普通说明 |
| `PLANNING_REVIEW` | `redcap-layerb-fsm.py` / Prism 验收 | 计划审核阶段，复杂任务不让作者自审 plan |
| mechanism vitality | `redcap-mechanism-vitality-check.py` | 检查优秀机制是否仍在诊断链里有可见面 |
| 三表对账 | `closeout-cap.sh status` + `redcap-current-status.sh` + `redcap-diagnose.sh` | 用三个状态视角互相校验，抓内部状态漂移 |
| receipt | closeout runtime receipts | 完工收据，证明任务不是口头完成 |
| pending closure | pending-closure state | 尚未清掉的收尾红线或 blocker |
| human output quality | `redcap-human-output-quality-check.sh` | 正式任务报告的人话质量强门，防止章节齐全但摘要、术语、完成等级和 receipt 证据互相打架 |

### 3.3 关联变更

本轮触发了 docs catalog 重新生成；同时发现上一轮 `sync-promises` 会把已完成 runtime state 回退到 prepared，因此补入状态保持修复和 acceptance 回归。正式 closeout 复验时又抓到 `complete -> session-end` 没有继承 runtime binding，会把真实 session-end 打进 `missing-runtime-claim` 降级分支；已把 binding 初始化收进 closeout runtime，并新增回归防复发。

追加复验时发现 `compass/docs/.DS_Store` 会被 docs catalog 当作普通文档索引，形成新的 token 污染入口；同时 full acceptance 因多处历史夹具老化无法跑到底。已将 catalog 生成器改为只索引明确文档后缀并排除隐藏路径，并把 acceptance 中仍指向旧 `on-complete` 入口、旧 task report 断言、缺失脚本依赖、共享 runtime 污染和真实任务账本耦合的 case 改为自包含 fixture。

再追加的人话质量加固把“汇报质量”从纯自然语言要求推进到正式任务报告强门：`redcap-human-output-quality-check.sh` 会拒绝占位符摘要、空术语对照、缺少 completion 等级、以及“已经正式完成却还说下一步生成 receipt”的陈旧报告。即时对话仍受宿主实时拦截能力限制，因此只诚实声明为 host-limited，不冒充 100% 物理强保障。

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 全景图表达是否符合 Norven 的学习目标 | 机器只能校验结构和入口，不能判断“人话程度”是否完全满足用户学习体验 | P1 |

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 机制活性 | `bash compass/tools/redcap-mechanism-vitality-check.sh` | 通过 |
| Layer B FSM | `bash compass/tools/redcap-layerb-fsm-check.sh` | 通过 |
| 执行保障 | `bash compass/tools/redcap-execution-guarantee-check.sh` | 通过 |
| 总规范检查 | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| 总诊断 | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 通过；显示 lifecycle-state=CLOSED、receipt=present、promise=12/12 |
| full acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh all` | 通过；完整套件最终返回 `ACCEPTANCE_OK` |
| 人话质量强门 | `bash compass/tools/redcap-human-output-quality-check.sh --task-file .dev-task.md` | 通过 |
| acceptance 回归 | `bash compass/tools/redcap-multi-session-acceptance.sh human-output-quality-check` | 通过；会拒绝“已正式完成但下一步仍写生成 receipt”的陈旧报告 |
| docs catalog | `bash compass/tools/redcap-docs-catalog.sh check` | 通过；`.DS_Store` 不再进入 catalog |
| acceptance 回归 | `bash compass/tools/redcap-multi-session-acceptance.sh layerb-closeout-runtime-sync-preserves-completed-state` | 通过 |
| acceptance 回归 | `bash compass/tools/redcap-multi-session-acceptance.sh layerb-closeout-runtime-attaches-session-end-binding` | 通过 |
| acceptance 回归 | `bash compass/tools/redcap-multi-session-acceptance.sh layerb-closeout-runtime-session-end-failure-writes-pending` | 通过 |
| FSM 状态派生 | Python 直接调用 `derive_state()` 检查 planning / plan-review | 通过 |
| diff 空白检查 | `git diff --check` | 通过 |
| 任务卡重锚定 | `bash compass/tools/redcap-drift-check.sh reanchor codex .dev-task.md` | 通过 |
| 任务卡范围审计 | `bash compass/tools/redcap-drift-check.sh workspace codex .dev-task.md` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] Norven 可打开全景图 Markdown/HTML，判断“人话解释”和学习材料是否符合预期。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 12/12 已清 |
| 棱镜验收 | 通过；`review-closeout-runtime-binding-20260424` 已绑定当前任务，Kimi + Copilot 两家族均无 blocker |
| closeout summary | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/summaries/redcap-workflow-panorama-mechanism-vitality-cc725ca8e175f72f9dfff94639e844e130283cb0ea8826fdf82a3e2b98defaad.md` |
| closeout receipt | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/redcap-workflow-panorama-mechanism-vitality-cc725ca8e175f72f9dfff94639e844e130283cb0ea8826fdf82a3e2b98defaad.json` |
| pending closure | 无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是；Kimi + Copilot 两家族通过 |
| 已正式完成 | 是；closeout runtime 返回 `status=completed`，`diagnose` 显示 `CLOSED` |

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 无当前 tranche 级 blocker | 当前任务的实现、自检、Prism acceptance、commit、receipt 均已完成 | - |

### 6.2 触发的新问题

当前 Prism provider 池仍不稳定，说明“棱镜验收作为默认验收人”的理念已经清楚，但 provider 运行层还需要单独硬化；本轮最终使用 Kimi + Copilot 形成可接受 quorum，Gemini/Claude 超时只记录为 provider 稳定性治理项，不阻塞当前任务。

### 6.3 推荐的下一步行动

1. Prism provider health / timeout / fallback 运行层可作为后续独立治理任务处理。
2. 老旧资产 authority / archive / translate 治理可作为后续独立治理任务处理。

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-111 | 旧 receipt 不能覆盖新任务 | `.dev-task.md` 必须随当前真实任务重新锚定，否则状态面会把上一轮完成态误当成本轮完成态 |
| L-112 | 机制活性要有诊断面 | 自然语言协议不足以防止 zero-work；至少要让机制进入 `diagnose / spec-check` |
| L-113 | 人话质量强门要防误伤 | 把软规范变成机器强门时，必须先剥离代码/Markdown/JSON 等合法结构，避免粗暴正则制造新 blocker |

### 7.2 流程改进建议

将 Prism provider 稳定性从“遇到审查时临时嗅探”升级为独立 runtime 能力，否则默认棱镜验收会在 provider 卡住时变成新的瓶颈。

## 八、附录

### 附录 A：Commits

```text
f8aefb4 feat: 强化 RedCap 全景图与机制活性门禁
9312462 fix: 允许 session-end 清理 commit-proof 红线
2f9a8c9 fix: 修复 closeout runtime 的 session-end 绑定
9e5b487 fix: 修复文档索引与验收夹具老化
本报告最终状态同步提交见当前 git HEAD
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| Kimi CLI 只读审查 | closeout runtime binding 修复是否有阻塞 | 未发现阻塞；提示 PID fallback 为低风险 | `prism/runs/review-closeout-runtime-binding-20260424/collect/kimi_review/parsed.json` |
| Copilot CLI 只读审查 | closeout runtime binding 修复是否有阻塞 | 未发现阻塞 | `prism/runs/review-closeout-runtime-binding-20260424/collect/copilot_review/parsed.json` |
| Kimi / Copilot 历史审查 | 全景图、机制活性、task-card reanchor | 前序 run 已通过，后续 binding 修复另开 run 复审 | `prism/runs/review-workflow-panorama-mechanism-vitality-20260424/collect/*_review/parsed.json` |
| Gemini / Claude | 同上 | 超时/无输出，已记录降级 | `prism/runs/review-workflow-panorama-mechanism-vitality-20260424/collect/*_review/meta.json` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- 全景图 Markdown：`compass/docs/research/2026-04-24-redcap-workflow-panorama.md`
- 全景图 HTML：`compass/docs/research/2026-04-24-redcap-workflow-panorama.html`
- 机制活性检查：`compass/tools/redcap-mechanism-vitality-check.py`
