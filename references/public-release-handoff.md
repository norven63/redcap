# Public Release Handoff

> 这份文件回答一个很实际的问题：如果下一步真的要进入公开 npm/CLI 发布任务，工程侧已经准备好了什么，还剩哪些必须由 Norven 明确授权。

## 当前可以确认的事

- RedCap 已有可运行的 CLI 入口：`redcap revive`、`redcap status`、`redcap diagnose`、`redcap closeout`、`redcap package-manifest`、`redcap publish-safety`、`redcap package-surface`、`redcap pre-release-review`。
- npm 包面已经从“把所有 RedCap 自维护工具都带上”收窄为“运行时、复活、诊断、收尾、Prism 可用性、发布安全预检和交接文档”这一组公开候选。
- `redcap diagnose` 面向未来包用户时默认使用 runtime profile，只做运行时/发布安全相关体检；源码仓库维护者仍可用 `REDCAP_DIAGNOSE_PROFILE=source bash compass/tools/redcap-diagnose.sh` 跑完整治理链。
- 包内容按“源码对用户可见”处理：安全边界来自显式排除、扫描和 dry-run，不依赖混淆或隐藏源码。
- `redcap-arsenal` 只能声明已有首批 Forge 审查样本，不能声明已经完成历史知识迁移或成熟公共知识库。

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
- 如果 Norven 明确启动正式 release task，RedCap 应先重新运行 package manifest、publish safety、package surface、pre-release review、Prism review 和 clean workspace E2E，再触碰发布开关。
- 如果任一安全扫描失败，release task 必须 fail closed，不允许“先发再修”。
