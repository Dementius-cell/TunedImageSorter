#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate ONNX Runtime provider visibility before/after Windows packaging.

This script is intentionally small and import-safe.  It catches the common GPU
packaging failure where both ``onnxruntime`` and ``onnxruntime-gpu`` metadata are
present, but the imported module exposes only CPU providers.

v69.6 also checks the pinned CUDA 12 GPU runtime versions and can run a tiny
CUDAExecutionProvider session smoke-test.  This catches the v67.8 regression
where an unpinned build pulled onnxruntime-gpu 1.27.x, which looked for CUDA 13
DLL names while the portable profile bundles CUDA 12 wheels.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXPECTED_GPU_RUNTIME_VERSIONS: Dict[str, str] = {
    "onnxruntime-gpu": "1.26.0",
    "nvidia-cuda-runtime-cu12": "12.9.79",
    "nvidia-cudnn-cu12": "9.23.1.3",
    "nvidia-cublas-cu12": "12.9.2.10",
    "nvidia-cuda-nvrtc-cu12": "12.9.86",
    "nvidia-cufft-cu12": "11.4.1.4",
    "nvidia-curand-cu12": "10.3.10.19",
    "nvidia-nvjitlink-cu12": "12.9.86",
}


def _safe_version(dist_name: str) -> str:
    try:
        import importlib.metadata as md
        return md.version(dist_name)
    except Exception:
        return ""


def _preload() -> List[str]:
    added: List[str] = []
    try:
        from face_sorter_mvp.core.preflight import _add_native_dll_directories_light
        added = list(_add_native_dll_directories_light())
    except Exception:
        pass
    try:
        import onnxruntime as ort  # type: ignore
        preload = getattr(ort, "preload_dlls", None)
        if callable(preload):
            # Official ORT docs: directory="" searches NVIDIA site-packages.
            try:
                preload(cuda=True, cudnn=True, msvc=True, directory="")
            except TypeError:
                preload()
            except Exception:
                # A failed preload should be visible through providers/smoke-test,
                # but this script should still return structured diagnostics.
                pass
    except Exception:
        pass
    return added


def _version_mismatches(payload: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    actual = dict(payload.get("native_distribution_versions") or {})
    actual["onnxruntime-gpu"] = str(payload.get("onnxruntime_gpu_distribution_version") or "")
    mismatches: Dict[str, Dict[str, str]] = {}
    for name, expected in EXPECTED_GPU_RUNTIME_VERSIONS.items():
        got = actual.get(name, "")
        if got != expected:
            mismatches[name] = {"expected": expected, "actual": got or "not installed"}
    return mismatches


def _cuda_session_smoke_test() -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "ok": False,
        "providers": [],
        "output": [],
        "error": "",
    }
    try:
        import numpy as np  # type: ignore
        import onnx  # type: ignore
        import onnxruntime as ort  # type: ignore
        from onnx import TensorProto, helper  # type: ignore

        x = helper.make_tensor_value_info("x", TensorProto.FLOAT, [1])
        y = helper.make_tensor_value_info("y", TensorProto.FLOAT, [1])
        z = helper.make_tensor_value_info("z", TensorProto.FLOAT, [1])
        node = helper.make_node("Add", ["x", "y"], ["z"])
        graph = helper.make_graph([node], "face_sorter_mvp_cuda_smoke", [x, y], [z])
        model = helper.make_model(graph, opset_imports=[helper.make_operatorsetid("", 13)])
        # Keep IR version conservative for older ORT wheels.
        model.ir_version = min(int(getattr(model, "ir_version", 8) or 8), 8)

        with tempfile.NamedTemporaryFile(suffix=".onnx", delete=False) as tmp:
            tmp.write(model.SerializeToString())
            model_path = tmp.name
        try:
            session = ort.InferenceSession(model_path, providers=["CUDAExecutionProvider"])
            providers = list(session.get_providers())
            payload["providers"] = providers
            if "CUDAExecutionProvider" not in providers:
                raise RuntimeError(f"CUDAExecutionProvider was requested but session providers are {providers!r}")
            result = session.run(None, {
                "x": np.array([1.0], dtype=np.float32),
                "y": np.array([2.0], dtype=np.float32),
            })
            out = result[0].tolist() if result else []
            payload["output"] = out
            if out != [3.0]:
                raise RuntimeError(f"unexpected smoke output: {out!r}")
            payload["ok"] = True
        finally:
            try:
                os.remove(model_path)
            except Exception:
                pass
    except Exception as exc:
        payload["error"] = f"{type(exc).__name__}: {exc}"
    return payload


def snapshot(*, run_cuda_session: bool = False) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "python_executable": sys.executable,
        "python_version": sys.version.replace("\n", " "),
        "cwd": os.getcwd(),
        "onnxruntime_distribution_version": _safe_version("onnxruntime"),
        "onnxruntime_gpu_distribution_version": _safe_version("onnxruntime-gpu"),
        "expected_gpu_runtime_versions": EXPECTED_GPU_RUNTIME_VERSIONS,
        "native_distribution_versions": {
            name: _safe_version(name)
            for name in (
                "nvidia-cuda-runtime-cu12",
                "nvidia-cudnn-cu12",
                "nvidia-cublas-cu12",
                "nvidia-cuda-nvrtc-cu12",
                "nvidia-cufft-cu12",
                "nvidia-curand-cu12",
                "nvidia-nvjitlink-cu12",
            )
        },
        "gpu_runtime_version_mismatches": {},
        "gpu_runtime_versions_match_expected": False,
        "dll_directories_added": [],
        "onnxruntime_import_ok": False,
        "onnxruntime_module_version": "",
        "onnxruntime_module_file": "",
        "onnx_providers": [],
        "cuda_provider_available": False,
        "cuda_session_smoke_test": {"ok": None, "skipped": not run_cuda_session},
        "error": "",
    }
    payload["gpu_runtime_version_mismatches"] = _version_mismatches(payload)
    payload["gpu_runtime_versions_match_expected"] = not bool(payload["gpu_runtime_version_mismatches"])
    try:
        payload["dll_directories_added"] = _preload()
        import onnxruntime as ort  # type: ignore
        payload["onnxruntime_import_ok"] = True
        payload["onnxruntime_module_version"] = str(getattr(ort, "__version__", ""))
        payload["onnxruntime_module_file"] = str(getattr(ort, "__file__", "") or "")
        get_available_providers = getattr(ort, "get_available_providers", None)
        if not callable(get_available_providers):
            raise RuntimeError(
                "Imported onnxruntime module is incomplete: get_available_providers() is missing. "
                "This usually means CPU onnxruntime was uninstalled after onnxruntime-gpu in a reused "
                "Python environment; force-reinstall the pinned onnxruntime-gpu wheel."
            )
        providers = list(get_available_providers())
        payload["onnx_providers"] = providers
        payload["cuda_provider_available"] = "CUDAExecutionProvider" in providers
        if run_cuda_session:
            payload["cuda_session_smoke_test"] = _cuda_session_smoke_test()
    except Exception as exc:
        payload["error"] = f"{type(exc).__name__}: {exc}"
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-cuda", action="store_true", help="Exit non-zero when CUDAExecutionProvider is absent.")
    parser.add_argument("--require-no-cuda", action="store_true", help="Exit non-zero when CUDAExecutionProvider is present; used for CPU portable builds.")
    parser.add_argument("--require-no-gpu-distribution", action="store_true", help="Exit non-zero when onnxruntime-gpu distribution metadata is present; used for CPU portable builds.")
    parser.add_argument("--require-pinned-gpu-runtime", action="store_true", help="Exit non-zero when GPU runtime package versions differ from the pinned CUDA 12 profile.")
    parser.add_argument("--require-cuda-session", action="store_true", help="Run a tiny CUDAExecutionProvider ONNX session and exit non-zero if it cannot execute.")
    parser.add_argument("--json", action="store_true", help="Print JSON only.")
    args = parser.parse_args(argv)
    payload = snapshot(run_cuda_session=args.require_cuda_session)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("ONNX Runtime provider check")
        print("Python:", payload["python_executable"])
        print("onnxruntime dist:", payload["onnxruntime_distribution_version"] or "not installed")
        print("onnxruntime-gpu dist:", payload["onnxruntime_gpu_distribution_version"] or "not installed")
        print("onnxruntime module:", payload["onnxruntime_module_version"], payload["onnxruntime_module_file"])
        print("providers:", payload["onnx_providers"])
        if args.require_pinned_gpu_runtime or payload.get("onnxruntime_gpu_distribution_version"):
            print("pinned GPU runtime versions:", "OK" if payload.get("gpu_runtime_versions_match_expected") else "MISMATCH")
            if payload.get("gpu_runtime_version_mismatches"):
                print("runtime mismatches:", payload["gpu_runtime_version_mismatches"])
        else:
            print("pinned GPU runtime versions: not checked (CPU profile; onnxruntime-gpu is not expected)")
        if args.require_cuda_session:
            print("CUDA session smoke-test:", payload.get("cuda_session_smoke_test"))
        if payload["error"]:
            print("error:", payload["error"])
    if args.require_cuda and not payload.get("cuda_provider_available"):
        print("ERROR: CUDAExecutionProvider is not available in the imported ONNX Runtime module.", file=sys.stderr)
        print("Fix: rebuild from a clean environment or let build_windows_gui.ps1 force-reinstall the pinned onnxruntime-gpu wheel after insightface.", file=sys.stderr)
        return 2
    if args.require_no_cuda and payload.get("cuda_provider_available"):
        print("ERROR: CUDAExecutionProvider is visible in a CPU-profile ONNX Runtime module.", file=sys.stderr)
        print("Fix: rebuild after removing onnxruntime-gpu and force-reinstalling CPU onnxruntime.", file=sys.stderr)
        return 5
    if args.require_no_gpu_distribution and payload.get("onnxruntime_gpu_distribution_version"):
        print("ERROR: onnxruntime-gpu distribution metadata is present during a CPU-profile build.", file=sys.stderr)
        print("Fix: rebuild after CPU ORT cleanup removes onnxruntime-gpu.", file=sys.stderr)
        return 6
    if args.require_pinned_gpu_runtime and payload.get("gpu_runtime_version_mismatches"):
        print("ERROR: GPU runtime package versions do not match the pinned CUDA 12 profile.", file=sys.stderr)
        print(json.dumps(payload.get("gpu_runtime_version_mismatches"), ensure_ascii=False, indent=2), file=sys.stderr)
        return 3
    if args.require_cuda_session:
        smoke = dict(payload.get("cuda_session_smoke_test") or {})
        if not smoke.get("ok"):
            print("ERROR: CUDAExecutionProvider session smoke-test failed.", file=sys.stderr)
            print(smoke.get("error") or smoke, file=sys.stderr)
            return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
