# 任务完成报告：P4-2i runtime 最小兼容物理布局落地

**报告日期**：2026-05-08  
**执行者**：Cap（Codex.app + Claude Code / Kimi Prism 复核）  
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 已新增 package-visible 的最小 runtime 物理布局：`runtime/redcap-core/**` 与 `runtime/host-adapters/**`。
- 详情：新增 runtime wrapper 会委托回根入口，保持 `bin/redcap`、`revive-cap.sh`、`closeout-cap.sh` 继续作为兼容入口；没有移动 `compass/tools`、`prism/tools`，也没有删除任何旧入口或运行证据。

### 0.2 上一步完成的是

- 上一步完成的是：P2-8 已把 `prism/runs` 的清理提示改成只读审查 / dry-run / 物理删除需显式批准的安全口径，并完成 closeout receipt。

### 0.3 下一步计划做的是

- 下一步计划做的是：若继续推进 public release，只能进入独立 release task；当前仍不能替用户决定 `private=false`、license、npm 凭据和真实发布动作。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：信息架构治理 → package 白名单预检 → CLI 产品面加固 → runtime 最小兼容布局 → 未来独立 release task。
- 当前所在位置：P4-2i `redcap-runtime-layout-minimum-compatible-apply`，这是发布前 blocker 的工程收敛切片，不是发布切片。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮只处理 AI 可推进的 runtime 布局 blocker；`private=false`、license 与 npm 发布仍保留给未来显式 release 任务。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 好的，现在请你和棱镜继续稳步推进未完成的任务，完成时序和优先级由你们内部讨论评审和决策即可。如果有必要，可以每次执行一步，都做一次阶段性的项目全局扫描和评审，因为你们现在做的开发动作比较“伤筋动骨”。

### 1.2 触发背景

父任务账本和发布前架构审查仍显示 P4-2 public release 没完成。三项 blocker 中，发布开关/凭据和 license 属于人工发布边界；runtime/project/user 物理拆分仍 dry-run-only 是唯一可以由 Cap 与棱镜继续推进的工程项。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | partial-with-explicit-defer |
| 已覆盖 | 处理 runtime 布局 blocker：建立最小 runtime 物理层、同步 package surface、刷新发布前架构事实。 |
| 延期 | 不做 npm publish、不改 `private=true`、不选择 license、不做完整工具树迁移、不删除旧入口。 |
| 用户可见边界 | 本轮是“runtime 最小兼容布局已存在”，不是“RedCap 已 public-release-ready”。 |

---

## 二、方案讨论

### 2.1 问题分析

原状态只有 dry-run manifest，文件系统里没有 `runtime/` 目录，导致发布前审查合理地把 runtime layout 标为 release blocker。直接搬迁 `compass/tools` 或 `prism/tools` 风险太高，会牵动 hook、validator、Prism 和 closeout 全链路。因此本轮采用 copy-first / shim-first 的最小布局：先让包里存在可验证 runtime 层，但旧入口和工具树继续稳定工作。

### 2.2 决策结果

| 问题 | 决策 | 理由 |
|---|---|---|
| 是否推进 npm 发布 | 否 | 发布开关、凭据、license 是人工边界。 |
| 是否移动工具树 | 否 | 缺少 import map 和 hook adapter 全量验证，风险过高。 |
| 是否建立最小 runtime 布局 | 是 | 这是 AI 可推进的 release blocker，且可通过 wrapper 保持兼容。 |

---

## 三、落地结果

### 3.1 完成内容

- 新增 package-visible runtime 层：`runtime/redcap-core/README.md`、`runtime/redcap-core/bin/redcap`、`runtime/redcap-core/revive-cap.sh`、`runtime/redcap-core/closeout-cap.sh`。
- 新增 host adapter 边界说明：`runtime/host-adapters/codex/README.md`。
- package surface 从 234 个文件变成 239 个文件；新增的 5 个 runtime/host-adapter 文件进入 npm pack dry-run 与 publish-safety 扫描。
- `execution-layer-split-dry-run.json` 从 `dry-run-only` 更新为 `minimum-compatible-layout-exists`，但完整 apply 仍保持关闭。
- 发布前架构审查从 3 个 release blocker 变为 2 个 release blocker：发布开关/凭据、license。runtime 完整瘦身仍保留为 should-fix。

### 3.2 人话解释

这次不是把 RedCap 整台机器搬家，而是在机器外壳上先装好一个“未来 runtime 的正式接口层”。外部包已经能看到 runtime 层，runtime 层也能把命令安全地交回根入口执行；但真正把内部工具树搬进 runtime、做更瘦的 public package，还需要后续单独任务。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|---|---|---|
| runtime 最小布局 | `runtime/redcap-core/**` | npm 包里能看到的运行时目录骨架；它证明 RedCap 不再只有 skill-root 形态。 |
| wrapper | `runtime/redcap-core/bin/redcap` | 一个很薄的入口脚本，把命令安全转交给现有根入口，不复制复杂逻辑。 |
| full runtime split | `references/execution-layer-split-dry-run.json` | 未来把工具树、hook adapter、import map 都迁入正式 runtime 的更大手术；本轮没有做。 |
| release blocker | `references/pre-release-product-architecture-review.json` | 发布前必须解决的阻塞项；本轮只移除了 runtime 根不存在这一项。 |
| should-fix | `references/pre-release-product-architecture-review.json` | 发布后或广泛推广前应继续优化的问题，但不再是当前 public release 的硬阻塞。 |

---

## 四、棱镜评审

| 角色 | Agent | 结论 | 重点意见 |
|---|---|---|---|
| reviewer | Claude Code | pass | 可以推进最小 runtime 布局；禁止触碰发布、license、工具树迁移。 |
| challenger | Kimi | warn | 方案可行，但 package candidate count、review facts、split status 必须同步，否则 checker 链会误报。 |

---

## 五、验证结果

### 5.1 已通过验证

| 验证项 | 结果 |
|---|---|
| runtime wrapper smoke | 通过：`runtime/redcap-core/bin/redcap version`、`doctor`、`revive --help`、`closeout status` 均可执行 |
| package manifest | 通过：candidate_count=239，publish_allowed=false |
| public package surface | 通过：private=true，license 仍 manual-before-public-publish |
| pre-release product architecture | 通过：release_blockers=2，should_fix=2，deferred=1 |
| pre-release structure task tree | 通过：nodes=13 |
| package publish safety | 通过：files_scanned=239 |
| Prism acceptance | 通过：2 reviewers，2 families，0 blocker |

### 5.2 closeout runtime / receipt

| 项目 | 结果 |
|---|---|
| 执行承诺账本 | closeout 时核对 |
| closeout receipt | closeout 时生成 |
| rescue audit | 如有则记录在 runtime 审计路径 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|---|---|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是 |
| 已正式完成 | 否；等待 closeout runtime receipt |

---

## 六、遗留问题与下一步

| 问题 | 当前边界 | 下一步 |
|---|---|---|
| npm public release | 仍 blocked | 未来单开 release task，处理 `private=false`、npm 凭据、版本和回滚计划。 |
| license | 仍 blocked | 需要 Norven 的法律/产品决策，Cap 不替代选择。 |
| 完整 runtime 瘦身 | should-fix | 未来需要 import map、hook adapter 和工具树迁移回归，不和本轮混做。 |
| `prism/runs` 物理清理 | 未执行 | 需要显式批准 `prune-local --apply`。 |

---

## 七、经验沉淀

### 7.1 本轮经验

| 维度 | 内容 |
|---|---|
| 问题源 | 发布前 blocker 不一定都能由 AI 推进；发布开关与 license 是人工边界，runtime 布局才是工程边界。 |
| 解决方案 | 把 blocker 拆成“人工发布决策”和“AI 可做工程收敛”，对后者采用最小 wrapper 布局。 |
| 最后效果 | P4-2a blocker 从 3 个降为 2 个，同时没有破坏根入口和现有工具链。 |

### 7.3 Evolution Factory 候选处理

- 候选：copy-first / shim-first 的 runtime 布局推进方法。
- 处理：no-promote；当前已有执行层 split dry-run 与 package readiness 经验覆盖，本轮先不新增重复 lesson。

---

## 八、附录

### 附录 A：棱镜记录

- run_id：`20260508-runtime-layout-minimum-compatible-apply`
- 报告：`prism/reports/2026-05-08-runtime-layout-minimum-compatible-apply.md`

### 附录 B：Commits

```
待提交
```
