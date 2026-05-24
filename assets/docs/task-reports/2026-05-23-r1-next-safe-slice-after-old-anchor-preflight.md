# 任务完成报告：P4-20 发布准备下一安全切片选择

**报告日期**：2026-05-23
**执行者**：Cap（Codex.app 主执行，Prism 使用 Claude Code + Kimi；Copilot 按保护策略未调用）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：P4-20 已完成下一条发布前安全切片的路线选择。Claude Code 建议回到 `internal-control-plane`，Kimi 建议先做旧报告入口别名/查询网关；Cap 裁决下一步登记为 P4-21，选择 `internal-control-plane` 的非破坏性 support-copy-first 续切片。
- 详情：本轮只完成路线裁决和下一任务登记，没有执行 P4-21 本身，也没有修改发布开关、删除旧报告或清理 raw evidence。

### 0.2 上一步完成的是

- 上一步完成的是：P4-19 证明旧 `prism/reports` 入口现在不能直接退休，原因是后冻结报告、旧路径引用、别名/查询契约和人工授权边界还没有闭合。

### 0.3 下一步计划做的是

- 下一步计划做的是：自动进入 P4-21，挑选 `internal-control-plane` 中一个最小、非破坏、可回滚、可机器检查的 support-copy-first 子切片继续推进。旧报告入口别名/查询网关保留为后续候选。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P4-18 发布差距地图 → P4-19 旧报告入口退休预检 → P4-20 下一安全切片路线裁决 → P4-21 internal-control-plane 非破坏性续切片。
- 当前所在位置：framework-upgrade / P4-20 已完成路线裁决；正式公开发布仍保持 blocked。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要
- 说明：P4-20 没有触碰任何人工硬门。只有当后续要正式发布、选择许可证、使用 registry 凭据、删除旧报告、清理 raw evidence 或裁决 Layer A 产品边界时，才需要 Norven 人工决策。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> “就是现在的状态是，你总是中途停顿下来，需要我人工机械的回复“好的，请你们继续”，但其实这根本不需要中断，完全可以由你和棱镜自动续上。并且，我经常会不在电脑旁，导致无法及时响应来回复这段机械的指令，你就会等很久才会继续推进，极大的延缓了项目推进速度”

### 1.2 触发背景

P4-19 收口后，父任务自动续跑门提示下一条 pending 项是 P4-20。P4-20 的任务不是“继续大改”，而是先决定下一条最安全、最有价值、不会越过人工硬门的发布准备切片。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | partial-with-explicit-defer |
| 原始意图 | 无人工硬门时，Cap/Prism 应自动续上父任务线，不再停下来等机械“继续” |
| 已覆盖 | P4-20 已按 parent-autocontinue 自动续跑，并登记下一条 P4-21 |
| 未覆盖/延期 | P4-21 实现、正式发布、许可证/registry/发布级别决策、破坏性删除、raw evidence cleanup、Layer A 产品裁决 |
| 后续路径 | 已登记 P4-21；人工硬门候选继续保留在 manifest 的 deferred candidates 中 |

---

## 二、方案讨论

### 2.1 候选路线

| 候选 | 人话解释 | 是否自动推进 |
|---|---|---|
| A：internal-control-plane 续切片 | 回到正式发布前更大的工程 blocker，但只做非破坏性 support-copy-first 小切片 | 可以 |
| B：旧报告入口别名/查询网关 | 直接承接 P4-19，补未来退休旧报告入口前必须有的兼容入口 | 可以，但本轮未选 |
| C：raw evidence 清理 | 可能减少本地残留，但会碰审计证据 | 不可以，需要人工授权 |
| D：Layer A 产品边界 | 决定产品范围 | 不可以，Norven 保留决策 |
| E：正式 npm/CLI 发布 | 真正发布到外部 registry | 不可以，需要许可证、凭据、发布级别等人工决策 |

### 2.2 收敛结论

选择 A。理由是：P4-19 已经把旧报告风险安全停住，如果继续只做旧报告链路，会让 RedCap 陷入局部治理循环；而 `internal-control-plane` 仍是正式发布前更大的工程 blocker。选择 A 不代表允许大拆大改，P4-21 必须继续保持非破坏、小切片、可回滚。

---

## 三、落地结果

### 3.1 本轮完成了什么

本轮把“下一步做什么”从口头判断变成了可检查的 route manifest。manifest 记录了候选矩阵、棱镜分歧、Cap 裁决、禁止声明和下一任务登记，避免后续把“选好了下一步”误报成“下一步已经完成”。

### 3.2 关键产物

| 产物 | 作用 |
|---|---|
| `references/r1-next-safe-slice-after-old-anchor-preflight.json` | P4-20 路线裁决 manifest |
| `compass/tools/redcap-r1-next-safe-slice-after-old-anchor-preflight-check.sh` | P4-20 机器检查入口 |
| `prism/reports/2026-05-23-r1-next-safe-slice-after-old-anchor-preflight.md` | P4-20 棱镜评审报告 |
| `references/backlogs/framework-upgrade.json` | 标记 P4-20 done，并登记 P4-21 pending |

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 人话解释 | 本轮用途 |
|---|---|---|
| route manifest | 路线裁决清单 | 记录下一步选什么、为什么选、哪些不能做 |
| support-copy-first | 先补兼容/支撑副本，不先破坏旧入口 | 限制 P4-21 只能做非破坏性小切片 |
| human hard gate | 必须由 Norven 决策的门 | C/D/E 不能自动推进 |
| deferred candidate | 这轮不做但不能忘的候选 | 旧报告别名/查询网关保留为后续候选 |

---

## 四、人工审核要点

本轮不需要 Norven 人工介入。你需要知道的核心结论是：P4-20 只是“选择下一步”，下一步选了 `internal-control-plane`，但它还没有被实现，正式发布也没有被解除阻塞。

### 4.1 棱镜评审

| Agent | 建议 | 要点 |
|---|---|---|
| Claude Code | A | `internal-control-plane` 是更大的发布 blocker，copy-first / support-copy-first 可以非破坏性推进 |
| Kimi | B | 旧报告入口别名/查询网关更小、更直接承接 P4-19 |
| Gemini | 未调用 | Claude Code 与 Kimi 已形成本轮路线评审 quorum |
| Copilot | 未调用 | Copilot 是保护性兜底，Claude Code 与 Kimi 可用时不调用 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|---|---|---|
| P4-20 checker | `bash compass/tools/redcap-r1-next-safe-slice-after-old-anchor-preflight-check.sh` | 通过 |
| Prism archive check | `bash prism/tools/prism-archive-check.sh --report prism/reports/2026-05-23-r1-next-safe-slice-after-old-anchor-preflight.md` | 通过 |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过 |
| token-risk-audit | `bash compass/tools/redcap-token-risk-audit.sh` | 通过 |
| spec-check | `bash compass/tools/redcap-spec-check.sh .` | 通过 |
| diagnose | `bash compass/tools/redcap-diagnose.sh` | 通过 |
| clean workspace E2E result check | `bash compass/tools/redcap-clean-workspace-e2e.sh --check-result --timeout 180` | 通过 |

### 5.2 最终收口验证

| 验证项 | 结果 |
|---|---|
| spec-check | 通过 |
| diagnose | 通过 |
| clean workspace E2E | 通过 |
| closeout runtime | 提交后复跑生成 receipt；本报告不把未提交工作树冒充为已收口 |

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|---|---|
| closeout receipt | 提交后由 `redcap-layerb-closeout-runtime` 写入运行时收口目录 |
| closeout summary | 提交后由 `redcap-layerb-closeout-runtime` 写入运行时收口目录 |
| 承诺账本 | 6/6，已兑现 |

### 5.4 完成等级（禁止混报）

| 等级 | 当前结论 | 说明 |
|---|---|---|
| 已实现 | 是 | route manifest、checker、Prism 报告和 P4-21 登记已落地 |
| 已自检 | 是 | P4-20 checker、Prism archive、Prism acceptance 与 token 风险审计已通过 |
| 已独立验收 | 是 | Claude Code 与 Kimi 完成棱镜路线评审 |
| 已正式完成 | 提交后 closeout runtime 复跑确认 | commit-proof 要求工作树干净，因此 receipt 必须在提交后生成 |
| P4-21 实现 | 未完成 | 本轮只登记下一任务，不实现下一任务 |
| 正式发布准备完成 | 未完成 | 本轮不是正式发布，也不解除 release blocker |

---

## 六、遗留问题与下一步

| 问题 | 原因 | 建议优先级 |
|---|---|---|
| P4-21 还未实现 | P4-20 只做路线选择 | P0 |
| 旧报告入口别名/查询网关未做 | 本轮裁决先回到更大的 `internal-control-plane` blocker | P0 后续候选 |
| 正式发布仍 blocked | 仍有人类发布决策、Layer A、raw evidence、release readiness 等边界 | P0 |

### 推荐下一步

1. 提交本轮 P4-20 变更后复跑 closeout runtime，生成 receipt。
2. 自动进入 P4-21，不等待 Norven 机械回复“继续”。
3. P4-21 只允许做 `internal-control-plane` 的非破坏性 support-copy-first 小切片。

---

## 七、经验沉淀

- 问题源：路线选择任务容易在“最小切片”和“最大 blocker”之间摇摆；如果没有棱镜分歧和裁决规则，容易无限延长局部治理链。
- 解决方案：把路线选择做成 route manifest，明确候选矩阵、人工硬门、禁止声明、下一 backlog 项和 deferred candidates。
- 最后效果：P4-20 没有把“选路”冒充成“实现”，也没有停下来等待机械“继续”；父任务线可以自动进入 P4-21。

### 7.3 Evolution Factory 候选处理

| 维度 | 结论 |
|---|---|
| 问题源 | 自动续跑场景下，路线选择如果没有结构化候选矩阵，容易被最近一次局部任务牵引，忽略更大的主线 blocker |
| 解决方案 | 用 route manifest + Prism 分歧 + Cap 裁决 + backlog 续接登记，把“下一刀做什么”变成可审计决策 |
| 最后效果 | deferred-with-owner owner=Cap trigger=P4-21-closeout-or-next-route-selection；本轮经验适合保留为私有治理经验，暂不晋升 public arsenal |

---

## 八、附录

- 本轮没有读取 `.env` 或任何 secret。
- 本轮没有调用 Copilot。
- 本轮没有删除旧报告、清理 raw evidence、修改发布开关或执行正式发布命令。
