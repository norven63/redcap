#!/usr/bin/env python3
"""验证 Cap 复活路径可迁移性，不读取真实私有身份正文。"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
RUNTIME_BIN = REPO_ROOT / "runtime" / "bin" / "redcap"
EVIDENCE_SOUL_DIR = REPO_ROOT / "assets" / "evidence" / "soul"
RSP_EVIDENCE = REPO_ROOT / "assets" / "evidence" / "rsp" / "rsp-16-cap-revival-portability.json"
RSP_CLAIM = REPO_ROOT / "assets" / "evidence" / "rsp" / "rsp-16-claim.json"
PUBLIC_SCAN_ROOTS = [
    REPO_ROOT / "assets" / "docs",
    REPO_ROOT / "assets" / "contracts",
    REPO_ROOT / "runtime",
    REPO_ROOT / "assets" / "evidence",
]


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def private_identity_path_marker() -> str:
    return "/" + "/".join(["Users", "norven", ".cap", "identity.md"])


def fixture_markers() -> dict[str, str]:
    prefix = "RSP16_"
    return {
        "title": prefix + "PRIVATE_TITLE_" + "SENTINEL",
        "body": prefix + "PRIVATE_BODY_" + "SENTINEL",
        "secret": prefix + "SECRET_" + "VALUE",
    }


def public_text_replacements() -> dict[str, str]:
    markers = fixture_markers()
    return {
        private_identity_path_marker(): "$CAP_HOME/identity.md",
        markers["title"]: "[REDACTED_PRIVATE_TITLE]",
        markers["body"]: "[REDACTED_PRIVATE_BODY]",
        markers["secret"]: "[REDACTED_SECRET_VALUE]",
    }


def forbidden_public_fragments() -> list[str]:
    return list(public_text_replacements().keys())


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def load_json(path: pathlib.Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON 必须是对象：{path}")
    return payload


def run_load(*, env: dict[str, str], evidence_dir: pathlib.Path) -> dict[str, Any]:
    completed = subprocess.run(
        [
            str(RUNTIME_BIN),
            "soul-load",
            "load",
            "--json",
            "--evidence-dir",
            str(evidence_dir),
        ],
        cwd=str(REPO_ROOT),
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    latest = evidence_dir / "latest-load.json"
    packet: dict[str, Any] | None = None
    if latest.exists():
        packet = load_json(latest)
    return {
        "exit_code": completed.returncode,
        "ok": completed.returncode == 0,
        "stdout_tail": (completed.stdout or "")[-1000:],
        "stderr_tail": (completed.stderr or "")[-1000:],
        "packet": packet,
    }


def fixture_env(*, home: pathlib.Path, cap_home: pathlib.Path | None) -> dict[str, str]:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(home),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", ""),
        "REDCAP_RSP16_PORTABILITY_PROBE": "1",
    }
    if cap_home is not None:
        env["CAP_HOME"] = str(cap_home)
    return {key: value for key, value in env.items() if value}


def private_source(packet: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(packet, dict):
        return {}
    sources = packet.get("sources")
    if not isinstance(sources, list):
        return {}
    for source in sources:
        if isinstance(source, dict) and source.get("id") == "cap_identity":
            return source
    return {}


def assert_private_source_sanitized(source: dict[str, Any], *, configured_path: str, expect_ok: bool) -> list[str]:
    failures: list[str] = []
    if expect_ok and source.get("exists") is not True:
        failures.append("身份源应存在")
    if expect_ok and source.get("readable") is not True:
        failures.append("身份源应可读")
    if source.get("configured_path") != configured_path:
        failures.append(f"configured_path 应为 {configured_path}")
    if source.get("resolved_path") != configured_path:
        failures.append("resolved_path 应保持为可迁移占位符")
    if source.get("resolved_path_redacted") is not True:
        failures.append("resolved_path_redacted 应为 true")
    if source.get("title") is not None:
        failures.append("私有身份标题正文不得写入证据")
    if expect_ok and source.get("title_present") is not True:
        failures.append("证据应只记录标题存在状态")
    return failures


def case_report(
    *,
    case_id: str,
    result: dict[str, Any],
    expected_ok: bool,
    configured_path: str,
) -> dict[str, Any]:
    source = private_source(result.get("packet"))
    failures: list[str] = []
    if result["ok"] is not expected_ok:
        failures.append(f"退出状态不符合预期：expected_ok={expected_ok}")
    failures.extend(
        assert_private_source_sanitized(
            source,
            configured_path=configured_path,
            expect_ok=expected_ok,
        )
    )
    if expected_ok and not source.get("sha256"):
        failures.append("正向身份源应记录哈希")
    return {
        "case_id": case_id,
        "ok": not failures,
        "expected_ok": expected_ok,
        "exit_code": result["exit_code"],
        "configured_path": configured_path,
        "private_source": {
            "configured_path": source.get("configured_path"),
            "resolved_path": source.get("resolved_path"),
            "resolved_path_redacted": source.get("resolved_path_redacted"),
            "exists": source.get("exists"),
            "readable": source.get("readable"),
            "sha256": source.get("sha256"),
            "line_count": source.get("line_count"),
            "char_count": source.get("char_count"),
            "title": source.get("title"),
            "title_present": source.get("title_present"),
        },
        "failures": failures,
    }


def text_leak_scan(paths: list[pathlib.Path], forbidden_fragments: list[str]) -> dict[str, Any]:
    hits: list[dict[str, str]] = []
    for root in paths:
        if not root.exists():
            continue
        files = [root] if root.is_file() else [item for item in root.rglob("*") if item.is_file()]
        for file_path in files:
            try:
                text = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for fragment in forbidden_fragments:
                if fragment and fragment in text:
                    hits.append({
                        "path": str(file_path.relative_to(REPO_ROOT)) if file_path.is_relative_to(REPO_ROOT) else str(file_path),
                        "fragment_sha256": sha256_text(fragment),
                    })
    return {
        "ok": not hits,
        "scanned_paths": [str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path) for path in paths],
        "forbidden_fragment_sha256s": [sha256_text(fragment) for fragment in forbidden_fragments if fragment],
        "hit_count": len(hits),
        "hits": hits,
    }


def sanitize_public_text_files(
    paths: list[pathlib.Path],
    replacements: dict[str, str],
    *,
    dry_run: bool,
) -> dict[str, Any]:
    changed_files: list[dict[str, Any]] = []
    scanned_files = 0
    for root in paths:
        if not root.exists():
            continue
        files = [root] if root.is_file() else [item for item in root.rglob("*") if item.is_file()]
        for file_path in files:
            try:
                original = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            scanned_files += 1
            updated = original
            counts: dict[str, int] = {}
            for fragment, replacement in replacements.items():
                count = updated.count(fragment)
                if count:
                    counts[sha256_text(fragment)] = count
                    updated = updated.replace(fragment, replacement)
            if updated == original:
                continue
            rel = str(file_path.relative_to(REPO_ROOT)) if file_path.is_relative_to(REPO_ROOT) else str(file_path)
            changed_files.append({
                "path": rel,
                "replacement_counts_by_fragment_sha256": counts,
                "original_sha256": sha256_text(original),
                "updated_sha256": sha256_text(updated),
            })
            if not dry_run:
                tmp = file_path.with_name(f".{file_path.name}.{os.getpid()}.redact.tmp")
                tmp.write_text(updated, encoding="utf-8")
                os.replace(tmp, file_path)
    post_scan = text_leak_scan(paths, list(replacements.keys()))
    return {
        "schema_id": "redcap-cap-revival-public-text-sanitize",
        "rsp": "RSP-16",
        "created_at": iso_now(),
        "dry_run": dry_run,
        "ok": bool(post_scan.get("ok")) if not dry_run else True,
        "scanned_file_count": scanned_files,
        "changed_file_count": len(changed_files),
        "changed_files": changed_files,
        "post_scan": post_scan,
        "replacement_policy": {
            "private_identity_path": "$CAP_HOME/identity.md",
            "fixture_private_markers": "redacted symbolic placeholders",
            "mode": "known-fragment replacement only; no broad content rewriting",
        },
    }


def structured_soul_evidence_scan() -> dict[str, Any]:
    failure_counts: dict[str, int] = {}
    checked_files: list[str] = []
    def add_failure(message: str) -> None:
        failure_counts[message] = failure_counts.get(message, 0) + 1

    if not EVIDENCE_SOUL_DIR.exists():
        return {"ok": True, "checked_files": checked_files, "failures": []}
    for path in EVIDENCE_SOUL_DIR.rglob("*"):
        if not path.is_file() or path.suffix not in {".json", ".jsonl"}:
            continue
        checked_files.append(str(path.relative_to(REPO_ROOT)))
        lines = path.read_text(encoding="utf-8").splitlines()
        payloads: list[dict[str, Any]] = []
        if path.suffix == ".json":
            payloads.append(load_json(path))
        else:
            for index, line in enumerate(lines, start=1):
                if not line.strip():
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError as exc:
                    add_failure(f"{path.relative_to(REPO_ROOT)} JSONL 解析失败：{exc}")
                    continue
                if isinstance(parsed, dict):
                    payloads.append(parsed)
        for payload in payloads:
            source = private_source(payload)
            if not source:
                continue
            if source.get("resolved_path_redacted") is not True:
                add_failure(f"{path.relative_to(REPO_ROOT)} 私有身份 resolved_path 未脱敏")
            if source.get("resolved_path") not in {"$CAP_HOME/identity.md", "~/.cap/identity.md"}:
                add_failure(f"{path.relative_to(REPO_ROOT)} 私有身份 resolved_path 不是可迁移占位符")
            if source.get("title") is not None:
                add_failure(f"{path.relative_to(REPO_ROOT)} 私有身份标题正文未脱敏")
    failures = [
        f"{message}（{count} 条）" if count > 1 else message
        for message, count in sorted(failure_counts.items())
    ]
    return {
        "ok": not failures,
        "checked_files": checked_files,
        "rules": [
            "cap_identity.resolved_path_redacted 必须为 true",
            "cap_identity.resolved_path 必须是 $CAP_HOME/identity.md 或 ~/.cap/identity.md",
            "cap_identity.title 必须为 null，只允许 title_present",
        ],
        "failures": failures,
    }


def build_report(out_path: pathlib.Path | None) -> dict[str, Any]:
    markers = fixture_markers()
    body = (
        f"# {markers['title']}\n\n"
        f"{markers['body']}\n"
        f"{markers['secret']}=should-not-enter-evidence\n"
    )
    failures: list[str] = []
    cases: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="redcap-rsp16-portability-") as raw:
        root = pathlib.Path(raw)

        env_home = root / "env-home"
        cap_home = root / "cap-home"
        cap_home.mkdir(parents=True)
        (cap_home / "identity.md").write_text(body, encoding="utf-8")
        cases.append(
            case_report(
                case_id="cap_home_valid",
                result=run_load(env=fixture_env(home=env_home, cap_home=cap_home), evidence_dir=root / "evidence-env"),
                expected_ok=True,
                configured_path="$CAP_HOME/identity.md",
            )
        )

        fallback_home = root / "fallback-home"
        fallback_identity = fallback_home / ".cap" / "identity.md"
        fallback_identity.parent.mkdir(parents=True)
        fallback_identity.write_text(body, encoding="utf-8")
        cases.append(
            case_report(
                case_id="fallback_home_valid",
                result=run_load(env=fixture_env(home=fallback_home, cap_home=None), evidence_dir=root / "evidence-fallback"),
                expected_ok=True,
                configured_path="~/.cap/identity.md",
            )
        )

        cases.append(
            case_report(
                case_id="missing_cap_home",
                result=run_load(env=fixture_env(home=root / "missing-home", cap_home=root / "missing-cap-home"), evidence_dir=root / "evidence-missing-cap-home"),
                expected_ok=False,
                configured_path="$CAP_HOME/identity.md",
            )
        )

        missing_identity_home = root / "missing-identity-home"
        missing_identity_home.mkdir()
        cases.append(
            case_report(
                case_id="cap_home_without_identity",
                result=run_load(env=fixture_env(home=root / "home-without-identity", cap_home=missing_identity_home), evidence_dir=root / "evidence-missing-identity"),
                expected_ok=False,
                configured_path="$CAP_HOME/identity.md",
            )
        )

        empty_home = root / "empty-home"
        empty_home.mkdir()
        (empty_home / "identity.md").write_text("", encoding="utf-8")
        cases.append(
            case_report(
                case_id="empty_identity",
                result=run_load(env=fixture_env(home=root / "empty-env-home", cap_home=empty_home), evidence_dir=root / "evidence-empty"),
                expected_ok=False,
                configured_path="$CAP_HOME/identity.md",
            )
        )

        file_home = root / "cap-home-is-file"
        file_home.write_text("not a directory\n", encoding="utf-8")
        cases.append(
            case_report(
                case_id="cap_home_is_file",
                result=run_load(env=fixture_env(home=root / "file-home", cap_home=file_home), evidence_dir=root / "evidence-file-home"),
                expected_ok=False,
                configured_path="$CAP_HOME/identity.md",
            )
        )

        unreadable_home = root / "unreadable-home"
        unreadable_home.mkdir()
        unreadable_identity = unreadable_home / "identity.md"
        unreadable_identity.write_text(body, encoding="utf-8")
        unreadable_identity.chmod(0)
        try:
            cases.append(
                case_report(
                    case_id="unreadable_identity",
                    result=run_load(env=fixture_env(home=root / "unreadable-env-home", cap_home=unreadable_home), evidence_dir=root / "evidence-unreadable"),
                    expected_ok=False,
                    configured_path="$CAP_HOME/identity.md",
                )
            )
        finally:
            unreadable_identity.chmod(0o600)

        fixture_scan = text_leak_scan(
            [root],
            [markers["body"], markers["secret"], markers["title"]],
        )
        # 夹具目录本身包含身份源正文；只允许身份源文件命中，证据文件不能命中。
        fixture_hits_outside_identity = [
            hit for hit in fixture_scan["hits"]
            if not hit["path"].endswith("identity.md")
        ]
        fixture_evidence_scan = {
            **fixture_scan,
            "ok": not fixture_hits_outside_identity,
            "hits": fixture_hits_outside_identity,
            "hit_count": len(fixture_hits_outside_identity),
        }

    public_text_scan = text_leak_scan(
        PUBLIC_SCAN_ROOTS,
        forbidden_public_fragments(),
    )
    public_structured_scan = structured_soul_evidence_scan()

    for item in cases:
        if not item["ok"]:
            failures.append(f"{item['case_id']}: {'; '.join(item['failures'])}")
    if not fixture_evidence_scan["ok"]:
        failures.append("夹具私有正文进入临时证据")
    if not public_text_scan["ok"]:
        failures.append("公共可见文本仍含私有身份路径或夹具私有正文标记")
    if not public_structured_scan["ok"]:
        failures.extend(public_structured_scan["failures"])

    report = {
        "schema_id": "redcap-cap-revival-portability",
        "rsp": "RSP-16",
        "created_at": iso_now(),
        "ok": not failures,
        "scope": {
            "fixture_only": True,
            "real_private_identity_opened": False,
            "real_private_identity_copied": False,
            "real_private_identity_migrated": False,
            "public_evidence_body_allowed": False,
        },
        "changed_reality": [
            "Cap 身份加载证据不再写入真实私有身份绝对路径。",
            "Cap 身份加载证据不再写入真实私有标题正文。",
            "迁移验证仅使用临时夹具身份源，并覆盖 CAP_HOME、默认 ~/.cap、缺失、空文件、不可读和路径错误场景。",
        ],
        "acceptance": {
            "positive": {
                "status": "pass" if all(item["ok"] for item in cases[:2]) else "fail",
                "checks": [
                    "CAP_HOME 指向临时身份源时可加载，且公共证据只写占位符路径和标题存在状态。",
                    "CAP_HOME 缺失时可回退到 HOME 下的 .cap/identity.md，且公共证据只写占位符路径和标题存在状态。",
                ],
                "cases": [item for item in cases if item["expected_ok"]],
            },
            "negative": {
                "status": "pass" if all(item["ok"] for item in cases[2:]) else "fail",
                "checks": [
                    "CAP_HOME 缺失、缺少 identity.md、identity.md 为空、CAP_HOME 是普通文件、identity.md 不可读时均被阻断。",
                    "夹具私有正文、疑似密钥和标题正文不得进入临时证据。",
                    "公共 soul evidence 不得保留真实私有身份绝对路径或真实私有标题正文。",
                ],
                "cases": [item for item in cases if not item["expected_ok"]],
            },
            "fixture_evidence_leak_scan": fixture_evidence_scan,
            "public_text_scan": public_text_scan,
            "public_structured_scan": public_structured_scan,
        },
        "artifacts": [
            "assets/contracts/cap-revival-portability.json",
            "runtime/core/soul_loader.py",
            "runtime/core/cap_revival_portability.py",
            "runtime/bin/redcap soul-load portability-check",
            "runtime/bin/redcap check --only soul-load-portability-check",
            str(out_path.relative_to(REPO_ROOT)) if out_path else "assets/evidence/rsp/rsp-16-cap-revival-portability.json",
        ],
        "failures": failures,
    }
    return report


def cmd_portability_check(args: argparse.Namespace) -> int:
    out_path = pathlib.Path(args.out).resolve() if args.out else None
    if args.sanitize_public_leaks:
        report = sanitize_public_text_files(
            PUBLIC_SCAN_ROOTS,
            public_text_replacements(),
            dry_run=bool(args.dry_run),
        )
    elif args.public_leak_scan:
        report = {
            "schema_id": "redcap-cap-revival-public-leak-scan",
            "rsp": "RSP-16",
            "created_at": iso_now(),
            "ok": True,
            "scan": text_leak_scan(
                PUBLIC_SCAN_ROOTS,
                forbidden_public_fragments(),
            ),
        }
        report["ok"] = bool(report["scan"].get("ok"))
    else:
        report = build_report(out_path)
    if out_path is not None:
        write_json(out_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if report["ok"]:
        print("REDCAP_CAP_REVIVAL_PORTABILITY_OK")
        return 0
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RedCap Cap 复活迁移与路径边界验证")
    parser.add_argument("--out")
    parser.add_argument("--public-leak-scan", action="store_true")
    parser.add_argument("--sanitize-public-leaks", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.set_defaults(func=cmd_portability_check)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
