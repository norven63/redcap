#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / "references/information-architecture-artifact-governance-policy.json"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-information-architecture-check] {message}")


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        fail(f"{label} missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid {label} json: {exc}")
    if not isinstance(payload, dict):
        fail(f"{label} must be a JSON object")
    return payload


def resolve(root: Path, raw: str) -> Path:
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    return root / path


def require_text(payload: dict[str, Any], key: str, label: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        fail(f"{label}: missing non-empty {key}")
    return value.strip()


def require_list(payload: dict[str, Any], key: str, label: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        fail(f"{label}: {key} must be a non-empty list")
    return value


def parse_task_metadata(task_file: Path) -> dict[str, str]:
    if not task_file.is_file():
        return {}
    metadata: dict[str, str] = {}
    for raw in task_file.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+):\s*(.*?)\s*$", raw)
        if match:
            metadata[match.group(1)] = match.group(2).strip()
    return metadata


def file_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.iterdir() if item.is_file() and not is_acceptance_tmp_file(item))


def is_acceptance_tmp_file(item: Path) -> bool:
    if os.environ.get("REDCAP_ACCEPTANCE_RUNNING") != "1":
        return False
    return item.name.startswith(("zz-acceptance-", "zz-review-"))


def validate_policy(policy: dict[str, Any], root: Path) -> None:
    if policy.get("version") != 1:
        fail("policy version must be 1")
    if policy.get("policy_id") != "redcap-information-architecture-artifact-governance":
        fail("unexpected policy_id")
    if "public CLI/runtime release" not in require_text(policy, "release_boundary", "policy"):
        fail("release_boundary must explicitly reference public CLI/runtime release")

    root_classes = require_list(policy, "root_classes", "policy")
    required_ids = {
        "current-task-truth",
        "current-task-reports",
        "private-task-report-archive",
        "active-knowledge",
        "private-research-archive",
        "prism-runs",
        "shared-knowledge-template",
        "external-redcap-arsenal",
    }
    seen: set[str] = set()
    for item in root_classes:
        if not isinstance(item, dict):
            fail("root_classes entries must be objects")
        item_id = require_text(item, "id", "root_class")
        if item_id in seen:
            fail(f"duplicate root class id: {item_id}")
        seen.add(item_id)
        path = require_text(item, "path", item_id)
        require_text(item, "class", item_id)
        require_text(item, "visibility", item_id)
        require_text(item, "lifecycle", item_id)
        require_text(item, "human_meaning", item_id)
        require_text(item, "public_export", item_id)
        if item_id != "external-redcap-arsenal" and not resolve(root, path).exists():
            fail(f"{item_id}: path does not exist: {path}")
        if item_id == "current-task-reports":
            max_files = item.get("max_files")
            if not isinstance(max_files, int) or max_files <= 0:
                fail("current-task-reports must declare positive max_files")
            actual = file_count(resolve(root, path))
            if actual > max_files:
                fail(
                    "current task report inbox too large: "
                    f"files={actual} max={max_files}; "
                    "move old reports through the explicit legacy-asset lifecycle into "
                    "redcap-knowledge/task-reports/ before claiming the active inbox is healthy"
                )
    missing = sorted(required_ids - seen)
    if missing:
        fail("missing root classes: " + ", ".join(missing))

    report = policy.get("report_lifecycle")
    if not isinstance(report, dict):
        fail("report_lifecycle must be an object")
    active_root = require_text(report, "active_root", "report_lifecycle")
    archive_root = require_text(report, "private_archive_root", "report_lifecycle")
    if active_root == archive_root:
        fail("report active_root and private_archive_root must differ")
    if not resolve(root, active_root).is_dir():
        fail(f"report active_root missing: {active_root}")
    if not resolve(root, archive_root).is_dir():
        fail(f"report private_archive_root missing: {archive_root}")
    summary_rule = require_text(report, "summary_rule", "report_lifecycle")
    for phrase in ["sections 0.1-0.4", "manual review", "manual validation"]:
        if phrase not in summary_rule:
            fail(f"report summary_rule missing phrase: {phrase}")
    if not require_list(report, "must_not_claim", "report_lifecycle"):
        fail("report_lifecycle must define must_not_claim")

    boundaries = policy.get("artifact_boundaries")
    if not isinstance(boundaries, dict):
        fail("artifact_boundaries must be an object")
    forbidden = require_list(boundaries, "raw_private_sources_forbidden_in_public", "artifact_boundaries")
    for required in ["compass/docs/task-reports/**", "redcap-knowledge/**", "compass/knowledge/**", "prism/runs/**", ".env"]:
        if required not in forbidden:
            fail(f"artifact boundary missing forbidden raw source: {required}")
    for required in ["privacy and secret scan", "normalized duplicate check", "append-only timestamped entry", "index-first retrieval metadata"]:
        if required not in require_list(boundaries, "public_outputs_require", "artifact_boundaries"):
            fail(f"artifact boundary missing public output requirement: {required}")

    for linked in require_list(policy, "required_policy_links", "policy"):
        if not isinstance(linked, str) or not linked.strip():
            fail("required_policy_links must contain strings")
        if not resolve(root, linked).exists():
            fail(f"required policy link missing: {linked}")

    p4 = policy.get("p4_status_semantics")
    if not isinstance(p4, dict):
        fail("p4_status_semantics must be an object")
    phrase = require_text(p4, "required_ledger_phrase", "p4_status_semantics")
    ledger = (root / "references/redcap-parent-task-ledger.md").read_text(encoding="utf-8", errors="replace")
    if phrase not in ledger:
        fail("parent ledger missing P4 status semantics phrase")


def validate_cross_policies(root: Path) -> None:
    shared = load_json(root / "references/shared-knowledge-policy.json", "shared knowledge policy")
    remote = load_json(root / "references/shared-knowledge-remote-binding.json", "shared knowledge remote binding")
    human = load_json(root / "references/human-communication-policy.json", "human communication policy")

    if "RedCap Forge" not in json.dumps(shared, ensure_ascii=False):
        fail("shared knowledge policy must mention RedCap Forge")
    forbidden = remote.get("forbidden_path_globs")
    if not isinstance(forbidden, list):
        fail("remote binding forbidden_path_globs must be a list")
    for required in ["compass/docs/task-reports/**", "redcap-knowledge/**", "compass/knowledge/**", "prism/runs/**"]:
        if required not in forbidden:
            fail(f"remote binding missing forbidden path glob: {required}")

    final_rule = str(human.get("report_led_summary_rule", ""))
    if "0.1-0.4" not in final_rule or "人工审核" not in final_rule or "人工验证" not in final_rule:
        fail("human communication policy missing report-led summary/manual intervention rule")


def validate_task_card(root: Path) -> None:
    meta = parse_task_metadata(root / ".dev-task.md")
    report = meta.get("task_report", "")
    if report and not report.startswith("compass/docs/task-reports/"):
        fail(f"current task_report must live in active report inbox: {report}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    policy_path = Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = root / policy_path
    policy = load_json(policy_path, "information architecture policy")

    validate_policy(policy, root)
    validate_cross_policies(root)
    validate_task_card(root)

    print("INFORMATION_ARCHITECTURE_GOVERNANCE")
    print(f"root_classes={len(policy.get('root_classes', []))}")
    print("INFORMATION_ARCHITECTURE_GOVERNANCE_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
