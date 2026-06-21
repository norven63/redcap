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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260621-rsp-25-hook-quality-metrics/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "RSP-25 Hook 误伤率与漏检率持续度量实施评审",
  "review_mode": "design_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 5,
  "known_constraint_count": 4
}

--- REVIEW REQUEST JSON ---

{
  "task": "RSP-25 Hook 误伤率与漏检率持续度量实施评审",
  "task_id": "20260621-rsp-25-hook-quality-metrics",
  "title": "RSP-25 Hook 误伤率持续度量",
  "risk_level": "medium",
  "user_intent": "实施残留任务 RSP-25：建立 Hook 质量样本、误伤率、漏检率和趋势阈值，避免只靠个案修复证明 Hook 稳定。",
  "main_claim": "本轮尚未声明完成；准备新增 hook-quality 度量合同和运行检查，回放误伤、漏检、正确阻断、正确放行四类样本，并让误伤/漏检超阈值时失败。",
  "changed_reality": [
    "RSP-21 已补齐 advisory-stop 健康三态，但只证明 degraded、blocked 不会冒充 healthy，没有持续误伤率和漏检率趋势度量。",
    "runtime/core/check_runner.py 已可接入独立检查步骤，适合把 hook-quality 作为常规聚合检查而非 Stop 热路径检查。",
    "本轮必须改动运行时代码、合同和聚合检查，不允许只补文档描述。"
  ],
  "target_reality": "新增可运行的 hook-quality 度量入口，能够回放误伤、漏检、正确阻断、正确放行四类样本；输出误伤率、漏检率、变化原因；当误伤或漏检超过合同阈值时失败；阈值变更必须进入棱镜评审。",
  "evidence": [
    {
      "kind": "document",
      "reference": "assets/docs/residual-todo-final-solution-plan.md",
      "summary": "RSP-25 要求 Hook 质量样本集、误伤率、漏检率和趋势阈值。"
    },
    {
      "kind": "code",
      "reference": "runtime/core/advisory_stop.py",
      "summary": "建议型 Stop 主轴回放、健康三态和自检入口。"
    },
    {
      "kind": "code",
      "reference": "runtime/host-adapters/codex/codex-hook.py",
      "summary": "Codex Hook 运行适配器和事件记录来源。"
    },
    {
      "kind": "code",
      "reference": "runtime/core/check_runner.py",
      "summary": "聚合检查入口。"
    },
    {
      "kind": "contract",
      "reference": "assets/contracts/advisory-stop.json",
      "summary": "建议型 Stop 合同和健康状态规则。"
    }
  ],
  "review_mode": "design_review",
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
      "runtime/core/check_runner.py",
      "assets/contracts/advisory-stop.json",
      "runtime/bin/redcap"
    ],
    "max_files": 10,
    "max_bytes_per_file": 50000,
    "max_total_bytes": 180000
  },
  "proposed_changes": [
    "新增 assets/contracts/hook-quality-metrics.json，记录样本分类、阈值、阈值变更评审要求和输出字段。",
    "新增 runtime/core/hook_quality_metrics.py，提供 check 和 self-check 命令，读取合同样本并输出 redcap-hook-quality-metrics-report。",
    "将 runtime/bin/redcap 接入 hook-quality check|self-check。",
    "将 runtime/core/check_runner.py 接入 hook-quality-metrics-check。",
    "建立 RSP-25 证据、完成声明、生命周期证据和自我净化条目。"
  ],
  "quality_requirements": [
    "误伤样本失败必须导致报告失败，不能被归类为 healthy。",
    "漏检高风险样本失败必须导致报告失败。",
    "样本至少覆盖 false_positive、false_negative、true_block、true_pass 四类。",
    "阈值默认不能靠放宽来通过；阈值变更需要在合同中记录 prism_review_required=true。",
    "RSP-25 只关闭 Hook 质量度量，不声明 Stop 永久零误伤或 RedCap 完整复活。"
  ],
  "known_non_goals": [
    "不替换 RSP-21 的健康三态检查。",
    "不声称未来真实会话永远零误伤。",
    "不运行完整 E2E 二轮验收。"
  ],
  "known_constraints": [
    "不降低或绕开 Stop 的核心收口检查能力。",
    "不把完整 RedCap 检查塞进 Stop 热路径。",
    "误伤率和漏检率阈值不能静默放宽；阈值变更必须在合同中声明需要 Prism 评审。",
    "本轮只关闭 RSP-25 当前机器化度量范围，不关闭 E2E 二轮验收或 RedCap 完整复活父目标。"
  ],
  "files_to_review": [
    "assets/docs/residual-todo-final-solution-plan.md",
    "runtime/core/advisory_stop.py",
    "runtime/host-adapters/codex/codex-hook.py",
    "runtime/core/check_runner.py",
    "assets/contracts/advisory-stop.json"
  ],
  "questions_for_prism": [
    "这个实现边界是否足以防止 RSP-25 继续停留在个案修复？",
    "样本分类和阈值策略是否存在放宽标准换通过的风险？",
    "是否需要把质量度量接入 Stop 热路径，还是只接入聚合检查和 Hook 变更验收？",
    "还缺哪些负向样本，才能证明误伤回放失败和漏检高风险写入都会失败？"
  ]
}


--- AUTHORIZED FILE ACCESS ---

mode: bounded-read

Authorized bundle JSON: /Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260621-rsp-25-hook-quality-metrics/kimi.review.brief.files.json

Bundle sha256: 3b46b1d335cf150a727fbf8f1d64c68bd1eb4eccdfe758f8902690209b6e8407

Rules:

- You may read only this generated bundle JSON if file evidence is needed.

- Do not inspect the original source paths directly.

- Do not run commands.

- If the bundle is insufficient, report missing evidence instead of fetching more files.

