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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260613-advisory-stop-post-restart-verification/review-request-v2.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "复评建议型 Stop Hook 重启后验证：补充耗时观测后是否仍有阻塞风险",
  "review_mode": "post_fix_recheck",
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
  "task": "复评建议型 Stop Hook 重启后验证：补充耗时观测后是否仍有阻塞风险",
  "user_intent": "Norven 要求确认建议型 Stop Hook（停止前检查钩子）是否已经落实，并测试验证新 Stop Hook 运行是否符合预期；若发现问题要修复并复测。",
  "main_claim": "已采纳 Claude Code 的有效担忧，补充 Stop 热路径耗时观测与回归断言：Stop 最新标记会记录 stop_hook_duration_ms、stop_hook_outcome、stop_hook_completed_at；advisory-stop 回归现在断言默认热路径不运行完整 runtime/bin/redcap check，并输出两次 Stop 的实际耗时。",
  "changed_reality": [
    "runtime/host-adapters/codex/codex-hook.py 增加 mark_stop_timing，在 Stop 正常通过、建议阻断、覆盖放行、观察模式和显式 redcap check 分支都记录耗时与结果。",
    "runtime/core/advisory_stop.py 的端到端回归新增断言：first Stop 和 override Stop 都必须记录 stop_hook_duration_ms，且默认热路径 redcap_check_attempted=false。",
    "assets/contracts/advisory-stop.json 的 health-observation 约束已明确要求记录总耗时和完整总检查是否被排除在热路径外。",
    "runtime/bin/redcap advisory-stop check 通过，并报告 first_stop_duration_ms=41.446、override_stop_duration_ms=41.971。",
    "runtime/bin/redcap host-hook-audit、runtime/bin/redcap hook-coverage-check、runtime/bin/redcap enforcement-check 均已通过。"
  ],
  "verification_performed": [
    "runtime/bin/redcap advisory-stop check",
    "python3 runtime/host-adapters/codex/codex-hook.py --self-check-intent-judge",
    "runtime/bin/redcap host-hook-audit",
    "runtime/bin/redcap hook-coverage-check",
    "runtime/bin/redcap enforcement-check"
  ],
  "verification_result": "所有复测命令通过；新增回归给出了 Stop 热路径实际耗时，并证明完整 runtime/bin/redcap check 不在默认 Stop 热路径内。",
  "review_questions": [
    "Claude Code 第一轮指出的 Stop 热路径未测量风险是否已被充分缓解？",
    "当前仍缺少真实宿主自然触发 Stop 的证据；在本轮最终回答会自然触发 Stop 的前提下，这是否应作为剩余边界而不是当前阻塞？",
    "是否仍存在必须在本轮继续修复的 Stop 回答主轴偏移风险？",
    "Kimi 如果能完成评审，请独立判断当前方案是否可用于继续推进后续 RedCap 工作。"
  ],
  "known_limits": [
    "真实 Codex 宿主自然触发 Stop 的证据只有在最终回答收口时产生；当前已有 adapter 真实 stdin/stdout 路径回归、host-hook-audit 和 SessionStart 重启证据。",
    "Stop 覆盖标记只覆盖建议型 Stop 本身；危险写入、生命周期、终局目标等硬门禁仍由其他检查承接。",
    "本轮只验证建议型 Stop，不声明 RedCap 完整复活状态变化。"
  ],
  "expected_output": "返回严格 JSON，字段包括 provider, verdict, confidence, reality_delta, main_concern, top_risks, missing_evidence, minimum_fix, anti_loop_signal, user_intent_alignment。",
  "review_mode": "post_fix_recheck",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ]
}
