#!/usr/bin/env python3
# 用途：发布前 E2E 矩阵脚本；详细职责见文件查阅字典。
# Dictionary: references/file-lookup-dictionary.md#package-publish-safety

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "references/release-readiness-e2e-matrix.json"


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-release-e2e-matrix-check] {message}")


def main() -> int:
    try:
        payload = json.loads(MATRIX.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid matrix json: {exc}")
    if payload.get("version") != 1 or payload.get("matrix_id") != "redcap-release-readiness-e2e-matrix":
        fail("matrix identity mismatch")
    environments = payload.get("environments")
    if not isinstance(environments, list) or len(environments) < 4:
        fail("matrix must cover source, clean install, npm pack, and external machine")
    ids = {item.get("id") for item in environments if isinstance(item, dict)}
    required_ids = {"source-worktree-self-development", "clean-workspace-local-install", "npm-pack-dry-run", "multi-os-external-machine"}
    if ids != required_ids:
        fail(f"environment set mismatch: {ids}")
    for item in environments:
        if not isinstance(item, dict):
            fail("environment entries must be objects")
        if item.get("status") not in {"covered", "deferred-to-formal-release-task"}:
            fail(f"{item.get('id')}: invalid status")
        checks = item.get("required_checks")
        if not isinstance(checks, list) or not checks:
            fail(f"{item.get('id')}: required_checks missing")
    boundaries = " ".join(str(item) for item in payload.get("manual_release_boundaries", []))
    for phrase in ["License selection", "npm credentials", "private=false", "publish_allowed=true", "npm publish"]:
        if phrase not in boundaries:
            fail(f"manual_release_boundaries missing: {phrase}")
    handoff = (ROOT / "references/public-release-handoff.md").read_text(encoding="utf-8", errors="replace")
    if "release-readiness-e2e-matrix" not in handoff:
        fail("public release handoff must mention release-readiness-e2e-matrix")
    print("RELEASE_E2E_MATRIX_OK")
    print(f"environments={len(environments)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
