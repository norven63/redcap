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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260621-rsp-25-hook-quality-metrics/request-evidence-refresh.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "RSP-25 Hook 质量度量证据补强复审",
  "review_mode": "implementation_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 6,
  "known_constraint_count": 2
}

--- REVIEW REQUEST JSON ---

{
  "task": "RSP-25 Hook 质量度量证据补强复审",
  "task_id": "20260621-rsp-25-hook-quality-metrics",
  "risk_level": "medium",
  "user_intent": "复核上一轮 concern 是否已被证据补强消除：负向探针收据可见，样本来源和标注审计可见。",
  "main_claim": "本轮补强了 RSP-25 证据包：所有负向探针已有独立收据和摘要；合同中的 40 个样本均绑定真实 Hook 事件行号、事件哈希和来源字段，并标注独立评审需求。",
  "changed_reality": [
    "assets/evidence/rsp/rsp-25-negative-probe-summary.json 汇总五个负向探针的退出码、失败原因、样本计数和指标。",
    "assets/contracts/hook-quality-metrics.json 的每个样本都包含 source_kind=real_hook_event、events_jsonl_line、events_jsonl_sha256、event_id。",
    "runtime/core/hook_quality_metrics.py 会校验样本来源字段，缺失 event_id、line 或 hash 会失败。",
    "hook-quality check 报告 sample_provenance.unique_source_event_count=40。",
    "全部 RSP-25 收据已刷新。"
  ],
  "evidence": [
    {
      "kind": "contract",
      "reference": "assets/contracts/hook-quality-metrics.json",
      "summary": "40 个样本、真实 Hook 事件来源、标注审计和阈值治理。"
    },
    {
      "kind": "code",
      "reference": "runtime/core/hook_quality_metrics.py",
      "summary": "新增 source_event 来源字段校验和 sample_provenance 报告。"
    },
    {
      "kind": "evidence",
      "reference": "assets/evidence/rsp/rsp-25-negative-probe-summary.json",
      "summary": "五个负向探针的直接摘要。"
    },
    {
      "kind": "receipt",
      "reference": "assets/evidence/check-receipts/20260621-rsp-25-hook-quality-metrics/hook-quality-false-positive-failure.receipt.json",
      "summary": "误伤负向探针收据。"
    },
    {
      "kind": "receipt",
      "reference": "assets/evidence/check-receipts/20260621-rsp-25-hook-quality-metrics/hook-quality-false-negative-failure.receipt.json",
      "summary": "漏检负向探针收据。"
    },
    {
      "kind": "receipt",
      "reference": "assets/evidence/check-receipts/20260621-rsp-25-hook-quality-metrics/hook-quality-threshold-relaxed-unreviewed.receipt.json",
      "summary": "未评审阈值放宽负向探针收据。"
    }
  ],
  "review_mode": "implementation_review",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "file_access": {
    "mode": "bounded-read",
    "paths": [
      "assets/contracts/hook-quality-metrics.json",
      "runtime/core/hook_quality_metrics.py",
      "assets/evidence/rsp/rsp-25-negative-probe-summary.json",
      "assets/evidence/check-receipts/20260621-rsp-25-hook-quality-metrics/hook-quality-false-positive-failure.receipt.json",
      "assets/evidence/check-receipts/20260621-rsp-25-hook-quality-metrics/hook-quality-false-negative-failure.receipt.json",
      "assets/evidence/check-receipts/20260621-rsp-25-hook-quality-metrics/hook-quality-threshold-relaxed-unreviewed.receipt.json",
      "assets/evidence/check-receipts/20260621-rsp-25-hook-quality-metrics/hook-quality-check.receipt.json",
      "assets/evidence/check-receipts/20260621-rsp-25-hook-quality-metrics/check-hook-quality-metrics-check.receipt.json"
    ],
    "max_files": 12,
    "max_bytes_per_file": 80000,
    "max_total_bytes": 240000
  },
  "known_constraints": [
    "只评估 RSP-25 当前机器化度量范围，不声明 Stop 永久零误伤。",
    "如果仍有 concern，必须给出最小修复，不允许用复审次数替代修复。"
  ],
  "questions_for_prism": [
    "上一轮提出的负向探针不可见问题是否已解决？",
    "上一轮提出的样本来源和标注审计不可见问题是否已至少达到关闭 RSP-25 当前机器化范围的最低标准？",
    "是否还存在必须立即修复的 block 或 concern？"
  ]
}


--- AUTHORIZED FILE ACCESS ---

mode: bounded-read

Authorized bundle JSON: /Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260621-rsp-25-hook-quality-metrics/kimi.evidence-refresh.review.brief.files.json

Bundle sha256: 505c26fe526588be77e49a2f207eb51e3625e79e9050f0c1404d99ef308b9741

Rules:

- You may read only this generated bundle JSON if file evidence is needed.

- Do not inspect the original source paths directly.

- Do not run commands.

- If the bundle is insufficient, report missing evidence instead of fetching more files.

