# 任务完成报告：autonomy escalation P0

**报告日期**：2026-04-12  
**执行者**：Cap（Copilot CLI / GPT-5.4）  
**报告版本**：v1.0

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 1. 需要立即把docs/目录下的文件按照他们本身的定位放置到合理的文件层级下，而不是大杂烩耦合在docs/下
> 2. 从一个缺口要联想反应到全貌都可能存在类似的隐患，所以由本次docs/的问题引起的警惕，需要开展全架构性质的搜索评估工作。因此，可以预见的是，这是一个长任务、复杂任务，你需要多家利用棱镜的优势来消化这个长任务。同时，为了防止长任务带来的上下文稀释影响，可以把“防偏航/防上下文稀释”大体系下的目录暂缓到最后执行，避免留痕体系出岔子。但是开始“防偏航/防上下文稀释”迁移之前，要做好充分记录，告知自己和团队要开始迁移“防偏航/防上下文稀释”体系的文件了，避免“防偏航/防上下文稀释”迁移过程中的动作自我干扰。
> 3. 反思为什么最终review环节没有看到到我这次从docs/提出来的严重问题，哪里出的问题，怎么弥补，防止后续类似的严重问题再被淹没和忽视
> 4. gemini cli的使用率有没有高达50%？如果没有，为什么不用他？如果没有合理的理由，则必须提高gemini cli的使用，但不用刻意使用以追求50%的线，只要能提高使用率即可
>
> 我发现你现在已经100%触发阻断任务，并向我寻求人工介入了，这应该是某个skill导致的，这严重违反了你被赋予的“你可以借住棱镜团队自主决定大部分决策，只有在必须要人工介入提供AI无法计算和识别的能力时，才需要人工介入”的准则。这个当作一个P0故障先排查和解决掉，否则其余任务一律做好备份然后存档暂不执行。

### 1.2 触发背景

本轮原计划进入 `compass/docs/` 信息架构与全架构耦合审计，但在 tranche 分解阶段，宿主通用 brainstorming skill 把原本可由 RedCap 自主吸收的决策错误升级成了 ask_user。  
用户据此指出：这不是普通澄清，而是一次 **自治失效 / authority inversion**，必须优先按 P0 修复，其余工作全部冻结。  
因此本次任务的目标不是继续 docs 主线，而是收紧 **宿主 overlay skill 与 RedCap-native 控制面** 的边界。

---

## 二、方案讨论

### 2.1 问题分析

Q1 的核心问题不是“问了一个多余的问题”，而是 **宿主 overlay protocol 越权**：brainstorming 把 ask_user / approval / spec lane 当成默认主路，压过了 `.dev-task.md`、PM Gate、自主执行授权与棱镜协商。  
Q2 的核心问题是 **人工介入门定义不够精确**：如果只说“复杂了就问人”，那 Prism 死锁、内部争议、提示词习惯都可能被误当成人工介入理由。  
Q3 的核心问题是 **必须守住 repo-owned 收口边界**：只改 RedCap 口头提醒不够，但直接改冲突宿主 skill 又会越过资产边界，因此最终只能把 RedCap 自身规则补齐，并把宿主冲突路径诚实标注为 degraded / unsupported。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 选项 A | 只在 RedCap 文档里声明“以后别这样做” | 改动小 | 冲突 skill 仍保留默认 ask_user / spec lane，复发概率高 |
| Q1 | 选项 B | 只改 brainstorming skill | 直击表面触发点 | 这属于改宿主共享资产，不是修 RedCap 自身 |
| Q1 | 选项 C | repo-owned 收口 + degraded 判定 | 不依赖改宿主 shared skill，口径更稳 | 宿主冲突仍需按 degraded / unsupported 诚实标注 |
| Q2 | 选项 A | 允许 Prism 死锁 / Dispatcher 建议直接构成人工介入理由 | 实现简单 | 会留下新的非 canonical 上抛逃生门 |
| Q2 | 选项 B | 只有缺失外部事实、非自动化人工动作、或 Norven 保留决策时才允许上抛；Prism/Dispatcher 只能诊断 | 口径最严整，符合用户要求 | 需要同步修正多份规则文本 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 选项 C | 这是一次协议碰撞，但最终只能修 repo-owned 控制面；若不改宿主 skill 就无法成立，就必须降级为 degraded / unsupported | CAP_DECIDE |
| Q2 | 选项 B | 用户要求“只有 AI 真算不出来或必须由人类亲自完成的能力”才允许介入，因此 Prism/Dispatcher 不能成为独立上抛理由 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `.dev-task.md` | 修改 | 切到 `autonomy-escalation-p0`，冻结 docs 相关 tranche，并显式声明 `human_escalation_policy` / `overlay_skill_policy` |
| `SKILL.md` | 修改 | 新增宿主通用 skill 兼容规则与 overlay subordinate 规则，收紧 ask_user 条件 |
| `compass/CONTRIBUTING.md` | 修改 | 新增“宿主通用 skill overlay 兼容规则”，明确人工介入条件与实现口径 |
| `ARCHITECTURE.md` | 修改 | 将宿主通用 skill 纳入 truth surface / governance model，明确 advisory-only 边界 |
| `references/agent-constraints.md` | 修改 | 为子 Agent 增加人工介入门，避免再次把可自治问题上抛给人类 |
| `compass/knowledge/lessons.md` | 修改 | 更新 L-48 并新增 L-49，沉淀 overlay authority collision 与宿主资产边界经验 |
| `compass/docs/specs/2026-04-12-host-skill-overlay-governance-design.md` | 新建 | 固化本次 P0 的设计边界、非目标与 repo-owned 修复口径 |
| `compass/docs/task-reports/2026-04-12-autonomy-escalation-p0.md` | 新建 | 归档本次 P0 修复的完整报告 |
| `/Users/norven/.copilot/session-state/.../plan.md` | 修改 | 宿主镜像 workboard 切到当前 P0 并冻结其他 tranche |

### 3.2 技术实现要点

第一，当前任务真相源被重新收口：`.dev-task.md` 已切到 `autonomy-escalation-p0`，而 docs 架构整顿主线被显式冻结，不再让宿主 `plan.md` 或外层 skill 默认推进后续 tranche。  
第二，RedCap-native 侧新增了统一的 **overlay subordinate** 规则：宿主通用 skill 只能 advisory-only，不能覆盖 `.dev-task.md`、PM Gate、自主执行授权，也不能默认把 tranche 决策抛回给人类。  
第三，人工介入门被收紧成三类 canonical 缺口：**外部事实**、**非自动化人工动作/验证**、**Norven 保留决策**。Prism 死锁和 Dispatcher 建议现在只算诊断信号，不能单独成为 ask_user 理由。  
第四，repo 最终没有把共享宿主 skill 当成修复面：曾经出现过直接修改 external brainstorming skill 的错误尝试，但已被回滚；最终受支持的口径是 **共享宿主 skill 属于 carrier-owned overlay，不是 RedCap 的 patch surface**。  
第五，子 Agent 共享约束也同步更新，避免棱镜或外包 Agent 继续用 `need_user` 把本可自治的问题扔回给人类。  
第六，整个修复被诚实地归类为 **prompt-level hard limitation + canonical-truth discipline**；若宿主 shared skill 仍冲突，正确结论是 degraded / unsupported，而不是去改写宿主共享原件。

### 3.3 关联变更

这次修复直接冻结了原本待执行的 `compass/docs/` 主线，并把它们保留在 `.dev-task.md` 原始输入中，作为后续恢复位点。  
此外，独立 review 还指出一个容易误伤现有流程的副作用：过窄的人类介入门会破坏 QA 的 GUI/manual validation 路径。因此本次补丁随后又把“AI 无法直接执行/验证的人类动作”明确纳入合法上抛条件，避免修复 P0 时反向损坏 Layer A。

---

## 四、人工审核要点

> ⚠️ 以下是 Norven 需要重点确认的内容，其他部分 Cap 已自行验证。

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 真实宿主会话中是否仍会出现 overlay skill 越权 | 本次只修了 RedCap repo-owned 控制面，未再触碰共享宿主 skill；真实运行效果仍需后续观察 | P1 |
| 2 | 冻结的 docs 主线恢复顺序 | 本次只修 P0，不恢复后续 tranche；恢复节奏仍需按后续风险重新安排 | P1 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 旧的独立上抛理由已移除 | `rg "Prism 真死锁|Dispatcher 明确要求上抛" SKILL.md compass/CONTRIBUTING.md references/agent-constraints.md compass/docs/specs/2026-04-12-host-skill-overlay-governance-design.md` | ✅（No matches found） |
| repo 口径已声明“共享宿主 skill 不是 patch surface” | `rg "patch surface|degraded / unsupported overlay" SKILL.md compass/CONTRIBUTING.md ARCHITECTURE.md compass/knowledge/lessons.md compass/docs/specs/2026-04-12-host-skill-overlay-governance-design.md` | ✅ |
| repo 内本轮 diff rereview | `repo-quick-review` | ✅（No significant issues found in the reviewed changes） |
| 定向 rereview 找出并修复 QA manual verification 漏口 | `autonomy-patch-review-1` | ✅（发现 1 个高优问题，已修复） |
| 外部 shared skill 改动已回滚 | 手动回滚 `/Users/norven/.claude/skills/brainstorming/SKILL.md` 到原始宿主版本 | ✅ |
| repo-owned remediation 终态审查 | `repo-owned-remediation-review` | ✅（No significant issues found in the reviewed changes） |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 在真实 RedCap + brainstorming 同时激活的宿主会话里，确认已锁定 tranche 不会再次 ask_user
- [ ] 在真实 GUI/manual validation 任务中，确认 QA 仍能合法返回 `need_user`

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| ask_user 的物理拦截仍不可用 | ask_user 属于宿主层工具调用，本仓库脚本无法像 closure hook 那样直接拦截 | P1 |
| `compass/docs/` 信息架构与全架构耦合审计尚未恢复 | 用户要求先修 P0，其余 tranche 全部冻结 | P0 |

### 6.2 触发的新问题

本次最终确认了一个新的框架级结论：**overlay skill compatibility 本身必须被当成 host-agent interop governance 的组成部分**。  
此前治理主要覆盖 `plan.md`、runtime state、delegation boundary、closure contract；现在还必须把宿主通用 skill 的默认协议也纳入 authority layering 审核。

### 6.3 推荐的下一步行动

1. 用一次真实宿主会话复测 RedCap + brainstorming 叠加场景，观察 ask_user 是否彻底收敛到合法边界。
2. 在 P0 被确认稳定后，再恢复 `compass/docs/` 主线，并把本次新增的 overlay-skill 审查项纳入 review checklist。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-48 | 宿主通用 skill 只能是 overlay，不能把可自治决策升级成人工阻断 | overlay skill 必须向 controlling framework 让位；人工介入只能围绕外部事实、人工动作或保留决策 |

### 7.2 流程改进建议

今后凡是引入或叠加新的宿主 skill，都必须先问一个问题：**它是 authority，还是 overlay？**  
如果只是 overlay，就不能拥有自己的默认 ask_user / spec lane / transition lane；这些都必须受 RedCap-native 控制面的边界约束。

---

## 八、附录

### 附录 A：Commits

```text
7734f5e feat(框架): 收口多会话隔离与互操作治理
d1c8a57 docs(框架): 新增 host-agent 互操作治理设计
664333f docs(spec): add prism coordinator phase a design
31fa41d docs(spec): add multi-session isolation design
```

### 附录 B：独立评审记录

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| review | `autonomy-patch-review-1`：新的人工介入门是否误伤现有合法流程 | 发现 QA manual verification 漏口，已修为“外部事实 / 人工动作 / 保留决策”三类合法上抛条件 | `N/A` |
| review | `repo-quick-review`：repo 内当前 diff 是否还有高信号问题 | No significant issues found in the reviewed changes | `N/A` |
| review | `brainstorm-skill-check`：中间态 external shared-skill patch 是否仍残留 ask_user / approval 冲突 | No significant issues remain，但该中间态随后已因“shared host skill 不是 patch surface”结论而整体回滚 | `N/A` |
| review | `repo-owned-remediation-review`：回滚 external shared skill 后，repo 最终口径是否仍有高信号矛盾 | No significant issues found in the reviewed changes | `N/A` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- 设计文档：`compass/docs/specs/2026-04-12-host-skill-overlay-governance-design.md`
- 任务报告：`compass/docs/task-reports/2026-04-12-autonomy-escalation-p0.md`
