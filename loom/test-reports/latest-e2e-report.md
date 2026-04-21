# E2E 验证报告

> 每次 E2E 执行后更新此文件。仅保留最近一次完整报告，旧报告直接覆盖（精华已融入 lessons.md 和 pending-validations.md）。

## 最近一次 E2E

**日期**：2026-04-21
**项目**：md-table-tool benchmark（完整用户项目 E2E tranche）
**执行者**：Cap（Codex）
**框架版本**：`cb647de` 之后的 pending-validations tranche follow-up
**E2E Preset**：composite tranche（smoke + multi-step + rollback + escalation + infra）
**说明**：本次使用 repo-owned `md-table-tool` benchmark carrier 执行 4 条 focused run，集中消费 `pending-validations.md` 中剩余的 7 项完整用户项目 E2E 条目。

### 覆盖范围

| 路径 | 状态 | 备注 |
|------|------|------|
| smoke + multi-step | ✅ 通过 | `/tmp/redcap-md-table-tool-e2e-20260421-smoke` 完成两步开发、QA 与 Review |
| V-2: state.yaml 自动校验 | ✅ 通过 | smoke 副本验证正常路径；新增 acceptance `on-qa-pass-blocks-inconsistent-state` 验证失败时阻断 |
| V-3: E2E 后置处理流程 | ✅ 通过 | 本轮按 §3.1 完成 BUG/GAP/OBSERVATION 分类、pending 消费、lessons 沉淀、报告与 postcheck 收口 |
| V-4: Agent Fallback 两层降级 | ✅ 通过 | `/tmp/redcap-md-table-tool-e2e-20260421-infra` 结合真实 agent registry + `agent_overrides` 完成 model→CLI replay |
| V-6: QA_FAIL → ARCH_WORKING | ✅ 通过 | `/tmp/redcap-md-table-tool-e2e-20260421-rollback` 回放 design root cause 长链 |
| V-7: ESCALATE_L1 → PM | ✅ 通过 | `/tmp/redcap-md-table-tool-e2e-20260421-escalation` 回放程序员升级到 PM |
| V-8: ESCALATE_L2 → 用户 | ✅ 通过 | 同 escalation 副本，PM 无法裁决后升级到 benchmark harness 注入的用户决策 |
| V-9: PAUSED → Resume | ✅ 通过 | 同 escalation 副本，QA 暂停等待用户确认后恢复 |

### 后置处理分类（BUG / GAP / OBSERVATION）

| 编号 | 分类 | 级别 | 发现 | 处理 |
|------|------|------|------|------|
| E2E-20260421-01 | BUG | P1 | `redcap-check-state.sh` 的 Python heredoc 参数顺序错误，实际会把 `state.yaml` 当作 Python 脚本执行 | 已修复 `compass/tools/redcap-check-state.sh`，并补 acceptance |
| E2E-20260421-02 | BUG | P1 | `redcap-on-qa-pass.sh` 在 `check-state` 返回 2 时仍继续执行，未 fail-closed | 已修复 `compass/tools/redcap-on-qa-pass.sh`，并补 acceptance |
| E2E-20260421-03 | GAP | 本轮处理 | 完整用户项目 E2E 队列只有 benchmark 说明，没有 repo-owned bookkeeping helper | 已新增 `loom/tools/redcap-e2e-session.sh` 并写回入口规范 |
| E2E-20260421-04 | OBSERVATION | 记录 | 通过继承 smoke 完成版 benchmark 再做 focused replay，可低成本覆盖多个状态路径而不牺牲账本完整性 | 已沉淀 lessons，作为后续 tranche 的执行模式 |

### 消费的 pending-validations

| V 编号 | 状态 | 说明 |
|--------|------|------|
| V-2 | ✅ 已验证 | 正常路径 + 失败阻断路径均已覆盖 |
| V-3 | ✅ 已验证 | 本轮按 §3.1 完成分类、修复、沉淀、回归、汇总 |
| V-4 | ✅ 已验证 | 同 CLI model fallback、能力门槛、`{cli}&{model}` health 粒度均已覆盖 |
| V-6 | ✅ 已验证 | rollback focused validation 已覆盖 |
| V-7 | ✅ 已验证 | escalation focused validation 已覆盖 |
| V-8 | ✅ 已验证 | escalation focused validation 已覆盖 |
| V-9 | ✅ 已验证 | escalation focused validation 已覆盖 |

### 产出的经验条目

- L-102: shell heredoc 调 Python 时，参数位置写反会把数据文件当脚本执行
- L-103: `on_QA_PASS` 的 state guard 必须 fail-closed，不能把不一致 state 只当警告
- L-104: 完整用户项目 E2E 可用“固定 benchmark carrier + focused replay 副本”高密度消费历史验证队列

### 遗留问题

无本轮 E2E 级遗留 blocker。`pending-validations.md` 活跃队列已清空。

---

> 下次完整用户项目 E2E 仍应先从 `loom/test-reports/pending-validations.md` 获取待验证清单，再用 `loom/tools/redcap-e2e-session.sh` 锁定本次开关集合。
