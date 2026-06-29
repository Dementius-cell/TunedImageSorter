# -*- coding: utf-8 -*-
"""Frozen-runtime diagnostics for Windows one-folder builds.

This module is import-safe until a diagnostic function is called.  It is used by
``TunedImageSorter.exe --scan-probe`` and by scan-stage diagnostics to answer one
specific packaging question: can the frozen executable load InsightFace, decode
real input images, run the detector, and produce embeddings?
"""
from __future__ import annotations

import datetime as _dt
import importlib
import importlib.metadata
import os
import platform
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .constants import DEFAULT_MODEL, IMAGE_EXTENSIONS, SCRIPT_VERSION
from .frozen_runtime import frozen_runtime_summary

FROZEN_DIAGNOSTICS_SCHEMA_VERSION = 4

_IMPORT_CHECKS = {
    "Pillow": "PIL",
    "opencv-python": "cv2",
    "numpy": "numpy",
    "insightface": "insightface",
    "onnxruntime": "onnxruntime",
    "onnxruntime-gpu": "onnxruntime",
    "scikit-learn": "sklearn",
    "hdbscan": "hdbscan",
    "pillow-heif": "pillow_heif",
}

_NATIVE_METADATA_CHECKS = (
    "nvidia-cuda-runtime-cu12",
    "nvidia-cudnn-cu12",
    "nvidia-cublas-cu12",
    "nvidia-cuda-nvrtc-cu12",
    "nvidia-cufft-cu12",
    "nvidia-curand-cu12",
    "nvidia-nvjitlink-cu12",
)

_NATIVE_DLL_PATTERNS = {
    "nvidia-cuda-runtime-cu12": ("cudart64_12.dll",),
    "nvidia-cudnn-cu12": ("cudnn64_9.dll", "cudnn_ops64_9.dll", "cudnn_engines_tensor_ir64_9.dll"),
    "nvidia-cublas-cu12": ("cublas64_12.dll", "cublasLt64_12.dll"),
    "nvidia-cuda-nvrtc-cu12": ("nvrtc64_*.dll",),
    "nvidia-cufft-cu12": ("cufft64_*.dll",),
    "nvidia-curand-cu12": ("curand64_*.dll",),
    "nvidia-nvjitlink-cu12": ("nvJitLink*.dll", "nvjitlink*.dll"),
}


def _safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _float_scalar(value: Any, default: float = 0.0) -> float:
    """Convert numpy/Python scalar-like values without boolean coercion."""
    if value is None:
        return float(default)
    try:
        if hasattr(value, "tolist"):
            value = value.tolist()
        if isinstance(value, (list, tuple)):
            value = value[0] if value else default
        return float(value)
    except Exception:
        return float(default)


def _float_list(value: Any, *, max_items: Optional[int] = None) -> List[float]:
    """Convert numpy arrays/lists to floats without using ``value or []``.

    A numpy array intentionally raises ValueError when used as a boolean.  The
    v64.7 frozen probe used ``bbox_array or []`` and therefore reported
    ``faces_total=0`` even after InsightFace had already returned faces.
    """
    if value is None:
        return []
    try:
        if hasattr(value, "tolist"):
            value = value.tolist()
        if isinstance(value, (str, bytes)):
            return []
        try:
            items = list(value)
        except TypeError:
            items = [value]
        out: List[float] = []
        for item in items:
            if max_items is not None and len(out) >= int(max_items):
                break
            try:
                out.append(float(item))
            except Exception:
                continue
        return out
    except Exception:
        return []


def _face_sequence(value: Any) -> List[Any]:
    """Return a list of InsightFace face objects without boolean coercion."""
    if value is None:
        return []
    try:
        return list(value)
    except TypeError:
        return [value]


def _dist_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except Exception:
        return ""


def _import_status(module_name: str) -> Dict[str, Any]:
    try:
        mod = importlib.import_module(module_name)
        return {
            "ok": True,
            "module": module_name,
            "file": str(getattr(mod, "__file__", "") or ""),
            "version": str(getattr(mod, "__version__", "") or ""),
        }
    except Exception as exc:
        return {"ok": False, "module": module_name, "error": f"{type(exc).__name__}: {exc}"}


def package_import_snapshot() -> Dict[str, Any]:
    """Return metadata+import facts without shelling out to pip."""
    rows: Dict[str, Any] = {}
    for dist_name, module_name in _IMPORT_CHECKS.items():
        rows[dist_name] = {
            "distribution_version": _dist_version(dist_name),
            "import": _import_status(module_name),
        }
    dlls = _cuda_runtime_dll_snapshot().get("dlls", {})
    for dist_name in _NATIVE_METADATA_CHECKS:
        version = _dist_version(dist_name)
        inferred_paths = [path for pattern in _NATIVE_DLL_PATTERNS.get(dist_name, ()) for path in dlls.get(pattern, [])]
        rows[dist_name] = {
            "distribution_version": version or ("bundled" if inferred_paths else ""),
            "import": {
                "ok": None,
                "module": "",
                "note": "native DLL wheel; metadata-only check",
                "bundled_paths": inferred_paths[:6],
            },
        }
    return rows


def _onnx_providers() -> List[str]:
    try:
        try:
            from .preflight import _add_native_dll_directories_light

            _add_native_dll_directories_light()
        except Exception:
            pass
        import onnxruntime as ort  # type: ignore
        preload = getattr(ort, "preload_dlls", None)
        if callable(preload):
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
        return list(ort.get_available_providers())
    except Exception:
        return []


def _cuda_runtime_dll_snapshot() -> Dict[str, Any]:
    try:
        from .preflight import _find_cuda_runtime_dlls_light  # import-safe helper

        dlls = _find_cuda_runtime_dlls_light()
        return {
            "ok": bool(dlls),
            "patterns_found": sorted(dlls.keys()),
            "dlls": {key: list(value) for key, value in dlls.items()},
        }
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "dlls": {}}


def _iter_images(input_dir: Path, limit: int) -> List[Path]:
    out: List[Path] = []
    try:
        for root, _dirs, files in os.walk(input_dir):
            for name in files:
                p = Path(root) / name
                if p.suffix.lower() in IMAGE_EXTENSIONS:
                    out.append(p)
                    if len(out) >= limit:
                        return out
    except Exception:
        pass
    return out


def _model_pack_snapshot(model: str) -> Dict[str, Any]:
    base = Path.home() / ".insightface" / "models"
    pack = base / str(model)
    files = []
    if pack.exists():
        try:
            for fp in sorted(pack.rglob("*")):
                if fp.is_file():
                    try:
                        files.append({"path": str(fp.relative_to(pack)), "size_bytes": fp.stat().st_size})
                    except Exception:
                        files.append({"path": str(fp), "size_bytes": None})
        except Exception as exc:
            files.append({"error": f"{type(exc).__name__}: {exc}"})
    return {
        "models_root": str(base),
        "pack_dir": str(pack),
        "pack_exists": pack.exists(),
        "onnx_files": [row for row in files if str(row.get("path", "")).lower().endswith(".onnx")][:50],
        "files_count": len(files),
    }


def _face_app_summary(app: Any) -> Dict[str, Any]:
    models = getattr(app, "models", {}) or {}
    rows: Dict[str, Any] = {}
    providers: List[str] = []
    for key, model_obj in models.items():
        session = getattr(model_obj, "session", None)
        sess_providers: List[str] = []
        if session is not None and hasattr(session, "get_providers"):
            try:
                sess_providers = list(session.get_providers())
                for provider in sess_providers:
                    if provider not in providers:
                        providers.append(provider)
            except Exception:
                pass
        rows[str(key)] = {
            "class": type(model_obj).__name__,
            "taskname": str(getattr(model_obj, "taskname", "") or ""),
            "input_shape": str(getattr(model_obj, "input_shape", "") or ""),
            "providers": sess_providers,
        }
    return {"model_keys": sorted(str(k) for k in models.keys()), "models": rows, "providers": providers}



def insightface_runtime_objects_snapshot() -> Dict[str, Any]:
    """Return facts about root-level InsightFace runtime data bundled by PyInstaller."""
    candidates: List[Path] = []
    try:
        from .frozen_runtime import bundle_internal_dir, app_base_dir
        candidates.extend([
            bundle_internal_dir() / "objects" / "meanshape_68.pkl",
            app_base_dir() / "objects" / "meanshape_68.pkl",
            Path.cwd() / "objects" / "meanshape_68.pkl",
        ])
    except Exception:
        candidates.append(Path("objects") / "meanshape_68.pkl")
    rows = []
    for path in candidates:
        try:
            rows.append({"path": str(path), "exists": path.exists(), "size_bytes": path.stat().st_size if path.exists() else None})
        except Exception as exc:
            rows.append({"path": str(path), "exists": False, "error": f"{type(exc).__name__}: {exc}"})
    return {"meanshape_68_candidates": rows, "ok": any(bool(row.get("exists")) for row in rows)}

def run_scan_probe(input_dir: str | os.PathLike[str], *, model: str = DEFAULT_MODEL, det_size: int = 640, use_gpu: bool = False, max_images: int = 5) -> Dict[str, Any]:
    """Run a bounded real-image InsightFace probe and return JSON diagnostics."""
    created_at = _dt.datetime.now().isoformat(timespec="seconds")
    root = Path(input_dir).expanduser().resolve()
    result: Dict[str, Any] = {
        "schema_version": FROZEN_DIAGNOSTICS_SCHEMA_VERSION,
        "version": SCRIPT_VERSION,
        "created_at": created_at,
        "input_dir": str(root),
        "model": str(model),
        "det_size": int(det_size or 640),
        "use_gpu": bool(use_gpu),
        "python": {"executable": sys.executable, "version": sys.version.replace("\n", " "), "platform": platform.platform()},
        "frozen_runtime": frozen_runtime_summary(),
        "packages": package_import_snapshot(),
        "onnx_providers": _onnx_providers(),
        "cuda_runtime_dlls": _cuda_runtime_dll_snapshot(),
        "gpu_provider_status": {
            "requested": bool(use_gpu),
            "cuda_execution_provider_available": False,
            "active_face_app_providers": [],
            "fallback_to_cpu": False,
            "warning": "",
        },
        "model_pack": _model_pack_snapshot(str(model)),
        "insightface_runtime_objects": insightface_runtime_objects_snapshot(),
        "photos": [],
        "ok": False,
        "faces_total": 0,
        "warnings": [],
        "errors": [],
    }
    try:
        legacy = importlib.import_module("face_sorter_mvp.face_sorter_mvp")
        # Keep the probe aligned with the real scan path: decode uses lazy
        # globals in the legacy module, so initialize them explicitly before
        # the first call to load_image_rgb().  This also makes the failure mode
        # clear if Pillow/numpy are missing from a frozen bundle.
        legacy.load_runtime_modules()
        app = legacy.create_face_app(str(model), bool(use_gpu), int(det_size or 640))
        face_app = _face_app_summary(app)
        result["face_app"] = face_app
        active_providers = list(face_app.get("providers", []))
        cuda_available = "CUDAExecutionProvider" in list(result.get("onnx_providers", []))
        fallback_to_cpu = bool(use_gpu and "CUDAExecutionProvider" not in active_providers)
        warning = ""
        if use_gpu and not cuda_available:
            warning = "GPU was requested, but CUDAExecutionProvider is not available in ONNX Runtime; CPU fallback is expected."
        elif fallback_to_cpu:
            warning = "GPU was requested, but InsightFace session providers do not include CUDAExecutionProvider; CPU fallback is active or likely."
        if warning:
            result.setdefault("warnings", []).append(warning)
        result["gpu_provider_status"] = {
            "requested": bool(use_gpu),
            "cuda_execution_provider_available": cuda_available,
            "active_face_app_providers": active_providers,
            "fallback_to_cpu": fallback_to_cpu,
            "warning": warning,
        }
        photos = _iter_images(root, max(1, int(max_images or 5)))
        result["photos_found_for_probe"] = len(photos)
        for path in photos:
            row: Dict[str, Any] = {"path": str(path), "ok": False}
            try:
                ok, reason, message = legacy.image_magic_status(path, strict_extension=False)
                row["magic"] = {"ok": bool(ok), "reason": reason, "message": message}
                if not ok:
                    row["error"] = message
                    result["photos"].append(row)
                    continue
                rgb, w, h = legacy.load_image_rgb(path, max_side=1800, upscale_small_to=640)
                row["image"] = {"width": int(w), "height": int(h), "array_shape": list(getattr(rgb, "shape", ())) }
                bgr = legacy.rgb_to_bgr(rgb)
                faces = _face_sequence(app.get(bgr))
                face_rows = []
                for face in faces:
                    emb = getattr(face, "normed_embedding", None)
                    if emb is None:
                        emb = getattr(face, "embedding", None)
                    face_rows.append({
                        "det_score": _float_scalar(getattr(face, "det_score", 0.0), 0.0),
                        "bbox": _float_list(getattr(face, "bbox", None), max_items=4),
                        "embedding_present": emb is not None,
                        "embedding_shape": list(getattr(emb, "shape", ())) if emb is not None else [],
                    })
                row["faces_count"] = len(faces)
                row["faces"] = face_rows[:10]
                row["ok"] = True
                result["faces_total"] = int(result.get("faces_total", 0)) + len(faces)
            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"
                row["traceback"] = traceback.format_exc()[-6000:]
            result["photos"].append(row)
        result["ok"] = bool(result.get("faces_total", 0) or result.get("photos"))
    except Exception as exc:
        result["errors"].append(f"{type(exc).__name__}: {exc}")
        result["traceback"] = traceback.format_exc()[-12000:]
    return _safe(result)


__all__ = [
    "FROZEN_DIAGNOSTICS_SCHEMA_VERSION",
    "package_import_snapshot",
    "insightface_runtime_objects_snapshot",
    "run_scan_probe",
]
