# -*- coding: utf-8 -*-
"""Import-safe runtime/environment preflight helpers for future Windows UI.

v69.6 / Этап 055 keeps this module so a PySide6 UI can check the Python
runtime, installed distributions, ONNX providers and optional GPU readiness
before starting a real photo-processing run.  The default preflight is light:
it does not import InsightFace, does not initialize models and does not scan
user photos.  Expensive GPU/model smoke-tests are opt-in.
"""
from __future__ import annotations

import datetime as dt
import importlib
import importlib.metadata as md
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .constants import SCRIPT_VERSION


PREFLIGHT_SCHEMA_VERSION = 2

_DLL_DIRECTORY_HANDLES: List[Any] = []
_DLL_DIRECTORIES_ADDED = False

CORE_DISTRIBUTIONS: Tuple[str, ...] = (
    "numpy",
    "Pillow",
    "tqdm",
    "opencv-python",
    "scikit-learn",
    "insightface",
    "hdbscan",
)

OPTIONAL_DISTRIBUTIONS: Tuple[str, ...] = (
    "pillow-heif",
    "psutil",
)

GPU_DISTRIBUTIONS: Tuple[str, ...] = (
    "onnxruntime",
    "onnxruntime-gpu",
    "nvidia-cuda-runtime-cu12",
    "nvidia-cudnn-cu12",
    "nvidia-cublas-cu12",
    "nvidia-cuda-nvrtc-cu12",
    "nvidia-cufft-cu12",
    "nvidia-curand-cu12",
    "nvidia-nvjitlink-cu12",
)

# These NVIDIA CUDA/cuDNN/cuBLAS wheels provide native DLLs/libraries.
# They are distributions that can be checked through importlib.metadata,
# but they are not normal Python import modules such as
# ``import nvidia_cuda_runtime_cu12``.  v65.4 keeps them metadata-only even
# when callers request ``import_check=True``.
NATIVE_LIBRARY_DISTRIBUTIONS: Tuple[str, ...] = (
    "nvidia-cuda-runtime-cu12",
    "nvidia-cudnn-cu12",
    "nvidia-cublas-cu12",
    "nvidia-cuda-nvrtc-cu12",
    "nvidia-cufft-cu12",
    "nvidia-curand-cu12",
    "nvidia-nvjitlink-cu12",
)


def _windows_no_window_creationflags() -> int:
    """Return CREATE_NO_WINDOW for captured Windows subprocess probes.

    Windowed PyInstaller GUI processes have no console.  Starting console tools
    such as nvidia-smi from that process can briefly flash a terminal window
    unless CREATE_NO_WINDOW is used.  On non-Windows platforms this returns 0.
    """
    if os.name != "nt":
        return 0
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))

NATIVE_LIBRARY_DISTRIBUTION_DLL_PATTERNS: Dict[str, Tuple[str, ...]] = {
    "nvidia-cuda-runtime-cu12": ("cudart64_12.dll",),
    "nvidia-cudnn-cu12": ("cudnn64_9.dll", "cudnn_ops64_9.dll", "cudnn_engines_tensor_ir64_9.dll"),
    "nvidia-cublas-cu12": ("cublas64_12.dll", "cublasLt64_12.dll"),
    "nvidia-cuda-nvrtc-cu12": ("nvrtc64_*.dll",),
    "nvidia-cufft-cu12": ("cufft64_*.dll",),
    "nvidia-curand-cu12": ("curand64_*.dll",),
    "nvidia-nvjitlink-cu12": ("nvJitLink*.dll", "nvjitlink*.dll"),
}


@dataclass(frozen=True)
class PackageStatus:
    """Status of one Python distribution/import required by the backend."""

    name: str
    installed: bool
    version: str = ""
    import_name: str = ""
    import_ok: Optional[bool] = None
    location: str = ""
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GpuPreflightStatus:
    """Lightweight GPU/ONNX Runtime status for UI diagnostics."""

    nvidia_smi_found: bool
    nvidia_gpu: str = ""
    nvidia_driver: str = ""
    onnxruntime_import_ok: bool = False
    onnxruntime_version: str = ""
    onnxruntime_location: str = ""
    onnx_providers: Tuple[str, ...] = ()
    cuda_provider_available: bool = False
    cuda_dlls: Dict[str, Tuple[str, ...]] = field(default_factory=dict)
    smoke_test_requested: bool = False
    smoke_test_result: Optional[Dict[str, Any]] = None
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["onnx_providers"] = list(self.onnx_providers)
        data["cuda_dlls"] = {key: list(value) for key, value in self.cuda_dlls.items()}
        return data


@dataclass(frozen=True)
class RuntimePreflightResult:
    """Serializable result of startup/environment checks for a future UI."""

    ok: bool
    version: str
    refactor_stage: str
    schema_version: int
    created_at: str
    duration_ms: int
    python_executable: str
    python_version: str
    platform: str
    cwd: str
    package_statuses: Tuple[PackageStatus, ...]
    gpu: GpuPreflightStatus
    missing_required: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    errors: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["package_statuses"] = [item.to_dict() for item in self.package_statuses]
        data["gpu"] = self.gpu.to_dict()
        return data


def _distribution_version(name: str) -> Tuple[bool, str, str]:
    """Return installed/version/location for a distribution without importing it.

    v65.4 intentionally uses ``importlib.metadata.version(...)`` as the
    primary installed/version check.  This is important for native-library
    wheels such as ``nvidia-cuda-runtime-cu12``: their distribution metadata is
    valid even though there is no same-named Python module to import.
    """
    try:
        version = md.version(name)
        location = ""
        try:
            dist = md.distribution(name)
            location = str(getattr(dist, "locate_file", lambda value: "")(""))
        except Exception:
            # Version metadata is enough to prove the package is installed.
            location = ""
        return True, version or "", location
    except md.PackageNotFoundError:
        return False, "", ""
    except Exception as exc:  # defensive: metadata can be broken in damaged envs
        return False, "", f"metadata error: {type(exc).__name__}: {exc}"


def _import_name_for_distribution(name: str) -> str:
    mapping = {
        "Pillow": "PIL",
        "opencv-python": "cv2",
        "scikit-learn": "sklearn",
        "pillow-heif": "pillow_heif",
        "onnxruntime-gpu": "onnxruntime",
    }
    return mapping.get(name, name.replace("-", "_"))


def _is_frozen_runtime() -> bool:
    return bool(getattr(sys, "frozen", False))


def _add_native_dll_directories_light() -> Tuple[str, ...]:
    """Best-effort Windows DLL search-path setup for frozen GPU diagnostics."""
    global _DLL_DIRECTORIES_ADDED
    if os.name != "nt" or _DLL_DIRECTORIES_ADDED:
        return ()
    patterns = (
        "cudnn*.dll",
        "cublas*.dll",
        "cudart*.dll",
        "nvrtc*.dll",
        "cufft*.dll",
        "curand*.dll",
        "nvjitlink*.dll",
        "onnxruntime_providers_cuda.dll",
    )
    dirs: List[Path] = []
    for root in _native_runtime_roots():
        for search_root in (root / "nvidia", root / "onnxruntime", root / "onnxruntime" / "capi"):
            if not search_root.exists():
                continue
            for pattern in patterns:
                try:
                    for dll in search_root.rglob(pattern):
                        if dll.is_file() and dll.parent not in dirs:
                            dirs.append(dll.parent)
                except Exception:
                    continue
    added: List[str] = []
    for directory in sorted(dirs, key=lambda p: (len(str(p)), str(p).lower())):
        try:
            text = str(directory.resolve())
            if hasattr(os, "add_dll_directory"):
                _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(text))
            os.environ["PATH"] = text + os.pathsep + os.environ.get("PATH", "")
            added.append(text)
        except Exception:
            continue
    _DLL_DIRECTORIES_ADDED = True
    return tuple(added)


def _native_runtime_roots() -> List[Path]:
    """Return source and frozen roots that may contain CUDA/ORT native DLLs."""
    roots: List[Path] = []
    try:
        import site

        roots.extend(Path(p) for p in site.getsitepackages())
        user_site = site.getusersitepackages()
        if user_site:
            roots.append(Path(user_site))
    except Exception:
        pass
    roots.extend(Path(p) for p in sys.path if p and "site-packages" in p)
    try:
        # GPU Lite first-run runtime cache.  Import lazily so the normal CPU/full
        # GPU preflight remains lightweight and does not depend on the installer.
        from .gpu_lite_runtime import gpu_lite_runtime_dir

        roots.append(gpu_lite_runtime_dir())
    except Exception:
        pass
    try:
        if _is_frozen_runtime():
            exe_dir = Path(sys.executable).resolve().parent
            roots.extend([exe_dir / "_internal", exe_dir])
            meipass = getattr(sys, "_MEIPASS", "")
            if meipass:
                roots.append(Path(meipass))
    except Exception:
        pass
    out: List[Path] = []
    seen = set()
    for root in roots:
        try:
            key = str(root.resolve())
        except Exception:
            key = str(root)
        if key in seen:
            continue
        seen.add(key)
        out.append(root)
    return out


def _import_fallback_status(name: str, import_name: str) -> Optional[PackageStatus]:
    """Use module import as a frozen-bundle fallback when dist metadata is absent.

    PyInstaller bundles Python modules and extension DLLs, but distribution
    metadata can be incomplete or absent.  In frozen mode, a successful import is
    the reliable signal that a runtime dependency is available.
    """
    if not import_name:
        return None
    try:
        module = importlib.import_module(import_name)
    except Exception:
        return None
    version = str(getattr(module, "__version__", "bundled") or "bundled")
    location = ""
    try:
        location = str(Path(getattr(module, "__file__", "")).resolve())
    except Exception:
        location = str(getattr(module, "__file__", "") or "")
    return PackageStatus(
        name=name,
        installed=True,
        version=version,
        import_name=import_name,
        import_ok=True,
        location=location,
        error="",
    )


def package_status(name: str, *, import_check: bool = False) -> PackageStatus:
    """Check one distribution and optionally verify that its import works.

    ``nvidia-*-cu12`` packages are native-library wheels.  They are valid
    installed distributions even though they are not importable as Python
    modules with names like ``nvidia_cuda_runtime_cu12``.  For those packages,
    installation/version metadata is the correct diagnostic signal, so v65.4
    intentionally skips Python import attempts even when ``import_check=True``.
    """
    installed, version, location = _distribution_version(name)
    import_name = _import_name_for_distribution(name)
    import_ok: Optional[bool] = None
    error = ""
    if not installed and _is_frozen_runtime() and name != "onnxruntime-gpu":
        # Do not use the shared top-level `onnxruntime` import as evidence that
        # the GPU distribution is installed.  CPU and GPU wheels expose the same
        # module name; v67.9.1 diagnostics could therefore label a CPU portable
        # runtime as `onnxruntime-gpu` after a reused build environment.
        fallback = _import_fallback_status(name, import_name)
        if fallback is not None:
            return fallback
    if name in NATIVE_LIBRARY_DISTRIBUTIONS:
        import_name = ""
        # In a frozen PyInstaller bundle, distribution metadata for NVIDIA
        # wheels is often absent even when the actual DLLs were bundled under
        # _internal/nvidia.  Treat matching DLLs as a bundled native runtime
        # signal so diagnostics do not misleadingly say "not installed".
        if not installed and _is_frozen_runtime():
            dlls = _find_cuda_runtime_dlls_light()
            patterns = NATIVE_LIBRARY_DISTRIBUTION_DLL_PATTERNS.get(name, ())
            if any(pattern in dlls and dlls.get(pattern) for pattern in patterns):
                installed = True
                version = "bundled"
                location = "; ".join(path for pattern in patterns for path in dlls.get(pattern, ())[:3])
        # Metadata/version or bundled DLL presence is the correct health signal
        # for these native wheels.  Leave import_ok as None: there was no Python
        # import attempt and therefore no Python import failure.
    elif import_check and installed:
        try:
            importlib.import_module(import_name)
            import_ok = True
        except Exception as exc:
            import_ok = False
            error = f"{type(exc).__name__}: {exc}"
    return PackageStatus(
        name=name,
        installed=installed,
        version=version,
        import_name=import_name,
        import_ok=import_ok,
        location=location,
        error=error,
    )


def collect_package_statuses(
    *,
    include_optional: bool = True,
    include_gpu_packages: bool = True,
    import_check: bool = False,
) -> Tuple[PackageStatus, ...]:
    """Collect package statuses for UI display without installing anything."""
    names: List[str] = list(CORE_DISTRIBUTIONS)
    if include_gpu_packages:
        names.extend(GPU_DISTRIBUTIONS)
    if include_optional:
        names.extend(OPTIONAL_DISTRIBUTIONS)
    seen = set()
    result: List[PackageStatus] = []
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        result.append(package_status(name, import_check=import_check))
    return tuple(result)


def _run_nvidia_smi() -> Tuple[bool, str, str]:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return False, "", ""
    try:
        proc = subprocess.run(
            [exe, "--query-gpu=name,driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
            creationflags=_windows_no_window_creationflags(),
        )
        first = (proc.stdout or "").strip().splitlines()[0] if proc.stdout else ""
        if first:
            parts = [part.strip() for part in first.split(",", 1)]
            gpu_name = parts[0] if parts else ""
            driver = parts[1] if len(parts) > 1 else ""
            return True, gpu_name, driver
        return True, "", ""
    except Exception as exc:
        return True, "", f"nvidia-smi error: {type(exc).__name__}: {exc}"


def _find_cuda_runtime_dlls_light() -> Dict[str, Tuple[str, ...]]:
    """Find common CUDA/cuDNN DLLs in site-packages without importing ORT."""
    patterns = (
        "cudnn64_9.dll",
        "cudnn_engines_tensor_ir64_9.dll",
        "cudnn_ops64_9.dll",
        "cublas64_12.dll",
        "cublasLt64_12.dll",
        "cudart64_12.dll",
        "nvrtc64_*.dll",
        "cufft64_*.dll",
        "curand64_*.dll",
        "nvJitLink*.dll",
        "nvjitlink*.dll",
        "onnxruntime_providers_cuda.dll",
    )
    roots = _native_runtime_roots()

    found: Dict[str, List[str]] = {pattern: [] for pattern in patterns}
    for root in dict.fromkeys(roots):
        if not root.exists():
            continue
        # Keep this lightweight for UI startup: scan only known package roots,
        # never the whole site-packages tree.
        search_roots = [root / "nvidia", root / "onnxruntime" / "capi"]
        for search_root in search_roots:
            if not search_root.exists():
                continue
            for pattern in patterns:
                for path in search_root.rglob(pattern):
                    text = str(path)
                    if text not in found[pattern]:
                        found[pattern].append(text)
    return {key: tuple(value[:12]) for key, value in found.items() if value}


def gpu_preflight(*, run_smoke_test: bool = False, model: str = "buffalo_l", det_size: int = 640) -> GpuPreflightStatus:
    """Check GPU/ONNX status for UI diagnostics.

    The default check imports only ONNX Runtime and queries providers.  The
    optional smoke test can initialize InsightFace and should be used only when
    the UI explicitly asks for a deeper GPU check.
    """
    nvidia_found, nvidia_gpu, nvidia_driver = _run_nvidia_smi()
    providers: List[str] = []
    ort_version = ""
    ort_location = ""
    ort_ok = False
    error = ""
    smoke: Optional[Dict[str, Any]] = None

    try:
        _add_native_dll_directories_light()
        import onnxruntime as ort  # type: ignore
        ort_ok = True
        ort_version = str(getattr(ort, "__version__", ""))
        ort_location = str(Path(getattr(ort, "__file__", "")).resolve()) if getattr(ort, "__file__", "") else ""
        preload = getattr(ort, "preload_dlls", None)
        if callable(preload):
            # directory="" is the official ORT way to search NVIDIA site-packages;
            # the no-argument call keeps compatibility with default PATH/PyTorch paths.
            try:
                preload(cuda=True, cudnn=True, msvc=True, directory="")
            except TypeError:
                try:
                    preload(directory="")
                except TypeError:
                    preload()
            except Exception:
                pass
            try:
                preload()
            except Exception:
                pass
        providers = list(ort.get_available_providers())
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    if run_smoke_test:
        try:
            try:
                from .. import face_sorter_mvp as legacy
            except ImportError:  # script-folder mode
                import face_sorter_mvp as legacy  # type: ignore
            smoke = dict(legacy.gpu_model_smoke_test_details(model_name=model, det_size=det_size))
        except Exception as exc:
            smoke = {"ok": False, "kind": "exception", "message": f"{type(exc).__name__}: {exc}"}

    return GpuPreflightStatus(
        nvidia_smi_found=nvidia_found,
        nvidia_gpu=nvidia_gpu,
        nvidia_driver=nvidia_driver,
        onnxruntime_import_ok=ort_ok,
        onnxruntime_version=ort_version,
        onnxruntime_location=ort_location,
        onnx_providers=tuple(providers),
        cuda_provider_available="CUDAExecutionProvider" in providers,
        cuda_dlls=_find_cuda_runtime_dlls_light(),
        smoke_test_requested=run_smoke_test,
        smoke_test_result=smoke,
        error=error,
    )


def runtime_preflight(
    *,
    include_optional: bool = True,
    include_gpu: bool = True,
    import_check: bool = False,
    run_gpu_smoke_test: bool = False,
    model: str = "buffalo_l",
    det_size: int = 640,
) -> RuntimePreflightResult:
    """Return a JSON-friendly runtime preflight result for a future UI.

    This function never installs/uninstalls packages and never touches user
    photo folders.  With ``run_gpu_smoke_test=False`` it also avoids model
    initialization and photo processing.
    """
    started = time.perf_counter()
    packages = collect_package_statuses(
        include_optional=include_optional,
        include_gpu_packages=include_gpu,
        import_check=import_check,
    )
    missing_required = tuple(item.name for item in packages if item.name in CORE_DISTRIBUTIONS and not item.installed)
    errors: List[str] = []
    warnings: List[str] = []
    if missing_required:
        errors.append("Missing required packages: " + ", ".join(missing_required))
    for item in packages:
        if item.import_ok is False:
            errors.append(f"Import failed for {item.name}: {item.error}")
    gpu = gpu_preflight(run_smoke_test=run_gpu_smoke_test, model=model, det_size=det_size) if include_gpu else GpuPreflightStatus(nvidia_smi_found=False)
    exe_name = Path(sys.executable).name.lower()
    app_dir_name = Path(sys.executable).resolve().parent.name.lower()
    is_cpu_portable = "cpu" in exe_name or "cpu" in app_dir_name
    if include_gpu and gpu.nvidia_smi_found and not gpu.cuda_provider_available:
        if is_cpu_portable and _is_frozen_runtime():
            warnings.append("CPU portable build: CUDAExecutionProvider is not bundled or expected. Use the GPU CUDA12 portable build for NVIDIA acceleration.")
        else:
            warnings.append("NVIDIA GPU was detected, but CUDAExecutionProvider is not available in ONNX Runtime.")
    if include_gpu and gpu.smoke_test_result and not bool(gpu.smoke_test_result.get("ok")):
        warnings.append("GPU smoke-test did not pass: " + str(gpu.smoke_test_result.get("message", "")))
    duration_ms = int((time.perf_counter() - started) * 1000)
    return RuntimePreflightResult(
        ok=not errors,
        version=SCRIPT_VERSION,
        refactor_stage="Этап 055",
        schema_version=PREFLIGHT_SCHEMA_VERSION,
        created_at=dt.datetime.now().isoformat(timespec="seconds"),
        duration_ms=duration_ms,
        python_executable=sys.executable,
        python_version=sys.version,
        platform=platform.platform(),
        cwd=os.getcwd(),
        package_statuses=packages,
        gpu=gpu,
        missing_required=missing_required,
        warnings=tuple(warnings),
        errors=tuple(errors),
    )


def runtime_preflight_summary(**kwargs: Any) -> Dict[str, Any]:
    """Convenience helper returning a compact summary for UI status labels.

    v69.6 keeps the old keys but also exposes separate CPU/GPU ONNX Runtime
    metadata and an effective imported-module status.  This avoids misleading
    frozen-package summaries where distribution metadata may be absent while
    the imported ONNX Runtime module still exposes CUDAExecutionProvider.
    """
    result = runtime_preflight(**kwargs)
    packages = {item.name: item for item in result.package_statuses}
    onnx_cpu = packages.get("onnxruntime")
    onnx_gpu = packages.get("onnxruntime-gpu")
    if result.gpu.cuda_provider_available:
        onnx_status = onnx_gpu or onnx_cpu
    else:
        onnx_status = onnx_cpu or onnx_gpu
    try:
        from .frozen_runtime import frozen_runtime_summary

        frozen = frozen_runtime_summary()
    except Exception:
        frozen = {}

    metadata_note = ""
    if result.gpu.onnxruntime_import_ok and result.gpu.cuda_provider_available and (onnx_gpu is None or not onnx_gpu.installed):
        metadata_note = (
            "onnxruntime-gpu distribution metadata is not visible, but the imported ONNX Runtime "
            "module exposes CUDAExecutionProvider. In a frozen portable build this can be a metadata "
            "visibility issue rather than a GPU failure."
        )

    return {
        "ok": result.ok,
        "version": result.version,
        "refactor_stage": result.refactor_stage,
        "python_executable": result.python_executable,
        "python_version": result.python_version.split()[0] if result.python_version else "",
        "missing_required": list(result.missing_required),
        "onnxruntime": onnx_status.to_dict() if onnx_status is not None else None,
        "onnxruntime_package": onnx_cpu.to_dict() if onnx_cpu is not None else None,
        "onnxruntime_gpu_package": onnx_gpu.to_dict() if onnx_gpu is not None else None,
        "onnxruntime_effective": {
            "import_ok": result.gpu.onnxruntime_import_ok,
            "module_version": result.gpu.onnxruntime_version,
            "module_location": result.gpu.onnxruntime_location,
            "providers": list(result.gpu.onnx_providers),
        },
        "runtime_profile_detected": "gpu-cuda" if result.gpu.cuda_provider_available else "cpu",
        "metadata_note": metadata_note,
        "cuda_provider_available": result.gpu.cuda_provider_available,
        "onnx_providers": list(result.gpu.onnx_providers),
        "nvidia_gpu": result.gpu.nvidia_gpu,
        "frozen": frozen,
        "warnings": list(result.warnings),
        "errors": list(result.errors),
    }


__all__ = [
    "PREFLIGHT_SCHEMA_VERSION",
    "CORE_DISTRIBUTIONS",
    "OPTIONAL_DISTRIBUTIONS",
    "GPU_DISTRIBUTIONS",
    "NATIVE_LIBRARY_DISTRIBUTIONS",
    "PackageStatus",
    "GpuPreflightStatus",
    "RuntimePreflightResult",
    "package_status",
    "collect_package_statuses",
    "gpu_preflight",
    "runtime_preflight",
    "runtime_preflight_summary",
]
