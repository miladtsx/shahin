from __future__ import annotations

from typing import Optional

try:
    import core_native  # type: ignore
except Exception as exc:  # pragma: no cover - native licensing is mandatory
    raise RuntimeError(f"core_native module is required for licensing: {exc}") from exc


# Expose the Rust-backed status object for compatibility with prior Python code.
LicenseStatus = core_native.LicenseStatus


def get_machine_fingerprint() -> str:
    return core_native.get_machine_fingerprint()


def verify_license_blob(blob: str) -> LicenseStatus:
    return core_native.verify_license_blob(blob)


def license_status() -> LicenseStatus:
    return core_native.license_status()


def license_is_valid() -> bool:
    return core_native.license_is_valid()


def activate_license(blob: str) -> LicenseStatus:
    return core_native.activate_license(blob)


def current_license_summary() -> Optional[dict]:
    return core_native.current_license_summary()
