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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260620-loom-role-chain-e2e-fix/followup-request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "复核 Loom 角色链与行为验证修复的补充证据",
  "review_mode": "implementation_followup_review",
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
  "task_id": "loom-role-chain-e2e-fix-followup",
  "created_at": "2026-06-20T00:00:00Z",
  "task": "复核 Loom 角色链与行为验证修复的补充证据",
  "user_intent": "确认本次修复不是文档化失败、不是降低验收标准，而是让 RedCap E2E 能在失败时保持 Loom 角色链完整，并在修复后允许下一轮真实验证。",
  "main_claim": "已补齐两位评审方要求的关键证据：实际差异、无跳过自检、收敛守卫、失败轮自我净化消费路径；filename-fallback 不再作为页面可见业务标题，但真实角色玩家关系仍必须由 DOM 同容器证明。",
  "changed_reality": [
    "不跳过载体探针的运行器自检通过：runtime/bin/redcap complete-revival-e2e self-check --timeout-seconds 300 -> REDCAP_AI_E2E_SELF_CHECK_OK。",
    "总检查通过：runtime/bin/redcap check -> REDCAP_CHECK_OK，69/69。",
    "收敛守卫对第四轮旧失败证据给出结构性停止；对当前源码签名变化给出允许修复后验证。",
    "self-check 中存在失败轮自我净化种子验证：write_runner_self_purification_resolution(... allow_runner_failure_candidate=True ...) 必须产生 runner_seeded=true，且不写公共能力或私有人格正文。",
    "关系探针现在把 filename-fallback 存入 event_title_fallback，event_title 为空；只有 event_title_source=payload 时才要求 relation_event_title_visible=true。角色和玩家同容器 DOM 证明仍然是硬条件。"
  ],
  "review_mode": "implementation_followup_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "question": "请基于补充证据判断：是否仍必须先修复才能运行下一轮 E2E，还是可以进入下一轮真实 E2E？如果仍有阻塞，请指出具体代码级阻塞点；如果只是需要通过下一轮 E2E 验证，请给出 pass 或 concern 但 recommended_next_action=run_next_e2e。",
  "diff_summary": {
    "tester_structural_vs_outcome": [
      "validate_tester_outputs 允许 status=completed|failed|blocked_by_upstream，其中 failed/blocked 必须 passed=false。",
      "commands、positive_checks、probes 只在非 blocked_by_upstream 时强制非空。",
      "tester_outcome_failures 单独把测试未通过记为 E2E 不通过，避免结构证据与结果判定混淆。"
    ],
    "loom_chain_after_failure": [
      "developer-readiness 修复循环停止时写 developer-repair-feedback 与 blocked-package.json。",
      "随后仍启动 tester，tester 读取 blocked-package.json 产出结构化失败证据。",
      "只要 tester 出现，就写 loom-role-session-manifest-pre-review.json 并启动 reviewer；reviewer 负责 failure-backlog、review-verdict、自我净化候选和人格沉淀裁决。"
    ],
    "filename_fallback_rule": [
      "candidate_title 缺失时 event_title 为空，event_title_fallback 记录文件名。",
      "relation_event_title_visibility_required 仅在 event_title_source=payload 且 event_title 非空时为 true。",
      "relation_passed 仍要求 dom_relation.same_structural_container=true 和记录状态匹配。",
      "validate_meaningful_e2e_evidence 也只在 event_title_source=payload 时要求活动标题页面可见。"
    ],
    "anti_loop_and_consumption": [
      "developer_repair_decision 保留 max_repair_rounds 硬上限。",
      "convergence-rerun-guard 基于上一轮 convergence-diagnosis 与当前源码签名阻止无变化重跑。",
      "loom-failure-route-plan 带 max_same_root_cause_routes、escalation_threshold、no_blind_rerun_without_source_or_evidence_delta。",
      "runner-self-purification-resolution 消费 self-purification-candidates.json；失败早于 reviewer 时由 runner_seeded 候选补位，并限制不写公共或私有人格正文。"
    ]
  },
  "checks": [
    {
      "command": "runtime/bin/redcap complete-revival-e2e self-check --timeout-seconds 300",
      "result": "passed",
      "marker": "REDCAP_AI_E2E_SELF_CHECK_OK"
    },
    {
      "command": "runtime/bin/redcap check",
      "result": "passed",
      "marker": "REDCAP_CHECK_OK"
    },
    {
      "command": "runtime/bin/redcap complete-revival-e2e convergence-guard-check --work-root /Users/norven/workspace/redcap-e2e-runs/run-20260620-redcap-fourth-e2e",
      "result": "passed",
      "marker": "REDCAP_AI_E2E_CONVERGENCE_GUARD_OK",
      "meaning": "源码签名变化后允许修复验证，不是盲目重跑。"
    },
    {
      "command": "runtime/bin/redcap complete-revival-e2e convergence-check --evidence <fourth-e2e-evidence>",
      "result": "structural_stop",
      "marker": "REDCAP_AI_E2E_CONVERGENCE_STRUCTURAL_STOP",
      "meaning": "旧失败证据自身仍阻止盲目重跑。"
    }
  ],
  "expected_output": {
    "verdict": "pass|concern|block",
    "blocking_findings": [],
    "concerns": [],
    "recommended_next_action": "run_next_e2e|fix_first"
  }
}
