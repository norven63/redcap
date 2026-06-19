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

/private/tmp/redcap-stop-hook-false-positive-followup2-request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "Second follow-up review for Stop hook false-positive fix after addressing prior Claude concern.",
  "review_mode": "implementation_review",
  "risk_level": "medium",
  "requested_providers": [
    "claude-code"
  ],
  "evidence_count": 0,
  "known_constraint_count": 0
}

--- REVIEW REQUEST JSON ---

{
  "task": "Second follow-up review for Stop hook false-positive fix after addressing prior Claude concern.",
  "user_intent": "Stop hook must stop disrupting normal conversation while preserving anti-false-completion guardrails.",
  "main_claim": "The prior concern was addressed: status-report context is evaluated before self-completion patterns, simple answer_only status answers are covered, and English status report terms were added.",
  "changed_reality": [
    "completion_claim_detected now checks status_report_context before self_completion_claim_detected.",
    "SIMPLE_STATUS_ANSWER_PATTERNS allows short answer_only/review_only status replies such as 完成了 or done.",
    "STATUS_REPORT_MESSAGE_PATTERNS includes English status words such as remains, open, pending, in progress, still, not yet.",
    "Self-check now covers answer_only simple status, answer_only mixed status with 任务A已经完成/仍是缺口/运行正常, and review_only English verification complete/all checks passed/remains pending.",
    "runtime/bin/redcap final-claim self-check returned OK.",
    "Historical-style replay returned completion_claim_detected=false for required prompt.",
    "runtime/bin/redcap check returned OK."
  ],
  "review_mode": "implementation_review",
  "risk_level": "medium",
  "requested_providers": [
    "claude-code"
  ],
  "implementation_diff": "diff --git a/runtime/core/final_claim_guard.py b/runtime/core/final_claim_guard.py\nindex 352e960..960ed17 100644\n--- a/runtime/core/final_claim_guard.py\n+++ b/runtime/core/final_claim_guard.py\n@@ -16,7 +16,7 @@ REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]\n DEFAULT_EVENTS = REPO_ROOT / \"assets\" / \"evidence\" / \"host-hooks\" / \"codex\" / \"events.jsonl\"\n DEFAULT_COMPLETION_MARKER = REPO_ROOT / \"assets\" / \"evidence\" / \"lifecycle\" / \"latest-completion.json\"\n TASK_BODY_EVIDENCE_KINDS = {\"code\", \"code-and-review\", \"runtime-change\", \"runtime_change\", \"test\", \"migration\"}\n-COMPLETION_TERMS = [\n+CHINESE_COMPLETION_TERMS = [\n     \"一切正常\",\n     \"已完成\",\n     \"已处理\",\n@@ -40,6 +40,8 @@ COMPLETION_TERMS = [\n     \"功能完备\",\n     \"问题解决\",\n     \"不再有\",\n+]\n+ENGLISH_COMPLETION_TERMS = [\n     \"ready\",\n     \"all set\",\n     \"good to go\",\n@@ -57,6 +59,30 @@ COMPLETION_TERMS = [\n     \"finished\",\n     \"goal achieved\",\n ]\n+SELF_COMPLETION_PATTERNS = [\n+    r\"(?:我|我们|本轮|这轮|这次|该任务|这个任务|任务|修复|改动|实现|检查|验证).{0,24}(?:已经完成|已经处理|已经修复|已经解决|已完成|已处理|已应用|已生效|执行完|做完|完成了|搞定了|弄好了|问题解决|运行正常|正常运行)\",\n+    r\"(?:已完成|已处理|已应用|已生效|执行完|做完|完成了|搞定了|弄好了).{0,24}(?:本轮|这轮|这次|任务|修复|改动|实现|检查|验证)\",\n+    r\"^\\s*(?:[-*]\\s*)?(?:已完成|已处理|已应用|已生效|执行完|做完|完成了|搞定了|弄好了|一切正常)[。.!！]?\\s*$\",\n+    r\"\\b(?:i|we|this task|the task|the fix|the change|the implementation|the check|the verification)\\b.{0,80}\\b(?:ready|all set|good to go|deployed|accomplished|resolved|fixed|complete|completed|done|finished)\\b\",\n+    r\"\\b(?:all|checks?|tests?|verification)\\s+(?:passed|green|clear|ok|successful|complete)\\b\",\n+]\n+STATUS_REPORT_PROMPT_PATTERNS = [\n+    r\"哪些.{0,20}(?:完成|未完成|状态|情况)\",\n+    r\"(?:是否|是不是).{0,24}(?:完成|解决|修复|落实|落地)\",\n+    r\"(?:盘点|回顾|review|审核|检查|评估|状态|情况|清单|列表)\",\n+    r\"(?:还有|哪些|什么).{0,24}(?:缺口|问题|风险|待办|遗留)\",\n+    r\"what(?:'s| is| are).{0,40}(?:done|left|status|remaining)\",\n+]\n+STATUS_REPORT_MESSAGE_PATTERNS = [\n+    r\"(?:仍是|仍有|还没有|尚未|缺口|风险|待办|遗留|当前判断|状态|盘点|可判为|不宜)\",\n+    r\"\\b(?:remains?|remaining|open|pending|in progress|still|not yet)\\b\",\n+    r\"^\\s*\\|.+\\|\\s*$\",\n+    r\"^\\s*(?:[-*]|\\d+\\.)\\s+\",\n+]\n+SIMPLE_STATUS_ANSWER_PATTERNS = [\n+    r\"^\\s*(?:是的[，,]?\\s*)?(?:已完成|完成了|已处理|已修复|修复了|已解决|解决了|未完成|还没有|尚未|不是|没有)[。.!！]?\\s*$\",\n+    r\"^\\s*(?:yes[,.]?\\s*)?(?:done|complete|completed|resolved|fixed|not yet|pending|open|in progress)[.!]?\\s*$\",\n+]\n \n \n def load_json(path: pathlib.Path) -> dict[str, Any]:\n@@ -97,11 +123,73 @@ def parse_time(value: Any) -> dt.datetime | None:\n     return parsed\n \n \n-def completion_claim_detected(message: str) -> bool:\n+def prompt_authorized_scope(prompt: dict[str, Any] | None) -> str | None:\n+    if not isinstance(prompt, dict):\n+        return None\n+    for key in [\"prompt_intent_effective\", \"prompt_intent\"]:\n+        intent = prompt.get(key)\n+        if isinstance(intent, dict):\n+            scope = intent.get(\"authorized_scope\")\n+            if isinstance(scope, str) and scope.strip():\n+                return scope\n+    return None\n+\n+\n+def prompt_text(prompt: dict[str, Any] | None) -> str:\n+    if not isinstance(prompt, dict):\n+        return \"\"\n+    value = prompt.get(\"prompt\")\n+    if isinstance(value, str):\n+        return value\n+    if isinstance(value, dict):\n+        excerpt = value.get(\"normalized_excerpt\")\n+        if isinstance(excerpt, str):\n+            return excerpt\n+    return \"\"\n+\n+\n+def english_term_pattern(term: str) -> re.Pattern[str]:\n+    return re.compile(rf\"(?<![a-z0-9_-]){re.escape(term)}(?![a-z0-9_-])\", re.I)\n+\n+\n+ENGLISH_COMPLETION_PATTERNS = [english_term_pattern(term) for term in ENGLISH_COMPLETION_TERMS]\n+SELF_COMPLETION_REGEXES = [re.compile(pattern, re.I | re.M | re.S) for pattern in SELF_COMPLETION_PATTERNS]\n+STATUS_REPORT_PROMPT_REGEXES = [re.compile(pattern, re.I | re.S) for pattern in STATUS_REPORT_PROMPT_PATTERNS]\n+STATUS_REPORT_MESSAGE_REGEXES = [re.compile(pattern, re.I | re.M | re.S) for pattern in STATUS_REPORT_MESSAGE_PATTERNS]\n+SIMPLE_STATUS_ANSWER_REGEXES = [re.compile(pattern, re.I | re.S) for pattern in SIMPLE_STATUS_ANSWER_PATTERNS]\n+\n+\n+def self_completion_claim_detected(message: str) -> bool:\n+    return any(pattern.search(message) for pattern in SELF_COMPLETION_REGEXES)\n+\n+\n+def completion_terms_present(message: str) -> bool:\n     lowered = message.casefold()\n-    if any(term in lowered for term in COMPLETION_TERMS):\n+    if any(term in lowered for term in CHINESE_COMPLETION_TERMS):\n+        return True\n+    return any(pattern.search(message) for pattern in ENGLISH_COMPLETION_PATTERNS)\n+\n+\n+def status_report_context(prompt: dict[str, Any] | None, message: str) -> bool:\n+    scope = prompt_authorized_scope(prompt)\n+    prompt_value = prompt_text(prompt)\n+    prompt_asks_status = any(pattern.search(prompt_value) for pattern in STATUS_REPORT_PROMPT_REGEXES)\n+    message_looks_status = any(pattern.search(message) for pattern in STATUS_REPORT_MESSAGE_REGEXES)\n+    message_is_simple_status = any(pattern.search(message) for pattern in SIMPLE_STATUS_ANSWER_REGEXES)\n+    return (\n+        scope in {\"answer_only\", \"review_only\"}\n+        or prompt_asks_status\n+    ) and (message_looks_status or message_is_simple_status)\n+\n+\n+def completion_claim_detected(message: str, prompt: dict[str, Any] | None = None) -> bool:\n+    if status_report_context(prompt, message):\n+        return False\n+    if self_completion_claim_detected(message):\n         return True\n-    return bool(re.search(r\"\\b(all|checks?|tests?|verification)\\s+(passed|green|clear|ok|successful|complete)\\b\", lowered))\n+    if not completion_terms_present(message):\n+        return False\n+    return True\n \n \n def latest_prompt(events: list[dict[str, Any]], session_id: str | None, turn_id: str | None) -> dict[str, Any] | None:\n@@ -122,9 +210,9 @@ def check_final_claim(\n     session_id: str | None,\n     turn_id: str | None,\n ) -> dict[str, Any]:\n-    detected = completion_claim_detected(message)\n     events = load_events(events_path)\n     prompt = latest_prompt(events, session_id, turn_id)\n+    detected = completion_claim_detected(message, prompt)\n     required_prompt = isinstance(prompt, dict) and prompt.get(\"gate_decision\") == \"required\"\n     result: dict[str, Any] = {\n         \"ok\": True,\n@@ -271,6 +359,102 @@ def cmd_self_check(_: argparse.Namespace) -> int:\n         )\n         if non_whitelisted[\"ok\"]:\n             failures.append(\"completion marker with non-whitelisted evidence_kind was not blocked\")\n+        answer_events_path = tmp / \"answer-events.jsonl\"\n+        answer_events_path.write_text(json.dumps({\n+            \"event\": \"UserPromptSubmit\",\n+            \"session_id\": \"fixture-session\",\n+            \"turn_id\": \"fixture-answer\",\n+            \"recorded_at\": prompt_time.isoformat(),\n+            \"gate_decision\": \"required\",\n+            \"prompt_intent\": {\n+                \"authorized_scope\": \"answer_only\",\n+                \"prompt_kind\": \"question\",\n+                \"action_evidence\": \"none\",\n+            },\n+            \"prompt\": {\n+                \"normalized_excerpt\": \"哪些项目已经完成，哪些还未完成？请盘点当前状态。\",\n+            },\n+        }, ensure_ascii=False) + \"\\n\", encoding=\"utf-8\")\n+        answer_status_report = check_final_claim(\n+            message=(\n+                \"| 项目 | 当前判断 |\\n\"\n+                \"|---|---|\\n\"\n+                \"| A | 已完成 |\\n\"\n+                \"| B | 仍是缺口 |\\n\"\n+                \"| C | unresolved，不等于 resolved |\\n\"\n+            ),\n+            events_path=answer_events_path,\n+            completion_marker_path=marker_path,\n+            session_id=\"fixture-session\",\n+            turn_id=\"fixture-answer\",\n+        )\n+        if not answer_status_report[\"ok\"]:\n+            failures.append(\"answer-only status report with completion words was blocked\")\n+        review_events_path = tmp / \"review-events.jsonl\"\n+        review_events_path.write_text(json.dumps({\n+            \"event\": \"UserPromptSubmit\",\n+            \"session_id\": \"fixture-session\",\n+            \"turn_id\": \"fixture-review\",\n+            \"recorded_at\": prompt_time.isoformat(),\n+            \"gate_decision\": \"required\",\n+            \"prompt_intent\": {\n+                \"authorized_scope\": \"review_only\",\n+                \"prompt_kind\": \"mixed\",\n+                \"action_evidence\": \"diagnostic\",\n+            },\n+            \"prompt\": {\n+                \"normalized_excerpt\": \"请 review 当前有哪些 done/remaining 状态。\",\n+            },\n+        }, ensure_ascii=False) + \"\\n\", encoding=\"utf-8\")\n+        review_status_report = check_final_claim(\n+            message=\"当前判断：completed 是被盘点的状态词；中文报告仍是缺口。\",\n+            events_path=review_events_path,\n+            completion_marker_path=marker_path,\n+            session_id=\"fixture-session\",\n+            turn_id=\"fixture-review\",\n+        )\n+        if not review_status_report[\"ok\"]:\n+            failures.append(\"review-only status report with English completion words was blocked\")\n+        answer_simple_status = check_final_claim(\n+            message=\"完成了\",\n+            events_path=answer_events_path,\n+            completion_marker_path=marker_path,\n+            session_id=\"fixture-session\",\n+            turn_id=\"fixture-answer\",\n+        )\n+        if not answer_simple_status[\"ok\"]:\n+            failures.append(\"answer-only simple status answer was blocked\")\n+        answer_mixed_status = check_final_claim(\n+            message=\"任务A已经完成，任务B仍是缺口，验证流程运行正常。\",\n+            events_path=answer_events_path,\n+            completion_marker_path=marker_path,\n+            session_id=\"fixture-session\",\n+            turn_id=\"fixture-answer\",\n+        )\n+        if not answer_mixed_status[\"ok\"]:\n+            failures.append(\"answer-only mixed status report was blocked by self-completion pattern\")\n+        review_english_status = check_final_claim(\n+            message=\"verification complete; all checks passed for A. B remains pending.\",\n+            events_path=review_events_path,\n+            completion_marker_path=marker_path,\n+            session_id=\"fixture-session\",\n+            turn_id=\"fixture-review\",\n+        )\n+        if not review_english_status[\"ok\"]:\n+            failures.append(\"review-only English status report was blocked by self-completion pattern\")\n+        if completion_claim_detected(\"The previous concern is unresolved.\"):\n+            failures.append(\"unresolved should not match resolved\")\n+        if completion_claim_detected(\"This is a completion marker discussion, not a closeout claim.\"):\n+            failures.append(\"completion should not match complete\")\n+        implementation_self_claim = check_final_claim(\n+            message=\"我已经完成 Stop hook 修复。\",\n+            events_path=events_path,\n+            completion_marker_path=tmp / \"missing-marker.json\",\n+            session_id=\"fixture-session\",\n+            turn_id=\"fixture-turn\",\n+        )\n+        if implementation_self_claim[\"ok\"]:\n+            failures.append(\"implementation self-completion claim without marker was not blocked\")\n     print(json.dumps({\"ok\": not failures, \"failures\": failures}, ensure_ascii=False, indent=2))\n     if failures:\n         return 1\n",
  "verification_evidence": [
    "runtime/bin/redcap final-claim self-check -> REDCAP_FINAL_CLAIM_GUARD_SELF_CHECK_OK",
    "runtime/bin/redcap final-claim check replay -> REDCAP_FINAL_CLAIM_GUARD_OK and completion_claim_detected=false",
    "runtime/bin/redcap check -> REDCAP_LAYOUT_OK with no failures shown"
  ],
  "questions_for_prism": [
    "Were the prior required-now concerns addressed?",
    "Does this remain bounded to final_claim_guard without weakening action-evidence Stop hook behavior?",
    "Is this safe to commit?"
  ]
}
