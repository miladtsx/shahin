# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_submodules

REPO_ROOT = os.environ.get("SHAHIN_REPO_ROOT")
if not REPO_ROOT:
    REPO_ROOT = os.path.abspath(os.getcwd())
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

ENTRY_STUB = os.path.join(REPO_ROOT, "scripts", "pyinstaller_stub.py")
CRITICAL_MODULES = [
    "main",
    "tray_app",
    "src.common_utils.app_logger",
    "src.common_utils.resource_path",
    "src.common_utils.license_utils",
    "src.common_utils.native_guard",
]

hiddenimports = [
    module for module in collect_submodules("src") if module not in CRITICAL_MODULES
]
hiddenimports += [
    "src.common_utils.image_save",
    "frontend.app",
]
hiddenimports += collect_submodules("pystray")

launcher_name = "core_native.exe"
LAUNCHER_PATH = os.path.join("core_native", "target", "release", launcher_name)
LAUNCHER_BINARY = (LAUNCHER_PATH, ".")
PROTECTED_DATAS = ("build/protected", "protected")

pathex = [REPO_ROOT]

a = Analysis(
    [ENTRY_STUB],
    pathex=pathex,
    binaries=[LAUNCHER_BINARY],
datas=[
        ("frontend/static", "frontend/static"),
        ("res/main.py.sha256", "res"),
        PROTECTED_DATAS,
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=CRITICAL_MODULES,
    noarchive=True,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Shahin',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Shahin'
)
