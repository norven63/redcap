# RedCap docs retention log

<!-- redcap:docs-retention-log -->

## 2026-04-19

- 决策：本轮不删除 closure evidence，不批量搬迁历史 task report / spec / trace / research。
- 原因：`compass/docs/**` 的 token 压力已经通过 catalog + plan + budget 进入渐进式披露；直接删除或移动历史 evidence 会折损考古链、task report closure 证据和旧 blocker 根因追踪。
- 当前执行化边界：`redcap-docs-catalog.sh check` 负责 catalog freshness；`redcap-docs-catalog.sh plan` 负责候选定位；`redcap-docs-catalog.sh budget` 负责精确读取集合预算；`redcap-docs-catalog.sh retention-check` 负责保留策略的 check-only 审计。
- 后续归档原则：若将来要把 cold-candidate task reports 移入 archive，必须保留 catalog 摘要、源路径迁移记录、替代入口，以及对应任务报告中的 closure evidence 链接；不得为了节省 token 直接删除历史证据。
