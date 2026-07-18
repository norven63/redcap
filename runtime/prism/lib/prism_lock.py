from __future__ import annotations

import contextlib
import errno
import json
import os
import pathlib
import time
from collections.abc import Iterator
from typing import Any

if os.name == "nt":
    import msvcrt
else:
    import fcntl


class PrismLockError(RuntimeError):
    pass


def _utc_stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _try_kernel_lock(fd: int) -> bool:
    try:
        if os.name == "nt":
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        if exc.errno in {errno.EACCES, errno.EAGAIN}:
            return False
        raise
    return True


def _release_kernel_lock(fd: int) -> None:
    if os.name == "nt":
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)


def _write_locked_owner(fd: int, owner_text: str) -> None:
    payload = owner_text.encode("utf-8")
    os.lseek(fd, 0, os.SEEK_SET)
    written = 0
    while written < len(payload):
        chunk_size = os.write(fd, payload[written:])
        if chunk_size <= 0:
            raise OSError("could not persist lock owner metadata")
        written += chunk_size
    os.ftruncate(fd, len(payload))
    os.fsync(fd)


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

    # The stable inode is intentionally reused across acquisitions. Unlinking a
    # lock file while another process may hold it would allow a second inode and
    # therefore two independent exclusive locks. Cleanup may remove the parent
    # run directory only after its processes have exited.
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        os.chmod(lock_path, 0o600)
    except OSError:
        pass
    if os.name == "nt" and os.fstat(fd).st_size == 0:
        os.write(fd, b"\0")
        os.fsync(fd)

    acquired = False
    try:
        for _ in range(attempts):
            if _try_kernel_lock(fd):
                acquired = True
                break
            time.sleep(delay)
        if not acquired:
            raise PrismLockError(f"could not acquire lock: {lock_path}")
        owner = {
            "pid": os.getpid(),
            "created_at": _utc_stamp(),
            "target": str(target),
        }
        owner_text = json.dumps(owner, ensure_ascii=False, sort_keys=True) + "\n"
        _write_locked_owner(fd, owner_text)
        yield
    finally:
        if acquired:
            try:
                _release_kernel_lock(fd)
            except OSError:
                pass
        os.close(fd)


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
