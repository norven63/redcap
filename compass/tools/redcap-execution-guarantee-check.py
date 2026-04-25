#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import sys


REQUIRED_IDS = {
    "revival-core-files",
    "revival-current-status",
    "revival-reload-rules",
    "external-four-line-status",
    "lessons-preflight",
    "lessons-closeout",
    "knowledge-index-navigation",
    "workflow-panorama-surface",
    "soul-identity-read",
    "soul-identity-update",
    "install-revival-entry",
    "prism-formal-run",
    "prism-cli-health",
    "cli-registry-refresh",
    "overlay-ask-user-boundary",
    "diagnostic-overview",
    "tracking-health-overview",
    "scribe-runtime-vitality",
    "task-card-reanchor-scope",
    "state-machine-contract",
    "layerb-closeout-runtime",
    "planning-review-gate",
    "acceptance-index-navigation",
    "task-report-closure",
    "docs-catalog-freshness",
    "docs-progressive-disclosure",
    "token-risk-audit",
    "contributing-core-routing",
    "review-tracks-gate",
    "hook-contract-audit",
    "runtime-helper-convergence",
    "cli-console-mirror-contract",
    "control-gate-failure-propagation",
    "host-hook-convergence",
    "main-agent-interruption-boundary",
    "evolution-grade-baseline",
    "evolution-candidate-pool",
    "evolution-harvest-gate",
    "skill-lifecycle-single-source",
    "legacy-asset-lifecycle",
}

ALLOWED_PRIORITIES = {"P0", "P1", "P2", "P3"}
ALLOWED_STATUSES = {"scripted", "hooked", "validator", "documented", "manual-only", "not-automatable"}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-execution-guarantee-check] {message}")


def strip_anchor(path: str) -> str:
    return path.split("#", 1)[0]


def exists(root: pathlib.Path, rel_path: str) -> bool:
    rel_path = strip_anchor(rel_path).strip()
    if not rel_path:
        return False
    if rel_path.startswith("~/"):
        return True
    candidate = pathlib.Path(rel_path)
    if candidate.is_absolute():
        return candidate.exists()
    return (root / candidate).exists()


def main() -> None:
    root = pathlib.Path(sys.argv[1])
    registry_path = pathlib.Path(sys.argv[2])

    if not registry_path.is_file():
        fail(f"missing registry: {registry_path}")

    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid json: {exc}")

    if data.get("version") != 1:
        fail("version must be 1")

    required_categories = data.get("required_categories")
    if not isinstance(required_categories, list) or not required_categories:
        fail("required_categories must be a non-empty list")
    required_categories = {item for item in required_categories if isinstance(item, str) and item.strip()}

    guarantees = data.get("guarantees")
    if not isinstance(guarantees, list) or not guarantees:
        fail("guarantees must be a non-empty list")

    seen_ids: set[str] = set()
    seen_categories: set[str] = set()
    revival_count = 0
    hook_count = 0

    for entry in guarantees:
        if not isinstance(entry, dict):
            fail("guarantee entries must be objects")
        gid = entry.get("id")
        if not isinstance(gid, str) or not gid.strip():
            fail("guarantee entry missing id")
        if gid in seen_ids:
            fail(f"duplicate guarantee id: {gid}")
        seen_ids.add(gid)

        category = entry.get("category")
        if category not in required_categories:
            fail(f"{gid}: category is missing or not listed in required_categories: {category}")
        seen_categories.add(category)

        priority = entry.get("priority")
        if priority not in ALLOWED_PRIORITIES:
            fail(f"{gid}: invalid priority: {priority}")

        status = entry.get("status")
        if status not in ALLOWED_STATUSES:
            fail(f"{gid}: invalid status: {status}")

        rule = entry.get("rule")
        if not isinstance(rule, str) or len(rule.strip()) < 20:
            fail(f"{gid}: rule must be a meaningful sentence")

        sources = entry.get("source_paths")
        if not isinstance(sources, list) or not sources:
            fail(f"{gid}: source_paths must be non-empty")
        for source in sources:
            if not isinstance(source, str) or not source.strip():
                fail(f"{gid}: invalid source path")
            if not exists(root, source):
                fail(f"{gid}: source path does not exist: {source}")

        auto_enforceable = entry.get("auto_enforceable")
        if not isinstance(auto_enforceable, bool):
            fail(f"{gid}: auto_enforceable must be boolean")

        guarantee_paths = entry.get("guarantee_paths", [])
        if guarantee_paths is None:
            guarantee_paths = []
        if not isinstance(guarantee_paths, list):
            fail(f"{gid}: guarantee_paths must be a list")

        if auto_enforceable:
            if not guarantee_paths:
                fail(f"{gid}: auto-enforceable rule has no guarantee_paths")
            for path in guarantee_paths:
                if not isinstance(path, str) or not path.strip():
                    fail(f"{gid}: invalid guarantee path")
                if not exists(root, path):
                    fail(f"{gid}: guarantee path does not exist: {path}")
        else:
            reason = entry.get("non_automation_reason")
            if not isinstance(reason, str) or len(reason.strip()) < 20:
                fail(f"{gid}: non-auto rule must explain why automation is unsafe")

        if entry.get("revival_required") is True:
            revival_count += 1
        if entry.get("hook_required") is True:
            hook_count += 1

    missing_ids = sorted(REQUIRED_IDS - seen_ids)
    if missing_ids:
        fail("missing required guarantee ids: " + ", ".join(missing_ids))

    missing_categories = sorted(required_categories - seen_categories)
    if missing_categories:
        fail("required categories have no guarantee entries: " + ", ".join(missing_categories))

    if revival_count == 0:
        fail("no revival_required guarantees declared")
    if hook_count == 0:
        fail("no hook_required guarantees declared")

    boundaries = data.get("manual_review_boundaries")
    if not isinstance(boundaries, list) or not boundaries:
        fail("manual_review_boundaries must be non-empty")
    for boundary in boundaries:
        if not isinstance(boundary, dict):
            fail("manual_review_boundaries entries must be objects")
        if not isinstance(boundary.get("id"), str) or not boundary["id"].strip():
            fail("manual_review boundary missing id")
        if not isinstance(boundary.get("reason"), str) or len(boundary["reason"].strip()) < 20:
            fail(f"manual_review boundary has weak reason: {boundary.get('id')}")

    print("EXECUTION_GUARANTEES_OK")


if __name__ == "__main__":
    main()
