# 任务完成报告：P0-1 Prism availability cache provenance/path 污染修复

**报告日期**：2026-04-26  
**执行者**：Cap（Codex.app 主 Agent）  
**报告版本**：v1.0  

---

## 零、先看懂当前局面

### 0.1 当前已完成

- 当前已完成：`prism-availability` 的 cache 可信条件从“只看 TTL / timeout”升级为“TTL + timeout + provenance 一致性”。
- provenance 覆盖：repo root、cache path、health probe 路径与内容摘要、provider policy 路径与内容摘要、PATH 指纹。
- 结果：acceptance fixture、旧 PATH、旧 probe / policy 生成的 cache 即使仍未过期，也不会被真实 Prism 调度继续信任。

### 0.2 上一步完成的是

- 上一步完成的是：`redcap-r0-r22-parent-reanchor-and-plan-audit` 已 closeout，并把本项列为父任务账本 P0-1。

### 0.3 下一步计划做的是

- 下一步计划做的是：继续父任务账本 P0-2，将 R0-R22 原始编号恢复为机器可读 registry，避免后续再靠报告段落考古编号状态。

### 0.4 整体计划脉络图与当前位置

- 整体计划脉络图是：父任务重锚定 → P0-1 Prism cache 污染修复 → P0-2 R0-R22 编号 registry → P1 执行层/旧资产 dry-run → 后续 runtime / CLI / shared-knowledge 迁移。
- 当前所在位置：P0-1 已实现、review、targeted acceptance、spec-check、diagnose，并准备 closeout receipt。

---

## 一、需求背景

### 1.1 原始问题

本轮来自父任务账本 P0-1：`Prism availability cache provenance/path 污染修复`。

### 1.2 问题根因

旧版 `prism-availability` 判断 cache 是否 fresh 时只检查：

- `version == 1`
- `expires_at` 未过期
- `timeout_s` 不低于当前要求
- `agents` 非空

这会漏掉一个关键事实：cache 可能是在另一个运行面生成的。例如 acceptance fixture 改写 PATH 后生成了 fake CLI 路径，或者 provider policy / health probe 已变更但路径没变。旧 cache 仍在 TTL 内时，真实 Prism 调度会继续信任它。

这不是“cache 不该存在”的问题，而是“cache 缺少出生证明”的问题。

---

## 二、方案讨论

### 2.1 代码修复

| 文件 | 变更 |
|---|---|
| `prism/tools/prism-availability.py` | 新增 provenance contract；fresh 校验必须匹配 root、cache path、health probe、provider policy、probe/policy sha256、PATH sha256 |
| `prism/tools/prism-availability.py` | 新增 `--refresh` 和 `PRISM_AVAILABILITY_REFRESH=1` 强制刷新入口 |
| `compass/tools/redcap-multi-session-acceptance.sh` | 新增无 provenance、错 PATH 指纹、错 provider policy hash、过期 cache、强制刷新入口的回归 |

### 2.2 文档与保障面

| 文件 | 变更 |
|---|---|
| `prism/README.md` / `prism/protocol.md` | Prism 可用性清单升级为 provenance-aware，明确 probe / policy 内容摘要参与可信判断 |
| `references/execution-guarantees.json` | 将 Prism availability cache 的执行保障描述同步为 provenance-aware |
| `references/file-lookup-dictionary.md` / policy | 更新文件查阅字典的人话解释 |
| `compass/knowledge/lessons.md` | 新增 L-125：可用性缓存不能只证明“还没过期”，还要证明“是在当前运行面生成” |

---

## 三、落地结果

### 3.1 核心结果

Prism availability cache 已经从“时间新鲜”升级为“运行面可信”。同一运行面下仍复用 fresh cache；运行面变化、策略变化、探活脚本变化、PATH 变化或强制刷新时，会重新探活。

### 3.2 Prism Review

| 项 | 结论 |
|---|---|
| run_id | `20260426-prism-availability-cache-provenance-guard` |
| 可用性状态 | Kimi pass；Gemini / Claude timeout；Codex unsupported；Copilot frozen |
| reviewer | Kimi reviewer + Kimi final reviewer |
| verdict | pass |
| blockers | 0 |
| 处理过的建议 | 追加 `--refresh` / `PRISM_AVAILABILITY_REFRESH=1` 回归；将 provider policy 内容摘要纳入 provenance；再补 provider policy hash mismatch 回归 |
| 残余风险 | 真实 CLI 探活可能因 provider 响应慢而超时；这是环境/timeout 边界，不是本次修复引入 |

Prism quorum 状态是 resource-limited：本轮只有 Kimi 可用，因此没有冒充多家族 formal quorum。

### 3.2.1 术语对照（按文件/功能解释）

| 术语 | 对应文件/功能 | 人话解释 |
|---|---|---|
| availability cache | `compass/.workflow/prism-agent-availability.json` | Prism 调度前看的“当前哪些 CLI 真能用”的短期缓存 |
| provenance | `prism/tools/prism-availability.py` | cache 的“出生证明”：说明它是在什么 repo、什么脚本、什么 policy、什么 PATH 下生成的 |
| PATH 指纹 | `provenance.path_sha256` | 不暴露原始 PATH，只用摘要判断 cache 是否来自同一运行环境 |
| probe / policy 内容摘要 | `health_probe_sha256`、`provider_policy_sha256` | 防止探活脚本或冻结策略内容变了，但旧 cache 仍因为路径没变而被误用 |
| resource-limited Prism | `prism/runs/20260426-prism-availability-cache-provenance-guard/artifacts/resource-limited.json` | 本轮只有 Kimi 可用，所以只做单路独立 review，并诚实记录其他 provider 不可用原因 |

---

## 四、人工审核要点

- 本轮修复不禁用 cache，而是补齐 cache 可信条件。
- 本轮 Prism review 是 resource-limited，不冒充多家族 formal quorum。
- 下一步仍应继续执行父任务账本 P0-2，不能把 P0-1 完成误认为 R0-R22 全部完成。

---

## 五、验证结果

| 验证项 | 命令 | 结果 |
|---|---|---|
| PM Gate | `bash compass/tools/redcap-pm-gate-check.sh strict codex .dev-task.md` | 通过 |
| intent coverage | `bash compass/tools/redcap-intent-coverage-check.sh .dev-task.md` | 通过 |
| change intake | `bash compass/tools/redcap-change-intake-check.sh .dev-task.md` | 通过 |
| Python compile | `python3 -m py_compile prism/tools/prism-availability.py` | 通过 |
| targeted acceptance | `bash compass/tools/redcap-multi-session-acceptance.sh prism-availability` | 通过 |
| 真实 cache 状态 | `PRISM_AVAILABILITY_PROBE_TIMEOUT=20 bash prism/tools/prism-availability.sh status --ttl-seconds 3600` | `has_provenance=True`，`has_probe_hash=True`，`has_policy_hash=True`，Kimi pass |
| JSON validity | `python3 -m json.tool references/execution-guarantees.json` 等 | 通过 |

### 5.3 closeout runtime / receipt

| 项 | 值 |
|---|---|
| closeout receipt | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/receipts/prism-availability-cache-provenance-guard-eddd6b2e5edb04433fb18935698d7653aa0c0679e3c3a04d76dc323fcb0e6227.json` |
| closeout summary | `/tmp/redcap/project/d9d581491be7d5ef6880b56dbd0dc65f/governance/closeout-runtime/summaries/prism-availability-cache-provenance-guard-eddd6b2e5edb04433fb18935698d7653aa0c0679e3c3a04d76dc323fcb0e6227.md` |
| promise ledger | 7/7 completed |
| pending closure | clear |

### 5.4 完成等级（禁止混报）

| 层级 | 状态 | 说明 |
|---|---|---|
| 已实现 | 是 | provenance-aware cache freshness、强制刷新入口与污染回归已落地 |
| 已自检 | 是 | PM Gate、intent coverage、change-intake、py_compile、targeted acceptance、JSON validity、spec-check 已通过 |
| 已独立验收 | 是，resource-limited | Kimi reviewer / final reviewer pass，无 blocker；其他 provider 当前不可用或冻结 |
| 已正式完成 | 是 | closeout runtime 将以上 receipt 路径作为本轮正式完成证明 |

---

## 六、遗留问题与下一步

本轮只完成 P0-1：Prism availability cache provenance/path 污染修复。

本轮不声明以下事项完成：

- R0-R22 父任务全部完成
- 执行层物理目录迁移完成
- shared-knowledge 远端仓库绑定完成
- npm / CLI / runtime 正式发布完成
- 全部旧资产迁移完成

下一步：继续父任务账本 P0-2，建立 R0-R22 原始编号机器可读 registry。

---

## 七、经验沉淀

### 7.3 Evolution Factory 候选处理

| 候选 | 处理 | 理由 |
|---|---|---|
| EVO-2026-04-26-P0-1-001 Prism availability cache provenance/path 污染经验 | promoted-to-lessons | 已沉淀为 `compass/knowledge/lessons.md` 的 L-125，包含问题源、解决方案、最后效果 |
| EVO-2026-04-26-P0-1-002 Kimi reviewer 对 `--refresh` 与 policy hash 的建议 | no-promote-integrated | 已转为 acceptance 回归与 provenance 内容摘要实现，不再单独保留候选 |

---

## 八、附录

- 任务锚点：`.dev-task.md`
- 任务报告：`compass/docs/task-reports/2026-04-26-prism-availability-cache-provenance-guard.md`
- Prism 本地证据：`prism/runs/20260426-prism-availability-cache-provenance-guard/`
