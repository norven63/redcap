# 待验证登记簿（Pending Validations）

> 每次框架变更命中 CONTRIBUTING.md §3.1 触发条件时，**必须**在此登记。
> E2E 执行时逐项消费，验证通过标记 ✅，未通过保留为下轮。

## 当前队列边界

- 当前无活跃完整用户项目 E2E 条目。
- 2026-04-21 的 `md-table-tool` benchmark tranche 已消费完此前遗留的 V-2 / V-3 / V-4 / V-6 / V-7 / V-8 / V-9。
- 后续若新增完整用户项目验证项，仍应优先使用 repo-owned benchmark carrier，而不是临时寻找外部用户项目。

## 登记格式

```markdown
### V-{序号}: {功能简述}
- **来源 commit**：{hash} {message}
- **触发类型**：状态机 | 通信协议 | Prompt模板 | 路由逻辑
- **验证要点**：{具体要测什么}
- **状态**：待验证 | 部分验证 | 已验证（E2E-{日期}）
```

---

## 活跃条目

> 当前无活跃条目。

---

## 已验证归档

> E2E 验证通过的条目移到此区域，保留记录便于追溯。

### V-11: Codex CLI reviewer fallback ✅
- **验证日期**：E2E-2026-04-18（RedCap Layer B live closeout / hook-level replay）
- **来源 commit**：`1d59616` fix(governance): 接入 codex reviewer fallback；后续 `fc0a820` / `d13f33e` / `b391197` / `1cb15bf` 补齐 timeout 进程组、stdin、file-backed prompt 与大文本解析边界
- **触发类型**：路由逻辑 / Prompt 模板 / Hook reviewer runner
- **验证方式**：targeted acceptance 覆盖 Codex fallback、`--output-last-message` 噪声隔离、stdin/file-backed prompt、timeout 子进程组清理；full suite `redcap-multi-session-acceptance.sh all` 与 `redcap-spec-check.sh` 已通过；真实 Copilot live runtime 回放验证除独立 review 内容 verdict 外的 `session-end` validator 链均能收口。
- **结论**：V-11 作为 Layer B stop-review runner 的 hook-level 验证项已消费。完整用户项目里的 Agent Fallback 两层降级仍由 V-4 跟踪，不与本条混淆。

### V-10: Gemini CLI SessionEnd Hook 验证 ✅
- **验证日期**：E2E-2026-04-08
- **验证方式**：物理标记文件法（touch /tmp/redcap-gemini-hook-fired-*），并确认 Layer B 分发路径触发 redcap-on-stop-review.sh
- **结论**：.gemini/settings.json 正确加载，SessionEnd 物理触发，Layer A/B 分发逻辑均验证通过

### V-9: PAUSED → Resume 暂停恢复路径 ✅
- **验证日期**：E2E-2026-04-21
- **来源**：smoke-test-backlog #15
- **触发类型**：状态机
- **验证方式**：`/tmp/redcap-md-table-tool-e2e-20260421-escalation` focused replay；QA 在 Step 2 对 CSV 可读性发起 `PAUSED`，随后由 benchmark harness 注入用户确认并恢复执行。
- **结论**：need_user → Resume 链已覆盖，最终重新回到 `ALL_DONE`。

### V-8: ESCALATE_L2 → 用户决策升级路径 ✅
- **验证日期**：E2E-2026-04-21
- **来源**：smoke-test-backlog #14
- **触发类型**：状态机
- **验证方式**：`/tmp/redcap-md-table-tool-e2e-20260421-escalation` focused replay；PM 对“多表 CSV 是否插入标题注释行”无法裁决，升级到 benchmark harness 注入的用户决策，再回注流程。
- **结论**：Agent → PM → 用户的二级升级链已覆盖。

### V-7: ESCALATE_L1 → PM 决策升级路径 ✅
- **验证日期**：E2E-2026-04-21
- **来源**：smoke-test-backlog #13
- **触发类型**：状态机
- **验证方式**：`/tmp/redcap-md-table-tool-e2e-20260421-escalation` focused replay；程序员对“智能表格识别”模糊需求发起升级，PM 明确冻结为标准 GFM 范围。
- **结论**：L1 决策升级链已覆盖。

### V-6: QA_FAIL → ARCH_WORKING 设计回退路径 ✅
- **验证日期**：E2E-2026-04-21
- **来源**：smoke-test-backlog #12
- **触发类型**：状态机
- **验证方式**：`/tmp/redcap-md-table-tool-e2e-20260421-rollback` focused replay；QA 将 Step 2 的过滤语义缺口归类为 `design`，随后走 ARCH 修订 → DEV 对齐 → QA 回归。
- **结论**：QA → ARCH → DEV → QA 长链路已完整走通。

### V-5: QA_FAIL → DEV_WORKING 回退路径 ✅
- **验证日期**：E2E-2026-04-07（md-table-tool smoke，自然触发）
- **结论**：BUG-STEP2-001 触发完整 QA→DEV→QA 回退链，revision 字段传递正常

### V-4: Agent Fallback 两层降级（Model→CLI）✅
- **验证日期**：E2E-2026-04-21
- **来源 commit**：`4f51037` feat: Agent Fallback 两层降级（Model→CLI）
- **触发类型**：路由逻辑
- **验证方式**：`/tmp/redcap-md-table-tool-e2e-20260421-infra` focused replay；先执行真实 `agent-registry.yaml` 嗅探，再通过 `e2e_config.agent_overrides` 注入受控候选链，验证同 CLI fallback、最低能力门槛跳过与 `{cli}&{model}` 粒度 `agent_health`。
- **结论**：三项验证要点均已覆盖，不再保留为活跃 backlog。

### V-3: E2E 后置处理流程（7 步）✅
- **验证日期**：E2E-2026-04-21
- **来源 commit**：`928ab33` feat(框架): E2E 后置处理流程
- **触发类型**：Prompt模板（影响 Dispatcher 行为流程）
- **验证方式**：本轮完整用户项目 tranche 按 §3.1 完成问题提取、BUG/GAP/OBSERVATION 分类、P1 修复、lessons 沉淀、focused 回归、E2E 汇总与 postcheck 收口。
- **结论**：此前缺失的“独立分类定性步骤”已补上，V-3 现已消费。

### V-2: state.yaml 自动校验脚本 ✅
- **验证日期**：E2E-2026-04-21
- **来源 commit**：`9d06d2e` feat(框架): __redcap_status outbox 文件模式 + state.yaml 自动校验
- **触发类型**：状态机
- **验证方式**：smoke/rollback/escalation/infra 四个 benchmark 副本均通过 `redcap-check-state.sh`；新增 acceptance `on-qa-pass-blocks-inconsistent-state` 覆盖“校验失败时阻断流程”。
- **结论**：正常路径与失败阻断路径均已覆盖；过程中还发现并修复 `redcap-check-state.sh` heredoc 调用缺陷。

### V-1: __redcap_status outbox 文件模式 ✅
- **验证日期**：E2E-2026-04-07（md-table-tool smoke）
- **结论**：所有角色 outbox 交付 100%，跨 trpg-web + md-table-tool 两次 E2E 一致确认
