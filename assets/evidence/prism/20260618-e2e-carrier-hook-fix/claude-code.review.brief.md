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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260618-e2e-carrier-hook-fix/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "修复 Codex CLI 项目级 Hook 承载探针，恢复完整 E2E 前置条件。",
  "review_mode": "design_review",
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
  "task": "修复 Codex CLI 项目级 Hook 承载探针，恢复完整 E2E 前置条件。",
  "user_intent": "继续推进 RedCap 复活直到可验证交付，但不允许绕过、降级或用形式产物替代真实运行能力。",
  "main_claim": "当前 E2E 阻塞不是 Codex CLI 项目级 Hook 完全不可用，而是 carrier_probe 的成功条件过弱、重试逻辑过早停止、子 Codex 继承了无关全局外部服务噪音；应通过真实文件副作用、严格事件检查、缺失事件继续重试和子进程隔离来正面修复。",
  "changed_reality": [
    "实验证明：在外部项目中要求子 Codex 创建真实文件后，SessionStart、UserPromptSubmit、PreToolUse、PostToolUse、Stop 五类项目级 Hook 事件全部触发。",
    "实验证明：使用 mcp_servers.<name>.enabled=false 配置可以隔离 neon、railway 等全局 MCP 噪音，且不影响五类 Hook 触发。",
    "源码现状：carrier_probe 仍使用 `pwd + carrier-probe-ok` 的弱提示，未强制真实文件副作用。",
    "源码现状：carrier_probe 在 result.ok 但 missing_events 非空时会 break，导致没有用完重试机会。"
  ],
  "problem_statement": "完整 E2E 在项目级 Hook 承载探针处阻塞。原探针使用 `pwd + carrier-probe-ok` 作为成功条件，模型可以口头回答而不触发工具路径，导致 PreToolUse/PostToolUse/Stop 缺失；同时当前代码在命令成功但 Hook 缺失时提前停止重试，漏掉了可恢复场景。",
  "diagnostic_evidence": [
    {
      "case": "原 carrier_probe 失败",
      "result": "events=[]，missing_events 包含 SessionStart、UserPromptSubmit、PreToolUse、PostToolUse、Stop；命令本身 exit_code=0 且 completion_marker=carrier-probe-ok。"
    },
    {
      "case": "只禁用 plugins 的复现",
      "command": "REDCAP_E2E_CODEX_INTERACTIVE_DISABLE_PLUGINS=1 REDCAP_E2E_CARRIER_PROBE_MAX_ATTEMPTS=1 runtime/bin/redcap complete-revival-e2e carrier-probe --work-root /Users/norven/workspace/redcap-e2e-runs/20260618-carrier-debug-disable-plugins --timeout-seconds 240",
      "result": "仍然 events=[]；说明 plugins 不是唯一根因。"
    },
    {
      "case": "要求子 Codex 创建真实文件副作用",
      "command_shape": "codex --enable hooks --dangerously-bypass-hook-trust ... --cd <project> ... prompt=create carrier-shell-marker.txt",
      "result": "marker_exists=true；events=[SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, Stop]。"
    },
    {
      "case": "显式隔离外部 MCP 与插件噪音",
      "command_shape": "追加 -c mcp_servers.neon.enabled=false、railway.enabled=false、openaiDeveloperDocs.enabled=false、node_repl.enabled=false，并 --disable plugins --disable apps",
      "result": "marker_exists=true；events=[SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, Stop]；无 neon/railway 启动噪音。"
    }
  ],
  "proposed_fix": [
    "把 carrier_probe 的提示从 `执行 pwd 后口头回答` 改为 `必须通过 shell 创建 carrier-shell-marker.txt，内容为 carrier-shell-ok，然后再回答 carrier-probe-ok`。",
    "把 carrier_probe 的成功条件改为：命令成功、completion marker 或 completion file 达成、marker 文件存在且内容正确、五类 Hook 事件全部出现。只要 Hook 缺失或 marker 缺失，即使命令返回 ok，也继续按上限重试。",
    "为 Codex 子进程增加可审计的隔离参数：默认禁用用户全局 MCP 服务器 openaiDeveloperDocs、node_repl、neon、railway，并默认禁用 plugins/apps，避免外部登录态或插件启动噪音影响项目级 RedCap E2E。",
    "把隔离策略记录进 carrier_probe 输出，避免未来误判；不减少 REQUIRED_HOOK_EVENTS，不引入伪造事件，不跳过真实 Codex CLI。"
  ],
  "non_goals_and_forbidden_shortcuts": [
    "不得把 REQUIRED_HOOK_EVENTS 减少为 SessionStart/UserPromptSubmit。",
    "不得用手动写 carrier-hook-events.jsonl 伪造 Hook 事件。",
    "不得改成非 Codex CLI 的假承载器。",
    "不得因为 MCP 噪音而跳过 carrier_probe 或把完整 E2E 标为通过。"
  ],
  "review_mode": "design_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "file_access": {
    "mode": "bounded-read",
    "purpose": "评审拟修改点是否正面修复项目级 Hook 承载，且没有降级 RedCap E2E。",
    "max_files": 4,
    "max_bytes_per_file": 650000,
    "max_total_bytes": 1200000,
    "allowed_paths": [
      "runtime/core/complete_revival_e2e.py",
      "assets/contracts/complete-revival-e2e-acceptance-design.json",
      "assets/contracts/project-installation.json",
      ".codex/hooks.json"
    ]
  },
  "questions_for_prism": [
    "该修复方案是否正面解决了项目级 Hook 承载探针误判，而不是绕过或降级？",
    "默认隔离用户全局 MCP、plugins、apps 是否会损害 RedCap E2E 的核心能力？若有风险，请指出必须保留的能力边界。",
    "实施前是否还有必须补充的检查或负向测试？如果没有，请 verdict=pass。"
  ]
}
