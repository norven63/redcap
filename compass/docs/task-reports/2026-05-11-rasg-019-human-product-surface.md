# 任务完成报告：RASG-019 人类可读产品表面治理

**报告日期**：2026-05-11  
**执行者**：Cap（Codex.app + Prism: Claude Code；Kimi resource-limited）  
**报告版本**：v0.4

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 已把 CLI、状态、深入诊断和飞书通知的默认主叙事改为“先讲人话、再给证据”。
- 详情：本轮解决的是一个产品表面问题：用户看到 RedCap 输出时，不应该先被内部术语、门禁名、收尾组件名淹没。现在 `redcap help`、`redcap doctor`、`redcap status` 首屏、`redcap diagnose` 开场和飞书样例都会先解释当前做到了什么、下一步是什么、是否需要人工介入；内部机制仍保留在后续诊断和机器证据里，不牺牲审计严谨性。

### 0.2 上一步完成的是

- 上一步完成的是：已完成 RASG-017 根目录信息架构目标模型，并在该基础上接续到 RASG-019，优先修复人类无法快速读懂 RedCap 当前状态的问题。

### 0.3 下一步计划做的是

- 下一步计划做的是：执行全量回归和正式 closeout；若通过，本轮后续可继续转入 RASG-020 或 RASG-021。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：历史债务治理 -> RASG-017 根目录目标模型 -> RASG-019 人类可读产品表面 -> RASG-020 public/internal contract -> RASG-021 Prism 降级韧性 -> 正式发布准备。
- 当前所在位置：当前位于 RASG-019 的回归与正式收口阶段；产品表面改造、机器检查器和 resource-limited Prism acceptance 已完成，等待最终回归和 receipt。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮还没有触及发布开关、许可证、凭据、私密资产删除或不可逆目录迁移；后续可以由 Cap + Prism 继续完成评审和收口。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> “好的，你们继续稳步推进吧”

### 1.2 触发背景

RASG-018 的全局审判后，发布前仍有三条开放债务：RASG-019、RASG-020、RASG-021。RASG-019 关注的是 RedCap 的人类可读产品表面：即使内部治理机制很强，如果默认输出仍然像机器日志，人类就无法判断当前完成了什么、是否阻塞、下一步该怎么走。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | partial-with-explicit-defer |
| 原始意图 | 继续推进 RedCap 发布前开放债务。 |
| 已覆盖 | 本轮覆盖 CLI help/doctor/debug、status 首屏、diagnose 开场、飞书样例和对应机器检查器。 |
| 未覆盖/延期 | RASG-020 public/internal runtime contract、RASG-021 Prism degradation metrics、npm publish、全量历史文档改写。 |
| 用户可见边界 | 本轮完成后只能声明关键人类输出表面已加固，不能声明所有历史文档都已改写。 |
| 后续路径 | 完成本轮 closeout 后继续推进 RASG-020 或 RASG-021。 |

---

## 二、方案讨论

### 2.1 问题分析

问题不在于 RedCap 缺少证据，而是证据太容易抢走主叙事。人类需要先知道“现在做完了什么、效果是什么、下一步是什么、是否需要我做事”；内部机制名只适合进入证据、诊断、调试和机器字段。否则 RedCap 会在可靠性增强的同时降低可理解性。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 只改文案 | 直接把几个输出改成人话 | 快 | 容易回退，后续修改可能重新把内部术语放回首屏 |
| Q1 | 政策 + 真实样例检查 | 定义产品表面政策，并跑真实 CLI/status/diagnose/Feishu 样例 | 可持续、防回退 | 需要维护检查器和样例 |
| Q1 | 全量文档改写 | 把所有历史报告和文档都改成人类可读 | 表面最彻底 | 范围过大，容易破坏考古锚点，不适合本轮 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 政策 + 真实样例检查 | 既能把当前人类入口改好，又能通过机器门禁防止未来回退；历史文档保持按需治理，不在本轮大规模改写。 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `.dev-task.md` | 修改 | 将当前任务从已关闭的 RASG-017 重锚到 RASG-019。 |
| `bin/redcap` | 修改 | 将默认帮助和错误提示改为中文主叙事，同时保留命令名与结构化错误键。 |
| `compass/tools/redcap-cli-product-surface.py` | 修改 | 将 `doctor/debug/help/trace` 主输出改为人类可读中文表达。 |
| `compass/tools/redcap-current-status.py` | 修改 | 将状态首屏的 fallback 与收尾表达改为“完工凭证、未清收尾项、需求指纹”等人话。 |
| `compass/tools/redcap-progress-meter.py` | 修改 | 将前进刻度表的人类字段从 `closeout/receipt/promise` 口径改为完工凭证和承诺完成口径。 |
| `compass/tools/redcap-diagnose.sh` | 修改 | 在内部诊断前新增人类可读开场说明。 |
| `references/human-product-surface-policy.json` | 新建 | 定义人类首屏表面、内部术语边界和样例检查要求。 |
| `compass/tools/redcap-human-product-surface-check.py` / `.sh` | 新建 | 直接运行真实 CLI/status/diagnose/Feishu 样例，防止内部术语回流到主叙事。 |
| `compass/tools/redcap-spec-check.sh` / `compass/tools/redcap-diagnose.sh` | 修改 | 将新检查器接入规范检查和诊断链。 |
| `references/file-lookup-dictionary.md` / `references/file-lookup-dictionary-policy.json` | 修改 | 为新政策和检查器补充查阅入口。 |
| `references/execution-guarantees.json` | 修改 | 将“人类产品表面”纳入执行保障条目。 |
| `redcap-knowledge/task-reports/2026-05-09-codex-lifecycle-hooks-candidate.md` | 移动 | 将一份无外部引用的旧活跃报告迁入私有知识归档，避免活跃 task-reports inbox 超过上限。 |
| `prism/reports/2026-05-11-rasg-019-human-product-surface.md` / `prism/reports/index.yaml` | 新建 / 修改 | 记录 Claude Code 评审、Kimi 超时和 resource-limited acceptance 结论。 |

### 3.2 技术实现要点

本轮采用“展示层治理，不削弱证据链”的解法。CLI 和状态首屏先讲人类能理解的结论，内部检查、receipt、gate、Prism 等仍保留在后续诊断区和机器字段中，避免把严谨性误删成漂亮摘要。

新增检查器不是只检查 JSON 是否存在，而是实际执行 `redcap help`、`redcap doctor`、`redcap status`、`redcap diagnose` 和飞书 formatter 样例。这样未来如果有人把 `Layer B`、`pending closure`、`active_slice` 这类内部词重新放回人类首屏，检查会直接失败。

`diagnose` 是深度体检，完整运行会比较重；检查器只验证它的开场输出，不把“人类首屏检查”变成全量诊断的时间黑洞。完整诊断仍由 `redcap diagnose` 和 spec/check 链负责。

棱镜评审采用资源受限收口：Claude Code 返回 `pass-with-fixes` 且没有阻塞项，Kimi 在窗口内没有返回完整 verdict。RedCap 将 Kimi 记录为超时证据，并只在 Claude 建议被修复后绑定 resource-limited acceptance。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|------|--------------|---------|
| 人类产品表面 | `references/human-product-surface-policy.json` | 人第一次看到的输出层，包括 CLI 帮助、体检、状态首屏、诊断开场和飞书通知。 |
| 完工凭证 | closeout receipt | 证明任务正式完成的机器证据；人类首屏用“完工凭证”表达，诊断区仍可保留 receipt 细节。 |
| 未清收尾项 | pending closure | 表示还有收尾问题没处理完；首屏用人话表达，机器区保留原始字段。 |
| 需求指纹 | confirmed_hash | 当前任务需求内容的哈希，用来区分不同版本；人类只需要知道它是“当前需求版本”。 |
| 棱镜评审 | Prism acceptance | 由外部 Agent 视角做独立评审，防止主执行者自证完成。 |

### 3.3 关联变更

本轮联动更新了文件查阅字典和执行保障，因为新增政策与检查器属于发布前关键入口，不应只散落在实现文件中。新增报告触发了活跃 task-reports inbox 上限检查，因此同步把一份无外部引用的旧报告迁入私有知识归档，保持默认 docs 入口不继续膨胀。

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 无必须人工审核项 | 本轮没有触及发布、凭据、许可证、私密资产删除或不可逆迁移。 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 人类产品表面检查 | `bash compass/tools/redcap-human-product-surface-check.sh` | ✅ |
| CLI 产品面检查 | `bash compass/tools/redcap-cli-product-surface-check.sh` | ✅ |
| 人类沟通格式检查 | `bash compass/tools/redcap-human-communication-check.sh` | ✅ |
| 文件查阅字典 | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | ✅ |
| 执行保障 | `bash compass/tools/redcap-execution-guarantee-check.sh` | ✅ |
| CLI runtime/workspace 边界 | `bash compass/tools/redcap-runtime-workspace-boundary-check.sh` | ✅ |
| package manifest | `bash compass/tools/redcap-runtime-package-manifest.sh --check` | ✅ |
| public package surface | `bash compass/tools/redcap-public-package-surface.sh` | ✅ |
| clean workspace E2E | `bash compass/tools/redcap-clean-workspace-e2e.sh --write-result --timeout 300` + `--check-result` | ✅ |
| spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | ✅ |
| architecture smell backlog | `bash compass/tools/redcap-architecture-smell-governance-check.sh` | ✅ |
| task report check | `bash compass/tools/redcap-task-report-check.sh "$PWD" 620e106fc532fc0e3c3eb44da201e23858ce169a HEAD codex` | ✅ |
| validator-chain | `bash compass/tools/redcap-validator-chain.sh obligation-reconcile codex .dev-task.md ... text` | ✅ |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | ✅ resource-limited-pass |
| diagnose | `./bin/redcap diagnose --workspace "$PWD" --task-file .dev-task.md` | ✅ |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 无必须人工验证项。

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 待 closeout 核对 |
| 棱镜验收 | 通过（resource-limited-pass） |
| closeout summary | `无` |
| closeout receipt | `无` |
| rescue audit（如有） | `无` |

说明：本轮曾出现一次旧宿主兜底留下的 pending closure。Cap 已在 validator-chain 证明 review、PM gate、drift、task-report、artifact lifecycle 等红线均通过后，通过 RedCap 自有 pending-closure 清理函数记录式清账；当前状态为 `pending_closure=no`、`promise=4/4`，等待提交后生成正式 receipt。

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是，resource-limited Prism acceptance |
| 已正式完成 | 否，receipt 尚未生成 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| RASG-020 public/internal runtime contract | 这是单独的发布前债务，需要区分公开运行时和维护者治理检查。 | P1 |
| RASG-021 Prism degradation metrics | 这是单独的棱镜韧性债务，需要统计 provider 降级频率和结论门可靠性。 | P1 |
| 全量历史文档改写 | 会破坏考古锚点且范围过大，本轮只治理关键默认输出表面。 | P2 |

### 6.2 触发的新问题

暂无新增必须登记的坏味；本轮发现并处理了“首屏检查不能拖成全量诊断”的检查器性能边界，以及“新增报告导致活跃 task-reports inbox 超上限”的活跃窗口治理问题。

### 6.3 推荐的下一步行动

1. 提交 clean workspace E2E 重锚结果。
2. 通过 closeout runtime 生成正式 receipt。
3. 转入 RASG-020 或 RASG-021。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| 无新增 Lesson | 无 | 本轮是既有“人类可读输出”原则的工程化落地，暂不新增独立 lesson。 |

### 7.2 流程改进建议

后续凡是新增人类入口，都应同时补“真实样例检查”，而不是只补政策文案或 JSON 结构检查。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选 | 本轮未发现需要晋升为独立长期演进项的新能力 | no-promote | 本报告与 Prism 报告 |

---

## 八、附录

### 附录 A：Commits

```
待提交
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| acceptance-review | RASG-019 人类产品表面是否可接受 | resource-limited-pass；Claude Code 无阻塞，Kimi 超时已记录 | `prism/reports/2026-05-11-rasg-019-human-product-surface.md` |
