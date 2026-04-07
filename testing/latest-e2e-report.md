# E2E 验证报告

> 每次 E2E 执行后更新此文件。仅保留最近一次完整报告，旧报告直接覆盖（精华已融入 lessons.md 和 pending-validations.md）。

## 最近一次 E2E

**日期**：2026-04-07  
**项目**：md-table-tool（Markdown 表格转换 CLI 工具）— 基准项目  
**执行者**：Cap（Dispatcher，VS Code Copilot / Claude Opus 4.6）  
**框架版本**：commit `93e1d0a` 之后  
**E2E Preset**：smoke（happy_path + multi_step + deliverable_check）  
**总耗时**：~56 分钟，10 次 Agent 调用，~19 Premium Requests  

### 覆盖范围

| 路径 | 状态 | 备注 |
|------|------|------|
| PM_WORKING → PM_DONE | ✅ 通过 | kimi CLI，需求采集完整 |
| ARCH_WORKING → ARCH_DONE | ✅ 通过 | copilot/opus，架构设计输出完整 |
| DEV_WORKING → DEV_DONE | ✅ 通过 | copilot/opus，代码可运行 |
| QA_WORKING → QA_DONE | ✅ 通过 | copilot/gpt-5.4，67 测试全部通过 |
| REVIEW_WORKING → REVIEW_DONE | ✅ 通过 | copilot/gpt-5.4，独立评审（3P1+2P2，无P0） |
| QA_PASS → has_next_step → ARCH | ✅ 通过 | 多步循环正常，Step 1 → Step 2 |
| QA_FAIL → DEV_WORKING 回退 | ✅ 自然触发 | BUG-STEP2-001，空字符串参数处理 |
| QA_FAIL → ARCH_WORKING 回退 | ❌ 未测 | smoke 预设不含 qa_fail_design |
| ESCALATE_L1/L2 升级 | ❌ 未测 | smoke 预设不含 escalate_l1/l2 |
| PAUSED → Resume | ❌ 未测 | smoke 预设不含 paused_resume |
| Agent Fallback 降级 | ❌ 未测 | smoke 预设不含 agent_fallback |

### Agent 路由

| 角色 | Agent | 模型 | 平均耗时 |
|------|-------|------|---------|
| PM | kimi | kimi-for-coding | 4m31s |
| Architect | copilot | claude-opus-4.6 | ~4m |
| Programmer | copilot | claude-opus-4.6 | 3-5m |
| QA | copilot | gpt-5.4 | 6-9m |
| Reviewer | copilot | gpt-5.4 | ~8m |

### 核心发现

1. **outbox 文件交付**：100% 可靠（所有角色均正确写入 outbox，延续 L-23 结论）
2. **QA 自主发现真实 BUG**：BUG-STEP2-001（`--columns ""` 空字符串处理），QA→DEV 反馈回路正常工作
3. **Dispatcher 代劳率**：0%（10/10 Session 均由独立 Agent 完成，对比 trpg-web 的 60% 代劳率大幅改善）
4. **跨 Agent 协作**：kimi(PM) + copilot/opus(ARCH+DEV) + copilot/gpt-5.4(QA+Review) 无缝协同
5. **Review 质量**：3P1 + 2P2，无阻断性问题。P1 包括单列表格解析、--format 无校验、多行单元格缺失

### 消费的 pending-validations

| V 编号 | 状态 | 说明 |
|--------|------|------|
| V-1 | ✅ 已验证 | outbox 文件模式 100% 可靠（所有角色） |
| V-2 | 🟡 部分 | state.yaml 校验 hook 触发正常，未测试校验失败阻断 |
| V-3 | 🟡 部分 | E2E 后置流程已执行（本次补齐），但完整度仍需改进 |
| V-5 | ✅ 已验证 | QA_FAIL → DEV_WORKING 回退自然触发并成功 |
| V-4, V-6~V-9 | 🔴 待验证 | smoke 预设范围外，需 rollback/escalation/infra 预设覆盖 |

### 产出的经验条目

- L-25: E2E 后置处理必须严格执行——报告路径、pending-validations 消费缺一不可

### 遗留问题

1. V-4（Agent Fallback 两层降级）、V-6~V-9 仍为 🔴 待验证
2. Review P1 问题未修复（属于基准项目本身，不影响框架）
3. 建议后续执行 `rollback` 预设覆盖 qa_fail_design + review_fail 路径

---

> 下次 E2E 执行时，从 `testing/pending-validations.md` 获取待验证清单，对照 `testing/benchmark-scenario.md` 的验证矩阵执行。
