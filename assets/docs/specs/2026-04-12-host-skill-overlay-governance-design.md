# Host Skill Overlay Governance — P0 修复设计

> 状态：已批准并进入实现
> 日期：2026-04-12
> 主题：修复宿主通用 skill 将 RedCap 可自治决策错误升级成人工介入的 P0 故障

---

## 1. 背景与问题

本次 P0 暴露的不是“单次 ask_user 用错了”，而是一次明确的 **protocol collision / authority inversion**：

1. RedCap 已有 `.dev-task.md` canonical truth、PM Gate、自主执行授权、Prism 支撑与 host-agent interop governance。
2. 宿主通用 brainstorming skill 仍把“逐轮 ask_user / 用户批准 / 独立 spec 工作流”作为默认硬门。
3. 当两者同时生效时，宿主 overlay protocol 越权覆盖了 RedCap-native 控制面，把原本可由 AI 自主吸收的 tranche 分解与设计收口错误升级成人工阻断。

这类故障若不单独收口，会持续破坏 RedCap 的核心承诺：**人类只在 AI 真算不出来时介入**。

---

## 2. 目标与非目标

### 2.1 目标

1. 明确声明：宿主通用 skill 只是 **advisory overlay**，不是 Layer B authority。
2. 明确人工介入门槛：仅限 AI 无法推断的外部事实/偏好/凭证、AI 无法直接执行/验证的人类动作、或 Norven 保留决策（包括架构方向禁区与外部依赖禁区）。
3. 只在 RedCap-native 一侧建立可拥有的规则；共享宿主 skill 若仍冲突，只能被视为 degraded overlay，不能作为 RedCap 任务中的 patch surface。
4. 明确 authority chain：overlay / host skill 产物不得覆盖 `.dev-task.md`、任务账本、门禁结果、runtime receipt 或 closeout 结论。
5. 把本次 P0 固化为 lesson 与 canonical ledger，防止后续长任务再次复现。

### 2.2 非目标

1. 不假装通过 shell gate 物理拦截所有 ask_user。当前 ask_user 发生在宿主层，仓库内脚本无法直接拦截。
2. 不重写 Loom 的 Layer A PM/QA 状态机。
3. 不恢复 `compass/docs/` 等被冻结 tranche 的实现；它们在本 P0 修复前继续暂停。

---

## 3. 方案对比

### 方案 A：只改 RedCap 文档

- 优点：改动小。
- 缺点：冲突 skill 本身仍保留默认 ask_user / approval 硬门，复发概率高。

### 方案 B：只改 brainstorming skill（宿主 shared asset）

- 优点：直击表面触发点。
- 缺点：这属于改宿主共享资产，不是修 RedCap 自身；即使短期见效，也不能作为 RedCap 的正式支持口径。

### 方案 C：repo-owned 收口 + degraded 判定（采纳）

只修改 RedCap 自身可拥有的资产，并把共享宿主 skill 明确降级为 carrier-owned overlay：

1. RedCap-native 控制面（`.dev-task.md`、`CONTRIBUTING.md`、`SKILL.md`、`ARCHITECTURE.md`、`agent-constraints.md`、`lessons.md`）
2. 宿主 shared skill 若仍冲突，则判定该集成为 **degraded / unsupported overlay**，而不是去修改它的原始文件

理由：

- 补的是 RedCap 自己的 authority 声明，而不是把宿主共享资产纳入可修改边界。
- 对当前问题更诚实：这是一条 **prompt-level hard limitation + canonical-truth discipline**；若宿主仍冲突，正确结论是 degraded，而不是偷偷改宿主 shared skill。

---

## 4. 最终设计

### 4.1 Authority 规则

新增一条显式不变量：

> **宿主通用 skill 只能是 advisory overlay；当它与 RedCap-native PM Gate / autonomy 冲突时，必须让位给 RedCap 控制面。**

### 4.2 人工介入门

只有以下场景允许 ask_user / need_user / blocked_on_user：

1. 缺少 AI 无法推断的外部事实、凭证、运行时信息或业务偏好
2. 缺少 AI 无法直接执行/验证的人类动作（如 GUI/manual validation）
3. Norven 明确保留的决策（包括架构方向性变更与外部依赖引入）

除此之外，tranche 分解、顺序裁剪、方案对比、设计收口都必须优先在 RedCap-native 控制面内完成。Prism 死锁或 Dispatcher 升级建议本身只算诊断信号，不算人工介入理由；它们必须先定位到具体缺口，才能上抛给 Norven。

### 4.3 repo-owned 修复面

#### RedCap-native

- `.dev-task.md`：切换到当前 P0，冻结其他 tranche
- `compass/CONTRIBUTING.md`：新增 overlay compatibility 规则
- `SKILL.md`：新增 overlay subordinate 索引规则
- `ARCHITECTURE.md`：把 host generic skill 纳入 truth surface / governance model
- `references/agent-constraints.md`：防止子 Agent 轻易把问题上抛给人类
- `compass/knowledge/lessons.md`：沉淀本次失败模式

#### host-shared skill 结论

- `brainstorming` 这类共享宿主 skill 只能被视为 carrier-owned overlay
- 若其默认协议与 RedCap 冲突，RedCap 只能在自己的控制面中拒绝承认越权结果，不能直接改写该 skill 原件
- 若未来需要兼容，应通过宿主侧独立版本化适配或上游维护者变更来解决，而不是由 RedCap 任务直接 patch

---

## 5. 验证口径

本次修复完成后，至少应满足：

1. 当前 P0 在 `.dev-task.md` 中成为 canonical truth，其他 tranche 明确冻结。
2. RedCap-native 文档与架构说明一致表达 overlay subordinate 规则。
3. RedCap-native 文档明确声明：共享宿主 skill 不是 patch surface；若不改宿主 skill 就无法稳定工作，则该集成按 degraded / unsupported overlay 处理。
4. 子 Agent 共享约束明确：只有 AI 真算不出来，或确实需要人类亲自执行/验证时，才返回 `need_user` / `blocked`。

---

## 6. 风险与限制

### 6.1 当前限制

由于 ask_user 属于宿主层工具调用，本仓库内的 shell gate 无法像 task-report / pending-closure 那样物理拦截它。因此本次修复的真实形态是：

- **prompt-level hard limitation**
- **canonical-truth discipline**
- **双边 skill 兼容约束**

### 6.2 风险控制

为避免“写了规则却仍被忘掉”，本设计要求：

1. 规则进入 `SKILL.md`、`CONTRIBUTING.md`、`ARCHITECTURE.md`
2. 失败模式进入 `lessons.md`
3. 子 Agent 共享约束同步更新
4. 当前 `.dev-task.md` 明确冻结其他 tranche，避免修复过程中再次偏航
