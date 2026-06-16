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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260616-archive-resume-e2e-continuation/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "评审归档恢复后继续 RedCap 完整复活 E2E 闭环的执行方案。",
  "review_mode": "execution_review",
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
  "task": "评审归档恢复后继续 RedCap 完整复活 E2E 闭环的执行方案。",
  "user_intent": "Norven 恢复了被归档的会话，并授权 Cap 恢复之前被中断的任务，继续完成直至所有目标达成。",
  "main_claim": "当前正确动作是先提交上一轮已经验证过的 E2E 入口识别与角色玩家关系探针修复，再执行下一轮外部项目完整 E2E；如果下一轮失败，则继续按失败证据修复并迭代，而不是停在状态汇报。",
  "changed_reality": [
    "第 31 轮 E2E 失败暴露出运行器把 public/index.html 误判为缺少入口。",
    "第 31 轮 E2E 还暴露出角色玩家关系探针只支持 players[] + playerId，误伤 characters[].player 这种直接玩家名关系。",
    "对应修复已经本地实现并通过 py_compile、complete-revival-e2e self-check、git diff --check、手动 Round31 项目探针和 runtime/bin/redcap check。",
    "归档恢复后需要重新建立生命周期包和门禁记录，再继续提交与下一轮 E2E。"
  ],
  "evidence": [
    {
      "kind": "lifecycle",
      "reference": "assets/evidence/lifecycle/20260616-archive-resume-e2e-continuation-lifecycle.json",
      "summary": "恢复后继续推进的生命周期边界；不包含完成声明。"
    },
    {
      "kind": "lifecycle",
      "reference": "assets/evidence/lifecycle/20260616-e2e-entrypoint-and-direct-player-lifecycle.json",
      "summary": "上一轮 E2E 入口识别和直接玩家名关系探针修复的生命周期证据。"
    },
    {
      "kind": "code",
      "reference": "runtime/core/complete_revival_e2e.py",
      "summary": "完整 E2E 运行器；已加入入口发现、public 交付物证据、直接玩家名关系探针。"
    },
    {
      "kind": "code",
      "reference": "runtime/core/e2e_independent_observer.py",
      "summary": "独立观察者；已加入入口发现和 public 交付物复核。"
    },
    {
      "kind": "external-e2e",
      "reference": "/Users/norven/workspace/redcap-e2e-runs/run-20260616-round31/",
      "summary": "第 31 轮失败项目和手动回归探针证据所在目录。"
    }
  ],
  "review_mode": "execution_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "known_constraints": [
    "不允许通过降低 E2E 验收标准来绕过失败。",
    "不允许把上一轮局部修复说成 RedCap 完整复活完成。",
    "下一轮 E2E 必须运行在 /Users/norven/workspace/redcap-e2e-runs/ 下的独立目录，不污染 RedCap 源工作区。",
    "如果 E2E 失败，必须把失败转换为可验证修复项继续推进。",
    "提交前必须保持 runtime/bin/redcap check 通过。"
  ],
  "questions_for_prism": [
    "在上述证据下，是否可以提交上一轮入口识别与角色玩家关系探针修复？",
    "下一轮 E2E 开始前还缺少哪些硬性前置检查？",
    "哪些证据必须通过，才可以把下一轮 E2E 视为阶段性有效？",
    "是否存在把局部修复、报告或账目误认为终局完整复活的风险？如果有，应如何约束？"
  ]
}
