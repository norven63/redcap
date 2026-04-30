# 任务完成报告：docs 治理与产物生命周期审计

**报告日期**：2026-04-12
**执行者**：Cap（Copilot CLI / GPT-5.4）
**报告版本**：v1.0

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> compass/docs/ 这个目录下的是不是都是临时产物？它的存在意义是否可以抹去，或者至少不应该被redcap任何能力所耦合？
>
> 现在里面的内容，只有分2种：调研资料、历史追踪，我理解的正确吗？
>
> 1. 需要立即把docs/目录下的文件按照他们本身的定位放置到合理的文件层级下，而不是大杂烩耦合在docs/下
> 2. 从一个缺口要联想反应到全貌都可能存在类似的隐患，所以由本次docs/的问题引起的警惕，需要开展全架构性质的搜索评估工作。
> 3. 反思为什么最终review环节没有看到到我这次从docs/提出来的严重问题，哪里出的问题，怎么弥补，防止后续类似的严重问题再被淹没和忽视

### 1.2 触发背景

多会话隔离与 host-agent interop 主线技术上已经收口，但用户从 `compass/docs/` 的目录形态反向指出：**功能闭环不等于信息架构健康**。
这暴露出的不是单一目录脏乱，而是更深层的 artifact lifecycle 问题——历史证据、设计快照、技术调研、本地 runtime cache 被放进了不正确的层级，且 review 没有显式检查这件事。
因此本 tranche 的目标是：重整 docs 信息架构、识别并移除误入 git 的本地状态、把生命周期分类写入权威文档与 review gate。

---

## 二、方案讨论

### 2.1 问题分析

Q1 的核心问题不是“文件名是否好看”，而是 **authority 混放**：`task-reports`、`specs`、`research`、`traces` 的用途完全不同，却被平铺在 `compass/docs/` 根目录。
Q2 的核心问题是 **宿主默认输出路径漂移**：两份 Layer B 设计文档仍落在根 `docs/superpowers/specs/`，等于 RedCap 自有文档仍依赖宿主默认目录。
Q3 的核心问题是 **lifecycle 漏审**：`compass/.workflow/agent-registry.yaml` 记录的是本机 CLI 路径、探测时间、配置 mtime，明显属于 local-only runtime cache，却仍被 git 跟踪。
Q4 的核心问题是 **review 维度缺口**：原先 stop-review 与 task-completion review 更偏向逻辑/路径/联动更新，没有把“这个文件为什么在这里、应不应该进 git”作为显式检查项。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1/Q2 | 选项 A | 保持 `compass/docs/` 平铺，只靠命名约定区分文件类型 | 改动少 | authority 混放继续存在，后续 review 仍难快速识别 |
| Q1/Q2 | 选项 B | 把 docs 拆成 `specs/`、`research/`、`traces/`、`task-reports/`，并把漂在根 `docs/` 的 Layer B 设计文档迁回 | 目录语义清晰，后续引用与审计有稳定锚点 | 需要批量修正引用路径 |
| Q3/Q4 | 选项 A | 只修 docs 路径，不触碰 `.gitignore`、review gate、lessons | 改动面更小 | 无法防止同类 lifecycle 污染再次发生 |
| Q3/Q4 | 选项 B | 同步建立 artifact lifecycle 四分法、收紧 `.gitignore`、把 stop-review/Task Completion Review Gate 纳入检查面，并沉淀 lesson | 形成长期治理闭环 | 需要联动更新多份规范/脚本/报告 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1/Q2 | 选项 B | docs 问题的根因是 authority 混放，不是单纯命名问题；必须把 Layer B 自有文档收回 repo-owned 分类树 | NORVEN_DECIDE + CAP_DECIDE |
| Q3/Q4 | 选项 B | 如果不把 lifecycle 分类与 review 维度一起硬化，今天能修 docs，明天还会有新的 runtime/local-only 文件混进 git | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `compass/docs/specs/**` | 新建/迁移 | 将原先平铺在 `compass/docs/` 与根 `docs/superpowers/specs/` 的 Layer B 设计文档统一迁入 `specs/` |
| `compass/docs/research/feishu-ai-agent-collaboration-report.md` | 新建/迁移 | 将技术调研文档从 `compass/docs/` 根目录迁入 `research/` |
| `compass/docs/traces/architecture-capability-trace.yaml` | 新建/迁移 | 将能力追踪矩阵迁入 `traces/`，与 specs / reports 分层 |
| `compass/docs/task-reports/*.md` | 修改 | 批量修正设计文档与 trace matrix 的引用路径 |
| `.gitignore` | 修改 | 新增 `compass/.workflow/` 忽略规则，防止本地 runtime cache 进入 git |
| `README.md` | 修改 | 更新目录树，明确 `specs / research / traces / task-reports` 分层与 `.workflow` local-only 身份 |
| `ARCHITECTURE.md` | 修改 | 新增 artifact lifecycle 四分法，并更新 trace matrix 路径 |
| `compass/CONTRIBUTING.md` | 修改 | 固化 Layer B 生命周期分类规则，并把 docs/lifecycle 检查写入 Stop Hook 与 Task Completion Review Gate |
| `compass/tools/redcap-detect-agents.sh` | 修改 | 默认 registry 落点改为 `compass/.workflow/agent-registry.yaml`，与生命周期治理口径对齐 |
| `loom/dispatcher/agent-adapters.md` | 修改 | 对齐嗅探脚本真实路径与 `compass/.workflow/agent-registry.yaml` cache 路径 |
| `compass/tools/redcap-on-stop-review.sh` | 修改 | 新增“目录与生命周期边界”评审维度 |
| `compass/knowledge/lessons.md` | 修改 | 新增 L-50，沉淀 docs 杂糅与 lifecycle 漏审的失败模式 |
| `loom/test-reports/benchmark-scenario.md` | 修改 | 修复残留的 `testing/...` 旧路径，统一到 `loom/test-reports/...` |
| `loom/test-reports/latest-e2e-report.md` | 修改 | 修复对 `testing/...` 的过时引用 |
| `compass/.workflow/agent-registry.yaml` | 删除（停止跟踪） | 退出 git，保留为本地 runtime cache |

### 3.2 技术实现要点

第一，`compass/docs/` 不再作为“大杂烩根目录”，而是按 **spec / research / trace / task-report** 四类 authority 明确分层。这样后续审计时，看到路径本身就能先判断文件应承担什么角色。
第二，Layer B 设计文档不再漂在根 `docs/superpowers/specs/`。这一步很关键，因为它切断了 RedCap 自有设计资产对宿主默认输出路径的耦合。
第三，本次不只做“搬目录”，还做了 **artifact lifecycle 收口**：`ARCHITECTURE.md` 和 `CONTRIBUTING.md` 共同定义了 repo-tracked canonical/evidence、session-isolated process state、local-only host assets、temporary runtime outputs 四类产物。
第四，`compass/.workflow/agent-registry.yaml` 被重新定性为 **local-only runtime cache**。它记录的是本机 CLI 路径、探测时间、配置 mtime，与共享历史无关，因此必须退出 git，并由 ignore 规则兜底。
第五，review 机制被补齐了 lifecycle 视角：`redcap-on-stop-review.sh` 现在会显式检查 session/local-only 文件是否误入 git、docs 落点是否正确、是否残留旧路径或宿主默认输出路径耦合。
第六，全架构搜索还顺手暴露了 `loom/test-reports/benchmark-scenario.md` 与 `latest-e2e-report.md` 里的旧 `testing/...` 路径口径，本 tranche 一并修复，避免后续 E2E 继续被错误路径误导。

### 3.3 关联变更

本次 docs 治理直接联动到了架构文档、开发规范、Stop Hook 评审脚本、E2E 文档和历史任务报告。
这不是“额外整理”，而是由生命周期分类自然触发的联动：只要目录语义变了，引用路径、review 检查面、lessons 与目录树说明就都必须一起收口。
同时，本次把“为什么之前 review 没看出来”的答案沉淀成 L-50，并补到 stop-review 与 task-completion gate 中，防止这次经验只停留在对话里。

---

## 四、人工审核要点

> ⚠️ 以下是 Norven 需要重点确认的内容，其他部分 Cap 已自行验证。

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 当前四分法是否满足你对“会话隔离 / 临时 / 本地 / 共享历史”的边界预期 | 本 tranche 已给出可执行分类并据此收口，但边界定义本身属于长期治理口径，Norven 的确认能作为后续一切 artifact 审计的稳定基线 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 旧 docs/spec 路径残留扫描 | `grep -R -nE --exclude-dir='.git' --exclude='2026-04-12-docs-governance-audit.md' 'compass/docs/(architecture-capability-trace|baton-design|engine-upgrade-part1-design-philosophy|engine-upgrade-part2-execution-framework|hook-chain-investigation-design|multi-session-isolation-design|prism-coordinator-phase-a-design)\\.(md|yaml)|docs/superpowers/specs/2026-04-12-host-(agent-interop-governance|skill-overlay-governance)-design\\.md' .` | ✅（No matches found） |
| runtime cache 是否仍被 git 跟踪 | `git ls-files | grep '/\\.workflow/'` | ✅（No matches found） |
| docs 分层结果检查 | `find compass/docs -maxdepth 2 -type f | sort` | ✅ |
| shell 语法检查 | `bash -n compass/tools/redcap-detect-agents.sh compass/tools/redcap-on-stop-review.sh` | ✅ |
| diff hygiene | `git diff --check` | ✅ |
| E2E 文档旧路径扫描 | `grep -R -nE --exclude-dir='.git' --exclude='2026-04-12-docs-governance-audit.md' 'testing/(benchmark-scenario|latest-e2e-report|pending-validations)\\.md' .` | ✅（No matches found） |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 若后续还有新的 Layer B 文档落盘，观察团队是否能稳定遵守 `specs / research / traces / task-reports` 四分法，而不再回到平铺混放

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| 暂无阻断性遗留问题 | 本 tranche 的目标是 docs/生命周期治理与 review 补强，当前范围内的问题已收口 | P2 |

### 6.2 触发的新问题

本次进一步确认：**review 如果只盯功能正确性，会系统性漏掉目录与生命周期污染。**
这类问题不会让脚本立即报错，但会慢慢破坏 repo 的 authority 结构，并在长任务中放大上下文稀释和考古成本。
因此 lifecycle 审计必须被当成一等检查面，而不是“最后顺手看看目录整不整齐”。

### 6.3 推荐的下一步行动

1. 以后每次新增 Layer B 文档或运行时目录，都先按四分法判断它属于 history/evidence、session state、local-only 还是 temporary，再决定是否进 git。
2. 若后续在 Loom / Prism 再发现类似“本地 cache 误入 git”的对象，直接按本 tranche 的治理口径处理，不再重新讨论“这是不是临时文件”。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-50 | docs / artifact 审计若只看内容正确性，会漏掉目录边界与生命周期污染 | review 必须同时检查 authority / lifecycle / ownership，不能只看内容能否打开和路径能否解析 |

### 7.2 流程改进建议

以后 docs 整理不应再被视为“文档美化”类工作，而应被视为 **控制面治理**。
只要某个目录同时承载 canonical history、设计快照、本地 cache、会话态，就意味着 authority boundary 已经开始失真，必须立即收口。

---

## 八、附录

### 附录 A：Commits

```text
f00d903 feat(治理): 恢复主线记录与通知路由治理
6032a26 fix(框架): 修正宿主 shared skill 资产边界
```

### 附录 B：独立评审记录

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| review | docs / lifecycle 迁移后是否仍残留路径耦合、runtime 污染或高信号回归 | 首轮发现 3 个问题（新 docs 未入 git、agent-registry 默认路径错误、spec 相对链接失效），修复后最终 rereview 返回 “No significant issues found in the reviewed changes.” | `N/A` |
| review | focused docs slice 是否仍存在分类/路径/提示词错位 | 发现 2 个中优问题（agent-registry 分类错位、stop-review 仍引用旧 `test-reports/` 路径），修复后 focused re-review 返回 “No significant issues found in the reviewed changes.” | `N/A` |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- 架构总纲：`ARCHITECTURE.md`
- trace 矩阵：`compass/docs/traces/architecture-capability-trace.yaml`
- 设计快照目录：`compass/docs/specs/`
- 历史任务报告目录：`compass/docs/task-reports/`
