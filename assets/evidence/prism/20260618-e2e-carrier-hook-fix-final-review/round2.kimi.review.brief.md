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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260618-e2e-carrier-hook-fix-final-review/request-round2.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "Codex CLI 项目级 Hook 承载探针修复后的二轮实现复审",
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
  "task": "Codex CLI 项目级 Hook 承载探针修复后的二轮实现复审",
  "user_intent": "继续推进 RedCap 复活直到可验证交付；任何修复不得绕过、降级或用形式产物替代真实运行能力。",
  "main_claim": "前一轮 implementation_review concern 已处理：本轮提供关键源码摘录、负向判定、真实失败复现、修复后真实通过证据，确认 carrier_probe 不再因提示词回显、缺失 marker、缺失 Hook 或清理失败而误判通过。",
  "changed_reality": [
    "carrier_probe_attempt_decision 统一决定单次尝试是否通过，并对 command_failed、marker_missing、marker_content_mismatch、hook_events_missing 分类。",
    "marker 内容允许文本文件常见的行尾换行，但正文必须归一化为 carrier-shell-ok；错误正文仍失败。",
    "carrier_probe 的最终 ok 也调用同一个 decision，不再存在尝试记录和最终汇总双轨判定。",
    "carrier_probe 用 finally 调用 cleanup_marker，并把 marker_cleanup_error 写进结果和 failures。",
    "completion marker 的字面量 carrier-probe-ok 不再出现在提示词里，避免终端回显误判；提示词只描述用连字符连接 carrier、probe、ok。",
    "round3 真实探针暴露 completion marker 被提示词回显误判问题，round4 修复后真实探针通过。"
  ],
  "source_excerpts": {
    "carrier_probe_attempt_decision": [
      "def carrier_probe_attempt_decision(...):",
      "    marker_normalized = marker_text.rstrip(\"\\r\\n\") if marker_exists and marker_text is not None else None",
      "    marker_ok = marker_normalized == \"carrier-shell-ok\"",
      "    if not command_ok: failure_reasons.append(\"command_failed\")",
      "    if not marker_exists: failure_reasons.append(\"marker_missing\")",
      "    elif not marker_ok: failure_reasons.append(\"marker_content_mismatch\")",
      "    if missing_events: failure_reasons.append(\"hook_events_missing\")",
      "    return {\"ok\": command_ok and marker_ok and not missing_events, ...}"
    ],
    "carrier_probe_core": [
      "argv.append(\"...最终只回答三个英文词，并用英文连字符连接：carrier、probe、ok。不要只口头说明。\")",
      "result = run_command_pty(... completion_markers=[\"carrier-probe-ok\"], completion_files=[marker_path], settle_seconds=10.0)",
      "attempt_decision = carrier_probe_attempt_decision(command_ok=bool(result[\"ok\"]), marker_exists=marker_exists, marker_text=marker_text, missing_events=missing)",
      "attempts.append({\"ok\": attempt_decision[\"ok\"], \"failure_reasons\": attempt_decision[\"failure_reasons\"], ...})",
      "if attempt_decision[\"ok\"]: break",
      "finally: cleanup_marker()",
      "final_decision = carrier_probe_attempt_decision(command_ok=bool(result.get(\"ok\")), marker_exists=marker_text is not None, marker_text=marker_text, missing_events=missing)",
      "\"ok\": final_decision[\"ok\"]",
      "if marker_cleanup_error: failures.append(...); probe[\"ok\"] = False"
    ],
    "self_check_negative_tests": [
      "命令成功但没有标记文件 -> marker_missing 且不得 ok",
      "命令成功但标记内容错误 -> marker_content_mismatch 且不得 ok",
      "命令成功且标记正确但 Hook 缺失 -> hook_events_missing 且不得 ok",
      "命令失败但标记和 Hook 看似正常 -> command_failed 且不得 ok",
      "命令成功、标记正确、Hook 完整 -> ok",
      "命令成功、标记正确且只有行尾换行、Hook 完整 -> ok",
      "自检禁止提示词直接包含“最终只回答 carrier-probe-ok”"
    ]
  },
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
      "command": "runtime/bin/redcap complete-revival-e2e carrier-probe --work-root /Users/norven/workspace/redcap-e2e-runs/20260618-carrier-hook-fix-verify-round3 --timeout-seconds 240",
      "result": "失败，但这是本轮发现并修复的新问题：completion marker 字面量出现在提示词里，曾导致提示词回显被误判；attempts 中出现 marker_missing/hook_events_missing 或 marker_content_mismatch，证明失败没有被误判通过。"
    },
    {
      "command": "runtime/bin/redcap complete-revival-e2e carrier-probe --work-root /Users/norven/workspace/redcap-e2e-runs/20260618-carrier-hook-fix-verify-round4 --timeout-seconds 240",
      "result": "通过，输出 REDCAP_AI_E2E_CARRIER_PROBE_OK；events=[SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, Stop]；missing_events=[]；attempt 1 ok；marker_text='carrier-shell-ok\\n'；marker_removed_after_probe=true；marker_cleanup_error=null。"
    },
    {
      "command": "runtime/bin/redcap complete-revival-e2e self-check",
      "result": "通过，输出 REDCAP_AI_E2E_SELF_CHECK_OK"
    }
  ],
  "previous_concerns_response": [
    {
      "provider": "kimi",
      "concern": "关键逻辑和负向测试不可检。",
      "response": "本请求直接内嵌关键源码摘录、失败复现、通过证据；同时 file_access 允许读取 runtime/core/complete_revival_e2e.py。"
    },
    {
      "provider": "claude-code",
      "concern": "验证自引用，负面路径未经独立验证，marker 清理需 finally。",
      "response": "round3 真实探针证明负面路径不会误判通过；self-check 覆盖纯函数负向分支；marker 清理已放入 finally；round4 真实探针证明正常路径可用。"
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
    "purpose": "二轮复核 carrier_probe 修复是否可以放行进入完整 E2E。",
    "max_files": 2,
    "max_bytes_per_file": 700000,
    "max_total_bytes": 900000,
    "allowed_paths": [
      "runtime/core/complete_revival_e2e.py",
      "assets/evidence/prism/20260618-e2e-carrier-hook-fix-final-review/merge.json"
    ]
  },
  "questions_for_prism": [
    "基于源码摘录和允许读取的源文件，是否仍存在命令成功但 marker 或 Hook 缺失却误判通过的路径？",
    "completion marker 不再直接出现在提示词后，是否已解决提示词回显误判？",
    "finally 清理和 marker_cleanup_error 处理是否足以处理 marker 残留风险？",
    "是否可以放行进入完整 E2E？如果不能，请只列必须先修、可验证、不可推迟的问题。"
  ],
  "forbidden_shortcuts": [
    "不得要求减少 REQUIRED_HOOK_EVENTS。",
    "不得接受伪造 Hook 事件或跳过 carrier_probe。",
    "不得把“尚未运行完整 E2E”作为 carrier 修复未通过的理由；本轮只判断是否可以进入完整 E2E。"
  ]
}


--- AUTHORIZED FILE ACCESS ---

mode: bounded-read

Authorized bundle JSON: /Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260618-e2e-carrier-hook-fix-final-review/round2.kimi.review.brief.files.json

Bundle sha256: e5861d48d763e41236bb2029d8de4623a35814d4a322c193937f59df5e76ac52

Rules:

- You may read only this generated bundle JSON if file evidence is needed.

- Do not inspect the original source paths directly.

- Do not run commands.

- If the bundle is insufficient, report missing evidence instead of fetching more files.

