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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260618-e2e-patrol-loop/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "评审 RedCap E2E 巡检循环方案：在近期大量修改后运行端到端验收，发现问题就修复并复测，但必须防止盲目无限循环和阶段成果误报终局完成。",
  "review_mode": "design_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 0,
  "known_constraint_count": 5
}

--- REVIEW REQUEST JSON ---

{
  "task": "评审 RedCap E2E 巡检循环方案：在近期大量修改后运行端到端验收，发现问题就修复并复测，但必须防止盲目无限循环和阶段成果误报终局完成。",
  "user_intent": "Norven 要求这次任务继续此前循环 E2E 巡检：运行 E2E，检查预期逻辑是否触发；如果有问题则修复再跑，直到没有新问题并达到预期效果。用户同时强调必须正面突破问题、保留原能力、避免任务未完成就汇报。",
  "main_claim": "本轮还未开始执行 E2E；当前只请求棱镜评审巡检方案。任何后续结论必须以外部项目 E2E 证据、收敛诊断、必要修复和复测为准。",
  "review_mode": "design_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "current_context": {
    "lifecycle_packet": "assets/evidence/lifecycle/20260618-e2e-patrol-loop-lifecycle.json",
    "e2e_contract": "assets/contracts/complete-revival-e2e-acceptance-design.json",
    "e2e_runner": "runtime/core/complete_revival_e2e.py",
    "known_goal": "运行、分析、修复、复测，直到没有新问题且达到预期效果；如果出现结构性缺口，必须先修机制，不能盲目继续跑。"
  },
  "changed_reality": [
    "近期 RedCap 已修改长任务入口、完成边界、棱镜裁决、E2E 运行器、Stop Hook 建议机制和发布安装相关逻辑，需要用真实 E2E 验证这些能力是否协同工作。",
    "用户明确指出首次 E2E 过于空洞：没有充分证明 Loom 角色分工、棱镜审核、需求和架构质量、自我净化、Cap 人格沉淀与工作流细节真实发挥作用。",
    "现有 E2E 合同已经要求外部项目、项目级 .redcap、独立 Codex CLI 角色、项目级 Hook、自我净化候选、最终证据包和收敛诊断，但这些要求需要通过真实运行再次验证。",
    "本轮任务目标不是写新方案，而是运行 E2E、观察缺口、修复机制、复测并避免盲目循环。"
  ],
  "known_constraints": [
    "不能绕过、降级或放宽严格度来换取通过；必须正面修复发现的问题。",
    "不能把某个局部绿色检查当作 RedCap 完整复活或永久可交付。",
    "不能让 E2E 污染 RedCap 源码区；运行时产物必须归属外部项目 .redcap。",
    "不能在 convergence-diagnosis 显示结构性缺口时继续盲目重跑。",
    "如果需要修改 RedCap 机制，修改后必须再次接受棱镜实现评审和本地验证。"
  ],
  "proposed_plan": [
    {
      "step": "preflight",
      "checks": [
        "complete-revival-e2e design-check",
        "complete-revival-e2e self-check",
        "project-install package/audit where needed",
        "redcap check"
      ],
      "purpose": "先确认通用 E2E 合同、准备器、自检和发布安装基础没有静态破损。"
    },
    {
      "step": "run_e2e",
      "checks": [
        "complete-revival-e2e run with external work-root under /Users/norven/workspace/redcap-e2e-runs"
      ],
      "purpose": "让独立 Codex CLI 角色在外部项目里使用项目级 .redcap 完成真实交付，而不是由当前 Cap 单上下文冒充所有角色。"
    },
    {
      "step": "inspect_expected_logic",
      "required_logic": [
        "Loom 角色产物和 session_id 记录",
        "项目级 Hook 事件",
        "棱镜协助或最终评审",
        "知识检索证据",
        "自我净化候选与 no-promote/晋升裁决",
        "Cap 人格沉淀边界裁决",
        "运行器负向探针",
        "浏览器或文件行为验证",
        "convergence-diagnosis 是否允许自动重跑",
        "completion-marker 只代表单轮 E2E，不代表 RedCap 永久完整复活"
      ],
      "purpose": "判断 E2E 是否真的触发了 RedCap 的关键工作流，而不只是产出一个玩具项目。"
    },
    {
      "step": "fix_or_stop_blind_loop",
      "rules": [
        "如果收敛诊断显示结构性缺口且 auto_rerun_allowed=false，先修复 RedCap 机制，再复跑。",
        "如果是外部项目临时实现缺陷，可按 E2E 运行器规则重试或让角色回流。",
        "如果是人类价值判断、外部服务不可用或权限缺失，标记真实阻塞，不伪装完成。"
      ]
    },
    {
      "step": "implementation_review",
      "rule": "任何 RedCap 机制修复后必须再次邀请棱镜做实现逻辑评审，并用 receipt（检查收据）或 E2E 证据关闭 concern（质疑点）。"
    }
  ],
  "questions_for_prism": [
    "这套 E2E 巡检方案是否能检出 Loom 角色工作流质量，而不是只看项目产物存在？",
    "是否还有会导致盲目无限重跑、或结构性缺口未修却继续循环的风险？",
    "是否需要在实际 E2E 前补充额外静态检查，尤其是项目级发布安装、Hook 继承和独立 Codex CLI 承载？",
    "哪些证据必须被视为本轮 E2E 通过的硬条件？",
    "如果 E2E 失败，如何区分应修 RedCap 机制、应修外部项目、应重试提供方、或应停止并向用户报告阻塞？"
  ]
}


--- KIMI FILE ACCESS ---
mode: prompt-only
No file reading is authorized for this review.
