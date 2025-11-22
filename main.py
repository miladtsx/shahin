# Ensure annotations don't break on Python 3.8+
from __future__ import annotations

from src.detect_vehicle import run_plate_detection
from src.common_utils.app_logger import get_logger, log_duration
from src.common_utils import license_utils, native_guard
from src.common_utils.resource_path import get_resource_path
import sys
import os
import time

logger = get_logger("app", logfile="logs/app.jsonl")

# add native extension import + pre-run checks
try:
    import core_native  # built from core_native Rust crate (pyo3)
except Exception as e:
    logger.exception("native_extension_load_failed", extra={"error": str(e)})
    logger.error(
        "native extension 'core_native' not available; build with maturin/pip. Aborting."
    )
    sys.exit(1)


def _read_expected_hash() -> str | None:
    env_hash = os.environ.get("SHAHIN_EXPECTED_MAIN_HASH")
    if env_hash:
        return env_hash.strip() or None

    p_root = get_resource_path("main.py.sha256")

    with open(p_root, "r") as f:
        val = f.read().strip()
        logger.info(f"hash_read_ok path={p_root}")
        return val
    return None


def _integrity_target_path() -> str | None:
    """Return the file path whose hash should be validated."""
    candidates: list[str] = []
    if getattr(sys, "frozen", False):
        if os.environ.get("SHAHIN_LAUNCH_TOKEN"):
            return None  # launcher already validated protected payloads
        try:
            candidates.append(get_resource_path(os.path.join("protected", "main.bin")))
        except Exception as e:
            logger.warning("integrity_target_resolve_failed", extra={"error": str(e)})
        # secondary fallbacks
        try:
            candidates.append(get_resource_path("main.py"))
        except Exception:
            pass
    else:
        candidates.append(__file__)

    for cand in candidates:
        if cand and os.path.exists(cand):
            return cand
    logger.error("integrity_target_not_found", extra={"candidates": candidates})
    return None


def _check_integrity_and_authorization() -> bool:
    print("Checking integrity")
    if getattr(sys, "frozen", False) and os.environ.get("SHAHIN_LAUNCH_TOKEN"):
        print("FROZEN")

        entry = os.environ.get("WIN_ENTRY")
        expected = os.environ.get("WIN_INTEGRITY")
        print(entry)
        print(expected)
        if not entry or not expected:
            logger.info(
                "integrity_check_skipped",
                extra={
                    "reason": "launcher_context_missing",
                    "entry": entry,
                    "expected": expected,
                },
            )
        else:
            try:
                hasher = getattr(core_native, "calculate_sanitized_self_hash", None)
                guard_label = "core_native.calculate_sanitized_self_hash"
                if hasher is None:
                    logger.warning(
                        "sanitized_hasher_missing",
                        extra={"fallback": "calculate_file_sha256"},
                    )
                    hasher = core_native.calculate_file_sha256
                    guard_label = "core_native.calculate_file_sha256"
                if not native_guard.allow_native_call(guard_label):
                    time.sleep(native_guard.degraded_delay())
                    logger.warning("integrity_guard_blocked", extra={"file": entry})
                    return False
                actual = hasher(entry)
                print("Actual", actual)
            except Exception as e:
                logger.exception(
                    "launcher_integrity_check_failed",
                    extra={"error": str(e), "file": entry},
                )
                return False
            if actual.strip().lower() != expected.strip().lower():
                logger.error(
                    "integrity_check_failed",
                    extra={"file": entry, "expected": expected, "actual": actual},
                )
                return False
            logger.info(
                "integrity_check_passed", extra={"file": entry, "mode": "launcher"}
            )
    else:
        print("non FROZEN")

        # verify main file hash
        expected = _read_expected_hash()
        if expected:
            ok = False
            target = _integrity_target_path()
            if not target:
                logger.error("integrity_target_missing")
                return False
            try:
                if not native_guard.allow_native_call("core_native.verify_file_hash"):
                    time.sleep(native_guard.degraded_delay())
                    logger.warning("integrity_guard_blocked", extra={"file": __file__})
                    return False
                ok = core_native.verify_file_hash(target, expected)
            except Exception as e:
                logger.exception(
                    "native_verify_failed", extra={"error": str(e), "target": target}
                )
                return False
            if not ok:
                logger.error("integrity_check_failed", extra={"file": target})
                return False
            logger.info("integrity_check_passed", extra={"file": target})
        else:
            logger.warning(
                "no_expected_hash_provided",
                extra={
                    "hint": "set SHAHIN_EXPECTED_MAIN_HASH or ensure res/main.py.sha256 is packaged"
                },
            )

    # check machine fingerprint if requested
    try:
        fp = license_utils.get_machine_fingerprint()
        logger.info("machine_fingerprint", extra={"fingerprint": fp})
    except Exception as e:
        logger.exception("fingerprint_failed", extra={"error": str(e)})
        return False

    status = license_utils.license_status(force_reload=True)
    if not status.valid:
        logger.error("license_invalid", extra={"reason": status.reason})
        return False
    payload = status.payload or {}
    logger.info(
        "license_valid",
        extra={
            "customer": payload.get("customer"),
            "license_id": payload.get("license_id"),
            "expiry": payload.get("exp"),
        },
    )

    return True


def main():
    logger.info("application_start", extra={"event": "application_start"})
    try:
        # TODO do the check not only on startup, but also on different critical paths
        if not _check_integrity_and_authorization():
            logger.error("startup_checks_failed")
            sys.exit(2)

        run_plate_detection()

        logger.info("application_exit", extra={"event": "application_exit"})
    except Exception as e:
        logger.exception(f"unhandled_exception:\n {e}")
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
