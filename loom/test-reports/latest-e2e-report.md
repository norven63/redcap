# E2E 验证报告

> 每次 E2E 执行后更新此文件。仅保留最近一次完整报告，旧报告直接覆盖（精华已融入 lessons.md 和 pending-validations.md）。

## 最近一次 E2E

**日期**：2026-04-18
**项目**：RedCap Layer B live closeout（框架自身收尾链）
**执行者**：Cap（Codex 接盘续修）
**框架版本**：`1cb15bf` 之后的 review-redline follow-up
**E2E Preset**：hook-level replay（stop-review / on-complete / session-end）
**说明**：本次不是用户项目完整流转 E2E，而是针对 Layer B Hook 与 reviewer runner 的物理闭环验证。完整用户项目 Agent Fallback 仍由 V-4 单独跟踪。

### 覆盖范围

| 路径 | 状态 | 备注 |
|------|------|------|
| stop-review reviewer fallback | ✅ 通过 | acceptance 覆盖前序 reviewer 不可用后进入 Codex fallback |
| Codex last-message 结果通道 | ✅ 通过 | fake Codex stdout/stderr banner 不污染 review payload |
| review prompt 文件化 / stdin 输入 | ✅ 通过 | prompt 不再进入 Bash 大字符串或超长 argv |
| reviewer timeout 进程组清理 | ✅ 通过 | timeout case 会杀掉 descendant，不遗留子进程 |
| on-complete validator host 透传 | ✅ 通过 | 显式 host / binding host 压过陈旧 runtime host |
| session-end pending refresh | ✅ 通过 | compatible pending 改写后可安全刷新并核销 |
| full acceptance suite | ✅ 通过 | `redcap-spec-check.sh` + `redcap-multi-session-acceptance.sh all` |
| real Copilot live session-end | 🟡 部分 | validator 链除 review verdict 外均 PASS；最后 review 内容指出文档联动与 V-11 消费缺口，本 follow-up 已补账 |

### 消费的 pending-validations

| V 编号 | 状态 | 说明 |
|--------|------|------|
| V-11 | ✅ 已验证 | Codex CLI reviewer fallback、last-message 消费、file-backed prompt、进程组 timeout 均已由 hook-level replay + acceptance 覆盖 |
| V-4 | 🔴 待验证 | 完整用户项目的 Model→CLI 两层 Agent Fallback 仍未执行 full/infra E2E，本次不冒领 |
| V-2, V-3, V-6~V-9 | 未变更 | 与本次 Layer B reviewer runner 收口无直接关系，保留原状态 |

### 产出的经验条目

- L-87: `session-end` 清 pending 前必须刷新并证明当前 pending 仍被本次成功覆盖
- L-88: reviewer fallback 列表必须覆盖当前可用宿主族，并隔离 CLI 噪声与评审 payload
- L-89: headless reviewer timeout 必须杀整个进程组，不能只等父进程返回
- L-90: headless reviewer 的长 prompt 必须从构造开始文件化，不能放进 Bash 大字符串
- L-91: 收尾评审的 P0/P1 需要能追到同一条物理证据链，不能让报告、pending-validations 与入口规范分叉

### 遗留问题

1. V-4（完整用户项目里的 Agent Fallback 两层降级）仍为待验证。
2. 当前 live runtime 仍需在本 follow-up commit 后重新跑 `on-complete / session-end / 飞书通知`，确认 `required_redlines=review` 被清掉。

---

> 下次完整用户项目 E2E 仍从 `loom/test-reports/pending-validations.md` 获取待验证清单，对照 `loom/test-reports/benchmark-scenario.md` 的验证矩阵执行。
