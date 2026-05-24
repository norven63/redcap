# 任务完成报告：RASG-020 公开 runtime 契约与维护者工具分层

**报告日期**：2026-05-11  
**执行者**：Cap（Codex.app + Prism：Claude Code / Kimi）  
**报告版本**：v0.3

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：RedCap 已把未来普通用户可依赖的 CLI/runtime 命令，和维护者才该使用的发布准备、源码治理命令分开，并通过机器检查和棱镜评审。
- 详情：本轮解决的是发布前产品边界问题。以后即便 npm 候选包里为了 readiness 暂时保留维护者检查器，它们也不会被 README、help、runtime import map 或 package policy 误写成普通用户稳定 API。

### 0.2 上一步完成的是

- 上一步完成的是：RASG-019 已把 CLI、状态、诊断和飞书通知的人类首屏改成“先讲人话、再给证据”。

### 0.3 下一步计划做的是

- 下一步计划做的是：完成 closeout receipt 和提交，然后转入 RASG-021。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：历史债务治理 -> RASG-017 根目录目标模型 -> RASG-019 人类可读产品表面 -> RASG-020 公开/维护者契约分层 -> RASG-021 Prism 降级韧性 -> 正式发布准备。
- 当前所在位置：当前位于 RASG-020 的最终收口阶段；实现、本地回归和棱镜评审均已完成。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮没有触碰许可证、registry 凭据、`private=false`、`publish_allowed=true`、`npm publish` 或不可逆资产删除。

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> “好的，你们开始推进吧”

### 1.2 触发背景

RASG-018 的全局审判指出：当前 npm 候选包面仍混合了普通 runtime 入口、维护者治理检查和发布准备工具。如果不先分层，将来即使安全扫描通过，普通用户也可能被迫理解 RedCap 内部维护机械，维护者工具还可能被误冻结为稳定公开 API。

### 1.3 原始意图覆盖审计

| 项 | 结论 |
|---|---|
| scope_status | partial-with-explicit-defer |
| 原始意图 | 继续推进正式发布前剩余坏味治理。 |
| 已覆盖 | 本轮覆盖公开 runtime 命令、维护者发布准备命令、源码治理命令、候选包面分类、README/help/handoff/import-map 口径与机器检查器。 |
| 未覆盖/延期 | RASG-021 Prism 降级频率、正式 npm 发布、许可证/registry 决策、完整工具树物理迁移。 |
| 用户可见边界 | 本轮完成后只能声明“公开/维护者契约边界已固化并可检查”，不能声明 release-ready 或 npm publish 已发生。 |
| 后续路径 | 完成本轮 closeout 后继续推进 RASG-021。 |

---

## 二、方案讨论

### 2.1 问题分析

问题不是 RedCap 缺少发布安全检查，而是缺少“产品契约分层”。一个工具能被打包，不代表它就是普通用户稳定 API。RedCap 当前仍需要一些维护者检查器来保护 alpha readiness，但这些检查器必须被标记为维护者支持工具，而不是用户日常流程。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 直接从包里删掉维护者工具 | 候选包只保留极小 runtime | 包面最干净 | 风险高，可能破坏 diagnose、spec-check 和发布前安全检查 |
| Q1 | 保留但明确分层 | 继续保留 alpha readiness 所需支持工具，同时建立公开/维护者契约政策和检查器 | 稳妥，不削弱安全门 | 候选包仍不是最终 public runtime 最小形态 |
| Q1 | 暂不处理 | 等正式发布时再决定 | 当前工作少 | 会让发布前风险继续沉积 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 保留但明确分层 | 当前阶段更重要的是不破坏安全检查，同时把“公开 API”和“维护者支持工具”说清并机器化检查。正式发布任务可再决定是否裁剪或拆 maintainer profile。 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `.dev-task.md` | 修改 | 将当前任务从 RASG-019 完成态重锚到 RASG-020。 |
| `references/runtime-public-contract-policy.json` | 新建 | 定义普通 runtime 命令、维护者发布准备命令、源码治理命令、候选包面分类和禁止声明。 |
| `compass/tools/redcap-runtime-contract-surface-check.py` / `.sh` | 新建 | 基于真实 package candidate list 分类所有候选文件，并检查 help/import-map/docs/policies 是否同口径。 |
| `runtime/redcap-core/import-map.json` | 修改 | 将 package-manifest/publish-safety/package-surface/pre-release-review 从 public runtime entrypoints 拆到 maintainer release entrypoints。 |
| `bin/redcap` / `compass/tools/redcap-cli-product-surface.py` | 修改 | 帮助输出分成普通使用命令、维护/发布准备命令、源码仓库治理命令。 |
| `references/runtime-package-readiness-policy.json` / `references/public-package-surface-policy.json` / `references/package-publish-safety-policy.json` | 修改 | 三处发布相关政策共同引用 runtime public contract policy，并承认 alpha readiness split contract。 |
| `README.md` / `references/public-release-handoff.md` / `runtime/redcap-core/README.md` | 修改 | 用人话解释普通用户命令和维护者命令的区别，避免将维护者工具包装成用户日常流程。 |
| `compass/tools/redcap-spec-check.sh` / `compass/tools/redcap-diagnose.sh` | 修改 | 将 runtime contract surface 检查接入规范检查和源码诊断链。 |
| `references/file-lookup-dictionary.md` / `references/file-lookup-dictionary-policy.json` / `references/execution-guarantees.json` | 修改 | 补齐查阅入口和执行保障。 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 修改 | 补齐新增门禁在 spec-check 故障传播验收里的 fixture，避免测试夹具先被缺脚本打断。 |

### 3.2 技术实现要点

本轮新增的核心不是一个“又多一个 JSON”，而是一条产品边界：普通用户将来应该先认识 runtime 命令，而不是先认识 RedCap 自维护检查器。机器检查器会实际生成候选包文件列表并给每个文件分类；如果出现无法归类的候选、被禁止的私有路径、或把 `compass/tools/**` 这类内部支持文件标成公开 API，检查会失败。

当前候选包面为 181 个文件。这个数字仍属于 alpha readiness surface，不是最终 public runtime 最小包面。正式发布任务仍需要重新决定：继续保留维护者工具、裁剪成更小 runtime profile，还是拆出单独 maintainer profile。

Kimi 评审发现 `prism-availability` 已经是公开命令但 import map 没单独表达，且检查器缺少“所有公开命令都必须被 import map 覆盖”的反向完整性检查。本轮已修复这两个点：`redcap prism-availability` 现在是独立公开入口，检查器会阻止公开命令和 import map 再次漂移。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 人话解释 | 本轮作用 |
|------|---------|---------|
| 公开 runtime 契约 | 普通用户安装 RedCap 后可以依赖的日常命令，例如 revive/status/doctor/diagnose/closeout。 | 防止用户把维护者检查器误当成日常 API。 |
| 维护者发布准备命令 | 准备发布时才需要跑的检查，例如 package-manifest、publish-safety、package-surface、pre-release-review。 | 保留发布安全能力，但不把它们包装成普通用户流程。 |
| 源码治理命令 | RedCap 自己维护自己的命令，例如 file-dictionary、shared-knowledge、change-intake。 | 继续服务源码仓库治理，不进入用户首要认知面。 |
| alpha readiness surface | 还没正式发布前，为了安全和回归暂时保留的候选包面；不是最终 API 承诺。 | 说明当前 181 个候选文件不是最终公开最小包。 |

---

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 无必须人工审核项 | 本轮未触发许可证、发布、凭据、删除或不可逆迁移边界。 | P2 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| runtime contract surface | `bash compass/tools/redcap-runtime-contract-surface-check.sh` | ✅ |
| package manifest + npm dry-run | `bash compass/tools/redcap-runtime-package-manifest.sh --check --npm-pack-dry-run --json` | ✅ |
| public package surface | `bash compass/tools/redcap-public-package-surface.sh --json` | ✅ |
| publish safety | `bash compass/tools/redcap-package-publish-safety-check.sh` | ✅ |
| human product surface | `bash compass/tools/redcap-human-product-surface-check.sh` | ✅ |
| file lookup dictionary | `bash compass/tools/redcap-file-lookup-dictionary-check.sh` | ✅ |
| execution guarantees | `bash compass/tools/redcap-execution-guarantee-check.sh` | ✅ |
| pre-release architecture | `bash compass/tools/redcap-pre-release-product-architecture-check.sh` | ✅ |
| spec-check gate propagation | `bash compass/tools/redcap-multi-session-acceptance.sh spec-check-propagates-control-gate-failures` | ✅ |
| spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | ✅ |
| diagnose | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | ✅ |
| Prism acceptance | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | ✅ |
| information architecture | `bash compass/tools/redcap-information-architecture-check.sh` | ✅ |
| cold archive inventory | `bash compass/tools/redcap-cold-archive-inventory.sh check` | ✅ |

### 5.2 Prism 评审

| Provider | 角色 | 状态 | 结论 |
|---|---|---|---|
| Claude Code | reviewer | responded | `pass`，无阻塞项 |
| Kimi | challenger | responded | `pass-with-fixes`，两个补强项已修复 |
| Copilot | - | 未调用 | 按保护策略，Claude Code 与 Kimi 可用时不调用 |

### 5.3 closeout runtime / receipt

| 项目 | 结果 |
|------|------|
| 执行承诺账本 | 待 closeout 核对 |
| 棱镜验收 | 已绑定并通过 |
| closeout receipt | 待生成 |

### 5.4 完成等级（禁止混报）

| 等级 | 结果 |
|------|------|
| 已实现 | 是 |
| 已自检 | 是 |
| 已独立验收 | 是 |
| 已正式完成 | 否，receipt 尚未生成 |

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| RASG-021 Prism degradation metrics | 这是独立的 Prism 韧性债务。 | P1 |
| 正式 npm 发布 | 仍需要许可证、registry 权限、发布开关和正式 release task。 | 人工边界 |
| 最终 public runtime 最小包面裁剪 | 本轮选择 alpha readiness 分层，不做破坏性裁剪。 | release task 内再决策 |

### 6.2 触发的新问题

本轮发现并修复了两个回归类问题：

- RASG-019 的人类产品表面检查还期待旧标题“常用命令”，现已改为“普通使用命令”。
- spec-check 故障传播验收缺少新增门禁 fixture，现已补齐 human-product-surface、progress-meter 和 runtime-contract-surface。
- active task-reports 因新增报告超过上限 1 个；已将无外部引用的旧报告 `2026-05-10-change-intent-continuity-gate.md` 归档到 `redcap-knowledge/task-reports/`，并刷新 docs catalog 与 cold archive inventory。

### 6.3 推荐的下一步行动

1. 生成 closeout receipt。
2. 提交 RASG-020。
3. 转入 RASG-021。

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| 无新增 Lesson | 无 | 本轮是既有“发布前契约边界必须机器化”的落地，暂不新增独立 lesson。 |

### 7.2 流程改进建议

后续新增 CLI 命令时，不仅要考虑“能不能路由”，还要同步判断它属于普通用户 runtime、维护者发布准备，还是源码治理工具。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
|------|------|----------|------|
| 无新增候选 | 本轮没有发现需要晋升为独立长期演进项的新能力 | no-promote | 本报告与后续 Prism 报告 |

---

## 八、附录

### 附录 A：Commits

```
待提交
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| acceptance-review | RASG-020 公开 runtime 契约与维护者工具分层是否可接受 | pass-after-fixes | `prism/reports/2026-05-11-rasg-020-runtime-contract-surface.md` |
