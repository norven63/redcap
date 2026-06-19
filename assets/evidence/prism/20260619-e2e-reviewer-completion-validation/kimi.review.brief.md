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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260619-e2e-reviewer-completion-validation/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "评审 E2E reviewer 角色完成判定修复方案",
  "review_mode": "implementation_review",
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
  "task": "评审 E2E reviewer 角色完成判定修复方案",
  "user_intent": "用户要求 RedCap 复活任务不能因边界误判而中途停止，也不能用降级或绕过方式把真实缺陷掩盖成通过。当前 E2E 必须继续推动 RedCap 成为更可靠的开发辅助工具，而不只是产出 TRPG 示例项目。",
  "main_claim": "当前 E2E 失败的直接原因不是 reviewer 未执行，而是 reviewer 产物中“请求运行器统一调度棱镜”的字段写在 reviews[].prism_assistance_request 内，校验器只接受顶层 prism_assistance_request，导致角色完成状态被降级为 role_command_failed。",
  "changed_reality": [
    "最近一次完整 E2E 运行已触发项目级 .redcap、Loom 角色链、棱镜协助字段、自我净化候选、人格沉淀边界、独立观察者和浏览器验证。",
    "reviewer 角色退出码为 0，role-artifacts/reviewer.json.status 为 completed，review-verdict.json.status 为 completed，blocking_findings 为空。",
    "reviewer 的 prism-assisted-review.json.status 为 completed，used 为 true，reviews 为非空数组，cap_decision 为 blocked，但 prism_assistance_request 只出现在 reviews[0] 内。",
    "validate_reviewer_outputs 当前只检查 prism-assisted-review.json 顶层 prism_assistance_request.requested == true，因此把该 reviewer 判为失败。",
    "loom-role-session-manifest.json 因 reviewer 校验失败产生 session_loss_alarms=[role_command_failed]，最终 completion-marker.json 未写入。"
  ],
  "evidence": [
    {
      "kind": "runtime-output",
      "reference": "/Users/norven/workspace/redcap-e2e-runs/redcap-e2e-基于旧-trpg-server-与-trpg-web-的能力-开发一个简/.redcap/evidence/e2e/role-runs/reviewer.json",
      "summary": "reviewer exit_code=0，expected_artifact_exists=true，但 role result ok=false，失败原因为缺少顶层 prism_assistance_request"
    },
    {
      "kind": "runtime-output",
      "reference": "/Users/norven/workspace/redcap-e2e-runs/redcap-e2e-基于旧-trpg-server-与-trpg-web-的能力-开发一个简/.redcap/evidence/e2e/prism-assisted-review.json",
      "summary": "棱镜协助请求存在于 reviews[0].prism_assistance_request，顶层没有该字段"
    },
    {
      "kind": "runtime-output",
      "reference": "/Users/norven/workspace/redcap-e2e-runs/redcap-e2e-基于旧-trpg-server-与-trpg-web-的能力-开发一个简/.redcap/evidence/e2e/review-verdict.json",
      "summary": "reviewer 阶段评审通过，terminal_completion=false，runner_owned_follow_up 明确列出最终收尾动作"
    },
    {
      "kind": "source",
      "reference": "runtime/core/complete_revival_e2e.py:2567",
      "summary": "validate_reviewer_outputs 只接受顶层 prism_assistance_request"
    },
    {
      "kind": "source",
      "reference": "runtime/core/complete_revival_e2e.py:2431",
      "summary": "reviewer 提示词要求写 prism-assisted-review.json，但没有明确要求 prism_assistance_request 必须位于顶层"
    }
  ],
  "review_mode": "implementation_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "known_constraints": [
    "不能删除或绕过 reviewer 校验。",
    "不能把非零退出、产物缺失、交互确认、超时、上下文丢失等真实问题放行。",
    "不能仅靠 completion-marker.json 或最终汇报证明完成；必须通过运行器真实证据链。",
    "修复后需要补自检或单元测试，证明 reviewer 字段位置和校验器要求一致。",
    "若采用兼容读取 reviews[].prism_assistance_request，也必须收紧 schema 或提示词，避免以后继续产生歧义。"
  ],
  "questions_for_prism": [
    "当前根因判断是否充分：这是字段结构契约不一致，而不是 reviewer 角色未执行？",
    "修复应优先收紧 reviewer 提示词/示例，让 prism_assistance_request 写到顶层，还是应让校验器兼容 reviews 内字段？是否需要两者都做？",
    "有哪些严格性不能放松，才能避免把真实 Loom 失败误判为通过？",
    "修复后最小但充分的验证命令和负向自检应该包含哪些？"
  ]
}


--- KIMI FILE ACCESS ---
mode: prompt-only
No file reading is authorized for this review.
