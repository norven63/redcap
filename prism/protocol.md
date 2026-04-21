# 棱镜协议（Prism Protocol）

> 棱镜分两个协议族。选对协议族，是运行成功的前提。

---

## 协议族选择

```
需要独立视角，结论不相互影响？
  ├─ YES → 独立取样协议（explore / redteam / test）
  └─ NO，需要多轮交互讨论？
        └─ YES → 议事协议（council）
```

---

## 一、独立取样协议（Independent Sampling Protocol）

> 适用模式：`explore` / `redteam` / `test`  
> 核心原则：**各 Agent 全程独立，Dispatch Firewall 在当前实现中以 prompt 级隔离 + dispatch gate 约束执行**

### Step 1 · Frame（冻结任务）

在 Dispatch 前冻结以下内容，写入运行内存（不落盘）：

```
问题陈述    ：本次分析的核心问题是什么？
禁止项      ：哪些结论/方案不在考虑范围？（对齐 PM Gate 已锁定决策）
角色分配    ：redteam 模式中，每个 Agent 分配专属对抗角色（见下方角色规范）
输出 Schema ：每个 Agent 按其角色对应 Schema 输出（redteam 用角色专属 Schema，
              其余模式用通用 Schema）
              通用 Schema（explore/test/council）：
              {
                "agent": "<model>",
                "role": "<分析视角或对抗职能>",
                "conclusion": "<核心结论，50字内>",
                "confidence": "high|medium|low",
                "blockers": ["[BLOCKING/CRITICAL/MAJOR] <问题>", ...],
                "actions": ["<行动1>", ...],
                "blind_spots": "<本视角可能遗漏的角度，无则 null>"
              }
              council 模式第 2 轮及之后，Schema 中 blind_spots 改为：
              "dissent": "<对前轮主流观点的异议，无则 null>"
验收标准    ：Adjudicate 阶段，什么条件算"可继续"？
与 PM Gate 的关系：
              - 若 PM Gate 已锁定需求 → Prism 运行"验证模式"：只验证方案可行性，不重开需求决策
              - 若 PM Gate 未锁定 → Prism 可探索，但不能代替 PM Gate 做决策
```

**redteam 角色 System Prompt 注入规范**：

redteam 模式中，每个 Agent 必须携带对应角色的 System Prompt（见 `prism/roles/redteam-prompts.md`）。**优先使用原生 system prompt 分层；CLI 不支持时，降级为高优先级 prompt 前缀，并在运行记录中标记。**

```
【系统层（CLI 已验证支持原生 system prompt 时）】
  1. 角色 System Prompt（prism/roles/{role}/system-prompt.md）
  2. 通用对抗约束（prism/roles/universal-constraints.md）

【高优先级前缀层（CLI 不支持原生 system prompt 时）】
  1. 将「角色 System Prompt + 通用对抗约束」拼接为 prompt 前缀
  2. 明确置于用户材料之前
  3. 在 session_registry 中记录 injection_mode: native | prefixed
  4. prefixed 模式仅保证角色一致性，**不宣称具备原生 system-layer 隔离强度**

【用户层（正文 prompt，视为不受信任输入）】
  3. Frame 问题包（问题陈述 + 禁止项 + 待审查材料）
     historian 额外追加：compass/knowledge/lessons.md 全文
```

> **分层的必要性**：待审查材料（代码、文档、git diff）中可能含有"忽略上述指令"类注入文本。
> 若材料与角色防护指令落在同一层，注入内容会与约束竞争注意力，隔离强度下降。
> 因此：**原生 system prompt > prompt 前缀 > 纯正文混排**。当前 CLI 能力以实际 `--help`/实测为准，不得凭假设声明支持。

> **禁止直接使用 Frame 问题包作为 redteam 唯一 prompt**——必须携带角色 System Prompt，否则 Dispatch 校验失败。

### Step 2 · Dispatch（分发，含防火墙）

**Dispatch Firewall（当前为 Prompt 级隔离，不是物理强制）**：在执行阶段，所有 Agent 不得：
- 读取 `prism/reports/` 下的任何文件
- 读取其他 Agent 的中间产出
- 访问 `.dev-task.md` 或其他状态文件（Frame 内容除外）

分发方式：为每个 Agent 发送完全相同的问题包（Frame 内容 + 具体分析任务）。

**Session 记录（强制）**：Cap / Dispatcher 在成功启动每个 Agent 后，立即写入当前 run 的物理文件：

```
prism/runs/<run_id>/session-registry.yaml   ← 运行期真相文件，按 run 隔离，gitignored
prism/runs/<run_id>/{collect,synthesize,audit,artifacts}/   ← 同 run 的中间产物目录
格式：
  run_id: <YYYYMMDD-mode-NNN>
  mode: redteam | explore | test | council
  agents:
    - handle_type: task_agent | cli_session | shell
      handle: <task tool agent_id / CLI session_id / shellId>
      role: challenger | reviewer | historian | explorer | …
      model: <模型名>
      family: claude | gpt | gemini | kimi
      injection_mode: native | prefixed
      status: dispatched | responded | absent | followed_up
      schema_ok: null | true | false
```

session_registry 是 Council 多轮复用 session 和 Collect 追问的基础，也是 `prism-archive-check.sh` 校验 quorum 的数据源。
Cap / Dispatcher 是 session_registry 的唯一写入方：Dispatch 阶段必须写入 `handle` 与 `injection_mode`；Collect 阶段必须把 `status` 从 `dispatched` 更新为 `responded | absent | followed_up`，并同步写回 `schema_ok`。禁止以默认值冒充已收集状态。

### `prism/runs`、报告归档与物理清理的边界

- `prism/runs/<run_id>/...` 是 **run-scoped 本地运行证据**：它服务于当前 run 的 collect / synthesize / audit 过程，默认 gitignored。
- `prism/reports/*.md` 与 `prism/reports/index.yaml` 是 **repo-tracked 归档证据**：只有报告写成、索引登记、archive-check 通过后，才算 formal Prism 被正式归档。
- `prism/reports/index.yaml` 中 `archived: true` 的条目才可当作 **replay-auditable formal baseline**；`archived: false` 只代表索引里存在历史记录，不能拿来冒充可重放的 formal 基线。
- `prism/runs` 的目录数量、残留数量，**不等于** formal Prism 成功次数，也不等于当前任务已经用过 formal quorum。
- 物理清理 `prism/runs` 是独立动作，不等于“报告已归档”；清理前必须先明确哪些运行证据仍需保留，并获得用户显式批准。
- 默认治理目标是：**禁止 bulk-read `prism/runs`，优先保持 run registry / report archive 口径诚实**；不是为了表面干净去删除本地证据。

### `prism/runs` 生命周期分类（机器可判定）

`prism/runs` 的物理清理不能靠目录名猜测，必须先通过 `prism/tools/prism-runs-lifecycle.sh` 做分类：

| lifecycle class | 含义 | 默认保留策略 | 是否允许纳入自动清理安全集 |
|---|---|---|---|
| `acceptance-fixture` | acceptance / regression 过程中生成的本地夹具运行证据（如 `acceptance-prism-*`） | `ephemeral-local` | ✅ 允许；但仅限非 active、未被报告绑定的 acceptance 目录 |
| `formal-run` | 以 `YYYYMMDD-*` 命名、用于 formal Prism 的 run-scoped 证据 | `preserve` | ❌ 默认不自动删 |
| `named-local-evidence` | `debug-run` / `council-*` / `review-*` / `safe-default` 这类命名运行证据 | `preserve` | ❌ 默认不自动删 |
| `infra-locks` | `.locks` 等内部锁目录 | `preserve` | ❌ 默认不自动删 |

执行入口：

```bash
bash prism/tools/prism-runs-lifecycle.sh summary
bash prism/tools/prism-runs-lifecycle.sh check
bash prism/tools/prism-runs-lifecycle.sh prune-acceptance        # dry-run
bash prism/tools/prism-runs-lifecycle.sh prune-acceptance --apply
```

规则：
- `prune-acceptance --apply` 只允许删除 `cleanup_eligible=true` 的 `acceptance-fixture`
- 命名运行、formal run、本轮 active run 与 `.locks` 必须 preserve-by-default
- 若当前任务只批准“降 token / 清 acceptance 残留”，不得顺手扩展到命名 run 或 formal run

若进入 council Round 2+，同一 role 只能复用原条目继续推进：
- 只有显式标记为后续轮次（`round > 1`）时，才允许 `responded -> followed_up`
- 只有显式标记为后续轮次（`round > 1`）且续接失败时，才允许 `responded|followed_up -> absent`
- 禁止为同一 role 另起新条目或偷换 handle
run 目录与 registry path 的创建/解析统一由 `prism/tools/prism-run-state.sh` 负责；worker 只写自己的产物，由 coordinator 回填 session_registry。

**Dispatch 前置校验（必须通过才能继续）**：

```bash
bash prism/tools/prism-dispatch-check.sh \
  --mode <模式> \
  --agents "model1:role1,model2:role2,..." \
  [--problem <问题包文件>]
# 退出码 1 = 校验失败，Dispatch 中止
```

Agent 数量：
- explore：3~5 个，≥2 家族
- redteam：4~6 个，**≥3 家族，必须含挑战者/审查员/旧错者；第 4 席优先 explorer**
- test：2~4 个，按评分维度分工

**Codex 进程限定规则**：
- 当当前宿主是 Codex，或 Prism/RedCap 准备调起 `codex` CLI 作为棱镜参与者、reviewer、synthesis audit 时，RedCap 控制面默认最多允许 **2 个 Codex-family 执行进程**同时存在；当前宿主 Agent 计为 1，因此默认只剩 1 个额外 Codex 子进程名额。
- 该限制只约束 RedCap / Prism 机制主动启动的 `codex` CLI 或 Codex-family 子 Agent，不限制当前宿主 Agent 自身在“不降低任务质量”的前提下做必要上下文管理。
- 若任务质量确实需要超过该限制，必须先向 Norven 明确说明原因、预计收益、token / 限流风险，并获得显式授权后再放宽。
- Prism 分发前若候选 roster 会超过该限制，优先选择非 Codex 家族的健康 CLI 补足多样性；若无法补足 quorum，应中止本次 Prism 运行并记录为资源不足，而不是偷偷并发更多 Codex 进程。

**GPT 系模型特别处理**：发送问题包前检查长度，超过 800 行的材料必须分段发送（GPT 系模型会静默截断大文件而不报错，见 lessons.md L-11）。

可用模型阵容见 `roles/README.md`。

### Step 3 · Collect（收集，含超时治理与追问）

```
超时限制：单个 Agent 超过 30min 无响应 → 进入追问流程（见下）
法定人数（quorum）：≥60% Agent 完成（含重试），否则中止本次运行，记录原因
收集完成：所有 Agent 均提交符合 Schema 的结果（ABSENT 视为弃权）
```

**Schema 完整性追问（强制，优先于标记 ABSENT）**：

Agent 响应后，检查输出是否符合 Frame 锁定的 Schema。若不符合或关键字段缺失：

```
Collect 解析顺序：
  0. 先做高容错提取：允许 JSON 外层存在 code fence、hook 噪音、前言/尾注；只要能稳定提取出完整 JSON 载荷，就先按 schema 校验
  1. 仅当无法提取合法 JSON，或 JSON 缺少关键字段时，才进入追问流程

追问流程：
  1. 若当前 backend 支持多轮追问（定义：当前 run 已保留可复用 handle，且适配层已实现该 backend 的续接/追问模板）：
      发送追问：
      "你的输出缺少以下字段：{缺失字段列表}。请按 Schema 补全后重新提交。"
  2. 追问最多 2 次
  3. 若 backend 仅“理论支持 session 续接”，但本轮未保留可复用 handle / 无续接模板 → 视为不支持追问，直接标记 status=absent，并记录 backend limitation
  4. 2 次追问后仍不合格 → 标记 status=absent，记录原因
  5. 超时（30min 无响应）→ 先追问 1 次，再超时 → status=absent
```

Collect 落盘约束：
- 最终记为 `responded` / `followed_up` 时，必须保留可复核的 `parsed.json`
- `raw.txt` 可选，但 collect 目录重试时必须整体替换，不能残留旧证据文件

**追问禁止项**：追问只能要求 Agent 补全 Schema 格式，不得：
- 透露其他 Agent 的输出内容
- 引导 Agent 修改已有结论
- 给出"正确答案"暗示

### Step 4 · Synthesize（提炼）

从各 Agent 的 Schema 输出中提炼：
- **共识行动**：≥N_consensus Agent 支持的行动项（见下方离散映射表）
- **弱共识**：≥N_weak 但 <N_consensus 支持，附少数意见
- **开放争议**：<N_weak 支持，双方论点均列出
- **ABSENT 说明**：记录哪个模型缺席及原因

**离散共识映射表**（按参与人数）：

| 参与 Agent 数 | N_consensus（共识） | N_weak（弱共识） | N_quorum（法定最低） |
|-------------|-------------------|----------------|-------------------|
| 3 | 3/3 | 2/3 | 2 |
| 4 | 3/4 | 2/4 | 3 |
| 5 | 4/5 | 3/5 | 3 |
| 6 | 5/6 | 4/6 | 4 |

**Quorum 分母定义**：Frame 阶段锁定的原始 Agent 数（含 ABSENT），不是实际响应数。3人组中1人ABSENT = 2/3响应 = quorum不达标，运行无效。

**跨角色 Finding 去重规则（必须在 Synthesize 前执行）**：

多个角色可能对同一问题产生语义重复的 finding。**关键区分**：「去重」的目的是合并重复条目，让列表清晰；但「支持人数」必须保留——2 个角色独立报出同一问题，投票权应为 2 票，不是 1 票。

去重步骤：
```
1. 收集所有角色输出的 findings（按 finding.id 区分）
2. 对每对 finding (A, B)，判断是否语义等价：
   - 相同判定标准：指向同一文件/函数/协议步骤 AND 问题核心描述一致（措辞不同不影响）
   - 不同判定标准：涉及不同文件 OR 同文件但根因不同（如 A 报 schema 缺字段，B 报 check 逻辑遗漏）

3. 若语义等价：
   a. 合并为单条 finding，保留最高 severity
   b. 在 finding 中记录：
      - [CROSS-VALIDATED by {role1}+{role2}] 附注到 area 字段
      - supporting_roles: [{role1}, {role2}]   ← 报出该 finding 的所有角色
      - validator_count: 2                      ← 独立报出的角色数
   c. ⚠ 共识人数计票时，票数 = validator_count（不是"1条finding=1票"）
      示例：3人组(N_weak=2)中，角色A和B均报出 finding X → 合并后 validator_count=2 → 仍算 2 票 → 达到弱共识

4. 若同一 finding 的 validator_count ≥3：
   - 标注为 [MULTI-VALIDATED]，在 Synthesize 摘要中优先展示
   - **仍须参与正常 Adjudicate 投票流程，不绕过共识门槛**
   - 视为"强信号/优先审议"，而非"已通过授权的行动项"

5. 去重后，在 Synthesize 摘要中注明：
   "已去重：X 条 finding（validator_count 合计 Y），其中跨角色验证 Z 条，单一角色发现 W 条"
```

**反模式警告**：禁止将两个指向不同文件或不同根因的 finding"因措辞相似"而合并——这会掩盖真实覆盖面。疑似重复时宁可保留两条并标注"待人工确认是否同源"。

**Synthesis Audit（必须执行）**：
Synthesize 完成后，启动 1 个独立 Agent（与参与 Dispatch 的 Agent 不同实例）做"摘要忠实度审计"：
```
审计任务：对比各 Agent 原始输出 vs Cap 的 Synthesize 摘要
检查项：
  ① 是否有结论被错误归类（如将 MAJOR 降级为 MEDIUM）
  ② 共识人数是否与原始输出一致
  ③ 是否有 BLOCKING 项被遗漏
  ④ 少数意见是否被合理保留
  ⑤ 去重规则是否正确执行（[CROSS-VALIDATED] 标注是否准确，有无不同根因的 finding 被错误合并）
输出：AUDIT_PASS（可进入 Adjudicate）或 AUDIT_FAIL + 具体偏差列表
```
AUDIT_FAIL 时必须修正 Synthesize 结果再重新审计，不得跳过进入 Adjudicate。

### Step 5 · Adjudicate（裁决）

```
consensus     ：共识行动 ≥1 条，无阻塞项 → 可继续执行
weak-consensus：有弱共识但无严重阻塞 → 可继续，标注风险
deadlock      ：核心议题无共识（<N_weak）→ 【硬终态】
escalate      ：发现 PM Gate 已锁定需求的边界问题 → 【硬终态】
```

**deadlock/escalate 硬终态规则**：
- 进入后系统只允许：Archive（写入 OPEN_QUESTION 清单）+ 等待 Norven 确认
- **必须收到 Norven 明确的「解锁确认」后，才能继续后续执行**
- 禁止：继续 Dispatch 新一轮、进入实现阶段、更新 lessons.md 结论
- 解锁方式：Norven 在对话中明确回复"确认继续"或提供决策方向

**Adjudicate 权威规则**：Prism 无权推翻已 PM Gate 锁定的决策。若 Prism 结论与锁定需求冲突，结论 = escalate，不是 override。

### Step 6 · Archive（归档）

```
1. 写入运行报告：
   prism/reports/YYYYMMDD-{mode}-NNN.md
   （NNN 为当天流水号，从 001 起）
   报告头部必须显式记录 `run_id`，用于将报告与 `prism/runs/<run_id>/session-registry.yaml` 绑定

2. 更新索引：
   prism/reports/index.yaml
   （格式见下方 Index Schema）

3. 若 Adjudicate = consensus 或 weak-consensus，且产出可被后续决策引用：
   将核心结论（1~3 条）沉淀至 compass/knowledge/lessons.md
   （理由：复活协议必读 lessons.md，这是棱镜结论进入"长期记忆"的唯一通道）

4. Archive 校验（必须通过才能 commit）：
   bash prism/tools/prism-archive-check.sh --report prism/reports/<报告文件>
   # 退出码 1 = 校验失败，禁止 commit
   # 必须实际读取 prism/runs/<report_run_id>/session-registry.yaml，验证：
   #   - 原始 Agent 总数与 N_quorum
   #   - responded/followed_up 数量是否达标
   #   - 不存在 lingering dispatched 状态
   #   - responded/followed_up 项的 schema_ok=true
   #   - 每个 Agent 的 injection_mode 已记录
   # 若 run-scoped registry 尚未迁移到位，只允许在 run_id 精确匹配时走只读 legacy bridge

5. git add + commit（prism/reports/ 全部 git 追踪，作为架构演进的审计轨迹）
```

报告保留策略：
- 活跃期（90天内）：直接存放于 `reports/`
- 90天后：移至 `reports/archive/`，index.yaml 保留摘要
- 永不 gitignore：所有报告均 git 追踪
- `prism/runs/` 不在此归档策略里；它是否物理清理，由单独的本地证据保留决策决定。

---

## 二、议事协议（Council Protocol）

> 适用模式：`council`  
> 核心原则：**共享前轮摘要，多轮收敛，有终点**

### Step 1 · Frame（同上，额外冻结）

在独立取样协议的 Frame 基础上，额外冻结：
```
最大轮数：N（推荐 3 轮）
收敛阈值：≥70% 参与者同意核心行动项
议题类型：open-ended（探索）| decision（选方案）| critique（审查）
```

### Step 2 · Round 1（独立意见轮）

各 Agent **独立**提交初始观点（此轮适用 Dispatch Firewall）。
输出 Schema 同独立取样协议。

### Step 3 · Round N（讨论轮，N=2,3,...）

各 Agent 收到前一轮**所有参与者的摘要**（非原始输出，由 Cap 提炼摘要再分发），
基于此更新或维持自己的立场。

每轮结束后检查收敛：
```
if 核心行动项同意率 ≥ 70%：
    进入 Adjudicate（提前结束）
elif 当前轮数 == N：
    进入 Adjudicate（强制结束）
else：
    继续下一轮
```

### Step 4 · Adjudicate + Archive（同独立取样协议）

---

## 三、Index Schema（报告索引格式）

```yaml
# prism/reports/index.yaml
reports:
  - id: "20260407-explore-001"
    mode: explore
    date: "2026-04-07"
    topic: "棱镜 v0.1 架构设计评审"
    agents: ["claude-sonnet-4.6", "claude-haiku-4.5"]
    verdict: "weak-consensus"          # consensus | weak-consensus | deadlock | escalate
    consensus_actions:
      - "拆分两个协议族"
      - "加入 Frame + Adjudicate 步骤"
    open_questions: []                  # deadlock 时填写
    lessons_updated: true              # 是否已沉淀至 lessons.md
    files_affected: ["prism/protocol.md", "prism/modes/"]
    archived: false                    # 是否已移至 archive/
```

---

## 四、触发条件（风险信号驱动）

不按文件数量触发，按**风险信号**触发：

| 风险信号 | 触发模式 |
|---------|---------|
| 改动核心协议/状态机（CONTRIBUTING.md §1-§13、SKILL.md §5.x） | redteam |
| 改动身份资产（soul.md、identity.md）| test |
| 存在 ≥2 个互斥方案，无法独立决策 | council |
| 已有明确不确定性或反对意见 | explore |
| 跨模型/跨框架验证需求 | redteam |
| 无法在 2 轮内自行解决的卡壳 | council |

**与 §10 PM Gate 的关系**：
```
需求不清晰 → §10 PM Gate 先行（Prism 不运行）
需求已锁定 + 方案有高风险信号 → Prism 运行（验证模式）
Prism 发现需求边界问题 → escalate → 回到 §10 PM Gate 重新锁定
```

**"Norven 不在"的可观测定义**：
- `.dev-task.md` 中显式标记 `absent: true`，或
- 当前会话中 Norven 已超过 2 个来回未回应 Cap 的澄清请求

---

## 五、与 §8/§9 的关系（迁移矩阵）

| 场景 | 推荐路径 | 说明 |
|------|---------|------|
| ≥5 个独立模块快速并行分析 | §8（保留） | 速度优先，无需多模型共识 |
| 提交前简单架构检查 | §9（保留） | 轻量 pre-commit，单模型即可 |
| 核心协议设计决策 | Prism redteam | 多家族模型，有 Adjudicate |
| soul/identity 大改验证 | Prism test | 结构化评分，有失败标准 |
| 方案分歧需迭代收敛 | Prism council | 多轮议事，有收敛终点 |
| 架构探索，方向未定 | Prism explore | 开放取样，提炼共识 |

§8/§9 是轻量快速路径，Prism 是高后果决策的系统化路径。两者并存，不替代。

---

## 六、Skill-Delegation 模式（外包模式）

> **用途**：Cap 或棱镜雇佣兵需要将某子任务外包给另一个专精 skill 完成，并回收其结果。
> **前提**：外包目标 skill 有标准的 `SKILL.md` 入口文件。

### 6.1 工作流

```
Cap/雇佣兵
  │
  ├─ 1. 决定外包：子任务超出当前 skill 能力边界，或有更专精的 skill 可完成
  │
  ├─ 2. 准备外包请求文件：.workflow/skill-delegation-{task_id}.md
  │     内容：任务描述 + 输入文件路径 + 期望输出格式 + 超时上限
  │
  ├─ 3. 启动雇佣兵 Agent（headless）：
  │     gemini -p "[读取 {skill_path}/SKILL.md 并按其协议完成以下任务]..." \
  │     --tools=all --yolo
  │     （路径传入 = 加载 skill，无需 prompt 注入或任何导入机制）
  │
  ├─ 4. 等待结果：雇佣兵将输出写入 `--output-file` 指定路径（建议：`.workflow/skill-delegation-{task_id}-result.md`）
  │     调用方须在启动时显式传入 `baton-delegate.sh --output-file .workflow/skill-delegation-{task_id}-result.md`
  │     - `baton-delegate.sh` 在 `--skill-path` 模式下会强制：
  │       prompt file = `.workflow/skill-delegation-{task_id}.md`
  │       result file = `.workflow/skill-delegation-{task_id}-result.md`
  │       不满足即直接退出，不视为协议内 delegation
  │     - 成功：result 包含 "##DONE##" 标记，读取并继续
  │     - 阻塞：exit 2，blocked 文件已写入 `.workflow/blocked-{role}-{ts}.md`，走 6.2 透传流程
  │     - 超时：exit 124，降级处理（记录到 lessons，自行完成或报错升级）
  │
  └─ 5. 清理：归档 delegation 文件，更新任务进度
```

### 6.2 BLOCKED 透传协议

当雇佣兵遇到需要人工决策的阻塞点时：

1. 雇佣兵将阻塞信息写入 `.workflow/blocked-{role}-{timestamp}.md`（格式见 `loom/dispatcher/agent-adapters.md §12.3`）
2. Cap 发现 PENDING 状态的 blocked 文件 → 读取内容 → 向 Norven 透传问题
3. Norven 给出决策 → Cap 在文件中追加 `**状态**：RESOLVED\n**决策**：{决策内容}`
4. Cap 重启雇佣兵 Agent，通过 `--resume` 续接 session（参照 `loom/dispatcher/agent-adapters.md §12`），并附加决策内容作为 context

**多轮 BLOCKED 处理**：若单次任务触发 ≥3 次 BLOCKED，升级为 Prism council 模式重新评估该子任务的可行性。

### 6.3 外包请求文件格式

```markdown
# Skill Delegation: {task_id}

**发起方**：{role/Cap}
**目标 Skill**：{skill_path}（如 /Users/norven/.claude/skills/some-skill）
**任务描述**：
> {具体要完成的任务，1-3句话}

**输入**：
- {文件路径或内容描述}

**期望输出**：
- 格式：{markdown / yaml / json / ...}
- 写入路径：`.workflow/skill-delegation-{task_id}-result.md`
- 完成信号：`##DONE##` 写在文件末尾

> ⚠️ **治理边界**：直接调用宿主 skill 而不经过上述 request/result 文件边界，不属于 RedCap 协议内 Skill-Delegation，只能算宿主侧能力使用，不能回写成 RedCap-native authority。

**超时**：{N} 分钟（超时后 Cap 自行降级处理）
**状态**：PENDING / IN_PROGRESS / DONE / BLOCKED / TIMEOUT
```
