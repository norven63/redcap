# 任务完成报告：P4-3 clean workspace / cross-machine install E2E

**报告日期**：2026-05-01  
**执行者**：Cap（Codex.app 主 Agent）  
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P4-3 clean workspace / cross-machine install E2E 已正式 closeout，clean clone 证据和 closeout runtime receipt 都已经生成。
- 重要修正：`.dev-task.md` 被纠正为运行时任务输入，不再被 execution guarantees 当成 clean clone 必备仓库资产；E2E receipt 已做本机路径脱敏，避免把 `/Users/**`、macOS 临时目录或密钥片段泄漏成可提交证据。
- 当前边界：P4-3 可以声明完成；父任务仍因 P4-2 public release / package publish 保持 incomplete。

### 0.2 上一步完成的是

- 上一步完成的是：P4-1 delete-last / canonical switch 已 closeout；父任务仍因 P4-2 public release 与 P4-3 clean workspace E2E 未完成而保持 incomplete。

### 0.3 下一步计划做的是

- 下一步计划做的是：不再继续扩张本轮 P4-3；父任务剩余唯一边界是 P4-2 public release / package publish，需要 Norven 对 registry、包名、凭据与发布边界做保留决策后才能推进。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：PM Gate 重锚 P4-3 → clean clone E2E 工具 → spec/diagnose/acceptance 接线 → machine-readable E2E receipt → Prism review → parent aggregation 更新 → full regression → closeout receipt。
- 当前所在位置：P4-3 已完成 closeout；父任务线仍停在 P4-2 blocked-external，因此不能声明父任务整体完成。

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
| Prism 初审发现 receipt 路径泄漏 | `stdout_excerpt`、`commands[].cwd`、`source_repo_path` 曾包含本机/临时绝对路径 | 新增 receipt redaction 与 committed-result 私密路径拒绝校验，并重新生成正式 receipt |
| Prism 初审发现 E2E 未独立登记进 execution guarantees | E2E 只通过 spec/diagnose/acceptance 间接存在 | 新增 `clean-workspace-install-e2e` execution guarantee，并同步 REQUIRED_IDS |

---

## 三、落地结果

| 项目 | 结果 |
|------|------|
| clean workspace E2E 工具 | 已新增，支持正式 clean HEAD 验收与本地 dirty snapshot 调试 |
| revive/install 验证 | 正式 receipt 已证明隔离 HOME/runtime/identity 下可通过 |
| CLI facade 验证 | `status`、`publish-safety`、`package-manifest` 已纳入 E2E |
| package 安全边界 | 候选包清单不包含 `.env`、宿主私密入口、runtime evidence、Prism runs、redcap-knowledge |
| 执行保障修正 | `.dev-task.md` 从仓库资产改为运行时输入，防止 clean clone 首启失败 |
| receipt 安全边界 | 本机仓库路径、临时 clone、临时 HOME/runtime/identity、candidate list 与命令输出已脱敏 |
| 回归接线 | 已接入 `spec-check`、`diagnose`、execution guarantees、File Lookup Dictionary 与 acceptance targeted case |
| parent aggregation | P4-3 已移入 completed child；P4-2 继续 blocked-external，因此父任务整体仍 incomplete |

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| clean workspace E2E | `redcap-clean-workspace-e2e.sh` | 在临时干净克隆里模拟“新工作区第一次打开 RedCap”，避免拿当前已初始化工作区冒充跨环境验证 |
| isolated HOME/runtime/identity | E2E 临时目录与环境变量 | E2E 不读取真实家目录、真实 Cap identity、真实 runtime evidence 或真实飞书配置 |
| dirty snapshot | `--allow-dirty` 调试模式 | 只给开发中自测使用；会把未提交修改做成临时快照提交，但不能写成正式 receipt |
| formal E2E receipt | `references/clean-workspace-install-e2e.json` | 可机器复验的 P4-3 证据，记录 clean HEAD、命令结果、包候选和安全边界 |
| runtime_source_paths | `references/execution-guarantees.json` | 表示 `.dev-task.md` 这类本地任务卡是运行时输入，不是 clean clone 必须带走的仓库文件 |
| parent aggregation | `references/parent-receipt-aggregation-policy.json` | 父任务视图：P4-3 可完成，但 P4-2 public release 未完成时父任务整体仍不能完成 |
| resource-limited Prism | Prism acceptance binding | 至少一个 reviewer 真实通过，另一个 provider 超时/不可用被诚实记录；不冒充 formal multi-family quorum |

---

## 四、人工审核要点

本轮没有需要 Norven 立即决策的 blocker。需要注意的是：P4-3 只关闭 clean workspace / cross-machine install E2E；P4-2 的真实 public release / package publish 仍涉及 registry、包名、凭据与发布边界，所以父任务整体仍不能声明完成。

## 五、验证结果

| 验证项 | 命令 | 结果 |
|--------|------|------|
| PM Gate / intent / change intake | `bash compass/tools/redcap-pm-gate-check.sh strict codex .dev-task.md && bash compass/tools/redcap-intent-coverage-check.sh .dev-task.md && bash compass/tools/redcap-change-intake-check.sh .dev-task.md --mode closeout` | 通过 |
| execution guarantees targeted | `bash compass/tools/redcap-multi-session-acceptance.sh execution-guarantees-check` | 通过 |
| clean workspace E2E targeted | `bash compass/tools/redcap-multi-session-acceptance.sh clean-workspace-e2e-check` | 通过 |
| spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| 正式 clean HEAD E2E receipt | `bash compass/tools/redcap-clean-workspace-e2e.sh --write-result --check-result --timeout 180` | 通过，npm_pack_dry_run=true |
| receipt 复验 | `bash compass/tools/redcap-clean-workspace-e2e.sh --check-result` | 通过 |
| path leak scan | `rg -o '/Users/|/private/var/folders|/var/folders|norven|KIMI_API_KEY|GEMINI_API_KEY|AIza|cli_a957|Uer56' references/clean-workspace-install-e2e.json` | 无命中 |
| Execution guarantees | `bash compass/tools/redcap-execution-guarantee-check.sh` | 通过 |
| File Lookup Dictionary | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | 通过，required_paths=165 |
| Prism 独立评审 | Claude 初审 + Kimi 初审/复审 + acceptance binding | 初审发现 2 个 blocker，已修复；最终为 resource-limited-pass，不冒充 formal quorum |
| diagnose / full acceptance | `bash compass/tools/redcap-diagnose.sh .dev-task.md`、`bash compass/tools/redcap-multi-session-acceptance.sh all` | 通过 |

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 已清：promises_total=6，promises_pending=0 |
| 棱镜验收 | 已绑定为 resource-limited-pass |
| closeout summary | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/summaries/redcap-clean-workspace-install-e2e-ff345b2c03b485832c942a8583638295027c38569db3a899ef12b47a3c765efd.md` |
| closeout receipt | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/redcap-clean-workspace-install-e2e-ff345b2c03b485832c942a8583638295027c38569db3a899ef12b47a3c765efd.json` |
| rescue audit（如有） | 发生过一次 closeout 前阻塞审计，已由后续 closeout complete 解除；最终状态 completed |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | targeted、spec、diagnose 与 full acceptance 已过 |
| 已独立验收 | 是，Prism 初审抓到并推动修复 blocker；Kimi 复审通过，Claude 最终复审超时按 resource-limited 记录 |
| 已正式完成 | 是，closeout runtime receipt 已生成；父任务仍因 P4-2 保持 incomplete |

---

## 六、遗留问题与下一步

| 边界 | 说明 |
|------|------|
| P4-2 public release | 仍需用户决策 registry、包名、凭据和发布边界；本轮不越权执行 |
| P4-3 正式 receipt | 已生成 E2E receipt 与 closeout runtime receipt，本轮 child 任务可声明完成 |
| 父任务整体完成 | P4-3 完成后仍不可声明父任务 complete，除非 P4-2 也完成或用户改变发布边界 |

---

## 七、经验沉淀

| 候选 | 来源 | 当前处理 |
|------|------|----------|
| 本地任务卡不是仓库资产 | clean clone revive 失败暴露 | 已转为 `runtime_source_paths` 机制，后续可沉淀为 lesson |
| dirty debugging 不等于正式 E2E | `--allow-dirty` 原设计测不到未提交补丁 | 已改为 dirty snapshot，仅作调试；正式 result 必须来自 clean source |
| 机器 receipt 也要脱敏 | Prism 初审发现本机路径出现在 receipt 摘要里 | 已把路径脱敏和泄漏拒绝写进 checker，适合沉淀为 lesson |

### 7.3 Evolution Factory 候选处理

结论：无新增候选留待人工评审；本轮暴露出的三个经验候选都已经直接晋升为机器约束、checker 或 execution guarantee。

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 本地任务卡不是仓库资产 | clean clone revive 失败 | 已直接晋升为 execution guarantee 机制：`source_paths` 与 `runtime_source_paths` 分离 | `references/execution-guarantees.json`、`redcap-execution-guarantee-check.py` |
| dirty snapshot 不能冒充正式 E2E | `--allow-dirty` 调试模式设计缺陷 | 已直接落成 checker 规则：committed result 必须来自 clean source，dirty snapshot result 不可通过 `--check-result` | `redcap-clean-workspace-e2e.py` |
| machine receipt 必须脱敏 | Prism 初审发现本机路径泄漏 | 已直接落成 receipt redaction 与 private-path leak validator；无需进入候选池等待后续人工筛选 | `references/clean-workspace-install-e2e.json`、`redcap-clean-workspace-e2e.py` |

---

## 八、附录

### 附录 A：Commits

```text
aaea015 feat(clean-workspace): 建立P4-3安装E2E
d7af7e0 fix(clean-workspace): 脱敏P4-3安装E2E收据
ca5776f fix(clean-workspace): 允许治理证据后置对账
9b38f19 feat(parent): 完成P4-3干净工作区E2E
8d607a7 fix(clean-workspace): 复用发布安全禁止清单
786895a test(clean-workspace): 刷新P4-3正式E2E收据
18e061d docs(clean-workspace): 补齐P4-3收口报告门禁
0972ec3 docs(clean-workspace): 补齐P4-3人工审核要点
```

### 附录 B：棱镜调用记录

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| Claude + Kimi 初审 | clean workspace E2E 是否存在 false positive、泄密、父任务混报风险 | 发现 execution guarantee 未独立登记与 receipt 路径泄漏；均已修复 | `prism/runs/20260501-redcap-clean-workspace-install-e2e/collect/*/raw-initial.txt` |
| Kimi 修复后复审 | 两个 blocker 是否修复、是否仍混报父任务 | 确认初审 blocker 已修复，同时要求 E2E receipt 入库、P4-3 parent aggregation 切 completed；本报告已纳入收口 | `prism/runs/20260501-redcap-clean-workspace-install-e2e/collect/kimi-reviewer/raw.txt` |
