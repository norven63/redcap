# 任务完成报告：P4-19 旧 Prism 报告锚点退休预检

**报告日期**：2026-05-23  
**执行者**：Cap（Codex.app 主执行，Prism 使用 Claude Code + Kimi；Gemini 因交互式登录提示未形成有效审查）  
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：旧 `prism/reports` 报告入口未来能否安全下线，已经完成第一轮机器预检。结论很明确：现在还不能执行真实退休，因为仍有后冻结报告、旧路径引用、别名/跳转契约和人工授权边界没有补齐。
- 详情：本轮只新增预检资产和检查器，没有删除、移动、重命名或替换任何旧报告文件，也没有清理 `prism/runs` 原始证据。

### 0.2 上一步完成的是

- 上一步完成的是：P4-18 把正式发布前剩余差距整理成地图，并把 P4-19 选为下一条最小安全切片。P0 自动续跑缺口修复后，本轮没有再等待 Norven 机械回复“继续”，而是自动进入 P4-19。

### 0.3 下一步计划做的是

- 下一步计划做的是：不要直接删除旧报告入口。后续应先补“旧报告入口别名/查询网关”或回到更大的 `internal-control-plane` 物理拆分任务；真实删除必须另立任务、重新评审并获得明确授权。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：P4-16 完成 Prism 报告 copy-first → P4-18 完成发布差距地图 → P4-19 完成旧报告入口退休预检 → 后续再决定是补别名契约还是推进控制面拆分。
- 当前所在位置：framework-upgrade / P4-19 已完成预检；正式公开发布仍保持 blocked。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要
- 说明：本轮没有执行破坏性动作。只有当后续要真实删除旧报告入口、清理 raw evidence、修改发布开关、选择许可证或执行公开发布时，才需要 Norven 人工决策。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> “就是现在的状态是，你总是中途停顿下来，需要我人工机械的回复“好的，请你们继续”，但其实这根本不需要中断，完全可以由你和棱镜自动续上。并且，我经常会不在电脑旁，导致无法及时响应来回复这段机械的指令，你就会等很久才会继续推进，极大的延缓了项目推进速度”

### 1.2 触发背景

P4-18 结束后，父任务线已经明确把 P4-19 登记为下一条 pending 任务。过去的问题是：子任务完成后，RedCap 只会汇报“已完成”，却没有机器硬门要求它自动接续父任务线，导致需要 Norven 机械回复“继续”。本轮先修复了这个自动续跑缺口，然后按新的父任务续跑规则进入 P4-19。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | continuation-without-mechanical-user-wait |
| 原始意图 | 无人工硬门时，Cap/Prism 应自动续上父任务线，不再停下来等机械“继续” |
| 已覆盖 | P0 自动续跑硬门已落地并验证；P4-19 已自动接续并完成预检 |
| 未覆盖/延期 | 未执行真实旧锚点删除、raw evidence cleanup、正式公开发布、许可证/registry/发布级别决策、Layer A 产品裁决 |
| 用户可见边界 | 只能声明“旧报告入口退休条件已预检清楚”；不能声明“旧入口已经退休” |

---

## 二、方案讨论

### 2.1 问题分析

旧 `prism/reports` 现在仍然承担“正式 Prism 报告入口”的角色。虽然 P4-16 已经把 55 份冻结报告复制到 `private-archive/prism-reports`，但这不等于旧入口可以删除。原因有四个：

| 阻塞点 | 人话解释 |
|---|---|
| 后冻结报告还在旧入口 | P4-16 之后又产生了 5 份报告，它们没有进入当时的私有归档集合 |
| 旧路径引用仍很多 | 仍有大量文档、策略、工具和历史报告引用 `prism/reports` |
| 没有别名/查询网关 | 删除旧入口后，还没有稳定方式保证旧 ID 和旧路径都能找到新位置 |
| 没有破坏性授权 | 本轮任务明确禁止真实删除，Norven 也没有授权破坏性迁移 |

### 2.2 收敛结论

| 分类 | 结论 |
|---|---|
| 当前能做 | 预检、引用扫描、风险分类、回滚要求、未来 apply 条件 |
| 当前不能做 | 删除、移动、重命名、替换、symlink 切换旧报告；清理 raw evidence；修改发布开关 |
| 机器保障 | P4-19 checker 已接入 `spec-check` 和 `diagnose`，后续不能把 preflight 冒充成真实 apply |
| 发布口径 | 正式公开发布仍 blocked；`prism-layer-and-evidence` blocker 仍未关闭 |

---

## 三、落地结果

### 3.1 本轮完成了什么

本轮把“旧报告入口是否可以下线”从口头判断变成了可重复检查的预检资产。它会重新计算报告数量、私有归档副本 hash、后冻结报告集合、包面排除和旧路径引用下限，并强制保持“不能真实退休、不能关闭 blocker、不能宣称 release-ready”的边界。

### 3.2 关键产物

| 产物 | 作用 |
|---|---|
| `references/r1-prism-report-archive-old-anchor-delete-last-preflight.json` | P4-19 预检结论：当前不具备真实 delete-last 条件 |
| `compass/tools/redcap-r1-prism-report-archive-old-anchor-delete-last-preflight-check.sh` | 可执行检查入口 |
| `compass/tools/redcap-r1-prism-report-archive-old-anchor-delete-last-preflight-check.py` | 重新计算报告、hash、引用和包面边界的机器检查器 |
| `references/execution-guarantees.json` | 把 P4-19 预检登记为执行保障项 |
| `prism/reports/2026-05-23-r1-prism-report-archive-old-anchor-delete-last-preflight.md` | 棱镜审查结论 |

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 人话解释 | 本轮用途 |
|---|---|---|
| old-anchor | 旧入口；这里指 `prism/reports` 下的正式报告路径 | 判断未来能否安全下线旧报告入口 |
| delete-last | 先复制/验证新位置，再最后删除旧位置的安全迁移模式 | 明确本轮只做删除前预检，不做真实删除 |
| preflight | 预检；只证明能不能做，不执行破坏性动作 | 固化“现在还不能删”的机器证明 |
| post-freeze report | P4-16 冻结归档集合之后新增的报告 | 防止新增报告绕过归档集合 |
| raw evidence | 棱镜运行原始证据，主要在 `prism/runs` | 本轮完全不清理，避免破坏审计链 |

---

## 四、人工审核要点

本轮没有需要 Norven 人工介入的发布、删除、证据清理或权限决策。人工需要知道的核心结论是：旧 `prism/reports` 入口现在还不能退休，后续必须先补别名/查询入口或继续推进 `internal-control-plane` 物理拆分。

### 4.1 棱镜评审

| Agent | 结果 | 要点 |
|---|---|---|
| Claude Code | PASS_WITH_NITS | 无 blocking；确认未触碰旧报告、raw evidence 或发布开关；建议收口时生成任务报告和 receipt |
| Kimi | PASS_WITH_NITS | 无 blocking；建议把引用扫描下限和当前实际值校准得更近，但承认当前 floor 设计不削弱安全性 |
| Gemini | 未形成有效审查 | CLI 返回交互式认证提示，没有产出审查结论；本轮不降级调用 Copilot |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|---|---|---|
| P4-19 checker | `bash compass/tools/redcap-r1-prism-report-archive-old-anchor-delete-last-preflight-check.sh` | 通过 |
| public package surface | `bash compass/tools/redcap-public-package-surface.sh` | 通过，candidate_count=301 |
| runtime package manifest | `bash compass/tools/redcap-runtime-package-manifest.sh --check --npm-pack-dry-run` | 通过，candidate_count=301 |
| R1 control-plane contract split | `bash compass/tools/redcap-r1-control-plane-contract-split-check.sh` | 通过，candidate_count=301 |
| Prism package visible support | `bash compass/tools/redcap-r1-prism-package-visible-support-copy-first-apply-check.sh` | 通过，candidate_count=301 |

### 5.2 待最终收口验证

- `bash compass/tools/redcap-spec-check.sh "$PWD"`
- `bash compass/tools/redcap-diagnose.sh .dev-task.md`
- `bash compass/tools/redcap-clean-workspace-e2e.sh --check-result --timeout 180`
- closeout runtime / receipt

### 5.4 完成等级（禁止混报）

| 等级 | 当前结论 | 说明 |
|---|---|---|
| 已实现 | 是 | 预检资产和检查器已经落地 |
| 已自检 | 是 | 核心预检、包面和结构检查已执行，最终全量回归仍在收口 |
| 已独立验收 | 是 | Claude Code 与 Kimi 完成棱镜审查，Gemini 因交互认证未产出有效意见 |
| 已正式完成 | 否 | closeout receipt 尚未生成，不能混报为正式完成 |
| P4-19 预检资产 | 已完成 | 预检 manifest、checker、Prism 报告和索引已落地 |
| 真实旧锚点退休 | 未完成 | 本轮禁止删除、移动、替换或切换旧 `prism/reports` 入口 |
| 正式发布准备完成 | 未完成 | 本轮不修改发布开关，也不解除 release blocker |
| 当前任务正式收口 | 待完成 | 仍需通过最终 spec-check、diagnose、clean workspace E2E 和 closeout runtime |

---

## 六、遗留问题与下一步

| 问题 | 原因 | 建议优先级 |
|---|---|---|
| 旧报告入口仍不能真实退休 | 还缺后冻结报告处理、别名/查询网关、引用迁移和人工授权 | P0 |
| internal-control-plane 仍是最大工程 blocker | 本轮只处理 Prism 报告入口预检，没有推进控制面物理拆分 | P0 |
| package count policy wording drift 仍存在 | 运行时发布策略仍保留更早的 280 语言；当前 alpha readiness surface 已到 301 | P1 |
| Gemini CLI 需要重新认证或 headless 配置 | 本轮 Gemini 返回认证提示，未形成有效审查 | P2 |

### 推荐下一步

1. 完成 P4-19 最终收口验证和 receipt。
2. 由 Cap/Prism 选择下一条安全切片：优先考虑 `internal-control-plane`，或先补旧报告入口别名/查询网关。
3. 真实删除旧报告入口前，必须另立任务并获得明确授权。

---

## 七、经验沉淀

- 问题源：copy-first 完成后，容易误以为旧入口已经可以 delete-last；但如果后冻结报告、旧引用、别名契约和人工授权没有同时闭合，真实删除会破坏考古能力。
- 解决方案：把 delete-last 之前的条件做成机器预检，检查器必须重新计算现状，不能只相信 manifest。
- 最后效果：旧 `prism/reports` 入口仍保留，但“为什么不能删、要满足什么才能删、后续怎么验收”已经被固定下来。

### 7.3 Evolution Factory 候选处理

| 维度 | 结论 |
|---|---|
| 问题源 | “复制完成”容易被误读成“旧锚点可以删除”，这是资产生命周期迁移中的典型风险模式 |
| 解决方案 | 将真实删除前的条件固化成预检资产，并要求后续 delete-last 任务重新引用这份预检而不是凭口头判断推进 |
| 最后效果 | deferred-with-owner owner=Cap trigger=P4-20-or-next-delete-last-apply；本轮经验适合进入 Forge 候选池，但因为它涉及当前发布结构和本地历史路径，先保留为私有候选，不直接晋升 public arsenal |

---

## 八、附录

- 本轮 commit 范围会包含 P4-19 预检资产、P4-20 自动续跑锚点、报告活跃箱归档、包面计数与上游 hash 证明刷新。
- 本轮未执行真实删除、发布、secret 读取、registry 登录或 Prism raw evidence 清理。
