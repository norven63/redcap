#!/usr/bin/env python3
"""RedCap E2E external observer.

This script is intentionally separate from the E2E runner. The harness invokes it
as a sibling process of the runner-worker so final evidence is not produced by
the same process that decides completion.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import socket
import subprocess
import sys
import time
import urllib.request
from typing import Any


OBSERVER_BROWSER_VIEWPORT = {"width": 1032, "height": 760}
ENTRYPOINT_CANDIDATES = ["index.html", "public/index.html", "dist/index.html", "build/index.html"]


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: pathlib.Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON must be an object: {path}")
    return payload


def bundle_declared_hash_input(bundle: dict[str, Any]) -> dict[str, Any]:
    payload = dict(bundle)
    payload.pop("bundle_sha256", None)
    return payload


def seconds_between(start_iso: str | None, end_iso: str | None) -> float | None:
    if not start_iso or not end_iso:
        return None
    try:
        start = dt.datetime.fromisoformat(start_iso)
        end = dt.datetime.fromisoformat(end_iso)
    except ValueError:
        return None
    return round((end - start).total_seconds(), 3)


def write_json_locked(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    seal_input = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    payload["observer_seal"] = {
        "algorithm": "sha256",
        "payload_sha256_without_seal": sha256_text(seal_input),
        "sealed_at": iso_now(),
        "intended_mode": "0444",
    }
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    path.chmod(0o444)


def run_command(argv: list[str], *, cwd: pathlib.Path, timeout_seconds: int = 30) -> dict[str, Any]:
    try:
        completed = subprocess.run(argv, cwd=str(cwd), text=True, capture_output=True, timeout=timeout_seconds, check=False)
        return {
            "argv": argv,
            "cwd": str(cwd),
            "exit_code": completed.returncode,
            "ok": completed.returncode == 0,
            "stdout_tail": completed.stdout[-2000:],
            "stderr_tail": completed.stderr[-2000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "argv": argv,
            "cwd": str(cwd),
            "exit_code": None,
            "ok": False,
            "timed_out": True,
            "stdout_tail": (exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-2000:] if isinstance(exc.stderr, str) else "",
        }


def ppid_of(pid: int) -> int | None:
    result = run_command(["ps", "-o", "ppid=", "-p", str(pid)], cwd=pathlib.Path.cwd(), timeout_seconds=5)
    if not result["ok"]:
        return None
    text = str(result.get("stdout_tail") or "").strip()
    if not text:
        return None
    try:
        return int(text.splitlines()[-1].strip())
    except ValueError:
        return None


def process_chain(pid: int, limit: int = 12) -> list[int]:
    chain: list[int] = []
    current = pid
    seen: set[int] = set()
    for _ in range(limit):
        if current <= 0 or current in seen:
            break
        chain.append(current)
        seen.add(current)
        parent = ppid_of(current)
        if parent is None:
            break
        current = parent
    return chain


def collect_versions(project: pathlib.Path) -> dict[str, Any]:
    return {
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "node": run_command(["node", "--version"], cwd=project, timeout_seconds=10),
        "npm": run_command(["npm", "--version"], cwd=project, timeout_seconds=10),
    }


def bundle_hash_map(bundle: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    deliverables = bundle.get("deliverables")
    if isinstance(deliverables, dict):
        for item in deliverables.get("files", []) if isinstance(deliverables.get("files"), list) else []:
            if isinstance(item, dict) and isinstance(item.get("path"), str) and isinstance(item.get("sha256"), str):
                result[item["path"]] = item["sha256"]
    files = bundle.get("files")
    if isinstance(files, list):
        for item in files:
            if isinstance(item, dict) and isinstance(item.get("path"), str) and isinstance(item.get("sha256"), str):
                result.setdefault(item["path"], item["sha256"])
    return result


def inspect_deliverables(project: pathlib.Path, bundle: dict[str, Any]) -> dict[str, Any]:
    candidates = [
        "README.md",
        "index.html",
        "app.js",
        "styles.css",
        "public/index.html",
        "public/app.js",
        "public/styles.css",
        "architecture.md",
        "risk-register.json",
        "data/events.json",
        "scripts/validate.mjs",
        "scripts/validate-data.mjs",
        "scripts/validate-data.js",
    ]
    expected = bundle_hash_map(bundle)
    records: list[dict[str, Any]] = []
    failures: list[str] = []
    for rel in candidates:
        path = project / rel
        record: dict[str, Any] = {"path": rel, "exists": path.exists()}
        if path.exists() and path.is_file():
            digest = sha256_file(path)
            record.update({"sha256": digest, "size": path.stat().st_size})
            if rel in expected:
                record["bundle_sha256"] = expected[rel]
                record["matches_bundle"] = expected[rel] == digest
                if expected[rel] != digest:
                    failures.append(f"关键交付文件哈希不匹配：{rel}")
            else:
                record["matches_bundle"] = None
        elif rel in expected:
            failures.append(f"final-evidence-bundle 声称存在但观察者未找到：{rel}")
        records.append(record)
    return {"files": records, "failures": failures}


def detect_browser_entrypoint(project: pathlib.Path) -> tuple[pathlib.Path | None, str | None, list[str]]:
    checked: list[str] = []
    for rel in ENTRYPOINT_CANDIDATES:
        checked.append(rel)
        path = project / rel
        if path.is_file():
            return path, rel, checked
    return None, None, checked


def dom_summary(page: Any) -> dict[str, Any]:
    snapshot = page.evaluate(
        """() => {
            const textOf = (el) => String(el.innerText || el.textContent || "").replace(/\\s+/g, " ").trim();
            const elements = Array.from(document.querySelectorAll("main, section, article, li, tr, button, [role='button'], [data-testid], .card, .event, .session"))
                .slice(0, 120)
                .map((el) => ({
                    tag: el.tagName.toLowerCase(),
                    id: el.id || "",
                    className: typeof el.className === "string" ? el.className : "",
                    role: el.getAttribute("role"),
                    text: textOf(el).slice(0, 220)
                }));
            return {
                title: document.title || "",
                bodyText: textOf(document.body).slice(0, 2000),
                bodyTextLength: textOf(document.body).length,
                elements
            };
        }"""
    )
    text = str(snapshot.get("bodyText") or "")
    elements = snapshot.get("elements") if isinstance(snapshot.get("elements"), list) else []
    return {
        "title": snapshot.get("title"),
        "visible_text_excerpt": text,
        "visible_text_length": snapshot.get("bodyTextLength"),
        "visible_text_sha256": sha256_text(text),
        "element_count_sampled": len(elements),
        "elements": elements[:40],
        "elements_sha256": sha256_text(json.dumps(elements, ensure_ascii=False, sort_keys=True)),
    }


def run_browser_observation(project: pathlib.Path, output_png: pathlib.Path) -> dict[str, Any]:
    target, target_rel, checked_entrypoints = detect_browser_entrypoint(project)
    result: dict[str, Any] = {
        "target": str(target) if target is not None else None,
        "target_relative_path": target_rel,
        "checked_entrypoints": checked_entrypoints,
        "ok": False,
        "checks": [],
        "failures": [],
        "screenshot": output_png.name,
    }
    if target is None or target_rel is None:
        result["failures"].append(f"缺少浏览器入口文件，已检查：{checked_entrypoints}")
        return result
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        result["failures"].append(f"无法导入 Playwright: {type(exc).__name__}: {exc}")
        return result
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])
    url = f"http://127.0.0.1:{port}/{target_rel}"
    server = subprocess.Popen(
        ["python3", "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=str(project),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    console_errors: list[str] = []
    page_errors: list[str] = []
    try:
        ready = False
        last_error = ""
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if server.poll() is not None:
                last_error = f"server exited: {server.returncode}"
                break
            try:
                with urllib.request.urlopen(url, timeout=0.5) as response:
                    ready = response.status < 500
                    if ready:
                        break
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                time.sleep(0.1)
        result["url"] = url
        result["server_ready"] = ready
        result["server_last_error"] = last_error
        if not ready:
            result["failures"].append(f"HTTP 服务未就绪：{last_error}")
            return result
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            browser_version = browser.version
            page = browser.new_page(viewport=OBSERVER_BROWSER_VIEWPORT)
            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto(url, wait_until="domcontentloaded", timeout=20_000)
            page.wait_for_timeout(500)
            before = dom_summary(page)
            clicked = None
            buttons = page.locator("button, [role='button']")
            for index in range(min(buttons.count(), 8)):
                button = buttons.nth(index)
                label = button.inner_text(timeout=2_000).strip()
                if not label:
                    continue
                try:
                    before_hash = dom_summary(page)["elements_sha256"]
                    button.click(timeout=5_000)
                    page.wait_for_timeout(400)
                    after_hash = dom_summary(page)["elements_sha256"]
                    if before_hash != after_hash:
                        clicked = label[:120]
                        break
                except Exception:
                    continue
            after = dom_summary(page)
            page.screenshot(path=str(output_png), full_page=True)
            browser.close()
        screenshot_record = {
            "path": output_png.name,
            "exists": output_png.exists(),
            "size": output_png.stat().st_size if output_png.exists() else 0,
            "sha256": sha256_file(output_png) if output_png.exists() else None,
        }
        checks = [
            {"name": "visible_text", "passed": int(before.get("visible_text_length") or 0) >= 80},
            {"name": "dom_summary", "passed": int(before.get("element_count_sampled") or 0) > 0},
            {"name": "screenshot_written", "passed": screenshot_record["exists"] and screenshot_record["size"] > 0},
            {"name": "no_browser_errors", "passed": not console_errors and not page_errors},
        ]
        result.update({
            "browser_version": browser_version,
            "browser_context": {
                "process_pid": os.getpid(),
                "browser_version": browser_version,
                "viewport": OBSERVER_BROWSER_VIEWPORT,
                "server_port": port,
                "capture_role": "independent-observer",
                "screenshot_phase": "after_interaction" if clicked else "after_static_observation",
            },
            "clicked_button": clicked,
            "before": before,
            "after": after,
            "screenshot_record": screenshot_record,
            "console_errors": console_errors,
            "page_errors": page_errors,
            "checks": checks,
        })
        result["failures"].extend(f"观察者浏览器检查失败：{item['name']}" for item in checks if item.get("passed") is not True)
        result["ok"] = not result["failures"]
        return result
    finally:
        try:
            os.killpg(os.getpgid(server.pid), 15)
            server.wait(timeout=2)
        except Exception:
            try:
                os.killpg(os.getpgid(server.pid), 9)
            except Exception:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description="RedCap E2E independent observer")
    parser.add_argument("--project", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--runner-pid", required=True, type=int)
    parser.add_argument("--harness-pid", required=True, type=int)
    args = parser.parse_args()

    project = pathlib.Path(args.project).resolve()
    evidence = pathlib.Path(args.evidence).resolve()
    bundle_path = pathlib.Path(args.bundle).resolve()
    output = pathlib.Path(args.output).resolve()
    screenshot = output.with_name("independent-observer.png")
    script_path = pathlib.Path(__file__).resolve()
    failures: list[str] = []
    try:
        bundle = load_json(bundle_path)
    except Exception as exc:
        bundle = {}
        failures.append(f"无法读取 final-evidence-bundle：{type(exc).__name__}: {exc}")
    first_observed_at = iso_now()
    first_observed_monotonic = time.monotonic()
    bundle_file_sha256 = sha256_file(bundle_path) if bundle_path.exists() else None
    declared_bundle_sha256 = bundle.get("bundle_sha256") if isinstance(bundle, dict) else None
    computed_bundle_sha256 = (
        sha256_text(json.dumps(bundle_declared_hash_input(bundle), ensure_ascii=False, sort_keys=True))
        if isinstance(bundle, dict)
        else None
    )
    time.sleep(2)
    cooldown_seconds = round(time.monotonic() - first_observed_monotonic, 3)
    cooldown_file_sha256 = sha256_file(bundle_path) if bundle_path.exists() else None
    bundle_fingerprint = {
        "path": str(bundle_path),
        "file_sha256": bundle_file_sha256,
        "declared_bundle_sha256": declared_bundle_sha256,
        "computed_bundle_sha256": computed_bundle_sha256,
        "matches_declared_bundle_sha256": bool(declared_bundle_sha256) and computed_bundle_sha256 == declared_bundle_sha256,
        "observer_first_read_at": first_observed_at,
        "bundle_created_at": bundle.get("created_at") if isinstance(bundle, dict) else None,
        "freeze_to_observer_seconds": seconds_between(bundle.get("created_at") if isinstance(bundle, dict) else None, first_observed_at),
        "cooldown_seconds": cooldown_seconds,
        "cooldown_file_sha256": cooldown_file_sha256,
        "file_sha256_stable_after_cooldown": bool(bundle_file_sha256) and bundle_file_sha256 == cooldown_file_sha256,
    }
    if not bundle_fingerprint["matches_declared_bundle_sha256"]:
        failures.append("观察者独立计算的 final-evidence-bundle 正文哈希与 bundle_sha256 声明不一致")
    if not bundle_fingerprint["file_sha256_stable_after_cooldown"]:
        failures.append("观察者冷却后复核发现 final-evidence-bundle.json 文件哈希发生变化")
    chain = process_chain(os.getpid())
    deliverables = inspect_deliverables(project, bundle)
    failures.extend(deliverables["failures"])
    browser = run_browser_observation(project, screenshot)
    if browser.get("ok") is not True:
        failures.extend(str(item) for item in browser.get("failures", []))
    output_parent_matches_harness = os.getppid() == args.harness_pid
    runner_not_parent = os.getppid() != args.runner_pid
    if not output_parent_matches_harness:
        failures.append("观察者父进程不是 harness，独立性证据不足")
    if not runner_not_parent:
        failures.append("观察者父进程是 runner-worker，违反兄弟进程约束")
    payload = {
        "schema_id": "redcap-e2e-independent-observer",
        "producer": "e2e-independent-observer-script",
        "created_at": iso_now(),
        "ok": not failures,
        "project": str(project),
        "evidence": str(evidence),
        "bundle": str(bundle_path),
        "script": {
            "path": str(script_path),
            "sha256": sha256_file(script_path),
            "mode": oct(script_path.stat().st_mode & 0o777),
        },
        "process": {
            "pid": os.getpid(),
            "ppid": os.getppid(),
            "runner_pid": args.runner_pid,
            "harness_pid": args.harness_pid,
            "ppid_chain": chain,
            "parent_is_harness": output_parent_matches_harness,
            "parent_is_not_runner": runner_not_parent,
            "executable": sys.executable,
            "argv": sys.argv,
            "cwd": str(pathlib.Path.cwd()),
        },
        "environment_allowlist": {
            "PATH_sha256": sha256_text(os.environ.get("PATH", "")),
            "PYTHONPATH_present": "PYTHONPATH" in os.environ,
            "REDCAP_E2E_WORKER_present": "REDCAP_E2E_WORKER" in os.environ,
            "REDCAP_E2E_OBSERVER_BY_HARNESS": os.environ.get("REDCAP_E2E_OBSERVER_BY_HARNESS"),
        },
        "versions": collect_versions(project),
        "bundle_fingerprint": bundle_fingerprint,
        "deliverable_hashes": deliverables,
        "browser_observation": browser,
        "failures": failures,
    }
    write_json_locked(output, payload)
    print(json.dumps({"ok": payload["ok"], "output": str(output), "failures": failures}, ensure_ascii=False))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
