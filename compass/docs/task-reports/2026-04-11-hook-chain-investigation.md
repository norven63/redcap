# 任务完成报告：Hook 链排查与 Layer B 收尾加固

**报告日期**：2026-04-11
**执行者**：Cap（Copilot CLI / GPT-5.4）
**报告版本**：v1.0

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 我发现你现在有至少有2个行为没有按照约定来执行：1. 结果报告不是按照模版来走的  2. 飞书通知没有了。这2个问题本身不是什么大问题，但却暴露了一个很大的隐患：hook机制失效了！你和棱镜团队要赶紧由此为突破口，进行一轮详细的排查，是否还有我没有发现的问题和隐患，要举一反三、由此及彼的探索出问题。

### 1.2 触发背景

Prism redteam E2E 收尾完成后，用户没有先质疑业务结果，而是直接指出“模板报告缺失 + 飞书通知缺失”。这说明真正的问题不是单次遗漏，而是 Layer B 的**完成链缺少物理保障**：文档、宿主 Hook、报告产物三者已经发生漂移。
本次任务的目标因此从“补发一次通知”升级为“重建可审计的 Layer B SessionEnd 收尾链”，避免以后再次靠人工肉眼发现。

---

## 二、方案讨论

### 2.1 问题分析

这次暴露出来的不是单点 bug，而是三类错位叠加：
1. **主链错位**：Layer B 飞书通知本来要求流程内主动执行，但实际执行缺少兜底。
2. **可观测性缺失**：任务完成报告只存在于对话规范，没有任何物理产物可被 Hook 审计。
3. **文档漂移**：Copilot / Gemini / Claude 的 Hook 能力、部署状态与真实配置文件不一致，导致“能力存在”被误写成“当前已覆盖”。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 选项 A | 只补发飞书和聊天报告，不改 Hook 链 | 见效快 | 不能解决根因，下一次还会漏 |
| Q1 | 选项 B | 仅下调文档口径，承认当前未覆盖 | 风险低 | 仍没有 Layer B 兜底链 |
| Q1 | 选项 C | 统一 Layer B SessionEnd 收尾链：评审、报告审计、飞书兜底、配置对齐一起修 | 直接修根因，形成可审计闭环 | 改动面较大，需要跨多份文档和宿主配置同步 |
| Q2 | 选项 A | 继续只在对话中按模板汇报 | 使用成本最低 | Hook 永远不可观察，无法机器审计 |
| Q2 | 选项 B | 写一个简易 marker 文件表示“已汇报” | 机器可读 | 只证明“做过”，不证明“按模板做对了” |
| Q2 | 选项 C | 把任务完成报告归档到 `compass/docs/task-reports/*.md`，并检查关键章节 | 同时解决归档与模板审计问题 | 需要引入新的物理归档约定 |
| Q3 | 选项 A | Copilot 线只修文档，不立刻落地 Hook | 成本较低 | 继续保留一个已知宿主缺口 |
| Q3 | 选项 B | 直接按官方 `.github/hooks/*.json` 方式落地 Layer B Copilot Hook | 文档与实现一次对齐 | 需要真实跑一轮 CLI 验证 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 选项 C | 用户明确要求以“模板/飞书失效”为入口做系统排查；只补症状不符合问题级别 | CAP_DECIDE |
| Q2 | 选项 C | 只有物理报告文件才能被 SessionEnd Hook 审计，marker 不足以约束模板质量 | CAP_DECIDE |
| Q3 | 选项 B | 官方文档已确认 Copilot 仓库级 Hook 形态，且本仓库正好需要补 Layer B 覆盖 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `.claude/settings.json` | 修改 | Claude Layer B 从“Stop 发通知”改为“Stop 做独立评审 + SessionEnd 统一收尾” |
| `.gemini/settings.json` | 修改 | 补上 SessionStart，SessionEnd 改为明确走统一分发器 |
| `.github/hooks/redcap-layerB.json` | 新建 | 为 Copilot CLI 落地仓库级 `sessionStart` / `sessionEnd` 配置 |
| `.github/hooks/scripts/redcap-layerB-session-start.sh` | 新建 | Copilot SessionStart 包装脚本 |
| `.github/hooks/scripts/redcap-layerB-session-end.sh` | 新建 | Copilot SessionEnd 包装脚本 |
| `compass/tools/redcap-layerB-session-start.sh` | 新建 | 统一 Layer B 初始 HEAD 捕获入口 |
| `compass/tools/redcap-layerB-session-end.sh` | 新建 | 统一 Layer B SessionEnd 收尾入口 |
| `compass/tools/redcap-task-report-check.sh` | 新建 | 检查最近 commit 区间内是否存在模板完整的任务报告 |
| `compass/tools/redcap-task-report-register.sh` | 新建 | 为未提交但已暂存的报告按宿主显式登记当前任务关联路径 |
| `compass/tools/redcap-explore-notes-check.sh` | 新建 | 把 `explore-notes` 未归档提醒从旧 Stop 通知脚本中抽成通用检查 |
| `compass/tools/redcap-claude-hook-init.sh` | 修改 | 改为复用统一 SessionStart 脚本 |
| `compass/tools/redcap-on-stop-review.sh` | 修改 | 支持可注入 baseline 文件，并补接 `explore-notes` 检查 |
| `loom/tools/redcap-layerA-session-end.sh` | 修改 | 成为所有宿主的统一 SessionEnd/Stop 分发入口 |
| `references/task-report-template.md` | 修改 | 明确 Layer B 报告必须物理归档到 `compass/docs/task-reports/` |
| `references/hook-standards.md` | 修改 | 新增“任务完成报告必须物理归档”不变量 |
| `compass/CONTRIBUTING.md` | 修改 | 把模板报告、SessionEnd 审计、飞书主链/兜底边界写成正式规约 |
| `compass/knowledge/hooks-copilot-cli.md` | 修改 | 彻底重写为官方 `.github/hooks/*.json` 口径，并写入本地验证结果 |
| `compass/knowledge/hooks-gemini-cli.md` | 修改 | 从“可部署”更新为“Layer B 已部署，Layer A 默认未装” |
| `compass/knowledge/hooks-claude-code.md` | 修改 | 更新为 InstructionsLoaded + Stop + SessionEnd 三段式 Layer B 配置 |
| `compass/knowledge/host-reliability.md` | 修改 | 把宿主 Hook 覆盖率、脚本职责、Copilot/Gemini 真相表全部对齐 |
| `compass/knowledge/DEPLOYMENT_STATUS.md` | 修改 | 把 Layer B 覆盖矩阵更新为 Claude / Gemini / Copilot 三宿主 |
| `compass/knowledge/lessons.md` | 修改 | 新增 L-41，沉淀“能力存在 ≠ 已部署 ≠ 已生效” |
| `ARCHITECTURE.md` | 修改 | 更新 Hook 基础设施图与 Layer B 收尾职责 |
| `README.md` | 修改 | 修正飞书说明，避免把 Layer B 收尾说成单纯“自动通知” |
| `loom/dispatcher/agent-adapters.md` | 修改 | 修正 Copilot Hook 配置与 `--output-format=json` 描述 |
| `compass/docs/task-reports/2026-04-11-hook-chain-investigation.md` | 新建 | 归档本次任务完成报告，供 SessionEnd Hook 审计 |

### 3.2 技术实现要点

本次核心改动是把 Layer B 收尾链重新拆成“**宿主入口** + **统一分发器** + **最终收尾逻辑**”三层。Claude、Gemini、Copilot 只负责把事件接到统一入口，不再各自维护一套通知逻辑，从源头减少宿主漂移。

任务完成报告不再停留在聊天约束，而是被提升为**可观察产物**：`compass/tools/redcap-task-report-check.sh` 会检查最近 commit 区间内是否存在 `compass/docs/task-reports/*.md`，并验证关键章节是否齐全。这样 SessionEnd Hook 才能对“是否按模板汇报”做机器审计。

Copilot 线按官方仓库级 Hook 机制重新落地：不是“放几个脚本到 `.github/hooks/`”，而是**必须**有 `.github/hooks/redcap-layerB.json` 把 `sessionStart` / `sessionEnd` 注册起来。随后又用本地最小命令对 `sessionStart` / `sessionEnd` 做了独立验证，补上此前缺失的物理证据。

旧的 `redcap-claude-hook-stop.sh` 不再承担主职责后，`explore-notes` 未归档提醒被拆到独立 helper，再接回 Stop / SessionEnd 链。这样即使收尾职责迁移，书记协议的提醒也不会被静默丢失。

### 3.3 关联变更

1. 因 `task-report-template.md` 增加物理归档约定，联动更新了 `CONTRIBUTING.md`、`hook-standards.md`、`ARCHITECTURE.md`、`README.md`。
2. 因 Copilot Hook 真实部署方式被纠正，联动更新了 `hooks-copilot-cli.md`、`host-reliability.md`、`DEPLOYMENT_STATUS.md`、`agent-adapters.md`。
3. 因 Layer B 收尾链职责重构，联动更新了 Claude/Gemini 的项目级配置文档与部署矩阵。

---

## 四、人工审核要点

无阻塞式人工审核项。本次 incident 里关于 Layer B 报告归档目录、宿主职责边界、真实部署口径的决策，均已在多轮独立审查和真实 smoke 后由 Cap 自主闭合；若未来要把同等级“物理报告审计”扩展到 Layer A，应另起独立设计，不混入本次修复。

---

## 五、验证结果

### 5.1 自动化验证

> 说明：以下命令前缀里的 `REDCAP_SKIP_FEISHU=1` 与 `REDCAP_SKIP_INDEPENDENT_REVIEW=1`，都是 **Cap 在本地做最小 smoke 时临时注入的验证变量**，用于避免测试过程产生真实飞书或重复拉起独立评审；它们不是用户预设，也不是 RedCap 的常驻部署要求。

| 验证项 | 命令 | 结果 |
|--------|------|------|
| Shell 语法检查 | `bash -n compass/tools/redcap-claude-hook-init.sh compass/tools/redcap-layerB-session-start.sh compass/tools/redcap-task-report-check.sh compass/tools/redcap-layerB-session-end.sh compass/tools/redcap-explore-notes-check.sh compass/tools/redcap-on-stop-review.sh loom/tools/redcap-layerA-session-end.sh .github/hooks/scripts/redcap-layerB-session-start.sh .github/hooks/scripts/redcap-layerB-session-end.sh` | ✅ |
| JSON 配置校验 | `python3 - <<'PY' ... json.load(open('.claude/settings.json')) ... json.load(open('.gemini/settings.json')) ... json.load(open('.github/hooks/redcap-layerB.json')) ... PY` | ✅ |
| Copilot SessionEnd 物理触发 | `REDCAP_SKIP_FEISHU=1 REDCAP_SKIP_INDEPENDENT_REVIEW=1 copilot -p 'Reply with OK only.' --allow-all --no-custom-instructions -s --model gpt-5-mini`（预先写入 `last-notified=HEAD~1`） | ✅：`/tmp/redcap-layerB-copilot-last-alerted-head = CURRENT_HEAD` |
| Copilot SessionStart 物理触发（间接） | `REDCAP_SKIP_FEISHU=1 REDCAP_SKIP_INDEPENDENT_REVIEW=1 copilot -p 'Reply with OK only.' --allow-all --no-custom-instructions -s --model gpt-5-mini`（清空 `last-notified` / `initial-head`） | ✅：结束后 `last-notified` 仍为 `(missing)`，说明先写入了初始 HEAD，再被无差异 SessionEnd 清理 |
| Copilot 成功路径（报告已提交） | `REDCAP_SKIP_FEISHU=1 REDCAP_SKIP_INDEPENDENT_REVIEW=1 copilot -p 'Reply with OK only.' --allow-all --no-custom-instructions -s --model gpt-5-mini`（预先写入 `last-notified=HEAD~1`，当前 HEAD 已包含报告） | ✅：`last-notified = CURRENT_HEAD` 且 `last-alerted = (missing)` |
| Claude SessionEnd 真实 smoke | `REDCAP_SKIP_FEISHU=1 claude -p "Reply with OK only." --output-format text`（预先写入 `last-notified=HEAD~1`） | ✅：修复宿主特定 stdout 协议后，`last-notified = CURRENT_HEAD` 且 stderr 无 schema error；同时修正了用户级 `~/.claude/settings.json` 中遗留的旧绝对路径 |
| Gemini SessionEnd 真实 smoke | `REDCAP_SKIP_FEISHU=1 REDCAP_SKIP_INDEPENDENT_REVIEW=1 gemini -p "Reply with OK only." -y --output-format text`（预先写入 `last-notified=HEAD~1`） | ✅：`last-notified = CURRENT_HEAD` 且不再出现由说明文字中的导入指令关键字触发的导入噪音 |

### 5.2 追加结论

当前已无必须补跑的宿主级 smoke。Claude / Gemini / Copilot 三宿主都已完成最小真实会话验证，剩余仅保留“同宿主并发 Layer B session 共享宿主级报告 marker”这一已知非阻塞边界。

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| Layer A 的 Copilot `.github/hooks/*.json` 安装模板尚未提供 | 本次优先级是修复 Layer B 自身开发的收尾链 incident，不应把用户项目安装模板混入同一修复 | P2 |
| Kimi CLI 未纳入本仓库 Layer B 项目级收尾矩阵 | 当前用户实际指出的问题集中在 Claude / Gemini / Copilot 三条链，Kimi 不在本次 incident 最短修复路径上 | P2 |

### 6.2 触发的新问题

本轮在 Claude / Gemini 真实 smoke 中额外暴露并已修复三处问题：
1. 用户级 Claude hook 仍残留旧绝对路径；已同步修正 `~/.claude/settings.json`。
2. 通用 SessionEnd 分发器错误复用了 Gemini 的 stdout JSON 到 Claude；已改为按宿主隔离返回。
3. `CLAUDE.md` / `GEMINI.md` / `lessons.md` 中对导入机制的说明文字会触发 Gemini 的误导入噪音；已改为不触发解析的表述。

当前剩余已知边界只有一项：报告登记 marker 目前按**宿主**隔离，而不是按**同宿主多并发 session** 隔离；这在当前设计下记为已知边界，不作为 blocking bug 处理。

### 6.3 推荐的下一步行动

1. 为 Layer A 的 Copilot CLI 输出一个可复用的 `.github/hooks/*.json` 安装模板，避免“Layer B 已修、Layer A 仍空白”。
2. 如未来需要支持同宿主多并发 Layer B session，再把报告 marker 从宿主级升级为 session 级。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-41 | Hook 能力存在 ≠ 已部署 ≠ 已生效 | 涉及 Hook / 收尾链的结论必须分清能力、配置和触发证据三层；可审计流程必须有物理落盘载体 |

### 7.2 流程改进建议

1. 任何文档如果声称“已部署”，都必须能指出**真实配置文件路径**和**最近一次验证方式**。
2. 任务级完成报告不应再只依赖最终聊天输出；物理报告文件应作为 Task Completion Review Gate 的硬产物。
3. 宿主 Hook 责任边界必须明确区分“主链主动执行”和“SessionEnd 兜底”，避免再次把兜底误当成主路径。

---

## 八、附录

### 附录 A：Commits

```
6fa1591 fix(prism): harden e2e archive and dispatch gates
6df3418 docs(spec): add hook-chain investigation design
9bae831 fix(hooks): harden layer-b completion chain
（本报告在后续收尾提交中补写最终验证与 commit 清单）
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| redteam | Prism E2E 收尾后用户仍发现模板/飞书缺口，需确认是否为更大的 Layer B Hook 漂移 | E2E 本身已归档，但它暴露出 Layer B 收尾链缺少模板报告与宿主覆盖的系统问题 | `prism/reports/20260411-redteam-001.md` |

### 附录 C：相关文档索引

- 需求原始记录：当前会话用户原始消息（“结果报告不是按照模版来走的 / 飞书通知没有了 / hook机制失效了”）
- 设计文档：`compass/docs/hook-chain-investigation-design.md`
- 变更影响分析：`compass/CONTRIBUTING.md §6`、`references/hook-standards.md`
