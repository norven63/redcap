# RedCap Hook 行为契约 (Hook Standards)

> **定位**：本文件分两层定义 RedCap 的 Hook 体系：
> - **§1 不变量清单**：哪些动作必须被 Hook 保障、为什么不能依赖 LLM 自觉执行
> - **§2+ 实现规范**：Hook 脚本如何满足不变量要求
>
> 查询"某个动作是否需要 Hook 保障"→ 看 §1；查询"Hook 脚本怎么写"→ 看 §2。

---

## 1. 不变量清单（Hook 保障需求目录）

> **阅读方式**：每行代表一个必须由 Hook 物理保障的不变量。
> "不能靠 LLM 自觉"列解释为什么软约束（Prompt 指令）不够。

| 不变量 | 适用层 | 为什么不能靠 LLM 自觉 | 主动保障机制 | 兜底/审计机制 |
|--------|--------|----------------------|------------|-------------|
| **Review 不可被跳过** | Layer A | LLM 上下文衰减，ALL_DONE 后易直接关闭 | 状态机 REVIEW 节点 | Hook → 检测 REVIEW_PASS 缺失 → 新 Agent 补 Review |
| **飞书通知不可遗漏** | Both | 任务中断时 LLM 无法感知自己已停止 | on_ALL_DONE 脚本主动发送 | Hook → 检查本 session 是否已发送，若无则补发 |
| **临时标记文件必须清理** | Both | LLM 不感知副作用，无法自主清理 `/tmp/redcap-*` | — | Hook → rm -f（唯一保障层） |
| **Layer B 变更须独立评审** | Layer B | 作者盲点：改框架的 Agent 不能评价自身变更 | — | Hook → 检测 Layer B CWD → 拉起独立 Agent 架构评审 |
| **Pending Actions 必须落盘** | Layer A | 会话崩溃时未落盘 Action 永久丢失 | Dispatcher 主动写入 state.yaml | Hook → 检查 state.yaml 完整性（审计保障） |

> **扩展规则**：新增"必须保障"的动作，先在此表登记，再在 §2 中补充实现规范。不允许直接写进脚本而不在此表体现。

---

## 2. SessionEnd (Stop Hook) 铁律

任何宿主会话结束时，必须按以下顺序执行三个阶段，严禁跳过或部分执行。

> **顺序说明**：审计（Phase 1）先于清理（Phase 2），确保清理不会销毁审计所需的中间状态。

### Phase 1: 状态审计 (Audit)
- **目标**：防止 Agent 在任务未完结时"潜逃"或跳过门禁。
- **强制动作**：
  - **Review 漏失检查**：读取 `.workflow/state.yaml`，若 `status` 为 `ALL_DONE` 但 `history` 中缺失对应的 `REVIEW_PASS` 记录，则必须拉起新 Agent 补齐 Review。
  - **状态停滞检查**：若 `status` 仍为 `*_WORKING`，则在日志中记录异常中断。
  - **Layer B 专项评审**：若检测到正在修改 RedCap 框架自身，必须拉起独立评审 Agent 检查 §6 联动表和经验沉淀。

### Phase 2: 原子清理 (Cleanup)
- **目标**：销毁冗余的临时会话状态。
- **强制动作**：
  - 删除以本 `session_id` 命名的标记文件（`/tmp/redcap-layerA-head-*` 等）。
  - 清理 24 小时以上的历史过期标记文件。

### Phase 3: 异步通知与同步 (Sync)
- **目标**：保证人类搭档对进度的知情权。
- **强制动作**：
  - **飞书通知兜底**：检查本次 session 是否产生过 `on_ALL_DONE` 通知。若无，且状态已推进，则补发汇总通知。
  - **Pending Actions 持久化**：确认所有未完成的 Action 已落盘到 `state.yaml`。
---

## 3. 脚本实现规范

1. **宿主无关性**：脚本必须能自动识别当前 CWD 的项目类型，并根据 `state.yaml` 动态决策动作，而不是写死逻辑。
2. **静默失败**：审计过程中的非致命错误（如飞书网络不通）应记录 stderr 并 exit 0，严禁导致 CLI 进程僵死。
3. **幂等性**：Hook 脚本必须支持多次重复调用而不会产生副作用（防止多重 Hook 触发导致重复通知）。

---

## 4. 宿主对齐矩阵

> **单一来源**：各宿主的 Hook 部署状态和配置文件位置，以 [`knowledge/host-reliability.md §3.2`](../knowledge/host-reliability.md) 为权威来源，本节不重复维护。

本节只记录**不变的架构约束**：
- 所有宿主的 SessionEnd/Stop Hook 入口必须最终汇聚到 `tools/redcap-layerA-session-end.sh`（通用分发器）
- Layer A（用户项目）Hook 配置必须注册在**用户级**配置文件，使用 RedCap 安装目录的**绝对路径**，而非项目工作区
- Layer B（RedCap 自身）Hook 配置注册在 RedCap 仓库的**项目级**配置文件
