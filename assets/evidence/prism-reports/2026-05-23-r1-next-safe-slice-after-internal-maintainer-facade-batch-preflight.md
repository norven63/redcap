# Prism 报告：P4-22 下一安全切片选择

## 结论

Claude Code 与 Kimi 形成一致结论：P4-22 的下一条安全切片应选择 A，也就是继续 internal-control-plane 的小批次 copy-first facade 路线。

这不是正式发布，也不是下一批 facade 的实施。本轮只完成路线裁决，并保持所有 release blockers open。

## 为什么选择 A

P4-21 已经证明小批次 facade 模式可行：新入口只委托旧 `compass/tools`，旧锚点仍然权威，不触碰发布开关、Prism raw evidence 或 Layer A 产品边界。

相比之下：

- B 可以作为后续 preflight，但不如继续 P4-21 已验证路线直接。
- C 是安全候选，但会把注意力转回 Prism 旧报告入口，不如先继续消解 internal-control-plane。
- D 涉及 raw evidence cleanup，必须保留为人工硬门。
- E 涉及 Layer A 产品边界，必须保留为人工硬门。
- F 在 blockers 仍存在时过早。

## 约束

- 不执行被选中切片本身。
- 不批量处理全部 111 个 internal-control-plane 条目。
- 不删除、移动、替换或 symlink 切换旧锚点。
- 不清理 `prism/runs` raw evidence。
- 不修改发布开关、许可证、registry 或凭据。
- 不触碰 Layer A 产品边界。

## 下一步

登记 P4-23：继续 internal-control-plane 小批次 copy-first facade，批次规模不得超过 P4-21，仍然保持旧 `compass/tools` 权威。
