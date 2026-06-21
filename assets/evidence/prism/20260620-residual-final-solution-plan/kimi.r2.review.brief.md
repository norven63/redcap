# Prism Shared Brief

You are Prism, a heterogeneous opposition reviewer for the main executing AI.

Your job is not to approve the work. Your job is to find the strongest reason
the main AI may be wrong, self-deceived, incomplete, or drifting from the user's
real intent.

Allowed providers are only Kimi and Claude Code. Do not suggest adding other
providers.

Return a short structured review with:

- verdict: pass | concern | block
- confidence: low | medium | high
- reality_delta
- main_concern
- top_risks: max 3
- missing_evidence: max 3
- minimum_fix
- anti_loop_signal
- user_intent_alignment

Core question:

Did the user's intended reality actually change, or did the main AI only create
a convincing explanation, document, report, ledger, receipt, or plan?

--- PROVIDER PROMPT ---

# Kimi Prism Review Prompt

Use this prompt for Kimi.

## Role

You are the long-context Prism reviewer.

## Runtime Boundary

You are running through Kimi Code CLI in non-interactive prompt mode.

- Default to using only the text included in this prompt.
- Do not inspect files unless this prompt contains an `AUTHORIZED FILE ACCESS`
  section.
- If `AUTHORIZED FILE ACCESS` is present, read only the generated bundle JSON
  named in that section. Do not inspect the original source paths directly.
- Do not run commands.
- Do not call tools.
- Do not ask follow-up questions.
- If evidence is missing from the prompt text or authorized bundle, report it
  as missing evidence instead of fetching more files.

Focus on:

- User original intent.
- Historical drift.
- Narrative self-consistency that hides non-completion.
- Missing context.
- Anti-loop signals.
- Whether the main AI has rewritten the user's problem into an easier task.

## Review Bias

Be suspicious of:

- "We documented the boundary" as completion.
- "We generated evidence" as completion.
- "We deferred the hard part" as completion.
- "This was already covered" without concrete reality change.
- Large context dumps that conceal the missing action.

## Output

Return the Prism review shape from `schemas/prism-review.schema.json` with
`provider` set to `kimi`.

--- REVIEW REQUEST FILE ---

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260620-residual-final-solution-plan/request.r2.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "复审 RedCap 残留待完善项最终解决方案书第二轮",
  "review_mode": "strategy_and_solution_plan_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 0,
  "known_constraint_count": 0
}

--- REVIEW REQUEST JSON ---

{
  "task": "复审 RedCap 残留待完善项最终解决方案书第二轮",
  "review_mode": "strategy_and_solution_plan_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "language_policy": "中文优先；必要专有名词首次出现时给中文解释。",
  "user_intent": "Norven 要求只完成方案书编写，不执行开发实现。方案书必须汇总尚未解决、残留 todo、有待完善的任务，逐项制定最终解决方案，并且每个方案都不能引入新问题、不能降级或绕过、不能只留下文档残留，必须经过 Prism 深度评审并达成一致。",
  "main_claim": "第一轮 Prism 评审未通过。Cap 已采纳 Kimi 的 concern 和 Claude Code 的 block：补充全方案不变量、逐项可执行验收矩阵、Norven 决策点、实施顺序依赖，并把方案摘要内嵌到本请求，避免评审方无法读取本地文件。",
  "changed_reality": [
    "方案书新增 RSP-00 全方案不变量，把完成口径和文档替代实现防线提升为所有条目的前置约束。",
    "方案书新增 RSP-19 到 RSP-22，覆盖 redcap 命令面漂移、Codex CLI 插件/配置噪声、advisory-stop degraded 健康巡检、E2E 报告与验收合同映射。",
    "方案书新增可执行验收矩阵：每个 RSP 均有最低正向验收、最低负向探针和证据位置。",
    "方案书新增 Norven 人工决策点：unknown 历史目录删除、公共/私有知识边界、Cap 私人人格材料迁移、真实外部项目样本选择。",
    "方案书调整实施顺序：RSP-00/RSP-11/RSP-12 先固化，再处理 Stop/Hook、provider/Prism、Loom/长任务、知识/人格、迁移/E2E/长期样本。"
  ],
  "draft_plan": "assets/docs/residual-todo-final-solution-plan.md",
  "reviewable_plan_digest": {
    "scope": "本轮只写方案书，不做实际开发，不关闭运行时任务，不声明 RedCap 完整复活终局完成。",
    "invariants": [
      "每个条目实施时必须证明真实行为改变；方案、文档、账本、评审回执不能单独关闭问题。",
      "每个条目必须有至少一个正向验收和一个负向探针；无法设置负向探针时必须说明并由 Prism 复核。",
      "每个完成声明必须区分方案完成、代码实现、样本通过、外部项目通过、长期成熟。",
      "不可逆删除、公开发布、私人人格、公共知识晋升和跨机器迁移必须保留 Norven 决策点。"
    ],
    "items": [
      "RSP-00：全方案不变量，防止完成口径污染和文档替代实现。",
      "RSP-01：Stop 建议型检查误伤治理，正向验收 advisory-stop self-check，负向探针为原问题主轴偏移必须失败。",
      "RSP-02：Hook 语义判断统一链路，正向验收 gate semantic policy，负向探针为纯问题/反问/无授权不得通过 implementation。",
      "RSP-03：Kimi 路径、超时、文件访问稳定性，正向验收基础调用/续接/限定文件读取，负向探针为路径错误/权限阻塞/超时分类失败。",
      "RSP-04：Prism 通信边界，正向验收细节落文件摘要进上下文，负向探针为 raw 大输出不得进入 Cap 主上下文。",
      "RSP-05：Loom 真实项目角色链质量，正向验收外部项目角色链，负向探针为单 AI 伪装多角色必须失败。",
      "RSP-06：Loom 会话接续，正向验收 session_id 稳定，负向探针为 session_id 缺失/重复/漂移必须失败。",
      "RSP-07：自我净化自然触发，正向验收真实任务后生成候选或 no-candidate 理由，负向探针为私人人格候选进入公共仓库必须失败。",
      "RSP-08：知识召回影响决策，正向验收命中知识被计划/实现/验收引用，负向探针为无关命中或 0 命中无理由必须失败。",
      "RSP-09：项目级 .redcap 安装迁移，正向验收外部项目安装/运行/卸载/重装，负向探针为污染 RedCap 源仓库必须失败。",
      "RSP-10：长任务循环机制，正向验收进入/推进/停止条件，负向探针为同根因三轮失败继续重跑必须失败。",
      "RSP-11：完成口径污染防线，正向验收阶段完成不会通过终局完成声明，负向探针为文档完成冒充终局完成必须失败。",
      "RSP-12：文档即完成旧疾防线，正向验收完成项指向真实行为变化，负向探针为只有文档/账本/报告不得关闭运行问题。",
      "RSP-13：E2E 缓存 unknown 目录治理，正向验收分类、dry-run、执行清单完整，负向探针为未分类 unknown 静默删除必须失败。",
      "RSP-14：E2E 报告可读性，正向验收报告按能力项输出，负向探针为只报告页面可访问不得通过。",
      "RSP-15：Forge/redcap-arsenal 边界，正向验收公共晋升脱敏去重追加，负向探针为私人人格/凭据/未脱敏路径进入公共库必须失败。",
      "RSP-16：Cap 复活手册迁移，正向验收 CAP_HOME 与 ~/.cap 两种路径可加载，负向探针为公共仓库读取私人人格正文必须失败。",
      "RSP-17：旧 RedCap 15 项设计成熟度，正向验收成熟度矩阵，负向探针为合同覆盖冒充长期成熟必须失败。",
      "RSP-18：外部真实项目长期样本，正向验收三类真实外部项目均产出 RedCap 能力改进证据，负向探针为只交付目标应用不沉淀 RedCap 能力必须失败。",
      "RSP-19：runtime/bin/redcap 命令面漂移，正向验收 help 和子命令回归，负向探针为删除旧参数或破坏别名必须失败。",
      "RSP-20：Codex CLI 插件/配置噪声，正向验收隔离 Codex HOME 和禁用插件样本，负向探针为宿主插件噪声污染 E2E 必须失败。",
      "RSP-21：advisory-stop degraded 健康巡检，正向验收 degraded 触发健康告警和升级，负向探针为 degraded 被当成正常通过必须失败。",
      "RSP-22：E2E 报告与验收合同映射，正向验收报告字段映射验收合同，负向探针为报告字段缺少合同映射必须失败。"
    ],
    "implementation_order": [
      "0：先固化 RSP-00，并把 RSP-11/RSP-12 作为所有条目的完成口径不变量。",
      "1：处理 RSP-01/RSP-02/RSP-21，先稳定 Stop/Hook 判断系统。",
      "2：处理 RSP-03/RSP-04/RSP-20，先稳定 provider、Prism 和 Codex CLI 隔离。",
      "3：处理 RSP-05/RSP-06/RSP-10/RSP-19，推进 Loom、长任务和命令面主干。",
      "4：处理 RSP-07/RSP-08/RSP-15/RSP-16，推进知识、自我净化、公共/私有边界。",
      "5：处理 RSP-09/RSP-13/RSP-14/RSP-17/RSP-18/RSP-22，推进迁移、缓存、报告、成熟度和真实项目长期验证。"
    ],
    "norven_decision_points": [
      "RSP-13 unknown 历史目录是否允许删除、保留多久、哪些目录永久保留。",
      "RSP-15 哪些经验可进入公共 Forge 或 redcap-arsenal，哪些必须 keep_private。",
      "RSP-16 Cap 私人人格材料是否迁移、复制或纳入 CAP_HOME 版本控制。",
      "RSP-18 真实外部项目样本选择、是否对外发布、是否涉及真实用户或业务数据。"
    ]
  },
  "review_questions": [
    "第二轮方案是否已经覆盖第一轮 Kimi 指出的缺口：每项有命令/探针/证据方向，RSP-11/RSP-12 成为全方案不变量，实施顺序与依赖明确，Norven 决策点明确？",
    "第二轮方案是否解决 Claude Code 第一轮 block：即使无法读取本地文件，也能通过内嵌摘要实质审查方案核心内容？",
    "当前方案是否仍存在降级、绕过、文档替代实现或引入新问题的风险？如果有，请给出必须修复的最小改动。",
    "当前方案是否可以作为后续实施计划的依据？如果不能，请明确 block 条件。"
  ],
  "required_response": {
    "verdict_values": [
      "pass",
      "concern",
      "block"
    ],
    "must_include": [
      "coverage_gaps",
      "degradation_or_bypass_risks",
      "new_problem_risks",
      "ordering_concerns",
      "minimum_fixes",
      "consensus_conditions"
    ]
  },
  "file_access": {
    "mode": "bounded-read",
    "allowed_paths": [
      "assets/docs/residual-todo-final-solution-plan.md",
      "assets/contracts/open-loop-closure-queue.json",
      "assets/contracts/next-redcap-development-queue.json",
      "assets/contracts/known-issues-queue.json",
      "assets/contracts/advisory-stop.json",
      "assets/contracts/terminal-goals.json",
      "assets/contracts/complete-revival-e2e-acceptance-design.json",
      "assets/docs/cap-revival-manual.md",
      "assets/docs/redcap-revival-doctrine.md",
      "assets/docs/long-task-contract.md"
    ],
    "max_files": 10,
    "max_bytes_per_file": 260000,
    "max_total_bytes": 1200000,
    "purpose": "只评审方案书是否覆盖残留问题、是否满足不降级和不引入新问题要求；不执行开发实现。"
  },
  "non_goals": [
    "不要求 provider 编写代码。",
    "不要求 provider 关闭任何队列项。",
    "不允许 provider 用新的泛泛治理文件替代具体方案缺口。",
    "不把方案书完成称为实际问题已经解决。"
  ]
}


--- AUTHORIZED FILE ACCESS ---

mode: bounded-read

Authorized bundle JSON: /Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260620-residual-final-solution-plan/kimi.r2.review.brief.files.json

Bundle sha256: 5a50b63cee6cdd47605704649878cfb8e133411dfbcc46fb966b2af8f71319ef

Rules:

- You may read only this generated bundle JSON if file evidence is needed.

- Do not inspect the original source paths directly.

- Do not run commands.

- If the bundle is insufficient, report missing evidence instead of fetching more files.

