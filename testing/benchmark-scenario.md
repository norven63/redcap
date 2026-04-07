# E2E 基准测试场景

> 每次 E2E 验证使用同一个固定场景，保证跨版本可比性。
> 场景设计覆盖 RedCap 核心路径，同时刻意埋入缺陷触发回退/升级等非正常路径。

## 基准项目：TRPG Web 角色卡管理器

**选择理由**：
- 前后端分离（Express + Vue），覆盖全栈开发场景
- 业务逻辑适中（CRUD + 规则引擎），不至于太简单也不会过于复杂
- 已有一次完整 E2E 历史（trpg-web, 2026-04），可作为基线对比
- 天然支持多步骤（模型层→API层→前端层→集成测试）

## 固定需求描述

```
项目名称：TRPG 角色卡管理器（Web 版）
技术栈：后端 Express + TypeScript，前端 Vue 3 + TypeScript
核心功能：
  1. 角色卡 CRUD（创建、查看、编辑、删除）
  2. 属性点分配（力量、敏捷、体质、智力、感知、魅力，总点数 27）
  3. 技能计算（基于属性值自动计算技能修正值）
  4. 角色卡导出为 JSON
数据存储：SQLite（无需外部数据库依赖）
```

## E2E 验证矩阵

### 正向路径（必测）

| 阶段 | 验证点 | 对应状态机节点 |
|------|--------|--------------|
| PM 需求采集 | PM 输出结构化需求文档；outbox 交付物完整 | PM_WORKING → PM_DONE |
| 架构设计 | 架构师读取 PM 交付物；输出模块设计+API文档；outbox 完整 | ARCH_WORKING → ARCH_DONE |
| 开发实现 | 程序员读取架构交付物；代码可编译运行；outbox 完整 | DEV_WORKING → DEV_DONE |
| QA 测试 | QA 执行自动化测试；测试报告格式正确；outbox 完整 | QA_WORKING → QA_DONE |
| Review | Reviewer 独立评审；跨模型族验证 | REVIEW_WORKING → REVIEW_DONE |

### 刻意注入缺陷（按需选测）

> 以下缺陷在 E2E Prompt 中通过特殊指令注入，不修改框架代码。

| 缺陷注入 | 触发路径 | 对应 pending-validation |
|---------|---------|----------------------|
| 架构遗漏分页参数 | QA_FAIL → ARCH_WORKING 回退 | V-6 |
| API 返回字段缺失 | QA_FAIL → DEV_WORKING 回退 | V-5 |
| 需求模糊（"权限灵活配置"） | ESCALATE_L1 → PM | V-7 |
| 商业决策超出技术范畴 | ESCALATE_L2 → 用户 | V-8 |
| QA 需要人工验证 GUI | PAUSED → Resume | V-9 |

### 通信协议验证（每次必检）

| 检查项 | 方法 |
|--------|------|
| outbox 文件模式 | 每个角色完成后检查 `{role}/outbox/__redcap_status.json` 存在 |
| state.yaml 一致性 | 每次状态转移后执行 `tools/redcap-check-state.sh` |
| Session 管理 | 检查 `sessions.yaml` 记录完整性 |
| Fallback 触发 | 如首选 Agent 不可用，检查是否按 Model→CLI 两层降级 |

## 执行建议

1. **频率**：不强制每次迭代都 E2E，但 `pending-validations.md` 积累超过 5 个 🔴 时建议执行
2. **顺序**：先跑正向路径（快速验证基本功能），再选择性注入缺陷
3. **耗时预估**：正向路径约 30-60 分钟（取决于 Agent 响应速度），含缺陷注入约 2-3 小时
4. **报告产出**：执行结果写入 `testing/latest-e2e-report.md`
