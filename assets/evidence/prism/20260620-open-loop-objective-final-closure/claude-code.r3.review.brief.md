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

/Users/norven/workspace/AI Era/redcap/assets/evidence/prism/20260620-open-loop-objective-final-closure/followup-r3-request/request.json

--- REVIEW REQUEST SUMMARY ---

{
  "task": "实施后回审第五轮：基于内联源码片段和回执确认 external_validation_observer concern 是否解除。",
  "review_mode": "implementation_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "evidence_count": 5,
  "known_constraint_count": 3
}

--- REVIEW REQUEST JSON ---

{
  "task": "实施后回审第五轮：基于内联源码片段和回执确认 external_validation_observer concern 是否解除。",
  "review_mode": "implementation_review",
  "risk_level": "medium",
  "requested_providers": [
    "kimi",
    "claude-code"
  ],
  "language_policy": "中文优先；必要专有名词首次出现时给中文解释。",
  "user_intent": "Norven 要求不接受自证式完成。本轮只确认 external_validation_observer 的运行时强制检查、检查回执、运行时隔离和 OL-01 准入是否足以关闭上一轮 concern；不声明 RedCap 完整复活。",
  "main_claim": "上一轮 Kimi 要求的源码片段、design-check 回执、py_compile 回执已补齐；上一轮 Claude Code 要求的运行时隔离字段已进入验证器输出和合同硬准入。独立实体交叉审计不被冒充为已完成 OL-01，而是作为 OL-01 启动前硬准入写入队列和合同。本轮请求判断这些 concern 是否已在当前阶段关闭。",
  "inline_evidence": {
    "validate_contract_external_observer_source": "2052:         \"runtime/bin/redcap complete-revival-e2e run --direction <text> --work-root <external-dir>\",\n2053:         \"runtime/bin/redcap complete-revival-e2e harness-timeout-regression-test --work-root <external-dir>\",\n2054:         \"runtime/bin/redcap complete-revival-e2e runner-negative-probe-regression-test --work-root <external-dir>\",\n2055:         \"runtime/bin/redcap complete-revival-e2e self-check\",\n2056:         E2E_RETENTION_EXTERNAL_VALIDATOR_COMMAND,\n2057:     ]:\n2058:         if required not in commands:\n2059:             failures.append(f\"E2E 合同缺少命令定义：{required}\")\n2060:     external_observer = contract.get(\"external_validation_observer\")\n2061:     if not isinstance(external_observer, dict):\n2062:         failures.append(\"E2E 合同缺少 external_validation_observer\")\n2063:     else:\n2064:         if external_observer.get(\"status\") != \"hard_evidence_gate\":\n2065:             failures.append(\"external_validation_observer.status 必须为 hard_evidence_gate\")\n2066:         if external_observer.get(\"script\") != \"runtime/audit/e2e_retention_external_validation.py\":\n2067:             failures.append(\"external_validation_observer.script 必须指向独立保留策略验证器\")\n2068:         if external_observer.get(\"source_snapshot_required\") is not True:\n2069:             failures.append(\"external_validation_observer.source_snapshot_required 必须为 true\")\n2070:         if external_observer.get(\"invocation_record_required\") is not True:\n2071:             failures.append(\"external_validation_observer.invocation_record_required 必须为 true\")\n2072:         if external_observer.get(\"runtime_isolation_required\") is not True:\n2073:             failures.append(\"external_validation_observer.runtime_isolation_required 必须为 true\")\n2074:         evidence_required = external_observer.get(\"evidence_required\")\n2075:         for required_evidence in [\n2076:             \"retention-external-validation.json\",\n2077:             \"retention-external-validation-source.txt\",\n2078:             \"retention-external-validation-invocation.json\",\n2079:             \"retention-external-validation.json#validator.runtime_isolation\",\n2080:         ]:\n2081:             if not isinstance(evidence_required, list) or required_evidence not in evidence_required:\n2082:                 failures.append(f\"external_validation_observer.evidence_required 缺少：{required_evidence}\")\n2083:         if not E2E_RETENTION_EXTERNAL_VALIDATOR.exists():\n2084:             failures.append(\"独立保留策略验证器源码不存在\")\n2085:         else:\n2086:             validator_source = E2E_RETENTION_EXTERNAL_VALIDATOR.read_text(encoding=\"utf-8\")\n2087:             forbidden_imports = external_observer.get(\"must_not_import\")\n2088:             if not isinstance(forbidden_imports, list) or not forbidden_imports:\n2089:                 failures.append(\"external_validation_observer.must_not_import 必须声明禁止导入列表\")\n2090:             else:\n2091:                 hits: list[str] = []\n2092:                 validator_tree = ast.parse(validator_source)\n2093:                 forbidden_modules = {str(item) for item in forbidden_imports if str(item)}\n2094:                 for node in ast.walk(validator_tree):\n2095:                     if isinstance(node, ast.Import):\n2096:                         for alias in node.names:\n2097:                             if alias.name in forbidden_modules:\n2098:                                 hits.append(alias.name)\n2099:                     elif isinstance(node, ast.ImportFrom):\n2100:                         module = node.module or \"\"\n2101:                         if module in forbidden_modules:\n2102:                             hits.append(module)\n2103:                 if hits:\n2104:                     failures.append(f\"独立保留策略验证器含有禁止导入：{sorted(set(hits))}\")\n",
    "design_check_receipt": {
      "ok": true,
      "exit_code": 0,
      "stdout_tail": "{\n  \"schema_id\": \"redcap-ai-e2e-design-check\",\n  \"ok\": true,\n  \"contract\": \"/Users/norven/workspace/AI Era/redcap/assets/contracts/complete-revival-e2e-acceptance-design.json\",\n  \"failures\": []\n}\nREDCAP_AI_E2E_DESIGN_OK\n",
      "stderr_tail": ""
    },
    "py_compile_receipt": {
      "ok": true,
      "exit_code": 0,
      "stdout_tail": "",
      "stderr_tail": ""
    },
    "external_validation_summary": {
      "ok": true,
      "failures": [],
      "validator": {
        "path": "runtime/audit/e2e_retention_external_validation.py",
        "absolute_path": "/Users/norven/workspace/AI Era/redcap/runtime/audit/e2e_retention_external_validation.py",
        "sha256": "a1ce0c020f8b61f5a978d917789330e2a4c42af5fee6bd0463d8d4693afe974a",
        "runtime_isolation": {
          "pid": 39621,
          "ppid": 39588,
          "executable": "/Applications/Xcode.app/Contents/Developer/usr/bin/python3",
          "argv": [
            "runtime/audit/e2e_retention_external_validation.py",
            "--root",
            "/tmp/redcap-retention-external.L1q5kA/redcap-e2e-runs-retention-external",
            "--prune-result",
            "/tmp/redcap-retention-external.L1q5kA/evidence/prune-execute.json",
            "--live-dir",
            "/tmp/redcap-retention-external.L1q5kA/redcap-e2e-runs-retention-external/redcap-e2e-runs-live-active",
            "--stale-dir",
            "/tmp/redcap-retention-external.L1q5kA/redcap-e2e-runs-retention-external/redcap-e2e-runs-stale-active",
            "--sleep-pid",
            "39591",
            "--out",
            "/tmp/redcap-retention-external.L1q5kA/evidence/retention-external-validation.json"
          ],
          "cwd": "/Users/norven/workspace/AI Era/redcap",
          "python_version": "3.9.6",
          "process_snapshot": {
            "ok": true,
            "exit_code": 0,
            "stdout": "39621 39588 39588 S    /Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python runtime/audit/e2e_retention_external_validation.py --root /tmp/redcap-retention-external.L1q5kA/redcap-e2e-runs-retention-external --prune-result /tmp/redcap-retention-external.L1q5kA/evidence/prune-execute.json --live-dir /tmp/redcap-retention-external.L1q5kA/redcap-e2e-runs-retention-external/redcap-e2e-runs-live-active --stale-dir /tmp/redcap-retention-external.L1q5kA/redcap-e2e-runs-retention-external/redcap-e2e-runs-stale-active --sleep-pid 39591 --out /tmp/redcap-retention-external.L1q5kA/evidence/retention-external-validation.json",
            "stderr": ""
          },
          "parent_snapshot": {
            "ok": true,
            "exit_code": 0,
            "stdout": "39588 79300 39588 Ss   /bin/zsh -c set -euo pipefail\\012TMP_ROOT=\"$(mktemp -d /tmp/redcap-retention-external.XXXXXX)\"\\012ROOT=\"$TMP_ROOT/redcap-e2e-runs-retention-external\"\\012EVID=\"$TMP_ROOT/evidence\"\\012mkdir -p \"$ROOT\" \"$EVID\"\\012sleep 300 &\\012SLEEP_PID=$!\\012cleanup() { kill \"$SLEEP_PID\" >/dev/null 2>&1 || true; rm -rf \"$TMP_ROOT\"; }\\012trap cleanup EXIT\\012export ROOT EVID SLEEP_PID\\012python3 - <<'PY'\\012import json, os, pathlib, subprocess, time\\012root = pathlib.Path(os.environ['ROOT'])\\012evid = pathlib.Path(os.environ['EVID'])\\012pid = int(os.environ['SLEEP_PID'])\\012live = root / 'redcap-e2e-runs-live-active'\\012stale = root / 'redcap-e2e-runs-stale-active'\\012for path in [live, stale]:\\012    path.mkdir(parents=True, exist_ok=True)\\012    (path / 'redcap-e2e-run-summary.json').write_text(json.dumps({'schema_id': 'redcap-e2e-run-summary', 'ok': False, 'failures': ['external retention fixture']}, ensure_ascii=False, indent=2) + '\\n', encoding='utf-8')\\012(live / 'redcap-long-task-active-run.json').write_text(json.dumps({'schema_id': 'redcap-e2e-long-task-active-run', 'lifecycle_state': 'running', 'worker_pid': pid, 'worker_command_substrings': []}, ensure_ascii=False, indent=2) + '\\n', encoding='utf-8')\\012(stale / 'redcap-long-task-active-run.json').write_text(json.dumps({'schema_id': 'redcap-e2e-long-task-active-run', 'lifecycle_state': 'running'}, ensure_ascii=False, indent=2) + '\\n', encoding='utf-8')\\012old = time.time() - 120\\012for path in [live, stale]:\\012    for item in [path, path / 'redcap-e2e-run-summary.json', path / 'redcap-long-task-active-run.json']:\\012        os.utime(item, (old, old))\\012ps_before = subprocess.run(['ps', '-p', str(pid), '-o', 'pid=,ppid=,pgid=,stat=,command='], check=False, capture_output=True, text=True, timeout=10)\\012(evid / 'ps-before.txt').write_text(ps_before.stdout + ps_before.stderr, encoding='utf-8')\\012(evid / 'fixture-paths.json').write_text(json.dumps({'root': str(root), 'live_dir': str(live), 'stale_dir': str(stale), 'sleep_pid': pid}, ensure_ascii=False, indent=2) + '\\n', encoding='utf-8')\\012PY\\012PRUNE_CMD=(runtime/bin/redcap complete-revival-e2e prune-runs --root \"$ROOT\" --keep-latest-success 5 --keep-latest-failed 20 --delete-stale-active --stale-active-hours 0.0001 --delete-old-failed --old-failed-hours 72 --out \"$EVID/prune-execute.json\" --execute)\\012set +e\\012\"${PRUNE_CMD[@]}\" > \"$EVID/prune-stdout.txt\" 2> \"$EVID/prune-stderr.txt\"\\012PRUNE_EXIT=$?\\012set -e\\012printf '%s\\n' \"$PRUNE_EXIT\" > \"$EVID/prune-exit-code.txt\"\\012ps -p \"$SLEEP_PID\" -o pid=,ppid=,pgid=,stat=,command= > \"$EVID/ps-after.txt\" 2>&1 || true\\012SCRIPT=\"runtime/audit/e2e_retention_external_validation.py\"\\012VALIDATION_CMD=(python3 \"$SCRIPT\" --root \"$ROOT\" --prune-result \"$EVID/prune-execute.json\" --live-dir \"$ROOT/redcap-e2e-runs-live-active\" --stale-dir \"$ROOT/redcap-e2e-runs-stale-active\" --sleep-pid \"$SLEEP_PID\" --out \"$EVID/retention-external-validation.json\")\\012set +e\\012\"${VALIDATION_CMD[@]}\" > \"$EVID/retention-external-validation-stdout.txt\" 2> \"$EVID/retention-external-validation-stderr.txt\"\\012VALIDATION_EXIT=$?\\012set -e\\012printf '%s\\n' \"$VALIDATION_EXIT\" > \"$EVID/retention-external-validation-exit-code.txt\"\\012python3 - <<'PY'\\012import hashlib, json, os, pathlib, shlex\\012root = pathlib.Path(os.environ['ROOT'])\\012evid = pathlib.Path(os.environ['EVID'])\\012script = pathlib.Path('runtime/audit/e2e_retention_external_validation.py')\\012def sha(path):\\012    h=hashlib.sha256(); h.update(path.read_bytes()); return h.hexdigest()\\012source_text = script.read_text(encoding='utf-8')\\012(evid / 'retention-external-validation-source.txt').write_text(source_text, encoding='utf-8')\\012(evid / 'external-validation-summary.json').write_text((evid / 'retention-external-validation.json').read_text(encoding='utf-8'), encoding='utf-8')\\012prune_cmd = ['runtime/bin/redcap','complete-revival-e2e','prune-runs','--root',str(root),'--keep-latest-success','5','--keep-latest-failed','20','--delete-stale-active','--stale-active-hours','0.0001','--delete-old-failed','--old-failed-hours','72','--out',str(evid/'prune-execute.json'),'--execute']\\012validation_cmd = ['python3',str(script),'--root',str(root),'--prune-result',str(evid/'prune-execute.json'),'--live-dir',str(root/'redcap-e2e-runs-live-active'),'--stale-dir',str(root/'redcap-e2e-runs-stale-active'),'--sleep-pid',os.environ['SLEEP_PID'],'--out',str(evid/'retention-external-validation.json')]\\012(evid / 'retention-external-validation-invocation.json').write_text(json.dumps({'schema_id': 'redcap-e2e-retention-external-validation-invocation', 'cwd': str(pathlib.Path.cwd()), 'script': str(script), 'script_sha256': sha(script), 'source_snapshot': 'retention-external-validation-source.txt', 'prune_command': prune_cmd, 'validation_command': validation_cmd, 'prune_command_shell': ' '.join(shlex.quote(item) for item in prune_cmd), 'validation_command_shell': ' '.join(shlex.quote(item) for item in validation_cmd)}, ensure_ascii=False, indent=2) + '\\n', encoding='utf-8')\\012PY\\012runtime/bin/redcap evidence-restore restore --source \"$EVID\" --dest assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/process-fixture --replace\\012if [ \"$PRUNE_EXIT\" -ne 0 ] || [ \"$VALIDATION_EXIT\" -ne 0 ]; then\\012  echo \"prune_exit=$PRUNE_EXIT validation_exit=$VALIDATION_EXIT\" >&2\\012  exit 1\\012fi",
            "stderr": ""
          },
          "invocation_kind": "standalone-python-process"
        },
        "forbidden_runtime_import_modules": [
          "runtime.core.complete_revival_e2e",
          "complete_revival_e2e",
          "runtime.core.soul_loader",
          "soul_loader"
        ],
        "forbidden_import_hits": []
      },
      "observations": {
        "sleep_alive_after": true,
        "ps_after": {
          "ok": true,
          "exit_code": 0,
          "stdout": "39591 39588 39588 SN   sleep 300",
          "stderr": ""
        },
        "live_dir_exists_after": true,
        "stale_dir_exists_after": false,
        "deleted": [
          "/private/tmp/redcap-retention-external.L1q5kA/redcap-e2e-runs-retention-external/redcap-e2e-runs-stale-active"
        ],
        "plan_delete_candidates": [
          {
            "active_marker_running": true,
            "active_packet_count": 1,
            "active_packet_states": [
              {
                "declared_running": true,
                "process_checked": false,
                "process_running": false,
                "reason": "worker-pid-missing",
                "worker_pid": null
              }
            ],
            "active_process_running": false,
            "active_running": false,
            "active_unverified_running": true,
            "age_seconds": 120.21955299377441,
            "delete_allowed": true,
            "delete_reason": "陈旧 active 目录超过 0 秒，显式允许清理",
            "mtime": 1781951638.802952,
            "mtime_iso": "2026-06-20T10:33:58+00:00",
            "name": "redcap-e2e-runs-stale-active",
            "path": "/private/tmp/redcap-retention-external.L1q5kA/redcap-e2e-runs-retention-external/redcap-e2e-runs-stale-active",
            "stale_active_seconds": 0,
            "state_file_missing": false,
            "state_file_warning": "",
            "status": "stale-active",
            "summary_paths": [
              "/private/tmp/redcap-retention-external.L1q5kA/redcap-e2e-runs-retention-external/redcap-e2e-runs-stale-active/redcap-e2e-run-summary.json"
            ]
          }
        ]
      }
    },
    "invocation_summary": {
      "script_sha256": "a1ce0c020f8b61f5a978d917789330e2a4c42af5fee6bd0463d8d4693afe974a",
      "source_snapshot": "retention-external-validation-source.txt",
      "prune_command": [
        "runtime/bin/redcap",
        "complete-revival-e2e",
        "prune-runs",
        "--root",
        "/tmp/redcap-retention-external.L1q5kA/redcap-e2e-runs-retention-external",
        "--keep-latest-success",
        "5",
        "--keep-latest-failed",
        "20",
        "--delete-stale-active",
        "--stale-active-hours",
        "0.0001",
        "--delete-old-failed",
        "--old-failed-hours",
        "72",
        "--out",
        "/tmp/redcap-retention-external.L1q5kA/evidence/prune-execute.json",
        "--execute"
      ],
      "validation_command": [
        "python3",
        "runtime/audit/e2e_retention_external_validation.py",
        "--root",
        "/tmp/redcap-retention-external.L1q5kA/redcap-e2e-runs-retention-external",
        "--prune-result",
        "/tmp/redcap-retention-external.L1q5kA/evidence/prune-execute.json",
        "--live-dir",
        "/tmp/redcap-retention-external.L1q5kA/redcap-e2e-runs-retention-external/redcap-e2e-runs-live-active",
        "--stale-dir",
        "/tmp/redcap-retention-external.L1q5kA/redcap-e2e-runs-retention-external/redcap-e2e-runs-stale-active",
        "--sleep-pid",
        "39591",
        "--out",
        "/tmp/redcap-retention-external.L1q5kA/evidence/retention-external-validation.json"
      ]
    }
  },
  "changed_reality": [
    "runtime/audit/e2e_retention_external_validation.py 现在在输出中记录 validator.runtime_isolation，包括 pid、ppid、executable、argv、cwd、Python 版本和 ps 快照。",
    "assets/contracts/complete-revival-e2e-acceptance-design.json 要求 runtime_isolation_required=true，且 evidence_required 包含 retention-external-validation.json#validator.runtime_isolation。",
    "runtime/core/complete_revival_e2e.py 的 validate_contract 会在缺少 external_validation_observer、source_snapshot_required、invocation_record_required、runtime_isolation_required、evidence_required 或验证器源码时非零失败。",
    "assets/contracts/open-loop-closure-queue.json 的 OL-01 evidence_required 加入外部验证器运行时隔离记录。",
    "新增 enforcement-receipts 证据包，包含 design-check 与 py_compile 的 receipt.json，以及 validate_contract 源码片段。"
  ],
  "evidence": [
    {
      "kind": "runtime-check",
      "reference": "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/enforcement-receipts/complete-revival-e2e-design-check/receipt.json",
      "summary": "design-check ok=true"
    },
    {
      "kind": "runtime-check",
      "reference": "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/enforcement-receipts/py-compile-external-observer/receipt.json",
      "summary": "py_compile ok=true"
    },
    {
      "kind": "source-snippet",
      "reference": "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/enforcement-receipts/validate-contract-external-observer-source.txt",
      "summary": "validate_contract external_validation_observer 强制检查源码片段"
    },
    {
      "kind": "runtime-check",
      "reference": "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/process-fixture/retention-external-validation.json",
      "summary": "独立验证器输出 ok=true 且包含 runtime_isolation"
    },
    {
      "kind": "runtime-check",
      "reference": "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/process-fixture/retention-external-validation-invocation.json",
      "summary": "验证器调用记录与源码快照哈希"
    }
  ],
  "known_constraints": [
    "不声明 RedCap 完整复活。",
    "不把当前基础修复冒充为完整 OL-01 外部 E2E。",
    "如果仍有 concern，请判断它是否属于当前基础修复必须解决，还是 OL-01 实际执行阶段必须满足的准入。"
  ],
  "review_questions": [
    "Kimi 上一轮的 minimum_fix 是否已被内联源码片段、design-check receipt 和 py_compile receipt 满足？",
    "Claude Code 上一轮的 runtime isolation 关注点是否已被 validator.runtime_isolation 和合同 runtime_isolation_required 满足？",
    "独立实体交叉审计作为 OL-01 启动前硬准入是否足够，还是必须在当前基础修复阶段额外完成？如果必须，请给出无需完整 OL-01 的最小可执行检查。"
  ],
  "file_access": {
    "mode": "bounded-read",
    "allowed_paths": [
      "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/enforcement-receipts/complete-revival-e2e-design-check/receipt.json",
      "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/enforcement-receipts/py-compile-external-observer/receipt.json",
      "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/enforcement-receipts/validate-contract-external-observer-source.txt",
      "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/process-fixture/retention-external-validation.json",
      "assets/evidence/check-receipts/20260620-open-loop-objective-final-closure/external-validation/process-fixture/retention-external-validation-invocation.json"
    ],
    "max_files": 5,
    "max_bytes_per_file": 220000,
    "max_total_bytes": 700000,
    "purpose": "复核上一轮 concern 的证据，不展开完整 RedCap 复活结论。"
  }
}
