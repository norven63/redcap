#!/usr/bin/env python3
"""Validate RedCap skill lifecycle and host thin-entry policy.

Dictionary: references/file-lookup-dictionary.md#skill-and-host-distribution
"""
from __future__ import annotations

import json
import pathlib
import sys


def fail(message: str) -> None:
    raise SystemExit(f"[redcap-skill-lifecycle-check] {message}")


def load_json(path: pathlib.Path) -> dict:
    if not path.is_file():
        fail(f"missing policy: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid policy json: {exc}")


def resolve(root: pathlib.Path, rel_path: str) -> pathlib.Path:
    path = pathlib.Path(rel_path)
    return path if path.is_absolute() else root / path


def assert_path_exists(root: pathlib.Path, rel_path: str, label: str) -> None:
    if not rel_path or not isinstance(rel_path, str):
        fail(f"{label} path must be a non-empty string")
    if not resolve(root, rel_path).exists():
        fail(f"{label} path does not exist: {rel_path}")


def main() -> None:
    if len(sys.argv) != 3:
        fail("usage: redcap-skill-lifecycle-check.py <redcap_root> <policy_path>")

    root = pathlib.Path(sys.argv[1]).resolve()
    policy_arg = pathlib.Path(sys.argv[2])
    policy_path = policy_arg if policy_arg.is_absolute() else root / policy_arg
    policy = load_json(policy_path)

    if policy.get("version") != 1:
        fail("policy version must be 1")

    source = policy.get("source_of_truth")
    if not isinstance(source, dict) or not source:
        fail("source_of_truth must be a non-empty object")
    for key, rel_path in source.items():
        assert_path_exists(root, rel_path, f"source_of_truth.{key}")

    layers = policy.get("capability_layers")
    if not isinstance(layers, list) or not layers:
        fail("capability_layers must be a non-empty list")
    required_layers = {"redcap-native-capability", "host-exported-skill", "portable-skill-package"}
    seen_layers: set[str] = set()
    for layer in layers:
        if not isinstance(layer, dict):
            fail("capability layer entries must be objects")
        layer_id = layer.get("id")
        if layer_id in seen_layers:
            fail(f"duplicate capability layer: {layer_id}")
        seen_layers.add(layer_id)
        authority = layer.get("authority")
        if not isinstance(authority, str) or len(authority.strip()) < 20:
            fail(f"{layer_id}: authority must be meaningful")
        paths = layer.get("source_paths")
        if not isinstance(paths, list) or not paths:
            fail(f"{layer_id}: source_paths must be non-empty")
        for rel_path in paths:
            assert_path_exists(root, rel_path, f"{layer_id}.source_paths")
    missing_layers = sorted(required_layers - seen_layers)
    if missing_layers:
        fail("missing required capability layers: " + ", ".join(missing_layers))

    lifecycle_states = policy.get("lifecycle_states")
    required_states = {
        "proposed",
        "designed",
        "implemented",
        "installed",
        "verified",
        "published",
        "deprecated",
        "rolled-back",
        "retired",
    }
    if not isinstance(lifecycle_states, list):
        fail("lifecycle_states must be a list")
    missing_states = sorted(required_states - {state for state in lifecycle_states if isinstance(state, str)})
    if missing_states:
        fail("missing lifecycle states: " + ", ".join(missing_states))

    required_controls = policy.get("required_controls")
    required_control_keys = {"create", "version", "install", "invoke", "test", "rollback", "deprecate", "repair"}
    if not isinstance(required_controls, dict):
        fail("required_controls must be an object")
    missing_controls = sorted(required_control_keys - set(required_controls.keys()))
    if missing_controls:
        fail("missing required controls: " + ", ".join(missing_controls))
    for key in required_control_keys:
        values = required_controls.get(key)
        if not isinstance(values, list) or not values:
            fail(f"required_controls.{key} must be a non-empty list")
        for value in values:
            if not isinstance(value, str) or len(value.strip()) < 20:
                fail(f"required_controls.{key} items must be meaningful")

    entries = policy.get("host_entries")
    if not isinstance(entries, list) or not entries:
        fail("host_entries must be a non-empty list")
    required_hosts = {"codex", "claude-code", "gemini-cli", "copilot-cli"}
    seen_hosts: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            fail("host entry must be an object")
        host = entry.get("host")
        if not isinstance(host, str) or not host.strip():
            fail("host entry missing host")
        if host in seen_hosts:
            fail(f"duplicate host entry: {host}")
        seen_hosts.add(host)
        entry_path = entry.get("entry_path")
        assert_path_exists(root, entry_path, f"{host}.entry_path")
        content = resolve(root, entry_path).read_text(encoding="utf-8")
        if entry.get("mode") != "thin-index":
            fail(f"{host}: mode must remain thin-index")
        for needle in entry.get("must_include", []):
            if not isinstance(needle, str) or needle not in content:
                fail(f"{host}: entry missing required anchor: {needle}")
        for needle in entry.get("must_not_include", []):
            if not isinstance(needle, str):
                fail(f"{host}: invalid forbidden anchor")
            direct_import = any(line.strip() == needle or line.strip().startswith(needle + " ") for line in content.splitlines())
            if direct_import:
                fail(f"{host}: entry directly imports forbidden large anchor: {needle}")
    missing_hosts = sorted(required_hosts - seen_hosts)
    if missing_hosts:
        fail("missing required host entries: " + ", ".join(missing_hosts))

    rules = policy.get("rules")
    if not isinstance(rules, list) or len(rules) < 3:
        fail("rules must contain at least three lifecycle constraints")
    for rule in rules:
        if not isinstance(rule, str) or len(rule.strip()) < 20:
            fail("skill lifecycle rules must be meaningful")

    print("SKILL_LIFECYCLE_POLICY")
    print(f"layers={len(layers)} hosts={len(entries)}")
    print("source=single")
    print("SKILL_LIFECYCLE_OK")


if __name__ == "__main__":
    main()
