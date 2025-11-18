"""
PyInstaller bootstrapper that hands control to the Rust launcher.

PyInstaller still needs a Python entry point so it can discover the
runtime dependencies, but the actual application logic lives in
`core_native`. This stub resolves the packaged launcher binary (or
falls back to the development build) and executes it, forwarding all
arguments and exit codes.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable


def _resource_base() -> Path:
    """Return the directory that contains packaged resources."""
    tmp_root = getattr(sys, "_MEIPASS", None)
    if tmp_root:
        return Path(tmp_root)
    return Path(__file__).resolve().parent


def _launcher_candidates() -> Iterable[Path]:
    exe_name = "core_native.exe" if os.name == "nt" else "core_native"
    # When running from a PyInstaller bundle, the launcher is packaged
    # alongside this stub inside the extraction directory.
    yield _resource_base() / exe_name

    # Allow direct invocation from a development checkout as well.
    repo_root = Path(__file__).resolve().parents[1]
    yield repo_root / "core_native" / "target" / "release" / exe_name


def _resolve_launcher() -> Path:
    for candidate in _launcher_candidates():
        if candidate.exists():
            return candidate
    raise FileNotFoundError("core_native launcher is missing from the bundle")


def _pause_on_exit(returncode: int) -> None:
    """Keep the console window open so stdout/stderr remain visible."""
    if not getattr(sys, "frozen", False):
        return
    if os.environ.get("SHAHIN_NO_PAUSE"):
        return
    stdin = getattr(sys, "stdin", None)
    if stdin is None or not stdin.isatty():
        return
    try:
        input(
            f"\ncore_native exited with code {returncode}. "
            "Press Enter to close this window."
        )
    except EOFError:
        pass


def main() -> None:
    bundle_root = _resource_base()
    os.environ["SHAHIN_BUNDLE_ROOT"] = str(bundle_root)
    launcher = _resolve_launcher()
    # Share the bundle's sys.path with the Rust-side interpreter so it can import
    # the same vendored modules that PyInstaller exposes to this stub.
    bundle_sys_path = os.pathsep.join(dict.fromkeys(sys.path))
    os.environ["SHAHIN_BUNDLE_SYSPATH"] = bundle_sys_path
    cmd = [str(launcher), *sys.argv[1:]]
    # Inherit stdio so logging and prompts behave identically to
    # launching the Rust executable directly.
    completed = subprocess.run(cmd, check=False)
    _pause_on_exit(completed.returncode)
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
