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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260620-open-loop-full-objective-continuation/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "评审 RedCap 原始长目标继续执行方案：开放队列全量闭环、外部 E2E 证据、Cap 复活边界、自我净化和缓存治理循环。",
  "review_mode": "strategy_and_execution_plan_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 7,
  "known_constraint_count": 5
}

--- REVIEW REQUEST JSON ---

{
  "task": "评审 RedCap 原始长目标继续执行方案：开放队列全量闭环、外部 E2E 证据、Cap 复活边界、自我净化和缓存治理循环。",
  "review_mode": "strategy_and_execution_plan_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "language_policy": "中文优先；必要专有名词首次出现时给中文解释。",
  "main_claim": "当前 RedCap 完整复活仍未完成；开放队列有 9 个 P0/P1 阻断项。计划不再新增外围治理，而是以开放队列为主线，先评审整体方案，再执行能覆盖多项阻断的外部完整 E2E，并把新问题入队循环，直到开放队列允许收口。",
  "changed_reality": [
    "上一轮已修复完整复活验收误判：complete-revival-check 会因开放队列未闭环而失败。",
    "上一轮已补充 Cap 复活手册、私有人格边界、E2E 缓存治理外部观察器、自我净化公共知识沉淀和总回归证据。",
    "当前仍有 OL-01 到 OL-08、OL-10 共 9 个 P0/P1 项未 verified；其中多数要求下一轮外部完整 E2E 证据。",
    "本轮生命周期包已通过，门禁显示 Prism 可选，但用户目标明确要求棱镜评审，因此仍必须执行棱镜评审。"
  ],
  "proposed_plan": [
    "先把开放队列作为唯一权威待办边界，不改名、不遗忘、不用阶段状态冒充 verified。",
    "优先执行外部完整 E2E，因为它同时覆盖 OL-01、OL-02、OL-03、OL-04、OL-05、OL-06、OL-07、OL-08、OL-10 的剩余证据需求。",
    "外部 E2E 前先确认项目级安装包、外部 work-root、Loom 角色会话清单、自我净化前后置证据和 E2E 缓存保留策略。",
    "E2E 失败时不由 Cap 直接修目标项目；由 Loom 失败回流路由到目标角色，角色修复后再向下游重放。",
    "每次测试发现新问题必须写入开放队列并重新排序；若同根因连续三轮失败，停止盲目重跑，进入架构评审。",
    "只有所有 P0/P1 verified、failure_backlog 无开放项、complete-revival-check 通过，才允许完整复活收口。"
  ],
  "evidence": [
    {
      "kind": "queue",
      "reference": "assets/contracts/open-loop-closure-queue.json",
      "summary": "当前开放队列和退出标准。"
    },
    {
      "kind": "lifecycle",
      "reference": "assets/evidence/lifecycle/20260620-open-loop-full-objective-continuation/packet.json",
      "summary": "本轮继续执行生命周期包。"
    },
    {
      "kind": "runtime-check",
      "reference": "runtime/core/complete_revival_check.py",
      "summary": "完整复活验收硬阻断实现。"
    },
    {
      "kind": "runtime",
      "reference": "runtime/core/complete_revival_e2e.py",
      "summary": "外部 E2E 运行器和缓存治理实现。"
    },
    {
      "kind": "runtime",
      "reference": "runtime/core/loom_runtime.py",
      "summary": "Loom 角色会话与失败回流运行机。"
    },
    {
      "kind": "runtime",
      "reference": "runtime/core/self_purification.py",
      "summary": "自我净化运行闭环。"
    },
    {
      "kind": "docs",
      "reference": "assets/docs/cap-revival-manual.md",
      "summary": "Cap 复活手册公共部分。"
    }
  ],
  "known_constraints": [
    "不能声明 RedCap 完整复活完成。",
    "不能把 runtime-verified-pending-full-e2e 当作 verified。",
    "不能为了通过测试降低、绕过或删除开放项标准。",
    "不能让 Cap 替代 Loom 角色修目标项目。",
    "不能把 E2E 缓存治理只做成手动清理；必须纳入每轮流程。"
  ],
  "review_questions": [
    "这个推进顺序是否正确：先棱镜评审，再执行外部完整 E2E 以覆盖多数开放项？",
    "在外部 E2E 前，是否还有必须先修的基础设施阻断项？",
    "开放队列中哪些项可以通过一次外部 E2E 共同验证，哪些必须单独补测？",
    "当前方案是否仍存在把阶段成果冒充终局完成、或让 Cap 越权替 Loom 执行的风险？",
    "如果 E2E 继续失败，三轮同根因后进入架构评审的阈值是否合适？"
  ],
  "file_access": {
    "mode": "bounded-read",
    "allowed_paths": [
      "assets/contracts/open-loop-closure-queue.json",
      "assets/evidence/lifecycle/20260620-open-loop-full-objective-continuation/packet.json",
      "runtime/core/complete_revival_check.py",
      "runtime/core/complete_revival_e2e.py",
      "runtime/core/loom_runtime.py",
      "runtime/core/self_purification.py",
      "runtime/core/project_install.py",
      "assets/docs/cap-revival-manual.md",
      "assets/contracts/complete-revival-e2e-acceptance-design.json",
      "assets/contracts/loom-workflow.json"
    ],
    "max_files": 10,
    "max_bytes_per_file": 260000,
    "max_total_bytes": 1400000,
    "purpose": "只评审继续执行方案、开放队列闭环顺序和进入外部 E2E 前是否仍有基础阻断。"
  },
  "user_intent": "Norven 要求保留原始长目标，执行全部遗漏未闭环任务，发现新问题入队并循环，直到没有新问题、新需求；本轮先请棱镜评审整体方案和执行顺序。"
}


--- AUTHORIZED FILE ACCESS ---

mode: bounded-read

Authorized bundle JSON: /Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260620-open-loop-full-objective-continuation/kimi.review.brief.files.json

Bundle sha256: a7dde56328f4d6c5b2cbae6dee327271b4928614411e1729594292ef17408984

Rules:

- You may read only this generated bundle JSON if file evidence is needed.

- Do not inspect the original source paths directly.

- Do not run commands.

- If the bundle is insufficient, report missing evidence instead of fetching more files.

