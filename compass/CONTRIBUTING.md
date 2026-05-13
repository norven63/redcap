# RedCap 自身开发规范

> 本文件约束 **RedCap 框架自身** 的变更流程。项目 Agent 在开发用户项目时遵守的规范见 `references/` 目录。

---

## 1. 变更前：经验回顾

修改框架文件前，**必须先按需检查以下入口**，不得为了“完整复活”默认全文读取大文件：

1. **`compass/knowledge/design-principles.md`**（元原则）— 确认本次变更不违背 P-1 至 P-5 五项战略层原则
2. **`compass/knowledge/index.md` → `compass/knowledge/lessons.md` 热点主题速览 → 精确 L-编号**（经验库）— 先用 knowledge index 与热点簇定位，再打开相关 lessons；不要默认全文读 lessons
3. **`rg -n "^## |^### " compass/CONTRIBUTING.md`** — 先定位本次变更涉及的规范章节，再按精确行段读取

重点关注：
- L-4（Fallback 深度不足）：修改路由/降级逻辑时
- L-7（gemini headless 挂起）：修改 Agent 适配器时
- L-8（先测再改）：涉及 Agent 调用方式变更时，必须先实测再改文档
- L-16（设计≠部署≠生效）：修改 Hook 配置或 Dispatcher 路由时，必须端到端验证
- L-17（Agent 信息茧房）：编写提示词时，确保关键资产文件有显式引用路径
- L-18（A2A 讨论优于指令）：Agent 间协作采用讨论共识模式，而非单向命令模式
- L-24（前置对抗缺失）：设计方案中出现"不可行"判断时，必须执行 §1.1 Pre-mortem 挑战
- L-25（E2E 后置处理不可省略）：E2E 完成后必须执行 `bash loom/loom/tools/redcap-e2e-postcheck.sh`，不可凭记忆
- L-26（E2E 预设必须锁定）：E2E 启动时必须创建 `loom/test-reports/e2e-session.yaml` 锁定用户指定的预设和开关

若一次变更同时命中多类经验，不要从上到下扫完整个 `lessons.md`；先按“收尾 / 账面一致性”“宿主 / Hook / runtime 边界”“docs / knowledge / token 风险”“评审 / 执行保障”这四个热点主题缩到正确簇，再精读对应 L-编号。

### 1.1 设计自检：前置对抗（Red Team Self-Check）

> **触发时机**：设计方案成型、准备动手实现之前。
> **问题根因**：Layer B 无多角色制衡，Cap 独自设计容易产生"浅层判断即收手"的偷懒倾向（L-24）。

#### 第一层：自检（成本低，每次执行）

对设计方案中的**每一条"不可行/无法做到/暂不实现"的判断**，执行以下 Pre-mortem 挑战：

```
对每条"不可行"判断：
  1. 假设这个判断是错的 — 尝试找到至少一种实现方式
  2. 如果找到 → 评估成本，决定是否纳入
  3. 如果确实找不到 → 记录尝试过的方案，标注为"已验证的不可行"
  4. 禁止出现无尝试记录的"不可行"结论
```

对设计方案中的**覆盖范围声明**（如"覆盖 X 个功能点"），执行完备性挑战：

```
  1. 列出完整的功能点全集（从权威来源获取，如状态机所有路径）
  2. 逐项标记：已覆盖 / 未覆盖
  3. 对每个"未覆盖"项执行上述 Pre-mortem
```

#### 第二层：独立 Agent 红队审查（对抗力强，选择性执行）

> 自检是同一大脑挑战自己——先天偏盲。独立 Agent 审查复用 L-15 模式（新 Agent = 新认知、无历史上下文污染）。

**触发条件**（满足任一即触发）：
- 设计中包含 ≥2 条"不可行/暂不实现"的判断
- 设计涉及覆盖范围声明（如测试覆盖矩阵、功能点清单）
- 设计方案影响 ≥3 个框架文件

**Agent 选择**：复用 `agent-adapters.md §1.3` 动态路由算法，但角色设为 `reviewer`（天然获得 cross-family +2 加分），确保选出的 Agent 与当前设计者不同模型族。降级逻辑同 §6（Model 降级 §6.3 → CLI 降级 → 用户决策 §6.5）。

> 简化版选择流程（Cap 在 Layer B 无完整 Dispatcher 环境时）：
> 1. 读 `compass/.workflow/agent-registry.yaml` 获取可用 Agent 列表
> 2. 排除与自身同 family 的 Agent（如当前是 claude 族，排除所有 claude 系 CLI）
> 3. 从剩余中选 `reasoning` 评分最高者（红队审查的核心能力需求）
> 4. 若无跨族可用 Agent → 降级为同族不同 Model；仍无 → 记录"红队审查跳过（无可用 Agent）"并继续

**执行方式**：将设计方案写入临时文件，调用选定 Agent 执行红队审查：

```bash
# 1. 将设计方案写入临时文件
cat > /tmp/redcap-design-review.md << 'EOF'
## 待审查设计方案
{设计方案全文}

## 自检记录
{第一层自检结果，含"不可行"判断和尝试记录}
EOF

# 2. 调用独立 Agent 红队审查（由上述选择流程确定具体 CLI）
# 示例：若选中 kimi → kimi -p；若选中 gemini → gemini -p --yolo（L-7）
{selected_cli} -p "你是 RedCap 框架的独立红队审查员（Red Team Reviewer）。
你的唯一目标是找出设计方案中的缺陷、遗漏和错误假设。

审查要求：
1. 对每条'不可行/无法做到'的判断：尝试提出至少一种实现方式来反驳
2. 对覆盖范围声明：检查是否遗漏了功能点（参考 loom/dispatcher/state-machine.md 的完整状态列表）
3. 对设计假设：指出哪些假设可能在实际运行中不成立
4. 对成本评估：质疑是否低估了某些方案的可行性或高估了成本

输出格式：
- CHALLENGE: {对某条结论的挑战} — {你的反驳理由和替代方案}
- MISS: {设计遗漏的功能点或路径}
- RISK: {可能在运行时出问题的假设}
- PASS: 无问题的部分（简要列出即可，重点放在挑战上）

$(cat /tmp/redcap-design-review.md)"
```

> 各 CLI 的 headless 调用参数参见 `agent-adapters.md §2-§5`（含 L-7 等已知陷阱）。

**结果处理**：
- 有 CHALLENGE/MISS → 评估并决定是否修改设计，记录决策理由
- 有 RISK → 记录到设计文档的"已知风险"段落
- 全部 PASS → 直接进入实现

> ⚠ 红队 Agent 的审查结论不是命令——设计者（Cap）仍然是最终决策者。但每个被驳回的挑战必须记录驳回理由，防止"听了但没改"的黑洞。

> 这不是形式主义——L-24 的教训是：5 条"无法覆盖"中 3 条一经追问就发现完全可做。Pre-mortem 的成本（多想 5 分钟 + Agent 调用 2-3 分钟）远低于遗漏被用户发现后的修复成本。

## 2. Commit 规范

采用中文 Conventional Commit 格式：

```
type(scope): 简要描述

正文（可选，说明动机和关键变更）
```

**type 取值**：

| type | 用途 |
|------|------|
| `feat` | 新功能、新机制 |
| `fix` | 缺陷修复、行为修正 |
| `refactor` | 重构（不改变外部行为） |
| `docs` | 仅文档变更 |
| `chore` | 构建、工具、配置等杂务 |

**scope 取值**（框架自身常用）：

| scope | 对应目录/文件 |
|-------|-------------|
| `框架` | SKILL.md 核心流程 |
| `状态机` | loom/dispatcher/state-machine.md |
| `适配器` | loom/dispatcher/agent-adapters.md |
| `模板` | dispatcher/prompt-templates/ |
| `角色` | roles/ 下的角色手册 |
| `规范` | references/ 下的规范文件 |
| `feishu` | compass/tools/feishu-notifier.py + 相关配置 |
| `经验` | compass/knowledge/lessons.md |
| `铁律` | 涉及安全铁律的变更 |

**示例**：
```
feat(feishu): 前台阻塞模式+中断恢复
fix(框架): 修正Git规范 — commit由Dispatcher执行
refactor(状态机): PAUSED 伪代码更新为前台阻塞
docs(经验): 新增 L-9 飞书架构局限性
```

## 2.1 对外术语与命名可读性（强制）

**适用范围**：对 Norven 的对话回复、`cli_console.md`、`.dev-task.md`、`plan.md`、任务报告、规范文档，以及其他面向人阅读的文本。

**不在本条直接约束内**：代码标识符、文件名、命令行原文、协议 ID、JSON/YAML 键名、用户原文与代码片段；但这些内容在被解释给 Norven 时，仍须遵守下列规则。

1. **默认中文优先**：能用中文说明的内容，不得只抛英文术语。
2. **必要英文首现释义**：确需保留英文原文时，首次出现必须写成 `英文原文（中文解释）`。
3. **新增命名必须短且直观**：标题、阶段名、结论标签、治理项命名应让读者不依赖英语背景也能大致看出设计意图；禁止把多个英文术语直接拼接成面向人阅读的名字。
4. **原文保真例外**：命令、路径、脚本名、字段名、代码片段、用户原文按原样保留，不做强行翻译。
5. **同文一致**：同一文档或同一轮汇报中，术语中文名与括注口径必须保持一致，避免前后漂移。
6. **不可用“便于和代码对齐”逃避可读性**：面对 Norven 的文本必须先满足可读，再谈和实现细节对齐。
7. **优先“说人话”**：如果一句话只有在熟悉 RedCap 内部黑话、缩写或阶段命名的前提下才能读懂，就视为不合格；必须改写成普通读者也能直接理解的表达。
8. **未约定术语先解释**：凡是此前未与 Norven 明确约定过的内部术语、链路名、缩写、阶段名、治理项名，首次出现必须补“它在仓库里对应哪个文件/功能、做了什么、为什么重要”的解释；不能把解释留到对方追问后再补。
9. **状态汇报先给“四句先看懂”**：当 Norven 主动追问进展、要求阶段汇报、或任务最终收尾时，开头应优先给出 `当前已完成 / 上一步完成的是 / 下一步计划做的是 / 整体计划脉络图与当前位置` 四段摘要，再补详细展开。
10. **汇报要有结论和段落感**：阶段汇报、最终汇报、飞书节点通知和任务报告开头都要优先讲人能直接判断的结论：本次要解决什么问题、采用了什么解法、解决后的效果如何、下一步是什么、是否还需要 Norven 协助。若任务本身不适合这些维度，可按实际情况表达，但不得刻意堆砌“新增文件/修改脚本/移动到某处/跑了某命令”这类工程流水账来冒充完成说明；工程细节可以放在报告后半部分或验证表里。
11. **`cli_console.md` 只允许做覆盖式镜像**：它不是第二份答案，也不是历史日志；如需镜像长回复，必须保持与最终回复一致，并使用覆盖写入而不是追加堆积。当前可用 `compass/tools/redcap-cli-console-mirror.sh` 统一处理本地镜像。

**执行口径**：本条分两层执行。第一层是正式落盘产物：`compass/docs/task-reports/*.md` 已由 `redcap-task-report-check.sh` 调用 `redcap-human-output-quality-check.sh` 做结构化质量审计，检查“四句先看懂”、术语对照、完成等级与 receipt 证据是否自洽。第二层是即时对话、命令输出、代码片段等宿主实时回复：当前仍不新增全局正则拦截，避免误伤路径、键名与代码；这部分必须在最终 review / 棱镜验收 / 任务复盘中审查，并诚实标为 host-limited。

## 3. 变更后：经验沉淀检查

每轮变更完成后，执行以下自检（同 `compass/knowledge/lessons.md` 中的归档触发检查点）：

1. 本轮是否发现了**新的失败模式或反直觉行为**？→ 归档为 Lesson
2. 本轮是否验证了一个**之前文档中写错的假设**？→ 归档为 Lesson
3. 本轮使用的**工作方法本身**是否值得复用？→ 归档为方法论 Lesson

## 3.1 E2E 验证：触发条件与最小产出物

### E2E 启动配置锁定（强制）

E2E 启动时，Dispatcher **必须**先创建 `loom/test-reports/e2e-session.yaml` 锁定本次配置，否则不得开始执行：

```yaml
# loom/test-reports/e2e-session.yaml — E2E 启动时创建，全部完成后删除
created_at: "2026-04-07T21:00:00Z"
preset: full                          # 用户指定的预设
switches_on: [happy_path, multi_step, qa_fail_code, ...]  # 展开后的全部开关
switches_completed: []                # 每验证完一个开关追加
user_instruction: "全量回归"          # 用户原话，防止漂移
```

每个开关对应的路径执行完毕后，**立即**将该开关追加到 `switches_completed`。此文件是防止"目的漂移"（L-21）和"部分执行当全量"（L-25）的物理屏障。

推荐直接使用 repo-owned helper 维护它，而不是手工改 YAML：

```bash
bash loom/tools/redcap-e2e-session.sh start --preset full --instruction "执行完整用户项目 E2E"
bash loom/tools/redcap-e2e-session.sh mark happy_path
bash loom/tools/redcap-e2e-session.sh status
```

**触发条件**——以下任一情况满足时，必须在真实项目中做端到端验证：

| 变更类型 | 示例 | 为什么需要 E2E |
|---------|------|---------------|
| 状态机转移逻辑变更 | 新增/修改状态、转移条件 | 静态审查无法验证运行时行为 |
| 通信协议变更 | `__redcap_status` 传递方式、JSON Schema | Agent 是否遵从只有实测才知道（L-23） |
| Prompt 模板结构性改动 | 新增变量、改变角色指令格式 | Agent 对 Prompt 变化的响应不可预测 |
| Agent 适配器/路由逻辑变更 | CLI 参数、降级策略 | CLI 行为只有调用才确定（L-8） |

单纯的文档措辞修正、经验沉淀、注释更新等不需要 E2E。

**变更登记（强制）**——commit 命中上表任一触发类型时，**必须**在 `loom/test-reports/pending-validations.md` 追加一条 V-编号条目，格式见该文件头部说明。这是防止"待验证黑洞"的核心机制——不登记就会遗忘。

> ⚠ Stop Hook 评审（§4）会检查：本次 commit 是否涉及触发类型但未登记 pending-validation。

**最小产出物**——E2E 不要求写完整报告，但必须产出以下内容并融入框架：

1. **经验条目**（L-编号）：每个新发现的失败模式/反直觉行为 → 沉淀到 `compass/knowledge/lessons.md`
2. **Bug 修复**：发现的问题当场修复并 commit
3. **E2E 报告更新**：更新 `loom/test-reports/latest-e2e-report.md`（覆盖范围、核心发现、遗留问题）
4. **消费 pending-validations**：验证通过的条目标记 ✅ 并移入归档区
5. **一句话结论**：在 commit message 正文中记录 E2E 范围和核心结论（如 "E2E(trpg-web): 5 步正向流转 100%，回退路径 0%"）

> E2E 执行使用 `loom/test-reports/benchmark-scenario.md` 定义的固定场景，保证跨版本可比性；若需要 repo-owned 基准用户项目载体，先运行 `bash loom/tools/redcap-e2e-benchmark-carrier.sh init <dest-dir>`，不得再把“没有真实用户项目”当作长期挂起 V-2 / V-3 / V-4 / V-6 / V-7 / V-8 / V-9 的默认借口。

### E2E 后置处理流程

E2E 验证产生原始发现后，按以下流程处理：

```
E2E 执行完毕
    │
    ▼
① 提取问题清单
    从 E2E 过程中收集所有发现（失败、异常、反直觉行为）
    每条记录：现象、根因分析、影响范围
    │
    ▼
② 分类定性
    每条发现标记类别：
    · BUG — 逻辑错误、功能不符合设计（必须修复）
    · GAP — 设计假设与实际不符（必须修正设计或沉淀经验）
    · OBSERVATION — 值得记录但不需立即行动（仅沉淀经验）
    │
    ▼
③ 排序
    BUG 按影响度排序：
    · P0 — 流程阻断（状态机卡死、交付物丢失）→ 立即修复
    · P1 — 功能降级（降级路径失效、通信协议部分失效）→ 本轮修复
    · P2 — 体验/效率问题 → 记录到 backlog，不阻塞本轮
    GAP 全部在本轮处理（修正设计或沉淀经验）
    │
    ▼
④ 逐项修复（BUG + GAP）
    对每个 P0/P1 BUG 和每个 GAP：
    a. 修复代码/文档
    b. 检查 §6 影响范围表 — 联动更新受影响的文件
    c. 单独 commit（commit message 标注来源，如 "fix(框架): 修复xxx — 源自 E2E(项目名)"）
    │
    ▼
⑤ 经验沉淀
    对每条发现执行 §3 的三项自检：
    · 新的失败模式？→ 新增 L-编号
    · 验证了错误假设？→ 新增 L-编号
    · 工作方法可复用？→ 新增方法论 L-编号
    已有 L-编号覆盖的发现 → 更新复现次数和最后命中日期
    │
    ▼
⑥ 回归确认
    修复涉及 §3.1 触发条件中的变更类型（状态机、通信协议、Prompt 模板、路由）？
    · 是 → 需要在同一 E2E 项目中回归验证修复效果（不必全量重跑，只验证修复点）
    · 否 → 静态审查即可
    │
    ▼
⑦ 汇总 commit
    所有修复完成后，在最后一个 commit message 中附带 E2E 汇总：
    "E2E({项目名}): {覆盖范围}, {核心结论}, BUG={P0数}P0/{P1数}P1/{P2数}P2, GAP={数量}, L-{新增编号列表}"
    │
    ▼
⑧ 完整性 Gate（强制 — 100% 硬保障）
    执行 `bash loom/loom/tools/redcap-e2e-postcheck.sh`
    此脚本检查：
    · e2e-session.yaml 中 switches_on 与 switches_completed 是否一致
    · 报告是否写入 loom/test-reports/latest-e2e-report.md（E2E 报告必须在此路径）
    · pending-validations 是否有消费动作
    · lessons.md 是否有更新
    · 最近 commit 是否包含 E2E 结论
    
    全部 PASS → 删除 e2e-session.yaml，E2E 后置处理完成
    任一 FAIL → 必须修复后重新执行，不得跳过
    
    双重保障：Stop Hook 检测到 e2e-session.yaml 存在时自动执行此脚本
```

> **防止链路断裂的关键点**：步骤④要求每个修复都检查 §6 影响范围表。这是 E2E 后置流程依赖的唯一外部机制——如果 §6 的表不完整，联动更新就会遗漏。因此每次新增框架文件时，必须同步更新 §6。

## 4. 独立架构评审（Stop Hook 自动触发）

> **本节属于 Layer B（开发 RedCap 自身）**。Layer A 的评审由状态机 `REVIEW_WORKING` 节点驱动，当 LLM 跳过 Review 直接进入 ALL_DONE 时，Layer A Stop Hook 会检测缺失并拉起新 Agent 兜底执行项目级 Review（`loom/tools/redcap-layerA-review-fallback.sh`）。两层共享同一设计模式：Hook 100% 触发 + 新 Agent 生命周期保证认知能力（详见 L-15）。

**问题**：开发 Agent 在长对话末期注意力衰减，可能遗漏规范检查、文件联动、经验沉淀等收尾动作。即使 §3 写了自检清单，长任务末期的 LLM 也可能"忘记"执行。

**解法**：Layer 0（物理 Hook）+ 全新 Agent 生命周期。

- **触发机制**：Claude Code Stop Hook → `compass/tools/redcap-on-stop-review.sh`
- **执行方式**：脚本提取 `git diff`，拉起一个全新的、无历史上下文污染的 Agent（`kimi -p` / `claude -p`）执行独立评审
- **评审维度**：Commit 规范、经验回顾、文件联动（§6 影响范围表）、内容质量、经验沉淀遗漏、设计完备性（§1.1 Pre-mortem 是否执行——含"不可行"判断和覆盖范围声明）、E2E 完整性（e2e-session.yaml 是否处理、报告路径、pending-validations 消费）、目录与生命周期边界（docs/specs/research/traces/task-reports 落点、session/local-only 产物是否误入 git）
- **结果处理**：
  - `PASS` → 静默通过
  - `FAIL`（含 P0 问题）→ 飞书告警 + 写标记文件 `/tmp/redcap-stop-review-result`
  - 评审日志始终保存到 `/tmp/redcap-stop-review-log.md`

> ⚠ Claude Code 的 Stop hook 退出码非零不会阻塞 Agent 退出。FAIL 时通过飞书告警通知用户，下次会话的 init hook 也可检查未解决的评审标记。

**宿主适配**：

| 宿主 | 触发方式 | 状态 |
|------|---------|------|
| Claude Code | `.claude/settings.json` Stop hook | ✅ 已部署 |
| Kimi CLI | `dispatcher` Stop 事件路由 | ⏳ 待适配 |
| VS Code Copilot | 无原生 Hook | ❌ 不支持 |
| Gemini CLI | `.gemini/settings.json` SessionEnd Hook | ✅ 已部署 |
| Copilot CLI | `.github/hooks/redcap-layerB.json` | ✅ 已部署 |

## 5. 飞书通知

> **本节属于 Layer B（开发 RedCap 自身）**。Layer A（RedCap 开发用户项目）的 Hook 由 SKILL.md §5.10 定义，通过 Dispatcher 状态机触发。两层架构详见 `compass/knowledge/host-reliability.md` §0。

RedCap 自身变更不走 Dispatcher 主状态机。飞书只做“节点汇报”和“需要 Norven 人工介入的中断”两类用户可见信号；宿主 SessionEnd Hook 只负责兜底审计与 blocker 告警，不应重复发送成功刷屏。

**账号与通道（强约束）**：RedCap 官方通知路径只允许 `references/feishu-notification-policy.json` 指定的 `cli_a9579f5b12219bb5` lark-cli DM profile。`webhook`、旧 profile、followup watcher、SessionEnd 默认成功通知都不是合法生产路径。策略与本地 ignored 配置由以下检查兜底：

```bash
bash compass/tools/redcap-feishu-notification-policy-check.sh
```

**回复入口（允许，但只进收件箱）**：普通飞书回复可以由 `pending-scan` 收入 RedCap 收件箱；它只是“收到一条可能需要合并到任务树的用户消息”，不是远程命令通道。任何“继续、纠错、新需求、重新评审”等回复，都必须先进入中插需求、人工决策或当前任务合并流程，再经过任务账本与 closeout；不得因为飞书里出现一句话就直接执行。

```bash
bash compass/tools/redcap-feishu-inbox.sh check
bash compass/tools/redcap-feishu-inbox.sh summary --human
```

**节点汇报（允许，低频）**：每轮真正完成 closeout 节点时，统一通过 on-complete 发送一次 `node-report`；不要在每个内部小状态都发飞书。

```bash
python3 compass/tools/feishu-notifier.py notify "RedCap 节点汇报: <简要描述>" --project "redcap" --window-type node-report
```

**人工介入中断（允许，阻塞式）**：只有需要用户做决策、授权或解除 blocker 时，才允许发人工介入类通知：

```bash
python3 compass/tools/feishu-notifier.py ask "方案A还是方案B？" --project "redcap"
python3 compass/tools/feishu-notifier.py notify "RedCap 需要人工介入: <原因>" --project "redcap" --window-type manual-intervention
python3 compass/tools/feishu-notifier.py pending-list --limit 5
```

**重复通知治理**：`feishu-notifier.py notify` 对同一 `project + window_type + message` 默认做短窗口去重。不同内容的真实 blocker 告警不能被合并；相同内容在去重窗口内只保留第一条。


## 6. 文件变更影响范围提示

| 修改的文件 | 可能需要同步更新的文件 |
|-----------|---------------------|
| SKILL.md §5.2 事件循环 | loom/dispatcher/state-machine.md 伪代码 |
| SKILL.md §5.10 Hooks | loom/dispatcher/state-machine.md 对应触发点 |
| references/communication-protocol.md | roles/ 下各角色手册中的状态返回说明 + compass/knowledge/a2a-communication.md §5.4 |
| loom/dispatcher/agent-adapters.md | SKILL.md §5.5 路由表 + compass/knowledge/a2a-communication.md §2 |
| loom/dispatcher/state-machine.md 状态枚举 | compass/knowledge/a2a-communication.md §4（NEGOTIATING 状态同步） |
| SKILL.md §5.10 Hooks 表 | loom/dispatcher/state-machine.md `populate_pending_actions` + SKILL.md §5.13 映射表 |
| CONTRIBUTING.md 自身 | `compass/CONTRIBUTING.core.md` + .github/copilot-instructions.md + CLAUDE.md + GEMINI.md（`AGENTS.md` 仅作本地 Codex carrier，不再视为 fresh clone 必备输入）；不得通过 `@compass/CONTRIBUTING.md` 默认导入全文，修改入口规则后需运行 `redcap-contributing-ia-check.sh` 与 `redcap-token-risk-audit.sh` |
| references/agent-constraints.md | 项目级 CLAUDE.md / GEMINI.md 通过 `@` 导入此文件；修改此文件影响所有子 Agent 行为 |
| knowledge/design-principles.md | ARCHITECTURE.md 设计哲学章节 + CONTRIBUTING.md §1（元原则引用） |
| compass/knowledge/a2a-communication.md | ARCHITECTURE.md 通信协议章节 + loom/dispatcher/state-machine.md（前瞻标注） |
| 任何 Agent 调用方式 | 先实测（L-8），再改文档 |
| CONTRIBUTING.md §7 | .github/copilot-instructions.md + CLAUDE.md + GEMINI.md（入口索引中的断点续传检查指令）|
| tools/ 下 Hook 脚本 | .claude/settings.json（Hook 注册）+ .gemini/settings.json（Gemini 注册）+ compass/knowledge/host-reliability.md（防线文档）+ references/hook-standards.md §1（不变量清单）|
| loom/tools/redcap-layerA-*.sh | ~/.claude/settings.json（用户级 Hook 注册）+ compass/knowledge/host-reliability.md §3.3/§3.5 + CONTRIBUTING.md §4 |
| references/hook-standards.md | loom/tools/redcap-layerA-session-end.sh（实现必须满足§1不变量）+ compass/knowledge/host-reliability.md §3（宿主覆盖率）|
| references/communication-protocol.md §2 | SKILL.md §5.3 + loom/dispatcher/state-machine.md 伪代码 5e-5f + 全部 prompt-templates + ARCHITECTURE.md 通信协议节 |
| compass/tools/redcap-check-state.sh | compass/tools/redcap-on-qa-pass.sh（集成调用）|
| 涉及 §3.1 触发类型的任何变更 | loom/test-reports/pending-validations.md（登记待验证条目）|
| loom/test-reports/benchmark-scenario.md | loom/test-reports/pending-validations.md（验证矩阵变更可能影响待验证项的验证方法）|
| loom/test-reports/latest-e2e-report.md | loom/test-reports/pending-validations.md（报告产出后消费待验证条目）+ compass/knowledge/lessons.md（经验沉淀）|
| loom/tools/redcap-e2e-postcheck.sh | CONTRIBUTING.md §3.1 步骤⑧ + compass/tools/redcap-on-stop-review.sh（E2E gate 集成）|
| loom/test-reports/e2e-session.yaml（新增/删除）| loom/test-reports/latest-e2e-report.md + loom/test-reports/pending-validations.md + compass/knowledge/lessons.md |

## 7. Layer B 大型任务断点续传

> **本节属于 Layer B（开发 RedCap 自身）**。Layer A 的断点续传由 `.workflow/state.yaml` 这类单一显式 FSM 自动保证；Layer B 不采用同一种单中心状态文件，而是使用 `.dev-task.md + 承诺账本 + closeout runtime + pending closure + closure-ledger + validator-chain + session-start/stop-review/on-complete/session-end` 组成的分布式控制面生命周期。详见 `references/runtime-memory-architecture.md`。

**问题**：Layer B 曾经缺少像 Layer A 那样显眼的单一 FSM 表达，导致会话中断后容易被误判成“只能靠上下文记忆恢复”，也让入口文档和实际控制面之间出现口径漂移。

**解法**：以 `.dev-task.md` 作为当前任务真相源，再由 pending closure、closure-ledger 与 session hooks 补齐闭环事务与恢复链。

### 触发条件

默认在以下情况创建**完整版** `.dev-task.md`：

> **预计超过 2 个独立阶段、且单次会话大概率无法完成** → 创建 `.dev-task.md`

若 §10 PM Gate 已触发但任务本身较小，也允许创建**薄版** `.dev-task.md`：
- 至少包含：`控制面元数据`、`原始输入`、`已确认需求`、`漂移哨兵`、`允许修改范围`
- checklist / 断点备注可以精简，但 canonical truth 不可缺席

因此：**大任务 = 完整版；小任务但进入 PM Gate = 薄版。**

### 文件格式

```markdown
# 当前任务：<任务名称>

## 控制面元数据（机器校验）
task_id: <稳定 ID>
source_of_truth: .dev-task.md
top_goal: <总目标>
active_slice: <当前子任务>
subtask_of: <若 active_slice != top_goal，则填写>
parent_completion_claim: <若是子任务，填写 child-only；不得用子任务 receipt 冒充父任务完成>
host_surface_policy: mirror_only
delegation_boundary: redcap-native-first
governance_tranche: false
governance_debts_addressed: []

## 原始输入（用户原文）
<逐条原文>

## 已确认需求（执行依据）
<逐条确认版 + 执行摘要>

## 漂移哨兵
- <top_goal / active_slice / subtask_of 等防偏航约束>

## 允许修改范围
- <文件 glob>

## 完成标准
- [ ] Phase 1: ...
- [ ] Phase 2: ...
- [x] Phase N: ... ← 已完成的打勾

## 执行承诺账本（Agent 自追加承诺，closeout 必核对）
- [ ] <若你在执行中明确承诺“下一步会做 A/B/C”，写在这里>

## 中插需求账本（执行期新增需求 / 纠偏 / 约束变更时必填）

| id | 触发 | 类型 | 阻塞当前任务 | 优先级 | 处理方式 | 确认需求更新 | 计划更新 | 验收更新 | 状态 | 证据 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| U1 | <用户原文位置> | new-requirement | yes/no | P0-P3 | merge-current / split-child / replace-scope / defer-followup / reject-out-of-scope | yes/no/n/a | yes/no/n/a | yes/no/n/a | captured/replanning/integrated/split/deferred/rejected/superseded/blocked | <证据> |

## 断点备注
<当前进度、下一步、已知阻塞项>
```

### 生命周期

| 时机 | 动作 |
|------|------|
| 大型任务启动 | 在 RedCap 工作区根目录创建 `.dev-task.md` |
| 每完成一个阶段 | 更新 checklist + 断点备注（通常和 commit 是同一个认知时机，顺手打勾） |
| 新会话启动 | 入口索引检查该文件是否存在 → 存在则读取，然后 `git log --oneline -10` 交叉验证实际进度（可能最后一次更新后又做了几个 commit） |
| 任务全部完成 | 删除文件 |

### 控制面硬化（authority inversion 防护）

- `.dev-task.md` 是 Layer B 的 **canonical ledger**，宿主 `plan.md` / workboard 只能做镜像，不得充当真相源
- `compass/tools/redcap-pm-gate-check.sh`
  - SessionStart：warning + runtime stamp
  - Stop review / SessionEnd：blocking
- `compass/tools/redcap-drift-check.sh`
  - 校验 `top_goal / active_slice / subtask_of`
  - 校验本轮改动文件不得超出 `## 允许修改范围`
  - 范围审计必须同时覆盖 tracked、staged 与 untracked 文件；否则新增报告、全景图或研究材料会绕过任务卡，形成“旧 receipt 冒充新任务完成态”的复发路径
  - 当新需求被正式立项并更新 `.dev-task.md` 后，必须显式跑 `redcap-drift-check.sh reanchor <host> .dev-task.md` 刷新宿主控制面指纹；普通 `workspace/strict` 模式发现 hash 漂移仍必须 fail-closed
- Layer B FSM 中的 `PLANNING / PLANNING_REVIEW`
  - `PLANNING` 用于承接方案、切片、执行承诺账本与验证路径；复杂任务不得把计划质量完全交给作者自检
  - `PLANNING_REVIEW` 用于让棱镜审核计划本身；Norven 只负责战略方向与 AI 不可计算事项，不再默认承担细节 plan 审稿
  - 轻量任务可从 `TASK_LOCKED` 直接进入 `EXECUTING`，但高风险、跨机制或治理重构任务必须保留计划审核证据
- Layer B FSM 中的 `CHANGE_INTAKE / REPLAN_REVIEW`
  - `CHANGE_INTAKE` 是执行期中插需求的暂停点：新增需求、纠偏、约束变更、优先级调整先写入 `## 原始输入` 的 `U<n>` 与 `## 中插需求账本`
  - `REPLAN_REVIEW` 是重计划审核点：必须把 U 项归类为合并当前任务、拆子任务、替换范围、延期跟进或拒绝出界，并同步确认需求、计划和验收
  - 子任务 closeout 只能证明子任务完成；若 `.dev-task.md` 存在 `subtask_of`，必须声明 `parent_completion_claim: child-only|none`，不得用子任务 receipt 冒充父任务完成
- `compass/tools/redcap-validator-chain.sh`
  - 统一编排 Layer B 的 session-start / obligation-reconcile / stop-review / on-complete / session-end validator
  - 当前已覆盖 commit proof、review proof、reanchor、PM Gate、drift、backlog、spec registry、task report、artifact lifecycle 等检查，并输出结构化结果供下游消费
  - `session-start` 仍是 advisory / stamp-only，不阻断进入；若发现 outstanding pending closure，只允许通过独立 auto-reconcile helper 尝试核销/收缩**当前可证明的** blocker
  - `stop-review`、RedCap self-dev 的 `on-complete` 与 `session-end` 才是 blocking gate
  - 对非 RedCap 自身项目，`on-complete` 只保留通用的 commit proof，不启用 Layer B 专属的 PM Gate / drift / task-report / artifact lifecycle
  - 输出结构化结果，避免多条控制面检查散落在调用方
- `compass/tools/redcap-interop-governance.sh`
  - 统一维护 interop audit、pending closure obligation 与 `closure-ledger/` 事务日志
  - `pending-closure/` 表示当前 outstanding obligation；`closure-ledger/` 负责保留阶段性 closure 证据，不得互相冒充
- `compass/tools/redcap-artifact-lifecycle-check.sh`
  - 复用 `compass/tools/redcap-artifact-classifier.sh` 统一给路径做 lifecycle 分类，并读取 `compass/docs/index.yaml` 的根目录准入规则
  - 对 **RedCap 自身工作区**，`.githooks/pre-commit` 会用 staged set 模式在提交前拦住 session/local/temp artifact；若 repo-tracked 与非 repo-tracked 产物混提，必须显式报 mixed-lifecycle
  - `stop-review` / `on-complete` / `session-end` 继续检查本轮 commit 区间里所有曾进入历史的路径，而不是只看最终 net diff
  - 一旦命中违规路径，会阻断收尾通过，并显式暴露这批违规产物
  - 阻断 `compass/docs/` 根目录重新长成未分类条目
- `compass/tools/redcap-ensure-git-hooks.sh`
  - 由 `redcap-layerB-session-start.sh` 尝试自动设置 repo-local `core.hooksPath=.githooks`
  - 若仓库原先已经有其他 `core.hooksPath`，必须先写入 `redcap.previousHooksPath`，再由 `.githooks/pre-commit` 在 RedCap 闸门通过后回调旧 hook，避免静默覆盖
- `compass/tools/redcap-on-complete.sh`
  - 对 RedCap 自身 on-complete fail-closed 校验 `commit proof + PM Gate + drift + backlog + spec registry + task report + artifact lifecycle`
  - 若 notify 或 validator-chain 暴露出的 `commit proof / PM Gate / drift / backlog / spec registry / task report / artifact lifecycle` 仍有缺口，必须写回 pending closure，保留下次 reconcile 机会
- `compass/tools/redcap-layerb-closeout-runtime.sh` / `closeout-cap.sh`
  - 作为 Layer B 终态统一入口，先同步 `.dev-task.md` 中的 `## 执行承诺账本`，再串起 `redcap-prism-acceptance-check.sh + redcap-on-complete.sh + redcap-layerB-session-end.sh`
  - closeout 只有在**承诺已兑现 + Prism 验收通过 + pending closure 已清 + receipt 已生成**时才算完成；否则必须写回 blocker / audit，不能只靠“session-end 绿了”口头宣布完成
  - `audit-open` 只做两件事：能补 receipt 时补 receipt；不能补 receipt 时补 blocker / audit。禁止偷偷把未闭环任务改写成 completed
  - 当前至少要有一条强入口消费 `audit-open`；本仓库现行实现选择 `redcap-diagnose.sh` 的 diagnose-rescue 路径
- `compass/tools/redcap-layerB-session-end.sh`
  - 先消费 `validator-chain session-end` 的 `review proof + reanchor + PM Gate + drift + backlog + spec registry + task report + artifact lifecycle`，再决定 notify / pending closure clear
  - 若 validator-chain 未产出可判定 step、notify 失败、pending closure 无法清除，或 closure 证据写回失败，必须保留/更新 pending closure；`session-end` 作为 authority reconcile 入口应以当前 blocker set 重写 `required_redlines`
  - 若 blocker 已判定但 `pending closure / closure-ledger` 无法持久化，必须 fail-closed，不能继续按“正常收尾”退出
- `compass/tools/redcap-pending-closure-reconcile.sh`
  - 由 `session-start` 在成功 re-anchor 后 advisory 触发，用于消费 pending closure 的确定性 redline（reanchor / PM Gate / drift / task report / artifact lifecycle）
  - 只允许在 `task_id + confirmed_hash` 仍匹配当前 canonical pointer 时 auto-clear / rewrite；identity mismatch 时必须保留旧 obligation，不得静默代偿
  - 不负责发送 notify，也不把 SessionStart 升级为 blocking gate；它的职责是“收缩 stale blocker / 自动核销可证明义务”，剩余 blocker 继续交给严格 closure 入口处理
- `loom/tools/redcap-layerA-session-end.sh`
  - 作为宿主通用 SessionEnd 分发器，必须传播 Layer B `session-end` 的 fail-closed 结果，不能用 `|| true` 吞掉 authority 脚本的非零退出
  - Gemini 宿主若接到 Layer B fail-closed，需映射为宿主可识别的 system-block 退出码，而不是继续返回 `allow`
- `compass/tools/redcap-host-workboard-sync.sh`
  - 仅向宿主 workboard 写 canonical pointer / confirmed hash / backlog anchor
  - 不允许反向把需求/验收真相从宿主 workboard 回灌为 RedCap authority
- `compass/tools/redcap-backlog-check.sh`
  - 当 `.dev-task.md` 声明 `backlog_source / backlog_id / backlog_item` 时，负责校验当前任务锚点是否存在于机器可读 backlog 权威
  - `strict` 模式还会检查给人看的 backlog 说明文档是否包含必需的人类摘要结构，并确认自动同步区块没有过期
  - `sync` 模式会用机器权威重写 backlog 说明里的“当前状态总览（自动同步）”区块，避免“机器状态更新了，人类说明还停在旧版本”
- `compass/tools/redcap-current-status.sh`
  - 面向接盘、长任务中途汇报、飞书摘要与人工追问，统一输出 `当前已完成 / 上一步完成的是 / 下一步计划做的是 / 整体计划脉络图与当前位置`
  - 同时汇总 `.dev-task.md` 当前锚点、pending closure 红线、长期 backlog 计数、CLI 工具族 registry cache 与待验证登记，避免只靠零散飞书或 closure ledger 让 Norven 反向考古
  - 当前实现要求宿主提供可写临时目录；read-only reviewer sandbox 只能诚实视为 degraded/manual-only，不再宣称物理强保障
  - 当用户追问“现在整体到哪了 / backlog 还有什么 / 是否已完成”时，优先运行该脚本再汇报；若脚本输出与人工记忆冲突，以脚本和账本为准并说明差异
- `compass/tools/redcap-mechanism-vitality-check.sh`
  - 审计书记官、经验沉淀、灵魂锚点、计划审核与人话全景图是否仍有 runtime 可见面，防止优秀机制只剩自然语言规则
  - 它不能替代宿主级 pre-reply veto，但会被 `diagnose / spec-check` 消费，至少让“zero work”机制在状态面里暴露出来
- `compass/tools/redcap-docs-catalog.sh`
  - 维护 `compass/docs/catalog.json`，把 specs / research / traces / task-reports 的标题、摘要、读法策略、体量与粗略 token 压力压成首读索引
  - 接盘、考古或长任务恢复时，优先运行 `redcap-docs-catalog.sh summary` / `redcap-docs-catalog.sh plan "<问题>"` 定位候选，再用 `redcap-docs-catalog.sh budget <精确路径...>` 审计读取集合；不得默认全量读取 `compass/docs/**`
  - 当前实现要求宿主提供可写临时目录；只读 sandbox 下不再冒充强保障入口
  - `budget` 会拒绝目录、glob、未登记路径、过多文件与超预算读取；真实需要大规模考古时，必须在任务报告中写明范围、理由与折中
  - 修改、移动、新增 `compass/docs/**` 后，必须重新执行 `redcap-docs-catalog.sh generate` 并让 `redcap-docs-catalog.sh check` 通过，避免首读索引陈旧
  - catalog 中 task report 的 `hot / warm / cold-candidate` 只是文件名近因提示，不代表当前 active truth；当前任务锚点必须以 `redcap-current-status.sh`、pending closure 与 `.dev-task.md` 为准
- `references/execution-guarantees.json`
  - 作为“执行保障目录”，把已经形成规则、但必须进入复活协议 / Hook / validator / manual-only 边界的事项列成机器可读清单
  - 后续新增强制规则时，必须先登记 `id / category / priority / source_paths / guarantee_paths / auto_enforceable`；不能只把规则写进自然语言文档
  - 对不能或不宜自动化的规则，必须写 `non_automation_reason`，例如 identity 内容判断、lessons 内容质量、外部 CLI 登录态修复与自然语言风格细节
- `compass/knowledge/index.md`
  - 作为 knowledge 首读导航，说明 lessons、design principles、host hooks、A2A、部署状态、治理债务分别去哪查
  - 需要读取 `compass/knowledge/**` 时，先读 index，再打开 1-3 个精确文件；不得默认 bulk-read 整个 knowledge 目录
  - 新增、移动或删除 `compass/knowledge/*.md` 后，必须同步更新 index，并让 `redcap-knowledge-index-check.sh` 通过
- `compass/tools/redcap-execution-guarantee-check.sh`
  - 校验 `references/execution-guarantees.json` 的必备类别、必备规则 ID、来源文件、保障文件与 manual-only 原因
  - 已接入 `redcap-spec-check.sh`；若检查失败，说明某条规则只停在文档里，没有进入执行保障体系
- `compass/tools/redcap-revival-check.sh`
  - 维护“复活协议是否真正重载执行纪律”的静态门禁，检查 `compass/soul.md`、宿主入口文件、reload-rules、hook standards 与执行保障目录是否对齐
  - 已接入 `redcap-spec-check.sh`；后续新增必须复活时执行的规则，应先补进 `soul.md §6.5` 与 `references/execution-guarantees.json`，再补本检查脚本
- `compass/tools/redcap-acceptance-index.sh`
  - 为巨型 `redcap-multi-session-acceptance.sh` 生成 case 首读索引；需要定位 acceptance case 时先用 `summary/find`，再打开精确行段，不得默认全文读测试脚本
  - 当前实现要求宿主提供可写临时目录；只读 sandbox 下必须退回手工 case 定位或 wrapper
- `compass/tools/redcap-token-risk-audit.sh`
  - 审计 tracked 大文件、ignored 大目录、入口文件大文件自动导入、docs/knowledge/acceptance 首读保护与 Prism 运行残留风险
  - 当前实现要求宿主提供可写临时目录；因此它在只读 reviewer sandbox 中属于 degraded/manual-only，而不是物理强保障
  - 已接入 `redcap-spec-check.sh` 与 `redcap-diagnose.sh`；修改入口文件、docs/knowledge/acceptance/Prism 运行态规则后必须运行
  - 若检查失败，说明复活协议与执行保障脱节；必须先修协议 / 门禁，再继续宣称当前会话已“复活完成”
- `compass/tools/redcap-cli-console-mirror.sh`
  - 负责把 `cli_console.md` 维护成**覆盖式本地展示镜像**，避免继续追加旧回复而让人误以为这里是第二份历史日志
  - 它只能帮助“镜像一致”，不能替代最终对话回复本身；如果镜像内容与最终回复不一致，以最终回复为准
- `compass/tools/redcap-spec-check.sh`
  - `references/spec-registry.json` 是 `compass/docs/specs/*.md` / `compass/docs/archive/specs/*.md` 的机器登记表；每份 spec 必须声明自己的角色、状态、是否 runtime authority、以及它对应哪条控制面或治理债务
  - `references/spec-lifecycle-policy.json` 负责声明 spec 能放哪、什么状态必须归档、何时必须补 `replaced_by`
  - `references/spec-contribution-standard.md` 负责给人说明新增 spec 的命名、role、状态与替代关系该怎么写
  - 校验目标不是把 spec 变成新 authority，而是防止 `specs/` 再次退化成匿名堆放区；凡是被修改的 spec，必须先在 registry 里说清楚“它是什么、它不是什么、它和哪条执行链相关”
- `compass/tools/redcap-session-resume-gate.sh`
  - 基于 `references/host-session-capability-matrix.json` 统一判定 Layer B `full / degraded / unsupported` 隔离模式
  - 只有 gate 明确给出 `full` 与受允 recovery path 时，`redcap-layerB-session-start.sh` 才能 attach/create runtime session
- `compass/tools/redcap-session-continuity.sh`
  - 先把 continuity authority 发布到 `compass/.runtime/sessions/<runtime_session_id>/manifest.yaml` / `provenance.yaml`，再向宿主 workboard 追加 session mirror（`session_handle / binding_key / task metadata / isolation_mode / resume_gate_reason / resume_gate_profile / resume_gate_evidence / continuity_state / import_protocol / next_action / import_ready_signal / import_ready_summary / import_success_summary`；其中 `import_ready_signal` 允许值为 `blocked-no-runtime / not-needed-own-record / not-ready-no-compatible-source / ready / completed`）
  - 只允许基于 repo-local manifest 给出 compatible source suggestion；宿主 `plan.md` 与 `files/imported-sessions/*/metadata.json` 不得反向充当 authority
  - 只有拿到**经过 capability / live process claim 校验**的 runtime binding，才允许发布 manifest 或执行 explicit import；不能信任 shell 里残留导出的 stale capability。显式导入时还必须满足 target workboard 的 Session Mirror runtime 与当前 verified runtime 一致，且 source manifest 已存在。显式导入成功后必须同步写 `compass/.runtime/continuity/import-registry.jsonl` 与 `audit-log.jsonl`
  - 缺少可验证 `runtime_session_id` 时只能输出 `continuity_authority=degraded-no-runtime-manifest` 的 no-runtime mirror；此时 `isolation_mode` 可由 resume gate 判成 `degraded` 或 `unsupported`，但仍不得伪造 `self-recorded / import-suggested / imported`
  - `import_protocol` 是 continuity engine 对当前导入姿态的权威枚举：`runtime-session-unavailable`、`no-compatible-source-detected`、`not-needed-current-session-has-own-record`、`explicit-only`、`explicit-copy-preserve-source`
  - `import` 的 source task metadata 以 source manifest 为唯一 authority；source manifest 必须是 `continuity_state=self-recorded` 的 self-recorded source，携带完整 `task_id / top_goal / confirmed_hash`，且 `own_record_present=1`，同时 source 当前 Session Mirror/runtime 也必须仍与该 manifest 绑定。缺失 source manifest、缺关键 metadata、`continuity_state!=self-recorded`、`own_record_present!=1`、source 当前 mirror/runtime 已退化失绑，或 source/target task metadata mismatch 时必须 fail-closed，不能回退成“只看 source workboard pointer”
  - cross-host continuity 也走这同一套协议：**唯一 host-specific 输入**只有 `references/host-session-capability-matrix.json` 对宿主 full/degraded/unsupported 的判定与恢复路径；只要 source/target 两侧都已是 verified `full` runtime，manifest / explicit import contract 在 claude、gemini、copilot 等受支持宿主之间保持 host-agnostic，不得为某个宿主另写一套“特殊导入语义”

> 该文件已加入 `.gitignore`——它是临时过程状态，不应进入版本控制。

### 治理 tranche 附加要求

当某个 Layer B 任务满足以下任一条件时，应将 `.dev-task.md` 中的 `governance_tranche` 标记为 `true`：

1. 修改 hook / gate / validator / runtime state / closure chain 等框架保障机制
2. 修改 docs / specs / authority / lifecycle 这类会影响全局治理口径的规则
3. 引入或调整“业内权威规范 → RedCap 可执行约束”的映射

当 `governance_tranche: true` 时，额外要求如下：

1. `.dev-task.md` 中必须填写 `governance_debts_addressed`
2. 任务执行前后都要对照 `references/governance-review-checklist.md`
3. 若发现“设计已完成、实现未完成”的治理项，必须补录到 `compass/knowledge/governance-debt-register.md`
4. task report 中必须显式说明：
   - 本 tranche 触及了哪些治理边界
   - 哪些规则已经脚本化 / gate 化
   - 哪些仍是 debt，为什么暂不实现
5. 若任务绑定了长期路线 backlog，`.dev-task.md` 中必须声明 `backlog_source / backlog_id / backlog_item`，并在收尾前确保人类说明文档已由 `redcap-backlog-check.sh sync` 对齐
6. 若任务修改了 `compass/docs/specs/*.md` 或 `compass/docs/archive/specs/*.md`，必须同步更新 `references/spec-registry.json`；若这份 spec 暂无对应执行链，至少要诚实挂到治理债务，不能假装它已经是 runtime guarantee
7. 若某份 spec 被新版替代，必须同步执行三件事：移动到 `compass/docs/archive/specs/`、在 registry 中把状态改为 `superseded`、并填写 `replaced_by`

---

### Layer B 产物生命周期分类

新增/移动文件前，先判断它属于哪一类：

| 类别 | 判断标准 | 典型位置 | git 策略 |
|------|---------|---------|---------|
| **共享规范 / 历史证据** | 需要跨会话共享、可审计、后续要考古 | `compass/docs/specs/`、`compass/docs/traces/`、`compass/docs/task-reports/`、`prism/reports/`、`loom/test-reports/` | **必须进 git** |
| **会话隔离状态** | 只服务当前会话/当前运行态，换机会重建 | `.dev-task.md`、`prism/runs/`、`compass/.workflow/`、`compass/.runtime/`、宿主 `plan.md` | **不得进 git** |
| **本地宿主资产** | 绑定本机路径、凭证、CLI 配置或探测结果 | `.env.local`、`compass/tools/feishu-config.json`、agent registry cache | **不得进 git** |
| **纯临时产物** | 只在脚本执行期间存在，用完即删 | `/tmp/redcap-*`、临时 prompt/result、`__pycache__/` | **不得进 git** |

判断顺序必须是：**先看 authority / 共享必要性，再看文件名像不像“报告”或“状态”**。
例如 `loom/test-reports/latest-e2e-report.md` 虽然名叫 latest，但它是当前基线的共享验证证据，应进 git；而 `compass/.workflow/agent-registry.yaml` 虽然是 YAML，但它记录的是本机 CLI 路径和探测时间，属于本地 runtime cache，不应进 git。

### `docs / knowledge / continuity assets` 的硬边界

- `compass/docs/`：冻结后的正式资产，只放 spec / research / trace / task-report 这类跨会话 evidence
- `compass/knowledge/`：活的操作知识与 heuristics，只放 lessons / host behavior / routing knowledge
- continuity assets：`.dev-task.md`、`explore-notes.md`、宿主 `plan.md` / workboard、imported session artifacts
- `compass/docs/catalog.json`：docs 首读索引，只承载摘要、读法策略与体量信息，不替代任何原始 evidence
- `compass/knowledge/index.md`：knowledge 首读导航，只帮助定位经验/宿主/治理知识，不替代 lessons 或具体 host 记录
- `templates/shared-knowledge/`：未来独立公共知识库的本地模板，负责 append-only 团队沉淀、按用户隔离、索引优先读取；远端仓库未绑定前不得冒充已完成团队共享部署
- `references/file-lookup-dictionary.md`：关键文件定位和人话解释入口；coverage 以 `references/file-lookup-dictionary-policy.json` + checker 为准

补充规则：

1. `docs/` 与 `knowledge/` 是**平级不同职**，不得互相吞并。
2. continuity assets 可以索引、镜像、显式导入，但**不能**直接伪装成 `docs/` evidence。
3. `compass/docs/index.yaml` 是 docs collection 的 retention / archive 索引；新增 docs collection 前先改它，再改目录。
4. spec 生命周期的机器策略以 `references/spec-lifecycle-policy.json` 为准；对人解释以 `references/spec-contribution-standard.md` 为准。两者若不一致，先改策略与说明，再继续改 spec 文件。
5. `compass/docs/**` 不再作为默认工作记忆批量导入；需要考古时，先用 `redcap-docs-catalog.sh summary/plan` 定位，再用 `redcap-docs-catalog.sh budget <精确路径...>` 审计读取集合，只打开 budget 通过的必要源文档。
6. `compass/docs/catalog.json` 只能作为导航索引；涉及 closure verdict、历史根因、runtime authority 或当前 pending 时，必须打开对应原文核对。
7. `compass/knowledge/**` 不再作为默认工作记忆批量导入；需要查经验、宿主行为或治理债务时，先看 `compass/knowledge/index.md`，只打开必要原文。
8. `redcap-multi-session-acceptance.sh` 不再作为默认工作记忆批量读取；需要查 case 时先运行 `redcap-acceptance-index.sh find <关键词>`。
9. 入口文件（AGENTS/CLAUDE/GEMINI/Copilot）必须自动导入小型 `compass/CONTRIBUTING.core.md`，但不得自动导入 `CONTRIBUTING.md` 全文或 `lessons.md` 这类大文件；新会话必须先走 core / current-status / index / rg / budget。
10. `CONTRIBUTING.md` 不是 token 陷阱本身，它仍是权威规范全文；风险点是无差别全文注入。若全文继续膨胀，应优先做 core/section 信息架构、合并重复、迁移历史事故到 lessons/task report，而不是简单削弱规范权威。
11. 宿主入口文件分名存在是 carrier 约束，不是多权威设计。它们必须保持“薄 shim”形态，只负责指向同一套首读链；若入口文件开始各自长出不同规则、不同默认流程或大量独有正文，视为信息架构退化。
12. 新增关键 runtime / Prism / knowledge / host-adapter / product-shape 文件时，必须同步补 File Lookup Dictionary policy 和字典条目，并运行 `redcap-file-lookup-dictionary-check.sh`。
13. 公共沉淀写入 `shared-knowledge` 前必须先查重复；条目文件只新增不改旧文件，索引是派生物，真实任务需要正文时再按路径读取。

---

### 跨工具指令文件位置参考（经官方文档验证 2026-04）

| 工具 | 指令文件 | 有效路径 | 导入机制 |
|------|---------|---------|---------|
| VS Code Copilot | `.github/copilot-instructions.md` | 项目 `.github/` 下 | 无原生导入；使用 `read_file` 指令 |
| Claude Code | `CLAUDE.md` | `./CLAUDE.md` 或 `./.claude/CLAUDE.md` | `@file` 原生自动导入 |
| Gemini CLI | `GEMINI.md` | 项目根目录（及父目录层级） | `@file.md` 原生自动导入 |

---

## 8. Layer B 长任务并行裂变协议

> **本节属于 Layer B（开发 RedCap 自身）**。Layer A 的子任务并行机制见 `SKILL.md §5.15`。

**问题**：分析 RedCap 框架自身时（如 Q3/Q4 审计），单一 Agent 上下文有限，串行处理 5+ 个独立模块会导致上下文溢出或结论被压缩。

**触发条件**（同时满足）：
1. 分析/评估目标 ≥ 5 个独立模块（如 5 个角色文件、5 个 hook 脚本）
2. 子任务之间无耦合（A 的结论不依赖 B）
3. 只关注结论，不需要记录和存储任务过程

### 执行步骤

```
1. 将分析目标拆解为 N 个互不依赖的子任务，每条描述清晰（不依赖当前上下文）
2. 用 explore agent（Copilot task tool）或 headless CLI（claude -p / gemini -p -y）并行启动
3. 完成标记：每个子任务结果写入 /tmp/redcap-subtask-{session_id}-{n}.txt，写完追加 ##DONE##
4. 主 Agent 等待所有 ##DONE## 出现后再汇总（不读取半成品）
5. 汇总完成后清理所有 /tmp/redcap-subtask-{session_id}-* 文件
```

**实例**：Q3/Q4 分析（5 个并行 explore agent，分别分析 Layer A/B 各钩点、角色定义、工具脚本、参考文档、状态机），汇总后无损益精简项，发现 hook-standards.md 与 host-reliability.md 轻微重叠但目的不同（保留）。

---

## 9. Layer B Red Teaming 协议

> **本节属于 Layer B（开发 RedCap 自身）**。Layer A 的 Red Teaming 见 `SKILL.md §5.16`。Stop Hook 对 Layer B 变更的事后独立评审见 `§4`。

**问题**：Cap 改动框架自身时，作者盲点（L-24）比 Layer A 更严重——改文档的 Agent 无法客观评价自己的改动。

**触发条件**（满足任意一条）：
- 改动 `SKILL.md` / `CONTRIBUTING.md` / `roles/` 下任意文件，且总变更行数 > 20
- 新增或删除角色定义文件
- 修改 hook 脚本逻辑（不含注释/格式）

### 执行步骤

```
1. 获取 diff：git diff HEAD（或 git diff [base]..[head]）
2. 启动独立 critic Agent（claude -p 或 gemini -p -y），传入完整 diff
3. Critic prompt 框架：
   "你是一个对抗审查员，不看作者解释，只看 diff。
    请找出：① 逻辑错误或与现有规范矛盾之处 ② 遗漏的关联文件 ③ 无意引入的增熵内容。
    以 JSON 输出：[{severity: 'blocking'|'warning', file, area, problem, impact}]"
4. 处理结论：
   - blocking → 必须修复后才能 commit
   - warning → 评估是否接受，不接受的写入 knowledge/pending-validations.md
```

### ⚠️ Rubber-duck 等待规则

> **本规则解决"先开工后审查"导致 blocking 问题需要返工的风险。**

| 变更影响等级 | 判断标准 | Rubber-duck 策略 |
|------------|---------|----------------|
| **高影响** | 涉及核心协议（CONTRIBUTING.md/SKILL.md/prism/protocol.md）、跨 ≥3 个框架文件、新增 Layer B 工具脚本 | **必须等 rubber-duck 完成后再开工**，不得并行 |
| **中影响** | 改动单一文档或脚本（<50行），§6 联动文件 <3 个 | rubber-duck 与初步调研可并行，**必须在第一行代码前等待结果** |
| **低影响** | 格式/注释修正、追加内容到已有文档末尾 | 可跳过 rubber-duck |

**操作规范**：
- 高/中影响变更：先发 rubber-duck，完整读取结果，处理全部 blocking 后再开工
- 不得以"可以边做边改"为由跳过等待步骤——rubber-duck 的价值在于**发现设计级问题**，代码写了再改的成本远高于等待
- 若 rubber-duck 超时（>10分钟无结果），记录到 `knowledge/explore-notes.md` 并按高风险人工执行

### ⚠️ 质量优先铁律：质量关键审查禁止因等待而降级

> **本规则解决“因为 reviewer 回得慢，于是先用较弱证据收口”的质量塌陷风险。**

以下场景都属于**质量关键审查**：

1. 中途 review / tranche review
2. reviewer / challenger / auditor 这类多角色对抗审查
3. 用于决定“是否继续实现 / 是否可宣称通过”的独立 Agent 审查

**强制规则**：

1. 时间因素不是首要判断标准；**质量保障优先于等待成本**
2. 若某一路质量关键审查长时间未返回，**不得**因为“已有部分结论”就直接降级到更弱审查层级收口
3. 正确动作是启动一个**同等质量的回收任务**：
   - 角色等价（如 reviewer ↔ reviewer、challenger ↔ challenger）
   - 审查目标等价
   - 能力等级不得低于原任务
4. replacement 任务返回前，不得把“原任务可能永远不回来”当成默认前提，更不得用它为降级背书
5. 只有在**明确证明同等级回收路径也不可用**时，才允许标记为 degraded；且必须在结论中诚实声明“保障层级已下降”

**禁止动作**：

- 因 impatience/超时焦虑，直接用较弱 agent、较少角色、较浅审查维度提前给通过结论
- 把“先给一个临时结论，后面再补审”当作默认策略
- 在未拿到等同质量回收结果前，把时间压力凌驾于质量红线之上

> 若命中本条，应优先遵守本铁律，而不是选择“先推进、后补票”。

**与 §4（Stop Hook）的分工**：
- §9 是**主动**、**commit 前**的对抗审查（作者发起）
- §4 是**被动**、**会话结束时**的独立评审（Hook 兜底）
- 两者互补，不互相替代

---

## 10. Layer B 需求确认门（PM Gate）

> **本节属于 Layer B（开发 RedCap 自身）**。防止长任务执行期因上下文衰减导致需求漂移。

**问题根因（L-31）**：用户同时提出多个问题时，需求描述存在于对话早期；随着讨论轮次增加，原始文本在 attention 窗口中的权重持续下降，最终被压缩截断。Cap 执行时依赖的是自己的"记忆概括"而非原始文本，导致执行偏离。

### 触发条件（满足任意一条）

- 用户提出 **任意需求**（即使只有 1 个 Q，也可能因澄清对话变长而稀释原意）
- 涉及 **RedCap 框架架构设计决策**（新增角色、修改核心协议、调整 Layer A/B 边界等）

### 执行流程

**Step 0：原文即时固化（澄清讨论开始之前）**

> ⚠️ 这是整个流程中**最优先**的动作，任何讨论之前必须先完成。

触发确认门后，**第一件事**：将用户原始输入逐条原文写入 `.dev-task.md` 的 `## 原始输入（用户原文）` 段。
- 内容为用户消息的**字面原文**，禁止概括、改写或精简
- 写完之后才开始任何澄清对话
- 若任务执行中用户又追加了**新的需求、纠偏、约束、优先级或范围变更**，也必须在**本轮结束前**按 `U<n>` 继续追加到同一段，并同步 `## 中插需求账本`；禁止只依赖会话记忆

> 原理：PM 对话可能走很多轮，原始文本会在 attention 窗口中衰减。先落盘就不会失真——即使后续确认版与原文有出入，也随时可回溯对比。

**Phase 1：需求澄清（PM 模式）**

Cap 引用 `roles/product-manager/handbook.md §一` 的策略执行：
- 规模评估：≥3 个 Q 时先做拆分确认，明确本轮范围 / 后续阶段 / 暂不处理；单个 Q 同样完整走本流程
- 逐 Q 澄清边界：目标是什么、不包含什么、验收标准
- 每次只问一个问题，优先用选择题
- 发现潜在问题时主动指出并给出替代方案

> ⚠️ 此阶段 **禁止开始执行任何实现**，即使某些 Q 已经足够清晰。

**Phase 2：需求锁定**

用户发出明确确认语句后（如"就这样干吧"/"确认"/"开始"/"可以"），执行需求锁定：

1. 在 `.dev-task.md` 中写入 `## 已确认需求（逐条，禁止改写）` 段（见模板）
2. 内容为 PM 对话结束后的**最终确认版**（可能与原始输入有合理出入，但必须有据可查）
3. 执行每个 Q 之前，**必须 re-read 该段对应 Q 的描述**，而不是依赖记忆

**Phase 2.5：原始意图覆盖审计（scope coverage）**

在进入执行前，必须写入 `.dev-task.md` 的 `## 原始意图覆盖审计` 段，并通过 `redcap-intent-coverage-check.sh`：

1. 明确 `scope_status`：`full-implementation`、`route-only`、`partial-with-explicit-defer` 或 `not-applicable`
2. 对比 `## 原始输入`、`## 已确认需求` 和 `## 完成标准`，说明哪些原始意图已经覆盖
3. 若只是路线图、方案、部分实现或显式延期，必须写清未覆盖/降级项、用户可见边界和后续任务
4. 复杂任务的 Planning Review 也必须审这个覆盖段，防止 Agent 把战略目标降级成容易完成的小账本

**Phase 3：执行门控**

- 没有明确确认语句 → 不进入执行，继续澄清或等待
- 每完成一个 Q → 在该 Q 描述下追加 `> 执行摘要：<一句话>` 用于对标检查
- 若用户在执行期新增了独立要求，必须同时补：`## 原始输入` 新条目 + `## 已确认需求` 对应新 Q 或修订条目，再继续执行
- 若用户在执行期新增需求、纠偏、约束或优先级变化，必须先进入 `CHANGE_INTAKE`：补 `## 原始输入` 的 `U<n>`、补 `## 中插需求账本`、重新评估优先级和验收，再决定继续当前任务、拆子任务、替换范围、延期或拒绝出界；禁止直接把最新插入项做完后宣称全部完成
- 若拆出子任务，必须在子任务 `.dev-task.md` 声明 `subtask_of` 与 `parent_completion_claim: child-only`，并在父任务账本保留未完成范围；子任务 receipt 不得自动关闭父任务

### `.dev-task.md` 模板扩展

在 §7 模板基础上，触发本节时新增两个需求段：

```markdown
# 当前任务：<任务名称>

## 原始输入（用户原文，触发时立即记录，禁止改写）

### Q1
<用户原文粘贴，一字不改>

### Q2
<用户原文粘贴，一字不改>

## 已确认需求（PM 确认后填写，执行依据）

### Q1: <确认后标题>
<PM 对话结束后的最终确认描述，可能与原始输入有合理出入>
> 执行摘要：（执行完成后填写，用于对标检查）

### Q2: <确认后标题>
<最终确认描述>
> 执行摘要：（执行完成后填写）

## 完成标准
- [ ] Q1: ...
- [ ] Q2: ...

## 原始意图覆盖审计
scope_status: <full-implementation|route-only|partial-with-explicit-defer|not-applicable>

- 原始意图：...
- 已覆盖：...
- 未覆盖/延期：...
- 用户可见边界：...
- 后续路径：...

## 断点备注
<当前进度、下一步、已知阻塞项>
```

> **两段分工**：原始输入 = 防失真底稿（永不修改，随时回溯）；已确认需求 = 执行依据（经 PM 细化，可合理演进）。

**执行期真相源**：`.dev-task.md` 是 Layer B 的唯一 canonical truth。  
宿主 `plan.md` / session workboard 只允许镜像 `task_id`、`canonical_path`、`confirmed_hash`、`active_slice` 等 pointer 信息，以及 `session_handle / binding_key / continuity_state` 这类 continuity mirror，不得承载需求正文或验收真相。

### ⚠️ 关键认知修正

> **"Norven 在场给出授权" ≠ "PM Gate 已完成"**

即便 Norven 全程在场、明确说了"开始"，PM Gate 仍须执行。授权只是"推进许可"，不等于：
- 需求被完整澄清（细节可能仍停留在口头讨论中）
- 需求被正式记录（无文档 = 无追溯）

**正确认知**：PM Gate 的产物是**需求文档**（`.dev-task.md` 中的已确认需求段），不是口头确认。文档产出后才算 PM Gate 完成。

### 与现有机制的关系

| 机制 | 解决的问题 | 触发时机 |
|------|----------|---------|
| §7 断点续传 | 会话中断后如何恢复**进度** | 大型任务启动 |
| §10 需求确认门 | 执行过程中如何保持**需求保真** | 任意需求（含单 Q） |

> 两者互补：§10 确保需求在 Phase 1 被锁定，§7 确保锁定后的进度在会话中断时可恢复。

### 自主执行授权（Norven 2026-04-11 明确授权）

当满足以下**全部条件**时，Cap 可在不阻塞等待 Norven 显式指令的情况下**自主执行 PM Gate 并推进任务**：

| 条件 | 判断方 | 说明 |
|------|--------|------|
| **优先级高** | Cap 自评 | 该任务对框架健康/一致性有明显收益，延迟有实质代价 |
| **必要性高** | Cap 自评 | 不做会导致明确的缺口或风险（非"锦上添花"） |
| **棱镜团队多人一致通过** | 棱镜内部评审 | 通过棱镜协议召集 ≥2 个独立视角，无 blocking 反对意见 |

**执行规范**：
- 自主执行时仍需完整走 PM Gate 流程（Step 0 固化原始输入 + Phase 1 澄清 + Phase 2 锁定）
- 棱镜评审结论写入 `.dev-task.md` 的 `## 自主决策依据` 段，作为可追溯的授权记录
- 任务完成后，**必须**按 `references/task-report-template.md` 归档到 `compass/docs/task-reports/YYYY-MM-DD-<topic>.md`，再同步给 Norven
- 若执行过程中出现超出预期的影响范围扩大，立即暂停并向 Norven 透传
- Stop review / SessionEnd 若 `redcap-pm-gate-check.sh` 或 `redcap-drift-check.sh` 失败，则不得宣称 Layer B 任务收尾完成

> **本规则不适用于**：涉及架构方向性变更（如调整 Layer A/B 边界、新增/删除核心角色）、外部依赖引入、以及 Norven 明确要求介入的决策点——这些仍须等待 Norven 显式确认。

### 宿主通用 skill overlay 兼容规则

宿主侧的通用 brainstorming / planning / visual 类 skill，只能视为 **overlay protocol**，不能视为 Layer B 的 authority。

这意味着：

1. 若 `.dev-task.md`、Norven 显式授权、或棱镜评审结论已足以锁定当前 tranche / 顺序 / 方案，Cap **不得**因为 overlay skill 的默认流程而再次 ask_user 要求 Norven 重新选择。
2. overlay skill 可以帮助做规模评估、方案比较、设计表达，但这些产物只能作为 **输入建议**，最终锁定仍由 RedCap-native PM Gate 完成。
3. 若 overlay skill 自带“设计完成后继续交给 writing-plans / planning 类宿主下游 skill”的默认后继链，Cap 必须在设计产出落盘后回到 RedCap-native `.dev-task.md` / `plan.md` / PM Gate 继续；缺少这类宿主下游 skill 不是合法 blocker，也不允许因此中断主流程。
4. 人工介入只允许用于以下场景：
   - 缺少 AI 无法推断的外部事实、凭证、业务偏好或运行时信息
   - 缺少 AI 无法直接执行/验证的人类动作（如 GUI/manual validation）
   - Norven 已明确保留该决策（包括架构方向性变更、外部依赖引入）
5. 若确需人工介入，必须先在 `.dev-task.md` 或 `explore-notes.md` 中记录 **为什么 AI 不能自己算出来**，再进入 ask_user / need_user / blocked_on_user。
6. Prism 死锁或 Dispatcher 升级建议本身不构成合法人工介入理由；它们必须先定位到上述某个具体缺口，才能上抛给 Norven。
7. 共享宿主 skill 属于宿主资产，不属于 RedCap 的 patch surface。Cap 不得通过直接修改宿主 shared skill 的原始文件来让 RedCap 能力“成立”；若不改宿主 skill 就无法稳定工作，则该能力必须在报告与架构口径中标记为 **degraded / unsupported overlay**。
8. `baton-delegate.sh --skill-path` 这类 skill 外包能力，只允许把 external skill 当作 **leaf worker / evidence producer / advisory helper** 使用；它不得拥有 `.dev-task`、ask_user、状态迁移、commit、通知或收尾 authority。若离开这些权力就无法工作，则仍按 **degraded / unsupported overlay** 处理。
9. overlay / host skill 产物不得覆盖 `.dev-task.md`、任务账本、门禁结果、runtime receipt 或 closeout 结论；它们只能成为参考输入，最终 authority 必须回到 RedCap-native 控制面。

> **实现口径说明**：这一条当前属于**prompt-level hard limitation + canonical-truth discipline**。由于 ask_user/tool 调用发生在宿主层，仓库内的 shell gate 无法物理拦截每一次升级动作，因此 RedCap 只能在自己的控制面里拒绝承认越权结果；若宿主 shared skill 仍与之冲突，正确结论是该集成处于 **degraded / unsupported**，而不是去改写宿主共享资产本体。

---

## §11 棱镜（Prism）— 多视角协同分析引擎

> 详细协议见 `prism/` 目录。本节为快速参考。

棱镜是 RedCap 的底层公共能力，将多 Agent 协同分析系统化为可复用的标准流程。当单一视角不足以得出可信结论时，召唤棱镜。

### 何时用棱镜 vs §8/§9

| 场景 | 路径 |
|------|------|
| ≥5 模块快速并行（结论不需要跨模型共识） | §8（保留，轻量） |
| 提交前简单检查（单模型足够） | §9（保留，轻量） |
| 核心协议改动需要跨家族模型审查 | Prism redteam |
| soul/identity 大改后的效果验证 | Prism test |
| 方案有分歧，连续两轮卡壳 | Prism council |
| 架构探索，方向未定 | Prism explore |

§8/§9 是轻量快速路径，Prism 是高后果决策的系统化路径，两者并存。

### Dispatch 前可用性硬门

- Prism roster 必须写成 `provider&model:role`，例如 `kimi&kimi-k2:reviewer`；未写 provider 时，RedCap 无法判断要调用哪个本地 CLI，必须拒绝。
- Dispatch 前必须先通过 `bash prism/tools/prism-availability.sh check-roster --agents "<roster>"`；该脚本维护 `compass/.workflow/prism-agent-availability.json`，TTL 为 1 小时。
- 清单过期时自动调用 `redcap-agent-health-probe` 做真实 headless 嗅探；只有 `pass` 可进入本轮 roster，`frozen`、`timeout`、`fail`、`unsupported` 都不得调用。
- `filter-roster` 只能帮忙筛出当前可用候选；筛完以后仍要重新检查角色、模型家族和 quorum 是否满足 Prism 模式要求，不能静默降配。

### 触发条件（风险信号驱动）

- 改动核心协议（本文 §1-§13、SKILL.md §5.x）→ **redteam**
- 改动 soul.md / identity.md → **test**
- 存在 ≥2 个互斥方案 → **council**
- 已有明确不确定性或反对意见 → **explore**
- 无法在 2 轮内自行解决的卡壳 → **council**
- **`model-capability-matrix.yaml` 的 `next_review` 日期已到** → 触发矩阵更新流程（见下）

### 结论性输出 Prism Gate

RedCap 官方结论不能再由主 Agent 单路自证。凡是会指导后续工程的架构判断、完成性判断、风险分类、发布姿态、长期路线或治理决策，都属于 `references/conclusion-prism-policy.json` 定义的 conclusion-class 输出：

1. 先判断这是否是 RedCap 官方结论，而不是只解释已有 receipt、命令输出或 tracked policy。
2. 若是官方结论，必须走 Prism 协作、复核或验收；资源受限时必须留下 resource-limited 证据链，不能把单路观点写成“我们共同评审结论”。
3. 未经 Prism 的即时回复只能叫“建议稿 / 初判 / proposal / first-pass”，不得作为工程决议落账。
4. task report、closeout、release readiness、长期路线分类这类 repo-owned 结论，必须在收口前能被 `redcap-conclusion-prism-check.sh` 与 Prism acceptance / receipt 链复核。

### 计划型完成与后续任务登记

如果官方结论只是 `design-complete`、`plan-complete`、`route-only` 或 `partial-with-explicit-defer`，不能把它写成物理完成或全量完成。结论、报告和 closeout 必须同时说明：

1. 哪些内容已经完成。
2. 哪些内容没有完成，尤其是后续 physical apply、目录迁移、发布前置或治理加固。
3. 每个后续项被登记在哪里：当前任务账本、架构/治理 backlog、receipt deferred item，或带 owner surface 的 no-follow-up 理由。

缺少 durable follow-up 登记时，Prism reviewer 必须把它当作 closure-gap，而不是只给“方案合理”的通过意见。

### 新增能力的固化保障优先级

后续 RedCap 新增能力、流程节点或纪律规则时，默认先评估能否进入脚本、validator、hook、acceptance、receipt、diagnose/spec-check 或 `references/execution-guarantees.json`。只有在评估后确认“不需要这么严格保障”“自动化会误伤”“当前宿主没有物理控制点”时，才允许降级为 documented / manual-only，并必须写清降级理由和后续如何发现漂移。

### 模型矩阵更新流程

Cap 每次任务启动时检查 `compass/knowledge/model-capability-matrix.yaml` 的 `next_review` 字段：

```bash
TODAY=$(date +%Y-%m-%d)
NEXT_REVIEW=$(grep 'next_review:' compass/knowledge/model-capability-matrix.yaml | awk '{print $2}')
if [[ "$TODAY" > "$NEXT_REVIEW" || "$TODAY" == "$NEXT_REVIEW" ]]; then
  # 触发更新
fi
```

**触发后执行**：
1. 收集新模型信息（Gemini/Claude/GPT 发布记录、lessons.md 新增条目）
2. 更新矩阵评分（对比旧评分，偏差 ≥1 分的模型标注 `updated: true`）
3. 对比路由算法：是否影响各角色首选模型
4. 若首选变更 → 更新 `agent-registry.yaml`，通知 Norven
5. 更新 `last_updated` + `next_review`（+30 天）并 commit

### 与 §10 PM Gate 的顺序

```
需求不清晰 → §10 PM Gate 先行（Prism 不运行）
需求已锁定 + 有高风险信号 → Prism 运行（验证模式，不重开需求决策）
Prism 发现需求边界问题 → escalate → 回到 §10 PM Gate 重新锁定
```

### 索引

- 协议全文：`prism/protocol.md`
- 模式说明：`prism/modes/README.md`
- 报告归档：`prism/reports/`（git 追踪）
- 报告索引：`prism/reports/index.yaml`

---

## §12 书记协议（Scribe Protocol）

> **本节属于 Layer B（开发 RedCap 自身）**。防止 PM Gate 前的方向探讨因上下文压缩丢失，解决"讨论阶段无记录机制"的系统性缺口。

**问题根因**：多Q探讨阶段（PM Gate 触发前）可能走很多轮——用户抛方向、Cap 细化加工、反复讨论——整个演进过程没有任何沉淀。当真正需要回溯某轮细节时，已无从查找。这比需求漂移更早发生，且无法被 §10 PM Gate 覆盖（那时方向尚未确定）。

### 触发条件（满足任意一条立即触发）

- 当前对话中**存在 ≥2 个未解决问题**
- 同一主题已**连续 >3 轮对话未做任何记录**
- 用户明确提出讨论存在**分歧或选项**（即使只有 1 个 Q）

### 执行动作

触发后，Cap 立即将当前讨论状态写入 `compass/knowledge/explore-notes.md`（书记模式）：

1. **即时性**：触发条件成立后**本轮对话结束前**完成写入，不推迟到下一轮
2. **完整性**：用户原始问题必须逐字原文记录（与 §10 PM Gate 同等要求，禁止概括）
3. **增量追加**：每次触发追加新条目，不覆盖已有记录
4. **归档闭环**：Q 决策落定后，将对应条目状态更新为 `[ARCHIVED]`，并沉淀到 `.dev-task.md` 或 `knowledge/lessons.md`

### 写入格式

```markdown
## [YYYY-MM-DD HH:MM] Q<N>: <问题标题>

**原始问题**（用户原文，禁止改写）：
> ...

**演进过程**：
- 轮次 1：...
- 轮次 2：...

**关键分歧 / 选项**：
- 选项 A：...（支持理由）
- 选项 B：...（支持理由）

**当前共识**：...

**待决策**：[NORVEN_DECIDE] / [CAP_DECIDE] / 已决定：...

**状态**：exploring / aligned / decided / [ARCHIVED]
```

### 与 §10 PM Gate 的衔接

```
书记模式（§12）                    PM Gate（§10）
─────────────────                  ──────────────────
• 探讨阶段（方向未定）触发          • 方向确定后触发
• 写入 explore-notes.md            • 写入 .dev-task.md
• 防止"讨论丢失"                   • 防止"执行漂移"
↓                                   ↑
explore-notes.md 作为 PM Gate Phase 1 的原始资料直接消费
```

PM Gate 触发时，**必须先读 `explore-notes.md`** 的相关活跃条目，作为需求澄清的上下文底稿。

### Stop Hook 检查

`compass/tools/redcap-explore-notes-check.sh` 在 Layer B 的 Stop / SessionEnd 链中检查：
- 若 `explore-notes.md` 存在且有**未归档**（非 `[ARCHIVED]`）的活跃条目 → 只输出本地 stderr 提醒并写去重标记，不再发送飞书；该提醒不属于“节点汇报/人工介入中断”
- 提醒内容：条目数量 + 归档指引

### 文件位置

`compass/knowledge/explore-notes.md`（持久化，git 追踪，与 lessons.md 同级）

---

## §13 任务级完成强制复盘协议（Task Completion Review Gate）

> **问题来源**：§4 Stop Hook 是会话级检查（每轮结束），§9 rubber-duck 是变更级检查（单次改动前）。但两者之间存在盲区——**"这批任务全做完了"这个时刻缺少强制绑定的整体 review 动作**，导致大规模迭代结束后无人触发全量复盘，遗漏问题只能靠 Norven 手动发现（如本次收尾工作暴露的问题）。

**本节封堵该盲区**：任务完成时触发强制全量 review + 复盘 + 报告。

### 触发条件（满足任意一条）

| 条件 | 说明 |
|------|------|
| 本次任务**变更文件数 ≥ 10** | 大范围改动，单点 rubber-duck 无法覆盖全局。计数口径：`git diff --name-only <base>..HEAD` 输出的文件数，重命名计 1 个，合并多 commit 按整体范围算 |
| **全部 todos 标记为 done** 且涉及框架级文件（CONTRIBUTING.md / SKILL.md / prism/protocol.md） | 框架型迭代完成。触发主体：Cap 在每次将最后一个 todo 标记 done 后自检 |
| 用户明确说"完成了"/"收工"/"结束" | 显式触发 |

### 对外输出纪律（强制）

1. **默认连续执行**：长任务默认连续推进，不得因单路评审回执、后台 Agent 完成、`system_notification`（系统通知）、阶段性 clean 结论或局部小结而主动打断 Norven。
2. **只允许 3 种主动输出**：
   - 命中人工介入门（缺外部事实 / 人工动作 / Norven 保留决策）
   - Norven 主动追问当前状态
   - 当前 `.dev-task.md` 下**全部 todos 完成**，进入本节 Step 4 任务完成报告
3. **中间进展只写账本**：未命中上面三条时，中间过程只允许写入 `.dev-task.md`、`plan.md`、宿主镜像、closure 账本等连续性资产，不主动占用对话通道。
4. **人工介入必须先亮明原因**：一旦需要打断 Norven，第一句先明确“是否需要你介入”，并说明缺的究竟是外部事实、人工动作还是保留决策。
5. **切片完成不等于任务完成**：`active_slice` 或局部子任务完成后，若 `.dev-task.md` 仍有未完成 todo，Cap 必须继续执行，不得把该切片包装成“终局汇报”。
6. **中插完成不等于整体完成**：执行期用户新增的 U 项若被拆成子任务或局部完成，输出只能称为“U 项已处理 / 子任务已完成”；只有父任务承诺账本、完成标准、Prism 验收与 receipt 全部闭环，才允许终局汇报。

### 执行步骤（必须按顺序完成，不可跳过）

```
Step 1: 文档一致性扫描
  - 检查所有变更文件的交叉引用是否对齐（文件路径、节号、版本描述）
  - 扫描 baton-design.md / 路线图类文档，确保已实现项标记更新
  - 检查 docs/ 信息架构与产物生命周期是否一致：spec / research / trace / task-report 是否各归其位，`.workflow/` / `.dev-task.md` / 本机 cache 是否仍停留在本地态

Step 2: explore-notes.md 全量归档
  - 将所有已决策条目标记 [ARCHIVED]，更新归档索引表

Step 3: 全量 rubber-duck 对抗评审
  - 传入本次任务所有变更文件的 diff（git diff <base>..<head>）
  - Prompt 要求：找出跨文件的逻辑矛盾、遗漏的联动更新、协议不一致
  - 所有 blocking 问题修复后才能进入 Step 4

Step 4: 任务完成报告
  - 按 references/task-report-template.md 整理完整报告
  - 归档到 `compass/docs/task-reports/YYYY-MM-DD-<topic>.md`
  - 同步给 Norven（对话中引用报告内容/路径）
  - 完成所有 todo 后，优先通过 `./closeout-cap.sh` 或 `bash compass/tools/redcap-layerb-closeout-runtime.sh complete ...` 执行统一 closeout runtime，而不是手工拼接棱镜验收 / on-complete / session-end
  - closeout runtime 会核对 `## 执行承诺账本`、Prism 独立验收、summary / receipt / rescue audit；承诺未清、验收缺失、receipt 缺失或 blocker 未清时，不得伪装成收口完成
  - 作者只能汇报“已实现 / 已自检”；只有 Prism 验收通过且 receipt 已生成后，才允许汇报 completed
  - 报告文件最迟需在 SessionEnd 前存在且已纳入 Git（已提交或已暂存均可被审计；建议随最终提交一起归档）
  - 若报告尚未提交，先 `git add <report_path>`，再执行 `bash compass/tools/redcap-task-report-register.sh <claude|gemini|copilot> <report_path>` 显式登记本次任务的报告路径
  - SessionEnd Hook 会审计报告文件是否存在且模板关键章节齐全
  - 报告开头必须提供 `当前已完成 / 上一步完成的是 / 下一步计划做的是 / 整体计划脉络图与当前位置` 四段摘要；stdout 收尾摘要与飞书通知会直接优先抽取这四段
  - 终局对话回复必须先说明：本次做了什么、上一刀是什么、下一刀是什么、当前位于整条路线的哪里；然后再补是否仍需你介入、是否还有遗留 todo 与报告路径
  - 最终对话回复不得只说“报告已归档”；若 `人工审核要点 / 人工验证项` 中存在非空内容，必须先显式顶出，再给报告路径
```

### 与现有机制的关系

| 机制 | 粒度 | 触发时机 | 解决的问题 |
|------|------|---------|----------|
| §4 Stop Hook | 会话级 | 每轮结束 | 未归档告警、事后评审 |
| §9 rubber-duck | 变更级 | 单次改动前 | 设计缺陷、blocking 问题 |
| **§13 本节** | **任务级** | **全部 todos 完成时** | **跨变更全局一致性、遗漏收尾项** |

> 三者形成三层防护：§9 防止单次变更出错 → §13 防止任务收尾遗漏 → §4 防止会话结束时还有未处理问题。

---

## §14 调研协议（Research Protocol）

> **适用范围**：任何以"调研 / 找最佳实践 / 参考外部资料"为目的的任务。
> **核心原则**：调研内容具有实验性和不确定性，未经严格评审直接采用是高风险行为。

### 14.1 调研工具优先级

按以下优先级选择调研渠道，越前质量越高：

| 优先级 | 工具 | 适用场景 |
|--------|------|---------|
| 1 | **GitHub MCP**（高星仓库搜索） | 寻找已被工程验证的开源实现、框架设计 |
| 2 | **Gemini CLI（Google Search）** | 最新资讯、学术论文、技术博客 |
| 3 | **web_fetch（已知 URL）** | 官方文档、规范文件（URL 已知时） |
| 4 | **训练知识** | 仅作为初始线索，不得作为单独信源 |

> 仅凭训练知识输出调研结论视为**不合规**。调研必须有外部信源支撑，且信源须在报告中明确引用。

### 14.2 调研报告评审流程（强制）

调研报告在被采纳为设计依据前，**必须经过以下评审步骤**：

```
Step 1: 调研执行
  - 使用 ≥2 种调研渠道（至少含 GitHub MCP 或 Gemini Search 之一）
  - 明确标注每条结论的信源（仓库名/URL/论文名）
  - 标注每条结论的"确定性"（Verified = 已有工程验证 / Experimental = 理论/小样本）

Step 2: 初轮内部评审（rubber-duck）
  - 传入调研报告全文
  - Prompt 要求：找出逻辑跳跃、信源不可靠、与已有设计冲突的地方
  - 所有 blocking 修复后进入 Step 3

Step 3: 对抗评审（Prism redteam，可选但推荐）
  - 触发条件：调研结论将影响核心协议或架构决策
  - 至少 challenger + reviewer 两角色对调研报告发起对抗分析
  - 发现 CRITICAL 问题须修订调研结论后重走 Step 2

Step 4: 采纳标注
  - 调研报告中每条被采纳的结论标注 [ADOPTED]
  - 被评审否决的结论标注 [REJECTED: 原因]
  - 待验证的结论标注 [EXPERIMENTAL: 验证计划]
```

### 14.3 调研结论的置信度标注

调研报告中，每条关键结论须附置信度标签：

| 标签 | 含义 | 采纳要求 |
|------|------|---------|
| `[VERIFIED]` | 有多个高星工程实现印证 | 可直接采纳 |
| `[EXPERIMENTAL]` | 理论合理，但工程验证样本少 | 须在实现中标注风险，制定回滚方案 |
| `[UNVERIFIED]` | 仅有单一信源或训练知识 | 不得采纳为设计依据，须补充调研 |

### 14.4 与现有机制的关系

| 机制 | 粒度 | 解决的问题 |
|------|------|----------|
| §9 rubber-duck | 变更级 | 实现代码/设计的 blocking 问题 |
| §13 任务复盘 | 任务级 | 全局一致性、收尾遗漏 |
| **§14 本节** | **调研级** | **外部信源不可靠、实验性结论贸然采用** |
