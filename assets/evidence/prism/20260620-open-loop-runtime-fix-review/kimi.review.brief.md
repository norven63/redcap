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
  "evidence_count": 7,
  "known_constraint_count": 4
}

--- REVIEW REQUEST JSON ---

{
  "task": "复核 RedCap 未闭环任务清单、Cap复活手册边界修复、E2E缓存治理运行接入与当前缓存处理。",
  "user_intent": "Norven 要求把遗漏未闭环点编排成整体任务清单，与棱镜讨论达成一致；参考旧 RedCap 的 compass/soul.md 形成路径无关的 Cap 复活手册；治理 E2E 缓存膨胀并接入每轮流程；之后执行、测试、修复并循环到没有新问题。",
  "main_claim": "本轮修复只声明三个阶段性事实：未闭环任务清单已经有退出标准，Cap 复活手册已经通过公共/私有边界检查，E2E 缓存治理已经接入每轮外层运行收尾并清理了当前陈旧缓存；这不声明 RedCap 完整复活，也不关闭仍 open 的 Loom、自我净化、项目级发布和二次 E2E 验收任务。",
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
    "runtime/bin/redcap check 已通过 69/69 步。"
  ],
  "evidence": [
    {
      "kind": "diff",
      "reference": "runtime/core/complete_revival_e2e.py",
      "summary": "E2E缓存保留计划接入每轮外层 run 收尾，并支持陈旧 active 分类。"
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
      "kind": "test",
      "reference": "runtime/bin/redcap complete-revival-e2e self-check --skip-carrier-probe",
      "summary": "E2E运行器自检通过。"
    },
    {
      "kind": "test",
      "reference": "runtime/bin/redcap check",
      "summary": "RedCap主检查 69/69 步通过。"
    }
  ],
  "review_questions": [
    "你是否认可 E2E 缓存治理已经从手动命令推进到每轮运行收尾路径？如不认可，请指出还缺哪条运行证据。",
    "你是否认可 Cap复活手册的公共/私有边界问题已经修复到当前阶段可接受？如不认可，请指出具体泄露或误伤风险。",
    "你是否认可 open-loop 队列已避免无限循环生成器风险？如不认可，请指出需要补的退出条件。",
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


--- KIMI FILE ACCESS ---
mode: prompt-only
No file reading is authorized for this review.
