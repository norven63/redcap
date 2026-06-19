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

## Authorized File Access

If the review request JSON contains `file_access.mode = "bounded-read"` and an
`allowed_paths` list, you are authorized and expected to inspect those paths
directly before judging implementation reality.

- Read only the listed paths unless the prompt explicitly expands scope.
- Treat unreadable listed files as missing evidence, not as proof that the main
  claim is false.
- Do not rely only on the request's narrative when code or evidence files are
  authorized.
- When the request also includes generated compact audit evidence, prefer that
  compact evidence over broad source reads if context is tight.

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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260619-e2e-watchdog-deadline-classification-fix/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "评审 E2E harness 看门狗 deadline 终止误判和 active_run 残留 running 的修复方案。",
  "review_mode": "implementation_plan",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 5,
  "known_constraint_count": 5
}

--- REVIEW REQUEST JSON ---

{
  "schema_id": "redcap-prism-review-request",
  "task_id": "20260619-e2e-watchdog-deadline-classification-fix",
  "task": "评审 E2E harness 看门狗 deadline 终止误判和 active_run 残留 running 的修复方案。",
  "language_policy": "中文优先；专有名词首次出现请给中文解释。",
  "review_mode": "implementation_plan",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "user_intent": "Norven 要求网络中断恢复后继续推进 RedCap 复活目标，且不能因为执行器自身缺陷让长任务无限循环、误判或残留未收口状态。",
  "main_claim": "最新外部 E2E 失败已经证明：看门狗把 worker 因硬截止终止后，harness 仍把负退出码归类为 crash，并把失败轮次 active_run 期望状态留成 running。这不是放宽验收能解决的问题，必须把 watchdog cleanup 作为主控可消费的一等证据，并让失败轮次进入终态收口。",
  "changed_reality": [
    "新的隔离 E2E 工作根中，worker 退出码为 -15，watchdog cleanup 记录 reason=worker-deadline-exceeded、terminated=true、identity_matched=true。",
    "harness 当前输出 worker_exit_reason=crash、worker_timed_out=false、process_group_killed=false，导致真实 deadline 终止被误归因。",
    "worker 未返回可解析 JSON 时，harness 会生成失败摘要，但随后 final_status=failed 时 expected_lifecycle_state 仍被设置为 running。",
    "active_run 因此残留 lifecycle_state=running，后续巡检会看到已失败轮次仍像进行中，污染长任务父目标判断。",
    "上一轮 reviewer 顶层棱镜请求契约已经修复并提交，本轮不是继续修 reviewer，而是修 E2E 主控执行器的超时归因和终态收口。"
  ],
  "evidence": [
    {
      "kind": "runtime-output",
      "reference": "/Users/norven/workspace/redcap-e2e-runs-reviewer-contract-cycle/redcap-e2e-run-summary.json",
      "summary": "E2E run ok=false，失败包含 worker 没有返回 JSON 和没有 observer-request；harness worker_exit_reason=crash。"
    },
    {
      "kind": "runtime-output",
      "reference": "/tmp/redcap-harness-watchdog/33601cd3b900-76827-77507.cleanup.json",
      "summary": "看门狗 cleanup reason=worker-deadline-exceeded，terminated=true，说明 worker 是被 deadline 清理而不是普通崩溃。"
    },
    {
      "kind": "source",
      "reference": "runtime/core/complete_revival_e2e.py:10457",
      "summary": "主控 cleanup_harness_watchdog_record 后没有消费 cleanup reason 来修正 exit_reason。"
    },
    {
      "kind": "source",
      "reference": "runtime/core/complete_revival_e2e.py:10566",
      "summary": "失败型 final_status=failed 时 expected_lifecycle_state 被设置为 running。"
    },
    {
      "kind": "contract",
      "reference": "runtime/core/long_task_contract.py:830",
      "summary": "终态 active_run 需要 completion_boundary；running 不能含 terminal completion_boundary。"
    }
  ],
  "proposed_design": [
    "新增或抽取 harness_watchdog_exit_classification，用 watchdog_cleanup.reason 修正 timed_out、interrupted、exit_reason 和 process_group_killed。",
    "watchdog_cleanup.reason=worker-deadline-exceeded 时，harness summary 必须标记 worker_exit_reason=timeout、worker_timed_out=true，并追加可读 timeout failure。",
    "watchdog_cleanup.reason=parent-missing 时，harness summary 必须标记 interrupt，并保留 cleanup 证据。",
    "final_status=failed 的 E2E 轮次必须写入 terminal active_run，expected_lifecycle_state 应为 failed，且 require_completion_boundary=true。",
    "失败型 completion_boundary 的 evidence 要指向 harness-summary、run-summary、patrol ledger 和失败摘要，避免用空证据收口。",
    "增加单元或回归测试，覆盖看门狗 deadline cleanup 被正确归因，以及 failed active_run 不再残留 running。"
  ],
  "known_constraints": [
    "不能把 watchdog 终止一律归 timeout；只有 cleanup reason 明确为 worker-deadline-exceeded 才能这么归因。",
    "真正未被看门狗清理、无 timeout/interruption 证据的负退出码仍必须保留 crash。",
    "不能降低 E2E 对 observer-request、Loom 角色链、棱镜、自我净化和浏览器验证的要求。",
    "不能把本轮修复说成 RedCap 完整复活终局完成。",
    "不能删除旧 E2E 账本或外部运行目录来伪造通过。"
  ],
  "file_access": {
    "mode": "bounded-read",
    "purpose": "评审 E2E harness 看门狗 deadline 归因和 active_run 终态修复。",
    "max_files": 8,
    "max_bytes_per_file": 260000,
    "max_total_bytes": 900000,
    "allowed_paths": [
      "runtime/core/complete_revival_e2e.py",
      "runtime/core/test_e2e_layered_preflight.py",
      "runtime/core/long_task_contract.py",
      "assets/evidence/lifecycle/20260619-e2e-watchdog-deadline-classification-fix-lifecycle.json",
      "assets/evidence/prism/20260619-e2e-watchdog-deadline-classification-fix/request.json",
      "/Users/norven/workspace/redcap-e2e-runs-reviewer-contract-cycle/redcap-e2e-run-summary.json",
      "/tmp/redcap-harness-watchdog/33601cd3b900-76827-77507.cleanup.json"
    ]
  },
  "questions_for_prism": [
    "这个方案是否会错误掩盖真正 crash？如果会，请指出必须保留的区分字段。",
    "失败型 E2E active_run 是否应该进入 failed 终态并带 completion_boundary？是否有更符合长任务合同的状态选择？",
    "回归测试是否足以防止 worker-deadline-exceeded 再被误判为 crash 或 running？",
    "是否存在对 patrol、convergence 或 observer request 逻辑的副作用？"
  ],
  "expected_output": {
    "format": "json",
    "required_fields": [
      "verdict",
      "confidence",
      "main_concern",
      "minimum_fix",
      "risk_notes",
      "evidence_reviewed"
    ],
    "verdict_options": [
      "pass",
      "concern",
      "block"
    ]
  }
}
