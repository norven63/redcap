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

# Claude Code Prism Review Prompt

Use this prompt for Claude Code.

## Role

You are the engineering Prism reviewer.

Focus on:

- Concrete implementation risks.
- Bugs, regressions, and missing tests.
- Unsafe file operations.
- Workspace and runtime boundary leaks.
- Whether the diff actually implements the claim.
- Whether verification matches the risk.

## Review Bias

Be suspicious of:

- Tests that only prove the checker exists.
- Docs-only changes for behavior tasks.
- Broad edits that exceed the task.
- Generated evidence that is not tied to the changed behavior.
- Claims that rely on closeout artifacts instead of implementation facts.

## Output

Return the Prism review shape from `schemas/prism-review.schema.json` with
`provider` set to `claude-code`.

--- REVIEW REQUEST FILE ---

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260618-long-task-entry-boundary/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "评审 RedCap 长任务机制补强方案：把上一版 long-task 合同检查器补成可接入任务入口、可区分模板与真实运行、可验证稳定证据、可防止局部完成误报整体完成的运行治理能力。",
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
  "task": "评审 RedCap 长任务机制补强方案：把上一版 long-task 合同检查器补成可接入任务入口、可区分模板与真实运行、可验证稳定证据、可防止局部完成误报整体完成的运行治理能力。",
  "user_intent": "Norven 要求修复此前遗留问题，并修复最新复盘发现的问题：任务还没完成就汇报，本质是 Cap 对能力边界识别错误。修复必须正面突破、保留原能力、根治复发，并正常触发棱镜方案评审和实现后逻辑评审。",
  "main_claim": "上一版 long-task 只达到合同检查器层，不能声称长任务能力完成。本轮应补入口决策、真实运行账本、模板/运行态分离、稳定证据白名单、能力覆盖检查和完成声明防误报，并把这些接入 RedCap 自开发生命周期与总检查。",
  "review_mode": "design_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "changed_reality": [
    "runtime/core/long_task_contract.py 文件头部明确写着该检查器不运行循环本身。",
    "assets/contracts/long-task-contract.json 的 non_claimed_boundaries 明确写着本合同不直接执行任务循环。",
    "assets/contracts/long-task-contract.json 当前 iteration_ledger 为空，但现有检查仍可通过，说明模板合同与真实运行合同没有分离。",
    "上一轮生命周期包与棱镜 resolution 引用了 assets/evidence/prism/20260617-long-task-contract 和 assets/evidence/check-receipts/20260617-long-task-contract 下的证据，但这些目录仍处于 ignore（忽略）状态，稳定证据可复现性不足。",
    "最新复盘暴露出 Cap 会把某一层检查通过误识别为整个能力完成，需要机器检查层面阻断这种边界误判。"
  ],
  "known_constraints": [
    "不允许用绕过、降级、放宽严格度的方式解决；必须保留长任务持续推进能力，同时补足入口、停止、仲裁和证据边界。",
    "不能把所有任务默认拖进重型长任务模式；低风险回答、小改动、单步修复必须有 fast-path（轻量路径）。",
    "不能允许空 iteration_ledger（迭代账本）冒充真实运行完成；只有 policy_template（策略模板）可以为空，active_run（真实运行）必须有轮次、证据和推进差量。",
    "不能大范围放开 assets/evidence；只能白名单稳定摘要、评审 JSON、resolution（裁决记录）和必要 receipt（检查收据），继续排除 raw（原始输出）和 stdout/stderr（标准输出/标准错误流）大文本。",
    "不能只更新文档或账本；每个 minimum fix（最低修复项）都必须落到代码、合同或检查器。"
  ],
  "proposed_design": {
    "task_entry_decision": {
      "new_command": "runtime/bin/redcap long-task decide --task TEXT --risk-level LEVEL",
      "purpose": "在任务入口给出 enabled（进入长任务）或 fast_path（轻量路径）决策，输出 JSON 供 gate、lifecycle 或人工执行前检查使用。",
      "rules": [
        "用户显式要求持续推进、循环直到完成、E2E、发布验收、Loom 多角色、RedCap 自开发中高风险、连续 3 次同类失败、跨 2 个以上运行边界时进入 enabled。",
        "纯回答、纯评审、低风险、一步小修、无 E2E、无发布、无自开发、无跨角色时进入 fast_path。",
        "Codex 目标 blocked 不是 RedCap 工程失败，也不要求先清除；但如果当前任务进入 enabled 且外部父目标 blocked，则 1 轮内必须 Cap 仲裁。"
      ]
    },
    "contract_kind_split": {
      "field": "contract_kind",
      "policy_template": "允许 iteration_ledger 为空，只能表达策略模板，不得作为运行完成证据。",
      "active_run": "必须包含非空 iteration_ledger、failure_backlog、action_evidence、objective_delta、source_signature、evidence_signature 和停止/仲裁结论。"
    },
    "capability_coverage_guard": {
      "purpose": "防止把合同层、文档层或检查器层通过误报成完整能力完成。",
      "required_layers": [
        "task_entry_decision",
        "contract_validation",
        "active_run_ledger",
        "failure_backlog",
        "completion_boundary_guard",
        "stable_evidence_policy",
        "aggregate_check_integration",
        "prism_review_resolution"
      ],
      "rule": "若 completion_claim.present=true，则 required_layers 必须被 completed_layers 覆盖；否则只能声明阶段状态和 non_claimed_boundaries。"
    },
    "stable_evidence_policy": {
      "purpose": "修复被引用证据仍被 ignore 的复现风险。",
      "rule": "仅对白名单任务目录放开稳定 JSON、brief.md 和 receipt.json，不放开 raw.json、raw.meta.json、stdout.txt、stderr.txt。"
    },
    "verification": [
      "runtime/bin/redcap long-task self-check",
      "runtime/bin/redcap long-task decide --task <low-risk question> --risk-level low",
      "runtime/bin/redcap long-task decide --task <self-development fix> --risk-level medium",
      "runtime/bin/redcap long-task check --packet assets/contracts/long-task-contract.json --require-integration",
      "runtime/bin/redcap check --only long-task-contract-self-check",
      "runtime/bin/redcap check --only long-task-contract-check",
      "runtime/bin/redcap lifecycle check --packet assets/evidence/lifecycle/20260618-long-task-entry-boundary-lifecycle.json",
      "runtime/bin/redcap prism-resolution --merge assets/evidence/prism/20260618-long-task-entry-boundary/merge.json --resolution assets/evidence/prism/20260618-long-task-entry-boundary/resolution.json --review ... --manifest ...",
      "git diff --check"
    ]
  },
  "questions_for_prism": [
    "这套方案是否真正补到了任务入口和运行账本，而不是继续停留在合同检查器层？",
    "contract_kind 分离是否足够防止空账本被误判为真实运行完成？",
    "capability_coverage_guard 是否足够防止 Cap 再把局部层完成误报成整体能力完成？",
    "stable_evidence_policy 的窄白名单是否保留证据复现能力，同时避免放开 raw/stdout/stderr 后造成上下文和仓库噪音？",
    "是否还存在会导致小任务被错误拖进重型循环，或长任务未完成就提前汇报的风险？"
  ]
}
