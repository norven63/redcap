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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260620-open-loop-objective-final-closure/followup-r2-request/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "实施后回审第四轮：确认外部验证可审计性与 OL-01 准入合同修复是否解除上一轮 concern。",
  "review_mode": "implementation_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 7,
  "known_constraint_count": 3
}

--- REVIEW REQUEST JSON ---

{
  "task": "实施后回审第四轮：确认外部验证可审计性与 OL-01 准入合同修复是否解除上一轮 concern。",
  "review_mode": "implementation_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "language_policy": "中文优先；必要专有名词首次出现时给中文解释。",
  "user_intent": "Norven 要求 RedCap 不再用不可审计的结果文件冒充真实完成；本轮只确认上一轮棱镜指出的外部验证不可审计、OL-01 准入不清两项 concern 是否已被真实修复。",
  "main_claim": "上一轮 concern 已按最小修复落地：新增不导入被测运行器模块的独立保留策略验证器；证据包包含验证器源码快照、调用记录、执行输出和前后 ps 快照；E2E 合同新增 external_validation_observer 硬准入，并把该验证器命令纳入 design-check；OL-01 队列要求外部验证源码快照与调用记录作为关闭条件。当前仍不声明 RedCap 完整复活，只声明该基础 concern 已请求复核。",
  "changed_reality": [
    "新增 runtime/audit/e2e_retention_external_validation.py，用 ast 解析真实 import 语句，确认验证器没有导入 complete_revival_e2e 或 soul_loader。",
    "assets/contracts/complete-revival-e2e-acceptance-design.json 新增 external_validation_observer，并把独立验证器命令加入 commands。",
    "runtime/core/complete_revival_e2e.py 的 validate_contract 现在强制检查 external_validation_observer、验证器源码存在、源码快照要求、调用记录要求和禁止导入。",
    "assets/contracts/open-loop-closure-queue.json 的 OL-01 runtime_checks、evidence_required、exit_criteria 纳入外部验证器源码快照与调用记录要求。",
    "重新生成 process-fixture 证据：真实 sleep 进程在清理前后都存活，live active 目录保留，stale active 目录删除，retention-external-validation.json ok=true，source.txt 与 invocation.json 已落证据包。",
    "runtime/bin/redcap complete-revival-e2e design-check 已通过，python3 -m py_compile 对新验证器与 E2E 运行器已通过。"
  ],
  "evidence": [
    {
      "kind": "source",
      "reference": "runtime/audit/e2e_retention_external_validation.py",
      "summary": "独立保留策略验证器源码，不导入被测运行器模块。"
    },
    {
      "kind": "contract",
      "reference": "assets/contracts/complete-revival-e2e-acceptance-design.json",
      "summary": "external_validation_observer 硬准入与独立验证器命令。"
    },
    {
      "kind": "contract",
      "reference": "assets/contracts/open-loop-closure-queue.json",
      "summary": "OL-01 纳入外部验证器源码快照和调用记录作为准入/关闭条件。"
    },
    {
      "kind": "runtime-check",
      "reference": "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/process-fixture/retention-external-validation.json",
      "summary": "独立验证器输出 ok=true。"
    },
    {
      "kind": "runtime-check",
      "reference": "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/process-fixture/retention-external-validation-source.txt",
      "summary": "证据包内验证器源码快照。"
    },
    {
      "kind": "runtime-check",
      "reference": "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/process-fixture/retention-external-validation-invocation.json",
      "summary": "验证器和 prune-runs 调用方式。"
    },
    {
      "kind": "runtime-check",
      "reference": "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/process-fixture/prune-execute.json",
      "summary": "真实 prune-runs 执行回执。"
    }
  ],
  "known_constraints": [
    "不声明 RedCap 完整复活。",
    "本轮只判断上一轮棱镜 concern 是否解除，以及是否可继续后续完整外部 E2E 准备。",
    "如果仍认为外部验证独立性不足，请给出可立即落地的最小修复，而不是泛化为必须完成完整 OL-01。"
  ],
  "review_questions": [
    "Kimi 上一轮提出的：证据包缺少 external-validation 脚本源码与调用方式，是否已由 source.txt 与 invocation.json 解除？",
    "Claude Code 上一轮提出的：OL-01 启动前要把外部验证者与被测实例的边界作为准入条件，是否已由 external_validation_observer 与 OL-01 队列条款解除？",
    "当前是否还存在必须先修复、否则不能进入后续完整外部 E2E 的 P0 基础设施问题？"
  ],
  "file_access": {
    "mode": "bounded-read",
    "allowed_paths": [
      "runtime/audit/e2e_retention_external_validation.py",
      "runtime/core/complete_revival_e2e.py",
      "assets/contracts/complete-revival-e2e-acceptance-design.json",
      "assets/contracts/open-loop-closure-queue.json",
      "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/process-fixture/retention-external-validation.json",
      "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/process-fixture/retention-external-validation-source.txt",
      "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/process-fixture/retention-external-validation-invocation.json",
      "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/process-fixture/prune-execute.json",
      "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/process-fixture/ps-before.txt",
      "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/process-fixture/ps-after.txt"
    ],
    "max_files": 10,
    "max_bytes_per_file": 220000,
    "max_total_bytes": 900000,
    "purpose": "只复核上一轮 concern 的最小修复是否满足。"
  }
}


--- AUTHORIZED FILE ACCESS ---

mode: bounded-read

Authorized bundle JSON: /Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260620-open-loop-objective-final-closure/kimi.r2.review.brief.files.json

Bundle sha256: 089d8ee0b629c43bd49f771f619c0fe77c6fd4f363cde31117dc416fbb0efe05

Rules:

- You may read only this generated bundle JSON if file evidence is needed.

- Do not inspect the original source paths directly.

- Do not run commands.

- If the bundle is insufficient, report missing evidence instead of fetching more files.
