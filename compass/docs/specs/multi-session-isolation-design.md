# 多会话隔离设计（Multi-Session Isolation Design）

> **定位**：本设计面向 RedCap 的跨会话并发隔离问题，覆盖 Layer A、Layer B、A↔B 通信、A2A 会话续接与 Prism 并发运行。  
> **状态**：runtime foundation、pending closure、host workboard mirror 与 explicit import protocol 已落地；更大范围 acceptance / archive 演进持续迭代。
> **设计策略**：方案 C —— **有截止线的兼容迁移**，不做长期双轨共存。
> **阅读指引**：若你想看面向人类解释的中文版说明，而不是偏设计约束的底稿，请同时阅读 `compass/docs/specs/session-isolation-continuity-guide.md`。

---

## 一、问题背景

RedCap 当前已经具备多种会话与并发形态：

1. **Layer A**：用户项目工作流，可被恢复、并行打开、跨 role 续接。
2. **Layer B**：RedCap 自身开发，会触发宿主 Hook、独立评审、任务报告审计与飞书兜底。
3. **A↔B 通信**：框架自身开发与用户项目工作流之间会共享部分上下文、协议与调度结果。
4. **A2A / Prism**：一个 Agent 拉起其他 Agent 或多个 Agent 并行分析，天然存在多 session / 多 run 并发。

当前问题不只是“某几个 marker 文件会冲突”，而是**临时状态、共享状态、发布状态和宿主状态缺少统一分层**。只要多个会话同时运行，就可能出现：

- 同宿主并发会话共享 `/tmp` 标记文件
- 旧会话误读新会话的临时缓存
- A↔B / Prism 误把“私有中间态”当成“可共享正式状态”
- 兼容逻辑无边界扩张，最终留下历史债

因此，这次设计的目标不是给某个脚本补丁，而是建立一套**统一、可证明、可迁移、可验收**的隔离模型。

---

## 二、设计目标

### 2.1 核心目标

1. **同宿主并发的框架级硬隔离**  
   两个 Claude / Gemini / Copilot / Kimi 会话同时运行时，彼此的临时状态和收尾链路不得互相干扰。

2. **跨 Layer 与 Prism 统一语义**  
   Layer A、Layer B、A↔B、A2A、Prism 不再各自发明“session 隔离”的实现方式，而是复用同一套状态分层和命名规则。

3. **私有态与发布态严格分离**  
   “当前 session 的临时脑内状态”与“允许其他角色/其他 run 依赖的正式发布状态”必须有清晰边界。

4. **兼容迁移不养债**  
   允许过渡期兼容，但兼容层必须是**短命施工层**，带删除门禁和命中统计，禁止长期双轨。

5. **验收以并发矩阵为准**  
   不再只靠单会话 smoke 宣称“已修复”；必须通过真实并发场景验证。

### 2.3 术语说明：本设计中的“硬隔离”是什么意思

本设计中的“硬隔离”特指 **RedCap 协议层 / helper 层的确定性非干扰保证**：

- 不同会话不会再因共享文件名、共享 registry 或模糊归属而**意外串号**
- 合规的 RedCap 组件必须持有正确的会话身份与能力令牌，才能读写 session 私有态
- 真相文件有明确主写者，其他参与方只能走 outbox / append-only

本设计**不宣称提供 OS 级安全沙箱**。  
也就是说，它解决的是“框架自身并发串扰”和“错误状态归属”问题，而不是防御同机同用户下的恶意越权进程。

### 2.2 非目标

1. 不把 git 工作树、版本控制文件、已提交文档做 session 隔离。
2. 不把所有状态一刀切全部 session 化。
3. 不把“能生成一个 ID”误当成“已经实现硬隔离”。
4. 不在本设计中重新发明 Dispatcher / Prism 协议本身，只重构其运行时隔离基础设施。

---

## 三、范围分期

### Phase 1：运行时状态隔离（Layer A / Layer B）

目标：消除宿主级 `/tmp` 共享 marker，建立统一的 `runtime_session_id` 与会话目录。

### Phase 2：通信与 run 级隔离（A↔B / A2A / Prism）

目标：建立 run-scoped 发布层，禁止跨 session 直接读取私有 temp，消除 Prism / A2A 的共享 registry 冲突。

### Phase 3：兼容迁移、删除旧协议与验收收口

目标：通过兼容读、旧协议删除门禁、并发矩阵验证，把系统稳定迁到新协议。

> 分期是**实施顺序**，不是三套不同设计。三期共享同一套状态模型与 ID 体系。

---

## 四、状态分层模型

这是本设计的核心。所有文件、标记、registry、缓存，都必须先归类，再实现。

| 层级 | 含义 | 是否共享 | 典型例子 | 规则 |
|---|---|---:|---|---|
| **Global-static** | 仓库内静态协议/规则/模板 | ✅ | `CONTRIBUTING.md`、`protocol.md`、角色定义、hook JSON | 版本控制管理，不做 session 隔离 |
| **Project-shared** | 一个项目内长期共享的业务真相 | ✅（项目内） | `.workflow/state.yaml`、项目级 `sessions.yaml`、已归档报告 | 不能承载临时缓存；必须可审计 |
| **Run-scoped** | 一次工作流或一次 Prism 运行的共享上下文 | ✅（本次 run 内） | `workflow_instance_id`、`prism_run_id` 对应目录、run manifest | 只能保存显式发布的数据 |
| **Session-scoped** | 单个运行时会话的私有中间态 | ❌ | initial-head、notified、review log、subtask 输出、collect 缓存 | 必须硬隔离，禁止跨 session 直读 |

### 4.1 设计铁律

1. **临时态默认属于 Session-scoped**，除非明确声明为 run/project 共享。
2. **任何跨 session 可见的数据，必须先“发布”到 run-scoped 层。**
3. **Project-shared 层是真相层，不是缓存层。**
4. **禁止再使用宿主级文件名承载 session 私有状态**，如 `/tmp/redcap-layerB-claude-*`。

---

## 五、统一身份模型

### 5.1 四类标识符

1. **`host_session_id`**  
   宿主原生提供的 session 标识。若宿主提供，应保存，但不能假设所有宿主都有。

2. **`runtime_session_id`**  
   RedCap 的统一运行时会话 ID。  
   **这是 session-scoped 状态的唯一主键。**

3. **`workflow_instance_id`**  
   Layer A 一次工作流实例的标识。  
   用于聚合同一次 PM→ARCH→DEV→QA→Reviewer 流转及相关 handoff。

4. **`prism_run_id`**  
   Prism 一次多 Agent 运行的标识。  
   用于聚合一次 redteam / council / explore / test 的全部 registry、collect、synthesis、audit 状态。

5. **`session_binding_key`**  
   用于把“恢复后的同一逻辑会话”重新绑定到原 `runtime_session_id`。  
   它是 **resume 语义的稳定定位键**，不能直接拿 `host_session_id` 代替，也**不是鉴权因子**。

### 5.2 关系规则

- 一个 `workflow_instance_id` 下可以有多个 `runtime_session_id`
- 一个 `prism_run_id` 下可以有多个 `runtime_session_id`
- `runtime_session_id` 是**私有态主键**
- `workflow_instance_id` / `prism_run_id` 是**共享态主键**
- `host_session_id` 只是**当前宿主回合的别名**
- `session_binding_key` 才是**恢复到原私有目录**时的稳定定位键

### 5.3 关于“自己生成并保存 session id”

**可以，但必须满足一个前提：后续事件能够稳定重新关联到同一会话。**

也就是说：

- **可行场景**：RedCap 掌握启动权，能在启动前生成 `runtime_session_id` 并注入到后续 hook / 子进程 / manifest
- **不可自欺场景**：宿主不给稳定标识、后续事件也拿不到映射键，只是“生成了一个 ID 并写到某处”，但无法证明 `sessionEnd` 一定能找到它

结论：  
**“能生成 ID” ≠ “已经完成会话隔离”。**  
会话隔离要求的是**稳定关联能力**，不是一次性造号能力。

### 5.4 `runtime_session_id`、`session_binding_key` 与能力令牌要求

`runtime_session_id` 必须满足以下约束：

1. **主机范围内全局唯一**：至少包含项目标识（如 `project_hash`）+ 128 bit 随机成分（如 UUIDv4 强度）
2. **不可预测**：不能使用时间戳自增、role 名或宿主名等低熵字段充当唯一性来源
3. **只作为目录键不够**：还必须配套一个 `runtime_session_capability`

`runtime_session_capability` 的职责：

- 由会话启动方生成
- 只传给当前会话拥有的进程树 / helper
- helper 读写 session 私有态前，必须同时验证：
  - `runtime_session_id`
  - `runtime_session_capability`

> 目录命名负责**避免碰撞**，能力令牌负责**防止合规组件误读误写别的会话私有态**。

`session_binding_key` 必须满足以下约束：

1. **在所属 run 内唯一**：同一 `workflow_instance_id` 或 `prism_run_id` 下，不允许两个 live session 复用同一个 `session_binding_key`
2. **跨 resume 稳定**：同一逻辑会话恢复后必须复用原 `session_binding_key`
3. **可公开但不可滥用**：它可以保存在 run-shared manifest 中作为定位键，但**不能单独用于授权恢复或 takeover**
4. **建议构成**：`<run_id>/<role-or-slot>/<launch_ordinal>` 或等价结构化键，重点是稳定与唯一，而不是保密

---

## 六、宿主引导策略（Host Bootstrap Strategy）

### 6.1 原生可识别宿主

适用：Claude / Gemini 等 Hook 能提供 `session_id` 的宿主。

策略：

1. 读取原生 `host_session_id`
2. 建立 `host_session_id -> runtime_session_id` 的**当前别名映射**
3. 同时在 run / session manifest 中持久化 `session_binding_key -> runtime_session_id` 作为**公开定位关系**
4. capability 只保存在 session 私有 owner 元数据或 launcher/coordinator 私有存储中，不写入 run-shared published state
5. resume 时先用 `session_binding_key` 定位，再通过 capability / owner lease 验证；`host_session_id` 仅作为当前回合别名，不作为唯一恢复依据
6. 所有 session 私有态写入 `runtime_session_id` 目录

### 6.2 RedCap 控制启动的宿主

适用：A2A、Prism、Dispatcher 拉起的子 CLI。

策略：

1. RedCap 在启动前先生成：
   - `runtime_session_id`
   - `runtime_session_capability`
   - `session_binding_key`
2. 通过环境变量、命令参数或 **session 私有 owner metadata / launcher 私有状态** 注入给被调起进程
3. hook / 脚本 / collect / review 全链路复用该 ID 与 capability
4. 后续 resume 按 `session_binding_key` 找回原目录，再由 launcher/coordinator 恢复 capability，而不是重新 mint 一个新目录

> 这是最可靠的硬隔离路径，因为启动权在我们手里。

### 6.3 宿主不提供 session_id，且启动权不在 RedCap 手里

适用：手工直接打开的 Copilot 仓库会话。

策略：

1. **full isolation mode**：必须通过 RedCap launcher / wrapper 启动，使 RedCap 在启动前注入 `runtime_session_id`
2. **safe degraded mode**：若是手工直接启动、又拿不到稳定身份，则只允许执行**无会话副作用**的 stateless hook 行为

safe degraded mode 的含义：

- 允许：只读审计、读取 project/run 已发布状态、静态检查、无需 once-only 语义的提醒
- 禁止：写 session-scoped marker、写 run manifest/outbox/handoff、参与 coordinator/owner 角色、once-only 通知判定、依赖 per-session 清理的逻辑、认领已有 `runtime_session_id`

> 核心原则：**宁可显式降级，也不伪装成“已经隔离”。**

### 6.4 宿主 continuity mirror 与 explicit import

在当前实现里，宿主 `plan.md` / workboard 不再只镜像 canonical pointer，还会追加一块 **Session Mirror**：

- `session_handle`
- `runtime_session_id`
- `session_binding_key`
- `task_id / confirmed_hash`
- `continuity_authority`
- `continuity_state`

其中 `continuity_state` 只允许取以下几类值：

| 状态 | 含义 |
|---|---|
| `fresh-session` | 当前会话没有自身 continuity record，也没找到兼容来源 |
| `self-recorded` | 当前会话已有自己的 continuity record |
| `import-suggested` | 当前会话没有自身记录，但找到了 compatible source session |
| `imported` | 已通过 explicit import 导入来源会话的 continuity artifacts |

对应协议：

1. **先发布，再镜像**：`redcap-session-continuity.sh sync` 会先把当前 continuity authority 发布到 `compass/.runtime/sessions/<runtime_session_id>/manifest.yaml` / `provenance.yaml`，然后才渲染宿主 Session Mirror。
2. **只建议，不自动继承**：系统只会基于 repo-local manifest 给出 compatible source session 与导入命令，不会默认自动接管最近会话。
3. **导入只复制 continuity artifacts**：`plan.md` 快照、`files/`、`checkpoints/` 进入目标会话的 `files/imported-sessions/<source_handle>/`
4. **源会话保持原样保留**：显式导入是 copy，不是 move，不会破坏原会话目录
5. **导入同时记账**：除拷贝资产外，还要追加 `compass/.runtime/continuity/import-registry.jsonl` 与 `audit-log.jsonl`
6. **导入资产带来源 metadata**：必须记录 `source_session_handle / source_plan / source_task_id / source_confirmed_hash / imported_at`
7. **无 runtime 不得伪造连续性**：缺少 `runtime_session_id` 时，只允许输出 `fresh-session + continuity_authority=degraded-no-runtime-manifest`，不得冒充 `self-recorded / import-suggested / imported`

> 这里的关键不是“省事续接”，而是让 continuity bridge 变成**显式、可审计、可保留来源**的协议动作。

---

## 七、存储布局升级

### 7.1 Session-scoped 目录

统一写入：

```text
/tmp/redcap/runtime/<runtime_session_id>/
  owner.json
  layerA/
    initial-head
    notified
    ownership-check
  layerB/
    initial-head
    notified-head
    alerted-head
    current-report-path
  review/
    review-result
    review-log.md
  a2a/
    round-cache/
  prism/
    collect-cache/
    role-output/
```

补充约束：

1. session 目录由创建方以 `0700` 权限创建
2. `owner.json` 至少记录：
   - `runtime_session_id`
   - `session_binding_key`
   - `project_hash`
   - `capability_hash`
   - `created_at`
3. helper 访问该目录前，必须校验 capability

### 7.2 Run-scoped 目录

#### Layer A

```text
.workflow/runs/<workflow_instance_id>/
  manifest.yaml
  role-sessions.yaml
  outbox/
  handoffs/
  checkpoints/
```

#### Prism

```text
prism/runs/<prism_run_id>/
  session-registry.yaml
  collect/
  synthesize/
  audit/
  artifacts/
```

### 7.3 Repo-local continuity 层

新增一层由 RedCap 自己维护、但只在本地存在的 continuity published state：

```text
compass/.runtime/
  sessions/<runtime_session_id>/
    manifest.yaml
    provenance.yaml
  continuity/
    import-registry.jsonl
    audit-log.jsonl
```

约束：

1. 该层是 **repo-local continuity authority**，必须加入 `.gitignore`
2. `manifest.yaml` / `provenance.yaml` 的单主写者是 `redcap-session-continuity.sh`
3. 宿主 workboard 只允许读取这层结果，不允许反向成为 authority

### 7.4 Project-shared 层

保留在原位置，但职责收窄为“长期真相”：

- `.workflow/state.yaml`
- `.workflow/sessions.yaml`（后续需升级索引粒度）
- 已归档任务报告 / Prism 报告 / lessons

---

## 八、通信模型：私有态与发布态分离

### 8.1 私有态不可直读

任何 session 私有目录中的内容，只能由**持有 `runtime_session_id + runtime_session_capability` 的 RedCap 合规执行者**通过 helper 读取或写入。

不允许再出现：

- 一个 hook 直接去读另一个会话的 `/tmp/redcap-*`
- Prism 一个 run 直接读取另一个 run 的 collect cache
- A↔B 通过“约定俗成的临时文件名”偷看中间状态

### 8.2 共享必须显式发布

若某个状态需要被其他 session / 角色 / Prism 运行依赖，则必须写入 run-scoped 层：

- `manifest.yaml`
- `outbox/`
- `session-registry.yaml`
- `handoffs/`

只有写入这些“发布层”后，其他参与方才允许读取。

### 8.3 一个真相文件只能有一个主写者

以下类型文件必须遵守**单主写者原则**：

- `state.yaml`
- `manifest.yaml`
- `session-registry.yaml`
- `role-sessions.yaml`

其他参与者若要上报状态，只能：

1. 写自己的 outbox / append-only 记录
2. 由主写者统一归并

> 并发不是靠“大家一起改同一个 YAML”解决，而是靠“私有产出 → 发布层 → 主写者归并”解决。

### 8.4 主写者归属与接管规则

| 真相文件 | 主写者 | 其他参与方如何上报 |
|---|---|---|
| `.workflow/state.yaml` | Layer A Dispatcher / workflow coordinator | 写 `outbox/` 或 status 记录，由 coordinator 归并 |
| `.workflow/runs/<workflow_instance_id>/manifest.yaml` | 当前 workflow coordinator | 写 append-only handoff / outbox，由 coordinator 归并 |
| `.workflow/runs/<workflow_instance_id>/role-sessions.yaml` | 当前 workflow coordinator | 不允许 worker 直接写 |
| `prism/runs/<prism_run_id>/session-registry.yaml` | Prism coordinator（Cap / Dispatcher） | 各 role 只写本角色产物，coordinator 回填 registry |

接管规则：

1. 每个 run 真相文件必须配套 `owner.json` / `lease.json`
2. 只有当前 owner 或合法接管者可以写真相文件
3. 接管必须满足以下之一：
   - 前 owner 显式 handoff
   - owner lease 过期
   - coordinator/launcher 依据 `session_binding_key` 完成定位，且重新签发有效 capability
4. worker session 不允许自发竞选 owner

---

## 九、A↔B、A2A 与 Prism 的具体约束

### 9.1 Layer A / A↔B

1. `sessions.yaml` 不再只按 `role` 建索引，应至少提升到 **`workflow_instance_id + role + session_binding_key`**
2. Layer B 不直接读取 Layer A 的 session 私有态，只能读其发布层
3. 跨 Layer handoff 必须写入 run manifest / handoffs 目录

### 9.2 A2A

1. A2A 的 CLI session handle 归属于某个 `workflow_instance_id` 或 `prism_run_id`
2. 不允许把 A2A 会话句柄写到全局单文件后供其他 run 复用
3. 多轮续接必须通过 run 目录中的 session map 查找

### 9.3 Prism

1. `session-registry.yaml` 从“全局单点运行时文件”升级为**每个 `prism_run_id` 独立一份**
2. collect / schema 追问 / synthesis / audit 缓存均落在该 run 目录下
3. Dispatch Firewall 不仅限制 Prompt 级读取，也要在运行时状态布局上避免误读其他 run 的中间产物

---

## 十、兼容迁移策略：新写旧读，禁止长期双写

### 10.1 迁移原则

1. **V2 是唯一权威写路径**
2. 兼容层只提供**旧读 / 有条件桥接**
3. 禁止无期限双写
4. 每次命中旧路径都必须统计 `legacy_hit`

### 10.2 迁移步骤

#### 第一步：引入 V2 运行时目录与 ID

- 新代码写入 `runtime_session_id` / `workflow_instance_id` / `prism_run_id` 新布局
- 旧文件仅保留读取

#### 第二步：兼容桥接

- 若发现旧 marker，先检查它能否通过可信键**确定性绑定**到当前运行上下文，例如：
  - `session_binding_key`
  - 与当前 owner lease 一致的 run owner 元数据
  - 旧标记中直接携带的 `runtime_session_id`
- **只有可确定绑定时**，才允许导入到 V2 目录并记录 `legacy_hit`
- 若旧 marker 来源不明、无法可信归属，则**禁止导入到权威目录**；只能进入 `legacy-quarantine/` 并触发告警
- 兼容层允许读取旧值，但不继续把新值镜像写回旧路径

#### 第三步：审计与收口

- 统计真实运行中的 `legacy_hit`
- 找出仍依赖旧路径的脚本 / hook / 文档
- 完成最后一批迁移

#### 第四步：删除兼容层

仅当满足删除门禁时，才能删 compatibility reader。

### 10.3 删除旧协议门禁

必须同时满足以下条件：

1. 并发验收矩阵全部通过
2. `legacy_hit` 归零
3. Layer A / Layer B / Prism 的运行时布局已全面切到新目录
4. reviewer 与 Prism redteam 未发现隐式旧路径依赖
5. 文档真相表已同步到位

---

## 十一、错误处理与降级策略

### 11.1 拿不到 `runtime_session_id`

处理：

- 进入 **safe degraded mode**
- 禁止写 session-scoped marker
- 仅允许无副作用审计或显式告警

### 11.2 run 级真相文件发生竞争写入

处理：

- 拒绝并发直接写入
- 写入方降级到 outbox / append-only
- 主写者负责归并

### 11.3 命中旧路径

处理：

- 读取允许
- 必须记录 `legacy_hit`
- 不允许 silent fallback

### 11.4 恢复 / 崩溃场景

处理：

- 以 run manifest、`session_binding_key` 与 session 目录为恢复基线
- 允许 resume 继续使用原有 `runtime_session_id`
- 若宿主回连后给出新的 `host_session_id`，必须通过 `session_binding_key` 回绑
- `session_binding_key` 只负责定位；真正恢复 session 私有写权限还需 coordinator/launcher 恢复 capability
- 不允许恢复时重新绑到另一个 session 私有目录

### 11.5 `safe degraded mode` 操作矩阵

| 操作 | 是否允许 |
|---|---:|
| 读取 Global-static / Project-shared | ✅ |
| 读取 run 已发布状态 | ✅（只读） |
| 写 session 私有目录 | ❌ |
| 写 run manifest / outbox / handoff | ❌ |
| 认领 coordinator / owner 角色 | ❌ |
| 触发 once-only 通知与去重语义 | ❌ |
| 输出只读审计 / 警告 | ✅ |

---

## 十二、验收矩阵

### 12.1 同宿主并发

1. 两个 Claude Layer B 会话并发
2. 两个 Gemini 会话并发
3. 两个 Copilot（full isolation mode）并发

验证点：

- 私有 marker 不冲突
- once-only 通知语义正确
- review log 不串号

### 12.2 跨层并发

1. Layer A 工作流运行中，同时开启 Layer B 自身开发会话
2. A↔B 有 handoff，但双方私有缓存互不可见

验证点：

- run 共享态可见
- session 私有态不可见

### 12.3 Prism 并发

1. 两个 Prism run 同时 dispatch / collect / synthesize
2. 不共享 session-registry
3. 不误读别的 run 的 collect cache / artifacts

### 12.4 迁移与恢复

1. 带旧 marker 升级启动
2. 中途崩溃恢复
3. resume 后继续同一 run / session
4. compatibility reader 删除前后对比

### 12.5 `safe degraded mode` 验收

1. 手工直接启动的 unmanaged Copilot 会话
2. 能读取已发布状态，但不会写 session 私有态
3. 不会误写 run manifest / outbox
4. 不会伪装成 full isolation mode

---

## 十三、实施建议（非代码细节）

1. **先抽象“运行时身份与路径解析”原语**  
   先统一 `runtime_session_id` / run path 的解析，再改各脚本；不要先在每个脚本里各自拼路径。

2. **先收口 Layer B，再扩到 Layer A / Prism**
   Layer B 是当前已知问题最集中处，也是最容易验证宿主并发的切入点。

3. **Prism 必须单独做并发验收**
   Prism 的问题不只是 session 冲突，还包括 run registry、collect cache、audit artifact 的并发污染。

4. **把“safe degraded mode”写进文档和脚本**
   不能让未来维护者误以为“手工 Copilot 会话也天然具备 full isolation”。

---

## 十四、主要风险与对应策略

| 风险 | 描述 | 对策 |
|---|---|---|
| 运行时身份引导不稳定 | 宿主不给 session_id，启动权也不在 RedCap 手里 | 区分 full isolation 与 safe degraded mode，禁止伪隔离 |
| 兼容层失控 | 旧读逻辑长期遗留 | 用 `legacy_hit` + 删除门禁收口 |
| 真相文件竞争写入 | 多个并发角色同时改 registry | 单主写者 + outbox 归并 |
| Prism 并发污染 | 多 run 共享中间产物 | run 目录独立 + registry per run |
| 文档再次漂移 | 实现改了，规范没跟上 | 把文档联动列入实现 gate 与 task report |

---

## 十五、结论

本设计的最终落点是：

1. 用 **`runtime_session_id`** 统一所有 session 私有态
2. 用 **`workflow_instance_id` / `prism_run_id`** 统一所有 run 共享态
3. 用 **session 私域 → run 发布层 → project 真相层** 重构通信边界
4. 用 **新写旧读 + 删除门禁** 实现兼容迁移
5. 用 **并发矩阵** 而不是单会话 smoke 作为交付标准

这不是对某几个 hook 的补丁，而是 RedCap 运行时状态模型的一次系统性升级。
