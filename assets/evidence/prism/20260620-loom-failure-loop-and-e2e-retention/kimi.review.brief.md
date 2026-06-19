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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260620-loom-failure-loop-and-e2e-retention/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "评审 Loom 失败回流运行机制与 E2E 运行目录保留策略的实施方案。",
  "review_mode": "design_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 0,
  "known_constraint_count": 5
}

--- REVIEW REQUEST JSON ---

{
  "schema_id": "redcap-prism-review-request",
  "task_id": "20260620-loom-failure-loop-and-e2e-retention",
  "task": "评审 Loom 失败回流运行机制与 E2E 运行目录保留策略的实施方案。",
  "language_policy": "中文优先；专有名词首次出现请给中文解释。",
  "review_mode": "design_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "user_intent": "Norven 指出此前 E2E 中 Cap 过多承担了 TRPG 项目的诊断、修复与重跑职责；这应当属于 Loom 角色链：测试或评审发现问题后，生成失败回流包，打回到产品经理、架构师或开发者，并从该角色节点重新推进。Norven 同时要求治理 E2E 历史产物膨胀，防止磁盘被长期运行目录打爆。",
  "main_claim": "本轮应把项目缺陷修复循环从 Cap/E2E runner 收回到 Loom：Cap 只负责路由、边界、证据和收口，不直接替目标项目做设计或开发；E2E runner 只能生成 Loom defect route 和下一轮起点，而不能把 runner 自己的诊断当作实现方案。E2E 历史运行目录应默认保留最近成功样本和失败/中断样本，清理更旧成功样本，并提供 dry-run。",
  "changed_reality": [
    "当前为实施前设计评审，尚未声称代码已变更。",
    "已建立本轮生命周期包：assets/evidence/lifecycle/20260620-loom-failure-loop-and-e2e-retention-lifecycle.json。",
    "已确认现有 Loom 合同有失败回流概念，但还需要补足运行时 failure-route 包和 E2E 运行器接入。",
    "已确认 E2E 运行目录存在历史产物膨胀风险，需要新增保留与清理策略。"
  ],
  "planned_changes": [
    "扩展 assets/contracts/loom-workflow.json：新增 failure_loop_policy，明确 tester/reviewer 只能报告缺陷和路由，目标角色负责修复，Cap 不得直接修目标项目。",
    "扩展 runtime/core/loom_workflow.py：校验 failure_loop_policy 必备字段与负向样例，防止合同回退。",
    "扩展 runtime/core/loom_runtime.py：新增 failure-route 子命令，写入项目级 .redcap/state/loom/failure-routes.jsonl，并校验 root_cause、target_phase、target_role、restart_from_phase、downstream_replay_required、evidence 等字段。",
    "扩展 runtime/core/complete_revival_e2e.py：当 E2E 收敛诊断发现 open failure 或 final Prism concern 时，写入 loom-failure-route-plan.json，说明下一轮应从哪个 Loom 角色节点恢复；最终证据必须包含该计划或说明无开放项。",
    "扩展 runtime/core/complete_revival_e2e.py：新增 prune-runs 子命令，默认 dry-run 支持，默认保留最近 5 个运行目录并保留失败/中断目录，清理更旧成功目录，且不允许清理 RedCap 源码区或旧仓库。",
    "补充 self-check 覆盖：Loom 失败回流包合法/非法样例、E2E 保留策略保留失败样本、不清理最新目录、不误删非 E2E 目录。"
  ],
  "known_constraints": [
    "不得把本轮实现说成 RedCap 完整复活终局完成。",
    "不得降低 E2E 验收标准或把缺陷改成 warning。",
    "不得让 Cap 或 runner 直接修改目标项目来替代 Loom 角色修复。",
    "不得删除当前运行中的 E2E 目录、最新失败证据、或 RedCap 源码区。",
    "不得让所有小任务都强制进入重型 Loom 循环；该循环面向项目开发和失败回流。"
  ],
  "questions_for_prism": [
    "该设计是否真实把项目缺陷修复职责从 Cap 收回到 Loom 角色链？",
    "failure-route 包字段是否足以表达打回角色、重启阶段、下游重放和证据来源？",
    "是否存在新的死循环风险，尤其是 tester/reviewer 与 developer/architect 之间无限互相打回？",
    "E2E prune-runs 默认保留策略是否足够安全，是否会误删后续诊断需要的失败证据？",
    "是否有必须本轮补充的硬门禁或自检，避免这只是文档化方案？"
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


--- KIMI FILE ACCESS ---
mode: prompt-only
No file reading is authorized for this review.
