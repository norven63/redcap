from __future__ import annotations

import contextlib
import json
import os
import pathlib
import random
import time
from collections.abc import Iterator
from typing import Any


class PrismLockError(RuntimeError):
    pass


def _utc_stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_owner_pid(lock_path: pathlib.Path) -> int | None:
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    pid = payload.get("pid")
    if isinstance(pid, int) and pid > 0:
        return pid
    return None


def _prune_stale_lock(lock_path: pathlib.Path) -> bool:
    if not lock_path.exists():
        return True
    owner_pid = _read_owner_pid(lock_path)
    if owner_pid is not None and _pid_is_alive(owner_pid):
        return False
    try:
        lock_path.unlink()
    except FileNotFoundError:
        return True
    return True


@contextlib.contextmanager
def file_lock(target_path: pathlib.Path, *, attempts: int = 200, delay: float = 0.05) -> Iterator[None]:
    target = pathlib.Path(target_path)
    lock_dir = target.parent / ".locks"
    lock_path = lock_dir / f"{target.name}.lock"
    lock_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(lock_dir, 0o700)
    except OSError:
        pass

    owner = {
        "pid": os.getpid(),
        "created_at": _utc_stamp(),
        "target": str(target),
        "nonce": random.randint(1, 2**31 - 1),
    }
    owner_text = json.dumps(owner, ensure_ascii=False, sort_keys=True) + "\n"
    lock_tmp = lock_dir / f".{target.name}.{owner['pid']}.{owner['nonce']}.tmp"
    lock_tmp.write_text(owner_text, encoding="utf-8")
    try:
        os.chmod(lock_tmp, 0o600)
    except OSError:
        pass

    acquired = False
    try:
        for _ in range(attempts):
            try:
                os.link(lock_tmp, lock_path)
                acquired = True
                break
            except FileExistsError:
                _prune_stale_lock(lock_path)
                time.sleep(delay)
        if not acquired:
            raise PrismLockError(f"could not acquire lock: {lock_path}")
        yield
    finally:
        try:
            lock_tmp.unlink()
        except FileNotFoundError:
            pass
        if acquired:
            try:
                if lock_path.read_text(encoding="utf-8") == owner_text:
                    lock_path.unlink()
            except FileNotFoundError:
                pass


def write_text_atomic(path: pathlib.Path, text: str) -> None:
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.parent / f".{target.name}.{os.getpid()}.{time.time_ns()}.tmp"
    try:
        with tmp.open("w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def write_json_atomic(path: pathlib.Path, payload: Any) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with file_lock(path):
        write_text_atomic(path, text)
