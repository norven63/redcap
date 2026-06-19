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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260618-long-task-unified-entry-final-review-round5/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "第五轮复核：确认上一轮 block 的运行时边界探针与集成干跑缺口是否闭合。",
  "review_mode": "implementation_review",
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
  "task": "第五轮复核：确认上一轮 block 的运行时边界探针与集成干跑缺口是否闭合。",
  "user_intent": "只确认能否回到 E2E 巡检；不要求声明 RedCap 完整复活。",
  "main_claim": "上一轮 block 的两个最小修复已落地：1）新增 runtime-boundary-probe，构造非法 lifecycle_state、running 携带 completion_boundary、completed 缺 completion_boundary、completion_boundary outcome 不匹配等坏包，确认 E2E 运行时边界会拒绝；2）新增 long-task-integration-dry-run，真实执行 redcap long-task start→record→complete，再由 E2E 巡检 discover active_run、读取 lifecycle_state=completed 与 completion_boundary。",
  "changed_reality": [
    "complete_revival_e2e.py 增加 e2e_active_run_entry_failures、e2e_active_run_final_failures 和 discover_e2e_long_task_active_run，E2E 主流程入口和收束都调用同一套运行时边界判断。",
    "complete_revival_e2e.py 增加 runtime-boundary-probe 命令，并保存 runtime-boundary-probe.receipt.json。",
    "complete_revival_e2e.py 增加 long-task-integration-dry-run 命令，并保存 long-task-integration-dry-run.receipt.json。",
    "complete-revival-e2e self-check 已接入上述两个探针，避免探针只作为临时脚本存在。",
    "已复跑 py_compile、runtime-boundary-probe、long-task-integration-dry-run、complete-revival-e2e self-check、long-task self-check、long-task check --require-integration、git diff --check。"
  ],
  "review_mode": "implementation_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "verification_evidence": [
    "assets/evidence/check-receipts/20260618-long-task-unified-entry/runtime-boundary-probe.receipt.json",
    "assets/evidence/check-receipts/20260618-long-task-unified-entry/long-task-integration-dry-run.receipt.json",
    "assets/evidence/check-receipts/20260618-long-task-unified-entry/summary.receipt.json",
    "assets/evidence/check-receipts/20260618-long-task-unified-entry/negative-irrelevant-complete.receipt.json"
  ],
  "file_access": {
    "mode": "bounded-read",
    "purpose": "确认上一轮 block 是否闭合，并只提出回到 E2E 巡检前必须修复的最小阻塞。",
    "max_files": 5,
    "max_bytes_per_file": 320000,
    "max_total_bytes": 1100000,
    "allowed_paths": [
      "runtime/core/complete_revival_e2e.py",
      "runtime/core/long_task_contract.py",
      "assets/evidence/check-receipts/20260618-long-task-unified-entry/runtime-boundary-probe.receipt.json",
      "assets/evidence/check-receipts/20260618-long-task-unified-entry/long-task-integration-dry-run.receipt.json",
      "assets/evidence/check-receipts/20260618-long-task-unified-entry/negative-irrelevant-complete.receipt.json"
    ]
  },
  "questions_for_prism": [
    "上一轮 block 中关于 E2E 运行时边界探针和 start→record→complete→discover 集成干跑的最小阻塞是否已经闭合？",
    "如果没有，请只列回到 E2E 巡检前必须修复的最小阻塞；如果已闭合，请 verdict=pass。"
  ]
}
