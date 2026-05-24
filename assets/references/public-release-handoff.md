# Public Release Handoff

> 这份文件回答一个很实际的问题：如果下一步真的要进入公开 npm/CLI 发布任务，工程侧已经准备好了什么，还剩哪些必须由 Norven 明确授权。

## 先看这里：正式发布准备的两个新入口

- 机器权威路线图：`references/formal-release-readiness-plan.json`。它把正式发布前后拆成 10 个阶段：任务锚点、延期根目录处置、包面收紧、CLI 体验、安全审计、E2E、人类决策、棱镜终审、registry 执行和发布后监控。
- 授权矩阵：`references/release-authorization-matrix.json`。它区分 Norven 必须决策、Cap + Prism 可自主决策，以及可提前给出的条件授权。
- 历史资产物理清理硬门：`references/historical-asset-physical-cleanup-release-gate.json`。它把“历史资产不能污染公开包或新用户运行面”升级为正式发布前硬门；没过这道门时，不允许进入真实发布动作。
- 高价值经验候选化硬门：`references/evolution-harvest-signal-policy.json`。它把 review、发布安全、测试失败、用户纠偏、递归/进程风暴等高价值信号接到 Evolution Factory 候选判断；没过这道门时，不允许把发布任务推进到授权或 registry 动作。
- E2E 边界仍以 `references/release-readiness-e2e-matrix.json` 为准；没有通过对应矩阵时，不能把发布准备说成正式发布已就绪。

## 当前可以确认的事

- RedCap 已有可运行的 CLI 入口：`redcap revive`、`redcap status`、`redcap diagnose`、`redcap closeout`、`redcap package-manifest`、`redcap publish-safety`、`redcap package-surface`、`redcap pre-release-review`。
- 普通用户日常依赖的是 `redcap revive`、`redcap status`、`redcap doctor`、`redcap diagnose`、`redcap debug`、`redcap closeout`、`redcap prism-availability`、`redcap help` 和 `redcap version`。
- `redcap package-manifest`、`redcap publish-safety`、`redcap package-surface`、`redcap pre-release-review` 是维护者发布准备命令，不是普通用户日常 workflow。它们可以在 alpha readiness 阶段保留，但正式 release task 必须再次决定是否裁剪到单独 maintainer profile。
- npm 包面已经从“把所有 RedCap 自维护工具都带上”收窄为“运行时、复活、诊断、收尾、Prism 可用性、发布安全预检、契约边界说明和交接文档”这一组公开候选。
- `redcap diagnose` 面向未来包用户时默认使用 runtime profile，只做运行时/发布安全相关体检；源码仓库维护者仍可用 `REDCAP_DIAGNOSE_PROFILE=source bash compass/tools/redcap-diagnose.sh` 跑完整治理链。
- 包内容按“源码对用户可见”处理：安全边界来自显式排除、扫描和 dry-run，不依赖混淆或隐藏源码。
- 公开 runtime / 维护者工具的机器可读边界见 `references/runtime-public-contract-policy.json`。
- `redcap-arsenal` 只能声明已有首批 Forge 审查样本，不能声明已经完成历史知识迁移或成熟公共知识库。
- 历史资产物理清理现在是 release-readiness 硬门：包面排除只能证明“不打进包”，不能单独证明“历史资产已经搬干净”；正式发布任务必须逐类给出物理迁移、私有归档、公共晋升或继续阻断发布的证据。
- 高价值经验候选判断现在也是 release-readiness 硬门：`evolution-candidate-check --strict` 只能检查已登记候选，正式发布任务还必须通过 `evolution-harvest` 证明“该登记的经验已经被判断为 promoted / no-promote / deferred-with-owner”。

## 仍然不能由 Agent 擅自完成的事

- 选择许可证。
- 把 `package.json.private` 改成 `false`。
- 把 `references/runtime-package-readiness-policy.json` 的 `publish_allowed` 改成 `true`。
- 登录或操作 npm registry。
- 运行 `npm publish`。
- 宣布 RedCap 已经 public-release-ready。

## 进入正式发布任务前的人工输入

正式 release task 至少需要 Norven 明确给出：

- 发布许可证，例如 MIT、Apache-2.0、私有/闭源继续保留，或其他选择。
- 是否公开发布到 npm，以及是否只做内部/私有包验证。
- npm scope `@norven63/redcap` 的账号权限是否已准备好。
- 发布版本号、发布窗口、失败回滚或撤回策略。

## RedCap 下一步应如何使用这份 handoff

- 如果 Norven 尚未给出上面的人工输入，RedCap 只能继续做非发布类治理，不得进入发布动作。
- 如果 Norven 明确启动正式 release task，RedCap 应先重新运行历史资产物理清理硬门、Evolution harvest signal gate、package manifest、publish safety、package surface、pre-release review、Prism review 和 clean workspace E2E，再触碰发布开关。
- 正式 release task 的 E2E 覆盖面以 `references/release-readiness-e2e-matrix.json` 为准；其中外部机器 / 多 OS 验证仍属于正式发布任务内的待执行项，不能由本地 clean workspace E2E 代替。
- 如果任一安全扫描失败，release task 必须 fail closed，不允许“先发再修”。
- 如果历史资产物理清理硬门仍有 unresolved blocker，release task 必须停在发布前治理阶段，不得向 Norven 索要或使用外部 registry 发布授权。
- 如果 Evolution harvest signal gate 仍有 unresolved blocker，release task 必须停在发布前治理阶段，不得把“候选池当前无未处理项”冒充为“本任务没有新经验需要判断”。
