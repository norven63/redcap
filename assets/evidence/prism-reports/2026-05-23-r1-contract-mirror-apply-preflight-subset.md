# Prism 报告：P4-27 小范围合同镜像 apply 预检

**运行 ID**：20260523-r1-contract-mirror-apply-preflight-subset
**verdict**: consensus

## 结论

Claude Code 与 Kimi 形成共识：P4-27 可以作为“小范围合同镜像 apply 预检”收口。

这里的“可以收口”只表示预检成立，不表示已经实施合同镜像。两位评审都确认：本轮没有创建 `contracts/**` 目标文件，没有复制、移动、删除或替换旧锚点，也没有触碰发布开关、许可证、registry、凭据、raw evidence cleanup 或 Layer A 产品边界。

## 为什么通过

P4-27 只从 P4-25 已分类的 public/internal contract 候选里挑出 7 个条目，作为未来 copy-first apply 的预检样本。这个范围足够小，能验证目标路径、源文件哈希、回滚策略和停止条件，又不会把“预检”误升级成“迁移实施”。

两位评审重点确认了三点：

- 7 个未来目标路径现在都不存在，因此本轮没有发生真实 apply。
- 4 个 public-contract 与 3 个 internal-contract 条目的来源、哈希和分类能对上。
- manifest 和 checker 都把 release blocker 保持为 open，并明确下一步只能继续做 route-selection。

## 仍然不能宣称的内容

- 不能说合同镜像已经实施。
- 不能说旧 `references/**` 锚点已经退休。
- 不能说 Prism raw evidence 已经清理。
- 不能说 Layer A 产品边界已经裁决。
- 不能说 RedCap 已经可以正式公开发布。

## 下一步

P4-27 收口后，下一步应进入 P4-28：继续做路线选择。P4-28 仍只能判断下一条安全切片，不能自动升级为真实迁移、删除、发布或凭据处理。
