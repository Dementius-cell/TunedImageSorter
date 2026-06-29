#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Write a small package identity self-check report for portable builds.

v69.6 / Этап 055 keeps this additive packaging/diagnostics helper and verifies the pre-release polish document set.  It is
intentionally build-safe: it does not run TunedImageSorter.exe, does not import Qt,
does not run ML, does not scan photos and does not modify user result folders.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from face_sorter_mvp.core.constants import SCRIPT_VERSION  # noqa: E402

PACKAGE_IDENTITY_SCHEMA_VERSION = 1
PACKAGE_IDENTITY_STAGE = "Этап 055"
PACKAGE_IDENTITY_JSON = "package_identity_check.json"
PACKAGE_IDENTITY_TXT = "package_identity_check.txt"
PORTABLE_MANIFEST = "portable_manifest.json"
REQUIRED_DOCS: Tuple[str, ...] = (
    "START_HERE_RU.txt",
    "START_HERE_EN.txt",
    "QUICK_START_RU.txt",
    "QUICK_START_EN.txt",
    "FIRST_RUN_RU.txt",
    "FIRST_RUN_EN.txt",
    "ERRORS_RU.txt",
    "ERRORS_EN.txt",
    "TROUBLESHOOTING_RU.txt",
    "TROUBLESHOOTING_EN.txt",
    "RC_CHECKLIST_RU.txt",
    "RC_CHECKLIST_EN.txt",
    "RELEASE_GATE_RU.txt",
    "RELEASE_GATE_EN.txt",
    "RELEASE_FREEZE_RU.txt",
    "RELEASE_FREEZE_EN.txt",
    "DOCS_I18N_HYGIENE_RU.txt",
    "DOCS_I18N_HYGIENE_EN.txt",
    "GPU_LITE_RU.txt",
    "GPU_LITE_EN.txt",
    "DUAL_GPU_PACKAGING_RU.txt",
    "DUAL_GPU_PACKAGING_EN.txt",
    "PRODUCT_RENAME_RU.txt",
    "PRODUCT_RENAME_EN.txt",
    "PRE_RELEASE_POLISH_RU.txt",
    "PRE_RELEASE_POLISH_EN.txt",
    "PROFILE_GUIDE_RU.txt",
    "PROFILE_GUIDE_EN.txt",
    "PRIVACY_LOCAL_PROCESSING_RU.txt",
    "PRIVACY_LOCAL_PROCESSING_EN.txt",
    "KNOWN_LIMITATIONS_RU.txt",
    "KNOWN_LIMITATIONS_EN.txt",
    "PUBLIC_RELEASE_NOTES_RU.txt",
    "PUBLIC_RELEASE_NOTES_EN.txt",
    "RELEASE_BUNDLE_RU.txt",
    "RELEASE_BUNDLE_EN.txt",
    "WHICH_VERSION_TO_DOWNLOAD_RU.txt",
    "WHICH_VERSION_TO_DOWNLOAD_EN.txt",
    "README_RU.txt",
    "README_EN.txt",
    "VERSION.txt",
    "SUPPORT_BUNDLE_RU.txt",
    "SUPPORT_BUNDLE_EN.txt",
)
REQUIRED_CONTRACT_TOKENS: Tuple[str, ...] = (
    "ML/recognition unchanged",
    "clustering unchanged",
    "pipeline stages unchanged",
    "SQLite schema unchanged",
    "project.json unchanged",
    "CSV report schemas unchanged",
    "ordinary Start must run mode=all, not apply-names",
)
GPU_RUNTIME_FAMILIES: Tuple[str, ...] = ("CUDA", "cuDNN", "cuBLAS", "NVRTC", "cuFFT", "cuRAND", "nvJitLink")
GPU_LITE_VERIFICATION_FILES: Tuple[str, ...] = ("gpu_lite_runtime_status_build_check.json",)
GPU_VERIFICATION_FILES: Tuple[str, ...] = (
    "runtime_preflight_gpu_build_check.json",
    "runtime_preflight_gpu_build_check.raw.txt",
)


@dataclass(frozen=True)
class PackageIdentityReport:
    ok: bool
    version: str
    refactor_stage: str
    schema_version: int
    profile: str
    package_dir: str
    created_at_utc: str
    checked: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    errors: Tuple[str, ...] = ()
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _read_manifest(path: Path, errors: List[str]) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        errors.append(f"portable_manifest.json cannot be parsed: {type(exc).__name__}: {exc}")
        return {}
    if not isinstance(data, dict):
        errors.append("portable_manifest.json must contain a JSON object")
        return {}
    return data


def _append_field_check(
    *,
    manifest: Dict[str, Any],
    key: str,
    expected: Any,
    errors: List[str],
) -> None:
    actual = manifest.get(key)
    if actual != expected:
        errors.append(f"manifest field {key!r} is {actual!r}; expected {expected!r}")


def _infer_profile(package_dir: Path) -> str:
    name = package_dir.name.lower()
    if "gpu_lite" in name or "gpu-lite" in name:
        return "gpu-lite"
    return "gpu" if "gpu" in name else "cpu"


def build_package_identity_report(package_dir: str | Path, *, profile: Optional[str] = None) -> PackageIdentityReport:
    package = Path(package_dir).expanduser().resolve()
    selected_profile = (profile or _infer_profile(package)).lower()
    checked: List[str] = []
    warnings: List[str] = []
    errors: List[str] = []
    details: Dict[str, Any] = {}

    if selected_profile not in {"cpu", "gpu", "gpu-lite"}:
        errors.append(f"unknown profile {selected_profile!r}; expected cpu, gpu or gpu-lite")

    checked.append("package_dir")
    if not package.exists() or not package.is_dir():
        errors.append(f"package directory does not exist: {package}")
        return PackageIdentityReport(
            ok=False,
            version=SCRIPT_VERSION,
            refactor_stage=PACKAGE_IDENTITY_STAGE,
            schema_version=PACKAGE_IDENTITY_SCHEMA_VERSION,
            profile=selected_profile,
            package_dir=str(package),
            created_at_utc=dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            checked=tuple(checked),
            warnings=tuple(warnings),
            errors=tuple(errors),
            details=details,
        )

    for rel in ("TunedImageSorter.exe", "TunedImageSorter_CLI.exe", "_internal", PORTABLE_MANIFEST, *REQUIRED_DOCS):
        checked.append(rel)
        if not (package / rel).exists():
            errors.append(f"missing package item: {rel}")

    manifest: Dict[str, Any] = {}
    manifest_path = package / PORTABLE_MANIFEST
    if manifest_path.exists():
        checked.append("portable_manifest:content")
        manifest = _read_manifest(manifest_path, errors)
        details["portable_manifest"] = manifest

    if manifest:
        for key, expected in (
            ("schema_version", 1),
            ("app", "Tuned Image Sorter"),
            ("package_kind", "friend-ready-portable"),
            ("version", SCRIPT_VERSION),
            ("refactor_stage", PACKAGE_IDENTITY_STAGE),
            ("ui_api_version", 21),
            ("profile", selected_profile),
        ):
            _append_field_check(manifest=manifest, key=key, expected=expected, errors=errors)

        launchers = manifest.get("launchers") if isinstance(manifest.get("launchers"), dict) else {}
        if launchers.get("gui") != "TunedImageSorter.exe":
            errors.append("manifest launchers.gui must be TunedImageSorter.exe")
        if launchers.get("cli") != "TunedImageSorter_CLI.exe":
            errors.append("manifest launchers.cli must be TunedImageSorter_CLI.exe")

        diagnostics = manifest.get("diagnostics") if isinstance(manifest.get("diagnostics"), dict) else {}
        runtime_preflight = str(diagnostics.get("runtime_preflight", ""))
        if selected_profile in {"gpu", "gpu-lite"} and "--runtime-preflight --gpu" not in runtime_preflight:
            errors.append("GPU/GPU Lite manifest runtime_preflight must use --runtime-preflight --gpu")
        if selected_profile == "cpu" and "--runtime-preflight --gpu" in runtime_preflight:
            errors.append("CPU manifest runtime_preflight must not use --gpu")
        for key in ("release_check", "runtime_preflight", "result_health", "support_bundle", "diagnostics_help"):
            if key not in diagnostics:
                errors.append(f"manifest diagnostics is missing {key!r}")

        runtime = manifest.get("runtime_expectations") if isinstance(manifest.get("runtime_expectations"), dict) else {}
        if selected_profile == "cpu":
            if runtime.get("onnxruntime_distribution") != "onnxruntime==1.27.0":
                errors.append("CPU manifest must record onnxruntime==1.27.0")
            if runtime.get("requires_cuda_execution_provider") is not False:
                errors.append("CPU manifest must state requires_cuda_execution_provider=false")
            if runtime.get("forbidden_provider") != "CUDAExecutionProvider":
                errors.append("CPU manifest must mark CUDAExecutionProvider as forbidden")
        if selected_profile in {"gpu", "gpu-lite"}:
            if runtime.get("onnxruntime_distribution") != "onnxruntime-gpu==1.26.0":
                errors.append("GPU/GPU Lite manifest must record onnxruntime-gpu==1.26.0")
            if runtime.get("requires_cuda_execution_provider") is not True:
                errors.append("GPU/GPU Lite manifest must require CUDAExecutionProvider")
        if selected_profile == "gpu":
            families = runtime.get("bundled_runtime_families") if isinstance(runtime.get("bundled_runtime_families"), list) else []
            missing_families = [item for item in GPU_RUNTIME_FAMILIES if item not in families]
            if missing_families:
                errors.append(f"GPU manifest is missing bundled runtime families: {missing_families}")
            if runtime.get("requires_bundled_cuda12_runtime") is not True:
                errors.append("Full GPU manifest must state requires_bundled_cuda12_runtime=true")
        if selected_profile == "gpu-lite":
            if runtime.get("requires_bundled_cuda12_runtime") is not False:
                errors.append("GPU Lite manifest must state requires_bundled_cuda12_runtime=false")
            if runtime.get("first_run_runtime_setup") is not True:
                errors.append("GPU Lite manifest must enable first_run_runtime_setup")
            if "--gpu-lite-runtime-setup" not in str(runtime.get("runtime_setup_command", "")):
                errors.append("GPU Lite manifest must include runtime_setup_command")

        unchanged = manifest.get("unchanged_contracts") if isinstance(manifest.get("unchanged_contracts"), list) else []
        missing_contracts = [token for token in REQUIRED_CONTRACT_TOKENS if token not in unchanged]
        if missing_contracts:
            errors.append(f"manifest unchanged_contracts is missing: {missing_contracts}")

    gpu_files = {rel: (package / rel).exists() for rel in GPU_VERIFICATION_FILES}
    details["gpu_verification_files"] = gpu_files
    if selected_profile == "cpu":
        for rel, exists in gpu_files.items():
            checked.append(f"cpu_absent:{rel}")
            if exists:
                errors.append(f"CPU package must not contain GPU verification file: {rel}")
    if selected_profile == "gpu":
        for rel, exists in gpu_files.items():
            checked.append(f"gpu_present:{rel}")
            if not exists:
                errors.append(f"GPU package identity report expects frozen GPU verification file: {rel}")
    if selected_profile == "gpu-lite":
        for rel in GPU_VERIFICATION_FILES:
            checked.append(f"gpu_lite_absent:{rel}")
            if (package / rel).exists():
                errors.append(f"GPU Lite package must not contain full GPU verification file: {rel}")
        for rel in GPU_LITE_VERIFICATION_FILES:
            checked.append(f"gpu_lite_present:{rel}")
            if not (package / rel).exists():
                errors.append(f"GPU Lite package identity report expects runtime status file: {rel}")
        checked.append("gpu_lite_absent:_internal/nvidia")
        if (package / "_internal" / "nvidia").exists():
            errors.append("GPU Lite package must not bundle _internal/nvidia")

    # This report confirms package identity only.  It deliberately does not
    # assert real CUDA usability; runtime-preflight/release-check remain the
    # executable diagnostics for that.
    warnings.append("package identity report is static; run runtime-preflight for live runtime/provider checks")

    return PackageIdentityReport(
        ok=not errors,
        version=SCRIPT_VERSION,
        refactor_stage=PACKAGE_IDENTITY_STAGE,
        schema_version=PACKAGE_IDENTITY_SCHEMA_VERSION,
        profile=selected_profile,
        package_dir=str(package),
        created_at_utc=dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        checked=tuple(checked),
        warnings=tuple(warnings),
        errors=tuple(errors),
        details=details,
    )


def format_package_identity_text(report: PackageIdentityReport) -> str:
    status = "OK" if report.ok else "ERROR"
    lines = [
        "Tuned Image Sorter package identity check",
        f"status: {status}",
        f"version: {report.version}",
        f"refactor_stage: {report.refactor_stage}",
        f"profile: {report.profile}",
        f"package_dir: {report.package_dir}",
        f"created_at_utc: {report.created_at_utc}",
        "",
        "checked:",
    ]
    lines.extend(f"  - {item}" for item in report.checked)
    if report.warnings:
        lines.append("")
        lines.append("warnings:")
        lines.extend(f"  - {item}" for item in report.warnings)
    if report.errors:
        lines.append("")
        lines.append("errors:")
        lines.extend(f"  - {item}" for item in report.errors)
    return "\n".join(lines) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Write Tuned Image Sorter portable package identity report.")
    parser.add_argument("--package-dir", required=True, help="Built TunedImageSorter_CPU/GPU package directory.")
    parser.add_argument("--profile", choices=("cpu", "gpu", "gpu-lite"), help="Package profile. Defaults from package folder name.")
    parser.add_argument("--write-json", help=f"Path for {PACKAGE_IDENTITY_JSON}.")
    parser.add_argument("--write-txt", help=f"Path for {PACKAGE_IDENTITY_TXT}.")
    parser.add_argument("--json", action="store_true", help="Print JSON report to stdout.")
    args = parser.parse_args(argv)

    report = build_package_identity_report(args.package_dir, profile=args.profile)
    payload = report.to_dict()
    if args.write_json:
        Path(args.write_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.write_txt:
        Path(args.write_txt).write_text(format_package_identity_text(report), encoding="utf-8")
    if args.json or (not args.write_json and not args.write_txt):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"package_identity_check: {'OK' if report.ok else 'ERROR'}")
        print(f"json={args.write_json}")
        print(f"txt={args.write_txt}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
