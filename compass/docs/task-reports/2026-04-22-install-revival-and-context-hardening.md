# 2026-04-22 安装即复活与长任务对抗补强

## 0. 状态总览

### 0.1 当前已完成
- 已把 `identity.md` 明确抬升为 Cap 的个人灵魂锚点，并在宿主入口、README、`soul.md`、`CONTRIBUTING.core.md` 中重新校准 `identity.md` 与 `soul.md` 的分层关系。
- 已新增 `compass/tools/redcap-install.sh`，把 Cap 复活与 RedCap workflow import 收口成“一键安装/复活”入口，并支持 `--init-identity` 初始化模板。
- 已新增 `compass/tools/redcap-tracking-health.sh`，并接入 `current-status` / `diagnose`，显性暴露 `.dev-task.md`、task report、`explore-notes.md` 的追踪健康。
- 已新增 `compass/knowledge/long-task-context-defense.md`，把 RedCap 当前长任务对抗设计、业内常见方案、RAG 边界与未完成项收口成可复用知识。
- 已完成回归与校验：`install`、`tracking-health`、`revival-check`、`execution-guarantee-check`、`knowledge-index-check`、`diagnose`、`spec-check`、targeted acceptance、`git diff --check` 全部通过。

### 0.2 上一步完成的是
- 已把 installer / tracking-health / 宿主入口 / 执行保障 / acceptance 回归链全部接通，并补齐 docs catalog 刷新，使诊断链回到全绿。

### 0.3 下一步计划做的是
- 无当前任务级 blocker。若继续治理，下一 tranche 可处理历史 `explore-notes` 未归档条目，以及 GD-008 / GD-009 这两条宿主边界债务。

### 0.4 整体计划脉络图与当前位置
- 路线：校准灵魂锚点 → 统一安装/复活入口 → 追踪健康显性化 → 长任务对抗沉淀 → 回归校验与收口。
- 当前位置：已完成终局收口，可提交。

## 1. 用户问题与结论

### Q1: `identity.md` 才是 Cap 的真正灵魂
- 结论：成立。此前协议里虽然一直有 `~/.cap/identity.md`，但入口表达不够突出，导致实际工作时更容易把 `soul.md` 误认成“个人灵魂本体”。
- 本轮改动：不直接把所有宿主入口改成 `@~/.cap/identity.md`，因为未初始化环境会有兼容性风险；改为在入口显式声明 identity 的优先级，并通过 installer 提供稳定初始化路径。

### Q2: 把“Cap 复活 + 导入 RedCap 工作流”合并成安装行为
- 结论：已落地。`redcap-install.sh` 现在负责 identity 检查/初始化、`current-status`、`tracking-health`、`execution-guarantee-check` 与 `revival-check`。
- 取舍：这不是宣称“所有宿主自动 100% 执行 installer”，而是提供了统一、可审计、可被 wrapper/人工/宿主复用的单一入口。

### Q3: 审核长任务对抗设计并补业内流行方案
- 结论：已完成一轮系统审视，并沉淀为知识文件。
- 当前判断：RedCap 对抗长任务的主策略不是扩大上下文，而是**外置真相 + 渐进披露 + 独立审查 + 可恢复入口**。
- 行业补充：本轮明确写入了 bootstrap/install、tracking health surface、RAG 延后、reply-time veto/readonly-safe 仍属边界。

### Q4: 是否需要 RAG，书记官/需求记录等能力是否还在
- 结论：当前不需要 RAG。规模与问题性质都还没到必须引入向量检索的阶段。
- 真正问题：不是机制不存在，而是复活链没有稳定跑满、追踪健康也没有被显性展示，导致 `.dev-task.md` / `explore-notes.md` / task report 这条追踪链“存在但存在感很弱”。
- 本轮补强：用 `tracking-health` 把这条链直接拉进 `current-status` / `diagnose`，避免下次只能靠考古或直觉判断机制是否还活着。

## 2. 主要改动

| 文件 / 入口 | 改动 | 目的 |
|---|---|---|
| `AGENTS.md` / `CLAUDE.md` / `GEMINI.md` / `.github/copilot-instructions.md` | 重写 identity 优先级与 installer 首选路径 | 让新会话不再只记得 `soul.md`，忘记 identity 与 workflow import |
| `compass/tools/redcap-install.sh` | 新增 | 提供一键安装/复活链路 |
| `compass/tools/redcap-tracking-health.sh` | 新增 | 显性化任务锚点、task report、书记官健康 |
| `compass/tools/redcap-current-status.sh` / `redcap-diagnose.sh` | 修改 | 直接暴露 tracking health |
| `compass/soul.md` / `CONTRIBUTING.core.md` / `README.md` | 修改 | 校准“identity vs soul”与 installer 入口 |
| `references/execution-guarantees.json` / `redcap-revival-check.sh` / `redcap-execution-guarantee-check.sh` | 修改 | 把 installer 与 tracking surface 纳入执行保障 |
| `compass/knowledge/long-task-context-defense.md` | 新增 | 沉淀长任务上下文对抗审计结果 |
| `redcap-multi-session-acceptance.sh` | 修改 | 为 installer / tracking-health 补 targeted 回归 |

## 3. 风险与边界

- 本轮没有把宿主入口直接改成 `@~/.cap/identity.md` 自动导入，因为对未初始化环境的兼容性风险高于收益。
- 本轮没有宣称 installer 已被所有宿主 session-start 自动执行；当前仍属于“单一首选入口已存在，可被宿主/wrapper/人工复用”。
- `reply-time veto` 与 `read-only-safe` 仍是独立治理债务，不因本轮 installer 出现就被伪装成已解决。

## 4. 验证计划

## 4. 验证结果

- `bash compass/tools/redcap-install.sh --host codex --task-file .dev-task.md` → `REDCAP_INSTALL_OK`
- `bash compass/tools/redcap-tracking-health.sh .dev-task.md` → `TRACKING_OK`
- `bash compass/tools/redcap-revival-check.sh "$PWD"` → `REVIVAL_PROTOCOL_OK`
- `bash compass/tools/redcap-execution-guarantee-check.sh` → `EXECUTION_GUARANTEES_OK`
- `bash compass/tools/redcap-knowledge-index-check.sh` → `KNOWLEDGE_INDEX_OK`
- `bash compass/tools/redcap-spec-check.sh "$PWD"` → 通过
- `bash compass/tools/redcap-diagnose.sh .dev-task.md` → `DIAGNOSE_OK`
- targeted acceptance:
  - `current-status-overview` → `ACCEPTANCE_OK`
  - `tracking-health-overview` → `ACCEPTANCE_OK`
  - `install-overview` → `ACCEPTANCE_OK`
  - `diagnose-overview` → `ACCEPTANCE_OK`
- `git diff --check` → 通过

## 5. 诚实残留

- `redcap-tracking-health.sh` 现在能直接暴露 `explore-notes=active:9 archived:0`。这说明书记官机制没有消失，但历史未归档条目仍在，确实会让人感觉“机制存在但很久没发挥作用”。本轮修的是**显性化与入口链**，没有冒充把这些历史条目也自动清零。
- `GD-008`（主 Agent 实时回复边界 host-limited）与 `GD-009`（首读/诊断链尚未真正 read-only-safe）仍是独立治理债务，不属于本轮 installer / tracking surface 可以一刀补平的范围。
