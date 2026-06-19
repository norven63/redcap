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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260618-e2e-patrol-loop-final-review/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "复核 RedCap 长任务与完整复活 E2E 边界误判修复。",
  "review_mode": "implementation_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 8,
  "known_constraint_count": 4
}

--- REVIEW REQUEST JSON ---

{
  "task": "复核 RedCap 长任务与完整复活 E2E 边界误判修复。",
  "user_intent": "Norven 要求正面修复此前任务未完成却汇报、长任务入口未真正接入、E2E 未验证 Hook 承载却继续执行的复发问题，并要求方案评审与最终实现逻辑评审都正常触发棱镜。",
  "main_claim": "本轮没有声明 RedCap 完整复活完成；本轮主张是：长任务与 E2E 的入口边界已被硬化为 active_run + 最大轮次 + 收敛守卫 + Codex CLI Hook 承载前置探针；当承载探针失败时，运行器会在 Loom 角色启动前阻断并记录阻塞，而不会继续执行或汇报 E2E 通过。",
  "changed_reality": [
    "complete_revival_e2e.py 在 run_e2e_harness 中把 carrier_probe 前置到 REDCAP_E2E_WORKER 启动前，失败时写 blocked active_run 并返回 blocked_before_project_run=true。",
    "complete_revival_e2e.py 的 self-check 增加源码级断言，要求 carrier_probe 早于 env[\"REDCAP_E2E_WORKER\"] 设置。",
    "complete-revival-e2e-acceptance-design.json 新增 codex_cli_hook_carrier_preflight 硬入口合同，明确失败时禁止启动 Loom 角色、禁止写 completion-marker、禁止声称 E2E 通过。",
    "project_install.py 生成项目级 .codex/config.toml，声明 hooks=true，避免发布安装产物缺少项目级 Hook 配置层。",
    "受控负向运行证明：当前 Codex CLI 子进程命令能返回 carrier-probe-ok，但未触发项目级 SessionStart、UserPromptSubmit、PreToolUse、PostToolUse、Stop，因此 E2E 被阻断在项目运行前。",
    "棱镜上一轮 concern 已通过 resolution.json 处理：Kimi 的反循环疑虑被接受并验证；Claude Code 的 Codex CLI Hook 承载疑虑升级为真实阻塞。"
  ],
  "evidence": [
    {
      "kind": "diff",
      "reference": "runtime/core/complete_revival_e2e.py",
      "summary": "E2E 入口前置 carrier_probe、active_run 阻断、自检源码断言和 PTY 承载稳定化。"
    },
    {
      "kind": "diff",
      "reference": "assets/contracts/complete-revival-e2e-acceptance-design.json",
      "summary": "新增 Codex CLI Hook 承载硬入口合同和当前阻塞声明。"
    },
    {
      "kind": "diff",
      "reference": "runtime/core/project_install.py",
      "summary": "项目级安装 init 生成 .codex/config.toml。"
    },
    {
      "kind": "test",
      "reference": "assets/evidence/check-receipts/20260618-e2e-patrol-loop/complete-revival-e2e-self-check.receipt.json",
      "summary": "E2E 自检通过，包含入口探针早于 worker 启动的断言。"
    },
    {
      "kind": "test",
      "reference": "assets/evidence/check-receipts/20260618-e2e-patrol-loop/long-task-contract-check.receipt.json",
      "summary": "长任务合同检查通过。"
    },
    {
      "kind": "test",
      "reference": "assets/evidence/check-receipts/20260618-e2e-patrol-loop/carrier-preflight-block.receipt.json",
      "summary": "Codex CLI Hook 承载失败时，E2E 入口按预期返回阻断。"
    },
    {
      "kind": "test",
      "reference": "assets/evidence/check-receipts/20260618-e2e-patrol-loop/carrier-preflight-no-role-artifacts.receipt.json",
      "summary": "阻断后未出现 Loom 角色或最终完成产物。"
    },
    {
      "kind": "document",
      "reference": "assets/evidence/prism/20260618-e2e-patrol-loop/resolution.json",
      "summary": "上一轮棱镜 concern 的处理：部分接受，Codex CLI Hook 承载升级阻塞。"
    }
  ],
  "review_mode": "implementation_review",
  "risk_level": "high",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "known_constraints": [
    "不得把本轮边界修复说成 RedCap 完整复活完成。",
    "不得绕过、降级或放松 Hook 能力；承载失败只能阻断或实现等价承载，不能伪装通过。",
    "如果认为仍缺少真实运行入口或验证证据，必须给出 block 或 concern，不要因有合同/收据就放行。",
    "最终答复必须说明当前真实状态和阻塞，不得宣称可以投入工程生产。"
  ]
}


--- KIMI FILE ACCESS ---
mode: prompt-only
No file reading is authorized for this review.
