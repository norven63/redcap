# 任务完成报告：P4-2c CLI 诊断产品面加固

**报告日期**：2026-05-05
**执行者**：Cap（Codex.app + Prism: Kimi / Claude Code）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap CLI 已补上面向外部用户和 Agent 容器的诊断产品面，`doctor`、`debug --json`、`--trace`、`help <command>` 和结构化错误都已进入机器门禁。
- 详情：本轮解决的是“内部脚本能跑，但公共 CLI 不好排障”的发布前阻塞。现在用户可以先用 `redcap doctor` 看人类可读健康摘要，Agent 或支持者可以用 `redcap debug --json` 获取脱敏诊断包，`--trace` 能解释命令路由但不会倾倒环境变量。发布前审判已把 `cli-debug-contract-incomplete` 从 release blocker 改为 pass，但 RedCap 仍未进入正式 public release-ready。

### 0.2 上一步完成的是

- 上一步完成的是：P4-2b 已把 runtime、project workspace、user state 三层边界拆清，CLI 不再默认把 RedCap 自身 `.dev-task.md` 当成外部项目状态。
- 详情：P4-2c 在这个边界之上继续做产品化诊断，确保新增命令也复用同一套 workspace/task-file 解析，而不是另开一套容易漂移的入口。

### 0.3 下一步计划做的是

- 下一步计划做的是：完成全量 acceptance、closeout receipt 和提交；主线下一刀是 P4-2d，处理 public package identity、license 和 package surface 策略。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P4-2a 产品架构审判 → P4-2b 边界拆分 → P4-2c CLI 诊断产品面 → P4-2d 包身份/许可证/包面 → P4-2e 公共 arsenal 口径。
- 当前所在位置：P4-2c 已实现并通过 targeted/spec/Prism 回归，正在执行 full acceptance 和 closeout 收口。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 好的，那么请你和棱镜团队继续稳步推进下面的任务

### 1.2 触发背景

P4-2a 的发布前产品架构审判指出：RedCap 虽然已有 CLI facade 和打包安全门，但仍缺少外部用户能理解的诊断、调试、追踪和帮助入口。这个缺口会让“内部维护者能排障”被误报成“公共 CLI 可用”，所以它被列为 public release 前的 P0 blocker。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 继续推进 RedCap release blocker 主线，不停在 P4-2b 后等待人工催促。 |
| 已覆盖 | 已完成 P4-2c 的 CLI doctor/debug/trace/help/error 产品面、隐私脱敏策略、机器检查器、棱镜复审、targeted/spec 回归和发布前审判更新。 |
| 未覆盖/延期 | P4-2d package identity/license/package surface、P4-2e public arsenal 内容口径、真实 npm publish 均不属于本轮。 |
| 用户可见边界 | 可以声明 CLI 诊断产品面已具备最小 public-ready 支撑；不能声明 RedCap 已 release-ready、已 npm 发布或 public package identity 已最终确定。 |
| 后续路径 | P4-2d 继续处理 public package name、license 与 curated package surface。 |

---

## 二、方案讨论

### 2.1 问题分析

本轮关键不是“多加几个命令名”，而是把 CLI 从内部脚本集合推进到可被外部用户排障的产品面。棱镜共同指出，如果 `doctor` 只是 `diagnose` 改名，或者 `debug --json` 直接吐出现有状态对象，就会泄漏本机路径、身份锚点甚至 host 配置，还会让发布前 blocker 被假修复。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| CLI 产品面 | 直接复用 `diagnose` 输出 | 把内部 gate 输出包一层命令名 | 成本低 | 人类不可读，且容易泄漏本机路径和内部状态 |
| CLI 产品面 | 独立 product surface renderer | `bin/redcap` 只薄路由，独立工具生成 doctor/debug/help/trace | 输出契约稳定，可被 checker 验证 | 需要新增策略、脚本和回归 |
| trace | 使用 shell `set -x` | 让 shell 自动打印执行过程 | 实现简单 | 会泄漏 env、PATH、HOME 和命令细节 |
| trace | allowlist trace | 只打印命令、runtime、workspace、task-file、委托目标 | 安全可控 | 需要维护 allowlist |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| CLI 产品面 | 独立 product surface renderer | 让 public CLI 输出和内部 diagnose 分层，避免“内部日志换皮”。 | Prism + Cap |
| trace | allowlist trace | 只暴露排障所需路由信息，不允许环境倾倒。 | Prism + Cap |
| debug | redacted JSON contract | Agent 容器需要结构化输出，但必须屏蔽本机路径、identity 字段和 secret-like 文本。 | Prism + Cap |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `bin/redcap` | 修改 | 增加 `doctor`、`debug`、`help <command>`、全局/命令内 `--trace` 与结构化错误输出。 |
| `references/cli-product-surface-policy.json` | 新建 | 固化 CLI 产品面契约、脱敏规则、debug JSON 字段、trace allowlist 和错误格式。 |
| `compass/tools/redcap-cli-product-surface.py` / `.sh` | 新建 | 生成 doctor、debug、trace、help 的人类可读/机器可读输出。 |
| `compass/tools/redcap-cli-product-surface-check.py` / `.sh` | 新建 | 验证外部 workspace、自开发模式、缺任务卡、help、trace、typo error 和脱敏输出。 |
| `compass/tools/redcap-runtime-workspace-boundary-check.py` | 修改 | 把 doctor/debug 纳入 P4-2b 边界回归，防止新增命令绕开 workspace/task-file 解析。 |
| `compass/tools/redcap-diagnose.sh` / `redcap-spec-check.sh` | 修改 | 将 CLI 产品面 checker 纳入总诊断和 spec 强门。 |
| `references/execution-guarantees.json` | 修改 | 新增 `cli-product-surface-gate`，让执行保障能追踪本轮能力。 |
| `references/pre-release-product-architecture-review.json` | 修改 | 将 CLI debug blocker 改为 pass，并更新真实 package candidate count。 |
| `references/file-lookup-dictionary.md` / `.json` | 修改 | 将新策略、实现和检查器纳入文件查找字典。 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 新增 CLI 产品面 acceptance case，并把 spec-check 传播门接入新 gate。 |
| `prism/runs/20260505-cli-diagnostic-product-surface-review/**` | 新建/更新 | 保存设计审查、实现复审与 acceptance 绑定证据。 |

### 3.2 技术实现要点

`bin/redcap` 保持薄入口：它只负责解析 runtime root、workspace root、task file 和命令路由；真正的输出格式由 `redcap-cli-product-surface.py` 管理。这样做的效果是，未来 CLI 包装方式变化时，用户可见契约仍由一个产品面工具维护，而不是散落在 bash case 里。

`debug --json` 的设计重点是“够用但不泄漏”：它保留 task id、boundary mode、任务卡状态和检查结果，但不输出 `identity_file`、`agent_name`、`.cap`、真实 home path 或 secret-like 字段。`--trace` 也只打印 allowlist 字段，不使用 `set -x`，避免把 shell 环境当成排障日志。

`doctor` 不复用内部 `diagnose` 的长门禁输出，而是给出整体状态、workspace/task-card 状态、最多五条优先级发现和下一步建议。缺少 `.dev-task.md` 时，它会降级说明“项目尚未初始化/未指定任务卡”，而不是崩溃或偷偷回退到 RedCap 自身任务卡。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| CLI 产品面 | `redcap doctor/debug/help/--trace` | 用户真正会接触的命令体验：看状态、导出诊断、理解路由、获得帮助。 |
| doctor | `redcap doctor` | 给人看的健康检查摘要，不是内部门禁流水账。 |
| debug JSON | `redcap debug --json` | 给支持者或 Agent 容器看的结构化诊断包，必须脱敏。 |
| trace allowlist | `redcap --trace <command>` | 只解释命令如何路由，不打印 shell 环境或 secret。 |
| workspace boundary | `runtime-workspace-boundary` | 区分 RedCap 工具所在目录和被 RedCap 管理的项目目录。 |

### 3.3 关联变更

发布前产品架构审判随本轮事实更新：`cli_has_doctor_command`、`cli_has_debug_command`、`cli_has_trace_option` 均改为 true，`cli-debug-contract-incomplete` 改为 pass。由于新增工具文件进入 npm candidate surface，package candidate count 从 207 更新为 212。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | P4-2d 是否进入下一轮 | 这是下一主线任务的时机选择，不影响 P4-2c 本轮收口。 | P1 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 语法检查 | `bash -n bin/redcap && python3 -m py_compile compass/tools/redcap-cli-product-surface.py compass/tools/redcap-cli-product-surface-check.py` | ✅ |
| CLI 产品面 | `bash compass/tools/redcap-cli-product-surface-check.sh` | ✅ |
| P4-2b 边界回归 | `bash compass/tools/redcap-runtime-workspace-boundary-check.sh` | ✅ |
| 发布前产品审判 | `bash compass/tools/redcap-pre-release-product-architecture-check.sh` | ✅ |
| 执行保障 | `bash compass/tools/redcap-execution-guarantee-check.sh` | ✅ |
| 文件查找字典 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | ✅ |
| acceptance：CLI 产品面 | `bash compass/tools/redcap-multi-session-acceptance.sh cli-product-surface-check` | ✅ |
| acceptance：边界回归 | `bash compass/tools/redcap-multi-session-acceptance.sh runtime-workspace-boundary-check` | ✅ |
| acceptance：发布前审判 | `bash compass/tools/redcap-multi-session-acceptance.sh pre-release-product-architecture-check` | ✅ |
| acceptance：spec 传播 | `bash compass/tools/redcap-multi-session-acceptance.sh spec-check-propagates-control-gate-failures` | ✅ |
| umbrella spec | `bash compass/tools/redcap-spec-check.sh "$PWD"` | ✅ |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 是否立即启动 P4-2d；这属于下一任务节奏，不是 P4-2c 的完成条件。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 收口前仍在核对；closeout 后更新 |
| 棱镜验收 | 通过：Kimi 与 Claude Code 实现复审均为 pass，binding 已通过 `redcap-prism-acceptance-check.sh` |
| closeout summary | 收口后生成 |
| closeout receipt | 收口后生成 |
| rescue audit（如有） | 当前无 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是；Prism acceptance 已通过 |
| 已正式完成 | 否；receipt 尚未生成 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| public package identity / license / package surface | 属于 P4-2d，不应和 P4-2c 混报。 | P0-before-public-release |
| runtime physical split | 仍是 release blocker，P4-2c 不负责物理 runtime 拆分。 | P0-before-public-release |
| public arsenal substantive content | 当前 arsenal 仍是 template-only，不能宣传为已有实质公共知识库。 | P1-before-broad-marketing |

### 6.2 触发的新问题

无新增 release blocker。棱镜设计审查阶段指出的 trace、debug 脱敏、错误契约和薄入口维护问题已在本轮实现中覆盖。

### 6.3 推荐的下一步行动

1. 收口 P4-2c receipt 后，进入 P4-2d：确认 public package identity、license、package surface 以及是否继续保持 private/readiness-only。
2. 保持 RedCap 不声明 public-release-ready，直到剩余 release blocker 被真实消除或明确降级。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-153 | CLI 诊断产品面不能复用内部门禁流水账 | public CLI 的 doctor/debug/trace 要有独立契约、脱敏和人类可读输出，不能把内部 diagnose 换名后交给用户。 |

### 7.2 流程改进建议

发布前 blocker 的修复必须同步更新“事实面”和“审判面”：只实现命令不够，pre-release review、execution guarantees、spec-check、acceptance 和文件字典也要一起吃到新事实。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选 | 本轮属于既有 release blocker remediation | no-promote；经验沉淀到 L-153，不新增 Evolution candidate | `compass/knowledge/lessons.md` |

---

## 八、附录

### 附录 A：Commits

```
收口提交后更新
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| design-review | P4-2c CLI 产品面方案审查 | Kimi 与 Claude Code 均为 pass-with-required-changes，要求补齐脱敏、trace allowlist、错误契约和 workspace 回归 | `prism/runs/20260505-cli-diagnostic-product-surface-review/collect/*/raw.txt` |
| implementation-review | P4-2c 实现后复审 | Kimi 与 Claude Code 均为 pass，未发现 blocker | `prism/runs/20260505-cli-diagnostic-product-surface-review/collect/*/followup-raw.txt` |

### 附录 C：相关文档索引

- 当前任务卡：`.dev-task.md`
- 产品面策略：`references/cli-product-surface-policy.json`
- 发布前产品审判：`references/pre-release-product-architecture-review.json`
- 文件查找字典：`references/file-lookup-dictionary.md`
