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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260620-residual-final-solution-plan/request.r9.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "最终证据链确认 RedCap 残留待完善项最终解决方案书第九轮",
  "review_mode": "design_review",
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
  "task": "最终证据链确认 RedCap 残留待完善项最终解决方案书第九轮",
  "review_mode": "design_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "user_intent": "只确认第八轮 Claude Code 提出的原文级交叉验证要求是否满足；不执行开发实现，不修改方案范围，不新增 RSP。",
  "main_claim": "已在本地执行原文级交叉验证，逐项确认第六轮 minimum_fix 对应内容存在于方案书正文中。Kimi 第八轮已 pass；Claude Code 第八轮仅要求原文级交叉验证。本轮只提交该验证结果。",
  "changed_reality": [
    "执行本地交叉验证：读取方案书正文、第六轮 Claude Code 评审、第七轮 Kimi/Claude Code 评审。",
    "验证最小检查语义、claim_file schema、evidence_file schema、loosen 例外流程、plan-change-control 示例、附录 A 均存在于方案书正文。",
    "验证结果 ok=true。"
  ],
  "non_goals": [
    "不实现 rsp-contract check。",
    "不关闭任何 RSP。",
    "不新增 RSP。",
    "不声明 RedCap 完整复活。",
    "不继续扩写方案。"
  ],
  "local_cross_verification": {
    "schema_id": "redcap-residual-plan-cross-verification-v1",
    "ok": true,
    "plan_path": "assets/docs/residual-todo-final-solution-plan.md",
    "r6_claude_review": "assets/evidence/prism/20260620-residual-final-solution-plan-r6/claude-code.review.json",
    "r7_kimi_review": "assets/evidence/prism/20260620-residual-final-solution-plan-r7/kimi.review.json",
    "r7_claude_review": "assets/evidence/prism/20260620-residual-final-solution-plan-r7/claude-code.review.json",
    "checks": [
      {
        "id": "check_semantics",
        "section": "最小检查语义",
        "ok": true,
        "missing": []
      },
      {
        "id": "claim_file_schema",
        "section": "claim_file 最小 JSON schema",
        "ok": true,
        "missing": []
      },
      {
        "id": "evidence_file_schema",
        "section": "evidence_file 最小 JSON schema",
        "ok": true,
        "missing": []
      },
      {
        "id": "loosen_exception",
        "section": "放宽标准的例外流程",
        "ok": true,
        "missing": []
      },
      {
        "id": "plan_change_example",
        "section": "plan-change-control 标注示例",
        "ok": true,
        "missing": []
      },
      {
        "id": "appendix_a_exists",
        "section": "附录 A",
        "ok": true,
        "missing": []
      }
    ],
    "r6_minimum_fix_excerpt": "方案书需补充：(1) 为每个 check 定义至少一条具体的通过/失败判定规则；(2) 定义 claim_file 与 evidence_file 的最小 JSON schema；(3) 为 plan-change-control 审计规则增加例外机制；(4) 给出完整的 plan-change-control 标注实例。",
    "r7_kimi_minimum_fix_excerpt": "提供最终方案书文件路径的只读授权，或附加 evidence bundle，使 Prism 能逐项验证 changed_reality 是否真实存在于文档中。",
    "r7_claude_minimum_fix_excerpt": "在方案书中新增附录：第六轮 minimum_fix 逐项对照表，每项列出原文要求、对应段落引用、满足状态。",
    "conclusion": "方案书正文包含第六轮 minimum_fix 要求的对应段落、最小 schema、例外流程、标注示例和附录 A 对照表。"
  },
  "file_access": {
    "mode": "bounded-read",
    "purpose": "Final verification of plan text and prior review records.",
    "allowed_paths": [
      "assets/docs/residual-todo-final-solution-plan.md",
      "assets/evidence/prism/20260620-residual-final-solution-plan-r6/claude-code.review.json",
      "assets/evidence/prism/20260620-residual-final-solution-plan-r7/kimi.review.json",
      "assets/evidence/prism/20260620-residual-final-solution-plan-r7/claude-code.review.json",
      "assets/evidence/prism/20260620-residual-final-solution-plan-r8/kimi.review.json",
      "assets/evidence/prism/20260620-residual-final-solution-plan-r8/claude-code.review.json"
    ],
    "max_files": 10,
    "max_bytes_per_file": 200000,
    "max_total_bytes": 700000
  },
  "review_questions": [
    "第八轮 Claude Code 的 minimum_fix 是否已由 local_cross_verification 满足？",
    "方案阶段是否还有 blocker？",
    "是否应当停止方案级评审，冻结方案并进入 RSP-00/RSP-11/RSP-12 实施阶段？"
  ],
  "required_response": {
    "format": "json",
    "fields": [
      "verdict",
      "confidence",
      "reality_delta",
      "main_concern",
      "top_risks",
      "missing_evidence",
      "minimum_fix",
      "anti_loop_signal",
      "user_intent_alignment"
    ]
  },
  "language_policy": "中文优先；只输出一个 JSON 对象，不要输出 Markdown，不要输出思考过程。"
}


--- AUTHORIZED FILE ACCESS ---

mode: bounded-read

Authorized bundle JSON: /Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260620-residual-final-solution-plan-r9/kimi.review.brief.files.json

Bundle sha256: 1591773b2aa9628d82daddd0e3dd560fe4f7eab93e69765eb4955cffabb50885

Rules:

- You may read only this generated bundle JSON if file evidence is needed.

- Do not inspect the original source paths directly.

- Do not run commands.

- If the bundle is insufficient, report missing evidence instead of fetching more files.

