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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260617-long-task-contract/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "评审 RedCap 长任务父目标循环机制：把 E2E 中证明有效的持续推进、防盲循环、收敛诊断能力抽成通用长任务合同，但默认关闭，只在高风险、多阶段、自开发、E2E、跨角色或用户显式长跑任务中启用。",
  "review_mode": "design_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 0,
  "known_constraint_count": 5
}

--- REVIEW REQUEST JSON ---

{
  "task": "评审 RedCap 长任务父目标循环机制：把 E2E 中证明有效的持续推进、防盲循环、收敛诊断能力抽成通用长任务合同，但默认关闭，只在高风险、多阶段、自开发、E2E、跨角色或用户显式长跑任务中启用。",
  "user_intent": "Norven 认可长任务持续 loop 的价值，但明确要求不能把所有小任务都拖进重型模式；机制必须和棱镜充分评审，防止本次 E2E 无限循环的恶果复发。Norven 也询问当前 Codex 目标 blocked 是否代表任务未完成、是否需要消除，以及是否会阻止新任务。",
  "main_claim": "Codex 目标 blocked 只是外部目标工具的状态，不等于 RedCap 工程验收失败，也不应成为 RedCap 长任务机制的单点依赖。RedCap 应新增一个通用长任务合同检查器：用显式进入条件、推进证据、停止条件、仲裁条件和防盲重跑规则来决定何时持续推进、何时停止修机制、何时请求人类决策。",
  "changed_reality": [
    "第 45 轮 E2E 已用 completion-marker、iteration-verdict、final-prism-review 和 convergence-diagnosis 证明工程试用可用，不是因用户叫停而伪完成。",
    "Codex 目标功能当前显示 blocked，说明它不能作为可靠的活跃父任务状态来源；但这个状态本身不证明 RedCap 工程验收失败。",
    "E2E 运行机已有 failure-backlog、iteration-verdict、convergence-diagnosis、auto_rerun_allowed 和 source_signature 等防盲循环设计，但这些能力目前主要绑定 complete-revival-e2e，不是通用长任务入口。",
    "需要新增通用 long-task-contract 检查能力，并接入 aggregate check；它只验证长任务合同，不直接接管所有任务执行。"
  ],
  "review_mode": "design_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "known_constraints": [
    "不能清除或篡改 Codex 目标 blocked 状态来制造完成感；除非目标工具本身允许且事实已满足，否则只能把它作为外部状态说明。",
    "不能把长任务循环机制设为默认开启；小任务、纯回答、低风险一步修复必须走 fast-path，不进入重型循环。",
    "不能允许无限自动重跑；当同一阻塞重复、源码或证据签名未变、auto_rerun_allowed=false 或需要人类决策时必须停止。",
    "不能把计划、文档或账本增长当作真实推进；每轮必须有 action_evidence 和 objective_delta。",
    "不能降低原有能力；本机制必须保留持续推进能力，同时增加明确停止和仲裁边界。"
  ],
  "proposed_design": {
    "new_runtime": "runtime/core/long_task_contract.py",
    "new_command": "runtime/bin/redcap long-task check|self-check",
    "contract_file": "assets/contracts/long-task-contract.json",
    "human_doc": "assets/docs/long-task-contract.md",
    "activation_policy": {
      "default": "off",
      "enabled_when_any": [
        "user_explicit_long_run",
        "redcap_self_development_medium_or_higher",
        "external_e2e_or_release_validation",
        "multi_role_loom_workflow",
        "multi_iteration_failure_repair",
        "cross_workspace_or_runtime_boundary_change"
      ],
      "fast_path_when_all": [
        "low_risk",
        "answer_only_or_review_only",
        "single_step_or_small_patch",
        "no_cross_role_no_e2e_no_release_no_self_development"
      ]
    },
    "required_loop_rules_when_enabled": [
      "parent_objective and terminal_acceptance are explicit",
      "non_claimed_boundaries prevent overclaim",
      "each iteration records action_evidence and objective_delta",
      "failure_backlog or equivalent open/closed issue list exists",
      "blind rerun is blocked when source_signature and evidence_signature are unchanged after a structural stop",
      "Cap arbitration is required after repeated same blocker or max_iterations_before_cap_arbitration",
      "human decision is required for policy, secret, destructive, external account, release, or product-scope ambiguity"
    ],
    "completion_boundary": "The contract can say a long task loop is governed or a round is ready to stop; it cannot by itself claim RedCap permanent complete revival."
  },
  "evidence_to_review": [
    "runtime/core/complete_revival_e2e.py",
    "assets/contracts/complete-revival-e2e-acceptance-design.json",
    "runtime/core/check_runner.py",
    "runtime/bin/redcap",
    "assets/evidence/prism/20260616-e2e-convergence-and-external-anchor/request.json",
    "assets/evidence/lifecycle/20260616-e2e-convergence-and-external-anchor-lifecycle.json"
  ],
  "questions_for_prism": [
    "这个设计是否足以解释 Codex 目标 blocked 与 RedCap 工程验收的关系，且不依赖清除外部目标状态？",
    "进入条件是否过宽，会不会导致小任务被强行拖进重型长任务循环？",
    "退出条件和防盲重跑规则是否足以避免本次 E2E 无限循环复发？",
    "是否还需要把该机制接入门禁、生命周期包或 aggregate check，才能避免只停留在文档层？"
  ]
}


--- KIMI FILE ACCESS ---
mode: prompt-only
No file reading is authorized for this review.
