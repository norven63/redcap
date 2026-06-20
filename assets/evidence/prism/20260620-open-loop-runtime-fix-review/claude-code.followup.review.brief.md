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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260620-open-loop-runtime-fix-review/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "复核 RedCap 未闭环任务清单、Cap复活手册边界修复、E2E缓存治理运行接入与当前缓存处理。",
  "review_mode": "implementation_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 12,
  "known_constraint_count": 4
}

--- REVIEW REQUEST JSON ---

{
  "task": "复核 RedCap 未闭环任务清单、Cap复活手册边界修复、E2E缓存治理运行接入与当前缓存处理。",
  "user_intent": "Norven 要求把遗漏未闭环点编排成整体任务清单，与棱镜讨论达成一致；参考旧 RedCap 的 compass/soul.md 形成路径无关的 Cap 复活手册；治理 E2E 缓存膨胀并接入每轮流程；之后执行、测试、修复并循环到没有新问题。",
  "main_claim": "已针对第一轮棱镜 concern 做实际补强：E2E 每轮外层 run 收尾现在默认清理超过阈值的陈旧 active 目录并记录缺状态文件警告；已用真实 complete-revival-e2e run 入口产生 redcap-e2e-run-retention-after-run.json 并删除陈旧 active 夹具；open-loop 队列已有机器检查器，当前结构有效但 closeout_allowed=false；Cap 复活手册已有可审计边界清单，证明公开手册不含私密正文标记和用户绝对路径。这仍不声明 RedCap 完整复活，也不关闭仍 open 的 Loom、自我净化、项目级发布和二次 E2E 验收任务。",
  "previous_prism_concerns": [
    "不要把任务清单、手册和评审当作完成证据。",
    "E2E 缓存治理不能只停留在手动 prune 命令或 dry-run，必须接入 complete-revival-e2e run 收尾。",
    "Cap 复活手册不能只描述公共/私有边界，必须通过边界检查，避免把私密身份内容写入公共资产。",
    "任务队列必须有退出条件，不能变成无限循环生成器。"
  ],
  "changed_reality": [
    "runtime/core/complete_revival_e2e.py 新增 stale-active 识别、显式 stale-active 清理开关、每轮外层 run 后 attach_e2e_run_retention_result，并写 redcap-e2e-run-retention-after-run.json。",
    "complete-revival-e2e self-check 已覆盖 stale-active 默认保留、显式清理、旧成功运行保留策略和自动收尾回执源码检查。",
    "assets/docs/cap-revival-manual.md 已移除会触发公共私有边界扫描的私密正文标记；runtime/bin/redcap revival-followthrough check 已通过。",
    "assets/contracts/open-loop-closure-queue.json 已加入 exit_criteria，并把 OL-06、OL-08 标成具体运行验证范围，其他条目仍保持 open。",
    "已执行 prune-runs --delete-stale-active --stale-active-hours 24 --execute，删除 15 个超过 24 小时的陈旧 active 目录；清理后 dry-run 删除候选为 0。",
    "runtime/core/complete_revival_e2e.py 已改为每轮收尾默认清理超过阈值的 stale-active，并把缺状态文件目录写入 state_file_warnings。",
    "已执行一次真实 complete-revival-e2e run 入口验证：通过测试注入在 layered preflight 快速阻断，但 cmd_run 收尾仍自动写 redcap-e2e-run-retention-after-run.json，并删除陈旧 active 夹具；manual_prune_used=false。",
    "runtime/core/revival_followthrough.py 新增 open-loop-check，当前 open-loop 队列 ok=true 但 closeout_allowed=false，明确阻止未闭环 P0/P1 被收口。",
    "Cap 复活手册已移除绝对路径示例；cap-revival-manual-boundary-inventory.json 显示 private_body_markers_found=[]、absolute_user_paths_found=[]。",
    "runtime/bin/redcap check 已通过 69/69 步。"
  ],
  "evidence": [
    {
      "kind": "diff",
      "reference": "runtime/core/complete_revival_e2e.py",
      "summary": "E2E缓存保留计划接入每轮外层 run 收尾，默认清理陈旧 active，并记录缺状态文件警告。"
    },
    {
      "kind": "diff",
      "reference": "runtime/core/revival_followthrough.py",
      "summary": "新增 open-loop-check，对未闭环队列做机器可判定收口边界检查。"
    },
    {
      "kind": "document",
      "reference": "assets/docs/cap-revival-manual.md",
      "summary": "路径无关 Cap 复活手册，公共/私有边界扫描已通过。"
    },
    {
      "kind": "document",
      "reference": "assets/contracts/open-loop-closure-queue.json",
      "summary": "整体未闭环任务清单，带退出标准和部分运行验证证据。"
    },
    {
      "kind": "log",
      "reference": "assets/evidence/check-receipts/20260620-open-loop-closure-plan/e2e-prune-stale-active-execute.receipt.json",
      "summary": "当前缓存实际清理回执。"
    },
    {
      "kind": "log",
      "reference": "assets/evidence/check-receipts/20260620-open-loop-closure-plan/e2e-prune-after-cleanup.receipt.json",
      "summary": "清理后删除候选为 0。"
    },
    {
      "kind": "log",
      "reference": "assets/evidence/check-receipts/20260620-open-loop-closure-plan/e2e-retention-real-run-proof.receipt.json",
      "summary": "真实 complete-revival-e2e run 入口自动收尾证明：manual_prune_used=false，删除陈旧 active 夹具。"
    },
    {
      "kind": "log",
      "reference": "assets/evidence/check-receipts/20260620-open-loop-closure-plan/cap-revival-manual-boundary-inventory.json",
      "summary": "Cap 复活手册边界清单：未命中私密正文标记，未命中用户绝对路径。"
    },
    {
      "kind": "test",
      "reference": "runtime/bin/redcap complete-revival-e2e self-check --skip-carrier-probe",
      "summary": "E2E运行器自检通过。"
    },
    {
      "kind": "test",
      "reference": "runtime/bin/redcap revival-followthrough open-loop-check --queue assets/contracts/open-loop-closure-queue.json",
      "summary": "open-loop 队列结构通过，但 closeout_allowed=false，证明未闭环项不会被误收口。"
    },
    {
      "kind": "test",
      "reference": "runtime/bin/redcap revival-followthrough self-check",
      "summary": "队列机器检查器正反样例通过。"
    },
    {
      "kind": "test",
      "reference": "runtime/bin/redcap check",
      "summary": "RedCap主检查 69/69 步通过。"
    }
  ],
  "review_questions": [
    "第一轮指出的 E2E 自动收尾证据缺口是否已经由 e2e-retention-real-run-proof.receipt.json 解决？如不认可，请指出仍需哪条运行证据。",
    "第一轮指出的 Cap 手册边界可审计性是否已经由 cap-revival-manual-boundary-inventory.json 解决？如不认可，请指出具体泄露或误伤风险。",
    "第一轮指出的 open-loop 队列退出条件是否已经由 open-loop-check 的 closeout_allowed=false/true 机制解决到当前阶段可接受？如不认可，请指出需要补的机器条件。",
    "请明确给出 verdict：pass / concern / fail。若 concern 或 fail，必须给出最小可执行修复项。"
  ],
  "review_mode": "implementation_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "known_constraints": [
    "不得声明 RedCap 完整复活终局完成。",
    "不得把手册、队列、评审、回执本身当成完成证据。",
    "不得读取、复制或公开 ~/.cap/identity.md 的私密内容。",
    "不得绕过或削弱严格门禁；只能正面修复误伤或能力缺口。"
  ]
}
