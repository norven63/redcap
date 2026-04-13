# RedCap 会话隔离与连续性说明

> **定位**：这是一篇面向人读的解释文档，用来回答“RedCap 的会话隔离到底怎么做”“哪些状态该共享、哪些状态必须私有”“哪些设计已经落地、哪些是刻意不自动化”。
>
> **关联文档**
> - 架构总纲：`ARCHITECTURE.md`
> - 设计底稿：`compass/docs/specs/multi-session-isolation-design.md`
> - docs 治理索引：`compass/docs/index.yaml`

---

## 一、先回答最容易混淆的两个点

### 1. `.dev-task.md` 是 canonical truth，不是 session-owned file

`.dev-task.md` 的职责是：为**当前 worktree 中正在推进的 Layer B 主任务**提供唯一真相源。  
所以它回答的是：

- 当前任务是什么；
- 当前 tranche / active slice 是什么；
- 用户原始输入和已确认需求是什么；
- 允许修改范围是什么。

它**不回答**：

- 这是哪一个宿主会话写出来的；
- 现在是谁“拥有”它；
- 哪个 session 应该覆盖哪个 session。

换句话说，**`.dev-task.md` 是 task-scoped canonical ledger，不是 session-scoped 私有文件**。

这意味着：

1. **同一个 worktree** 下，多个会话看到的是同一份 `.dev-task.md`。  
2. 当前会话不会试图判断“.dev-task.md 是不是我创建的”，因为这不是它的职责。  
3. 当前会话真正要判断的是：**“我和这份 canonical task metadata 是否兼容，我有没有自己的 continuity record，我是不是应该导入别的会话资产。”**

### 2. 会话隔离不是“把一切都按 session 建目录”

“文件夹隔离”这个思路本身是对的，但只适用于 **session-scoped process state**。  
它**不适合**把所有东西都 session 化。

正确分层是：

| 层 | 典型载体 | 是否按 session 隔离 | 原因 |
|---|---|---:|---|
| canonical truth | `.dev-task.md` | 否 | 这是当前任务的唯一真相源，不能每个 session 各写一份 |
| 宿主 continuity 资产 | `plan.md`、`files/`、`checkpoints/` | 是 | 这是当前宿主会话的私有连续性记录 |
| runtime 私有态 | runtime state / owner metadata / pending markers | 是 | 防止并发串号 |
| frozen evidence | `compass/docs/specs/**`、`task-reports/**` | 否 | 这是跨会话共享的正式证据 |

所以，**RedCap 的正确模型不是“全量文件夹隔离”，而是“分层隔离”**。

---

## 二、当前会话如何识别“这是我自己的连续性记录”

当前实现并不是去问“`.dev-task.md` 是谁创建的”，而是看三件事：

### 1. 当前 session folder 是否已有自己的 continuity assets

当前宿主会话目录（例如 Copilot 的 session-state 目录）下，如果已经存在：

- `files/` 中的本会话记录（排除 `imported-sessions/`）
- 或 `checkpoints/`

那么 `redcap-session-continuity.sh sync` 会把当前会话标记为：

- `continuity_state: self-recorded`

这表示：**当前会话已经有自己的连续性记录，不需要继承别人。**

### 2. 当前 session folder 是否已导入过兼容来源

如果当前目录下存在：

- `files/imported-sessions/<source_handle>/metadata.json`

那么系统会继续做 **task metadata compatibility check**：

- `task_id`
- `confirmed_hash`
- 必要时回退到 `top_goal`

只有兼容，才会标成：

- `continuity_state: imported`

如果 metadata 不兼容，只会记录：

- `stale_import_*`

而不会误判成已继承当前任务。

### 3. 当前没有 own record 时，是否存在 compatible source session

如果当前会话自己没有记录，系统会扫描同一宿主 session 根目录下的其他 `plan.md`，从它们的 canonical pointer 中比对：

- `canonical_path`
- `task_id`
- `confirmed_hash`
- `top_goal`

匹配成功时，宿主 workboard 上会出现：

- `continuity_state: import-suggested`
- `suggested_source_*`
- `next_action: bash compass/tools/redcap-session-continuity.sh import ...`

注意：**这里只是建议，不会自动 takeover。**

---

## 三、为什么当前设计没有让 `.dev-task.md` 也按 session 隔离

因为 `.dev-task.md` 是为了解决“长任务不偏航”，而不是为了解决“哪个 session 拥有哪个临时状态”。

如果把 `.dev-task.md` 改成：

- `.dev-task/<session-id>.md`
- 或每个会话一份独立 canonical

会立刻引入新的问题：

1. **同一个任务出现多个真相源**：PM Gate、允许修改范围、已确认需求可能漂移。  
2. **跨会话审计变难**：你无法一眼看出当前 worktree 的主线任务到底是哪一份。  
3. **恢复链失真**：session continuity 本来是围绕同一个 canonical task 做恢复；一旦 canonical 也 session 化，就会把“任务真相”和“会话私有态”混成一层。  

所以当前设计有意保持：

- **任务真相共享**
- **会话私有态隔离**
- **跨会话继承显式导入**

如果真的要同时并行推进**两个不同的 Layer B 主任务**，推荐做法不是在同一 worktree 里造两份 `.dev-task.md`，而是：

1. 分出独立 `git worktree` / clone；  
2. 每个 worktree 各自拥有自己的 `.dev-task.md`；  
3. 每个 worktree 内部再做 session continuity。  

这才是“任务隔离”和“会话隔离”同时成立的方式。

---

## 四、“文件夹隔离”这个思路到底落到哪里了

你的直觉是对的：**会话隔离必须有目录边界**。  
只是这个目录边界不应该覆盖 canonical truth，而应该覆盖 session-scoped continuity/process state。

当前已经落地的目录边界有两层：

### 1. 宿主 session folder

以 Copilot 当前会话为例，宿主目录本身就是：

- `/Users/norven/.copilot/session-state/<session_handle>/`

在这层里面：

- `plan.md`：宿主 workboard mirror
- `files/`：会话私有记录
- `checkpoints/`：会话级快照
- `files/imported-sessions/<source_handle>/`：显式导入资产

这已经是一种“以 session handle 为文件夹名”的隔离。

### 2. runtime binding / session identity

目录边界只解决“放哪里”，还没解决“谁有权认领这个目录”。  
所以还需要：

- `runtime_session_id`
- `session_binding_key`
- runtime capability / owner metadata（设计口径）

也就是说，**文件夹隔离负责防碰撞，binding / capability 负责防误认领。**

---

## 四点五、为什么不把多会话隔离全部塞进 RedCap 自己目录

这件事要分成两层回答：

### 1. 协议内核，本来就应该尽量由 RedCap 自己维护

真正属于 RedCap 自管理的，是这些东西：

- canonical truth（`.dev-task.md`）
- runtime identity / binding
- pending closure / closure obligation
- task metadata compatibility rule
- explicit import protocol

这些都不应该依赖某个宿主 UI 才成立。

### 2. 但 continuity surface 故意保留一部分在宿主侧

原因不是“做不到都收进 RedCap”，而是**不应该全收**：

1. **宿主 workboard 要可见**
   用户在当前宿主会话里，需要直接看到“我是不是 fresh / self-recorded / import-suggested / imported”。
   如果所有连续性状态都藏在 RedCap 私有目录里，协议更纯，但宿主可见性更差。

2. **不是所有宿主都稳定暴露原生 session id**
   有些宿主能稳定给，有些只能在启动后给，有些只能给“宿主会话目录句柄”而不是 CLI 原生 resume id。
   因此当前设计刻意区分：
   - `session_handle`：宿主/人类可见定位
   - `runtime_session_id`：RedCap runtime 私有态主键

3. **宿主路径里拿到的 handle，不等于宿主原生 sessionId**
   以 Copilot 为例，当前 session-state 目录名确实可用作 `session_handle`。
   但它**不能自动等同于** Copilot CLI 内部用于 `/resume` 的原生 sessionId。
   这也是为什么文档一直坚持把两者拆开，而不是偷懒混成一个字段。

所以更准确的说法是：

> **RedCap 应该自管协议内核，但不应把所有 continuity surface 都强行吸回自己目录。**

否则会牺牲宿主可见性，也会把“宿主可读句柄”和“runtime 私有主键”混为一谈。

### 3. 当前最合理的结构是“双层”

| 层 | 位置 | 职责 |
|---|---|---|
| **RedCap-owned core** | RedCap runtime / canonical / closure state | 维护协议真相、绑定、锁、兼容判定 |
| **Host-owned mirror** | 宿主 session folder / workboard | 让当前宿主会话看见自己的 continuity 状态与导入入口 |

这不是分裂实现，而是**同一协议的两层落点**。

---

## 五、五个关键原语分别干什么

### 1. `session_handle`

给人类看、给宿主 workboard 看、给 explicit import 定位来源会话用的**可读别名**。  
当前通常直接取宿主 session folder 名。

它的用途是：

- 告诉你“是哪个会话”
- 让导入路径可读
- 让 mirror 上的信息能对应到宿主文件夹

它**不是** CLI 原生 sessionId。

### 2. `runtime_session_id`

这是运行时真正的会话唯一标识。  
它是 session-scoped 私有状态的主键。

它的用途是：

- 标识当前 runtime 私有态属于哪个会话
- 支撑 helper / hook / pending closure 等运行时状态定位

如果宿主不给稳定 sessionId，RedCap 不能假装自己已经拿到了它；这时只能进入 degraded / mirror-only 路径。

### 3. `session_binding_key`

这是“恢复到原逻辑会话”的稳定定位键。  
它解决的是：

- 同一逻辑会话恢复后，怎么找到自己原来的 runtime 目录；
- 同一宿主多次 resume 时，怎么知道还在同一个槽位上。

它的重点是**稳定定位**，不是保密。

### 4. `task metadata`

这是判断“你能不能继承这个来源会话”的任务指纹。  
当前主要包括：

- `task_id`
- `confirmed_hash`
- `top_goal`

有了它，系统才知道：

- 这是同一个已确认任务；
- 还是只是“最近但不相关”的旧会话。

### 5. `explicit import protocol`

这是跨会话连续性桥。  
它的原则是：

1. 只建议，不自动接管；  
2. 只导入 continuity artifacts，不接管 canonical truth；  
3. 源会话保留不动；  
4. 导入资产必须带来源 metadata。  

当前导入的典型内容：

- `plan.md` 快照
- `files/`
- `checkpoints/`
- `metadata.json`

---

## 六、`continuity_state` 是怎么判定的

当前只允许以下几种状态：

| 状态 | 含义 | 触发条件 |
|---|---|---|
| `fresh-session` | 没有 own record，也没找到兼容来源 | 当前目录没有记录，且未命中 candidate |
| `self-recorded` | 当前会话已有自己的 continuity record | 当前 session folder 已存在本会话记录 |
| `import-suggested` | 当前会话没有自己的记录，但找到了 compatible source | sibling session 命中 task metadata |
| `imported` | 已显式导入兼容来源会话资产 | imported metadata 与当前 task metadata 兼容 |

因此，RedCap 判断的不是“这是不是我创建的 `.dev-task.md`”，而是：

> **当前 session 在 continuity 层处于什么状态，我应该继续自己、建议导入、还是保持 fresh。**

---

## 七、你说的“CSA 锁”，这里更准确是 CAS 风格状态比对 + task-scoped lock

你记忆里的“CSA 锁”，更准确的口径是：

- **task-scoped lock**
- 加上 **CAS（compare-and-swap）风格状态比对**

它主要保护的是 **pending closure / obligation 清理**，不是普通文件读写。

防护目标是：

1. 旧会话不能把新会话刚补录的 closure obligation 清掉；  
2. 弱 hook 宿主的 deferred reconcile 不能因为时序问题误判“已经收尾”；  
3. once-only 收尾动作不能被不同会话重复认领。  

其核心思想是：

1. 先拿 task-scoped lock；  
2. 再比较自己读到的旧状态是否仍然是当前状态（例如 `updated_at` 是否未变）；  
3. 只有“锁命中 + 状态没变”时，才允许 clear / transition。  

所以它保护的本质不是“互斥”本身，而是：

> **避免旧观察者基于过时快照去覆盖新状态。**

---

## 八、你之前提出的那些思路，哪些已经真正落地了

| 设计/判断 | 结论 | 当前状态 | 证据 |
|---|---|---|---|
| `docs/` 与 `knowledge/` 平级不同职 | 正确 | **已落地** | `ARCHITECTURE.md` §2.2.2、`compass/CONTRIBUTING.md`、`compass/docs/index.yaml` |
| specs / research / traces / task-reports 要有 retention / archive 规则 | 正确 | **已落地为 policy/index**；是否执行首次 archive 取决于体量阈值 | `compass/docs/index.yaml` |
| “追踪/记忆/防丢失”应统一看作连续性资产，但不能粗暴合并 | 正确 | **已落地** | `ARCHITECTURE.md` §2.2.2、`compass/docs/index.yaml` |
| 空目录要区分 repo 残留与 runtime empties | 正确 | **已落地** | `compass/roles/`、`loom/knowledge/` 已删；`prism/runs/**` 保留为 runtime empties |
| 当前会话有自己的记录时应继续恢复 | 方向正确 | **已落地为 continuity detection + self-recorded**；没有做“每次都 ask 用户”的强制交互 | `redcap-session-continuity.sh`、宿主 `Session Mirror` |
| 当前会话没有记录时，应该找最近兼容会话并让用户显式决定是否继承 | 方向正确 | **已落地为 import-suggested + explicit import**；没有做默认自动 takeover，这是有意设计 | `redcap-session-continuity.sh`、`compass/docs/index.yaml` |
| 所有宿主都能稳定拿到 session id 吗？ | 否 | **已文档化差异** | `loom/dispatcher/agent-adapters.md` §12.1 |

所以结论不是“你的想法只停留在讨论”，而是：

> **绝大多数已经转成技改需求并落地；少数地方没有 1:1 按原话实现，是因为我们故意把“自动接管”收紧成了“显式导入 + 保留来源 + mirror 先可见”。**

---

## 九、`git worktree` 到底解决什么，风险是什么

`git worktree` 解决的不是 session-scoped continuity，而是 **task/worktree isolation**：

- 不同主任务
- 不同 branch
- 不同未提交改动

它能防止这些东西在同一个工作树里互相污染。

### 1. 你担心的隐患是真实的

如果用户不知道自己当前在哪个 worktree，确实可能发生：

- 在 A worktree 改了代码，却以为自己还在 B
- 切回原目录后发现“刚才改动没生效”
- 误以为是 RedCap / session isolation 把改动吞了

这个风险**真实存在，而且不能忽视**。

### 2. 所以 `git worktree` 不能偷偷用

正确原则应该是：

1. **显式创建**
2. **显式命名**
3. **显式提示当前 worktree / branch**
4. **禁止在用户无感知时静默切换主工作区**

所以，`git worktree` 不是“默认后台魔法”，而应该是：

> **当用户明确要并行推进不同主任务时，才启用的任务级隔离工具。**

### 3. 它和会话隔离的边界

| 机制 | 处理对象 |
|---|---|
| 会话隔离 | 同一主任务、同一 worktree 中不同 session 的私有态 |
| `git worktree` | 不同主任务 / 不同分支 / 不同工作树 |

两者互补，但不能互相替代。

---

## 十、为什么 `compass/docs/specs/` 会出现“多会话隔离”文档

你的直觉**大体是对的**：
**归档/说明层** 和 **运行时隔离层** 是两个独立模块，不能在实现上耦合。

但这里要再补一层：

### 1. `specs/` 存放的是“冻结后的设计说明”

`compass/docs/specs/session-isolation-continuity-guide.md` 和 `multi-session-isolation-design.md` 的作用是：

- 解释系统为什么这么设计
- 作为后续审计/回归的参考
- 防止设计口径在长任务或新会话中漂移

它们**不是 runtime 组成部分**。

### 2. “多会话隔离出现在 specs”不等于“specs 参与运行”

这里的关系是：

- **运行模块**：脚本、runtime state、mirror、binding、closure lock
- **说明模块**：specs 文档，用来冻结设计口径

所以准确说法不是“specs 和隔离掺合了”，而是：

> **隔离系统作为一个能力，需要有对应的冻结设计文档；但 spec 文档本身不进入运行时控制链。**

### 3. 为什么这仍然有必要

如果没有 spec：

- 后续很容易把 `session_handle` 和原生 sessionId 混掉
- 容易把 host mirror 当 authority
- 容易把 explicit import 又做回自动 takeover

所以它不是运行依赖，而是**防设计漂移的证据层**。

---

## 十一、当前实现的边界与诚实口径

当前已经做到：

1. canonical truth 与 continuity assets 分层；  
2. 宿主会话目录上的 Session Mirror；  
3. compatible source detection；  
4. explicit import；  
5. stale import 防误判；  
6. docs / knowledge / continuity 的正式口径与 retention policy；  
7. session support matrix 文档化；  
8. 收尾摘要链与任务报告闭环。  

当前还没有宣称做到：

1. 所有宿主都能原生提供稳定 `runtime_session_id`；  
2. 同一 worktree 内多条独立 Layer B 主任务并行推进；  
3. 自动 takeover 最近会话。  

这些不是遗漏，而是当前版本**刻意不夸口**的边界。

---

## 十二、一句话总结

RedCap 的会话隔离不是“给每个 session 随便造个目录”这么简单，也不是“把 `.dev-task.md` 拆成每会话一份”。  

它真正做的是：

> **把任务真相、会话私有态、宿主镜像、历史证据分层；用 `session_handle + binding_key + task metadata + explicit import` 去做显式连续性桥；再用 task-scoped lock + CAS 风格状态比对防止旧会话误清新状态。**
