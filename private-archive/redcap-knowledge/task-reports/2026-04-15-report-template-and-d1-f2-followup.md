# 任务完成报告：汇报模板升级与 D1/F2 后续收口

**报告日期**：2026-04-15
**执行者**：Cap（Copilot CLI / GPT-5.4）
**报告版本**：v1.0

---

## 零、先看懂当前局面

> **这四段会被状态汇报、收尾摘要与飞书通知优先抽取。** 即使完整报告很长，这里也必须让 Norven 在 15-30 秒内先看懂：现在已经做到哪里、上一刀是什么、下一刀是什么、整条路线卡在哪个位置。

### 0.1 当前已完成

- 当前已完成：对外汇报入口已经统一成“四句先看懂”，并把 spec 生命周期治理从“有登记”推进到了“有 policy、有 gate、有 acceptance”。
- 详情：`references/task-report-template.md`、`compass/tools/redcap-task-report-check.sh`、`compass/tools/redcap-notify-format.sh` 与相关规范文档现在统一使用“当前已完成 / 上一步 / 下一步 / 整体脉络与当前位置”作为固定入口；`references/spec-lifecycle-policy.json`、`references/spec-contribution-standard.md`、`compass/tools/redcap-spec-check.sh` 与新增 acceptance 已把 spec 的目录归属、状态、role、summary、`replaced_by` 关系与 archive 规则补成可执行门。为避免后续回归，本轮还补上了 `replaced_by` 循环检测、host workboard 的动态 backlog 锚点，以及旧模板报告的同步迁移。

### 0.2 上一步完成的是

- 上一步完成的是：上一刀已经把 backlog 从“单份说明文档”升级成“机器权威 + 人类说明”的第一层机制，并落了第一版 spec registry 与 `cli_console.md` 覆盖式镜像 helper；这一轮是在那个基础上继续处理“怎么让人先看懂”和“怎么把 spec 规则真正接进 gate”。

### 0.3 下一步计划做的是

- 下一步计划做的是：继续 backlog 当前下一焦点 `F2 规范到 gate 的翻译链`，把 hook / lesson / contract / 状态机等治理规范继续翻译成可执行门；其后再推进 `A3 三轨评审门` 与 `F3 治理硬化`。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：阶段 0 路线机制化 → 阶段 1 权威核心与连续性加固 → 阶段 2 Session / Resume 主链收口 → 阶段 3 治理可执行化 → 阶段 4 宿主体验与诚实降级 → 阶段 5 信息架构与运行时收敛。
- 当前所在位置：阶段 3 的 D1 已收口、当前长期路线 live focus 已切到 F2；本轮任务切片 `report-template-and-d1-f2-followup` 已完成，`.dev-task.md` 已回到 `task-complete`。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 能否把汇报模版改成“当前已完成xxx，详情为xxxx”，“上一步完成的是xxxx”，“下一步计划做的是xxxx”，“整体计划脉络图是xxxx，当前所在位置在xxxx”？然后，继续推进后续任务吧

### 1.2 触发背景

上一轮 backlog 机制第一层已经落地，但用户明确指出：如果汇报仍然靠执行者视角组织，人类很难快速接管评审；同时，backlog 既然已经变成正式机制，就不能停在“设计好了”，而是要继续把后续阶段里真实未完成的部分往前推。  
因此，本轮被收敛成两条必须并行推进的主线：第一条是把“说人话 + 四句先看懂”补成模板、检查器和摘要链里的硬规则；第二条是承接 backlog 当前最合理的下一刀，也就是 D1 / F2 对应的 spec 生命周期门与规范到 gate 的翻译链。

---

## 二、方案讨论

### 2.1 问题分析

这轮不是简单改一份 markdown 模板。  
如果只改 `references/task-report-template.md`，而不改 `redcap-task-report-check.sh`、`redcap-notify-format.sh`、`CONTRIBUTING.md`、`SKILL.md` 和 `ARCHITECTURE.md`，那就会出现“文档写着要这样说，但机器检查和收尾摘要还是旧口径”的断链。

spec 生命周期治理也类似。  
上一轮只有 spec registry，说明“有哪些 spec 应该被登记”；但要把 D1 真正收口，还必须继续补“什么状态能放在哪个目录、哪些字段合法、superseded 何时必须指向替代项、archive 何时合法”这些机器能执行的规则。否则 registry 只是名册，不是真正的 gate。

最后，code-review 又暴露了两个收口问题：一个是旧的未归档报告还停留在旧模板，另一个是 `replaced_by` 只做了单层检查，没有拦住 A→B→A 这种替代环。  
这两个问题如果不补，前者会在 task-report gate 爆炸，后者会把未来任何“追踪最新 spec”一类逻辑埋成隐患。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q15 | 选项 A | 只改任务报告模板文件 | 改动最少 | 检查脚本、通知摘要和规范文案仍会断链 |
| Q15 | 选项 B | 模板、检查器、摘要链、规范文案一起改 | 对外口径真正统一，能执行 | 需要联动多处文件 |
| Q16 | 选项 A | 先大范围推进 F2，把 hook / lesson / contract 全部一起做 | 一次推进面广 | 本轮范围过大，容易失焦 |
| Q16 | 选项 B | 先把 D1 的 spec 生命周期门补完整，再把 F2 推进到“policy + gate”第二层 | 风险更可控，能形成完整闭环 | F2 其余部分要留到下一刀 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q15 | 选项 B | 用户要的是“固定可扫读入口”，这只有把模板、检查器、通知摘要和规范文案一起改掉才算真正生效 | CAP_DECIDE |
| Q16 | 选项 B | 当前 backlog live focus 是 F2，但 D1 与 F2 在 spec 维度紧耦合；先把 spec 生命周期门补成闭环，再往更广泛治理资产扩展，更符合“先补可执行门，再谈更大范围治理” | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `references/task-report-template.md` | 修改 | 把报告入口改成“四句先看懂”结构 |
| `compass/tools/redcap-task-report-check.sh` | 修改 | 把任务报告硬校验改为检查新四段摘要 |
| `compass/tools/redcap-notify-format.sh` | 修改 | 收尾摘要与通知优先抽取新四段，同时保留旧报告 fallback |
| `compass/CONTRIBUTING.md` | 修改 | 把新汇报模板与说人话约束写进权威规范 |
| `SKILL.md` | 修改 | 把新汇报入口结构写进主技能约束 |
| `ARCHITECTURE.md` | 修改 | 说明模板链、spec lifecycle gate 与控制面的关系 |
| `references/agent-constraints.md` | 修改 | 子 Agent 级约束同步到新汇报口径 |
| `compass/knowledge/lessons.md` | 修改 | 新增“四句先看懂”经验与 acceptance 前提污染经验 |
| `references/spec-lifecycle-policy.json` | 新建 | 以机器可读策略定义 spec roots / statuses / roles / summary / replacement 规则 |
| `references/spec-contribution-standard.md` | 新建 | 给人解释 spec 应该放哪里、怎么命名、哪些字段必填 |
| `references/spec-registry.json` | 新建/补齐 | 为现有 spec 提供统一登记清单 |
| `compass/tools/redcap-spec-check.sh` | 新建 | 把 spec 生命周期规则落实为可执行检查器，并补上 replacement cycle 检测 |
| `compass/docs/index.yaml` | 修改 | 接入 archive root、spec lifecycle policy 与 contribution standard |
| `compass/docs/archive/specs/.gitkeep` | 新建 | 为 superseded spec 预留 archive 物理根目录 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 新增 spec lifecycle 相关 acceptance，并修正 backlog 锚点和无-claim 前提污染问题 |
| `references/backlogs/framework-upgrade.json` | 修改 | 将 D1 标记为 done，并把 current focus 切到 F2 |
| `compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md` | 修改 | 通过 backlog sync 刷新人类说明文档的自动摘要区块 |
| `compass/knowledge/governance-debt-register.md` | 修改 | 把 GD-005 标记为完成，维持 GD-007 继续推进 |
| `compass/docs/task-reports/2026-04-14-backlog-mechanism-and-spec-governance.md` | 修改 | 将旧结构报告升级到新模板，避免 task-report gate 断链 |
| `compass/docs/task-reports/2026-04-15-report-template-and-d1-f2-followup.md` | 新建 | 归档本轮 follow-up 的终局报告 |

### 3.2 技术实现要点

第一，汇报模板链是按“模板 → 检查器 → 摘要器 → 规范文案”整条链一起改的。  
`references/task-report-template.md` 只负责“应该怎么写”，`compass/tools/redcap-task-report-check.sh` 负责“没按这个结构写就不让过”，`compass/tools/redcap-notify-format.sh` 负责“收尾消息和通知也按同一口径抽取”，而 `CONTRIBUTING.md` / `SKILL.md` / `ARCHITECTURE.md` 则负责把这件事从一次性偏好升成长期规则。

第二，spec 生命周期门被拆成“机器策略 + 人类说明 + 执行 gate”三层。  
`references/spec-lifecycle-policy.json` 负责放机器要判定的硬规则，`references/spec-contribution-standard.md` 负责给人类解释这些规则，`compass/tools/redcap-spec-check.sh` 负责真正执行。这样既避免只写文档没人管，也避免只写脚本没人看得懂。

第三，本轮把一个容易漏掉的逻辑洞一并补上了：`replaced_by` 的循环检测。  
以前只检查“不能指向自己”和“目标必须存在”，现在会沿着替代链往下走，只要出现 A→B→A 或更长的回环，就会直接报错，避免以后有人沿链追踪“最新 spec”时陷入死循环。

第四，acceptance 也补了两层收口。  
一层是业务层：新增 superseded 归档、`replaced_by` 必填、invalid role、replacement cycle 等用例；另一层是测试自身的稳态：`host-workboard-backlog-anchor` 不再写死 D1，而是动态读取 `.dev-task.md` 当前 `backlog_item`，`report-register-requires-claim` 则在 case 内主动清 runtime context，避免被前序 case 的 host pid 污染。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| “四句先看懂” | `references/task-report-template.md`、`compass/tools/redcap-task-report-check.sh`、`compass/tools/redcap-notify-format.sh` | 指所有面向 Norven 的汇报开头都先给出“现在做完了什么、上一刀是什么、下一刀是什么、整条路线到哪了”这四句稳定入口 |
| D1 | `references/backlogs/framework-upgrade.json` 中的 `D1` | 指“spec 生命周期权威收紧”，也就是把 spec 该放哪、何时归档、怎么替代这些规则补成可执行门 |
| F2 | `references/backlogs/framework-upgrade.json` 中的 `F2` | 指“规范到 gate 的翻译链”，也就是把原本写在文档里的治理规范，继续一条条翻译成脚本与检查器能执行的门禁 |
| spec-check | `compass/tools/redcap-spec-check.sh` | 这是专门检查 spec registry 和 spec 生命周期规则的脚本，不是通用 lint，它负责判定当前仓库里的 spec 是否满足 D1 的硬规则 |
| backlog 机制 | `references/backlogs/framework-upgrade.json` + `compass/tools/redcap-backlog-check.sh` + `compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md` | 指长期路线不再只靠一篇说明文档记忆，而是有机器可读权威、自动同步的人类说明和检查脚本三件套 |

### 3.3 关联变更

为了让这轮改动真正能落地，本轮还联动更新了 `README.md`、`references/governance-review-checklist.md`、`compass/docs/index.yaml`、`compass/knowledge/governance-debt-register.md` 等文件，把“spec lifecycle policy / contribution standard / spec-check / backlog current focus”的关系写进权威说明与治理账本。  
另外，旧的 `2026-04-14-backlog-mechanism-and-spec-governance.md` 也被一起迁移到新模板，避免“模板和检查器已经升级，但工作区里正准备归档的报告还是旧结构”这种断链。

---

## 四、人工审核要点

> ⚠️ 以下是 Norven 需要重点确认的内容，其他部分 Cap 已自行验证。

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 无必须人工裁决项；若要抽查，建议优先看本报告的“零、先看懂当前局面”与 `compass/tools/redcap-spec-check.sh` / `compass/tools/redcap-multi-session-acceptance.sh` 的对应实现 | 本轮改动全部发生在 repo-owned 边界内，不依赖外部系统、外包 skill 改造或人工操作 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 脚本语法检查 | `bash -n compass/tools/redcap-spec-check.sh compass/tools/redcap-notify-format.sh compass/tools/redcap-task-report-check.sh compass/tools/redcap-multi-session-acceptance.sh` | ✅ |
| backlog 权威检查 | `bash compass/tools/redcap-backlog-check.sh strict .dev-task.md` | ✅ |
| spec 生命周期检查 | `bash compass/tools/redcap-spec-check.sh "$PWD"` | ✅ |
| 定向 acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh host-workboard-backlog-anchor && bash compass/tools/redcap-multi-session-acceptance.sh spec-check-rejects-replacement-cycle && bash compass/tools/redcap-multi-session-acceptance.sh report-register-requires-claim` | ✅ |
| 全量 acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh all` | ✅ |
| 独立代码审查 | `background agent: followup-review` | ✅ |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [x] 无必须人工验证项；本轮未依赖宿主侧人工操作、外部服务响应或用户手动执行步骤。

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| hook / lesson / contract / 状态机等更广范围的“规范到 gate”翻译仍未完成 | 这属于 F2 / A3 / F3 的后续 tranche，不是本轮 D1 收口所能一次吃完的范围 | P1 |
| 对话实时输出本身仍缺 repo 内可机械校验的硬门 | 对话层属于宿主运行面，不完全落在 repo-owned surface 内；当前已经把 repo 内报告、模板、摘要、规范全部补成硬规则，但聊天窗口本身还不能只靠仓库脚本强制 | P2 |

### 6.2 触发的新问题

本轮执行中确实挖出了两个真实问题：旧模板报告尚未迁移、`replaced_by` 缺循环检测；两者都已在本轮内修完。  
另外，全量 acceptance 又暴露出 `report-register-requires-claim` 会被前序 case 污染前提，这个问题也已经通过“case 内部主动清 runtime context”收口，没有遗留成新的 blocker。

### 6.3 推荐的下一步行动

1. 继续 F2：把 hook / lesson / contract / 状态机等治理规范继续翻译成 gate，而不是继续堆文档描述。
2. 紧接着推进 A3 / F3：把三轨评审门与治理硬化补成可执行的运行链。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-67 | 缺 claim 的 acceptance 不能依赖外层清理 | 任何断言“当前没有 runtime / process claim”的 case，都必须在 case 内自行 `redcap_runtime_clear_context` 并清掉 recovery 相关环境变量，否则全量跑时很容易被前序 case 污染成假阳性 |

### 7.2 流程改进建议

以后只要升级了任务报告模板或摘要结构，就应同时检查当前 worktree 里准备归档的旧报告是否仍停在旧格式；如果有，就要在同一轮里一起迁移。否则最容易出现“模板和 gate 都升级了，但正准备提交的报告自己先把 gate 打爆”的断链。

---

## 八、附录

### 附录 A：Commits

```
f9ed7a5 docs(架构): 归档框架升级 backlog 设计
abb6f4d docs(规范): 固化中文优先术语规则
110c509 docs(规范): 固化不中断执行与终局汇报
（本轮 follow-up 变更当前仍在工作区，尚未形成新的 commit）
```

### 附录 B：棱镜调用记录（如有）

本轮没有单独归档 Prism 报告；采用了会话内独立 Agent 作为补充审计：

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| explore | D1 / F2 当前应该先落哪一刀 | 先补 spec 迁移门 / archive enforcement / role-status 准入，再继续扩大 F2 | 会话内 agent `d1-f2-audit`（无独立文件） |
| code-review | 当前改动是否还有真实重要问题 | 先指出旧报告模板与 replacement cycle 两个问题；修复后复审 clean | 会话内 agent `followup-review`（无独立文件） |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md` 中的 `U10`、`Q15`、`Q16`
- 长期路线权威：`references/backlogs/framework-upgrade.json`
- backlog 人类说明：`compass/docs/specs/2026-04-13-framework-upgrade-backlog-design.md`
- 上一刀报告：`compass/docs/task-reports/2026-04-14-backlog-mechanism-and-spec-governance.md`
- 本轮报告：`compass/docs/task-reports/2026-04-15-report-template-and-d1-f2-followup.md`
