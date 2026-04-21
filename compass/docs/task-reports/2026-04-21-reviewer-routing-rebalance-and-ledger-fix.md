# 任务完成报告：reviewer 选型重排与账面补锚

**报告日期**：2026-04-21
**执行者**：Cap（Codex / GPT-5.4）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：Copilot / Codex 的静态优先级限制已经去除，reviewer / stop-review 默认排序已统一收敛到“模型能力画像 + 本地 CLI 稳定性”这套机器真相源。
- 详情：新增了 `compass/tools/redcap-reviewer-order.py`，修正并扩充了 `compass/knowledge/model-capability-matrix.yaml`，同步更新了 `compass/CONTRIBUTING.core.md`、`loom/dispatcher/agent-adapters.md` 与 `compass/knowledge/lessons.md`。`.dev-task.md` 也已补成合法 canonical task ledger，三条 stop-review targeted acceptance、`spec-check`、`diagnose`、`git diff --check` 与 `current-status` 均已通过。

### 0.2 上一步完成的是

- 上一步完成的是：先补齐 `.dev-task.md` 的 canonical task ledger，再把 stop-review acceptance 夹具从真实宿主 compat fallback 印章中隔离出来，最终拿到三条 targeted acceptance 绿灯。

### 0.3 下一步计划做的是

- 下一步计划做的是：若继续治理，则转去处理非本轮 blocker 的长期债务，例如 GD-008（主 Agent 实时行为约束仍属 host-limited）与 GD-009（首读/诊断链尚未 read-only-safe）。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：锁定任务锚点 → 改 reviewer 排序真相源 → 接 stop-review → 跑 targeted acceptance → 盘点遗留项。
- 当前所在位置：`reviewer-routing-rebalance` 已完成，处于“已收口、待后续 tranche 决定是否继续治理宿主边界债务”的终局态。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 1. 把copilot/codex的优先级限制去除掉，然后所有模型都改为“业内对此模型的能力评估、适用场景评论”+“本地此Agent工具的运行稳定性”综合作为优先级考量。  
> 2. 现在工作区还有遗留未落地的todo或者任务吗？

### 1.2 触发背景

此前 reviewer 选择口径存在两种历史偏置：一边是 live 修补后留下的 `codex` 宿主优先顺序，一边是文档里“优先 Gemini/Kimi CLI”的旧说法。它们都不再适合作为长期默认规则，而且会让 stop-review、Prism 与文档解释互相打架。

---

## 二、方案讨论

### 2.1 问题分析

问题本质不是“把某个 CLI 提上去”这么简单，而是要把 reviewer 选择从历史补丁式经验，收敛成一套机器可消费、脚本与文档共享的默认算法。同时，本轮还暴露出一个更底层的账面缺口：旧 `.dev-task.md` 不再满足 `pm-gate` 的 canonical task ledger 约束。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 选项 A | 只改文档，不改 stop-review 脚本 | 风险小 | 真实行为不变，属于伪完成 |
| Q1 | 选项 B | 直接在 stop-review 里手写新顺序 | 改动快 | 仍然没有统一真相源，后续容易再漂移 |
| Q1 | 选项 C | 用能力矩阵 + 本地稳定性画像作为机器真相源，stop-review 读取它生成 reviewer 顺序 | 文档与脚本收敛到同一套规则 | 需要补 helper、补回归 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 选项 C | 只有把默认 reviewer 排序改成机器可消费的统一真相源，才能真正去掉静态偏置 | CAP_DECIDE |
| Q2 | 伴随补丁 | `.dev-task.md` 旧格式已真实阻断 validator chain，必须一起修复 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `.dev-task.md` | 修改 | 切换到本轮 reviewer-routing 任务，并补 canonical task ledger 必填段 |
| `compass/docs/catalog.json` | 修改 | 重新生成 docs catalog，纳入本轮 task report |
| `compass/tools/redcap-reviewer-order.py` | 新建 | 读取能力矩阵与本地 registry，生成 reviewer 候选顺序 |
| `compass/tools/redcap-on-stop-review.sh` | 修改 | 改为按 `{cli}@{model}` 目标执行 reviewer，并在 stop-review 中接入动态排序 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 新增/替换 stop-review 的动态排序回归用例 |
| `compass/knowledge/model-capability-matrix.yaml` | 修改 | 修正矩阵结构，新增 reviewer CLI 本地稳定性画像 |
| `loom/dispatcher/agent-adapters.md` | 修改 | 同步统一路由算法说明 |
| `compass/CONTRIBUTING.core.md` | 修改 | 去掉静态压低 Copilot/Codex 的旧口径 |
| `compass/knowledge/lessons.md` | 修改 | 归档 reviewer 排序不能长期继承历史偏置的新 Lesson |

### 3.2 技术实现要点

这轮把 reviewer 选择提升到 `{cli}&{model}` 粒度，不再只看 CLI 名字。`redcap-reviewer-order.py` 读取能力矩阵里的模型能力评分与 reviewer CLI 稳定性画像，再叠加本地 registry 的可用性与已知问题，输出 stop-review 的默认顺序。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| reviewer 路由真相源 | `compass/knowledge/model-capability-matrix.yaml` | 默认 reviewer 该怎么选，现在由这份机器文件说了算 |
| 本地 CLI 稳定性画像 | `reviewer_cli_profiles` | 不是模型强不强，而是这台机器上这个 CLI 做 headless review 稳不稳 |
| canonical task ledger | `.dev-task.md` | 当前任务的唯一执行真相源；缺关键段会让收尾链直接 fail-closed |

### 3.3 遗留项盘点结论

当前工作区已经没有本轮任务级 blocker，也没有未落地的当前 backlog 项。剩余项目需要诚实拆成三类：

| 分类 | 当前状态 | 是否阻断本轮收口 |
|------|---------|----------------|
| 当前任务级 blocker | 无 | 否 |
| 长期治理债务 | `GD-008`、`GD-009` 仍在 | 否 |
| 历史证据残留 | `prism/runs` 仍保留 19 个运行目录 | 否 |

补充说明：`references/backlogs/framework-upgrade.json` 当前 19/19 全部为 `done`，因此不存在“这轮 reviewer-routing 其实还挂着某个长期 backlog 子项没落地”的情况。

---

## 四、人工审核要点

本轮没有当前任务级 P0 / P1 人工 gate。若要继续推进后续治理，真正需要人工拍板的是：是否投入下一 tranche 处理 GD-008 / GD-009，而不是本轮 reviewer 排序补丁本身。

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| shell 语法检查 | `bash -n compass/tools/redcap-on-stop-review.sh && bash -n compass/tools/redcap-multi-session-acceptance.sh` | ✅ |
| reviewer 排序器 smoke | `python3 compass/tools/redcap-reviewer-order.py --matrix compass/knowledge/model-capability-matrix.yaml --registry compass/.workflow/agent-registry.yaml` | ✅ |
| stop-review fallback acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-falls-back-to-codex-after-unavailable-reviewers` | ✅ |
| stop-review codex 排名 acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-prefers-codex-when-best-ranked` | ✅ |
| stop-review copilot 排名 acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh on-stop-review-prefers-copilot-premium-model-over-lighter-clis` | ✅ |
| repo 级规范校验 | `bash compass/tools/redcap-spec-check.sh "$PWD"` | ✅ |
| 诊断总览 | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | ✅ |
| diff 空白/格式检查 | `git diff --check` | ✅ |
| 当前状态汇总 | `bash compass/tools/redcap-current-status.sh .dev-task.md` | ✅（`status: clear`） |

### 5.2 人工验证项（Cap 无法自动化验证的）

无当前任务级必须人工补跑项。

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| GD-008：主 Agent 实时行为约束仍属 host-limited | 当前 Codex.app 等宿主未暴露 repo-owned pre-reply veto | P1 |
| GD-009：首读/诊断链尚未 read-only-safe | `current-status / diagnose / docs-catalog` 仍依赖可写临时目录 | P1 |
| `prism/runs` 仍保留 19 个目录 | 这些是历史运行证据，不应在本轮 reviewer-routing 补丁里顺手物理清理 | P2 |

### 6.2 触发的新问题

旧 `.dev-task.md` 旧格式已经被证明不是“文档洁癖”问题，而是会物理拦住 stop-review 的真实 blocker。该问题已在本轮被修复并沉淀为新的治理经验。

### 6.3 推荐的下一步行动

1. 若后续要继续提质，优先开一条治理 tranche 处理 GD-008 / GD-009。
2. `prism/runs` 若要物理清理，应单开证据生命周期任务，而不是在本轮 reviewer-routing 补丁里混做。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-105 | reviewer 选型不能长期继承历史偏置 | reviewer 默认排序应统一回到“模型能力 + 本地稳定性”的机器真相源 |

### 7.2 流程改进建议

当 stop-review / validator chain 升级 canonical task ledger 约束时，要尽快把当前 `.dev-task.md` 一并迁到新格式，否则会出现“代码逻辑改好了，但 reviewer 根本走不到”的假故障。

---

## 八、附录

### 附录 A：Commits

```text
尚未提交；当前为工作区内治理补丁，已完成验证并处于可提交状态。
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| 无 | 本轮未启动 formal Prism | 当前为 repo-owned 治理补丁与 targeted acceptance 收口 | 无 |

### 附录 C：相关文档索引

- 需求原始记录：`.dev-task.md`
- 能力矩阵：`compass/knowledge/model-capability-matrix.yaml`
- stop-review 脚本：`compass/tools/redcap-on-stop-review.sh`
