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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260620-loom-role-chain-e2e-fix/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "评审 RedCap 完整复活 E2E 运行器的 Loom 角色链与行为验证修复",
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
  "schema_id": "redcap-prism-review-request",
  "task_id": "loom-role-chain-e2e-fix",
  "created_at": "2026-06-20T00:00:00Z",
  "task": "评审 RedCap 完整复活 E2E 运行器的 Loom 角色链与行为验证修复",
  "user_intent": "用户要求 RedCap 复活不能只产出目标项目这条“鱼”，而要持续修好开发辅助工具这张“渔网”；E2E 失败必须通过 Loom 角色链、失败路由、自我净化和独立评审暴露并推动 RedCap 自身改进。",
  "main_claim": "本次实现没有降低 E2E 验收标准，而是让失败轮也能按 Loom 角色链完整产出 tester/reviewer 证据，并修复文件名兜底导致的关系探针误判。",
  "changed_reality": [
    "runtime/core/complete_revival_e2e.py 修改了 tester 失败产物结构校验。",
    "runtime/core/complete_revival_e2e.py 修改了 developer-readiness 失败后的 tester/reviewer 继续执行路径。",
    "runtime/core/complete_revival_e2e.py 修改了 character-player relation 探针对 filename-fallback 的标题可见性要求。",
    "已运行 py_compile、complete-revival-e2e self-check、runtime/bin/redcap check，均通过。"
  ],
  "review_mode": "implementation_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "question": "请评审本次 RedCap 完整复活 E2E 运行器修复是否正面解决第四轮失败：包内棱镜已通过，但 Loom 角色链缺少 tester/reviewer，行为级关系探针把文件名 data 当作业务标题导致误判。请重点判断是否存在绕过、降级、死循环或职责错位。",
  "changed_files": [
    "runtime/core/complete_revival_e2e.py"
  ],
  "context": {
    "fourth_e2e_failures": [
      "Codex CLI Loom 角色管线执行失败",
      "缺少 tester/reviewer session_id 与角色证据",
      "behavioral-browser-verification 关系探针 event_title=data 不可见",
      "completion-marker.json 未写入",
      "final-prism-review 被前置失败跳过"
    ],
    "package_prism_status": "已修复，第四轮 package-prism-check ok=true duration_seconds=36.305",
    "implementation_summary": [
      "测试者结构化产物和测试是否通过拆分：blocked_by_upstream/failed 可以作为有效角色产物，但不会让 E2E 通过。",
      "开发者准备度无法继续修复时，运行器写 blocked-package.json，然后仍启动 tester 与 reviewer，保证失败轮有完整 Loom 判断。",
      "tester 未通过时 reviewer 仍会启动，负责 failure-backlog、review-verdict、自我净化候选与人格沉淀裁决。",
      "角色玩家关系探针只有 event_title_source=payload 时才要求活动标题在页面可见；filename-fallback 只作为数据定位信息。",
      "总检查已通过：runtime/bin/redcap check -> REDCAP_CHECK_OK，69/69。"
    ],
    "non_goals": [
      "不降低最终 E2E 通过标准。",
      "不让 Cap 或 E2E 运行器替 Loom 角色修改目标项目。",
      "不把阶段修复宣称为 RedCap 完整复活完成。"
    ]
  },
  "review_questions": [
    "测试者结构化失败产物与最终 E2E 通过判定的拆分是否合理？",
    "开发者准备度失败后仍启动 tester/reviewer，是否符合 Loom 角色化工程工作流？",
    "filename-fallback 不再要求页面可见，是否会放松真实关系可见性验证？",
    "是否还存在可能导致无限 E2E 循环、角色缺席、或运行器越权修项目的问题？",
    "在运行下一轮 E2E 前是否还有必须修复的阻塞点？"
  ],
  "local_checks": [
    "python3 -m py_compile runtime/core/complete_revival_e2e.py",
    "runtime/bin/redcap complete-revival-e2e self-check --skip-carrier-probe --timeout-seconds 240",
    "runtime/bin/redcap check"
  ],
  "expected_output": {
    "verdict": "pass|concern|block",
    "blocking_findings": [],
    "concerns": [],
    "recommended_next_action": "run_next_e2e|fix_first"
  }
}


--- KIMI FILE ACCESS ---
mode: prompt-only
No file reading is authorized for this review.
