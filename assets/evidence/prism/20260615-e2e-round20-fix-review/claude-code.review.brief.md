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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260615-e2e-round20-fix-review/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "Review the RedCap round 20 E2E verifier fixes before implementation and round 21 rerun.",
  "review_mode": "implementation_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 3,
  "known_constraint_count": 4
}

--- REVIEW REQUEST JSON ---

{
  "schema_id": "redcap-prism-review-request",
  "created_at": "2026-06-15T00:00:00+08:00",
  "requester": "Cap",
  "task": "Review the RedCap round 20 E2E verifier fixes before implementation and round 21 rerun.",
  "user_intent": "Norven authorized Cap to continue all unfinished RedCap revival tasks until the goals are met. Round 20 E2E made meaningful progress but failed on verifier-level issues: browser interaction clicked the default item, the negative probe required a less structured signupIntent field instead of signups records, and interactive gate marker evidence became noisy.",
  "main_claim": "The proposed fixes should strengthen the E2E verifier and evidence quality without bypassing Loom role execution, project-level hooks, Prism assistance, self-evolution checks, release installation, or terminal readiness checks.",
  "changed_reality": [
    "No implementation has been edited for this review yet.",
    "Round 20 produced concrete failure evidence in the external E2E work root.",
    "The next implementation intends to make browser interaction probing try observable non-default interactions, align signup evidence with signups arrays while keeping signupIntent compatibility, and suppress non-actionable interactive marker noise from successful role receipts."
  ],
  "review_mode": "implementation_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence": [
    {
      "kind": "e2e-result",
      "reference": "/Users/norven/workspace/redcap-e2e-runs/run-20260615-round20",
      "summary": "Round 20 failed with finalization_ok=false and meaningful_evidence_ok=false while codex_cli_ok, package_prism_ok, and hook_events_ok were true."
    },
    {
      "kind": "source",
      "reference": "runtime/core/complete_revival_e2e.py",
      "summary": "Contains the behavioral browser verifier, negative probe expectations, role receipts, and interactive gate marker logic targeted by this fix."
    },
    {
      "kind": "contract",
      "reference": "assets/contracts/complete-revival-e2e-acceptance-design.json",
      "summary": "Defines the acceptance contract that must remain strict after the fix."
    }
  ],
  "context": {
    "round20_result": {
      "work_root": "/Users/norven/workspace/redcap-e2e-runs/run-20260615-round20",
      "status": "failed",
      "codex_cli_ok": true,
      "package_prism_ok": true,
      "hook_events_ok": true,
      "finalization_ok": false,
      "meaningful_evidence_ok": false,
      "ready_for_engineering_use": false
    },
    "known_failures": [
      "behavioral-browser-verification.json 的 interactive_state_change 失败：验收器点击了默认活动卡片，页面文本没有变化，导致真实交互被误判。",
      "negative-probes.json 的静态数据探针失败：探针硬要求 event.signupIntent，但实现使用 event.signups 报名记录列表，测试协议与实现协议不一致。",
      "role-runs 中 interactive_gate_marker 有噪音：角色成功产出时仍记录交互门禁标记，容易污染证据解释。"
    ]
  },
  "proposed_fix": [
    {
      "id": "browser-interaction-probe",
      "summary": "浏览器行为验收不再只点第一个非全部按钮，而是遍历可点击候选项，选择第一个能让页面文本或可观测状态发生变化的交互，并记录全部尝试。",
      "non_goal": "不降低行为验收严格性，不把交互验证改成只检查页面可访问。"
    },
    {
      "id": "signup-intent-contract",
      "summary": "负向探针与测试提示改为接受更结构化的 signups 报名记录列表，同时兼容 signupIntent 单字段；优先鼓励 signups 数组。",
      "non_goal": "不放弃报名意向验收，不允许没有报名数据的项目通过。"
    },
    {
      "id": "interactive-marker-noise",
      "summary": "角色交互门禁标记只在需要触发重试或失败回流时作为行动证据写入，成功产物不再把非行动噪音写成风险标记。",
      "non_goal": "不移除交互式技能误触发检测和重试能力。"
    }
  ],
  "review_questions": [
    "这些修复是否正面解决第20轮失败，而不是绕过失败？",
    "是否会降低 Loom 角色化工程工作流、项目级 Hook、棱镜协助、自我进化和终局验收的覆盖率？",
    "是否还存在必须先修复、否则不应启动第21轮 E2E 的阻塞项？"
  ],
  "expected_response": {
    "verdict": "approve|concern|reject",
    "blocking": true,
    "concerns": [],
    "required_changes": [],
    "recommended_checks": []
  },
  "known_constraints": [
    "Do not claim RedCap complete revival from this fix alone.",
    "Do not lower E2E strictness or mark round 20 as passed retroactively.",
    "Do not remove project-level hook/session checks.",
    "If Prism raises a concern, Cap must accept and fix it or rebut it through the bounded protocol before rerunning E2E."
  ]
}
