# Prism 报告：P4-25 控制面 public/internal contract mirror 预检

## 结论

Claude Code 与 Kimi 均同意：P4-25 可以自主完成，但只能完成“预检”。它要把 internal-control-plane 未来的公开合同、内部合同、运行时公开支撑、维护控制面和人工交接面分清楚，并用机器检查保证边界不漂移。

关键裁决是：P4-25 完成后可以自动续接下一条路线选择或预检，但不能自动进入物理迁移。Kimi 特别指出，`physical-apply-preflight` 中的 completed 只代表“apply 预检已存在”，不代表可以实施 physical apply。

## 本轮必须守住的边界

- 不复制、移动、删除、重命名、替换或 symlink 切换旧锚点。
- 不把 preflight 完成误报成 contract mirror 已实施。
- 不关闭 internal-control-plane release blocker。
- 不清理 `prism/runs` raw evidence。
- 不修改发布开关、许可证、registry 或凭据。
- 不裁决 Layer A 产品边界。

## 棱镜意见如何合并

Claude Code 的重点是工程交付：manifest、checker、Prism、spec-check、diagnose、clean workspace E2E 和 receipt 必须齐全。

Kimi 的重点是反误报：不能把 225 条旧 dry-run 清单复述成“任务已完成”，也不能把 apply preflight 已存在误读成 physical apply 已解锁。

Cap 合并裁决：P4-25 只做合同镜像预检；通过后登记下一条 pending 任务为路线选择，不直接实施物理迁移。

## 下一步

完成 P4-25 后，父任务线应进入 P4-26：P4-25 后下一安全切片选择。P4-26 仍必须先做路线裁决，不能跳过裁决直接实施物理迁移、delete-last、raw evidence cleanup、正式发布或 Layer A 产品决策。
