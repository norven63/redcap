# 待验证登记簿（Pending Validations）

> 每次框架变更命中 CONTRIBUTING.md §3.1 触发条件时，**必须**在此登记。
> E2E 执行时逐项消费，验证通过标记 ✅，未通过保留为下轮。

## 登记格式

```markdown
### V-{序号}: {功能简述}
- **来源 commit**：{hash} {message}
- **触发类型**：状态机 | 通信协议 | Prompt模板 | 路由逻辑
- **验证要点**：{具体要测什么}
- **状态**：🔴 待验证 | 🟡 部分验证 | ✅ 已验证（E2E-{日期}）
```

---

## 活跃条目

### V-2: state.yaml 自动校验脚本
- **来源 commit**：`9d06d2e` feat(框架): __redcap_status outbox 文件模式 + state.yaml 自动校验
- **触发类型**：状态机
- **验证要点**：`tools/redcap-check-state.sh` 在 on_qa_pass hook 中是否正确触发；校验失败时是否阻断流程
- **状态**：🟡 部分验证（E2E-2026-04-07，md-table-tool smoke：hook 触发正常，但未测试校验失败时的阻断效果）

### V-3: E2E 后置处理流程（7 步）
- **来源 commit**：`928ab33` feat(框架): E2E 后置处理流程
- **触发类型**：Prompt模板（影响 Dispatcher 行为流程）
- **验证要点**：Dispatcher 在 E2E 结束后是否按 7 步执行；分类定性(BUG/GAP/OBSERVATION)是否准确
- **状态**：� 部分验证（E2E-2026-04-07，md-table-tool：Dispatcher 首次执行时遗漏后置处理，经用户审计后补齐。暴露 L-25。7 步未完整——缺少独立的 BUG/GAP/OBSERVATION 分类定性步骤）

### V-4: Agent Fallback 两层降级（Model→CLI）
- **来源 commit**：`4f51037` feat: Agent Fallback 两层降级（Model→CLI）
- **触发类型**：路由逻辑
- **验证要点**：① 同 CLI 内 Model 降级是否优先于 CLI 降级 ② 角色最低能力门槛是否生效（不达标 Model 被跳过） ③ agent_health 粒度是否为 `{cli}&{model}`
- **状态**：🔴 待验证

### V-6: QA_FAIL → ARCH_WORKING 设计回退路径
- **来源**：smoke-test-backlog #12
- **触发类型**：状态机
- **验证要点**：QA → ARCH → DEV → QA 长链路完整走通
- **状态**：🔴 待验证

### V-7: ESCALATE_L1 → PM 决策升级路径
- **来源**：smoke-test-backlog #13
- **触发类型**：状态机
- **验证要点**：Agent 遇无法自主决策问题时升级到 PM
- **状态**：🔴 待验证

### V-8: ESCALATE_L2 → 用户决策升级路径
- **来源**：smoke-test-backlog #14
- **触发类型**：状态机
- **验证要点**：二级升级链 Agent → PM → 用户完整走通
- **状态**：🔴 待验证

### V-9: PAUSED → Resume 暂停恢复路径
- **来源**：smoke-test-backlog #15
- **触发类型**：状态机
- **验证要点**：need_user 触发 PAUSED 后用户回复恢复执行
- **状态**：🔴 待验证

### V-11: Codex CLI reviewer fallback
- **来源 commit**：本轮 `fix(governance): 接入 codex reviewer fallback` follow-up
- **触发类型**：路由逻辑
- **验证要点**：当 Gemini / Copilot / Claude / Kimi reviewer 不可用时，stop-review 能 fallback 到 Codex CLI；程序化消费应读取 `--output-last-message`，stdout/stderr banner 或 warning 不得污染评审 payload；长 review prompt 必须从构造阶段就文件化，并经 stdin/file 传入，不能作为 Bash 大字符串或超长 argv；timeout 时必须杀掉 reviewer 进程组，不能遗留子进程。
- **状态**：🟡 部分验证（acceptance 覆盖；真实 E2E 待纳入下轮完整项目流转）

---

## 已验证归档

> E2E 验证通过的条目移到此区域，保留记录便于追溯。

### V-10: Gemini CLI SessionEnd Hook 验证 ✅
- **验证日期**：E2E-2026-04-08
- **验证方式**：物理标记文件法（touch /tmp/redcap-gemini-hook-fired-*），并确认 Layer B 分发路径触发 redcap-on-stop-review.sh
- **结论**：.gemini/settings.json 正确加载，SessionEnd 物理触发，Layer A/B 分发逻辑均验证通过

### V-1: __redcap_status outbox 文件模式 ✅
- **验证日期**：E2E-2026-04-07（md-table-tool smoke）
- **结论**：所有角色 outbox 交付 100%，跨 trpg-web + md-table-tool 两次 E2E 一致确认

### V-5: QA_FAIL → DEV_WORKING 回退路径 ✅
- **验证日期**：E2E-2026-04-07（md-table-tool smoke，自然触发）
- **结论**：BUG-STEP2-001 触发完整 QA→DEV→QA 回退链，revision 字段传递正常
