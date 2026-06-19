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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260611-redcap-design-structure-logic-review-rerun/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "整体评审当前新RedCap的设计思路、目录结构、逻辑实现，并判断需要改进、调整、优化和尚未执行完毕的任务。",
  "review_mode": "design_structure_logic_full_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 0,
  "known_constraint_count": 0
}

--- REVIEW REQUEST JSON ---

{
  "schema_id": "redcap-prism-review-request",
  "task_id": "20260611-redcap-design-structure-logic-review-rerun",
  "task": "整体评审当前新RedCap的设计思路、目录结构、逻辑实现，并判断需要改进、调整、优化和尚未执行完毕的任务。",
  "language_policy": "中文优先；专有名词首次出现请给中文解释。",
  "review_mode": "design_structure_logic_full_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "user_intent": "Norven要求回到此前未完成的事项：请和棱镜一起整体review当前新RedCap的设计思路、目录结构、逻辑实现，务必做到100%程度的细致review，并评估当前是否有需要改进、调整、优化和尚未执行完毕的任务。",
  "main_claim": "此前整体评审确实没有完成；当前新RedCap已经具备迁移可用阶段的核心运行与检查能力，但完整复活终局仍未关闭。本轮需要评估设计、目录与逻辑是否足够健康，以及哪些遗留任务必须继续推进。",
  "cap_current_answer_to_user_question": "是的，这件事之前没有完成。旧评审的棱镜合并结论是concern，resolution为escalated，只局部修复了skip-host-hook-audit语义等问题，不能当作整体评审闭环。",
  "changed_reality": [
    "本轮已经创建独立棱镜会话 assets/evidence/prism/20260611-redcap-design-structure-logic-review-rerun/session.json。",
    "本轮生命周期包已通过 runtime/bin/redcap lifecycle check。",
    "本轮棱镜门禁返回 required，要求 Kimi 和 Claude Code 两方评审。",
    "任务事实已把 redcap-design-structure-logic-review 从旧 escalated 状态推进为 in_progress。",
    "本轮评审请求放入 assets/evidence/prism/.../request.json，避免继续把一次性过程文件塞进 assets/contracts/。"
  ],
  "non_goals": [
    "不声明RedCap完整复活终局完成。",
    "不批量阅读旧RedCap仓库。",
    "不把本轮评审本身当成端到端验收器已经执行。",
    "不把文档、清单、生命周期包、棱镜评审或状态面通过单独当作终局完成证据。"
  ],
  "current_structure": {
    "top_level": [
      "README.md",
      "AGENTS.md",
      ".codex/",
      "runtime/",
      "assets/",
      ".gitignore"
    ],
    "running_unit": "runtime/ 是运行单元，承载命令入口、核心检查器、宿主适配器、棱镜协议与调度器。",
    "asset_unit": "assets/ 是资产单元，承载契约、文档、知识、证据、考古资料、迁移清单和可视化材料。",
    "host_entry": ".codex/ 是Codex宿主入口配置；规则逻辑应回到 runtime/host-adapters/ 与 runtime/core/。",
    "runtime_subdirs": [
      "runtime/bin",
      "runtime/bootstrap",
      "runtime/core",
      "runtime/host-adapters",
      "runtime/prism"
    ],
    "asset_subdirs": [
      "assets/archaeology",
      "assets/contracts",
      "assets/docs",
      "assets/evidence",
      "assets/knowledge",
      "assets/manifests",
      "assets/visuals"
    ]
  },
  "current_positive_evidence": [
    {
      "scope": "生命周期与棱镜门禁",
      "evidence": "runtime/bin/redcap lifecycle check --packet assets/evidence/lifecycle/redcap-design-structure-logic-review-rerun-lifecycle.json 通过；runtime/bin/redcap gate ... --lifecycle-packet ... 返回 required 且生命周期检查 ok。"
    },
    {
      "scope": "目录结构",
      "evidence": "runtime/bin/redcap layout-check 通过；根目录仍保持运行单元 runtime/、资产单元 assets/、宿主入口 .codex/ 的收敛结构。"
    },
    {
      "scope": "已知问题队列",
      "evidence": "runtime/bin/redcap known-issues-queue check 与 known-issues-order check 通过；KI-00 到 KI-03 为 verified，KI-04 与 KI-05 为 deferred_user_supervised。"
    },
    {
      "scope": "旧RedCap 360扫描",
      "evidence": "assets/archaeology/shards/old-redcap-360-scan-merge.json 含15项portable_designs；runtime/bin/redcap scan-conclusion check 通过。"
    },
    {
      "scope": "15项优秀设计覆盖",
      "evidence": "runtime/bin/redcap full-revival-amendment check 通过，required_design_count=15，scan_portable_count=15。"
    },
    {
      "scope": "Loom角色化工程工作流",
      "evidence": "runtime/bin/redcap loom-workflow check 通过，角色覆盖 product_manager、architect、developer、tester、reviewer、cap_orchestrator，阶段覆盖需求、架构、实现、测试、评审、变更、收尾、阻塞。"
    },
    {
      "scope": "项目级运行时隔离",
      "evidence": "runtime/bin/redcap boundary-consumers check 通过，外部项目写入自己的 .redcap/，不污染RedCap仓库。"
    },
    {
      "scope": "宿主钩子与棱镜调度边界",
      "evidence": "runtime/bin/redcap host-hook-audit 通过；Codex项目钩子覆盖 UserPromptSubmit、PreToolUse、PostToolUse、SessionStart、Stop；棱镜provider通过dispatcher-enforced模式。"
    },
    {
      "scope": "知识入口",
      "evidence": "runtime/bin/redcap knowledge-gateway check 通过，默认读取为index-only。"
    }
  ],
  "current_negative_evidence": [
    {
      "scope": "整体自检",
      "evidence": "runtime/bin/redcap check 当前返回非零，因为状态面发现非终局开放任务 redcap-design-structure-logic-review。"
    },
    {
      "scope": "完整复活前置验收",
      "evidence": "runtime/bin/redcap complete-revival-check 当前返回非零，失败原因是 status、revive、formal_usable 未通过，且状态面显示仍有非终局开放任务。"
    },
    {
      "scope": "终局目标",
      "evidence": "RedCap 完整复活父任务仍为 in_progress，current_level=migration_usable，terminal_verified=false；不得把阶段成果说成终局完成。"
    },
    {
      "scope": "端到端验收器",
      "evidence": "assets/contracts/complete-revival-e2e-acceptance-design.json 的 status 为 design_complete_not_executed；KI-04 仍 deferred_user_supervised。"
    },
    {
      "scope": "终局关闭流程",
      "evidence": "KI-05 仍 deferred_user_supervised，必须在端到端验收后才允许开展。"
    },
    {
      "scope": "自开发运行证据忽略策略",
      "evidence": "runtime/bin/redcap status --json 显示 self-development 模式下 project_runtime_gitignore_ok=false，路径为 assets/evidence/.gitignore；需要判断这是自开发例外下可接受的状态提示，还是应修复为健康项。"
    },
    {
      "scope": "过程文件放置",
      "evidence": "历史上已有多个 lifecycle 与 prism-request 文件在 assets/contracts/；本轮 request 已放入 assets/evidence/prism/.../request.json，但仍需判断既有过程文件是否需要迁移或保留策略。"
    },
    {
      "scope": "工作区状态",
      "evidence": "git status --short 显示存在多处已修改和未跟踪文件；本轮评审不得把未提交状态当作完成证据，但应判断是否影响目录与逻辑健康。"
    }
  ],
  "commands_observed": [
    "runtime/bin/redcap status --json",
    "runtime/bin/redcap task-facts summary",
    "runtime/bin/redcap layout-check",
    "runtime/bin/redcap known-issues-queue check",
    "runtime/bin/redcap known-issues-order check",
    "runtime/bin/redcap check",
    "runtime/bin/redcap revival-queue check",
    "runtime/bin/redcap complete-revival-check",
    "runtime/bin/redcap full-revival-amendment check",
    "runtime/bin/redcap loom-workflow check",
    "runtime/bin/redcap host-hook-audit"
  ],
  "review_questions": [
    "当前设计思路是否健康：RedCap是否已经从旧病的文档/回执/报告循环，转向可运行、可检查、可裁决的工作流机器？",
    "目录结构是否健康：runtime/与assets/二分是否仍然收敛，assets/contracts/是否过载，运行证据与过程文件是否应继续迁移到assets/evidence/？",
    "逻辑实现是否健康：门禁、宿主钩子、棱镜调度、生命周期、任务事实、终局目标、运行边界、Loom、知识入口之间是否存在重复真相源或互相打架？",
    "当前最应该改进、调整或优化的地方是什么？请按阻断、必须优先、可排期、可接受权衡分类。",
    "尚未执行完毕的任务有哪些？哪些属于RedCap完整复活终局前置，哪些只是后续增强？",
    "是否应把本轮整体评审任务在完成后标记为 verified，从而解除状态面中的非终局开放任务？如果不能，阻塞条件是什么？"
  ],
  "expected_output": {
    "format": "json",
    "required_fields": [
      "verdict",
      "confidence",
      "blocking_findings",
      "important_findings",
      "directory_findings",
      "logic_findings",
      "unfinished_tasks",
      "recommended_next_actions",
      "can_mark_review_task_verified",
      "review_task_blocker_if_any"
    ],
    "verdict_options": [
      "pass",
      "concern",
      "block"
    ]
  }
}
