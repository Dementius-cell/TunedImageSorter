# -*- coding: utf-8 -*-
"""GPU Lite first-run runtime bootstrap helpers.

v69.6 / Этап 055 adds an experimental GPU Lite package that does not bundle
``_internal\\nvidia``.  The stable full GPU portable package remains unchanged.

This module is intentionally import-safe: it uses only Python stdlib until an
interactive GUI prompt is explicitly requested.  It checks for a local NVIDIA
GPU/driver and for the pinned CUDA 12 runtime DLLs required by
``onnxruntime-gpu==1.26.0``.  With user consent it downloads pinned NVIDIA
wheel files from PyPI and extracts only native DLLs into a per-user cache under
``%LOCALAPPDATA%\\TunedImageSorter\\gpu_lite_runtime``.

It does not install system-wide drivers, does not require administrator rights,
does not modify the stable full GPU package and does not change ML/pipeline
behaviour.
"""
from __future__ import annotations

import contextlib
import dataclasses
import datetime as dt
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .constants import SCRIPT_VERSION

GPU_LITE_SCHEMA_VERSION = 1
GPU_LITE_STAGE = "Этап 055"
GPU_LITE_RUNTIME_ID = "cuda12_ort126_v69_3_1"
GPU_LITE_INSTALL_MARKER = "gpu_lite_runtime_install.json"
GPU_LITE_ENV_DIR = "FACE_SORTER_GPU_LITE_RUNTIME_DIR"
GPU_LITE_ENV_DISABLE_PROMPT = "FACE_SORTER_GPU_LITE_NO_PROMPT"
GPU_LITE_ENV_ASSUME_YES = "FACE_SORTER_GPU_LITE_ASSUME_YES"

GpuLiteProgressCallback = Callable[[Dict[str, Any]], None]

# Pinned to the same CUDA 12 runtime family that the confirmed full GPU package
# bundles.  The installer downloads wheels from PyPI metadata at first run and
# extracts only DLL files, not Python packages.
GPU_LITE_RUNTIME_PACKAGES: Tuple[Tuple[str, str], ...] = (
    ("nvidia-cuda-runtime-cu12", "12.9.79"),
    ("nvidia-cudnn-cu12", "9.23.1.3"),
    ("nvidia-cublas-cu12", "12.9.2.10"),
    ("nvidia-cuda-nvrtc-cu12", "12.9.86"),
    ("nvidia-cufft-cu12", "11.4.1.4"),
    ("nvidia-curand-cu12", "10.3.10.19"),
    ("nvidia-nvjitlink-cu12", "12.9.86"),
)

GPU_LITE_REQUIRED_DLL_PATTERNS: Tuple[str, ...] = (
    "cudart64_12.dll",
    "cublas64_12.dll",
    "cublasLt64_12.dll",
    "cudnn64_9.dll",
    "nvrtc64_*.dll",
    "cufft64_*.dll",
    "curand64_*.dll",
    "nvJitLink*.dll",
)

_DLL_DIRECTORY_HANDLES: List[Any] = []
_DLL_DIRECTORIES_ACTIVATED = False


@dataclass(frozen=True)
class GpuLiteRuntimeStatus:
    """Serializable GPU Lite runtime status."""

    ok: bool
    is_gpu_lite_package: bool
    version: str
    refactor_stage: str
    runtime_id: str
    runtime_dir: str
    nvidia_driver_found: bool
    nvidia_gpu: str = ""
    nvidia_driver: str = ""
    required_patterns: Tuple[str, ...] = GPU_LITE_REQUIRED_DLL_PATTERNS
    found_dlls: Dict[str, Tuple[str, ...]] = field(default_factory=dict)
    missing_patterns: Tuple[str, ...] = ()
    install_marker_exists: bool = False
    errors: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        data = dataclasses.asdict(self)
        data["required_patterns"] = list(self.required_patterns)
        data["missing_patterns"] = list(self.missing_patterns)
        data["found_dlls"] = {k: list(v) for k, v in self.found_dlls.items()}
        return data


@dataclass(frozen=True)
class GpuLiteInstallResult:
    """Serializable result of a local GPU Lite runtime install attempt."""

    ok: bool
    version: str
    refactor_stage: str
    runtime_id: str
    runtime_dir: str
    downloaded_packages: Tuple[str, ...] = ()
    extracted_files: Tuple[str, ...] = ()
    errors: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


def _windows_no_window_creationflags() -> int:
    if os.name != "nt":
        return 0
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))


def app_dir() -> Path:
    """Return the folder that contains the frozen EXE or the source root."""
    try:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
    except Exception:
        pass
    return Path(__file__).resolve().parents[2]


def is_gpu_lite_package(package_dir: Optional[str | Path] = None) -> bool:
    """Return True when running from / checking the experimental GPU Lite package."""
    if os.environ.get("FACE_SORTER_FORCE_GPU_LITE", "").strip() in {"1", "true", "yes"}:
        return True
    base = Path(package_dir).expanduser().resolve() if package_dir is not None else app_dir()
    if "gpu_lite" in base.name.lower() or "gpu-lite" in base.name.lower():
        return True
    manifest = base / "portable_manifest.json"
    if manifest.exists():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8-sig"))
            return str(data.get("profile", "")).lower() == "gpu-lite"
        except Exception:
            return False
    return False


def gpu_lite_runtime_dir() -> Path:
    """Return the primary per-user local runtime cache directory."""
    override = os.environ.get(GPU_LITE_ENV_DIR, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
        return Path(root) / "TunedImageSorter" / "gpu_lite_runtime" / GPU_LITE_RUNTIME_ID
    return Path.home() / ".tuned_image_sorter" / "gpu_lite_runtime" / GPU_LITE_RUNTIME_ID


def gpu_lite_legacy_runtime_dirs() -> Tuple[Path, ...]:
    """Return compatibility runtime caches created before the public rename."""
    if os.environ.get(GPU_LITE_ENV_DIR, "").strip():
        return ()
    out: List[Path] = []
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home()))
        # v69.6 rebrand: prefer the new TunedImageSorter path, but allow already
        # downloaded pre-rename FaceSorterMVP caches to satisfy DLL lookup so
        # existing users do not have to download the same pinned runtime again.
        old_parent = root / "FaceSorterMVP" / "gpu_lite_runtime"
        out.append(old_parent / GPU_LITE_RUNTIME_ID)
        if old_parent.exists():
            for item in old_parent.glob("cuda12_ort126_v69_*"):
                if item.is_dir():
                    out.append(item)
    else:
        old_parent = Path.home() / ".face_sorter_mvp" / "gpu_lite_runtime"
        out.append(old_parent / GPU_LITE_RUNTIME_ID)
        if old_parent.exists():
            for item in old_parent.glob("cuda12_ort126_v69_*"):
                if item.is_dir():
                    out.append(item)
    primary = gpu_lite_runtime_dir()
    unique: List[Path] = []
    seen = {str(primary)}
    for item in out:
        key = str(item)
        if key not in seen:
            unique.append(item)
            seen.add(key)
    return tuple(unique)


def _run_nvidia_smi() -> Tuple[bool, str, str, str]:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return False, "", "", "nvidia-smi not found"
    try:
        proc = subprocess.run(
            [exe, "--query-gpu=name,driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
            creationflags=_windows_no_window_creationflags(),
        )
        if proc.returncode != 0:
            return True, "", "", (proc.stderr or proc.stdout or "nvidia-smi returned non-zero exit code").strip()
        first = (proc.stdout or "").strip().splitlines()[0] if proc.stdout else ""
        if not first:
            return True, "", "", "nvidia-smi returned no GPU rows"
        parts = [part.strip() for part in first.split(",", 1)]
        return True, parts[0] if parts else "", parts[1] if len(parts) > 1 else "", ""
    except Exception as exc:
        return True, "", "", f"nvidia-smi error: {type(exc).__name__}: {exc}"


def _candidate_roots(package_dir: Optional[str | Path] = None, runtime_dir: Optional[str | Path] = None) -> Tuple[Path, ...]:
    base = Path(package_dir).expanduser().resolve() if package_dir is not None else app_dir()
    runtime = Path(runtime_dir).expanduser().resolve() if runtime_dir is not None else gpu_lite_runtime_dir()
    runtime_roots = [runtime, *gpu_lite_legacy_runtime_dirs()]
    roots: List[Path] = []
    for item in runtime_roots:
        roots.append(item)
        roots.append(item / "nvidia")
    roots.extend([base / "_internal", base / "_internal" / "nvidia", base])
    # PATH lookup keeps the checker honest if a user already has the DLLs in a
    # controlled corporate/runtime folder.  Do not scan the entire disk.
    for item in os.environ.get("PATH", "").split(os.pathsep):
        if item:
            roots.append(Path(item))
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
    return tuple(out)


def find_gpu_lite_runtime_dlls(
    *,
    package_dir: Optional[str | Path] = None,
    runtime_dir: Optional[str | Path] = None,
) -> Dict[str, Tuple[str, ...]]:
    """Find the CUDA DLLs required by the GPU Lite package."""
    found: Dict[str, List[str]] = {pattern: [] for pattern in GPU_LITE_REQUIRED_DLL_PATTERNS}
    for root in _candidate_roots(package_dir=package_dir, runtime_dir=runtime_dir):
        if not root.exists():
            continue
        # Known trees are small.  PATH entries are scanned one level by glob to
        # avoid accidentally walking large user folders.
        recursive = root == gpu_lite_runtime_dir() or root in gpu_lite_legacy_runtime_dirs() or root.name.lower() in {"nvidia", "_internal"}
        for pattern in GPU_LITE_REQUIRED_DLL_PATTERNS:
            try:
                iterator = root.rglob(pattern) if recursive else root.glob(pattern)
                for path in iterator:
                    if path.is_file():
                        text = str(path.resolve())
                        if text not in found[pattern]:
                            found[pattern].append(text)
            except Exception:
                continue
    return {pattern: tuple(paths[:16]) for pattern, paths in found.items() if paths}


def gpu_lite_runtime_status(package_dir: Optional[str | Path] = None) -> GpuLiteRuntimeStatus:
    """Check whether the GPU Lite runtime is already usable on this computer."""
    runtime = gpu_lite_runtime_dir()
    found = find_gpu_lite_runtime_dlls(package_dir=package_dir, runtime_dir=runtime)
    missing = tuple(pattern for pattern in GPU_LITE_REQUIRED_DLL_PATTERNS if not found.get(pattern))
    nvidia_found, gpu_name, driver, driver_error = _run_nvidia_smi()
    errors: List[str] = []
    warnings: List[str] = []
    if not is_gpu_lite_package(package_dir):
        warnings.append("not a GPU Lite package")
    if not nvidia_found:
        errors.append("NVIDIA driver/GPU not detected through nvidia-smi")
    elif driver_error:
        warnings.append(driver_error)
    if missing:
        errors.append("missing CUDA runtime DLLs: " + ", ".join(missing))
    marker = runtime / GPU_LITE_INSTALL_MARKER
    return GpuLiteRuntimeStatus(
        ok=nvidia_found and not missing,
        is_gpu_lite_package=is_gpu_lite_package(package_dir),
        version=SCRIPT_VERSION,
        refactor_stage=GPU_LITE_STAGE,
        runtime_id=GPU_LITE_RUNTIME_ID,
        runtime_dir=str(runtime),
        nvidia_driver_found=nvidia_found,
        nvidia_gpu=gpu_name,
        nvidia_driver=driver,
        found_dlls=found,
        missing_patterns=missing,
        install_marker_exists=marker.exists(),
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def activate_gpu_lite_runtime_paths(package_dir: Optional[str | Path] = None) -> Tuple[str, ...]:
    """Add installed GPU Lite runtime DLL directories to the process search path."""
    global _DLL_DIRECTORIES_ACTIVATED
    if _DLL_DIRECTORIES_ACTIVATED:
        return ()
    dirs: List[Path] = []
    found = find_gpu_lite_runtime_dlls(package_dir=package_dir)
    for paths in found.values():
        for text in paths:
            p = Path(text).parent
            if p not in dirs:
                dirs.append(p)
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
    _DLL_DIRECTORIES_ACTIVATED = True
    return tuple(added)


def _pypi_json_url(name: str, version: str) -> str:
    return f"https://pypi.org/pypi/{name}/{version}/json"


def _select_windows_wheel(files: Sequence[Dict[str, Any]]) -> Tuple[str, str, int]:
    candidates: List[Tuple[str, str, int]] = []
    for item in files:
        filename = str(item.get("filename") or "")
        url = str(item.get("url") or "")
        packagetype = str(item.get("packagetype") or "")
        if not filename.endswith(".whl") or packagetype != "bdist_wheel" or not url:
            continue
        if "win_amd64" not in filename:
            continue
        try:
            size = int(item.get("size") or 0)
        except Exception:
            size = 0
        candidates.append((filename, url, size))
    if not candidates:
        raise RuntimeError("No win_amd64 wheel found in PyPI metadata")
    # Prefer py3-none-win_amd64 native wheels, but accept cp wheels if metadata
    # changes in future pinned uploads.
    candidates.sort(key=lambda pair: (0 if "py3-none-win_amd64" in pair[0] else 1, pair[0]))
    return candidates[0]


def _emit_progress(progress_callback: Optional[GpuLiteProgressCallback], **payload: Any) -> None:
    if progress_callback is None:
        return
    try:
        progress_callback(payload)
    except Exception:
        # Progress reporting must never break the runtime installer.
        pass


def _format_bytes(size: int) -> str:
    value = float(max(0, size))
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024.0 or unit == "GiB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} GiB"


def _download(
    url: str,
    dest: Path,
    *,
    timeout: int = 120,
    progress_callback: Optional[GpuLiteProgressCallback] = None,
    package_label: str = "",
    package_index: int = 0,
    package_count: int = 0,
    downloaded_before: int = 0,
    total_size: int = 0,
) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": f"TunedImageSorter/{SCRIPT_VERSION} GPU-Lite"})
    started = time.monotonic()
    last_emit = 0.0
    local_downloaded = 0
    with urllib.request.urlopen(request, timeout=timeout) as response, dest.open("wb") as fh:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            fh.write(chunk)
            local_downloaded += len(chunk)
            now = time.monotonic()
            if now - last_emit >= 0.2:
                elapsed = max(0.001, now - started)
                global_downloaded = downloaded_before + local_downloaded
                _emit_progress(
                    progress_callback,
                    phase="download",
                    package=package_label,
                    package_index=package_index,
                    package_count=package_count,
                    downloaded_bytes=global_downloaded,
                    total_bytes=total_size,
                    speed_bytes_per_sec=int(local_downloaded / elapsed),
                    downloaded_text=_format_bytes(global_downloaded),
                    total_text=_format_bytes(total_size) if total_size else "unknown",
                    speed_text=f"{_format_bytes(int(local_downloaded / elapsed))}/s",
                )
                last_emit = now
    elapsed = max(0.001, time.monotonic() - started)
    _emit_progress(
        progress_callback,
        phase="download",
        package=package_label,
        package_index=package_index,
        package_count=package_count,
        downloaded_bytes=downloaded_before + local_downloaded,
        total_bytes=total_size,
        speed_bytes_per_sec=int(local_downloaded / elapsed),
        downloaded_text=_format_bytes(downloaded_before + local_downloaded),
        total_text=_format_bytes(total_size) if total_size else "unknown",
        speed_text=f"{_format_bytes(int(local_downloaded / elapsed))}/s",
    )


def _wheel_url_from_pypi(name: str, version: str) -> Tuple[str, str, int]:
    with urllib.request.urlopen(_pypi_json_url(name, version), timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    urls = payload.get("urls")
    if not isinstance(urls, list):
        raise RuntimeError("PyPI metadata has no urls list")
    return _select_windows_wheel(urls)


def _extract_runtime_dlls_from_wheel(wheel_path: Path, target_dir: Path) -> Tuple[str, ...]:
    extracted: List[str] = []
    with zipfile.ZipFile(wheel_path, "r") as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if info.is_dir():
                continue
            lower = name.lower()
            if not lower.startswith("nvidia/") or not lower.endswith(".dll"):
                continue
            # Keep the package directory structure under the cache so DLL search
            # paths can be added narrowly and diagnostics remain transparent.
            dest = target_dir / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, dest.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            extracted.append(str(dest))
    return tuple(extracted)


def install_gpu_lite_runtime(*, assume_yes: bool = False, progress_callback: Optional[GpuLiteProgressCallback] = None) -> GpuLiteInstallResult:
    """Download pinned NVIDIA wheels and extract local CUDA runtime DLLs."""
    runtime = gpu_lite_runtime_dir()
    downloaded: List[str] = []
    extracted: List[str] = []
    errors: List[str] = []
    warnings: List[str] = []
    if not assume_yes and os.environ.get(GPU_LITE_ENV_ASSUME_YES, "").strip().lower() not in {"1", "true", "yes"}:
        errors.append("install_gpu_lite_runtime requires explicit user consent")
        return GpuLiteInstallResult(False, SCRIPT_VERSION, GPU_LITE_STAGE, GPU_LITE_RUNTIME_ID, str(runtime), tuple(downloaded), tuple(extracted), tuple(errors), tuple(warnings))
    try:
        runtime.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="face_sorter_gpu_lite_") as tmp_name:
            tmp = Path(tmp_name)
            plan: List[Tuple[str, str, str, str, int]] = []
            _emit_progress(progress_callback, phase="metadata", message="Resolving pinned wheel metadata")
            for name, version in GPU_LITE_RUNTIME_PACKAGES:
                wheel_name, url, size = _wheel_url_from_pypi(name, version)
                plan.append((name, version, wheel_name, url, size))
            total_size = sum(size for _name, _version, _wheel_name, _url, size in plan)
            downloaded_bytes = 0
            package_count = len(plan)
            for package_index, (name, version, wheel_name, url, size) in enumerate(plan, start=1):
                wheel_path = tmp / wheel_name
                package_label = f"{name}=={version}"
                _emit_progress(
                    progress_callback,
                    phase="download",
                    package=package_label,
                    package_index=package_index,
                    package_count=package_count,
                    downloaded_bytes=downloaded_bytes,
                    total_bytes=total_size,
                    downloaded_text=_format_bytes(downloaded_bytes),
                    total_text=_format_bytes(total_size) if total_size else "unknown",
                    speed_text="starting",
                )
                _download(
                    url,
                    wheel_path,
                    progress_callback=progress_callback,
                    package_label=package_label,
                    package_index=package_index,
                    package_count=package_count,
                    downloaded_before=downloaded_bytes,
                    total_size=total_size,
                )
                downloaded_bytes += size or wheel_path.stat().st_size
                downloaded.append(package_label)
                _emit_progress(
                    progress_callback,
                    phase="extract",
                    package=package_label,
                    package_index=package_index,
                    package_count=package_count,
                    downloaded_bytes=downloaded_bytes,
                    total_bytes=total_size,
                    downloaded_text=_format_bytes(downloaded_bytes),
                    total_text=_format_bytes(total_size) if total_size else "unknown",
                    speed_text="extracting",
                )
                extracted.extend(_extract_runtime_dlls_from_wheel(wheel_path, runtime))
        _emit_progress(progress_callback, phase="verify", message="Checking extracted CUDA runtime DLLs")
        status = gpu_lite_runtime_status()
        marker = {
            "schema_version": GPU_LITE_SCHEMA_VERSION,
            "version": SCRIPT_VERSION,
            "refactor_stage": GPU_LITE_STAGE,
            "runtime_id": GPU_LITE_RUNTIME_ID,
            "created_at_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "packages": [f"{name}=={version}" for name, version in GPU_LITE_RUNTIME_PACKAGES],
            "status": status.to_dict(),
        }
        (runtime / GPU_LITE_INSTALL_MARKER).write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
        activate_gpu_lite_runtime_paths()
        if not status.ok:
            errors.extend(status.errors)
            warnings.extend(status.warnings)
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    return GpuLiteInstallResult(
        ok=not errors,
        version=SCRIPT_VERSION,
        refactor_stage=GPU_LITE_STAGE,
        runtime_id=GPU_LITE_RUNTIME_ID,
        runtime_dir=str(runtime),
        downloaded_packages=tuple(downloaded),
        extracted_files=tuple(extracted[:200]),
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def ensure_gpu_lite_runtime_interactive(package_dir: Optional[str | Path] = None) -> GpuLiteRuntimeStatus:
    """GUI first-run check: ask permission before installing missing runtime DLLs."""
    if not is_gpu_lite_package(package_dir):
        return gpu_lite_runtime_status(package_dir)
    activate_gpu_lite_runtime_paths(package_dir)
    status = gpu_lite_runtime_status(package_dir)
    if status.ok:
        return status
    if os.environ.get(GPU_LITE_ENV_DISABLE_PROMPT, "").strip().lower() in {"1", "true", "yes"}:
        return status
    try:
        from PySide6 import QtWidgets  # type: ignore
    except Exception:
        return status

    app = QtWidgets.QApplication.instance()
    owns_app = False
    if app is None:
        app = QtWidgets.QApplication([])
        owns_app = True
        try:
            app.setProperty("face_sorter_temp_gpu_lite_app", True)
        except Exception:
            pass
    try:
        if not status.nvidia_driver_found:
            QtWidgets.QMessageBox.warning(
                None,
                "Tuned Image Sorter GPU Lite",
                "GPU Lite не нашёл NVIDIA driver / nvidia-smi.\n\n"
                "Установите актуальный NVIDIA driver или используйте CPU / full GPU portable version.\n\n"
                "GPU Lite did not detect NVIDIA driver / nvidia-smi.",
            )
            return status
        text = (
            "GPU Lite не содержит встроенную папку _internal\\nvidia.\n\n"
            "Для GPU-режима нужно скачать pinned CUDA 12 runtime DLLs "
            "в локальную папку пользователя:\n"
            f"{gpu_lite_runtime_dir()}\n\n"
            "Системные драйверы и Python-пакеты изменяться не будут. "
            "Нужен интернет. Скачать и установить локальный runtime сейчас?\n\n"
            "GPU Lite does not bundle _internal\\nvidia. Download and install the local pinned CUDA 12 runtime now?"
        )
        answer = QtWidgets.QMessageBox.question(
            None,
            "Tuned Image Sorter GPU Lite — first run setup",
            text,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if answer != QtWidgets.QMessageBox.Yes:
            return status
        progress = QtWidgets.QProgressDialog(
            "GPU Lite runtime setup: downloading pinned CUDA 12 runtime files...\n"
            "This can take several minutes on the first run.\n"
            "The window remains active while download/extract is running.",
            "Cancel",
            0,
            0,
            None,
        )
        progress.setWindowTitle("Tuned Image Sorter GPU Lite — installing runtime")
        progress.setMinimumDuration(0)
        progress.setCancelButton(None)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.show()
        app.processEvents()

        result_holder: Dict[str, GpuLiteInstallResult] = {}
        progress_state: Dict[str, Any] = {"phase": "starting"}
        progress_lock = threading.Lock()

        def _progress_callback(payload: Dict[str, Any]) -> None:
            with progress_lock:
                progress_state.clear()
                progress_state.update(payload)

        def _worker() -> None:
            result_holder["result"] = install_gpu_lite_runtime(assume_yes=True, progress_callback=_progress_callback)

        worker = threading.Thread(target=_worker, name="FaceSorterGPU-LiteRuntimeSetup", daemon=True)
        worker.start()
        last_label = ""
        while worker.is_alive():
            with progress_lock:
                state = dict(progress_state)
            phase = str(state.get("phase") or "running")
            total_bytes = int(state.get("total_bytes") or 0)
            downloaded_bytes = int(state.get("downloaded_bytes") or 0)
            if total_bytes > 0:
                progress.setRange(0, 100)
                progress.setValue(max(0, min(100, int(downloaded_bytes * 100 / total_bytes))))
            else:
                progress.setRange(0, 0)
            if phase == "download":
                label = (
                    "GPU Lite runtime setup is downloading CUDA 12 DLL packages...\n"
                    f"Package {state.get('package_index', 0)}/{state.get('package_count', 0)}: {state.get('package', '')}\n"
                    f"Downloaded: {state.get('downloaded_text', '')} / {state.get('total_text', 'unknown')} | Speed: {state.get('speed_text', '')}\n"
                    "Please wait; do not close the application."
                )
            elif phase == "extract":
                label = (
                    "GPU Lite runtime setup is extracting CUDA 12 DLLs...\n"
                    f"Package {state.get('package_index', 0)}/{state.get('package_count', 0)}: {state.get('package', '')}\n"
                    f"Progress: {state.get('downloaded_text', '')} / {state.get('total_text', 'unknown')}\n"
                    "Please wait; do not close the application."
                )
            elif phase == "metadata":
                label = (
                    "GPU Lite runtime setup is resolving pinned package metadata...\n"
                    "Internet connection is required on the first run.\n"
                    "Please wait; do not close the application."
                )
            elif phase == "verify":
                label = (
                    "GPU Lite runtime setup is verifying extracted CUDA 12 DLLs...\n"
                    "Please wait; do not close the application."
                )
            else:
                label = (
                    "GPU Lite runtime setup is starting...\n"
                    "Please wait; do not close the application."
                )
            if label != last_label:
                progress.setLabelText(label)
                last_label = label
            app.processEvents()
            time.sleep(0.1)
        worker.join(timeout=0.1)
        result = result_holder.get(
            "result",
            GpuLiteInstallResult(
                False, SCRIPT_VERSION, GPU_LITE_STAGE, GPU_LITE_RUNTIME_ID, str(gpu_lite_runtime_dir()),
                errors=("GPU Lite runtime setup worker did not return a result",),
            ),
        )
        progress.close()
        app.processEvents()
        if result.ok:
            QtWidgets.QMessageBox.information(
                None,
                "Tuned Image Sorter GPU Lite",
                "GPU Lite runtime установлен локально.\n\n"
                "После OK приложение продолжит запуск автоматически. "
                "Далее можно выполнить Проверку окружения и GPU-сортировку.\n\n"
                "GPU Lite runtime was installed locally. The application will continue starting after OK.",
            )
        else:
            QtWidgets.QMessageBox.warning(
                None,
                "Tuned Image Sorter GPU Lite",
                "GPU Lite runtime не удалось установить.\n\n"
                + "\n".join(result.errors[:5])
                + "\n\nМожно использовать CPU или full GPU portable version.",
            )
        activate_gpu_lite_runtime_paths(package_dir)
        return gpu_lite_runtime_status(package_dir)
    finally:
        # Do not quit a pre-existing application instance.  If we created a
        # temporary QApplication, PySide will clean it up when the process exits.
        if owns_app:
            pass


__all__ = [
    "GPU_LITE_RUNTIME_PACKAGES",
    "GPU_LITE_REQUIRED_DLL_PATTERNS",
    "GpuLiteRuntimeStatus",
    "GpuLiteInstallResult",
    "activate_gpu_lite_runtime_paths",
    "ensure_gpu_lite_runtime_interactive",
    "find_gpu_lite_runtime_dlls",
    "gpu_lite_runtime_dir",
    "gpu_lite_legacy_runtime_dirs",
    "gpu_lite_runtime_status",
    "install_gpu_lite_runtime",
    "is_gpu_lite_package",
]
