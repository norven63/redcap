# Prism 报告：P4-24 P4-23 后下一安全切片选择

## 结论

Claude Code 与 Kimi 对下一步产生了健康分歧：Claude Code 建议 B，先做 internal-control-plane 的 public/internal contract mirror preflight；Kimi 建议 A，继续第三个小批次 facade。

Cap 裁决选择 B。原因是 P4-21 与 P4-23 已经连续完成两批 facade，继续第三批当然安全，但边际收益开始下降。下一步先把 public/internal contract 边界预检做清楚，可以降低后续真实迁移、包面收敛和旧锚点退休的风险。

这不是正式发布，也不是 contract mirror 的实施。本轮只完成路线裁决，并保持所有 release blockers open。

## 为什么选择 B

B 是 preflight-only 路线，不移动、不删除、不替换、不 symlink 切换任何旧锚点，也不触碰 registry、license、credentials、Prism raw evidence cleanup 或 Layer A 产品边界。

相比之下：

- A 仍然安全，但会继续堆 facade，可能让 internal-control-plane 的契约边界继续模糊。
- C 也是安全候选，但当前更优先的是把 internal-control-plane 自身的 public/internal 边界说清。
- D 涉及 raw evidence cleanup，必须保留为人工硬门。
- E 涉及 Layer A 产品边界，必须保留为人工硬门。
- F 在 blockers 仍存在时过早。

## 约束

- 不执行被选中切片本身。
- 不批量处理全部 internal-control-plane 条目。
- 不删除、移动、替换或 symlink 切换旧锚点。
- 不清理 `prism/runs` raw evidence。
- 不修改发布开关、许可证、registry 或凭据。
- 不触碰 Layer A 产品边界。

## 下一步

登记 P4-25：只做 internal-control-plane public/internal contract mirror preflight。P4-25 仍必须是预检，不允许物理迁移或关闭 release blocker。
