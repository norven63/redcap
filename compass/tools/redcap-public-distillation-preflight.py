#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / "references/public-distillation-preflight-policy.json"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-public-distillation-preflight] {message}")


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


def require_text(payload: dict[str, Any], key: str, label: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        fail(f"{label}: missing non-empty {key}")
    return value.strip()


def require_bool(payload: dict[str, Any], key: str, label: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        fail(f"{label}: missing boolean {key}")
    return value


def require_list(payload: dict[str, Any], key: str, label: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        fail(f"{label}: {key} must be a non-empty list")
    return value


def repo_path(root: Path, raw: str) -> Path:
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    return (root / path).resolve()


def safe_rel(raw: str, label: str) -> str:
    if raw.startswith("/") or ".." in Path(raw).parts:
        fail(f"{label} must be a safe repo-relative path: {raw}")
    return raw


def path_exists_for_source(root: Path, raw: str) -> bool:
    return repo_path(root, raw).exists()


def count_source_files(root: Path, raw: str) -> int:
    path = repo_path(root, raw)
    if not path.exists():
        return 0
    if path.is_file():
        return 1
    return sum(1 for item in path.rglob("*") if item.is_file())


def resolve_worktree(root: Path, binding: dict[str, Any]) -> Path | None:
    raw = binding.get("preferred_local_worktree")
    if not isinstance(raw, str) or not raw.strip():
        return None
    return repo_path(root, raw.strip())


def substantive_public_entries(worktree: Path | None) -> int:
    if worktree is None or not worktree.is_dir():
        return 0
    users_root = worktree / "users"
    if not users_root.is_dir():
        return 0
    count = 0
    for path in users_root.rglob("*"):
        if not path.is_file() or path.name == ".gitkeep":
            continue
        count += 1
    return count


def glob_matches(pattern: str, candidate: str) -> bool:
    return fnmatch.fnmatch(candidate, pattern) or fnmatch.fnmatch(candidate, pattern.rstrip("/") + "/**")


def contains_required_phrase(values: list[Any], phrase: str, label: str) -> None:
    if not any(phrase in str(item) for item in values):
        fail(f"{label} missing phrase: {phrase}")


def validate_policy_shape(policy: dict[str, Any]) -> None:
    if policy.get("version") != 1:
        fail("policy version must be 1")
    if policy.get("policy_id") != "public-distillation-preflight":
        fail("policy_id must be public-distillation-preflight")
    if policy.get("parent_child_id") != "P4-2h-0":
        fail("parent_child_id must be P4-2h-0")
    if policy.get("status") != "dry-run-only":
        fail("status must be dry-run-only")
    require_text(policy, "purpose", "policy")

    boundaries = policy.get("boundaries")
    if not isinstance(boundaries, dict):
        fail("boundaries must be an object")
    for key in [
        "public_write_allowed",
        "raw_public_export_allowed",
        "delete_or_move_allowed",
        "npm_publish_allowed",
        "arsenal_populated_claim_allowed",
    ]:
        if require_bool(boundaries, key, "boundaries") is not False:
            fail(f"dry-run boundary must remain false: {key}")

    source_roots = require_list(policy, "allowed_private_source_roots", "policy")
    if len(source_roots) < 4:
        fail("allowed_private_source_roots must cover reports, archive, knowledge, and candidates")
    seen_sources: set[str] = set()
    for item in source_roots:
        if not isinstance(item, dict):
            fail("allowed_private_source_roots entries must be objects")
        path = safe_rel(require_text(item, "path", "source root"), "source root path")
        seen_sources.add(path)
        if require_text(item, "raw_public_export", path) != "forbidden":
            fail(f"{path}: raw_public_export must be forbidden")
    for required in [
        "compass/docs/task-reports",
        "redcap-knowledge/task-reports",
        "compass/knowledge",
        "compass/evolution/candidates.json",
    ]:
        if required not in seen_sources:
            fail(f"missing allowed private source root: {required}")

    forbidden = [str(item) for item in require_list(policy, "forbidden_raw_public_sources", "policy")]
    for required in [
        ".dev-task.md",
        ".env",
        "compass/docs/task-reports/**",
        "redcap-knowledge/**",
        "compass/knowledge/**",
        "prism/runs/**",
        "~/.cap/identity.md",
    ]:
        if required not in forbidden:
            fail(f"missing forbidden raw public source: {required}")

    triage = require_list(policy, "triage_classes", "policy")
    expected = {
        "distill_candidate",
        "private_only",
        "no_promote_duplicate_or_low_value",
        "human_review_required",
    }
    actual: set[str] = set()
    for item in triage:
        if not isinstance(item, dict):
            fail("triage_classes entries must be objects")
        class_id = require_text(item, "id", "triage class")
        actual.add(class_id)
        if item.get("public_raw_allowed") is not False:
            fail(f"{class_id}: public_raw_allowed must be false")
        reviews = [str(value) for value in require_list(item, "requires_review", class_id)]
        if class_id == "distill_candidate":
            for required in ["privacy-safety", "secret-scan", "dedupe", "public-value", "evidence", "claim-boundary"]:
                if required not in reviews:
                    fail(f"distill_candidate missing review gate: {required}")
    if actual != expected:
        fail("triage class set mismatch: " + ", ".join(sorted(actual ^ expected)))

    schema = policy.get("future_public_entry_schema")
    if not isinstance(schema, dict):
        fail("future_public_entry_schema must be an object")
    if schema.get("append_only") is not True:
        fail("future public entries must be append-only")
    path_pattern = require_text(schema, "path_pattern", "future_public_entry_schema")
    if "../redcap-arsenal/users/<user>/" not in path_pattern:
        fail("future public entry path must target external redcap-arsenal user namespace")
    for required in ["problem_source", "solution", "final_effect", "privacy_review", "duplicate_review", "public_claim_boundary"]:
        if required not in require_list(schema, "required_sections", "future_public_entry_schema"):
            fail(f"future public entry schema missing required section: {required}")
    for forbidden_section in ["raw_private_transcript", "raw_task_report", "identity_anchor", "environment_secret"]:
        if forbidden_section not in require_list(schema, "forbidden_sections", "future_public_entry_schema"):
            fail(f"future public entry schema missing forbidden section: {forbidden_section}")

    outputs = policy.get("preflight_outputs")
    if not isinstance(outputs, dict):
        fail("preflight_outputs must be an object")
    if outputs.get("tracked_policy_only") is not True:
        fail("preflight must keep tracked output policy-only")
    for key in ["tracked_public_entries", "tracked_raw_content_snapshot"]:
        if outputs.get(key) is not False:
            fail(f"preflight output must remain false: {key}")

    for phrase in ["exports historical knowledge", "public entries are approved", "redcap-arsenal is populated", "npm release readiness"]:
        contains_required_phrase(require_list(policy, "must_not_claim", "policy"), phrase, "must_not_claim")


def validate_cross_policy(root: Path, policy: dict[str, Any]) -> tuple[int, int]:
    links = policy.get("policy_links")
    if not isinstance(links, dict):
        fail("policy_links must be an object")
    loaded: dict[str, dict[str, Any]] = {}
    for key in [
        "redcap_forge",
        "information_architecture",
        "public_arsenal_claim_boundary",
        "remote_binding",
        "pre_release_task_tree",
    ]:
        raw = require_text(links, key, "policy_links")
        safe_rel(raw, f"policy_links.{key}")
        loaded[key] = load_json(repo_path(root, raw), key)

    forge = loaded["redcap_forge"]
    info = loaded["information_architecture"]
    claim = loaded["public_arsenal_claim_boundary"]
    binding = loaded["remote_binding"]
    tree = loaded["pre_release_task_tree"]

    if forge.get("policy_id") != "redcap-forge":
        fail("linked RedCap Forge policy_id mismatch")
    if info.get("policy_id") != "redcap-information-architecture-artifact-governance":
        fail("linked information architecture policy_id mismatch")
    if claim.get("policy_id") != "public-arsenal-claim-boundary":
        fail("linked public arsenal claim boundary policy_id mismatch")
    if tree.get("policy_id") != "pre-release-structure-refactor-task-tree":
        fail("linked task tree policy_id mismatch")

    forbidden = [str(item) for item in require_list(policy, "forbidden_raw_public_sources", "policy")]
    forge_forbidden = [str(item) for item in require_list(forge, "forbidden_public_raw_sources", "RedCap Forge policy")]
    for required in ["compass/docs/task-reports/**", "redcap-knowledge/**", "compass/knowledge/**", "prism/runs/**", ".env"]:
        if required not in forbidden or required not in forge_forbidden:
            fail(f"forbidden raw public source not aligned with Forge: {required}")

    info_forbidden = [
        str(item)
        for item in require_list(
            info.get("artifact_boundaries", {}),
            "raw_private_sources_forbidden_in_public",
            "information architecture artifact boundaries",
        )
    ]
    for required in ["compass/docs/task-reports/**", "redcap-knowledge/**", "compass/knowledge/**", "prism/runs/**", ".env"]:
        if required not in info_forbidden:
            fail(f"information architecture missing forbidden raw source: {required}")

    if binding.get("publish_mode") != "template-only":
        fail("remote binding must remain template-only during preflight")
    if claim.get("current_state", {}).get("content_state") != "template-only":
        fail("public arsenal claim boundary must remain template-only during preflight")
    if claim.get("current_state", {}).get("substantive_entries") != 0:
        fail("public arsenal claim boundary must still report zero substantive entries")

    p4h = None
    p4h0 = None
    for node in tree.get("nodes", []):
        if isinstance(node, dict) and node.get("id") == "P4-2h":
            p4h = node
        if isinstance(node, dict) and node.get("id") == "P4-2h-0":
            p4h0 = node
    if p4h is None:
        fail("task tree missing P4-2h")
    if p4h.get("status") not in {"deferred", "in-progress", "completed"}:
        fail("P4-2h status must remain explicit")
    if p4h0 is None:
        fail("task tree missing P4-2h-0 preflight node")
    if p4h0.get("release_blocker") is not False:
        fail("P4-2h-0 must not be a default release blocker")

    source_count = 0
    for item in require_list(policy, "allowed_private_source_roots", "policy"):
        if not isinstance(item, dict):
            continue
        raw = str(item.get("path", ""))
        if not path_exists_for_source(root, raw):
            fail(f"allowed private source root missing: {raw}")
        source_count += count_source_files(root, raw)

    worktree = resolve_worktree(root, binding)
    public_count = substantive_public_entries(worktree)
    if public_count != 0:
        fail(f"preflight cannot run while redcap-arsenal has substantive entries: {public_count}")

    return source_count, public_count


def validate_no_public_raw_content(root: Path, policy: dict[str, Any]) -> None:
    binding = load_json(repo_path(root, policy["policy_links"]["remote_binding"]), "remote binding")
    worktree = resolve_worktree(root, binding)
    if worktree is None or not worktree.is_dir():
        return
    forbidden = [str(item) for item in require_list(policy, "forbidden_raw_public_sources", "policy")]
    for path in worktree.rglob("*"):
        if not path.is_file() or path.name == ".gitkeep":
            continue
        try:
            rel = path.relative_to(worktree).as_posix()
        except ValueError:
            continue
        if not rel.startswith("users/"):
            continue
        for pattern in forbidden:
            if glob_matches(pattern, rel):
                fail(f"public worktree contains forbidden raw source path: {rel}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate P4-2h-0 public distillation preflight.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    policy_path = Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = (Path.cwd() / policy_path).resolve()
    policy = load_json(policy_path, "public distillation preflight policy")

    validate_policy_shape(policy)
    source_count, public_count = validate_cross_policy(root, policy)
    validate_no_public_raw_content(root, policy)

    print("PUBLIC_DISTILLATION_PREFLIGHT_OK")
    print(f"private_source_files_seen={source_count}")
    print(f"public_substantive_entries={public_count}")
    print("mode=dry-run-only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
