# 任务完成报告：Layer B 中插/续接任务意图确认硬门

**报告日期**：2026-05-10
**执行者**：Cap（Codex + Prism: Kimi / Claude Code）
**报告版本**：v1.1

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 已补上“继续/接下来/按计划推进”类任务的续接确认硬门，防止任务再次被错误接到上一条旧任务线上。
- 详情：这次问题的根源不是代码实现难，而是任务锚点没有被机器强制确认。现在只要任务原文带有续接意味，就必须写清续接哪条线、本轮只做什么、不做什么、是否替换旧任务线，以及对 Norven 应该怎么说明边界。这样后续再说“继续推进”，RedCap 不能跳过确认直接把任务塞进旧 closeout 或内部发现的支线里。

### 0.2 上一步完成的是

- 上一步完成的是：上一轮修好了 closeout receipt 和 pending closure 的状态一致性问题；本轮是在修更上游的“任务续接不要跑偏”问题。

### 0.3 下一步计划做的是

- 下一步计划做的是：提交本轮变更并生成正式 closeout receipt，然后回到 Norven 指定的第二步：补做“三分 RedCap 前进刻度表”相关结论的棱镜评审。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：先修续接不跑偏 -> 补三分法结论的棱镜评审 -> 再落地三分进度仪与棱镜使用场景优化。
- 当前所在位置：第一步“续接/中插任务意图确认硬门”已实现，targeted checks、full acceptance、spec-check 与 diagnose 均已通过；正在执行最终提交与 closeout receipt。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮没有发布、删除历史资产、许可证、凭据、公开仓库写入等需要 Norven 保留决策的动作；下一步可由 Cap 继续完成验证和收口。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> “了解，我建议优先级应该是这样的：
> 1. 完全修复“中插/续接任务意图确认”这个机制已经识别的缺口，毕竟现在我们正在经历中插/接续任务的事情
> 2. 回顾前面那段你的“是否固化三分法以及那段话中涉及的其他点的结论”，然后对这些结论和方案执行棱镜评审，因为当时识别出了“缺失棱镜调用”的问题，所以少了一次评审，导致你那段“结论与方案”还不能直接逐一落盘到任务树中。为了防止你回顾错误，我把你那段结论和方案的大纲列一下：RedCap 前进刻度表、为什么应该固化、怎么避免历史债务无限膨胀、应该归属公共资产还是 Norven 私有资产、怎么和现有机制配合、人类和 AI 的入口要分开、我问的 3 个小点分类
> 3. 逐一落地这一波多轮对话中沉淀的各个演进方案，例如三分、棱镜使用等等
>
> 你们认为这样合理吗？”

> “我有留意到你刚才执行的时间很短，似乎没有到5分钟，所以刚才你说Claude Code调用超时，我觉得有可能你给它的执行时间还不够，应该新增一个改动，给棱镜的超时设定要足达10分钟才合理。
>
> 接下来，你们按照你们的计划继续推进吧。”

### 1.2 触发背景

Norven 的原意是让 RedCap 接着做“续接/中插任务意图确认”与后续三分法治理，但上一轮 Cap 曾把“继续执行计划”错误落到 closeout 状态一致性修复上。这暴露出一个比单次 bug 更底层的问题：RedCap 需要在机器层面要求任务卡写清“这次继续的是哪条任务线”，而不能靠 Agent 自觉理解上下文。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | partial-with-explicit-defer |
| 原始意图 | 先修复中插/续接任务意图确认缺口，再补三分法相关结论的棱镜评审，最后落地演进方案；同时把棱镜等待时间调到足够合理。 |
| 已覆盖 | 本轮覆盖“续接/中插任务意图确认”硬门，以及真实外部 Agent 任务默认等待 600 秒。 |
| 未覆盖/延期 | 三分 RedCap 前进刻度表、公共/私有归属、人类/AI 入口分离、棱镜使用场景优化的完整落地，延期到后续任务。 |
| 用户可见边界 | 不能宣称三分进度仪或棱镜调度优化已经全部完成。 |
| 后续路径 | 本轮收口后，进入“三分法结论补棱镜评审”任务。 |

---

## 二、方案讨论

### 2.1 问题分析

已有的 `intent-coverage` 能防止把用户目标缩水成小目标后自证完成；已有的 `change-intake` 能防止执行期新增需求不入账。但这两者都没有专门回答“这次继续的是哪条线”。所以当用户说“继续/接下来/按计划推进”时，Agent 仍可能把话接到内部发现的旧任务，而不是用户刚刚确认的任务。

### 2.2 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---|---|---|
| Q1 | 在 `change-intake` 检查中加入独立的续接意图确认门，并让所有调用链都执行它 | 该脚本已被 PM Gate、diagnose、spec-check 和 closeout 链路复用，放在这里能覆盖启动、中途和收尾阶段。 | Prism + Cap |
| U1 | 真实 Prism / baton Agent 任务默认等待 600 秒，但 availability 健康探测仍保持轻量 | Claude Code 评审指出健康探测和真实评审任务不能混成一层；否则每次只是探测 CLI 都可能卡 10 分钟。 | Prism + Cap |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|---|---|---|
| `compass/tools/redcap-change-intake-check.py` | 修改 | 新增续接意图确认检查。 |
| `references/layerb-change-intake-policy.json` | 修改 | 新增续接触发词、必填字段、锚点来源与旧任务线判定策略。 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 增加续接确认与 600 秒真实任务等待的回归。 |
| `compass/tools/baton-delegate.sh` / `compass/tools/baton-launcher.sh` | 修改 | 默认真实外部 Agent 任务等待从 300 秒提升到 600 秒。 |
| `prism/README.md` / `prism/protocol.md` / `references/prism-provider-policy.json` | 修改 | 明确 availability 是轻量健康探测，不能等同于完整评审任务执行窗口。 |
| `references/file-lookup-dictionary.md` / `references/file-lookup-dictionary-policy.json` | 修改 | 同步索引说明。 |

### 3.2 技术实现要点

新门禁不是只看有没有中插账本。它会先检查原始输入是否包含“继续、接下来、按计划、把计划执行干净”等续接型表达；如果命中，就必须出现 `## 续接/中插任务意图确认`，并写清续接锚点、锚点来源、本轮执行范围、未执行范围、是否替换旧任务线、决策理由和用户可见边界。

棱镜评审指出“10 分钟”应当用于真实评审任务，而不是 CLI 健康探测。于是本轮没有把 availability 探测改成长等待，而是把 baton/外部 Agent 任务默认执行窗口提升到 600 秒，同时在 Prism 文档中明确两者边界。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|---|---|---|
| 续接意图确认 | `redcap-change-intake-check.py` | 当用户说“继续”时，RedCap 必须先说明继续哪条任务线，避免接错。 |
| availability 健康探测 | `prism-availability.py` | 快速确认某个 CLI 是否可用，不负责等待完整评审任务做完。 |
| baton 真实任务执行 | `baton-delegate.sh` / `baton-launcher.sh` | RedCap 真正把任务交给外部 Agent 执行的入口，默认等待已提升到 600 秒。 |

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|---|---|---|---|
| 1 | 无必须人工审核项 | 本轮不涉及 Norven 保留决策。 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|---|---|---|
| JSON / Python / Shell 语法 | `python3 -m json.tool ...` / `python3 -m py_compile ...` / `bash -n ...` | 通过 |
| 当前任务卡门禁 | `redcap-intent-coverage-check` / `redcap-change-intake-check` / `redcap-pm-gate-check` | 通过 |
| 续接确认回归 | `bash compass/tools/redcap-multi-session-acceptance.sh change-intake-check` | 通过 |
| Prism / baton timeout 回归 | `bash compass/tools/redcap-multi-session-acceptance.sh prism-availability` | 通过 |
| 字典一致性 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过 |
| 全量回归 | `bash compass/tools/redcap-multi-session-acceptance.sh all` | 通过 |
| spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD" <baseline>` | 通过 |
| diagnose | `bash compass/tools/redcap-diagnose.sh` | 通过 |

### 5.2 人工验证项（Cap 无法自动化验证的）

- 无。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|---|---|
| 执行承诺账本 | 待 closeout runtime 最终核对 |
| 棱镜验收 | 方案评审：Claude Code + Kimi 均有效；实现后复核：Kimi pass，Claude Code 600 秒 resource-limited timeout |
| closeout summary | 待本报告提交后由 closeout runtime 生成 |
| closeout receipt | 待本报告提交后由 closeout runtime 生成 |
| rescue audit | 无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|---|---|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是；Kimi 实现后复核通过，Claude Code 实现后复核 600 秒 resource-limited timeout，已按资源受限验收绑定 |
| 已正式完成 | 待提交后生成 receipt |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|---|---|---|
| 三分 RedCap 前进刻度表及其归属/入口设计 | 这是 Norven 明确排序里的第二步，需要先补棱镜评审再落地 | P0-next |
| 棱镜使用场景优化完整落地 | 属于第三步演进方案，不应混入本轮导致范围再次漂移 | P1 |

### 6.2 触发的新问题

本轮新增 L-159 后触发了历史资产迁移基线与冷归档索引过期，已同步更新；新增任务报告导致 active task-report inbox 超过阈值，已将一个无外部锚点引用的旧报告移入 `redcap-knowledge/task-reports/` 私有冷归档，避免继续扩大默认上下文暴露面。Claude Code 实现后复核 600 秒超时已作为 resource-limited 事实记录，不冒充通过。

### 6.3 推荐的下一步行动

1. 完成本轮 full validation 与 closeout receipt。
2. 启动“三分 RedCap 前进刻度表”结论补棱镜评审。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|---|---|---|
| L-159 | “继续”类指令必须先确认任务锚点 | 续接型用户输入不能只靠上下文理解，必须落成机器可检查的任务锚点确认。 |

### 7.2 流程改进建议

后续所有“继续/接下来/按计划推进”类任务都应先通过续接意图确认，再进入实现。棱镜或外部 Agent 调用要区分轻量健康探测和真实任务执行等待，避免把短探测失败误记成评审不可用。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|---|---|---|---|
| 无新增候选 | 本轮机制修复 | no-promote：已直接固化为检查器、policy、acceptance 与 lesson | `.dev-task.md`、`compass/tools/redcap-change-intake-check.py` |

---

## 八、附录

### 附录 A：Commits

```
待提交
```

### 附录 B：棱镜调用记录

| 模式 | 问题 | 结论 | 报告路径 |
|---|---|---|---|
| explore/review | 续接意图确认方案评审 | Claude Code 与 Kimi 均指出 blocker：续接门不能只依赖 U1；10 分钟不能套到健康探测 | `prism/runs/20260510-change-intent-continuity-gate/collect/` |
| implementation review | 实现后复核 | Kimi pass；Claude Code 600 秒 resource-limited timeout | `prism/runs/20260510-change-intent-continuity-gate/collect/` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- 棱镜协议：`prism/protocol.md`
- 中插/续接策略：`references/layerb-change-intake-policy.json`
