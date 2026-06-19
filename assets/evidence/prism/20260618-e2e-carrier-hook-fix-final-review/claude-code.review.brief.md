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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260618-e2e-carrier-hook-fix-final-review/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "Codex CLI 项目级 Hook 承载探针修复后的实现复审",
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
  "task": "Codex CLI 项目级 Hook 承载探针修复后的实现复审",
  "user_intent": "继续推进 RedCap 复活直到可验证交付；任何修复不得绕过、降级或用形式产物替代真实运行能力。",
  "main_claim": "carrier_probe 已从弱口头成功判定升级为真实文件副作用、完整 Hook 事件、可配置外部服务隔离、失败原因分类、重试不早停和自检负向用例共同约束的项目级承载探针。",
  "changed_reality": [
    "新增 codex_mcp_isolation_argv，通过 REDCAP_E2E_CODEX_DISABLED_MCP_SERVERS 配置禁用用户全局 MCP 服务器，默认包含 openaiDeveloperDocs、node_repl、neon、railway。",
    "carrier_probe 现在要求子 Codex CLI 通过 shell 创建 carrier-shell-marker.txt，内容必须是 carrier-shell-ok。",
    "carrier_probe 的单次尝试必须同时满足命令成功、marker 正确、SessionStart/UserPromptSubmit/PreToolUse/PostToolUse/Stop 五类 Hook 事件完整，才允许通过。",
    "命令成功但 marker 缺失、marker 内容错误、Hook 缺失时都会记录 failure_reasons，并继续按尝试上限重试。",
    "carrier_probe 完成后会删除 marker 文件，并在结果中记录 marker_removed_after_probe。",
    "self-check 新增 carrier_probe_attempt_decision 负向测试，覆盖命令成功但无 marker、marker 错误、Hook 缺失、命令失败四类旧误判路径。",
    "build_codex_role_argv 与 carrier_probe 都加入 MCP 隔离参数；角色运行记录也写入 codex_disabled_mcp_servers。"
  ],
  "previous_prism_concerns_addressed": [
    {
      "concern": "无法确认实现是否真正强制 marker 与 Hook 完整。",
      "response": "已落地 carrier_probe_attempt_decision 并接入 carrier_probe；真实 carrier-probe 输出显示 marker_exists=true、marker_text=carrier-shell-ok、五类 Hook 事件完整。"
    },
    {
      "concern": "MCP 隔离不应硬编码为唯一列表。",
      "response": "已改为 REDCAP_E2E_CODEX_DISABLED_MCP_SERVERS 环境变量可配置，默认值只是当前已知噪音源。"
    },
    {
      "concern": "需要区分失败原因并清理 marker。",
      "response": "attempts[].failure_reasons 已区分 command_failed、marker_missing、marker_content_mismatch、hook_events_missing；marker_removed_after_probe=true。"
    },
    {
      "concern": "需要负向测试和通过运行证据。",
      "response": "self-check 覆盖负向判定；py_compile、self-check --skip-carrier-probe、完整 self-check、git diff --check、真实 carrier-probe 均已通过。"
    }
  ],
  "verification_evidence": [
    {
      "command": "python3 -m py_compile runtime/core/complete_revival_e2e.py",
      "result": "通过，退出码 0"
    },
    {
      "command": "runtime/bin/redcap complete-revival-e2e self-check --skip-carrier-probe",
      "result": "通过，输出 REDCAP_AI_E2E_SELF_CHECK_OK"
    },
    {
      "command": "git diff --check",
      "result": "通过，退出码 0"
    },
    {
      "command": "runtime/bin/redcap complete-revival-e2e carrier-probe --work-root /Users/norven/workspace/redcap-e2e-runs/20260618-carrier-hook-fix-verify --timeout-seconds 240",
      "result": "通过，输出 REDCAP_AI_E2E_CARRIER_PROBE_OK；events=[SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, Stop]；missing_events=[]；marker_removed_after_probe=true"
    },
    {
      "command": "runtime/bin/redcap complete-revival-e2e self-check",
      "result": "通过，输出 REDCAP_AI_E2E_SELF_CHECK_OK"
    }
  ],
  "review_mode": "implementation_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "file_access": {
    "mode": "bounded-read",
    "purpose": "复核 carrier_probe、Codex CLI 角色承载参数和 self-check 是否真正解决前一轮 concern，且没有降级完整 E2E。",
    "max_files": 3,
    "max_bytes_per_file": 650000,
    "max_total_bytes": 1000000,
    "allowed_paths": [
      "runtime/core/complete_revival_e2e.py",
      "runtime/bin/redcap",
      "assets/evidence/prism/20260618-e2e-carrier-hook-fix/merge.json"
    ]
  },
  "questions_for_prism": [
    "前一轮 concern 的 minimum fixes 是否已经被真实实现和验证证据覆盖？",
    "carrier_probe_attempt_decision 与 carrier_probe 的通过条件是否还能出现命令成功但 Hook 或 marker 缺失却误判通过的路径？",
    "MCP 隔离、插件隔离和 apps 隔离是否属于可接受的外部噪音隔离，而不是降级 RedCap 核心 E2E 能力？",
    "是否可以进入完整 E2E 运行？如果不能，请给出必须先修的最小问题。"
  ],
  "forbidden_shortcuts": [
    "不得把缺少完整 E2E 运行作为本轮 carrier 修复未通过的理由；本轮只评估是否可以进入完整 E2E。",
    "不得要求减少 REQUIRED_HOOK_EVENTS。",
    "不得接受伪造 Hook 事件或跳过 carrier_probe。",
    "如果 verdict=concern 或 block，必须指出可执行、最小、可验证的修复项。"
  ]
}
