# -*- mode: python ; coding: utf-8 -*-
# Tuned Image Sorter v69.6 / Этап 055 — CPU one-folder PyInstaller build.
# Run from project root:
#   tools\windows_packaging\build_windows_gui.ps1 -Profile cpu -InstallRequirements

from pathlib import Path
import sys

ROOT = Path.cwd().resolve()
PACKAGE_DIR = ROOT / "face_sorter_mvp"
ENTRY_SCRIPT = ROOT / "tools" / "windows_packaging" / "pyinstaller_gui_entry.py"
APP_NAME = "TunedImageSorter_CPU"

sys.path.insert(0, str(ROOT / "tools" / "windows_packaging"))
from pyinstaller_profile_common import PYINSTALLER_EXCLUDES, build_profile_inputs  # noqa: E402

hiddenimports, _datas, _binaries = build_profile_inputs(ROOT, PACKAGE_DIR, gpu=False)

block_cipher = None

a = Analysis(
    [str(ENTRY_SCRIPT)],
    pathex=[str(ROOT), str(ROOT / "tools" / "windows_packaging")],
    binaries=_binaries,
    datas=_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=list(PYINSTALLER_EXCLUDES),
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
gui_exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TunedImageSorter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(PACKAGE_DIR / "ui" / "resources" / "app_icon.ico") if (PACKAGE_DIR / "ui" / "resources" / "app_icon.ico").exists() else None,
)
cli_exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TunedImageSorter_CLI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(PACKAGE_DIR / "ui" / "resources" / "app_icon.ico") if (PACKAGE_DIR / "ui" / "resources" / "app_icon.ico").exists() else None,
)
coll = COLLECT(
    gui_exe,
    cli_exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
