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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260620-open-loop-objective-final-closure/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "实施后回审第三轮：补充外部验证后复核 RedCap 基础修复是否可进入下一阶段外部 E2E。",
  "review_mode": "implementation_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 6,
  "known_constraint_count": 3
}

--- REVIEW REQUEST JSON ---

{
  "task": "实施后回审第三轮：补充外部验证后复核 RedCap 基础修复是否可进入下一阶段外部 E2E。",
  "review_mode": "implementation_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "language_policy": "中文优先；必要专有名词首次出现时给中文解释。",
  "main_claim": "针对上一轮棱镜指出的自证风险，本轮已补充独立于被测模块的外部验证：真实 sleep 进程在 prune-runs 执行前后仍存活，live active 目录保留，stale marker 目录被删除；独立脚本直接读取 CAP_HOME 和默认 ~/.cap 身份文件并确认非空可读。基础修复可进入下一阶段 OL-01 外部 E2E，但这仍不代表 RedCap 完整复活完成。",
  "changed_reality": [
    "external-validation/process-fixture 使用真实 sleep 进程和 ps 快照，不依赖 complete_revival_e2e 的自检夹具判断活进程是否存在。",
    "process-fixture/prune-execute.json 由 RedCap pruner 执行，external-validation-summary.json 由外部脚本检查：sleep_seen_after=true、live_dir_exists_after=true、stale_dir_exists_after=false。",
    "external-validation/cap-home-direct/direct-identity-read.json 由独立脚本直接读取 CAP_HOME 与 fallback ~/.cap fixture，不调用 soul_loader。",
    "soul_loader 自检仍覆盖异常路径；complete_revival_e2e 自检仍覆盖活进程保护；外部验证用于补足自证风险。",
    "本轮不关闭 OL-01 完整外部 E2E，不声明 RedCap 完整复活。"
  ],
  "evidence": [
    {
      "kind": "external-validation",
      "reference": "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/process-fixture/external-validation-summary.json",
      "summary": "真实进程保护和 stale active 删除的独立验证摘要。"
    },
    {
      "kind": "external-validation",
      "reference": "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/process-fixture/ps-before.txt",
      "summary": "清理前真实进程快照。"
    },
    {
      "kind": "external-validation",
      "reference": "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/process-fixture/ps-after.txt",
      "summary": "清理后真实进程快照。"
    },
    {
      "kind": "external-validation",
      "reference": "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/cap-home-direct/direct-identity-read.json",
      "summary": "独立身份文件读取验证。"
    },
    {
      "kind": "runtime-check",
      "reference": "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/final-checks/complete-revival-e2e-self-check/receipt.json",
      "summary": "E2E 自检回执。"
    },
    {
      "kind": "runtime-check",
      "reference": "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/final-checks/soul-load-self-check/receipt.json",
      "summary": "Cap 加载器自检回执。"
    }
  ],
  "known_constraints": [
    "不允许声明 RedCap 完整复活完成。",
    "外部验证只证明本轮基础修复可进入下一阶段，不替代 OL-01 完整外部 E2E。",
    "如果仍有 P0/P1 基础设施阻塞项，请明确最小修复项；如果只剩 OL-01，请明确为下一阶段验收。"
  ],
  "review_questions": [
    "外部验证是否足以解决上一轮提出的自证风险？",
    "当前是否还存在必须先修复、否则不应进入 OL-01 外部 E2E 的基础设施问题？",
    "本轮是否可以收窄为：基础修复通过，完整复活仍待 OL-01 外部 E2E 验收？"
  ],
  "file_access": {
    "mode": "bounded-read",
    "allowed_paths": [
      "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/process-fixture/external-validation-summary.json",
      "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/process-fixture/ps-before.txt",
      "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/process-fixture/ps-after.txt",
      "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/process-fixture/prune-execute.json",
      "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/cap-home-direct/direct-identity-read.json",
      "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/final-checks/complete-revival-e2e-self-check/receipt.json",
      "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/final-checks/soul-load-self-check/receipt.json",
      "runtime/core/soul_loader.py",
      "runtime/core/complete_revival_e2e.py"
    ],
    "max_files": 12,
    "max_bytes_per_file": 220000,
    "max_total_bytes": 900000,
    "purpose": "只复核外部验证是否补足上一轮自证风险。"
  },
  "user_intent": "Norven 要求真实落地未闭环项，并要求所有阶段成果都不能冒充 RedCap 完整复活；本轮只复核补充外部验证后，基础修复是否可进入下一阶段外部 E2E。"
}
