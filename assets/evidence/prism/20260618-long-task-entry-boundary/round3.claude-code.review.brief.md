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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260618-long-task-entry-boundary/final-evidence-prism-request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "最终证据复核：确认 long-task 入口与完成边界修复已经通过正反向输出证据，而不是只靠状态说明。",
  "review_mode": "final_evidence_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 0,
  "known_constraint_count": 4
}

--- REVIEW REQUEST JSON ---

{
  "task": "最终证据复核：确认 long-task 入口与完成边界修复已经通过正反向输出证据，而不是只靠状态说明。",
  "user_intent": "Norven 要求此前问题与最新边界误判问题必须根治，不允许任务没完成就汇报；棱镜方案评审与实现后逻辑评审都必须正常触发。",
  "main_claim": "本轮已补齐第二轮棱镜提出的缺口：负向 active_run 空账本、缺 failure_backlog、自填 completed_layers 均有独立失败收据；正向入口决策、合同检查、总检查和关键 diff 均有完整输出收据。本声明仍只覆盖 long-task 入口与边界修复任务，不声明 RedCap 完整复活。",
  "review_mode": "final_evidence_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "changed_reality": [
    "新增收据目录 assets/evidence/check-receipts/20260618-long-task-entry-boundary，所有收据经 runtime/bin/redcap evidence-restore restore 写入，不绕过证据边界。",
    "negative-active-run-empty-ledger.receipt.json 显示 exit_code=1、expected_exit_code=1、ok=true，stdout 明确包含 active_run iteration_ledger must be non-empty 与 active_run requires failure_backlog object。",
    "negative-active-run-missing-failure-backlog.receipt.json 显示 exit_code=1、expected_exit_code=1、ok=true，stdout 明确包含 active_run requires failure_backlog object。",
    "negative-self-declared-completed-layers.receipt.json 显示 exit_code=1、expected_exit_code=1、ok=true，stdout 明确包含 capability_coverage.completed_layers must not be supplied by contract; checker derives completed layers。",
    "long-task-contract-check.receipt.json 显示 policy_template 正向检查通过，但 derived_capability_layers 仍明确缺 prism_review_resolution，说明它不会把阶段状态误报为完整完成。",
    "decide-low-answer.receipt.json 显示低风险解释任务 mode=fast_path；decide-medium-self-dev.receipt.json 显示 RedCap 中风险自开发 mode=enabled；decide-blocked-arbitration.receipt.json 显示 external_goal_status=blocked 时 requires_cap_arbitration=true。"
  ],
  "known_constraints": [
    "如果证据仍不足，请继续给 concern，不要因为已有实现就 pass。",
    "只能评审本次 long-task 入口与边界修复，不得扩大为 RedCap 完整复活完成。",
    "如果发现 capability_coverage 推导仍是文件存在性空壳，请明确指出还缺什么更硬的行为证据。",
    "如果发现入口决策过度触发或漏触发，请给出最小修复。"
  ],
  "evidence_to_review": [
    "runtime/core/long_task_contract.py",
    "assets/contracts/long-task-contract.json",
    "assets/docs/long-task-contract.md",
    "assets/evidence/.gitignore",
    "assets/evidence/check-receipts/20260618-long-task-entry-boundary/negative-active-run-empty-ledger.receipt.json",
    "assets/evidence/check-receipts/20260618-long-task-entry-boundary/negative-active-run-missing-failure-backlog.receipt.json",
    "assets/evidence/check-receipts/20260618-long-task-entry-boundary/negative-self-declared-completed-layers.receipt.json",
    "assets/evidence/check-receipts/20260618-long-task-entry-boundary/long-task-contract-check.receipt.json",
    "assets/evidence/check-receipts/20260618-long-task-entry-boundary/decide-low-answer.receipt.json",
    "assets/evidence/check-receipts/20260618-long-task-entry-boundary/decide-medium-self-dev.receipt.json",
    "assets/evidence/check-receipts/20260618-long-task-entry-boundary/decide-blocked-arbitration.receipt.json",
    "assets/evidence/check-receipts/20260618-long-task-entry-boundary/implementation-diff.receipt.json"
  ],
  "key_output_excerpts": {
    "negative_active_run_empty_ledger": [
      "exit 1 expected 1 ok True",
      "active_run iteration_ledger must be non-empty",
      "active_run requires failure_backlog object"
    ],
    "negative_missing_failure_backlog": [
      "exit 1 expected 1 ok True",
      "active_run requires failure_backlog object"
    ],
    "negative_self_declared_completed_layers": [
      "exit 1 expected 1 ok True",
      "capability_coverage.completed_layers must not be supplied by contract; checker derives completed layers"
    ],
    "positive_contract_check": [
      "contract_kind: policy_template",
      "derived_capability_layers includes task_entry_decision, active_run_ledger, failure_backlog, completion_boundary_guard, stable_evidence_policy",
      "missing_capability_layers: prism_review_resolution"
    ],
    "blocked_arbitration": [
      "mode: enabled",
      "requires_cap_arbitration: true",
      "external_goal_status: blocked"
    ]
  },
  "file_access": {
    "mode": "bounded-read",
    "purpose": "复核 long-task 入口与边界修复的源码、合同和收据证据。",
    "max_files": 12,
    "max_bytes_per_file": 80000,
    "max_total_bytes": 500000,
    "allowed_paths": [
      "runtime/core/long_task_contract.py",
      "assets/contracts/long-task-contract.json",
      "assets/docs/long-task-contract.md",
      "assets/evidence/.gitignore",
      "assets/evidence/check-receipts/20260618-long-task-entry-boundary/negative-active-run-empty-ledger.receipt.json",
      "assets/evidence/check-receipts/20260618-long-task-entry-boundary/negative-active-run-missing-failure-backlog.receipt.json",
      "assets/evidence/check-receipts/20260618-long-task-entry-boundary/negative-self-declared-completed-layers.receipt.json",
      "assets/evidence/check-receipts/20260618-long-task-entry-boundary/long-task-contract-check.receipt.json",
      "assets/evidence/check-receipts/20260618-long-task-entry-boundary/decide-low-answer.receipt.json",
      "assets/evidence/check-receipts/20260618-long-task-entry-boundary/decide-medium-self-dev.receipt.json",
      "assets/evidence/check-receipts/20260618-long-task-entry-boundary/decide-blocked-arbitration.receipt.json",
      "assets/evidence/check-receipts/20260618-long-task-entry-boundary/implementation-diff.receipt.json"
    ]
  },
  "questions_for_prism": [
    "第二轮要求的 active_run 空账本反向测试是否已经被独立输出证据闭合？",
    "self-declared completed_layers 被拒绝，是否足以回应 capability_coverage 自评风险？",
    "当前 policy_template 缺 prism_review_resolution 时仍不允许 completion_claim_allowed，是否防止了阶段误报完成？",
    "入口决策的 fast_path/enabled/blocked arbitration 样本是否足以支撑本轮修复范围？",
    "是否仍存在必须修复后才能收口的缺口？"
  ]
}
