#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify the v69.6 friend-ready portable package layout.

This command is intentionally import-safe and build-safe.  It does not run ML,
does not start Qt, does not scan photos and does not modify user folders.

Use cases:
  Source tree check:
    python tools/windows_packaging/verify_friend_ready_package.py

  Built CPU package check:
    python tools/windows_packaging/verify_friend_ready_package.py --package-dir dist/windows/TunedImageSorter_CPU --profile cpu

  Built GPU package check after frozen GPU verification:
    python tools/windows_packaging/verify_friend_ready_package.py --package-dir dist/windows/TunedImageSorter_GPU_FULL --profile gpu --after-gpu-verification

  Zip integrity check:
    python tools/windows_packaging/verify_friend_ready_package.py --zip dist/windows/TunedImageSorter_GPU_FULL_portable_v69_6.zip
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from face_sorter_mvp.core.constants import SCRIPT_VERSION  # noqa: E402
from face_sorter_mvp.core.windows_packaging import (  # noqa: E402
    FRIEND_READY_TOP_LEVEL_FILES,
    verify_friend_ready_source_layout,
)

GPU_VERIFICATION_FILES: Tuple[str, ...] = (
    "runtime_preflight_gpu_build_check.json",
    "runtime_preflight_gpu_build_check.raw.txt",
)
GPU_LITE_VERIFICATION_FILES: Tuple[str, ...] = ("gpu_lite_runtime_status_build_check.json",)

PORTABLE_MANIFEST_FILENAME = "portable_manifest.json"
PACKAGE_IDENTITY_JSON = "package_identity_check.json"
PACKAGE_IDENTITY_TXT = "package_identity_check.txt"

PACKAGE_REQUIRED_FILES: Tuple[str, ...] = (
    "TunedImageSorter.exe",
    "TunedImageSorter_CLI.exe",
    "_internal",
    PORTABLE_MANIFEST_FILENAME,
    PACKAGE_IDENTITY_JSON,
    PACKAGE_IDENTITY_TXT,
    *FRIEND_READY_TOP_LEVEL_FILES,
)

DOC_TOKEN_CHECKS: Dict[str, Tuple[str, ...]] = {
    "START_HERE_RU.txt": (
        "TunedImageSorter.exe",
        "TunedImageSorter_CLI.exe --runtime-preflight",
        "TunedImageSorter_CLI.exe --runtime-preflight --gpu",
        "SmartScreen",
        "output",
        "input",
        "--result-health",
        "--diagnostics-help",
    ),
    "START_HERE_EN.txt": (
        "TunedImageSorter.exe",
        "TunedImageSorter_CLI.exe --runtime-preflight",
        "TunedImageSorter_CLI.exe --runtime-preflight --gpu",
        "SmartScreen",
        "output",
        "input",
        "--result-health",
        "--diagnostics-help",
    ),
    "QUICK_START_RU.txt": (
        "TunedImageSorter.exe",
        "input",
        "output",
        "Проверка окружения",
        "Быстрый тест",
        "SmartScreen",
        "--result-health",
        "--support-bundle",
        "v69.6",
    ),
    "QUICK_START_EN.txt": (
        "TunedImageSorter.exe",
        "input",
        "output",
        "Environment check",
        "Quick test",
        "SmartScreen",
        "--result-health",
        "--support-bundle",
        "v69.6",
    ),
    "FIRST_RUN_RU.txt": (
        "TunedImageSorter.exe",
        "input",
        "output",
        "Проверка окружения",
        "Быстрый тест",
        "--support-bundle",
        "CUDAExecutionProvider",
        "v69.6",
    ),
    "FIRST_RUN_EN.txt": (
        "TunedImageSorter.exe",
        "input",
        "output",
        "Environment check",
        "Quick test",
        "--support-bundle",
        "CUDAExecutionProvider",
        "v69.6",
    ),
    "ERRORS_RU.txt": (
        "Статус / ошибки",
        "Что это значит",
        "Что сделать",
        "CUDAExecutionProvider",
        "problem_files.csv",
        "review_decisions.csv",
        "v69.6",
    ),
    "ERRORS_EN.txt": (
        "Status / errors",
        "Meaning",
        "Action",
        "CUDAExecutionProvider",
        "problem_files.csv",
        "review_decisions.csv",
        "v69.6",
    ),
    "TROUBLESHOOTING_RU.txt": (
        "TunedImageSorter.exe",
        "SmartScreen",
        "CUDAExecutionProvider",
        "NVIDIA driver",
        "problem_files.csv",
        "--runtime-preflight --gpu",
        "--result-health",
        "--support-bundle",
        "ordinary Start must run mode=all, not apply-names",
        "v69.6",
    ),
    "TROUBLESHOOTING_EN.txt": (
        "TunedImageSorter.exe",
        "SmartScreen",
        "CUDAExecutionProvider",
        "NVIDIA driver",
        "problem_files.csv",
        "--runtime-preflight --gpu",
        "--result-health",
        "--support-bundle",
        "ordinary Start must run mode=all, not apply-names",
        "v69.6",
    ),
    "RC_CHECKLIST_RU.txt": (
        "release_candidate_final_gate",
        "TunedImageSorter_CPU_portable_v69_6.zip",
        "TunedImageSorter_GPU_FULL_portable_v69_6.zip",
        "package_identity_check: OK",
        "zip_integrity: OK",
        "ordinary Start must run mode=all, not apply-names",
        "v69.6",
    ),
    "RC_CHECKLIST_EN.txt": (
        "release_candidate_final_gate",
        "TunedImageSorter_CPU_portable_v69_6.zip",
        "TunedImageSorter_GPU_FULL_portable_v69_6.zip",
        "package_identity_check: OK",
        "zip_integrity: OK",
        "ordinary Start must run mode=all, not apply-names",
        "v69.6",
    ),
    "RELEASE_GATE_RU.txt": (
        "PASS",
        "FAIL",
        "release-check",
        "friend-ready package verification",
        "portable_manifest.json",
        "package_identity_check",
        "TunedImageSorter_CPU_portable_v69_6.zip",
        "TunedImageSorter_GPU_FULL_portable_v69_6.zip",
        "v69.6",
    ),
    "RELEASE_GATE_EN.txt": (
        "PASS",
        "FAIL",
        "release-check",
        "friend-ready package verification",
        "portable_manifest.json",
        "package_identity_check",
        "TunedImageSorter_CPU_portable_v69_6.zip",
        "TunedImageSorter_GPU_FULL_portable_v69_6.zip",
        "v69.6",
    ),
    "RELEASE_FREEZE_RU.txt": (
        "release_freeze_final_package",
        "TunedImageSorter_CPU_portable_v69_6.zip",
        "TunedImageSorter_GPU_FULL_portable_v69_6.zip",
        "package_identity_check: OK",
        "zip_integrity: OK",
        "_internal\\nvidia",
        "Первый запуск",
        "v69.6",
        "Этап 055",
    ),
    "RELEASE_FREEZE_EN.txt": (
        "release_freeze_final_package",
        "TunedImageSorter_CPU_portable_v69_6.zip",
        "TunedImageSorter_GPU_FULL_portable_v69_6.zip",
        "package_identity_check: OK",
        "zip_integrity: OK",
        "_internal\\nvidia",
        "First launch",
        "v69.6",
        "Stage 055",
    ),
    "DOCS_I18N_HYGIENE_RU.txt": ("docs_i18n_hygiene_polish", "v69.6", "Этап 055", "release-check", "package_identity_check", "friend-ready package verification", "zip_integrity", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "ML", "не менялись"),
    "DOCS_I18N_HYGIENE_EN.txt": ("docs_i18n_hygiene_polish", "v69.6", "Stage 055", "release-check", "package_identity_check", "friend-ready package verification", "zip_integrity", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "ML", "unchanged"),

    "DUAL_GPU_PACKAGING_RU.txt": ("dual_gpu_packaging_release_docs", "v69.6", "Этап 055", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip", "GPU_FULL", "GPU_LITE", "package_identity_check: OK", "zip_integrity: OK", "ordinary Start must run mode=all, not apply-names"),
    "DUAL_GPU_PACKAGING_EN.txt": ("dual_gpu_packaging_release_docs", "v69.6", "Stage 055", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip", "GPU_FULL", "GPU_LITE", "package_identity_check: OK", "zip_integrity: OK", "ordinary Start must run mode=all, not apply-names"),
    "PRODUCT_RENAME_RU.txt": ("Tuned Image Sorter", "v69.6", "Этап 055", "TunedImageSorter.exe", "TunedImageSorter_CLI.exe", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip", "face_sorter_mvp", "compatibility fallback"),
    "PRODUCT_RENAME_EN.txt": ("Tuned Image Sorter", "v69.6", "Stage 055", "TunedImageSorter.exe", "TunedImageSorter_CLI.exe", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip", "face_sorter_mvp", "compatibility fallback"),
    "PRE_RELEASE_POLISH_RU.txt": ("Tuned Image Sorter", "v69.6", "Этап 055", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip", "face_sorter_mvp", "ordinary Start must run mode=all, not apply-names"),
    "PRE_RELEASE_POLISH_EN.txt": ("Tuned Image Sorter", "v69.6", "Stage 055", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip", "face_sorter_mvp", "Ordinary Start must run mode=all, not apply-names"),
    "PROFILE_GUIDE_RU.txt": ("CPU", "GPU_FULL", "GPU_LITE", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip", "v69.6", "Этап 055", "не менялись"),
    "PROFILE_GUIDE_EN.txt": ("CPU", "GPU_FULL", "GPU_LITE", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip", "v69.6", "Stage 055", "unchanged"),
    "PRIVACY_LOCAL_PROCESSING_RU.txt": ("privacy", "local processing", "исходные фотографии", "support-bundle", "Ordinary Start", "known non-blocking UX issue", "не менялись"),
    "PRIVACY_LOCAL_PROCESSING_EN.txt": ("privacy", "local processing", "source photos", "support-bundle", "ordinary Start", "known non-blocking UX issue", "unchanged"),
    "KNOWN_LIMITATIONS_RU.txt": ("known limitations", "reports", "known non-blocking UX issue", "GPU_LITE", "review_decisions.csv", "SmartScreen", "не менялись"),
    "KNOWN_LIMITATIONS_EN.txt": ("known limitations", "reports", "known non-blocking UX issue", "GPU_LITE", "review_decisions.csv", "SmartScreen", "unchanged"),
    "PUBLIC_RELEASE_NOTES_RU.txt": ("TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip", "known non-blocking issue", "ML/pipeline/schema/runtime split не менялись"),
    "PUBLIC_RELEASE_NOTES_EN.txt": ("TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip", "known non-blocking issue", "ML/pipeline/schema/runtime split are unchanged"),
    "RELEASE_BUNDLE_RU.txt": ("release bundle", "SHA256SUMS.txt", "RELEASE_BUNDLE_MANIFEST.json", "TunedImageSorter_v69_6_release", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip", "Этап 055", "не менялись"),
    "RELEASE_BUNDLE_EN.txt": ("release bundle", "SHA256SUMS.txt", "RELEASE_BUNDLE_MANIFEST.json", "TunedImageSorter_v69_6_release", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip", "Stage 055", "unchanged"),
    "WHICH_VERSION_TO_DOWNLOAD_RU.txt": ("CPU", "GPU_FULL", "GPU_LITE", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip", "Known issue"),
    "WHICH_VERSION_TO_DOWNLOAD_EN.txt": ("CPU", "GPU_FULL", "GPU_LITE", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip", "Known issue"),
    "README_RU.txt": (
        "TunedImageSorter.exe",
        "TunedImageSorter_CLI.exe",
        "--release-check",
        "CUDA Toolkit",
        "NVIDIA driver",
        "v69.6",
        "QUICK_START",
        "TROUBLESHOOTING",
        "--result-health",
        "--diagnostics-help",
    ),
    "README_EN.txt": (
        "TunedImageSorter.exe",
        "TunedImageSorter_CLI.exe",
        "--release-check",
        "CUDA Toolkit",
        "NVIDIA driver",
        "v69.6",
        "QUICK_START",
        "TROUBLESHOOTING",
        "--result-health",
        "--diagnostics-help",
    ),
    "VERSION.txt": (
        "version=v69.6",
        "refactor_stage=Этап 055",
        "ui_api_version=21",
        "QUICK_START_RU.txt",
        "TROUBLESHOOTING_RU.txt",
        "--result-health",
        "--diagnostics-help",
    ),
    "SUPPORT_BUNDLE_RU.txt": (
        "--support-bundle",
        "TunedImageSorter_CLI.exe",
        "исходные фотографии",
        "support-bundle",
        "--result-health",
        "result_health_check",
    ),
    "SUPPORT_BUNDLE_EN.txt": (
        "--support-bundle",
        "TunedImageSorter_CLI.exe",
        "source photos",
        "support-bundle",
        "--result-health",
        "result_health_check",
    ),
}


@dataclass(frozen=True)
class FriendReadyVerification:
    ok: bool
    version: str
    checked: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    errors: Tuple[str, ...] = ()
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _infer_profile(package_dir: Path) -> str:
    name = package_dir.name.lower()
    if "gpu_lite" in name or "gpu-lite" in name:
        return "gpu-lite"
    if "gpu" in name:
        return "gpu"
    return "cpu"



def _load_manifest(path: Path, errors: List[str]) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        errors.append(f"portable_manifest.json is not valid JSON: {type(exc).__name__}: {exc}")
        return {}
    if not isinstance(data, dict):
        errors.append("portable_manifest.json must contain a JSON object")
        return {}
    return data


def _verify_manifest(manifest: Dict[str, Any], *, selected_profile: str, errors: List[str], warnings: List[str]) -> None:
    required_pairs = {
        "schema_version": 1,
        "app": "Tuned Image Sorter",
        "package_kind": "friend-ready-portable",
        "version": SCRIPT_VERSION,
        "refactor_stage": "Этап 055",
        "ui_api_version": 21,
        "profile": selected_profile,
    }
    for key, expected in required_pairs.items():
        actual = manifest.get(key)
        if actual != expected:
            errors.append(f"portable_manifest.json field {key!r} is {actual!r}; expected {expected!r}")

    launchers = manifest.get("launchers") if isinstance(manifest.get("launchers"), dict) else {}
    if launchers.get("gui") != "TunedImageSorter.exe" or launchers.get("cli") != "TunedImageSorter_CLI.exe":
        errors.append("portable_manifest.json must list TunedImageSorter.exe and TunedImageSorter_CLI.exe launchers")

    diagnostics = manifest.get("diagnostics") if isinstance(manifest.get("diagnostics"), dict) else {}
    for key in ("release_check", "runtime_preflight", "result_health", "support_bundle", "diagnostics_help"):
        if key not in diagnostics:
            errors.append(f"portable_manifest.json diagnostics is missing {key!r}")
    if selected_profile in {"gpu", "gpu-lite"}:
        if "--runtime-preflight --gpu" not in str(diagnostics.get("runtime_preflight", "")):
            errors.append("GPU/GPU Lite portable_manifest.json must point runtime_preflight to --runtime-preflight --gpu")
    elif selected_profile == "cpu":
        if "--runtime-preflight --gpu" in str(diagnostics.get("runtime_preflight", "")):
            errors.append("CPU portable_manifest.json must not point runtime_preflight to GPU preflight")

    runtime = manifest.get("runtime_expectations") if isinstance(manifest.get("runtime_expectations"), dict) else {}
    if selected_profile in {"gpu", "gpu-lite"}:
        if runtime.get("requires_cuda_execution_provider") is not True:
            errors.append("GPU/GPU Lite portable_manifest.json must require CUDAExecutionProvider")
        if runtime.get("onnxruntime_distribution") != "onnxruntime-gpu==1.26.0":
            errors.append("GPU/GPU Lite portable_manifest.json must record onnxruntime-gpu==1.26.0")
        if selected_profile == "gpu-lite":
            if runtime.get("requires_bundled_cuda12_runtime") is not False:
                errors.append("GPU Lite portable_manifest.json must state requires_bundled_cuda12_runtime=false")
            if runtime.get("first_run_runtime_setup") is not True:
                errors.append("GPU Lite portable_manifest.json must enable first_run_runtime_setup")
            if "--gpu-lite-runtime-setup" not in str(runtime.get("runtime_setup_command", "")):
                errors.append("GPU Lite portable_manifest.json must include runtime_setup_command")
    elif selected_profile == "cpu":
        if runtime.get("requires_cuda_execution_provider") is not False:
            errors.append("CPU portable_manifest.json must state that CUDAExecutionProvider is not required")
        if runtime.get("forbidden_provider") != "CUDAExecutionProvider":
            errors.append("CPU portable_manifest.json must mark CUDAExecutionProvider as forbidden")

    unchanged = manifest.get("unchanged_contracts")
    if not isinstance(unchanged, list) or "ordinary Start must run mode=all, not apply-names" not in unchanged:
        warnings.append("portable_manifest.json should explicitly state that ordinary Start must not enter apply-names")




def _verify_package_identity_report(
    package: Path,
    *,
    selected_profile: str,
    errors: List[str],
    warnings: List[str],
    details: Dict[str, Any],
) -> None:
    json_path = package / PACKAGE_IDENTITY_JSON
    txt_path = package / PACKAGE_IDENTITY_TXT
    if not json_path.exists() or not txt_path.exists():
        return
    try:
        report = json.loads(json_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        errors.append(f"package_identity_check.json is not valid JSON: {type(exc).__name__}: {exc}")
        return
    details["package_identity_check"] = report
    if not isinstance(report, dict):
        errors.append("package_identity_check.json must contain a JSON object")
        return
    if report.get("ok") is not True:
        errors.append("package_identity_check.json must have ok=true")
    if report.get("version") != SCRIPT_VERSION:
        errors.append(f"package_identity_check.json version is {report.get('version')!r}; expected {SCRIPT_VERSION!r}")
    if report.get("refactor_stage") != "Этап 055":
        errors.append(f"package_identity_check.json refactor_stage is {report.get('refactor_stage')!r}; expected 'Этап 055'")
    if report.get("profile") != selected_profile:
        errors.append(f"package_identity_check.json profile is {report.get('profile')!r}; expected {selected_profile!r}")
    text = txt_path.read_text(encoding="utf-8", errors="replace")
    for token in ("Tuned Image Sorter package identity check", "status: OK", f"version: {SCRIPT_VERSION}", "refactor_stage: Этап 055", f"profile: {selected_profile}"):
        if token not in text:
            errors.append(f"package_identity_check.txt must mention {token!r}")
    if selected_profile == "gpu" and "runtime_preflight_gpu_build_check.json" not in text:
        warnings.append("package_identity_check.txt should mention the frozen GPU preflight JSON file")

def verify_package_dir(
    package_dir: str | Path,
    *,
    profile: Optional[str] = None,
    after_gpu_verification: bool = False,
) -> FriendReadyVerification:
    package = Path(package_dir).expanduser().resolve()
    selected_profile = (profile or _infer_profile(package)).lower()
    checked: List[str] = []
    warnings: List[str] = []
    errors: List[str] = []
    details: Dict[str, Any] = {"package_dir": str(package), "profile": selected_profile}

    if selected_profile not in {"cpu", "gpu", "gpu-lite"}:
        errors.append(f"unknown profile: {selected_profile!r}; expected cpu, gpu or gpu-lite")

    if not package.exists() or not package.is_dir():
        errors.append(f"package directory does not exist: {package}")
        return FriendReadyVerification(False, SCRIPT_VERSION, tuple(checked), tuple(warnings), tuple(errors), details)

    for rel in PACKAGE_REQUIRED_FILES:
        path = package / rel
        checked.append(rel)
        if not path.exists():
            errors.append(f"missing package item: {rel}")

    for rel, tokens in DOC_TOKEN_CHECKS.items():
        path = package / rel
        if not path.exists():
            continue
        text = _read_text(path)
        checked.append(f"{rel}:content")
        for token in tokens:
            if token not in text:
                errors.append(f"{rel} must mention {token!r}")

    manifest_path = package / PORTABLE_MANIFEST_FILENAME
    if manifest_path.exists():
        checked.append(f"{PORTABLE_MANIFEST_FILENAME}:content")
        manifest = _load_manifest(manifest_path, errors)
        details["portable_manifest"] = manifest
        if manifest:
            _verify_manifest(manifest, selected_profile=selected_profile, errors=errors, warnings=warnings)

    if (package / PACKAGE_IDENTITY_JSON).exists() or (package / PACKAGE_IDENTITY_TXT).exists():
        checked.append("package_identity_check:content")
        _verify_package_identity_report(package, selected_profile=selected_profile, errors=errors, warnings=warnings, details=details)

    gpu_file_presence = {rel: (package / rel).exists() for rel in GPU_VERIFICATION_FILES}
    details["gpu_verification_files"] = gpu_file_presence
    if selected_profile == "cpu":
        for rel, exists in gpu_file_presence.items():
            checked.append(f"cpu_absent:{rel}")
            if exists:
                errors.append(f"CPU package must not contain GPU verification file: {rel}")
    elif selected_profile == "gpu":
        if after_gpu_verification:
            for rel, exists in gpu_file_presence.items():
                checked.append(f"gpu_present_after_verification:{rel}")
                if not exists:
                    errors.append(f"GPU package after verification must contain: {rel}")
        else:
            present_count = sum(1 for exists in gpu_file_presence.values() if exists)
            if present_count not in {0, len(GPU_VERIFICATION_FILES)}:
                errors.append("GPU verification files are incomplete; expected both files or neither before verification")
            if present_count == 0:
                warnings.append("GPU verification files are absent; this is acceptable only before frozen GPU verification")
    elif selected_profile == "gpu-lite":
        for rel, exists in gpu_file_presence.items():
            checked.append(f"gpu_lite_absent:{rel}")
            if exists:
                errors.append(f"GPU Lite package must not contain full GPU verification file: {rel}")
        for rel in GPU_LITE_VERIFICATION_FILES:
            checked.append(f"gpu_lite_present:{rel}")
            if not (package / rel).exists():
                errors.append(f"GPU Lite package must contain: {rel}")
        checked.append("gpu_lite_absent:_internal/nvidia")
        if (package / "_internal" / "nvidia").exists():
            errors.append("GPU Lite package must not bundle _internal/nvidia")

    return FriendReadyVerification(
        ok=not errors,
        version=SCRIPT_VERSION,
        checked=tuple(checked),
        warnings=tuple(warnings),
        errors=tuple(errors),
        details=details,
    )


def verify_zip_integrity(zip_path: str | Path) -> FriendReadyVerification:
    path = Path(zip_path).expanduser().resolve()
    checked: List[str] = ["zip_exists", "zip_open", "zip_testzip", "zip_package_layout"]
    warnings: List[str] = []
    errors: List[str] = []
    details: Dict[str, Any] = {"zip_path": str(path)}
    if not path.exists() or not path.is_file():
        errors.append(f"zip file does not exist: {path}")
        return FriendReadyVerification(False, SCRIPT_VERSION, tuple(checked), tuple(warnings), tuple(errors), details)
    try:
        with zipfile.ZipFile(path, "r") as zf:
            bad = zf.testzip()
            names = [info.filename.replace("\\", "/") for info in zf.infolist()]
            details["entry_count"] = len(names)
            if bad is not None:
                errors.append(f"zip integrity failed at entry: {bad}")

            roots = sorted({name.split("/", 1)[0] for name in names if name and "/" in name})
            details["roots"] = roots
            if len(roots) != 1:
                errors.append(f"zip must contain exactly one top-level package folder; found {roots}")
            else:
                root = roots[0]
                required = ("TunedImageSorter.exe", "TunedImageSorter_CLI.exe", "_internal/", PORTABLE_MANIFEST_FILENAME, PACKAGE_IDENTITY_JSON, PACKAGE_IDENTITY_TXT, *FRIEND_READY_TOP_LEVEL_FILES)
                for rel in required:
                    prefix = f"{root}/{rel}"
                    exists = any(name == prefix or name.startswith(prefix) for name in names)
                    if not exists:
                        errors.append(f"zip package layout is missing: {rel}")
                inferred_profile = "gpu-lite" if ("gpu_lite" in root.lower() or "gpu-lite" in root.lower()) else ("gpu" if "gpu" in root.lower() else "cpu")
                manifest_name = f"{root}/{PORTABLE_MANIFEST_FILENAME}"
                if manifest_name in names:
                    with zf.open(manifest_name) as fh:
                        raw = fh.read().decode("utf-8-sig")
                    manifest = json.loads(raw)
                    details["portable_manifest"] = manifest
                    _verify_manifest(manifest, selected_profile=inferred_profile, errors=errors, warnings=warnings)
                identity_json_name = f"{root}/{PACKAGE_IDENTITY_JSON}"
                identity_txt_name = f"{root}/{PACKAGE_IDENTITY_TXT}"
                if identity_json_name in names and identity_txt_name in names:
                    with zf.open(identity_json_name) as fh:
                        identity = json.loads(fh.read().decode("utf-8-sig"))
                    details["package_identity_check"] = identity
                    if identity.get("ok") is not True:
                        errors.append("zip package_identity_check.json must have ok=true")
                    if identity.get("version") != SCRIPT_VERSION:
                        errors.append(f"zip package_identity_check.json version is {identity.get('version')!r}; expected {SCRIPT_VERSION!r}")
                    if identity.get("profile") != inferred_profile:
                        errors.append(f"zip package_identity_check.json profile is {identity.get('profile')!r}; expected {inferred_profile!r}")
    except Exception as exc:
        errors.append(f"zip read failed: {type(exc).__name__}: {exc}")
    return FriendReadyVerification(not errors, SCRIPT_VERSION, tuple(checked), tuple(warnings), tuple(errors), details)


def _print_result(label: str, result: Any, *, as_json: bool) -> None:
    payload = result.to_dict() if hasattr(result, "to_dict") else asdict(result)
    if as_json:
        print(json.dumps({label: payload}, ensure_ascii=False, indent=2))
        return
    status = "OK" if payload.get("ok") else "ERROR"
    print(f"{label}: {status}")
    print(f"version={payload.get('version')}")
    for warning in payload.get("warnings", ()):
        print(f"[WARN] {warning}")
    for error in payload.get("errors", ()):
        print(f"[ERROR] {error}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Tuned Image Sorter friend-ready portable package layout.")
    parser.add_argument("--source-root", default=str(ROOT), help="Source tree root to verify when --package-dir is not used.")
    parser.add_argument("--package-dir", help="Built TunedImageSorter_CPU/GPU directory to verify.")
    parser.add_argument("--profile", choices=("cpu", "gpu", "gpu-lite"), help="Package profile. Defaults from package folder name.")
    parser.add_argument("--after-gpu-verification", action="store_true", help="Require GPU verification files in a GPU package.")
    parser.add_argument("--zip", dest="zip_path", help="Portable zip to integrity-check.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args(argv)

    results: List[Tuple[str, Any]] = []
    if args.package_dir:
        results.append((
            "friend_ready_package",
            verify_package_dir(args.package_dir, profile=args.profile, after_gpu_verification=args.after_gpu_verification),
        ))
    else:
        results.append(("friend_ready_source", verify_friend_ready_source_layout(args.source_root)))

    if args.zip_path:
        results.append(("zip_integrity", verify_zip_integrity(args.zip_path)))

    if args.json:
        print(json.dumps({label: result.to_dict() for label, result in results}, ensure_ascii=False, indent=2))
    else:
        for label, result in results:
            _print_result(label, result, as_json=False)

    return 0 if all(result.ok for _, result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
