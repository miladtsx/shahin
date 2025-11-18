from __future__ import annotations

import os
import random
import sys
import threading
from typing import Final

from src.common_utils.app_logger import get_logger

logger = get_logger("native_guard")

_BLOCKED_FINGERPRINT: Final[str] = "debugger-blocked"
_thread_local = threading.local()


def debugger_present() -> bool:
    return False #TODO for development purposes
    tracer = sys.gettrace()
    if tracer is not None:
        return True
    # Fallback to heuristic env flags that common debuggers set.
    return any(
        os.environ.get(key)
        for key in ("PYDEVD_USE_FRAME_EVAL", "PYCHARM_HOSTED", "DEBUGGER_PRESENT")
    )


def allow_native_call(operation: str) -> bool:
    if getattr(_thread_local, "guard_override", False):
        return True
    if not debugger_present():
        return True
    logger.warning("debugger_detected", extra={"operation": operation})
    return False


class _Bypass:
    def __enter__(self):
        _thread_local.guard_override = True

    def __exit__(self, exc_type, exc, tb):
        _thread_local.guard_override = False


def temporarily_allow_native_calls():
    """Context manager to skip the guard for trusted internal ops."""

    return _Bypass()


def blocked_fingerprint() -> str:
    return _BLOCKED_FINGERPRINT


def degraded_delay() -> float:
    # Introduce small jitter to avoid tight loops when degraded.
    return random.uniform(0.05, 0.2)
