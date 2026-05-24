# 任务完成报告：正式发布外收敛父任务

**报告日期**：2026-05-24
**执行者**：Cap（Codex.app 主执行，Prism 使用 Claude Code + Kimi；Copilot 按保护策略未调用）
**报告版本**：v1.0

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：已修复 Codex Stop hook 的会话归属缺口、人类进度摘要旧焦点污染、RASG-025 账本状态漂移，并补齐棱镜评审与经验沉淀。
- 详情：普通讨论、只读会话、无 session id 或跨 session 情况只做 advisory，不再接管别的任务；危险命令被拒绝后立即返回，不会继续声明任务所有权；只读命令即使提到 `rm` 等词也不会被当作写动作。

### 0.2 上一步完成的是

- 上一步完成的是：Claude Code + Kimi 棱镜审查已完成，Kimi 提出的误判风险已通过 follow-up 修复和回归夹具闭环；经验 L-170 已沉淀。

### 0.3 下一步计划做的是

- 下一步计划做的是：生成 closeout receipt，并提交本轮变更；后续才进入真实发布决策。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：历史债务坏味清理 -> 当前正式发布外收敛 -> 最终回归与收口 -> 后续才进入真实发布决策。
- 当前所在位置：本轮实现、棱镜评审、经验沉淀、Prism acceptance、spec-check、diagnose 与专项回归均已通过，正在生成 closeout receipt。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：当前没有触及许可证、registry、凭据、正式发布开关、私密文件处理或破坏性删除。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> “我希望你制定一个完整的推进计划和目标，‘完成‘正式发布’外，我们已经发现、汇总的所有问题点、待完善项。如果当中你和棱镜发现有非常大的改动，可以自行中插‘review全局项目’的新需求，以便尽早发现可能因为改动而引入的新问题，并且如果发现新问题后，也可以自行中插‘修复因review而新发的问题’的新需求。如此循环往复，直至你们完成所有‘正式发布’外的任务为止’”

### 1.2 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | full-implementation |
| 原始意图 | 清完正式发布之外、当前已知且影响首次发布可信度的问题；允许棱镜 review 后修复新发现的同类阻塞项。 |
| 已覆盖 | Codex 会话归属、状态摘要、RASG-025 治理冻结完成态、棱镜评审、经验沉淀、回归接线。 |
| 未覆盖/延期 | 真实发布动作、许可证、registry、凭据、发布开关、破坏性删除、大规模历史资产迁移。 |
| 用户可见边界 | 只能说正式发布外已知阻塞项完成收敛，不能说 RedCap 已发布或长期演进全部完成。 |

## 二、方案讨论

本轮不再扩大到正式发布本身，也不再继续做大规模历史资产迁移。核心判断是：先把会影响首次发布可信度的非发布阻塞项清掉，让后续发布决策建立在可信状态面上。

棱镜评审承担独立视角：Claude Code 负责总体 review，Kimi 负责从误判和边界条件角度挑战实现。Kimi 提出的“只读命令提到危险词也可能被误判为写动作”被采纳并修复。

## 三、落地结果

### 1.1 Codex Stop hook 会话归属

问题：旧 Stop hook 只看工作区是否存在 pending closeout，可能让一个普通探讨会话被另一个任务的未完成收尾劫持。

修复：新增 session ownership gate。PreToolUse 在真实写动作发生时记录当前 session 与当前任务身份；Stop 只有看到匹配的 session ownership 才进入 RedCap 收尾，否则只记录 advisory 并放行。

效果：跨 session、无 session id、只读会话不会驱动别的任务收尾；真实执行会话仍可正常触发收尾检查。

### 1.2 人类进度摘要

问题：当前任务已经重锚，但摘要仍混入旧 `framework-upgrade` 当前焦点，让人误以为任务停在旧发布决策点。

修复：摘要只在当前任务明确绑定 `framework-upgrade.json` 时展示该 backlog 焦点；未绑定时以 `.dev-task.md` 当前任务目标为主。

效果：`bin/redcap summary` 的主线现在显示本轮正式发布外收敛任务，不再出现旧 P4-29 文案污染。

### 1.3 RASG-025 治理自增殖冻结

问题：防止“清理产生新清理”的冻结政策已经实现，但 RASG 账本仍显示 planned。

修复：复验冻结政策与检查脚本后，将 RASG-025、阶段摘要和人类导读统一改为 done。

效果：RedCap 前进刻度表显示历史债务无开放项；后续新发现必须先通过冻结分类，普通证据不会自动变成新任务。

### 1.4 发布前证据链同步

问题：新增 Codex 会话归属脚本后，公开包候选从 309 个变为 310 个，多个 R1 证据链文件仍保留旧哈希、旧计数和旧断言。如果不修复，正式发布前检查会继续接受过期事实。

修复：沿 `spec-check` 暴露出的链路逐项同步 package surface、R1 control-plane、Prism archive、Layer A 与 product architecture 相关证据；把 internal-control-plane 计数从 115/230 对齐为 116/231，并把旧的 `All 111` 断言改为不绑定过期数量的表述。

效果：发布前检查不再依赖旧事实；新增脚本已纳入公开包候选边界。但这只代表发布准备证据链恢复一致，不代表 RedCap 已发布。

## 2. 棱镜评审

- Claude Code：通过，无必须修复项。
- Kimi：通过，但指出第一版写动作识别过宽，可能把只读命令误判为写动作。
- Follow-up：已修复误判并补充回归，Claude Code 与 Kimi 复核均无 blocker。
- Copilot：按保护性 fallback 策略未调用，因为 Claude Code 与 Kimi 可用。

## 四、人工审核要点

本轮不需要 Norven 人工介入。没有触及许可证、registry、npm 凭据、发布开关、私密文件、破坏性删除或正式发布动作。

需要人工介入的事项仍然只属于后续真实发布阶段：许可证、npm registry/登录态、是否解除 `private=true`、是否打开 `publish_allowed=true`、版本号和发布时间窗口。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 人话解释 | 本轮用途 |
|---|---|---|
| session ownership | 当前会话是否拥有当前任务 | 防止普通讨论会话被别的任务收尾劫持 |
| advisory-only | 只记录提醒，不驱动收尾 | 无 session id、跨 session 或只读会话的安全默认行为 |
| RASG-025 | 发布前治理自增殖冻结条目 | 阻断“清理产生新清理”的循环 |
| Prism review | 棱镜独立评审 | 用 Claude Code 与 Kimi 做外部视角验收 |

## 五、验证结果

### 5.1 机器验收

- `bash compass/tools/redcap-codex-hooks-check.sh`
- `bash compass/tools/redcap-pre-release-freeze-policy-check.sh`
- `bash compass/tools/redcap-architecture-smell-governance-check.sh`
- `bash compass/tools/redcap-progress-meter-check.sh`
- `bash compass/tools/redcap-file-lookup-dictionary-check.sh`
- `bash compass/tools/redcap-knowledge-index-check.sh`
- `bash prism/tools/prism-archive-check.sh --report prism/reports/2026-05-24-non-publish-pre-release-convergence.md`
- `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md`
- `bash compass/tools/redcap-spec-check.sh "$PWD"`
- `bash compass/tools/redcap-diagnose.sh .dev-task.md`
- `bash compass/tools/redcap-public-package-surface.sh`
- `bash compass/tools/redcap-package-publish-safety-check.sh`
- `bash compass/tools/redcap-reference-asset-lifecycle.sh check`

### 5.3 closeout runtime / receipt

| 项目 | 当前值 |
|---|---|
| closeout receipt | 无 |
| 当前状态 | 回归已通过，等待 closeout runtime 生成 receipt |
| 人工介入 | 不需要 |

### 5.4 完成等级（禁止混报）

| 等级 | 结论 | 说明 |
|---|---|---|
| 已实现 | 是 | 会话归属门、摘要修复、RASG-025 状态对齐和经验沉淀已落地 |
| 已自检 | 是 | targeted checks、spec-check、diagnose、package surface 和 package safety 均已通过 |
| 已独立验收 | 是 | Claude Code 与 Kimi 棱镜评审通过 |
| 已正式完成 | 否 | closeout receipt 尚未生成，不能冒充正式完成 |

## 六、遗留问题与下一步

本轮没有遗留新的正式发布外阻塞项。后续要进入真实发布任务时，仍需单独处理许可证、registry、npm 凭据、版本号、发布开关和发布时间窗口。

未执行的大规模历史资产迁移、外部多 OS 发布矩阵、GraphRAG 或 full LLM-wiki 不属于本轮“正式发布外收敛父任务”的完成口径，不能被混报为已完成。

## 七、经验沉淀

- 新增 L-170：会话归属门要判定真实写动作，不能把“提到危险词”当作拥有任务。
- 这条经验记录了问题源、解决方案和最后效果，避免未来 hook / ownership gate 再用粗糙关键词扫描复发。

### 7.3 Evolution Factory 候选处理

本轮命中高价值经验信号，因为它同时涉及 hook 会话隔离、棱镜 review、发布前治理冻结和回归失败修复。

处理结论：no-promote。

原因：本轮高价值经验已沉淀为 L-170，且对应机制已通过 hook checker 和棱镜报告承接；暂不新增 Evolution candidate，避免把一个已落地的局部修复重复晋升为长期专项。

## 八、附录

### 8.1 未执行边界

- 未执行正式发布。
- 未改许可证、registry、凭据、发布开关或 npm package privacy。
- 未读取 `.env`、identity 原文、飞书 secret 或其他私密文件。
- 未做破坏性删除或大规模历史资产迁移。
