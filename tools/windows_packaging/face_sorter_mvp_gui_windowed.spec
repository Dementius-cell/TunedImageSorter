# -*- mode: python ; coding: utf-8 -*-
# Tuned Image Sorter v69.6 / Этап 055 — CPU one-folder PyInstaller build.
# Run from project root:
#   tools\windows_packaging\build_windows_gui.ps1 -Profile cpu -InstallRequirements

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

ROOT = Path.cwd().resolve()
PACKAGE_DIR = ROOT / "face_sorter_mvp"
ENTRY_SCRIPT = ROOT / "tools" / "windows_packaging" / "pyinstaller_gui_entry.py"
APP_NAME = "TunedImageSorter_CPU"

hiddenimports = []
for module_name in (
    "face_sorter_mvp",
    "face_sorter_mvp.backend",
    "face_sorter_mvp.ui",
    "face_sorter_mvp.ui.main_window",
    "face_sorter_mvp.core",
    "face_sorter_mvp.core.frozen_runtime",
    "face_sorter_mvp.core.frozen_diagnostics",
    "face_sorter_mvp.reports",
):
    hiddenimports.append(module_name)

for package_name in (
    "face_sorter_mvp",
    "insightface",
    "onnxruntime",
    "cv2",
    "sklearn",
    "hdbscan",
    "PIL",
    "pillow_heif",
):
    try:
        hiddenimports += collect_submodules(package_name)
    except Exception:
        pass

_datas = []
for rel in (
    "README_RU.md",
    "README_EN.md",
    "ARCHITECTURE_FOR_AGENTS.md",
    "ui/resources/app_icon.ico",
    "ui/resources/app_icon.png",
):
    path = PACKAGE_DIR / rel
    if path.exists():
        rel_path = Path(rel)
        target = str(Path("face_sorter_mvp") / rel_path.parent) if rel_path.parent != Path(".") else "face_sorter_mvp"
        _datas.append((str(path), target))

for rel in (
    "CHANGELOG.md",
    "docs/USER_GUIDE_RU.md",
    "docs/USER_GUIDE_EN.md",
    "docs/HELP_RU.md",
    "docs/HELP_EN.md",
    "docs/DEVELOPER_NOTES_RU.md",
    "docs/DEVELOPER_NOTES_EN.md",
    "tools/windows_packaging/README_WINDOWS_PACKAGING_RU.md",
    "tools/windows_packaging/README_WINDOWS_PACKAGING_EN.md",
):
    path = ROOT / rel
    if path.exists():
        target = str(Path(rel).parent) if Path(rel).parent != Path(".") else "."
        _datas.append((str(path), target))

for package_name in ("insightface", "onnxruntime", "cv2", "pillow_heif"):
    try:
        _datas += collect_data_files(package_name)
    except Exception:
        pass

# InsightFace's 3D landmark helper opens this data file by the process working
# directory/resource root (``objects/meanshape_68.pkl``), not through package
# resources.  PyInstaller's generic collect_data_files("insightface") can miss
# that root-level layout, which makes frozen app.get() crash inside
# insightface.utils.transform.  Bundle every discovered meanshape file both at
# the root-level objects/ path and next to its package data for compatibility.
def _add_insightface_runtime_objects() -> None:
    try:
        import importlib.util
        spec = importlib.util.find_spec("insightface")
        if spec is None or not spec.origin:
            return
        pkg_root = Path(spec.origin).resolve().parent
        search_roots = [pkg_root, pkg_root.parent]
        seen = set()
        for search_root in search_roots:
            if not search_root.exists():
                continue
            for candidate in search_root.rglob("meanshape_68.pkl"):
                if not candidate.is_file():
                    continue
                key = str(candidate.resolve())
                if key in seen:
                    continue
                seen.add(key)
                _datas.append((str(candidate), "objects"))
                try:
                    rel_parent = candidate.parent.relative_to(pkg_root).parent
                    target = Path("insightface") / rel_parent / "objects"
                    _datas.append((str(candidate), str(target)))
                except Exception:
                    pass
    except Exception:
        pass

_add_insightface_runtime_objects()


_binaries = []
for package_name in ("onnxruntime", "cv2", "hdbscan"):
    try:
        _binaries += collect_dynamic_libs(package_name)
    except Exception:
        pass

block_cipher = None

a = Analysis(
    [str(ENTRY_SCRIPT)],
    pathex=[str(ROOT)],
    binaries=_binaries,
    datas=_datas,
    hiddenimports=sorted(set(hiddenimports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["torch", "tensorflow", "sklearn.tests", "hdbscan.tests", "onnxruntime.quantization"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
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
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
