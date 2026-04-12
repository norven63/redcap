# 任务完成报告：multi-session isolation foundation

**报告日期**：2026-04-11
**执行者**：Cap（Copilot CLI + GPT-5.4）
**报告版本**：v1.0

---

## 一、需求背景

### 1.1 原始问题（用户原文，禁止改写）

> 我刚才也发现一个问题，就是如果新开一个会话触发redcap的话，会发生类似“多线程并发”的问题，即多个会话共享里redcap的工作流，包括各种缓存文件、hook机制等。这块是否应该做一次改造，隔离来自不同会话的中间产物，防止会话之间相互干扰呢？

> 好的，那么看来我们要专注于多会话隔离的问题了，这个问题很复杂，因为不仅仅Layer A、B要进行隔离，A和B的通信、A和B调度的棱镜团队之间的通信，这些情况都要考虑和兼容。

### 1.2 触发背景

本轮任务由 hook 失效、结果报告缺失、飞书通知遗漏引出的系统性排查升级而来。  
继续深挖后，根因收敛到 RedCap 仍混用了宿主级 `/tmp` marker、项目共享状态和 Prism 全局 registry，导致多会话并发时存在串号、误归属和兼容逻辑污染。  
因此本轮目标不是“修一个点”，而是把 Layer A / Layer B / Prism 的运行期真相层重新收口到可隔离、可降级、可兼容迁移的结构上。

---

## 二、方案讨论

### 2.1 问题分析

本轮问题可拆成两类。第一类是运行时身份与归属：Layer B 会在拿不到稳定身份时退回到宿主级 marker，Layer A 的 owner 也可能被后开的 session 抢走；这会直接破坏 stop/review/report 的可信性。第二类是 Prism 运行态：当前协议要求 `session_registry` 作为 quorum 真相源，但仓库里只有 global `.session-registry.yaml` 的 consumer，没有 run-scoped 的 producer/helper。  

在收口过程中，又追回了几个紧邻的真实风险：binding-init race 会分裂 runtime session；metadata writer 是 best-effort 会发布 broken binding；Layer A stop 早退会残留 process claim；archive gate 虽然看 report run_id，但 registry 仍是全局路径，无法避免并发 run 串号。

### 2.2 方案选项

| Q | 选项 | 描述 | 优点 | 缺点 |
|---|------|------|------|------|
| Q1 | 选项 A | 继续沿用 host-level `/tmp` marker + 局部补丁 | 改动小 | 无法从根上解决多会话串号 |
| Q1 | 选项 B | 建立 runtime session/capability/binding 原语，Layer A/B 全量切到 session 私有目录 | 真相层清晰，可做 safe degraded | 需要补齐 claim/rollback/owner 细节 |
| Q2 | 选项 A | 继续使用 `prism/reports/.session-registry.yaml`，在 consumer 上补判断 | 上手快 | 仍然是全局单点，Prism 并发 run 依旧互相污染 |
| Q2 | 选项 B | 新增 `prism-run-state` helper，切到 `prism/runs/<run_id>/session-registry.yaml`，仅保留 deterministic legacy bridge | 符合 run-scoped 单主写者设计 | 需要补 helper、archive consumer 和协议文档同步 |

### 2.3 决策结果

| Q | 采纳方案 | 决策理由 | 决策方 |
|---|---------|---------|------|
| Q1 | 选项 B | 多会话隔离必须建立在 runtime identity + capability + claim 的硬约束上，host-level truth 只能降级、不能再当权威真相 | CAP_DECIDE |
| Q2 | 选项 B | Prism 的核心风险就是 global registry；只有 run-scoped helper + archive consumer 迁移，才能让并发 run 真正隔离 | CAP_DECIDE |

---

## 三、落地结果

### 3.1 变更文件清单

| 文件 | 变更类型 | 变更摘要 |
|------|---------|---------|
| `compass/tools/redcap-runtime-state.sh` | 新建 | 建立 runtime session/binding/capability/process-claim/helper 真相层，并补齐 rollback、legacy_hit、degraded-mode 记账 |
| `compass/tools/redcap-layerB-session-start.sh` | 修改 | Layer B resume / safe degraded 收口，不再把 host marker 当 once-only 真相 |
| `compass/tools/redcap-layerB-session-end.sh` | 修改 | Layer B 无 runtime attach 时显式降级，并收紧 legacy 兼容路径 |
| `compass/tools/redcap-on-stop-review.sh` | 修改 | stop-review 只在可信 runtime attach 下写 session 私有评审结果 |
| `compass/tools/redcap-task-report-register.sh` | 修改 | report marker 持久化失败时改为硬失败，不再 silent succeed |
| `compass/tools/redcap-task-report-check.sh` | 修改 | report audit 不再把 host-level marker 当权威 fallback |
| `loom/tools/redcap-layerA-session-start.sh` | 修改 | workflow owner 改为 first-writer-wins，并落盘 session 私有 ownership-check |
| `loom/tools/redcap-layerA-stop.sh` | 修改 | stop 以 ownership-check 为主，attach 后统一清理 process claim / ownership-check |
| `loom/tools/redcap-layerA-session-end.sh` | 修改 | 修正 legacy owner cleanup 的 project-hash keyed 路径 |
| `loom/tools/redcap-layerA-review-fallback.sh` | 修改 | 无 runtime 时 safe degraded，避免全局 fallback 结果文件 |
| `prism/tools/prism-run-state.sh` | 新建 | 新增 Prism run-scoped helper，统一 run dir / registry / owner / legacy resolve |
| `prism/tools/prism-archive-check.sh` | 修改 | archive gate 现在按报告 run_id 解析 run-scoped registry，并仅在精确匹配时走 legacy bridge |
| `prism/protocol.md` | 修改 | 协议从 global registry 切到 per-run registry，并记录 legacy bridge 约束 |
| `prism/modes/council.md` | 修改 | 将 council 文档的 quorum 分母语义对齐到 protocol 的固定分母规则 |
| `.gitignore` | 修改 | 忽略 `prism/runs/` 运行期目录 |
| `compass/knowledge/explore-notes.md` | 修改 | 记录 Q7 的 helper 设计、archive consumer 迁移与剩余缺口 |

### 3.2 技术实现要点

第一，Layer A / Layer B 的运行时真相被收口到 `runtime_session_id + capability + binding + process-claim` 上：attach/load/init 都必须通过 capability 校验，metadata writer 改成 fail-fast，critical write 失败时回滚 session dir / binding / claim / context。  

第二，Layer A owner 模型改为“两层语义”：project-shared 的 `workflow-owner-session` 只保留 first-writer-wins 护栏，真正的完成权限由 session 私有 `layerA/ownership-check` 主导。这样 stop hook 即使在同项目多会话并发下，也不会被后开的 session 抢走完成权。  

第三，Prism 新增 `prism/tools/prism-run-state.sh` 作为 coordinator-side helper，把 `prism/runs/<run_id>/session-registry.yaml`、`owner.json`、run dir 结构和 legacy resolve 统一封装；`prism-archive-check.sh` 则改成按报告 `run_id` 解析 registry，避免再猜“当前全局唯一 registry 是谁的”。  

第四，兼容迁移继续遵守“新写旧读，禁止长期双写”：run-scoped registry 是唯一新写路径，legacy `.session-registry.yaml` 仅在 `run_id` 精确匹配时作为只读桥接，并记入 `legacy_hit`。

### 3.3 关联变更

- 为了让 runtime bootstrap 真正成为硬契约，本轮连带修复了 `attach_existing()` 失败残留半挂载上下文、`load_from_binding()` 吞掉 process-claim 写失败、Layer A stop 早退残留 claim/ownership-check 等问题。  
- 为了避免协议漂移固化错误语义，`prism/modes/council.md` 同步修正为“ABSENT 不移出 quorum 固定分母”。  
- 为了让任务级收口可被 Hook 识别，本轮补写任务完成报告并同步回到 `compass/docs/task-reports/`。

---

## 四、人工审核要点

> ⚠️ 以下是 Norven 需要重点确认的内容，其他部分 Cap 已自行验证。

| 序号 | 审核项 | 说明 | 优先级 |
|------|-------|------|------|
| 1 | 是否继续把 `prism-run-state.sh` 接入真实 dispatch / collect / council 写回链路 | 当前 helper 和 archive consumer 已就位，但仓库中仍没有完整的 scripted Prism coordinator；下一步是否继续深挖，需要确认优先级 | P1 |
| 2 | 何时移除 legacy `.session-registry.yaml` 桥接 | 现在仍保留 deterministic read-only legacy bridge 以兼容现有报告；完全移除前需要一个历史 run 清理窗口 | P1 |

---

## 五、验证结果

### 5.1 自动化验证

| 验证项 | 命令 | 结果 |
|--------|------|------|
| Runtime 相关脚本语法检查 | `bash -n loom/tools/redcap-layerA-stop.sh compass/tools/redcap-runtime-state.sh compass/tools/redcap-task-report-register.sh` | ✅ |
| Runtime 回归 harness | `python3 - <<'PY'  # attach_existing/load_from_binding/layerA-stop/report-register regression harness ... PY` | ✅ |
| Prism helper / archive 语法检查 | `bash -n prism/tools/prism-run-state.sh prism/tools/prism-archive-check.sh` | ✅ |
| Prism helper / archive harness | `python3 - <<'PY'  # owner metadata + init/upsert + run-scoped resolve + legacy bridge harness ... PY` | ✅ |
| 独立代码评审 | `checkpoint-mid-review` / `final-runtime-review` / `prism-migration-review` | ✅ |

### 5.2 人工验证项（Cap 无法自动化验证的）

- [ ] 在真实的 scripted Prism dispatch / collect / council 流程接入 helper 后，再做一次并发 run 级别的端到端验收
- [ ] 观察 legacy bridge 命中期内的实际 `legacy_hit` 走势，决定移除窗口

---

## 六、遗留问题与下一步

### 6.1 本次未处理的问题

| 问题 | 原因 | 建议优先级 |
|------|------|----------|
| Prism dispatch / collect / council 仍未使用 scripted coordinator 自动写回 run-scoped registry | 仓库里当前没有完整的 scripted coordinator 入口，本轮先完成 helper 与 archive consumer 的基础迁移 | P1 |
| 旧 `/tmp/redcap-layerA-*` / Layer B 旧路径 quarantine 仍未彻底清理 | 本轮优先处理真实串号风险和 Prism run-scoped foundation | P1 |

### 6.2 触发的新问题

本轮未发现新的 blocking 问题，但在实现过程中确认了一个流程性事实：archive consumer 若用 `$(helper ...)` 读取路径，会丢失 helper 在同进程内设置的 resolution source 全局变量，因此 run-state helper 这类“返回值 + side-channel metadata”接口必须避免 command substitution。

### 6.3 推荐的下一步行动

1. 为真实 Prism dispatch / collect / council 落一个 scripted coordinator，并让其统一调用 `prism-run-state.sh` 完成 init/upsert/write-owner
2. 当 scripted coordinator 完成并经过并发 acceptance 后，移除 legacy `.session-registry.yaml` 的 read bridge

---

## 七、经验沉淀

### 7.1 新增 Lesson（建议写入 knowledge/lessons.md）

| 编号 | 标题 | 核心内容 |
|------|------|---------|
| L-待定 | Prism registry 绑定必须显式锚定 run_id | archive / legacy bridge 都必须基于报告或显式参数里的 `run_id` 解析 registry，禁止猜 latest 或共用全局单点文件 |

### 7.2 流程改进建议

任务级收口应继续强制执行“物理报告 + 飞书同步”双动作，尤其是框架级大改（>10 files）时，避免只完成代码而漏掉归档和同步。

---

## 八、附录

### 附录 A：Commits

```text
31fa41d (HEAD -> main) docs(spec): add multi-session isolation design
cd3027d docs(report): clarify smoke env flags
5aa15d7 fix(hooks): close host smoke gaps
21bfd4a docs(report): finalize hook-chain closure
9bae831 fix(hooks): harden layer-b completion chain
```

### 附录 B：棱镜调用记录（如有）

| 模式 | 问题 | 结论 | 报告路径 |
|------|------|------|---------|
| N/A | 本轮未正式归档新的 Prism mode 运行报告 | 仅完成 helper / archive consumer foundation；rubber-duck 结论未单独归档到 `prism/reports/` | `-` |

### 附录 C：相关文档索引

- 需求原始记录：`compass/knowledge/explore-notes.md` §Q7
- 设计文档：`compass/docs/specs/multi-session-isolation-design.md`
- 变更影响分析：`/Users/norven/.copilot/session-state/c73ce3b2-e124-49d2-a1f8-770a2e08cb7a/plan.md`
