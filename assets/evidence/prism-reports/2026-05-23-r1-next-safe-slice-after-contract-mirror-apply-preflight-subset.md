# Prism 报告：P4-28 P4-27 后下一安全切片路线选择

**运行 ID**：20260523-r1-next-safe-slice-after-contract-mirror-apply-preflight-subset
**verdict**: consensus

## 结论

Claude Code 与 Kimi 形成共识：P4-28 应选择路线 A，即把 P4-29 登记为下一条安全切片。

人话解释：P4-28 只是决定“下一刀是什么”，不是现在就动文件；也就是说，本轮不实施 P4-29。下一刀 P4-29 可以被登记为 7 个合同文件的 copy-first apply：后续只允许把 P4-27 已预检的 7 个文件复制到 `contracts/public/**` 和 `contracts/internal/**`，旧的 `references/**` 锚点必须继续保留和可读。

## 为什么通过

两位评审都确认了同一个判断：P4-27 已完成 7 个文件的小范围预检，目标路径、哈希、回滚条件和停止条件都已经清楚；继续重复预检收益不高，直接进入正式发布、证据清理或 Layer A 产品裁决又会跨人工硬门。

因此最稳妥的路线是：P4-28 只登记 P4-29，不执行 P4-29。这样可以继续自动推进父任务线，同时不绕过删除、发布、凭据、许可证、raw evidence cleanup 或 Layer A 产品边界这些人工保留决策。

## 仍然不能宣称的内容

- 不能说 P4-29 已经执行。
- 不能说 `contracts/**` 文件已经创建。
- 不能说合同镜像 copy-first apply 已完成。
- 不能说旧 `references/**` 锚点已经退休、删除、移动、替换或重定向。
- 不能说 Prism raw evidence 已经清理。
- 不能说 Layer A 产品边界已经裁决。
- 不能说 RedCap 已经可以正式公开发布。

## 下一步

P4-28 收口后，父任务线焦点应推进到 P4-29。P4-29 如果执行，必须是单独任务、单独 Prism 评审、单独 checker、单独 closeout；它可以做 bounded copy-first apply，但仍不得删除旧锚点、清理 raw evidence、修改发布设置或关闭 release blocker。
