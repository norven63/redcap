# RedCap — 三体架构设计文档

> **一句话定义**：RedCap 是一个由 Dispatcher 驱动、多 AI Agent 分角色协作的软件工程框架，内部由织机（Loom）、璇玑（Compass）、棱镜（Prism）三个子系统构成。

---

## 目录

- [设计哲学](#设计哲学)
- [三体架构总览](#三体架构总览)
- [织机（Loom）— Layer A](#织机loom--layer-a)
  - [Dispatcher 事件循环](#dispatcher-事件循环)
  - [状态机](#状态机)
  - [通信协议](#通信协议)
  - [角色系统 + Prompt 组装](#角色系统--prompt-组装)
  - [可靠性工程](#可靠性工程)
- [璇玑（Compass）— Layer B](#璇玑compass--layer-b)
  - [框架自身开发流程](#框架自身开发流程)
  - [Hook 基础设施](#hook-基础设施)
  - [经验库机制](#经验库机制)
- [棱镜（Prism）](#棱镜prism)
- [References 共约层](#references-共约层)
- [设计决策速查](#设计决策速查)

---

## 设计哲学

RedCap 的架构由五项元原则驱动，完整定义见 [`compass/knowledge/design-principles.md`](compass/knowledge/design-principles.md)。以下是它们在架构层面的体现：

| 原则 | 架构体现 |
|------|---------|
| **角色分离** | PM/ARCH/DEV/QA/REVIEW 各执其职，Dispatcher 只调度、不执行 |
| **状态外部化** | 所有流程状态写入 `state.yaml`，进程崩溃后可从断点恢复 |
| **确定性优先** | 关键动作走宿主 Hook（OS 级 shell），不依赖 LLM 记忆 |
| **经验积累** | 踩过的坑结构化为 Lesson 持久化，跨会话防止重踩 |
| **层次清晰** | 用户项目开发（Layer A）与框架自身演化（Layer B）完全分离 |

**核心设计决策**：

| 决策 | 选择 | 理由 |
|------|------|------|
| Agent 通信方式 | CLI 调用（非 API/消息队列） | 零部署成本，与 AI CLI 工具天然对齐 |
| Agent 状态管理 | 无状态，流程状态由 Dispatcher 持有 | 降低耦合，Agent 崩溃不影响流程恢复 |
| 持久化格式 | YAML 文件（非数据库） | 零依赖、Git 可追踪、Agent 可直读写 |
| 通信协议 | outbox 文件写入（主）+ response 正则（兼容） | E2E 验证：outbox 100% 可靠，stdout JSON 0% 遵从 |

---

## 三体架构总览

```
┌──────────────────────────────────────────────────────────────────────┐
│                            RedCap                                      │
│                                                                        │
│  ┌─────────────────────────┐   ┌──────────────────────────────────┐   │
│  │  织机 Loom（Layer A）    │   │  璇玑 Compass（Layer B）          │   │
│  │                          │   │                                  │   │
│  │  为用户项目编织代码        │   │  Cap 的指挥所                    │   │
│  │  Dispatcher + 五角色      │   │  框架演化 + 知识库 + Hook 基建   │   │
│  │  状态机 + E2E 测试        │   │  soul.md（人格连续性）           │   │
│  └─────────┬───────────────┘   └─────────────┬────────────────────┘   │
│            │                                  │                        │
│            │      references/（共约层）        │                        │
│            │   security / code / commit /      │                        │
│            │   hook / communication / constraints│                      │
│            └────────────────┬─────────────────┘                        │
│                             │                                           │
│                  ┌──────────┴──────────┐                               │
│                  │   棱镜 Prism         │                               │
│                  │                     │                               │
│                  │  多视角分析引擎       │                               │
│                  │  高风险决策前评审     │                               │
│                  └─────────────────────┘                               │
└──────────────────────────────────────────────────────────────────────┘
```

**三层边界约定**：
- Loom 不修改 Compass 的规范文件（反向也是）
- Prism 只读取决策上下文，不直接触发 Dispatcher 流程
- references/ 是 Loom 与 Compass 共享的公约，任何层均可引用

---

## 织机（Loom）— Layer A

织机是 RedCap 的执行引擎。用户提出需求，织机负责从需求到可运行代码的完整交付。

```
loom/
├── dispatcher/       ← 调度核心（状态机、适配器、Prompt 模板、防退化配置）
├── roles/            ← 五角色手册（PM、架构师、程序员、QA、Reviewer）
├── tools/            ← Layer A 脚本（Hook 处理器、E2E 测试、on-complete）
└── test-reports/     ← E2E 测试报告
```

### Dispatcher 事件循环

Dispatcher 是**纯调度器**，不写代码、不做设计。它只做三件事：读状态、组 Prompt + 选 Agent、解析返回 + 推进状态。

完整事件循环（每轮 10 步）：

```
┌──────────────────────────────────────────────────────────────────┐
│  0. 防退化重载（按 reload-rules.yaml 刷新关键规范到上下文）         │
│  1. 读 state.yaml + 执行 pending_actions                         │
│  2. ALL_DONE? → 触发 on_ALL_DONE → 结束                          │
│  3. PAUSED?   → 飞书 ask / 终端等待 → 注入回复 → 恢复            │
│  4. *_DONE?   → 查转移表 → 更新 state                            │
│  5. *_WORKING? →                                                  │
│     a. 选 Agent CLI（首选 → Fallback）                            │
│     b. 组装 Prompt（模板 + 变量映射 → 写入 .workflow/）           │
│     c. 获取/创建 Session                                          │
│     d. 执行 CLI（阻塞等待）                                       │
│     e. 读取 outbox/__redcap_status.json（主）/ response 正则（兼容）│
│     f. 归档到 last-result.json + 清理 outbox 状态文件             │
│     g. 交付物完整性校验                                            │
│     h. 触发 Hooks（on_QA_PASS / on_need_revision / …）           │
│     i. 更新 state.yaml（+ pending_actions 原子写入）              │
│     j. 向用户汇报进展                                             │
│  6. → 回到 0                                                      │
└──────────────────────────────────────────────────────────────────┘
```

Agent 路由：每个 Agent 以 `{cli}&{model}` 双维度标识（如 `claude-code&claude-opus-4`）。路由表配置首选 + Fallback 链，连续 2 次失败才切换（防偶发），新步骤自动重置失败计数。

五种启动场景：

| 场景 | 条件 | 入口 |
|------|------|------|
| S0: 全新项目 | 无 `开发手册/` | 初始化 → PM |
| S1: 迭代开发 | `state.yaml` + `ALL_DONE` | 代码库扫描 → PM（增量模式） |
| S2: 中断恢复 | `state.yaml` + 非 `ALL_DONE` | 从断点恢复 |
| S3: 旧版项目 | 有旧版标记文件 | 目录迁移 → S1 |
| S4: 纳管已有项目 | 有代码无 `开发手册/` | 代码库扫描 → 初始化 → PM |

---

### 状态机

```
              ┌──────────────────────────── 正向流程 ──────────────────────┐
              │                                                             │
INIT ──→ PM_WORKING ──→ PM_DONE ──→ ARCH_WORKING ──→ ARCH_DONE           │
                                                              │             │
                 ┌────────────────────────────────────────────┘             │
                 ▼                                                           │
DEV_WORKING ──→ DEV_DONE ──→ QA_WORKING                                    │
                                   │                                        │
              ┌────────────────────┼──────────────────┐                    │
              ▼                    ▼                   ▼                    │
          QA_PASS            root=code           root=design                │
              │              → DEV_WORKING       → ARCH_WORKING             │
              │              root=requirement → PM_WORKING                  │
      ┌───────┴───────┐                                                     │
      │               │                                                     │
 has_next_step   no_next_step                                               │
      │               │                                                     │
      ▼               ▼                                                     │
 ARCH_WORKING   REVIEW_WORKING ──→ REVIEW_PASS ──→ ALL_DONE               │
                      │                                                     │
                REVIEW_FAIL                                                 │
             root=code → DEV_WORKING                                       │
             root=design → ARCH_WORKING                                    │
                      │                                                     │
                      └─────────────────────────────────────────────────────┘

特殊状态：
┌──────────────────────────────────────────┐
│ PAUSED           — 等待用户（飞书/终端）   │
│ SCAN_WORKING/DONE — 迭代代码库扫描        │
└──────────────────────────────────────────┘
```

**关键设计**：
- 状态 + 转移规则存储在 YAML 文件中，不硬编码 — 流程变更只改配置
- 所有状态写入 `state.yaml`，进程崩溃后可从断点恢复
- Hooks 与状态转移分离：转移决定"去哪"，Hooks 决定"还要做什么"
- QA 回退三分法：`root_cause=code` → DEV、`design` → ARCH、`requirement` → PM，精准回退
- 级联升级：Agent blocked → L1（PM Agent 决策）→ L2（用户决策），分层减少用户打扰

---

### 通信协议

#### 请求-响应流

```
Dispatcher                              Agent (CLI)
    │                                       │
    │──── CLI 调用 + Prompt 文件 ──────────→│
    │                                       │
    │     （Agent 执行任务、写交付物…）       │
    │                                       │
    │←── 交付物文件 + outbox/__redcap_status.json ──│
    │                                       │
    │  读取 outbox JSON ──→ 归档 last-result.json   │
    │  校验交付物 ──→ 触发 Hooks                    │
    │  更新 state.yaml                              │
```

#### `__redcap_status` JSON Schema

```jsonc
{
  "status": "completed",           // 必填：completed|failed|blocked|need_user|need_revision
  "summary": "用户管理模块完成",    // 必填：一句话摘要
  "deliverables": [                // 必填：产出文件列表（Dispatcher 据此校验完整性）
    "dev/outbox/用户管理模块.md"
  ],
  "lesson": {                      // 可选：新发现的经验
    "title": "…", "scenario": "…", "rule": "…"
  },
  "escalation": {                  // 仅 blocked 时必填
    "level": "L1", "target_role": "pm", "question": "…"
  },
  "revision": {                    // 仅 need_revision 时必填
    "root_cause": "design",        // code→DEV | design→ARCH | requirement→PM
    "description": "接口设计缺少分页字段"
  }
}
```

#### 三级传递策略

| 通道 | 机制 | 何时用 |
|------|------|--------|
| **方案 A（主通道）** | Agent 写入 `{role}/outbox/__redcap_status.json` | 正常情况（E2E 验证 100% 可靠） |
| **方案 B（兼容通道）** | 从 Agent 回复文本正则提取 JSON | 旧 Agent 兼容 |
| **方案 C（兜底）** | 读取 `.workflow/last-result.json` | 断点恢复 / 前两者均失败 |

#### 交付物协议

```
命名：{角色目录}/outbox/{步骤号}-{交付物名称}.md
规则：
  ✅ 必须自包含（下游无需回溯源角色草稿）
  ✅ 写入后锁定（除非被回退，源角色不应修改 outbox 文件）
  ✅ 文件头含步骤编号 + 生成时间 + 源角色标识
```

> A2A 通信（Agent 间直接对话，用于多轮讨论达成共识）见 [`compass/knowledge/a2a-communication.md`](compass/knowledge/a2a-communication.md)。

---

### 角色系统 + Prompt 组装

#### 五个角色

| 角色 | 核心职责 | 交付物 |
|------|---------|--------|
| **产品经理（PM）** | 意图澄清（苏格拉底提问法）→ 需求文档 | `pm/outbox/需求文档.md` |
| **架构师（ARCH）** | 技术框架设计 → 分步模块设计 | `arch/outbox/分步设计索引.md` + 各步模块设计 |
| **程序员（DEV）** | 按模块设计编码 + 自测 | 代码文件 + `dev/outbox/自测报告.md` |
| **测试 QA** | 验证代码 vs 设计 vs 需求 | `qa/outbox/测试报告.md` |
| **审查员（REVIEW）** | 最终交叉审查 | 审查报告 |

**为什么 5 个角色而非 3 个？** PM 与 ARCH 分离确保需求分析不被技术实现干扰；DEV 与 QA 分离确保测试独立性；REVIEW 作为最终门禁交叉检查。

#### Prompt 组装架构

```
┌──────────────────┐     ┌────────────────────────┐     ┌────────────────┐
│  loom/roles/      │     │  loom/dispatcher/        │     │  references/    │
│  */handbook.md    │     │  prompt-templates/       │     │  *.md           │
│  角色行为手册      │     │  *-prompt.md             │     │  全局规范        │
│  "Agent 读什么"   │     │  "Dispatcher 怎么组"     │     │  "所有人守什么"  │
└────────┬─────────┘     └────────┬───────────────┘     └────────┬───────┘
         │                        │                              │
         └──── Prompt 组装 ───────┘──────────────────────────────┘
                     │
                     ▼
         最终 Prompt = System（角色身份 + 手册 + 规范）
                    + Task（场景模板 + 变量替换）
```

变量映射（关键变量）：

| 变量 | 来源 |
|------|------|
| `{{handbook_content}}` | `loom/roles/{role}/handbook.md` |
| `{{user_intent}}` | `state.yaml.user_intent` |
| `{{project_dir}}` | 项目绝对路径 |
| `{{iteration_mode}}` | `new / iterate / onboard` |
| `{{revision_description}}` | 回退时的修订说明 |

每个角色 Prompt 包含多场景变种（新需求 / 恢复 Session / 回退修订 / 迭代增量）—— 通用模板导致场景边界模糊，Agent 容易混淆。

---

### 可靠性工程

RedCap 面对的核心挑战：**LLM 在长对话中的 attention 衰减导致指令遵从率下降**。

#### 四层防御架构

| 层 | 机制 | 可靠性 | 实现方式 |
|----|------|--------|---------|
| **Layer 0** | 宿主 Hooks（OS 级 shell） | **100%** | 绕过 LLM，宿主程序直接执行 |
| **Layer 1** | 系统级指令（每轮重注入） | ~30-50% 补救 | copilot-instructions.md / CLAUDE.md |
| **Layer 2** | SKILL.md hooks 表 | ~60-70% | 依赖 LLM attention（会衰减） |
| **Layer 3** | 下次启动审计 | ~95-100% | 新会话 attention 最强 |

#### 机制一：规则防退化（检查点重载）

**问题**：LLM 上下文压缩会保留"有 hooks 机制"的概念但丢失具体触发条件和动作细节。

**解决**：在关键检查点通过 `read_file` 重新加载规范段落，强制刷新被压缩的规则。

```yaml
# loom/dispatcher/reload-rules.yaml
checkpoints:
  on_role_switch:          # 角色切换时（主检查点）
    - SKILL.md §hooks 表
    - SKILL.md §交付物校验
    - SKILL.md §Fallback 路由
  before_commit:
    - references/commit-standards.md
  before_task_complete:
    - SKILL.md §收尾 hooks
  on_paused:
    - SKILL.md §飞书通知
```

成本分析：单次重读 ~500-1000 tokens，完整项目重载累计 ~2000-4000 tokens（≈ $0.02），远低于规则退化的返工成本。

#### 机制二：Pending Actions（待办持久化）

**问题**：Dispatcher 在状态转移后可能遗忘后续动作（如：更新了 `state=QA_PASS` 但忘了执行 git commit）。

**解决**：状态更新与 pending_actions 在**同一次 YAML 写入操作中原子提交**，下轮循环自动检查并执行。

```
状态转移（步骤 5i）:

state.yaml 单次原子写入:
  current_state: QA_PASS          ← 状态更新
  pending_actions:                 ← 待办清单（同批次写入）
    - type: run_script
      command: bash loom/tools/redcap-on-qa-pass.sh …
    - type: check_lesson
      hint: QA 通过，检查是否有新经验

下轮循环步骤 1:
  遍历 pending_actions → 逐项执行 → 清空
```

⚠️ **铁律**：`pending_actions` 与 `current_state` 必须同批次写入。禁止先写 state 再"记得"补写——这正是递归遗忘的根源。

| 转移目标 | 自动填充的 pending_actions |
|---------|---------------------------|
| → `QA_PASS` | `run_script`（git commit） |
| → `ALL_DONE` | `run_script`（清理 + 摘要 + 飞书通知） |
| → `PAUSED` | `feishu_ask`（阻塞等待用户回复） |
| 事件 `need_revision` | `check_lesson`（经验检查） |
| QA 失败 > 3 次 | `feishu_ask`（循环失败警报） |

---

## 璇玑（Compass）— Layer B

璇玑是 Cap 的指挥所，管理框架自身的演化。它独立于 Loom 运行，有自己的规范（CONTRIBUTING.md）、知识库（knowledge/）、工具集（tools/）和 Hook 基础设施。

```
compass/
├── soul.md          ← Cap 人格 + 复活协议（跨会话人格连续性）
├── CONTRIBUTING.md  ← 框架自身开发的唯一权威规范
├── CHANGELOG.md
├── knowledge/       ← lessons.md, design-principles.md, host-reliability.md,
│                       hooks-*.md, model-capability-matrix.yaml, explore-notes.md, …
├── tools/           ← 飞书通知、Claude/Gemini/Kimi Hook 处理器
├── docs/            ← 设计文档和技术调研（baton-design.md 等）
└── .workflow/       ← 运行时状态（agent-registry.yaml, blocked-*.md 等）
```

### 框架自身开发流程

框架变更**不走 Dispatcher**，由 AI Agent 直接编辑框架文件，流程如下：

```
0. PM Gate — 原文落盘 + 需求澄清锁定（防需求失真）
1. 读 compass/CONTRIBUTING.md — 获取完整规范
2. 读 compass/knowledge/lessons.md — 检查已知陷阱
3. 影响 > 20 行时 → Red Teaming（独立 critic Agent 对抗审查）
4. 执行变更
5. 检查影响范围（CONTRIBUTING.md §联动表）
6. 经验沉淀自检：是否有新 Lesson？
7. git commit（Conventional Commit 中文格式）
8. 飞书通知 + Stop Hook 触发独立架构评审
```

**Layer B 三大质量保障机制**：

| 机制 | 触发条件 | 作用 |
|------|---------|------|
| **§长任务并行裂变** | 分析目标 ≥5 个独立模块 | 拆解无耦合子任务，并行 Agent 执行，只汇收结论 |
| **§自身变更 Red Teaming** | 改动核心文件且 >20 行 | 独立 critic Agent 对抗审查后再 commit |
| **§PM Gate** | 任意需求（含单 Q） | 原文即时落盘 → PM 澄清 → 用户确认锁定 → 执行 |

### Hook 基础设施

RedCap 既是开发工具，也是被开发的对象。Hook 架构分两层，部署位置和触发逻辑完全分离：

```
┌────────────────────────────────────────────────────────────────┐
│  Layer A Hook — 为用户项目服务                                    │
│                                                                  │
│  部署位置：~/.claude/settings.json（用户级，所有项目生效）         │
│  核心挑战：cwd 在目标项目，但脚本在 RedCap repo                   │
│  解决方案：用户级全局 Hook + state.yaml 存在性检测 + 三重过滤      │
│                                                                  │
│  SessionStart → 捕获 HEAD + 清理僵尸标记                          │
│  Stop         → state.yaml 存在?                                 │
│                 → ALL_DONE?                                      │
│                   → 本 session 未通知?                           │
│                     → loom/tools/redcap-layerA-stop.sh           │
│  SessionEnd   → 清理 session 标记                                 │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│  Layer B Hook — 为 RedCap 框架自身服务                            │
│                                                                  │
│  部署位置：.claude/settings.json（项目级，仅 RedCap repo 生效）   │
│  InstructionsLoaded → 捕获初始 HEAD                              │
│  Stop → ① 独立架构评审（新 Agent，零上下文污染）                   │
│         ② 检测新 commit → 飞书通知                               │
└────────────────────────────────────────────────────────────────┘
```

宿主覆盖状态：

| 宿主 | Layer A | Layer B |
|------|---------|---------|
| Claude Code | ✅ 用户级 Hook | ✅ 项目级 Hook |
| Gemini CLI | ✅ 已部署 | ✅ 已部署 |
| Copilot CLI | ✅ 仓库级 `.github/hooks/` | ✅ 已部署 |
| Kimi CLI | ✅ SessionStart/Stop | ✅ 已部署 |
| VS Code Copilot | ❌ 无 Hook 支持 | — 退守 Layer 2+3 兜底 |

> Hook 详情见 `compass/knowledge/hooks-*.md`，部署指南见 `compass/knowledge/layerA-hook-deploy.md`。

**核心设计洞察**：将多步副作用封装为单一 shell 脚本（如 `redcap-on-complete.sh`），LLM 只需记住"调一个脚本"而非"记住 N 个步骤"。

### 经验库机制

**问题**：AI Agent 在当前对话中踩坑，新会话启动时同样的坑会被再次踩中。

**解决**：三层存储架构

```
compass/knowledge/lessons.md（活跃层，< 300 行）  ← 每次启动自动加载
         │
         │  score < 1.0 时自动归档
         ▼
compass/knowledge/lessons-archive.md（归档层）    ← 按需手动查阅
         │
         │  复现时复活
         ▼
lessons.md
```

归档评分公式：

```
score = impact_weight × recency_decay × frequency_boost

impact_weight:   high=4, medium=2, low=1
recency_decay:   <6mo=1.0, 6-12mo=0.6, >12mo=0.3
frequency_boost: min(复现次数, 5) / 5 → [0.2, 1.0]

score ≥ 1.0 → 保留活跃层 | score < 1.0 → 归档
豁免：impact=high 永不自动归档（框架底线必须持续可见）
```

---

## 棱镜（Prism）

棱镜是多视角分析引擎，用于高风险决策前的对抗性验证。

```
prism/
├── protocol.md     ← 棱镜协议（独立取样 + 议事两族）
├── modes/          ← 运行模式配置（explore/redteam/test/council）
├── roles/          ← 分析角色（挑战者、审查员、旧错者、运筹者等）
├── reports/        ← 历史运行报告
└── tools/          ← prism-dispatch-check.sh, prism-archive-check.sh
```

### 两族协议

```
需要独立视角，结论不相互影响？
  ├─ YES → 独立取样协议（explore / redteam / test）
  └─ NO，需要多轮交互讨论？
        └─ YES → 议事协议（council）
```

**独立取样协议**（explore / redteam / test）：
- 各 Agent 全程独立，Dispatch Firewall 强制隔离
- 流程：Frame（冻结任务）→ Dispatch（分发）→ Collect（收集）→ Adjudicate（裁决）
- 适用：对同一问题收集多个独立观点，防止群体思维

**议事协议**（council）：
- Agent 之间多轮交互，前一轮输出对后续 Agent 可见
- 适用：需要多轮讨论才能收敛的复杂决策

每个 Agent 输出标准 Schema：

```jsonc
{
  "agent": "<model>",
  "role": "<分析视角或对抗职能>",
  "conclusion": "<核心结论，50字内>",
  "confidence": "high|medium|low",
  "blockers": ["[BLOCKING/CRITICAL/MAJOR] <问题>", …],
  "actions": ["<行动>", …],
  "blind_spots": "<本视角可能遗漏的角度，无则 null>"
}
```

**与 PM Gate 的关系**：
- PM Gate 已锁定需求 → Prism 运行"验证模式"：只验证方案可行性，不重开需求决策
- PM Gate 未锁定 → Prism 可探索，但不能代替 PM Gate 做决策

---

## References 共约层

```
references/
├── security-rules.md         ← 安全铁律（注入每个 Agent Prompt）
├── code-standards.md         ← 代码规范
├── commit-standards.md       ← Git commit 规范（Conventional Commit 中文格式）
├── communication-protocol.md ← __redcap_status 通信协议完整 Schema
├── hook-standards.md         ← Hook 编写规范
├── agent-constraints.md      ← 子 Agent 共享约束（防退化、禁止操作等）
└── task-report-template.md   ← 任务完成报告标准模板（每次任务交付时使用）
```

这是 Loom 与 Compass 的**公约层**：
- Loom 通过 Prompt 注入将这些规范传递给每个 Agent
- Compass 在框架自身开发时遵守这些规范
- Prism 在分析时可引用这些规范作为评判基准

---

## 设计决策速查

| 维度 | 决策 | 理由 |
|------|------|------|
| **架构分层** | Loom / Compass / Prism 三层独立 | 用户项目开发 vs 框架演化 vs 决策评审，关注点完全不同 |
| **Dispatcher 角色** | 纯调度器，不写代码 | 职责单一，防止 Dispatcher 越权干扰 Agent 工作 |
| **状态持久化** | YAML 文件 | 零依赖、Git 可追踪、Agent 可直读写 |
| **Agent 通信** | outbox 文件写入（主）| E2E 验证：文件写入 100% 可靠，stdout 嵌入 0% |
| **回退策略** | 按 root_cause 三分类 | 精准回退到负责人，避免盲目重启浪费 token |
| **Hook 分层** | Layer A（用户级）+ Layer B（项目级） | 两种 Hook 目的不同，部署位置必须分离 |
| **经验库分层** | 活跃层 + 归档层 | 防止 lessons.md 膨胀挤占上下文 |
| **Prism 隔离** | Dispatch Firewall | 独立取样要求各 Agent 结论不相互污染 |
| **规则防退化** | 检查点 read_file 重载 | 成本 $0.02，远低于规则退化返工成本 |
| **Pending Actions** | 与 state 原子写入 | 防止"更新状态但忘记后续动作"的递归遗忘 |

---
