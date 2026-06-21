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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260621-rsp-01-advisory-stop-replay/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "RSP-01 Stop 建议型检查主轴保持回放实施评审",
  "review_mode": "design_review",
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
  "task": "RSP-01 Stop 建议型检查主轴保持回放实施评审",
  "user_intent": "Norven 要求逐项实施残留问题，不允许合批空转。当前只处理 RSP-01：Stop 建议型检查可以指出问题，但不得让二次回答围绕 Stop 本身偏离用户原始问题；实现必须保留 Stop 的防空转、防误收口能力。",
  "main_claim": "本轮尚未声明完成；准备在现有 advisory-stop 检查中补强主轴保持回放，让“用户问状态/未完成项，回答却主要解释 Stop 拦截”的负向样本失败，并生成 RSP-01 对应完成证据。",
  "changed_reality": [
    "advisory-stop 已有原始任务锚点、最大轮次熔断和 Cap 覆盖标记自检。",
    "当前 RSP-01 仍缺少专门覆盖“状态问题被 Stop 建议带偏”的回放证据。",
    "本轮必须改动运行时检查或回放逻辑，并用正向/负向样本证明 Stop 建议不抢主轴。"
  ],
  "evidence": [
    {
      "kind": "document",
      "reference": "assets/docs/residual-todo-final-solution-plan.md",
      "summary": "RSP-01 要求 Stop 只输出结构化建议、Cap 可仲裁、二次回答保留用户原问题主轴，并建立误伤回放集。"
    },
    {
      "kind": "code",
      "reference": "runtime/core/advisory_stop.py",
      "summary": "RSP-01 的检查入口和当前回放逻辑。"
    },
    {
      "kind": "code",
      "reference": "runtime/host-adapters/codex/codex-hook.py",
      "summary": "Stop 事件实际生成建议型收口提示的宿主适配器。"
    },
    {
      "kind": "code",
      "reference": "runtime/core/rsp_contract.py",
      "summary": "完成声明必须通过正向/负向验收、证据路径和真实行为变化检查。"
    }
  ],
  "review_mode": "design_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "file_access": {
    "mode": "bounded-read",
    "paths": [
      "assets/docs/residual-todo-final-solution-plan.md",
      "runtime/core/advisory_stop.py",
      "runtime/host-adapters/codex/codex-hook.py",
      "runtime/core/rsp_contract.py",
      "runtime/bin/redcap"
    ],
    "max_files": 8,
    "max_bytes_per_file": 30000,
    "max_total_bytes": 90000
  },
  "known_constraints": [
    "不删除 Stop 检查，不把 Stop 改成只记录不拦截。",
    "不允许 Stop 建议成为新的用户任务主轴。",
    "正向样本必须证明有问题时仍能给出建议。",
    "负向样本必须证明回答围绕 Stop 而非用户原问题时会失败。",
    "本轮只允许关闭 RSP-01 当前机器化落地范围，不关闭 RSP-02/RSP-21/RSP-25。"
  ],
  "questions_for_prism": [
    "RSP-01 的最小实现是否应只扩展 advisory_stop.py 的回放集，还是必须修改 codex-hook.py 的 Stop 输出结构？",
    "状态问题主轴保持的负向样本应检查哪些字段，才能避免再次把 Stop 建议当新任务？",
    "有哪些改法会表面降低误伤，实质削弱 Stop 防空转或防误收口能力？"
  ]
}
