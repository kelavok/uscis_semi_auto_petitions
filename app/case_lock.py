"""Reentrant case locks, shared by local HTTP requests and CLI processes."""
from __future__ import annotations

import hashlib
import os
import threading
import time
from contextlib import contextmanager
from functools import wraps

_guard = threading.Lock()
_locks: dict[str, threading.RLock] = {}
_active = threading.local()


@contextmanager
def locked_case(case_id: str):
    from .cli_support import CASE_ROOT, case_path
    from .safe_io import contained_path

    key = os.path.normcase(str(case_path(case_id).resolve()))
    with _guard:
        lock = _locks.setdefault(key, threading.RLock())
    with lock:
        depths = getattr(_active, "depths", {})
        if depths.get(key, 0):
            yield
            return
        root = contained_path(CASE_ROOT, ".locks")
        root.mkdir(parents=True, exist_ok=True)
        lock_path = root / (hashlib.sha256(key.encode("utf-8")).hexdigest() + ".lock")
        with lock_path.open("a+b") as handle:
            if not handle.tell():
                handle.write(b"0")
                handle.flush()
            deadline = time.monotonic() + 30
            while True:
                try:
                    handle.seek(0)
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError as exc:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Case is busy in another local process; retry later.") from exc
                    time.sleep(0.05)
            depths[key] = 1
            _active.depths = depths
            try:
                yield
            finally:
                del depths[key]
                if os.name == "nt":
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle, fcntl.LOCK_UN)


def case_operation(function):
    @wraps(function)
    def run(case_id, *args, **kwargs):
        with locked_case(case_id):
            return function(case_id, *args, **kwargs)
    return run
