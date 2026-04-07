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

### V-1: __redcap_status outbox 文件模式
- **来源 commit**：`9d06d2e` feat(框架): __redcap_status outbox 文件模式 + state.yaml 自动校验
- **触发类型**：通信协议
- **验证要点**：Agent 是否写入 `{role}/outbox/__redcap_status.json`；Dispatcher 能否正确解析；stdout 辅助通道是否仍可用
- **状态**：🟡 部分验证（trpg-web E2E 验证了 outbox 文件交付 100%，stdout 嵌入 0% 合规——确认文件管道为主通道。待新基准项目 md-table-tool 复验）

### V-2: state.yaml 自动校验脚本
- **来源 commit**：`9d06d2e` feat(框架): __redcap_status outbox 文件模式 + state.yaml 自动校验
- **触发类型**：状态机
- **验证要点**：`tools/redcap-check-state.sh` 在 on_qa_pass hook 中是否正确触发；校验失败时是否阻断流程
- **状态**：� 部分验证（脚本已集成到 on_QA_PASS hook，待 E2E 验证真实项目中的触发与阻断效果）

### V-3: E2E 后置处理流程（7 步）
- **来源 commit**：`928ab33` feat(框架): E2E 后置处理流程
- **触发类型**：Prompt模板（影响 Dispatcher 行为流程）
- **验证要点**：Dispatcher 在 E2E 结束后是否按 7 步执行；分类定性(BUG/GAP/OBSERVATION)是否准确
- **状态**：🔴 待验证

### V-4: Agent Fallback 两层降级（Model→CLI）
- **来源 commit**：`4f51037` feat: Agent Fallback 两层降级（Model→CLI）
- **触发类型**：路由逻辑
- **验证要点**：① 同 CLI 内 Model 降级是否优先于 CLI 降级 ② 角色最低能力门槛是否生效（不达标 Model 被跳过） ③ agent_health 粒度是否为 `{cli}&{model}`
- **状态**：🔴 待验证

### V-5: QA_FAIL → DEV_WORKING 回退路径
- **来源**：smoke-test-backlog #11（设计已就绪，未实测）
- **触发类型**：状态机
- **验证要点**：QA 发现代码缺陷后状态机回退到程序员；revision 字段传递完整
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

---

## 已验证归档

> E2E 验证通过的条目移到此区域，保留记录便于追溯。

（暂无）
