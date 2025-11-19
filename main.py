# Ensure annotations don't break on Python 3.8+
from __future__ import annotations

from src.detect_vehicle import run_plate_detection
from src.common_utils.app_logger import get_logger, log_duration
from src.common_utils import license_utils, native_guard
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
        "native extension 'core_native' not available — build with maturin/pip. Aborting."
    )
    sys.exit(1)


def _read_expected_hash() -> str | None:
    p = os.path.join(os.path.dirname(__file__), "res", "main.py.sha256")
    try:
        with open(p, "r") as f:
            return f.read().strip()
    except Exception:
        return None


def _check_integrity_and_authorization() -> bool:
    # verify main file hash
    expected = _read_expected_hash()
    if expected:
        ok = False
        try:
            if not native_guard.allow_native_call("core_native.verify_file_hash"):
                time.sleep(native_guard.degraded_delay())
                logger.warning("integrity_guard_blocked", extra={"file": __file__})
                return False
            ok = core_native.verify_file_hash(__file__, expected)
        except Exception as e:
            logger.exception("native_verify_failed", extra={"error": str(e)})
            return False
        if not ok:
            logger.error("integrity_check_failed", extra={"file": __file__})
            return False
        logger.info("integrity_check_passed", extra={"file": __file__})
    else:
        logger.warning(
            "no_expected_hash_provided",
            extra={"hint": "set SHAHIN_EXPECTED_MAIN_HASH"},
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
