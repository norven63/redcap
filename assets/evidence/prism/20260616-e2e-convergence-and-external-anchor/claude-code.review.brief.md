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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260616-e2e-convergence-and-external-anchor/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "评审 E2E 无限循环收敛治理修复。",
  "review_mode": "design_and_code_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 4,
  "known_constraint_count": 5
}

--- REVIEW REQUEST JSON ---

{
  "task": "评审 E2E 无限循环收敛治理修复。",
  "user_intent": "Norven 要求先解决多轮 E2E 无法把 RedCap 推进到最终可交付状态的问题，再继续被中断的 RedCap 复活任务；修复不能绕过、降级或放松验收标准。",
  "main_claim": "本轮改动把第 40 轮暴露出的验证拓扑不足、角色对抗证据不足、行为关系探针状态歧义和匿名内联脚本自证风险，收敛为可检查的运行器规则；最终棱镜未通过时会生成 convergence-diagnosis.json 并阻止结构性缺口被盲目重跑。",
  "changed_reality": [
    "runtime/core/complete_revival_e2e.py 新增 convergence-diagnosis.json 生成与校验，结构性最终评审 concern 会设置 auto_rerun_allowed=false。",
    "runtime/core/complete_revival_e2e.py 要求非 product_manager 的 Loom 角色记录 upstream_challenges、accepted_upstream_assumptions、rejected_upstream_assumptions，并要求 reviewer 写 role_opposition_matrix。",
    "runtime/core/complete_revival_e2e.py 要求独立浏览器验证脚本落盘为 independent-browser-verification-script.py 并记录 sha256。",
    "runtime/core/complete_revival_e2e.py 增强行为浏览器关系探针，记录 relation_event_control、behavioral-relation-probe.png 和被验证活动标题可见性。",
    "runtime/core/revival_followthrough.py 与 assets/contracts/complete-revival-e2e-acceptance-design.json 已把 convergence-diagnosis 纳入后续验收和合同。"
  ],
  "evidence": [
    {
      "kind": "code",
      "reference": "runtime/core/complete_revival_e2e.py",
      "summary": "E2E 运行器、角色提示、角色产物校验、行为浏览器验证、独立浏览器验证、最终棱镜复核和收敛诊断。"
    },
    {
      "kind": "code",
      "reference": "runtime/core/revival_followthrough.py",
      "summary": "复活后续推进检查器对 convergence-diagnosis 和 completion-marker 的验收要求。"
    },
    {
      "kind": "contract",
      "reference": "assets/contracts/complete-revival-e2e-acceptance-design.json",
      "summary": "E2E 方法论合同中对角色对抗、独立脚本、关系探针和收敛诊断的质量门禁。"
    },
    {
      "kind": "verification",
      "reference": "runtime/bin/redcap check",
      "summary": "65 个聚合检查已通过；prism-check 耗时 335 秒，提示后续仍应治理长检查心跳。"
    }
  ],
  "review_mode": "design_and_code_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "known_constraints": [
    "不能把第 40 轮失败说成通过。",
    "不能删除最终棱镜复核。",
    "不能用降级、绕过或放松验收制造 completion-marker.json。",
    "不能把本轮修复说成 RedCap 完整复活。",
    "如果仍存在结构性外部锚点缺口，应该要求停止盲目重跑并给出下一步动作。"
  ],
  "questions": [
    "这次根因判断是否覆盖了第 40 轮失败的主要原因，是否还有其他导致无限循环的结构性原因？",
    "convergence-diagnosis.json 加 auto_rerun_allowed=false 是否能有效阻止无意义重跑，同时不削弱严格验收能力？",
    "角色对抗证据、独立浏览器脚本落盘、行为关系截图这三项修复是否正面解决最终棱镜 concern？",
    "当前修复是否仍缺少必须立刻补上的代码或合同门禁？",
    "在这些改动通过后，是否可以进入下一轮 E2E 验证；如果不可以，阻塞条件是什么？"
  ]
}
