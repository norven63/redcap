# 任务完成报告：P4-3 clean workspace / cross-machine install E2E

**报告日期**：2026-05-01  
**执行者**：Cap（Codex.app 主 Agent）  
**报告版本**：v0.1

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P4-3 已进入 Layer B 任务卡，clean workspace E2E 工具已建立，并在本地 dirty snapshot 调试模式中证明隔离 clean clone 可以完成 revive、CLI status、publish safety 与 package manifest。
- 重要修正：`.dev-task.md` 被纠正为运行时任务输入，不再被 execution guarantees 当成 clean clone 必备仓库资产；否则首次安装环境会因缺少本地任务卡而失败。

### 0.2 上一步完成的是

- 上一步完成的是：P4-1 delete-last / canonical switch 已 closeout；父任务仍因 P4-2 public release 与 P4-3 clean workspace E2E 未完成而保持 incomplete。

### 0.3 下一步计划做的是

- 下一步计划做的是：把 E2E receipt、Prism 独立评审、parent aggregation、文件字典和执行保障补齐后提交，并由 closeout runtime 生成正式 receipt。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：PM Gate 重锚 P4-3 → clean clone E2E 工具 → spec/diagnose/acceptance 接线 → machine-readable E2E receipt → Prism review → parent aggregation 更新 → full regression → closeout receipt。
- 当前所在位置：实现与 targeted 回归正在推进，尚未进入最终 closeout。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 好的，那么请继续推进RedCap的父任务线，务必要和棱镜团队之间配合好，稳步迭代、谨慎评审与验收。并且，如果过程中没有“必须”要我人工介入决策的地方，禁止中途停止，你和棱镜团队需要按照redcap的开发工作流一直把所有任务都完成为止。

### 1.2 范围判断

父任务剩余项中，P4-2 是真实 public release / package publish，涉及 registry、包名、凭据、发布目标和分发边界，属于人工保留决策。本轮不能越权发布，也不能把 package readiness 或 npm dry-run 冒充真实发布。

P4-3 可以在本机通过临时 clean clone、隔离 HOME、隔离 runtime base 和隔离 identity 文件来验证“首次打开/跨环境安装”的主要风险。因此本轮目标是关闭 P4-3，并保持父任务整体因 P4-2 继续 incomplete。

---

## 二、方案讨论

本轮选择“干净克隆 + 隔离运行时”的 E2E，而不是在当前工作区重复执行 revive。原因很简单：当前工作区已经有本地 identity、runtime、缓存和任务卡，直接跑成功不能证明新机器或新工作区可用。

核心设计是：

- 用 `git clone --no-hardlinks` 创建临时 clean clone，正式验收只允许测试已提交 HEAD。
- 用临时 `HOME`、`REDCAP_IDENTITY_FILE`、`REDCAP_RUNTIME_PROJECT_BASE_DIR` 隔离本地身份和运行时状态。
- 在 clean clone 中运行 `./revive-cap.sh --host codex --init-identity`、`bin/redcap status`、`bin/redcap publish-safety`、`bin/redcap package-manifest --check`。
- 记录 JSON receipt，后续由 `spec-check`、`diagnose`、acceptance 和 parent aggregation 复验。

### 2.1 过程中新发现并修复的问题

| 问题 | 根因 | 处理结果 |
|------|------|----------|
| clean clone 中 revive 失败 | execution guarantees 把本地 `.dev-task.md` 作为仓库必备 `source_paths` | 新增 `runtime_source_paths`，把本地任务卡定义为运行时输入，只校验路径安全，不要求 clean clone 内存在 |
| `--allow-dirty` 调试模式测不到未提交补丁 | 原实现允许源工作区脏，但 clean clone 仍 checkout 已提交 HEAD | 调试模式改为把当前工作树应用成临时 clean snapshot commit；正式模式仍只接受真实已提交 HEAD |

---

## 三、落地结果

| 项目 | 结果 |
|------|------|
| clean workspace E2E 工具 | 已新增，支持正式 clean HEAD 验收与本地 dirty snapshot 调试 |
| revive/install 验证 | 已在隔离 HOME/runtime 下通过调试模式；正式 receipt 待提交后生成 |
| CLI facade 验证 | `status`、`publish-safety`、`package-manifest` 已纳入 E2E |
| package 安全边界 | 候选包清单不包含 `.env`、宿主私密入口、runtime evidence、Prism runs、redcap-knowledge |
| 执行保障修正 | `.dev-task.md` 从仓库资产改为运行时输入，防止 clean clone 首启失败 |
| 回归接线 | 已接入 `spec-check`、`diagnose` 与 acceptance targeted case |

---

## 四、验证结果

| 验证项 | 命令 | 结果 |
|--------|------|------|
| PM Gate / intent / change intake | `bash compass/tools/redcap-pm-gate-check.sh strict codex .dev-task.md && bash compass/tools/redcap-intent-coverage-check.sh .dev-task.md && bash compass/tools/redcap-change-intake-check.sh .dev-task.md --mode closeout` | 通过 |
| execution guarantees targeted | `bash compass/tools/redcap-multi-session-acceptance.sh execution-guarantees-check` | 通过 |
| clean workspace E2E targeted | `bash compass/tools/redcap-multi-session-acceptance.sh clean-workspace-e2e-check` | 通过 |
| spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| 正式 clean HEAD E2E receipt | 待提交后运行 `bash compass/tools/redcap-clean-workspace-e2e.sh --write-result --check-result` | 待生成 |
| Prism 独立评审 | 待调用可用 provider | 待完成 |
| diagnose / full acceptance | 待正式 receipt 和 parent aggregation 更新后执行 | 待完成 |

### 4.1 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 待 closeout runtime 同步 |
| 棱镜验收 | 待 Prism review artifact 生成 |
| closeout summary | 待提交后生成 |
| closeout receipt | 待提交后生成 |
| rescue audit（如有） | 暂无 |

### 4.2 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 进行中 |
| 已自检 | targeted 自检已过 |
| 已独立验收 | 待 Prism |
| 已正式完成 | 否，待正式 clean HEAD receipt 与 closeout runtime |

---

## 五、遗留边界与下一步

| 边界 | 说明 |
|------|------|
| P4-2 public release | 仍需用户决策 registry、包名、凭据和发布边界；本轮不越权执行 |
| P4-3 正式 receipt | 必须在实现提交后用 clean HEAD 运行，避免脏工作树结果冒充正式跨环境验证 |
| 父任务整体完成 | P4-3 完成后仍不可声明父任务 complete，除非 P4-2 也完成或用户改变发布边界 |

---

## 六、经验沉淀候选

| 候选 | 来源 | 当前处理 |
|------|------|----------|
| 本地任务卡不是仓库资产 | clean clone revive 失败暴露 | 已转为 `runtime_source_paths` 机制，后续可沉淀为 lesson |
| dirty debugging 不等于正式 E2E | `--allow-dirty` 原设计测不到未提交补丁 | 已改为 dirty snapshot，仅作调试；正式 result 必须来自 clean source |

---

## 七、附录

### 附录 A：Commits

```text
待提交本轮最终变更
```

### 附录 B：棱镜调用记录

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| 待执行 | clean workspace E2E 是否存在 false positive、泄密、父任务混报风险 | 待评审 | `prism/runs/20260501-redcap-clean-workspace-install-e2e/` |
