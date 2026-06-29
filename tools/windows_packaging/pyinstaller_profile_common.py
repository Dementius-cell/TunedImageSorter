# -*- coding: utf-8 -*-
"""Shared PyInstaller collection helpers for Tuned Image Sorter Windows profiles.

The CPU and GPU specs intentionally import this module instead of carrying two
copies of the same PyInstaller collection rules.  Profile-specific differences
stay limited to the app/output name and the GPU native-runtime collection flag.
"""
from __future__ import annotations

import importlib.metadata as md
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

DataEntry = Tuple[str, str]
BinaryEntry = Tuple[str, str]

COMMON_HIDDEN_MODULES: Tuple[str, ...] = (
    "face_sorter_mvp",
    "face_sorter_mvp.backend",
    "face_sorter_mvp.ui",
    "face_sorter_mvp.ui.main_window",
    "face_sorter_mvp.core",
    "face_sorter_mvp.core.frozen_runtime",
    "face_sorter_mvp.core.frozen_diagnostics",
    "face_sorter_mvp.reports",
)

COMMON_COLLECT_PACKAGES: Tuple[str, ...] = (
    "face_sorter_mvp",
    "insightface",
    "onnxruntime",
    "cv2",
    "sklearn",
    "hdbscan",
    "PIL",
    "pillow_heif",
)

COMMON_DATA_PACKAGES: Tuple[str, ...] = (
    "insightface",
    "onnxruntime",
    "cv2",
    "pillow_heif",
)

COMMON_BINARY_PACKAGES: Tuple[str, ...] = (
    "onnxruntime",
    "cv2",
    "hdbscan",
)

GPU_NATIVE_DISTRIBUTIONS: Tuple[str, ...] = (
    "nvidia-cuda-runtime-cu12",
    "nvidia-cudnn-cu12",
    "nvidia-cublas-cu12",
    "nvidia-cuda-nvrtc-cu12",
    "nvidia-cufft-cu12",
    "nvidia-curand-cu12",
    "nvidia-nvjitlink-cu12",
)

GPU_DLL_SUFFIXES: Tuple[str, ...] = (".dll", ".pyd")

# Keep PyInstaller hidden imports limited to runtime inference code.  Broad
# collect_submodules() calls can otherwise pull tests, converter tools and
# optional GUIs that are not used by TunedImageSorter and create noisy red build
# output such as missing hdbscan/sklearn tests or optional sympy/torch imports.
EXCLUDED_HIDDEN_IMPORT_PREFIXES: Tuple[str, ...] = (
    "hdbscan.tests",
    "sklearn.tests",
    "sklearn._loss.tests",
    "sklearn.callback.tests",
    "sklearn.cluster.tests",
    "sklearn.cluster._hdbscan.tests",
    "sklearn.compose.tests",
    "sklearn.conftest",
    "sklearn.externals.array_api_compat.torch",
    "sklearn.externals.array_api_compat.dask",
    "sklearn.externals.array_api_compat.cupy",
    "onnxruntime.tools",
    "onnxruntime.quantization",
    "onnxruntime.transformers",
    "onnxruntime.datasets",
    "onnxruntime.backend",
    "insightface.gui",
    "insightface.commands",
    "insightface.thirdparty.face3d",
)

EXCLUDED_BUNDLE_FILE_NAMES: Tuple[str, ...] = (
    # TunedImageSorter uses CUDAExecutionProvider only.  Bundling TensorRT provider
    # DLLs triggers PyInstaller dependency warnings for nvinfer/nvonnxparser and
    # does not improve the supported GPU profile.
    "onnxruntime_providers_tensorrt.dll",
)

PYINSTALLER_EXCLUDES: Tuple[str, ...] = (
    "torch",
    "tensorflow",
    "sympy",
    "cupy",
    "dask",
    "sklearn.externals.array_api_compat.dask",
    "sklearn.externals.array_api_compat.cupy",
    "sklearn.tests",
    "hdbscan.tests",
    "onnxruntime.tools",
    "onnxruntime.quantization",
    "onnxruntime.transformers",
    "onnxruntime.datasets",
    "onnxruntime.backend",
    "insightface.gui",
    "insightface.commands",
    "insightface.thirdparty.face3d",
)


def _dedupe_pairs(items: Iterable[Tuple[str, str]]) -> List[Tuple[str, str]]:
    seen = set()
    out: List[Tuple[str, str]] = []
    for src, dst in items:
        key = (str(src), str(dst))
        if key in seen:
            continue
        seen.add(key)
        out.append((str(src), str(dst)))
    return out


def _hidden_import_allowed(module_name: str) -> bool:
    name = str(module_name)
    return not any(name == prefix or name.startswith(prefix + ".") for prefix in EXCLUDED_HIDDEN_IMPORT_PREFIXES)


def _bundle_entry_allowed(src: str) -> bool:
    return Path(str(src)).name.lower() not in EXCLUDED_BUNDLE_FILE_NAMES


def _filter_bundle_pairs(items: Iterable[Tuple[str, str]]) -> List[Tuple[str, str]]:
    return [(src, dst) for src, dst in items if _bundle_entry_allowed(src)]


def _try_collect_submodules(package_name: str) -> List[str]:
    try:
        try:
            modules = collect_submodules(package_name, filter=_hidden_import_allowed)
        except TypeError:
            modules = collect_submodules(package_name)
        return [name for name in modules if _hidden_import_allowed(name)]
    except Exception:
        return []


def _try_collect_data_files(package_name: str) -> List[DataEntry]:
    try:
        return _filter_bundle_pairs(collect_data_files(package_name))
    except Exception:
        return []


def _try_collect_dynamic_libs(package_name: str) -> List[BinaryEntry]:
    try:
        return _filter_bundle_pairs(collect_dynamic_libs(package_name))
    except Exception:
        return []


def _project_datas(root: Path, package_dir: Path) -> List[DataEntry]:
    datas: List[DataEntry] = []
    for rel in (
        "README_RU.md",
        "README_EN.md",
        "ARCHITECTURE_FOR_AGENTS.md",
        "ui/resources/app_icon.ico",
        "ui/resources/app_icon.png",
    ):
        path = package_dir / rel
        if path.exists():
            rel_path = Path(rel)
            target = str(Path("face_sorter_mvp") / rel_path.parent) if rel_path.parent != Path(".") else "face_sorter_mvp"
            datas.append((str(path), target))

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
        path = root / rel
        if path.exists():
            target = str(Path(rel).parent) if Path(rel).parent != Path(".") else "."
            datas.append((str(path), target))
    return datas


def _add_insightface_runtime_objects(datas: List[DataEntry]) -> None:
    """Bundle meanshape_68.pkl at root-level objects/ and package-compatible paths."""
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
                datas.append((str(candidate), "objects"))
                try:
                    rel_parent = candidate.parent.relative_to(pkg_root).parent
                    target = Path("insightface") / rel_parent / "objects"
                    datas.append((str(candidate), str(target)))
                except Exception:
                    pass
    except Exception:
        pass


def _collect_distribution_dlls(distribution_names: Sequence[str]) -> List[BinaryEntry]:
    """Collect native DLLs from NVIDIA CUDA/cuDNN wheels by distribution metadata.

    PyInstaller hook helpers take importable package names, while NVIDIA wheels
    are best addressed through distribution names.  Preserving the metadata
    relative path (for example ``nvidia/cudnn/bin``) lets the frozen runtime scan
    ``_internal/nvidia`` the same way source mode scans ``site-packages/nvidia``.
    """
    binaries: List[BinaryEntry] = []
    for dist_name in distribution_names:
        try:
            dist = md.distribution(dist_name)
            files = list(dist.files or [])
        except Exception:
            continue
        for file_ref in files:
            rel = Path(str(file_ref))
            if rel.suffix.lower() not in GPU_DLL_SUFFIXES:
                continue
            try:
                src = Path(dist.locate_file(file_ref)).resolve()
            except Exception:
                continue
            if not src.exists() or not src.is_file():
                continue
            target = str(rel.parent) if str(rel.parent) != "." else "."
            binaries.append((str(src), target))
    return _filter_bundle_pairs(_dedupe_pairs(binaries))


def build_profile_inputs(root: Path, package_dir: Path, *, gpu: bool = False):
    """Return ``hiddenimports, datas, binaries`` for a CPU or GPU PyInstaller spec."""
    hiddenimports: List[str] = list(COMMON_HIDDEN_MODULES)
    for package_name in COMMON_COLLECT_PACKAGES:
        hiddenimports.extend(_try_collect_submodules(package_name))
    if gpu:
        hiddenimports.extend(_try_collect_submodules("nvidia"))

    datas: List[DataEntry] = _project_datas(root, package_dir)
    for package_name in COMMON_DATA_PACKAGES:
        datas.extend(_try_collect_data_files(package_name))
    _add_insightface_runtime_objects(datas)

    binaries: List[BinaryEntry] = []
    for package_name in COMMON_BINARY_PACKAGES:
        binaries.extend(_try_collect_dynamic_libs(package_name))
    if gpu:
        binaries.extend(_collect_distribution_dlls(GPU_NATIVE_DISTRIBUTIONS))

    hiddenimports = [name for name in hiddenimports if _hidden_import_allowed(name)]
    return sorted(set(hiddenimports)), _filter_bundle_pairs(_dedupe_pairs(datas)), _filter_bundle_pairs(_dedupe_pairs(binaries))
