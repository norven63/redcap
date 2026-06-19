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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260618-long-task-unified-entry-final-review-round7/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "第七轮最小复核：在源码读取失败时，基于内嵌精确行号片段确认上一轮 concern 是否闭合。",
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
  "task": "第七轮最小复核：在源码读取失败时，基于内嵌精确行号片段确认上一轮 concern 是否闭合。",
  "user_intent": "只确认能否回到 E2E 巡检；不要求声明 RedCap 完整复活。",
  "main_claim": "上一轮 block 的剩余问题是评审方无法读取源码。现将关键源码行号和片段直接嵌入请求：边界检查底层实现只有一个，入口 wrapper、收束 wrapper、discover、E2E 主流程和 self-check 都指向同一个底层函数。重构后 runtime-boundary-probe-v2、long-task-integration-dry-run-v2、complete-revival-e2e self-check、py_compile、git diff --check 均已通过。",
  "changed_reality": [
    "单一底层实现：runtime/core/complete_revival_e2e.py:5289 定义 e2e_active_run_boundary_failures。",
    "入口 wrapper：5335-5336 只有 return e2e_active_run_boundary_failures(active_run_status, phase=\"entry\")。",
    "收束 wrapper：5339-5350 只有 return e2e_active_run_boundary_failures(... phase=\"final\", parsed_ok=parsed_ok, final_status=final_status)。",
    "巡检发现：5397-5407 在 discover_e2e_long_task_active_run 中调用 e2e_active_run_boundary_failures(... phase=\"discover\", expected_lifecycle_state=..., require_completion_boundary=...)。",
    "运行器入口：7156 调用 e2e_active_run_entry_failures_via_boundary_check(active_run_start)。",
    "运行器收束：7294-7298 调用 e2e_active_run_final_failures_via_boundary_check(active_run_final, parsed_ok=..., final_status=...)。",
    "探针：5469、5497、5498 分别调用入口 wrapper 和收束 wrapper；非法包再通过 discover_e2e_long_task_active_run 复核。",
    "self-check 执行探针和集成干跑：7425-7430 调用 run_e2e_active_run_runtime_boundary_probe 和 run_long_task_e2e_integration_dry_run。",
    "self-check 防分裂：8255 用 re.findall(r\"^def e2e_active_run_boundary_failures\\(\", current_source, re.MULTILINE) 要求底层定义数量为 1。",
    "命令入口：8354-8360 注册 runtime-boundary-probe 与 long-task-integration-dry-run 子命令。"
  ],
  "embedded_source_lines": [
    "5289 def e2e_active_run_boundary_failures(",
    "5335 def e2e_active_run_entry_failures_via_boundary_check(active_run_status: dict[str, Any]) -> list[str]:",
    "5336     return e2e_active_run_boundary_failures(active_run_status, phase=\"entry\")",
    "5339 def e2e_active_run_final_failures_via_boundary_check(",
    "5345     return e2e_active_run_boundary_failures(",
    "5347         phase=\"final\",",
    "5397     failures.extend(e2e_active_run_boundary_failures(",
    "5404         phase=\"discover\",",
    "5405         expected_lifecycle_state=expected_lifecycle_state,",
    "5406         require_completion_boundary=require_completion_boundary,",
    "7156     entry_failures = e2e_active_run_entry_failures_via_boundary_check(active_run_start)",
    "7294     final_failures = e2e_active_run_final_failures_via_boundary_check(",
    "7425     runtime_boundary_probe = run_e2e_active_run_runtime_boundary_probe(work_root / \"runtime-boundary-self-check\")",
    "7428     integration_dry_run = run_long_task_e2e_integration_dry_run(work_root / \"long-task-integration-self-check\")",
    "8255     if len(re.findall(r\"^def e2e_active_run_boundary_failures\\(\", current_source, re.MULTILINE)) != 1:",
    "8354     runtime_probe = sub.add_parser(\"runtime-boundary-probe\")",
    "8358     integration_dry_run = sub.add_parser(\"long-task-integration-dry-run\")"
  ],
  "command_results_observed": [
    "python3 -m py_compile runtime/core/complete_revival_e2e.py: exit 0",
    "runtime/bin/redcap complete-revival-e2e runtime-boundary-probe --work-root /Users/norven/workspace/redcap-e2e-runs/20260618-runtime-boundary-probe-v2 --out assets/evidence/check-receipts/20260618-long-task-unified-entry/runtime-boundary-probe-v2.receipt.json: exit 0, marker REDCAP_AI_E2E_RUNTIME_BOUNDARY_PROBE_OK",
    "runtime/bin/redcap complete-revival-e2e long-task-integration-dry-run --work-root /Users/norven/workspace/redcap-e2e-runs/20260618-long-task-integration-dry-run-v2 --out assets/evidence/check-receipts/20260618-long-task-unified-entry/long-task-integration-dry-run-v2.receipt.json: exit 0, marker REDCAP_AI_E2E_LONG_TASK_INTEGRATION_DRY_RUN_OK",
    "runtime/bin/redcap complete-revival-e2e self-check --skip-carrier-probe: exit 0, marker REDCAP_AI_E2E_SELF_CHECK_OK",
    "runtime/bin/redcap long-task self-check: exit 0, marker REDCAP_LONG_TASK_CONTRACT_SELF_CHECK_OK",
    "runtime/bin/redcap long-task check --packet assets/contracts/long-task-contract.json --require-integration: exit 0, marker REDCAP_LONG_TASK_CONTRACT_OK",
    "git diff --check: exit 0"
  ],
  "review_mode": "implementation_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "verification_evidence": [
    "assets/evidence/check-receipts/20260618-long-task-unified-entry/runtime-boundary-probe-v2.receipt.json",
    "assets/evidence/check-receipts/20260618-long-task-unified-entry/long-task-integration-dry-run-v2.receipt.json"
  ],
  "file_access": {
    "mode": "bounded-read",
    "purpose": "若可读，复核完整源码；若不可读，基于 embedded_source_lines 做最小阻塞判断。",
    "max_files": 3,
    "max_bytes_per_file": 600000,
    "max_total_bytes": 1000000,
    "allowed_paths": [
      "runtime/core/complete_revival_e2e.py",
      "assets/evidence/check-receipts/20260618-long-task-unified-entry/runtime-boundary-probe-v2.receipt.json",
      "assets/evidence/check-receipts/20260618-long-task-unified-entry/long-task-integration-dry-run-v2.receipt.json"
    ]
  },
  "questions_for_prism": [
    "在文件读取失败也可基于 embedded_source_lines 判断的前提下，上一轮关于源码不可见和边界检查分裂的阻塞是否已闭合？",
    "是否还有回到 E2E 巡检前必须修复的最小阻塞？如果没有，请 verdict=pass。"
  ]
}


--- AUTHORIZED FILE ACCESS ---

mode: bounded-read

Authorized bundle JSON: /Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260618-long-task-unified-entry-final-review-round7/kimi.review.brief.files.json

Bundle sha256: 1ed50d20970566e2813e62a7f83289db5ec8ae01737c871339b3c1394f593c0f

Rules:

- You may read only this generated bundle JSON if file evidence is needed.

- Do not inspect the original source paths directly.

- Do not run commands.

- If the bundle is insufficient, report missing evidence instead of fetching more files.

