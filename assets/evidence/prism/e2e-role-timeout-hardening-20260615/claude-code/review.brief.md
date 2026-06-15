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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260615-e2e-role-timeout-hardening-request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "评审 RedCap E2E 中 Loom 角色执行抗抖动修复方案：独立 Codex CLI 角色不要继承用户级 xhigh 推理和插件配置，失败时允许有界重试，同时保持项目级 Hook、角色 session_id、角色隔离和证据链可验。",
  "review_mode": "design_review",
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
  "task": "评审 RedCap E2E 中 Loom 角色执行抗抖动修复方案：独立 Codex CLI 角色不要继承用户级 xhigh 推理和插件配置，失败时允许有界重试，同时保持项目级 Hook、角色 session_id、角色隔离和证据链可验。",
  "user_intent": "Norven 授权继续所有未完成任务直至最终目标。第九轮 E2E 暴露 developer 角色在独立 Codex CLI 中因传输抖动和高推理配置 420 秒超时且没有落盘，必须正面修复运行机，而不是绕过 Loom 或人工补项目。",
  "main_claim": "应修改 E2E 运行器：Loom 角色调用使用 --ignore-user-config、显式低推理配置和稳定模型参数，减少用户插件与 xhigh 推理对外部角色的影响；对无产物、传输类失败做最多一次有界重试；最终 session_id 仍来自项目级 Hook 的 UserPromptSubmit 事件，若多次尝试只把成功尝试作为角色上下文，失败尝试作为重试证据保留。",
  "changed_reality": [
    "第九轮 E2E 在持久目录 /Users/norven/workspace/redcap-e2e-runs/run-20260615-round9 执行，源仓库 guard 证明没有被污染。",
    "product_manager 与 architect 独立 Codex CLI 角色完成，developer 角色 exit_code=124、timed_out=true、process_group_killed=true。",
    "developer raw stderr 出现 responses_websocket tls handshake eof、stream disconnected retry 等传输抖动证据，且没有生成 implementation-log.json 或 role-artifacts/developer.json。",
    "当前 CLI 继承 ~/.codex/config.toml 中 model_reasoning_effort=xhigh 和大量插件配置，角色执行消耗和启动噪音过大。"
  ],
  "evidence": [
    {
      "kind": "runtime-e2e",
      "reference": "/Users/norven/workspace/redcap-e2e-runs/run-20260615-round9/redcap-e2e-简化版-trpg-活动组织平台-交付一个本地可运行的桌面角色扮演活动组织/.redcap/evidence/e2e/role-runs/developer.json",
      "summary": "developer 角色超时且未产出角色证据"
    },
    {
      "kind": "runtime-e2e",
      "reference": "/Users/norven/workspace/redcap-e2e-runs/run-20260615-round9/redcap-e2e-简化版-trpg-活动组织平台-交付一个本地可运行的桌面角色扮演活动组织/.redcap/evidence/e2e/role-raw/developer.stderr.txt",
      "summary": "包含传输抖动、websocket 失败和 stream disconnected 重试证据"
    },
    {
      "kind": "code",
      "reference": "runtime/core/complete_revival_e2e.py",
      "summary": "当前运行器生成 Codex CLI 角色命令并构建角色 session manifest"
    }
  ],
  "review_mode": "design_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "questions": [
    "该修复是否正面解决角色执行超时问题，而不是绕过 Loom？",
    "使用 --ignore-user-config 和低推理配置是否会破坏项目级 Hook 或角色 session_id 采集？",
    "一次有界重试如何避免多 session 被误判为角色上下文丢失？",
    "还需要哪些验证才能允许重新运行 E2E？"
  ],
  "known_constraints": [
    "不能降低 Loom 分角色要求，不能改成 Cap 自己写项目。",
    "不能取消项目级 Hook、session_id、角色产物和棱镜最终复核。",
    "不能把重试后的成功说成同一 AI 上下文连续；失败尝试必须作为证据保留，最终角色上下文必须指向成功尝试。",
    "不能只延长超时；必须减少外部角色执行噪音并保留原能力。"
  ]
}
