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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260621-rsp-09-13-14-17-18-22-residual-batch/request-round3.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "Third-round review for residual RSP implementation batch: RSP-09, RSP-13, RSP-14, RSP-17, RSP-18, and RSP-22.",
  "review_mode": "adversarial-implementation-review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 0,
  "known_constraint_count": 0
}

--- REVIEW REQUEST JSON ---

{
  "task": "Third-round review for residual RSP implementation batch: RSP-09, RSP-13, RSP-14, RSP-17, RSP-18, and RSP-22.",
  "user_intent": "Norven requires RedCap residual tasks to be closed by actual behavior changes and verified checks, not by ledgers, reports, or generated evidence volume. This review should decide whether the six listed residual RSP items may be closed narrowly, without implying RedCap full revival or production readiness.",
  "main_claim": "Cap replaced the round-2 evidence-inflation pattern with a single residual-batch integration command. The command runs all six RSP checks, validates six negative probes, runs six RSP contract binding checks, verifies obsolete RSP-18 paths are absent, and emits one integration evidence file plus one executed-check receipt.",
  "changed_reality": [
    "runtime/core/residual_batch.py was added as a reusable integration checker for the six residual RSP items.",
    "runtime/bin/redcap now exposes residual-batch check|self-check.",
    "runtime/core/check_runner.py now includes residual-batch-integration-check and residual-batch-self-check.",
    "assets/evidence/rsp/rsp-09-13-14-17-18-22-batch-integration.json records one batch run with six RSP steps, six detected negative probes, six successful contract checks, and removed-path checks for obsolete RSP-18 names.",
    "assets/evidence/check-receipts/20260621-rsp-09-13-14-17-18-22-residual-batch/rsp-residual-batch-integration-check.receipt.json records the actual command, stdout/stderr paths, exit code, hashes, elapsed time, and executor.",
    "The request now uses file_access.mode=bounded-read so Prism reviewers can inspect authorized files instead of judging path lists."
  ],
  "review_mode": "adversarial-implementation-review",
  "risk_level": "medium",
  "file_access": {
    "mode": "bounded-read",
    "allowed_paths": [
      "runtime/core/residual_batch.py",
      "runtime/core/check_runner.py",
      "runtime/bin/redcap",
      "assets/evidence/rsp/rsp-09-13-14-17-18-22-batch-integration.json",
      "assets/evidence/check-receipts/20260621-rsp-09-13-14-17-18-22-residual-batch/rsp-residual-batch-integration-check.receipt.json",
      "assets/evidence/check-receipts/20260621-rsp-09-13-14-17-18-22-residual-batch/rsp-residual-batch-integration-check.stdout.txt",
      "assets/evidence/check-receipts/20260621-rsp-09-13-14-17-18-22-residual-batch/source-diff-round3.stdout.patch",
      "assets/evidence/check-receipts/20260621-rsp-09-13-14-17-18-22-residual-batch/source-diff-round3.receipt.json",
      "assets/evidence/check-receipts/20260621-rsp-09-13-14-17-18-22-residual-batch/py-compile-round3.receipt.json",
      "assets/evidence/rsp/rsp-18-claim.json",
      "assets/contracts/fixture-external-project-samples.json"
    ],
    "max_files": 20,
    "max_directory_entries": 200,
    "max_bytes_per_file": 120000,
    "max_total_bytes": 600000,
    "purpose": "third-round Prism review of residual RSP batch implementation and single integration evidence"
  },
  "inline_behavioral_proof": {
    "single_integration_command": "runtime/bin/redcap residual-batch check --out assets/evidence/rsp/rsp-09-13-14-17-18-22-batch-integration.json",
    "integration_result": {
      "ok": true,
      "receipt": "assets/evidence/check-receipts/20260621-rsp-09-13-14-17-18-22-residual-batch/rsp-residual-batch-integration-check.receipt.json",
      "receipt_stdout_sha256": "8a45a1cec11a530a37e716987b357839e74f543e7d23885184b5bf816c8f8ce7",
      "integration_evidence": "assets/evidence/rsp/rsp-09-13-14-17-18-22-batch-integration.json"
    },
    "negative_probes_detected": [
      "RSP-09: source workspace pollution must be detected",
      "RSP-13: RedCap source workspace must be rejected as prune root",
      "RSP-14: toy page-access-only report must be rejected",
      "RSP-17: contract coverage alone must not be accepted as long-term maturity",
      "RSP-18: target-only sample without RedCap capability evidence must be rejected",
      "RSP-22: missing E2E contract mapping must be detected"
    ],
    "contract_checks": [
      "RSP-09 contract check ok",
      "RSP-13 contract check ok",
      "RSP-14 contract check ok",
      "RSP-17 contract check ok",
      "RSP-18 contract check ok",
      "RSP-22 contract check ok"
    ],
    "obsolete_rsp18_paths_absent": [
      "assets/contracts/external-project-long-samples.json",
      "assets/evidence/rsp/rsp-18-external-project-long-samples.json",
      "assets/evidence/check-receipts/20260621-rsp-09-13-14-17-18-22-residual-batch/rsp-18-external-project-long-samples-check.receipt.json",
      "assets/evidence/check-receipts/20260621-rsp-09-13-14-17-18-22-residual-batch/rsp-contract-rsp-18.receipt.json"
    ],
    "syntax_check": {
      "ok": true,
      "receipt": "assets/evidence/check-receipts/20260621-rsp-09-13-14-17-18-22-residual-batch/py-compile-round3.receipt.json"
    }
  },
  "review_focus": [
    "Verify whether the single residual-batch integration command is real behavior coverage or only another wrapper with no extra value.",
    "Verify whether the authorized files are now readable and sufficient to inspect implementation reality.",
    "Verify whether RSP-18 is honestly scoped to fixture external project samples and obsolete names are no longer active.",
    "Verify whether the six negative probes are meaningful enough for this narrow residual batch.",
    "If concern remains, identify the minimum concrete code or test change; do not ask for more evidence bundles."
  ],
  "forbidden_conclusions": [
    "Do not conclude RedCap full revival.",
    "Do not conclude RedCap production readiness.",
    "Do not conclude RSP-18 proves real long-term production project behavior.",
    "Do not accept completion if the single integration command does not add meaningful verification beyond listing files."
  ],
  "requested_providers": [
    "kimi",
    "claude-code"
  ]
}
