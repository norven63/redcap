# 2026-04-21 Pending Validations E2E Tranche

## 0.1 当前已完成

- 当前已完成：Codex 宿主差异点已写回 repo 权威面，完整用户项目 E2E tranche 已消费 V-2 / V-3 / V-4 / V-6 / V-7 / V-8 / V-9。

## 0.2 上一步完成的是

- 上一步完成的是：4 条 benchmark focused run、E2E 报告、pending-validations、lessons 与任务报告的账本回填。

## 0.3 下一步计划做的是

- 下一步计划做的是：无当前任务级剩余 repo-owned blocker；完成 `e2e-session.yaml` 清理后即可视为本轮 tranche 收口。

## 0.4 整体计划脉络图是

- 整体计划脉络图是：Codex 适配补强 → repo-owned bookkeeping → smoke/multi-step → rollback / escalation / infra focused replay → 后置处理与 gate 收口。

## 背景

本轮任务专门处理 `loom/test-reports/pending-validations.md` 中遗留的 7 项完整用户项目 E2E 队列，并吸收 `/Users/norven/workspace/AI Era/codex-cli-redcap-adaptation-guide.md` 中仍有价值的 Codex 宿主差异点。

## 本轮收口内容

1. 吸收 Codex 适配草案的剩余有效差异点：
   - 新增 `compass/knowledge/hooks-codex-cli.md`
   - 更新 `compass/knowledge/index.md`
   - 更新 `compass/knowledge/host-reliability.md`
   - 将 Codex 入口/非交互/host-limited 边界写回 repo 权威面

2. 为完整用户项目 E2E tranche 补齐 repo-owned bookkeeping：
   - 新增 `loom/tools/redcap-e2e-session.sh`
   - 更新 `loom/test-reports/benchmark-scenario.md`
   - 更新 `loom/fixtures/md-table-tool-benchmark/seed/REQUEST.md`
   - 在 `compass/CONTRIBUTING.md` 写入启动方式

3. 基于 `md-table-tool` benchmark carrier 执行 4 条 focused run：
   - `smoke + multi-step`
   - `rollback`
   - `escalation`
   - `infra`

4. 过程中发现并修复一个实质性框架缺口：
   - `compass/tools/redcap-check-state.sh` 的 Python heredoc 参数顺序错误，实际会把 `state.yaml` 当作 Python 脚本执行
   - `compass/tools/redcap-on-qa-pass.sh` 没有在 `check-state` 返回 2 时 fail-closed，而是继续后续动作
   - 已一并修复并补 acceptance 回归

## 结果

- 已消费条目：V-2 / V-3 / V-4 / V-6 / V-7 / V-8 / V-9
- `latest-e2e-report.md` 已切换到本轮完整用户项目 tranche
- `pending-validations.md` 已清空活跃队列
- `lessons.md` 已新增本轮经验沉淀

## 验证

- `bash compass/tools/redcap-multi-session-acceptance.sh on-qa-pass-blocks-inconsistent-state`
- `bash compass/tools/redcap-check-state.sh /tmp/redcap-md-table-tool-e2e-20260421-smoke/开发手册`
- `bash compass/tools/redcap-check-state.sh /tmp/redcap-md-table-tool-e2e-20260421-rollback/开发手册`
- `bash compass/tools/redcap-check-state.sh /tmp/redcap-md-table-tool-e2e-20260421-escalation/开发手册`
- `bash compass/tools/redcap-check-state.sh /tmp/redcap-md-table-tool-e2e-20260421-infra/开发手册`
- `npm test` in all 4 benchmark copies

## 备注

本轮 focused validation 中，`rollback / escalation / infra` 三条使用的是“继承 smoke 完成版 benchmark 后的路径回放副本”，目的是高密度验证框架状态机与路由，不是重新从零实现 3 次完整项目。
