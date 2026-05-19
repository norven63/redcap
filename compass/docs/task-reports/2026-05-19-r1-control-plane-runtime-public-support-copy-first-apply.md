# 任务完成报告：R1 控制面 runtime facade copy-first

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：`internal-control-plane` 的 batch-1 `runtime-public-support` 条目已经从“只有未来迁移地图”推进到“已有 runtime facade 入口”的状态。
- 详情：本轮新增的是 `runtime/redcap-core/tools` 下的轻量外壳入口；这些入口只把调用转发回旧的 `compass/tools` 权威实现，不复制旧实现内容，不移动、不删除、不替换旧锚点。

### 0.2 上一步完成的是

- 上一步完成的是：P4-5 已为 Prism evidence 建立 apply 前置护栏，并完成 closeout；它没有移动、删除或清理任何 Prism 证据。

### 0.3 下一步计划做的是

- 下一步计划做的是：用 closeout runtime 生成正式 receipt，并把 P4-6 标为 done。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：正式发布准备路线 → R1 延期根目录分类 → 控制面契约拆分预检 → 控制面 dry-run 地图 → 控制面 apply 预检 → 控制面 runtime facade copy-first → 后续 batch-2 / batch-3 / 真实旧锚点处理 / 最终发布授权。
- 当前所在位置：`framework-upgrade / P4-6`，处于 `internal-control-plane` batch-1 runtime facade copy-first 阶段。

### 0.5 是否需要 Norven 人工介入

- 人工介入：不需要。
- 说明：本轮不触碰许可证、发布开关、registry 凭据、真实发布、旧锚点删除、batch-2 / batch-3、Prism evidence cleanup 或 Layer A 产品范围裁决。

## 一、需求背景

P4-4 已经把 `compass/tools` 与 `references` 这组控制面资产拆成了未来迁移地图，并识别出 47 个 `runtime-public-support` 条目：这些工具是 revive、status、diagnose、closeout、package safety、runtime manifest 等运行时体验会依赖的入口。

但 P4-4 仍停留在 apply preflight：它说明“未来该怎么安全动手”，还没有给 runtime 包面提供真实可调用入口。这个缺口会让 RedCap 在向 CLI/runtime 产品形态推进时，继续依赖旧 `compass/tools` 路径作为用户可见入口，导致“运行时包面”和“维护者控制面”边界不够清楚。

本轮要解决的是这个最小可自主推进切片：先为 47 个 runtime-public-support 条目建立 copy-first facade，让 runtime 包面有可检查入口；同时保留旧 `compass/tools` 作为权威实现，避免大规模搬迁带来的断链风险。

## 二、方案讨论

### 2.1 如何解决

本轮采用“轻量外壳、旧实现委托”的方式，而不是直接复制旧脚本内容。原因是很多旧脚本会根据自身路径计算 RedCap 根目录；如果把脚本内容复制到 runtime 目录，可能会让路径推断发生偏移，引入隐蔽 bug。

因此新 facade 只做一件事：定位 RedCap 根目录，然后转调对应的旧 `compass/tools` 文件，并保留原始参数。Python facade 使用 `runpy` 执行旧脚本；Shell facade 使用 `exec bash` 转发给旧脚本。

### 2.2 边界裁决

本轮只覆盖 batch-1 `runtime-public-support`。以下内容明确不做：

- 不执行 batch-2 policy / contract 分类。
- 不执行 batch-3 maintainer control-plane tools。
- 不移动、删除、重命名或替换任何旧 `compass/tools`、`compass/` 或 `references/` 锚点。
- 不关闭 `internal-control-plane` release blocker。
- 不执行真实发布或修改发布开关。

## 三、落地结果

### 3.1 当前效果

现在 `runtime/redcap-core/tools` 下有 47 个 facade，覆盖 P4-4 batch-1 的全部 runtime-public-support 条目。每个 facade 都可执行，并且都显式委托到对应旧 `compass/tools` 权威脚本。

这让 runtime 包面向“可安装 CLI/runtime”形态前进了一步，但仍保持安全姿态：旧控制面没有被迁走，正式发布 blocker 仍保持开放。

### 3.2 已验证

- `bash compass/tools/redcap-r1-control-plane-runtime-public-support-copy-first-apply-check.sh`
- `bash compass/tools/redcap-multi-session-acceptance.sh r1-control-plane-runtime-public-support-copy-first-apply-check`
- `bash compass/tools/redcap-r1-control-plane-contract-split-check.sh`
- `bash compass/tools/redcap-r1-control-plane-physical-apply-preflight-check.sh`
- `bash compass/tools/redcap-public-package-surface.sh`
- `bash compass/tools/redcap-spec-check.sh "$PWD"`
- `bash compass/tools/redcap-diagnose.sh .dev-task.md`
- `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md`
- `bash compass/tools/redcap-clean-workspace-e2e.sh`

### 3.2.1 术语对照（按文件/功能解释）

| 术语 / 文件 | 人话解释 | 本轮作用 |
| --- | --- | --- |
| runtime facade | 放在 runtime 目录下的兼容入口 | 让外部 runtime 包面可以调用工具，但不复制旧实现 |
| copy-first | 先增加新入口，旧入口继续保留 | 降低大规模迁移导致断链的风险 |
| old anchor | 旧的 `compass/tools` 路径 | 本轮仍是权威实现，不能删除或替换 |
| batch-1 runtime-public-support | P4-4 识别出的第一批运行时支撑工具 | 本轮只处理这一批，共 47 个 |
| release blocker | 正式发布前必须解决的问题 | 本轮不关闭 blocker，只推进一个安全切片 |

## 四、人工审核要点

| 序号 | 审核项 | 说明 | 优先级 |
| --- | --- | --- | --- |
| 1 | 无需本轮人工审核 | 本轮不执行真实发布、许可证选择、registry 操作、旧锚点删除或破坏性迁移。 | P1 |

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 当前结果 |
| --- | --- | --- |
| runtime facade checker | `bash compass/tools/redcap-r1-control-plane-runtime-public-support-copy-first-apply-check.sh` | 通过 |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh r1-control-plane-runtime-public-support-copy-first-apply-check` | 通过 |
| control-plane contract split checker | `bash compass/tools/redcap-r1-control-plane-contract-split-check.sh` | 通过 |
| physical apply preflight checker | `bash compass/tools/redcap-r1-control-plane-physical-apply-preflight-check.sh` | 通过 |
| public package surface checker | `bash compass/tools/redcap-public-package-surface.sh` | 通过 |
| full spec-check | `bash compass/tools/redcap-spec-check.sh "$PWD"` | 通过 |
| diagnose | `bash compass/tools/redcap-diagnose.sh .dev-task.md` | 通过 |
| Prism acceptance binding | `bash compass/tools/redcap-prism-acceptance-check.sh --task-file .dev-task.md` | 通过 |
| clean workspace E2E | `bash compass/tools/redcap-clean-workspace-e2e.sh` | 通过 |

### 5.2 人工验证项

- 无。本轮不需要 Norven 做产品、发布、许可证、registry、删除或清理决策。

### 5.3 closeout runtime / receipt

| 项目 | 当前结果 |
| --- | --- |
| 执行承诺账本 | 待 closeout runtime 核对 |
| 棱镜验收 | 已通过；Claude Code 与 Kimi 均给出 pass，Gemini 不可用且 Copilot 按策略未调用 |
| closeout receipt | 待生成 |

### 5.4 完成等级（禁止混报）

| 层级 | 结论 | 说明 |
| --- | --- | --- |
| 已实现 | 是 | facade、manifest、checker、targeted acceptance 和包面快照同步已落地。 |
| 已自检 | 是 | targeted checks、full spec-check、diagnose 与 clean workspace E2E 均已通过。 |
| 已独立验收 | 是 | Prism formal acceptance 已绑定，2 个不同模型家族均无 blocker。 |
| 已正式完成 | 否 | closeout receipt 尚未生成。 |

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
| --- | --- | --- |
| batch-2 policy / contract 分类 | 本轮只处理 runtime-public-support facade，避免一次性扩大迁移面。 | P0-before-release |
| batch-3 maintainer control-plane tools | 仍是更大的维护者控制面迁移切片，需要独立评审。 | P0-before-release |
| 旧 `compass/tools` delete-last | 本轮禁止旧锚点删除；未来必须有 alias proof、clean E2E、Prism review 和用户授权边界。 | P0-before-release |
| 真实发布 | 本轮不修改发布开关、许可证、registry 或凭据。 | manual-release-boundary |

### 6.2 触发的新问题

- 新增 facade 使包候选数量从 214 变为 264；相关包面和 R1 快照已同步为当前事实，但不代表 release blocker 关闭。

### 6.3 推荐的下一步行动

1. 通过 closeout runtime 生成 receipt，并把 P4-6 标为 done。

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
| --- | --- | --- |
| L-new-runtime-facade-delegation | runtime facade 优先委托旧实现而不是复制旧实现 | 当旧脚本依赖自身路径推断仓库根目录时，copy-first 的第一步应优先使用 facade 委托，避免复制实现后路径语义漂移。 |

### 7.2 流程改进建议

控制面物理拆分不要一次性“搬目录”。更稳的顺序是：先建立 dry-run 地图，再建 apply preflight，再建 runtime facade，最后才考虑 batch-2 / batch-3 和 delete-last。这样每一步都有可审计的范围边界。

### 7.3 Evolution Factory 候选处理

| 候选 | 来源 | 处理结果 | 证据 |
| --- | --- | --- | --- |
| EVO-2026-05-19-001 / runtime facade 优先委托旧实现而不是复制旧实现 | 本轮 P4-6 实施 | promoted；已沉淀为 `L-168`，后续同类迁移先 facade 委托，再评估物理迁移 | 本报告、`references/r1-control-plane-runtime-public-support-copy-first-apply.json` 与 `compass/knowledge/lessons/l-168.md` |

## 八、附录

### 附录 A：相关文档索引

- 当前任务卡：`.dev-task.md`
- 本轮 apply manifest：`references/r1-control-plane-runtime-public-support-copy-first-apply.json`
- 上游物理 apply preflight：`references/r1-control-plane-physical-apply-preflight.json`
- 上游 contract split preflight：`references/r1-control-plane-contract-split-preflight.json`
- 本轮 checker：`compass/tools/redcap-r1-control-plane-runtime-public-support-copy-first-apply-check.sh`

## 九、剩余边界

本轮不可声明：

- `internal-control-plane` 已完整物理拆分。
- 旧 `compass/tools` 已迁移、删除、替换或不再权威。
- batch-2 或 batch-3 已完成。
- `internal-control-plane` blocker 已解决。
- RedCap 已 public-release-ready。
- 可以进入真实 registry publication。

## 十、棱镜状态

P4-5 后下一步路线评审已完成；本轮正式 Prism acceptance 也已完成并绑定到 `.dev-task.md`。Claude Code 与 Kimi 均给出 pass；Gemini 当前不可用，Copilot 按配额保护策略未调用。

## 十一、旁路归档说明

本轮为了维持活跃 task-report 数量上限，将旧报告 `compass/docs/task-reports/2026-05-13-rasg-022-root-ia-shared-knowledge-tranche.md` 迁入 `private-archive/redcap-knowledge/task-reports/2026-05-13-rasg-022-root-ia-shared-knowledge-tranche.md`，并同步更新 Root IA deferral 证据路径、docs catalog、reference asset lifecycle 与 cold archive inventory。

这不是 P4-6 的功能目标，也没有移动或替换任何 `compass/tools` 旧实现；它只是为了防止活跃报告区再次膨胀。
