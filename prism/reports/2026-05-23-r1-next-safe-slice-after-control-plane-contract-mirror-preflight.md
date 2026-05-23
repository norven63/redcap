# Prism 报告：P4-26 P4-25 后下一安全切片选择

**运行 ID**：20260523-r1-next-safe-slice-after-control-plane-contract-mirror-preflight
**verdict**: consensus

## 结论

Claude Code 与 Kimi 这次形成共识：下一步选择 A，也就是做一个“小范围合同镜像 apply 预检”。

这句话容易误读，所以边界必须说清：P4-26 只选择路线，不实施路线。被选中的 P4-27 也必须先保持预检/计划性质，用来挑出一小组 public/internal contract 条目，验证未来如果要执行合同镜像，需要满足哪些条件、怎样回滚、怎样不破坏旧锚点。

## 为什么选择 A

P4-25 刚把 225 条控制面候选分清楚，其中 public-contract 有 11 条，internal-contract 有 55 条。与其马上继续堆更多 facade，或者切到 Prism 证据治理，当前更自然的下一步是把这批分类成果继续收窄成一个小范围、可审计、不可误报的 apply 预检。

A 的优势是：它承接 P4-25，仍然不移动、不删除、不替换旧锚点，也不触碰发布、许可证、registry、凭据、raw evidence cleanup 或 Layer A 产品边界。

## 不选择其他路线的原因

- B 仍可能是后续安全路线，但它偏实施型；在 P4-25 后，先做小范围 apply 预检更稳。
- C 也是安全预检，但会切换到 Prism blocker；当前更优先把 internal-control-plane 的合同镜像路径继续收窄。
- D 涉及 raw evidence cleanup，必须保留为人工硬门。
- E 涉及 Layer A 产品边界，必须保留为人工硬门。
- F 涉及正式公开发布，在 blocker 仍存在时过早。
- G 没必要；当前没有缺少只能由 Norven 决定的信息。

## 约束

- 不实施 P4-27。
- 不复制、移动、删除、替换或 symlink 切换旧锚点。
- 不清理 `prism/runs` raw evidence。
- 不修改发布开关、许可证、registry 或凭据。
- 不触碰 Layer A 产品边界。
- 不调用 Copilot；本轮 Claude Code 与 Kimi 已满足两家族 quorum。

## 下一步

登记 P4-27：只做小范围 public/internal contract apply preflight。它仍必须是预检，不允许物理迁移或关闭 release blocker。
