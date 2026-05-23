#!/usr/bin/env python3
# 用途：校验 P4-27 只完成小范围合同镜像 apply 预检，不执行真实迁移。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_MANIFEST = ROOT / "references/r1-contract-mirror-apply-preflight-subset.json"
P4_26_ROUTE = ROOT / "references/r1-next-safe-slice-after-control-plane-contract-mirror-preflight.json"
P4_25_MANIFEST = ROOT / "references/r1-control-plane-public-internal-contract-mirror-preflight.json"
CONTRACT_SPLIT = ROOT / "references/r1-control-plane-contract-split-preflight.json"
BACKLOG = ROOT / "references/backlogs/framework-upgrade.json"
PRISM_REPORT = ROOT / "prism/reports/2026-05-23-r1-contract-mirror-apply-preflight-subset.md"
TASK_REPORT = ROOT / "compass/docs/task-reports/2026-05-23-r1-contract-mirror-apply-preflight-subset.md"
P4_29_APPLY = ROOT / "references/r1-contract-mirror-bounded-copy-first-apply.json"
EXPECTED_BLOCKERS = {"internal-control-plane", "prism-layer-and-evidence", "internal-layer-a"}


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-r1-contract-mirror-apply-preflight-subset-check] {message}")


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        fail(f"missing {label}: {path.relative_to(ROOT)}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid {label}: {exc}")
    if not isinstance(data, dict):
        fail(f"{label} must be a JSON object")
    return data


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_bool(value: Any, expected: bool, label: str) -> None:
    if value is not expected:
        fail(f"{label} must be {str(expected).lower()}")


def require_list(value: Any, label: str, *, min_len: int = 1) -> list[Any]:
    if not isinstance(value, list) or len(value) < min_len:
        fail(f"{label} must be a list with at least {min_len} items")
    return value


def contract_split_entries() -> dict[str, str]:
    split = load_json(CONTRACT_SPLIT, "contract split preflight")
    entries = split.get("physical_split_dry_run_manifest", {}).get("entries")
    if not isinstance(entries, list):
        fail("contract split entries must be a list")
    result: dict[str, str] = {}
    for item in entries:
        if isinstance(item, dict) and isinstance(item.get("source"), str):
            layer = item.get("target_layer")
            if isinstance(layer, str):
                result[item["source"]] = layer
    return result


def downstream_apply_manifest() -> dict[str, Any] | None:
    if not P4_29_APPLY.is_file():
        return None
    payload = load_json(P4_29_APPLY, "P4-29 bounded copy-first apply")
    if payload.get("apply_id") != "redcap-r1-contract-mirror-bounded-copy-first-apply":
        fail("P4-29 apply manifest apply_id mismatch")
    if payload.get("status") != "copy-first-apply-old-anchors-retained-no-release-blocker-closed":
        fail("P4-29 apply manifest status mismatch")
    return payload


def downstream_copy(payload: dict[str, Any] | None, source_rel: str, target_rel: str) -> dict[str, Any] | None:
    if payload is None:
        return None
    copies = payload.get("copies")
    if not isinstance(copies, list):
        fail("P4-29 apply manifest copies must be a list")
    for item in copies:
        if isinstance(item, dict) and item.get("source") == source_rel and item.get("target") == target_rel:
            return item
    return None


def downstream_source_update(payload: dict[str, Any] | None, source_rel: str, old_hash: str, current_hash: str) -> bool:
    if payload is None:
        return False
    updates = payload.get("source_updates_after_preflight", [])
    if not isinstance(updates, list):
        fail("P4-29 apply source_updates_after_preflight must be a list")
    for item in updates:
        if not isinstance(item, dict) or item.get("source") != source_rel:
            continue
        if item.get("preflight_source_sha256") != old_hash:
            fail(f"P4-29 source update preflight hash mismatch: {source_rel}")
        if item.get("current_source_sha256") != current_hash:
            fail(f"P4-29 source update current hash mismatch: {source_rel}")
        return True
    return False


def target_allowed_by_downstream_apply(payload: dict[str, Any] | None, source_rel: str, target_rel: str, current_source_hash: str) -> bool:
    copy = downstream_copy(payload, source_rel, target_rel)
    if copy is None:
        return False
    target = ROOT / target_rel
    if not target.is_file() or target.is_symlink():
        return False
    if copy.get("byte_identical") is not True or copy.get("old_anchor_retained") is not True:
        fail(f"P4-29 copy entry must keep byte-identical/old-anchor boundary: {target_rel}")
    if copy.get("source_sha256") != current_source_hash or copy.get("target_sha256") != sha256(target):
        fail(f"P4-29 copy entry hash is stale: {target_rel}")
    return sha256(target) == current_source_hash


def validate_source_truth(manifest: dict[str, Any]) -> None:
    source = manifest.get("source_truth")
    if not isinstance(source, dict):
        fail("source_truth must be an object")
    expected = {
        "p4_26_route": P4_26_ROUTE,
        "p4_25_manifest": P4_25_MANIFEST,
        "contract_split": CONTRACT_SPLIT,
    }
    for key, path in expected.items():
        if source.get(f"{key}_path") != str(path.relative_to(ROOT)):
            fail(f"source_truth.{key}_path mismatch")
        if source.get(f"{key}_sha256") != sha256(path):
            fail(f"source_truth.{key}_sha256 is stale")


def validate_subset(manifest: dict[str, Any]) -> None:
    downstream_apply = downstream_apply_manifest()
    policy = manifest.get("subset_policy")
    if not isinstance(policy, dict):
        fail("subset_policy must be an object")
    if policy.get("physical_apply_allowed_now") is not False:
        fail("subset_policy.physical_apply_allowed_now must be false")
    if policy.get("future_target_paths_must_not_exist_now") is not True:
        fail("subset_policy.future_target_paths_must_not_exist_now must be true")

    entries = require_list(manifest.get("selected_subset"), "selected_subset", min_len=4)
    if len(entries) > 8:
        fail("selected_subset must remain small (<= 8 items)")

    split_layers = contract_split_entries()
    seen_sources: set[str] = set()
    seen_targets: set[str] = set()
    counts = {"public-contract": 0, "internal-contract": 0}
    for item in entries:
        if not isinstance(item, dict):
            fail("selected_subset entries must be objects")
        source = item.get("source")
        layer = item.get("source_target_layer")
        target = item.get("future_target")
        if not isinstance(source, str) or not source:
            fail("selected_subset.source must be a string")
        if not isinstance(layer, str) or layer not in counts:
            fail(f"{source}: source_target_layer must be public-contract or internal-contract")
        if split_layers.get(source) != layer:
            fail(f"{source}: source layer does not match contract split preflight")
        source_path = ROOT / source
        if not source_path.is_file():
            fail(f"selected source missing: {source}")
        current_source_hash = sha256(source_path)
        preflight_source_hash = item.get("source_sha256")
        if preflight_source_hash != current_source_hash and not downstream_source_update(
            downstream_apply,
            source,
            str(preflight_source_hash),
            current_source_hash,
        ):
            fail(f"{source}: source_sha256 is stale without P4-29 downstream bridge")
        if not isinstance(target, str) or not target.startswith(f"contracts/{'public' if layer == 'public-contract' else 'internal'}/"):
            fail(f"{source}: future_target does not match layer")
        if (ROOT / target).exists() and not target_allowed_by_downstream_apply(
            downstream_apply,
            source,
            target,
            current_source_hash,
        ):
            fail(f"{source}: future target already exists without valid P4-29 downstream apply bridge")
        if item.get("apply_mode") != "future-copy-first-only":
            fail(f"{source}: apply_mode must be future-copy-first-only")
        if source in seen_sources:
            fail(f"duplicate selected source: {source}")
        if target in seen_targets:
            fail(f"duplicate future target: {target}")
        seen_sources.add(source)
        seen_targets.add(target)
        counts[layer] += 1

    if counts["public-contract"] < 3:
        fail("selected_subset must include at least 3 public-contract entries")
    if counts["internal-contract"] < 3:
        fail("selected_subset must include at least 3 internal-contract entries")
    if policy.get("selected_total") != len(entries):
        fail("subset_policy.selected_total must equal selected_subset length")
    if policy.get("selected_public_contract_count") != counts["public-contract"]:
        fail("subset_policy.selected_public_contract_count is stale")
    if policy.get("selected_internal_contract_count") != counts["internal-contract"]:
        fail("subset_policy.selected_internal_contract_count is stale")


def validate_future_apply_requirements(manifest: dict[str, Any]) -> None:
    requirements = manifest.get("future_apply_requirements")
    if not isinstance(requirements, dict):
        fail("future_apply_requirements must be an object")
    if requirements.get("allowed_future_operation") != "copy-first-only":
        fail("future_apply_requirements.allowed_future_operation must be copy-first-only")
    for key in ["required_before_apply", "rollback_plan", "stop_conditions"]:
        joined = "\n".join(str(item) for item in require_list(requirements.get(key), f"future_apply_requirements.{key}", min_len=3))
        for phrase in ["old", "release", "Prism"]:
            if key != "rollback_plan" and phrase.lower() not in joined.lower():
                fail(f"future_apply_requirements.{key} missing phrase: {phrase}")


def validate_claim_boundary(manifest: dict[str, Any]) -> None:
    boundary = manifest.get("claim_boundary")
    if not isinstance(boundary, dict):
        fail("claim_boundary must be an object")
    require_bool(boundary.get("apply_preflight_completed"), True, "claim_boundary.apply_preflight_completed")
    for key in [
        "physical_apply_completed",
        "files_copied",
        "files_moved",
        "files_deleted",
        "old_anchors_removed_or_replaced",
        "raw_run_evidence_deleted_or_cleaned",
        "release_switch_changed",
        "layer_a_product_decision_made",
        "release_blocker_closed",
        "public_release_ready",
    ]:
        require_bool(boundary.get(key), False, f"claim_boundary.{key}")


def iter_backlog_items(backlog: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for group in backlog.get("groups", []):
        if isinstance(group, dict):
            items.extend(item for item in group.get("items", []) if isinstance(item, dict))
    return items


def validate_backlog() -> None:
    backlog = load_json(BACKLOG, "framework upgrade backlog")
    items = {item.get("id"): item for item in iter_backlog_items(backlog)}
    if items.get("P4-27", {}).get("status") not in {"pending", "done"}:
        fail("P4-27 must be registered as pending or done")
    current_focus = backlog.get("current_focus", {}).get("item_id")
    if items.get("P4-27", {}).get("status") == "pending" and current_focus != "P4-27":
        fail("current_focus.item_id must be P4-27 while P4-27 is pending")
    if items.get("P4-27", {}).get("status") == "done":
        if current_focus == "P4-27":
            fail("current_focus.item_id must advance after P4-27 is done")
        if items.get("P4-28", {}).get("status") not in {"pending", "done"}:
            fail("P4-28 must be registered as pending or done after P4-27 is done")


def validate_prism_review(manifest: dict[str, Any]) -> None:
    review = manifest.get("prism_review")
    if not isinstance(review, dict):
        fail("prism_review must be an object")
    if review.get("run_id") != "20260523-r1-contract-mirror-apply-preflight-subset":
        fail("prism_review.run_id mismatch")
    verdict = review.get("verdict")
    if verdict == "pending":
        return
    if verdict not in {"pass-no-human-hard-gate-crossed", "pass-with-notes"}:
        fail("prism_review.verdict must confirm no human hard gate was crossed")
    agents = require_list(review.get("agents"), "prism_review.agents", min_len=2)
    families = {str(agent.get("provider")) for agent in agents if isinstance(agent, dict) and agent.get("status") == "responded"}
    if not {"claude-code", "kimi"}.issubset(families):
        fail("prism_review must include responded claude-code and kimi")


def validate_reports(manifest: dict[str, Any]) -> None:
    for path, label in [(PRISM_REPORT, "Prism report"), (TASK_REPORT, "task report")]:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for forbidden in ["已可发布", "已正式发布", "旧锚点已删除", "raw evidence 已清理"]:
            if forbidden in text:
                fail(f"{label} contains forbidden overclaim: {forbidden}")


def validate_result(manifest: dict[str, Any]) -> None:
    result = manifest.get("result")
    if not isinstance(result, dict):
        fail("result must be an object")
    if result.get("release_blocker_status") != "still-blocking-after-apply-preflight":
        fail("result.release_blocker_status must remain still-blocking-after-apply-preflight")
    require_bool(result.get("contract_mirror_apply_preflight_completed"), True, "result.contract_mirror_apply_preflight_completed")
    require_bool(result.get("physical_apply_completed"), False, "result.physical_apply_completed")
    require_bool(result.get("public_release_ready"), False, "result.public_release_ready")
    if set(result.get("remaining_release_blockers_after_this_preflight", [])) != EXPECTED_BLOCKERS:
        fail("result.remaining_release_blockers_after_this_preflight must keep all blockers open")


def validate(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("version") != 1:
        fail("version must be 1")
    if manifest.get("preflight_id") != "redcap-r1-contract-mirror-apply-preflight-subset":
        fail("preflight_id mismatch")
    if manifest.get("status") != "apply-preflight-only-no-files-copied-moved-or-deleted":
        fail("status must be apply-preflight-only-no-files-copied-moved-or-deleted")
    validate_source_truth(manifest)
    validate_subset(manifest)
    validate_future_apply_requirements(manifest)
    validate_claim_boundary(manifest)
    validate_backlog()
    validate_prism_review(manifest)
    validate_reports(manifest)
    validate_result(manifest)
    return {
        "selected": len(manifest["selected_subset"]),
        "next": manifest.get("post_closeout_autocontinuation", {}).get("next_backlog_item"),
    }


def main() -> int:
    manifest_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_MANIFEST
    summary = validate(load_json(manifest_path, "P4-27 contract mirror apply preflight subset manifest"))
    print(
        "R1_CONTRACT_MIRROR_APPLY_PREFLIGHT_SUBSET_OK "
        f"selected={summary['selected']} next={summary['next']} release_blocker_status=still-blocking"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
