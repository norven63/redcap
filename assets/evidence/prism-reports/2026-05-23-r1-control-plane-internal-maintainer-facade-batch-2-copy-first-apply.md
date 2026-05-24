# Prism 报告：P4-23 internal-control-plane 第二小批次 facade 实施

## 结论

Claude Code 与 Kimi 形成可执行共识：P4-23 可以实施提议的 8 个 internal-control-plane 维护工具 thin facade。

这不是正式发布，也不是 internal-control-plane 的全量迁移。本轮只增加第二个小批次兼容入口，旧 `compass/tools` 仍然是权威实现，所有 release blockers 继续保持 open。

## 为什么可以实施

P4-21 已经证明 thin facade 模式可行：新入口只负责定位 RedCap 根目录并 `exec bash` 委托旧脚本，不复制业务逻辑，也不改变旧锚点。

本轮 8 个候选均来自 R1 internal-control-plane dry-run manifest，数量与 P4-21 相同，不超过小批次上限。它们属于控制面维护、检查、索引或发布前预检入口，不触碰凭据、发布开关、证据清理或 Layer A 产品边界。

## 约束

- 新 facade 必须只委托旧 `compass/tools` 对应脚本。
- 旧 `compass/tools` 文件保持原路径、原权威、原语义。
- 不批量处理全部 111 个 internal-control-plane 条目。
- 不删除、移动、替换或 symlink 切换旧锚点。
- 不清理 `prism/runs` raw evidence。
- 不修改发布开关、许可证、registry 或凭据。
- 不触碰 Layer A 产品边界。

## 验收要求

- P4-23 apply manifest 必须记录 8 个新增 facade、来源 dry-run 条目和禁止声明。
- P4-23 checker 必须验证 facade 委托链、批次不重叠、旧锚点保留和 release blocker 仍 open。
- Prism acceptance、spec-check、diagnose 和 clean workspace E2E 必须通过。

## 下一步

P4-23 收口后，下一步应重新进入路线选择，比较继续 internal-control-plane、转向 Prism report alias/query gateway preflight、contract mirror preflight 或其他候选。仍不得直接进入正式发布或人工硬门。
