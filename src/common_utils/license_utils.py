from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.common_utils.app_logger import get_logger
from src.common_utils import native_guard

from .resource_path import get_data_path

try:
    import core_native  # type: ignore
except (
    Exception
) as exc:  # pragma: no cover - tray/backends require native module anyway
    raise RuntimeError(f"core_native module is required for licensing: {exc}") from exc

logger = get_logger("licensing")

LICENSE_PATH = Path(get_data_path(f"license/"))

@dataclass
class LicenseStatus:
    valid: bool
    reason: str
    payload: Optional[dict] = None


_CACHED_FINGERPRINT: Optional[str] = None


def get_machine_fingerprint() -> str:
    global _CACHED_FINGERPRINT
    if _CACHED_FINGERPRINT:
        return _CACHED_FINGERPRINT
    if not native_guard.allow_native_call("core_native.get_machine_fingerprint"):
        time.sleep(native_guard.degraded_delay())
        _CACHED_FINGERPRINT = native_guard.blocked_fingerprint()
        return _CACHED_FINGERPRINT
    fp = core_native.get_machine_fingerprint()
    _CACHED_FINGERPRINT = fp
    return fp


def _normalize_blob(raw: str) -> str:
    return "".join(raw.split())


def _decode_blob(blob: str) -> tuple[str, str, str]:
    normalized = _normalize_blob(blob)
    if "." not in normalized:
        raise ValueError("license format must be <payload_b64>.<signature_b64>")
    payload_b64, signature_b64 = normalized.split(".", 1)
    try:
        payload_json = base64.b64decode(payload_b64).decode("utf-8")
    except Exception as exc:
        raise ValueError("payload base64 is invalid") from exc
    return payload_json, payload_b64, signature_b64


def _parse_expiry(value: str) -> Optional[datetime]:
    try:
        iso = value.strip()
        if iso.endswith("Z"):
            iso = iso[:-1] + "+00:00"
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _verify_payload(payload_json: str, signature_b64: str) -> dict:
    if not native_guard.allow_native_call("core_native.verify_signed_blob"):
        time.sleep(native_guard.degraded_delay())
        raise ValueError("native_guard_blocked")
    verified = core_native.verify_signed_blob(payload_json, signature_b64)
    if not verified:
        raise ValueError("signature invalid")
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise ValueError("payload is not valid JSON") from exc
    return payload


def _validate_payload(payload: dict) -> LicenseStatus:
    fingerprint = payload.get("fingerprint")
    if not fingerprint or not isinstance(fingerprint, str):
        return LicenseStatus(False, "missing_fingerprint", payload=None)
    current_fp = get_machine_fingerprint()
    if fingerprint != current_fp:
        return LicenseStatus(False, "fingerprint_mismatch", payload=None)

    expiry = payload.get("exp")
    if expiry:
        expiry_dt = _parse_expiry(expiry)
        if expiry_dt is None:
            return LicenseStatus(False, "invalid_expiry_format", payload=None)
        if expiry_dt < datetime.now(timezone.utc):
            return LicenseStatus(False, "license_expired", payload=None)

    return LicenseStatus(True, "license_valid", payload=payload)


def verify_license_blob(blob: str) -> LicenseStatus:
    try:
        payload_json, _, signature = _decode_blob(blob)
        payload = _verify_payload(payload_json, signature)
    except ValueError as exc:
        return LicenseStatus(False, str(exc), None)
    return _validate_payload(payload)


def _read_license_from_disk() -> Optional[str]:
    if not LICENSE_PATH.exists():
        return None
    try:
        with open(LICENSE_PATH / "license.json", "r", encoding="utf-8") as fh:
            raw = fh.read().strip()
            if not raw:
                return None
            # Accept legacy JSON structure with explicit key if needed
            if raw.startswith("{"):
                data = json.loads(raw)
                if isinstance(data, dict):
                    if "license" in data and isinstance(data["license"], str):
                        return data["license"]
                    payload_b64 = data.get("payload_b64")
                    signature_b64 = data.get("signature_b64")
                    if (
                        isinstance(payload_b64, str)
                        and isinstance(signature_b64, str)
                        and payload_b64
                        and signature_b64
                    ):
                        return f"{payload_b64}.{signature_b64}"
                return None
            return raw
    except Exception as exc:
        logger.exception("failed_to_read_license", extra={"error": str(exc)})
        return None


def _write_license_to_disk(blob: str) -> None:
    LICENSE_PATH.mkdir(parents=True, exist_ok=True)
    data = {"license": _normalize_blob(blob)}
    with open(LICENSE_PATH / "license.json", "w", encoding="utf-8") as fh:
        json.dump(data, fh, separators=(",", ":"))


def license_status() -> LicenseStatus:
    blob = _read_license_from_disk()
    if not blob:
        return LicenseStatus(False, "missing_license", None)
    return verify_license_blob(blob)


def license_is_valid() -> bool:
    return license_status().valid


def activate_license(blob: str) -> LicenseStatus:
    status = verify_license_blob(blob)
    if status.valid:
        try:
            _write_license_to_disk(blob)
            license_status()
        except Exception as exc:
            logger.exception("failed_to_store_license", extra={"error": str(exc)})
            return LicenseStatus(False, "write_failed", None)
    return status


def current_license_summary() -> Optional[dict]:
    status = license_status()
    if not status.valid or not status.payload:
        return None
    payload = status.payload.copy()
    payload.pop("signature", None)
    return payload
