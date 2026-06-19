#!/usr/bin/env python3
"""独立验证 E2E 分层前置门禁，不通过 redcap CLI 自检闭环。"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest import mock


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "runtime" / "core" / "complete_revival_e2e.py"


def load_e2e_module():
    import sys

    sys.path.insert(0, str(MODULE_PATH.parent))
    spec = importlib.util.spec_from_file_location("complete_revival_e2e_under_test", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 complete_revival_e2e.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


e2e = load_e2e_module()


class LayeredPreflightTests(unittest.TestCase):
    def _write_minimal_reviewer_evidence(self, evidence: pathlib.Path) -> None:
        evidence.mkdir(parents=True, exist_ok=True)
        e2e.write_json(evidence / "failure-backlog.json", {
            "schema_id": "redcap-e2e-failure-backlog",
            "open_items": [],
            "closed_items": [],
            "next_round_required": False,
        })
        e2e.write_json(evidence / "self-purification-candidates.json", {
            "schema_id": "redcap-e2e-self-purification-candidates",
            "candidates": [
                {
                    "id": "reviewer-contract",
                    "summary": "校验 reviewer 顶层棱镜请求契约。",
                    "source": "unit-test",
                    "decisions": [
                        {
                            "decision": "no_promote",
                            "reason": "单测夹具不晋升为公共知识。",
                        }
                    ],
                }
            ],
        })
        e2e.write_json(evidence / "persona-distillation-decision.json", {
            "schema_id": "redcap-e2e-persona-distillation-decision",
            "privacy_class": "cap-private",
            "public_write": False,
            "private_body_written": False,
            "reason": "单测没有可晋升的人格信号。",
        })
        e2e.write_json(evidence / "review-verdict.json", {
            "schema_id": "redcap-e2e-review-verdict",
            "terminal_completion": False,
            "blocking_findings": [],
            "runner_owned_follow_up": e2e.REVIEWER_RUNNER_OWNED_FOLLOW_UP,
            "role_opposition_matrix": [
                {"role": "product_manager", "challenge_summary": "产品挑战", "reviewer_disposition": "accepted"},
                {"role": "architect", "challenge_summary": "架构挑战", "reviewer_disposition": "accepted"},
                {"role": "developer", "challenge_summary": "开发挑战", "reviewer_disposition": "accepted"},
                {"role": "tester", "challenge_summary": "测试挑战", "reviewer_disposition": "accepted"},
            ],
        })

    def test_reviewer_prism_assistance_request_must_be_top_level(self) -> None:
        with tempfile.TemporaryDirectory(prefix="redcap-reviewer-contract-unit-") as raw:
            evidence = pathlib.Path(raw) / "evidence"
            self._write_minimal_reviewer_evidence(evidence)

            valid_payload = {
                "schema_id": "redcap-e2e-prism-assisted-review",
                "used": True,
                "reviews": [
                    {
                        "scope": "runner-prism-boundary",
                        "finding": "顶层棱镜请求存在。",
                        "effect_on_verdict": "阶段评审通过。",
                    }
                ],
                "skip_reason": None,
                "cap_decision": "stage_pass",
                "prism_assistance_request": {"requested": True, "owner": "e2e-runner"},
            }
            e2e.write_json(evidence / "prism-assisted-review.json", valid_payload)
            self.assertEqual(e2e.validate_reviewer_outputs(evidence), [])

            nested_only = dict(valid_payload)
            nested_only.pop("prism_assistance_request")
            nested_only["reviews"] = [
                {
                    "scope": "runner-prism-boundary",
                    "finding": "错误嵌套棱镜请求。",
                    "effect_on_verdict": "必须失败。",
                    "prism_assistance_request": {"requested": True},
                }
            ]
            e2e.write_json(evidence / "prism-assisted-review.json", nested_only)
            nested_failures = e2e.validate_reviewer_outputs(evidence)
            self.assertTrue(any("reviews[] 内部不算有效请求" in item for item in nested_failures))

            missing = dict(valid_payload)
            missing.pop("prism_assistance_request")
            e2e.write_json(evidence / "prism-assisted-review.json", missing)
            missing_failures = e2e.validate_reviewer_outputs(evidence)
            self.assertTrue(any("顶层记录运行器统一调度棱镜的请求" in item for item in missing_failures))

    def test_preflight_records_command_failure_without_test_injection(self) -> None:
        def fake_run_command(argv, **_kwargs):
            command = " ".join(argv)
            ok = "knowledge-gateway search loom --require-hit" not in command
            return {
                "argv": argv,
                "cwd": str(REPO_ROOT),
                "exit_code": 0 if ok else 12,
                "ok": ok,
                "timed_out": False,
                "timeout_seconds": 240,
                "stdout": "ok" if ok else "",
                "stderr": "" if ok else "missing loom knowledge",
            }

        with tempfile.TemporaryDirectory(prefix="redcap-preflight-unit-") as raw:
            work_root = pathlib.Path(raw)
            with mock.patch.object(e2e, "run_command", side_effect=fake_run_command):
                result = e2e.run_layered_preflight(work_root)

            self.assertFalse(result["ok"])
            self.assertTrue(result["blocked_before_project_run"])
            self.assertFalse(result["auto_rerun_allowed"])
            self.assertIn("knowledge-search-loom 未通过", result["failures"])
            failed = [item for item in result["checks"] if item["id"] == "knowledge-search-loom"][0]
            self.assertFalse(failed["ok"])
            self.assertFalse(failed["test_injection"])
            self.assertTrue((work_root / "redcap-e2e-layered-preflight.json").exists())

    def test_harness_blocks_before_carrier_probe_when_preflight_fails(self) -> None:
        events: list[str] = []

        def fake_preflight(work_root):
            events.append("preflight")
            return {
                "schema_id": "redcap-ai-e2e-layered-preflight",
                "ok": False,
                "failures": ["knowledge-search-loom 未通过"],
            }

        def fake_active_run(*_args, **kwargs):
            events.append("active-run")
            self.assertFalse(kwargs["auto_rerun_allowed"])
            return {
                "packet": "/tmp/fake-redcap-long-task-active-run.json",
                "lifecycle_state": "blocked",
                "auto_rerun_allowed": False,
            }

        with tempfile.TemporaryDirectory(prefix="redcap-harness-unit-") as raw:
            work_root = pathlib.Path(raw)
            with (
                mock.patch.object(e2e, "patrol_iteration_guard", return_value={"next_iteration": 1, "blocked": False}),
                mock.patch.object(e2e, "convergence_rerun_guard", return_value={"ok": True, "blocked": False}),
                mock.patch.object(e2e, "run_layered_preflight", side_effect=fake_preflight),
                mock.patch.object(e2e, "write_e2e_long_task_active_run", side_effect=fake_active_run),
                mock.patch.object(e2e, "carrier_probe") as carrier_probe,
            ):
                result = e2e.run_e2e_harness("单元测试方向", work_root, timeout_seconds=240)

            self.assertEqual(events, ["preflight", "active-run"])
            carrier_probe.assert_not_called()
            self.assertFalse(result["ok"])
            self.assertTrue(result["blocked_before_project_run"])
            self.assertEqual(result["long_task_active_run"]["lifecycle_state"], "blocked")
            self.assertIn("RedCap E2E 分层前置检查失败", result["failures"][0])

    def test_observer_request_routing_ignores_stale_and_retries_unreadable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="redcap-observer-route-unit-") as raw:
            evidence = pathlib.Path(raw) / "project" / ".redcap" / "evidence" / "e2e"
            evidence.mkdir(parents=True)
            request = evidence / "observer-request.json"
            output = evidence / "independent-observer.json"

            unreadable = e2e.observer_request_routing_decision(request, worker_pid=222)
            self.assertFalse(unreadable["ready"])
            self.assertEqual(unreadable["reason"], "unreadable")

            request.write_text(json.dumps({"runner_pid": 111, "output": str(output)}), encoding="utf-8")
            stale = e2e.observer_request_routing_decision(request, worker_pid=222)
            self.assertFalse(stale["ready"])
            self.assertEqual(stale["reason"], "stale-runner-pid")

            request.write_text(json.dumps({"runner_pid": 222, "output": str(output)}), encoding="utf-8")
            current = e2e.observer_request_routing_decision(request, worker_pid=222)
            self.assertTrue(current["ready"])
            self.assertEqual(current["reason"], "current-worker-request")

            output.write_text("{}", encoding="utf-8")
            already_done = e2e.observer_request_routing_decision(request, worker_pid=222)
            self.assertFalse(already_done["ready"])
            self.assertEqual(already_done["reason"], "output-already-exists")


if __name__ == "__main__":
    unittest.main()
