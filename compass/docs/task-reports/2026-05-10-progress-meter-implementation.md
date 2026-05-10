# 任务完成报告：RedCap 前进刻度表与棱镜使用边界落地

**报告日期**：2026-05-10
**执行者**：Cap（Codex + Prism: Kimi / Claude Code）
**报告版本**：v1.2

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 已有一个可执行的“前进刻度表”，能把历史债务坏味、当前专注任务集、长期演进专项合成一张人类可读的全景视图。
- 关键结论：它不是新账本，只是聚合器。真正的事实仍来自 `.dev-task.md`、任务报告、backlog、receipt、治理债务表、生命周期表和 Evolution candidates。

### 0.2 上一步完成的是

- 上一步完成的是：三分法结论已经补做 Kimi 与 Claude Code 的棱镜评审，两个模型族均通过，无 blocker。

### 0.3 下一步计划做的是

- 下一步计划做的是：当前任务已经生成 closeout receipt；若继续推进，应回到父任务全景图，选择后续长期演进专项或正式发布专项，而不是继续停留在本轮实现。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：续接锚点不跑偏 -> 三分法结论补棱镜评审 -> 三分进度仪与棱镜使用边界落地 -> closeout receipt 收口。
- 当前所在位置：第三步“落地实现”已完成，提交、索引、回归、clean workspace E2E 与 closeout receipt 均已收口。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮不涉及 npm 发布、凭据、许可证、公共库大迁移、历史资产物理删除或不可逆操作。

---

## 一、需求背景

Norven 希望 RedCap 后续迭代能有一个稳定的“前进刻度表”，每次都能清楚回答：历史债务还有什么、当前主线推进到哪里、长期演进专项有哪些。同时，棱镜调用不能再因为超时设置过短而误判失败，真实评审任务应有足够等待时间。

本轮目标是把已经评审通过的三分法真正落地成可执行机制，而不是停留在报告或口头约定里。

---

## 二、方案讨论

### 2.1 本轮采用的方案

本轮采用“只读聚合器”方案：前进刻度表只读取既有真相源，不写入新的任务事实，也不替代任何账本。人类默认看到短摘要；AI 和检查脚本可以读取 JSON 输出，继续追溯到原始来源。

### 2.2 棱镜超时边界

真实棱镜评审任务默认保留 600 秒等待时间，避免 Claude Code / Kimi 在复杂评审里被过早判定为超时。与此同时，availability probe 仍保持轻量短探测，不能继承 600 秒，否则健康嗅探会变成时间黑洞。

### 2.3 Norven 关切的逐项结论

| 问题 | 本轮结论 |
|---|---|
| 为什么要固化前进刻度表 | 因为 RedCap 的任务事实散落在任务卡、报告、receipt、backlog 和治理表里；如果没有稳定总览，人类和 Agent 都容易只看到局部，误以为“某个子任务完成”等于“父任务完成”。 |
| 如何避免历史债务无限膨胀 | 前进刻度表只展示聚合后的数量、状态和少量代表项；债务本体仍按生命周期处理为 open / deferred / archived / blocked，不把每个历史碎片复制进新视图。 |
| 公共资产还是 Norven 私有资产 | 机制、策略、脚本和术语解释属于 RedCap 公共资产；Norven 私有证据、个人上下文、未脱敏经验和本地运行痕迹不能自动进入公共 arsenal。 |
| 怎么和现有机制配合 | 它读取现有真相源，并接入 current-status、diagnose、spec-check、acceptance 和文件查阅字典；它不替代 `.dev-task.md`、receipt、Prism acceptance 或 backlog。 |
| 人类入口和 AI 入口如何分开 | 人类默认看“当前完成什么、下一步是什么、是否需要人工介入”；AI 和检查脚本读取 JSON、来源映射和计数，用于追溯与门禁审计。 |
| 三个小点如何分类 | “公共 arsenal 大迁移”是长期演进专项；“历史资产物理删除”是历史债务治理但属于破坏性动作，不能默认执行；“Codex.app 交互式 hook 100% 证明”是长期演进专项兼宿主能力边界验证。 |

---

## 三、落地结果

| 能力 | 结果 |
|---|---|
| 前进刻度表策略 | 已落地，明确三类视图、来源映射、禁止竞争真相源和生命周期边界。 |
| 人类可读入口 | 已落地，输出整体任务全景图、当前位置、已完成、下一步和是否需要人工介入。 |
| 机器可读入口 | 已落地，提供 JSON 输出，保留桶、来源映射、棱镜边界和计数。 |
| current-status 集成 | 已落地，状态面现在会显示“RedCap 前进刻度表”。 |
| diagnose / spec-check 集成 | 已落地，进度仪检查失败会阻断治理检查。 |
| 文件查阅字典 | 已更新，后续 Agent 能按需定位相关文件，不需要全文乱扫。 |
| 棱镜使用边界 | 已固化真实任务 600 秒、轻量探测短超时、Copilot 仅兜底的规则。 |

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|---|---|---|
| 前进刻度表 | `redcap-progress-meter` | RedCap 的“现在在哪儿”总览，方便人和 AI 不再只看一堆散文件。 |
| 聚合视图 | `redcap-progress-meter-policy` 的 `aggregate-only` | 只总结现有事实，不自己发明事实。 |
| 历史债务坏味 | 架构坏味 backlog、治理债务表、生命周期表 | 以前遗留下来的结构问题、过期资产或需要治理的设计债。 |
| 当前专注任务集 | `.dev-task.md`、任务报告、closeout runtime、framework backlog | 本轮真正正在推进和需要收口的任务范围。 |
| 长期演进专项 | Evolution candidates、full LLM-wiki、arsenal/Forge 相关策略 | 有价值但不能抢占当前任务的未来增强方向。 |
| availability probe | Prism 可用性轻量探测 | 只确认某个 Agent 大致可用，不应该等 10 分钟。 |
| real Prism task | 棱镜真实评审任务 | 真正让 Kimi / Claude Code 阅读文件并给结论的任务，应允许最多 10 分钟。 |

---

## 四、人工审核要点

- 本轮可以声明“前进刻度表机制已落地并通过回归”，不能声明“所有历史债务或长期演进专项都完成了”。
- 本轮没有迁移公共 arsenal 实质知识，也没有删除历史资产。
- 本轮没有调用 Copilot；实现评审由 Kimi 与 Claude Code 完成。
- 真实 Prism 任务使用 600 秒边界；availability probe 继续保持轻量。

---

## 五、验证结果

| 验证项 | 结果 |
|---|---|
| `redcap-progress-meter-check` | 通过 |
| `progress-meter-check` acceptance | 通过 |
| `current-status-overview` acceptance | 通过 |
| Prism acceptance binding | 通过，Kimi + Claude Code，2 个模型族 |
| Kimi 实现评审 | pass，无 blocker；两个低风险一致性建议已修复 |
| Claude Code 实现评审 | pass，无 blocker；两个低风险一致性建议已修复 |

### 5.3 closeout runtime / receipt

| 项目 | 值 |
|---|---|
| closeout receipt | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/redcap-progress-meter-implementation-c8cbb9d86a691962f9abd8f01529d6a2633b8d426e7b3a69a1dfe73f2926534e.json` |
| closeout status | completed |
| promise ledger | 4/4 completed |
| acceptance | Prism acceptance pass，Kimi + Claude Code，2 个模型族 |

### 5.4 完成等级（禁止混报）

| 等级 | 本轮结论 |
|---|---|
| 已实现 | 是，策略、脚本、状态展示和门禁均已落地。 |
| 已自检 | 是，进度仪检查、acceptance 与 current-status 集成都已通过。 |
| 已独立验收 | 是，Kimi 与 Claude Code 均完成实现评审并给出 pass。 |
| 已正式完成 | 是，closeout receipt 已生成，承诺账本 4/4 完成，Prism acceptance 为 pass。 |

---

## 六、遗留问题与下一步

本轮没有阻塞项。后续不应把前进刻度表扩大成新账本；如果未来要让 closeout runtime 直接消费进度仪 JSON，应另立任务，并继续保持“只读聚合”边界。

长期延期项仍按原分类留在任务体系中：公共 arsenal 大迁移、历史资产物理删除、full LLM-wiki、Codex.app 宿主级 hook 证明，都不能混入本轮完成声明。

---

## 七、经验沉淀

### 7.1 新增 Lesson

| 编号 | 标题 | 核心内容 |
|---|---|---|
| L-161 | 声明的聚合源必须真的被读取，否则就是假覆盖 | 如果政策文件说某个来源被纳入治理视图，渲染器和检查器就必须能证明它被读取；否则后续维护者会误以为该来源已经受控。 |

### 7.2 流程改进建议

后续新增“聚合视图”类能力时，应同时检查三个方向：政策声明的来源、代码实际读取的来源、检查器能证明的来源。三者不一致时，即使功能展示正常，也不能算完全收口。

### 7.3 Evolution Factory 候选处理

no-promote：本轮没有新增 Evolution candidate pool 条目；本轮沉淀的是执行经验 L-161，属于当前治理实现的直接 lesson，不需要升级为长期演进候选。

---

## 八、附录

### 附录 A：棱镜调用记录

| Agent | 结论 | 证据 |
|---|---|---|
| Kimi | pass，无 blocker | `prism/runs/20260510-progress-meter-implementation/collect/kimi-reviewer.txt` |
| Claude Code | pass，无 blocker | `prism/runs/20260510-progress-meter-implementation/collect/claude-reviewer.json` |

### 附录 B：Commits

本报告不把手写 commit 清单作为最终真相源；最终完成头以 closeout receipt 的 `current_head` 和 `git log` 为准。关键提交包括：

```
3f78ac2 feat(redcap): 落地前进刻度表聚合视图
e221d26 test(redcap): 刷新前进刻度表干净工作区证据
7ce7818 fix(redcap): 修正前进刻度表收口后状态
92c6e55 test(redcap): 刷新前进刻度表收口证据
```

### 附录 C：Closeout Receipt

```
/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/redcap-progress-meter-implementation-c8cbb9d86a691962f9abd8f01529d6a2633b8d426e7b3a69a1dfe73f2926534e.json
```
