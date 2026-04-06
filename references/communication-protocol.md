# 通信协议

> **用途**：定义 RedCap 多 Agent 架构中 Dispatcher 与 Agent、Agent 与 Agent 之间的数据交换格式。  
> **适用范围**：所有角色 Agent 均须遵守本协议。

---

## 1. Agent 返回状态（`__redcap_status`）

每个 Agent 在完成工作后，**必须**在回复中包含以下 JSON 块。Dispatcher 依据此块决定下一步流转。

### 1.1 JSON Schema

```json
{
  "__redcap_status": {
    "status": "completed | failed | blocked | need_user | need_revision",
    "summary": "一句话工作摘要",
    "deliverables": ["交付物相对路径列表"],
    "escalation": {
      "level": 1,
      "target_role": "product-manager",
      "question": "需要决策的具体问题",
      "recommendation": "Agent 自己的建议（可选）"
    },
    "revision": {
      "target_role": "architect | programmer | product-manager",
      "root_cause": "design | code | requirement",
      "description": "需要修订的具体内容描述"
    },
    "next_suggestion": "Agent 对下一步的建议（可选）",
    "lesson": "本次工作中发现的可复用经验（可选）"
  }
}
```

### 1.2 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `status` | ✅ | 本次工作的最终状态，取值见 §1.3 |
| `summary` | ✅ | 一句话摘要，Dispatcher 可用于向用户汇报进展 |
| `deliverables` | ✅ | 本次产出的文件路径列表（相对于 `开发手册/`） |
| `escalation` | 仅 `blocked` 时 | 升级请求的详细信息 |
| `revision` | 仅 `need_revision` 时 | 回退请求的详细信息 |
| `next_suggestion` | ❌ | Agent 对下一步的建议，Dispatcher 仅参考不强制执行 |
| `lesson` | ❌ | 本次工作中发现的可复用经验，Dispatcher 收到后写入 `shared/lessons-learned.md` |

### 1.3 状态枚举

| status 值 | 含义 | Dispatcher 行为 |
|-----------|------|----------------|
| `completed` | 正常完成，交付物已就绪 | 读取 outbox，按状态机推进到下一角色 |
| `failed` | 执行失败（技术错误、超时等） | 记录错误，重试 1 次或升级至 L1 |
| `blocked` | 遇到无法自主决策的问题 | 按 `escalation.level` 升级（L1→PM / L2→用户） |
| `need_user` | 需要用户提供具体信息（密钥、ID 等） | 暂停流程，向用户转述问题 |
| `need_revision` | 发现上游交付物有问题，需要修订 | 按 `revision.root_cause` 回退到对应角色 |

---

## 2. 传递策略

### 2.1 方案 A（主通道）：Outbox 文件写入 ← E2E 验证后升级（2026-04）

Agent 将 `__redcap_status` JSON 写入**自身角色的 outbox 目录**：

```
{role}/outbox/__redcap_status.json
```

**设计依据**：E2E 测试（trpg-web）证明 outbox 文件交付方式 100% 可靠，而 stdout 嵌入方式 Agent 遵从率为 0%（L-12）。文件写入与交付物写入走同一管道，Agent 无需额外记忆"回复末尾输出 JSON"这一反直觉动作。

**Agent 写入约定**：
```json
// 文件路径: {role}/outbox/__redcap_status.json
// Agent 完成工作后，将此文件作为交付物之一写入
{
  "__redcap_status": {
    "status": "completed",
    "summary": "...",
    "deliverables": ["..."],
    ...
  }
}
```

> **生命周期**：Dispatcher 在读取并处理完 `__redcap_status.json` 后，将其内容写入 `.workflow/last-result.json` 作为持久化归档，然后**删除** outbox 中的 `__redcap_status.json`，避免下一轮误读旧状态。

### 2.2 方案 B（兼容通道）：嵌入 response

若 Agent 未写入 outbox 文件但在回复文本末尾输出了 `__redcap_status` JSON 块，Dispatcher 仍可正则提取。此通道保留向后兼容性，不再作为主推方式。

### 2.3 方案 C（断点恢复通道）：last-result.json

`.workflow/last-result.json` 由 Dispatcher 写入（取自方案 A 或 B 的解析结果）。用于断点恢复场景——新会话启动时读取此文件获取上次成功的状态。

> **所有权**：`last-result.json` 的唯一权威写入方是 Dispatcher。

### 2.4 解析优先级

```
1. 读取 {role}/outbox/__redcap_status.json → 存在且合法则使用（主通道）
2. 文件不存在 → 从 response 文本正则提取 __redcap_status JSON（兼容通道）
3. 提取失败 → 读取 .workflow/last-result.json（断点恢复/兜底）
4. 均失败 → 标记 status="failed"，保留原始 response，触发重试或升级
```

---

## 3. 交付物协议

### 3.1 命名约定

```
{角色目录}/outbox/{步骤号}-{交付物名称}.md
```

示例：
- `pm/outbox/需求文档.md`
- `architect/outbox/步骤1-用户认证.md`
- `programmer/outbox/步骤1-自测报告.md`
- `qa/outbox/步骤1-测试报告.md`

### 3.2 标准交付物表

| 源角色 | 交付物路径 | 消费角色 |
|--------|-----------|---------|
| 产品经理 | `pm/outbox/需求文档.md` | 架构师、测试QA |
| 架构师 | `architect/outbox/步骤X-{模块名}.md` | 程序员 |
| 架构师 | `architect/技术框架设计.md`（更新索引） | 程序员、测试QA |
| 程序员 | `programmer/outbox/步骤X-自测报告.md` | 测试QA |
| 程序员 | `shared/API接口文档.md` | 测试QA |
| 测试QA | `qa/outbox/步骤X-测试报告.md` | 产品经理（验收） |

### 3.3 交付物完整性要求

- 交付物必须是**自包含**的——消费角色无需回溯源角色的工作区草稿即可理解
- outbox 中的文件一旦写入，源角色不应在后续修改（除非被回退要求修订）
- 每个交付物文件头部应包含：步骤编号、生成时间、源角色标识

---

## 4. 根因回退码

QA 或其他角色发现问题时，通过 `revision.root_cause` 字段标识根因类型：

| root_cause | 含义 | 回退目标 |
|-----------|------|---------|
| `code` | 代码/实现缺陷 | 程序员 |
| `design` | 方案/架构/跨步约定问题 | 架构师 |
| `requirement` | 需求理解偏差、验收标准不清 | 产品经理 |
