# -*- coding: utf-8 -*-
"""Import-safe Windows packaging contract helpers.

v69.6 / Этап 055 verifies the confirmed Windows CPU/GPU one-folder EXE packaging layer and pre-release polish surface while runtime behavior stays unchanged.
This module verifies that the source tree contains the required build scripts,
spec files and requirements files.  It does not run PyInstaller, does not import
heavy ML packages and does not touch user photo folders.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .constants import SCRIPT_DIR, SCRIPT_VERSION

WINDOWS_PACKAGING_SCHEMA_VERSION = 21
WINDOWS_PACKAGING_DIR = Path("tools") / "windows_packaging"
WINDOWS_PACKAGING_OUTPUT_DIR = Path("dist") / "windows"


@dataclass(frozen=True)
class WindowsPackagingFile:
    """One file required by the Windows packaging layer."""

    relative_path: str
    purpose: str
    required: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WindowsPackagingPlan:
    """Serializable packaging plan for UI/release diagnostics."""

    version: str
    refactor_stage: str
    schema_version: int
    project_root: Path
    packaging_dir: Path
    output_dir: Path
    build_commands: Tuple[str, ...]
    files: Tuple[WindowsPackagingFile, ...]
    notes: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["project_root"] = str(self.project_root)
        data["packaging_dir"] = str(self.packaging_dir)
        data["output_dir"] = str(self.output_dir)
        data["files"] = [item.to_dict() for item in self.files]
        return data


@dataclass(frozen=True)
class WindowsPackagingCheckResult:
    """Result of verifying the Windows packaging layer files."""

    ok: bool
    version: str
    refactor_stage: str
    schema_version: int
    project_root: Path
    checked_files: Tuple[str, ...]
    missing_files: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    errors: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["project_root"] = str(self.project_root)
        return data


@dataclass(frozen=True)
class FriendReadySourceCheckResult:
    """Result of verifying source files needed for a friend-ready portable package."""

    ok: bool
    version: str
    refactor_stage: str
    schema_version: int
    project_root: Path
    checked_files: Tuple[str, ...]
    missing_files: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    errors: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["project_root"] = str(self.project_root)
        return data


FRIEND_READY_TOP_LEVEL_FILES: Tuple[str, ...] = (
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

FRIEND_READY_DOC_TOKEN_CHECKS: Dict[str, Tuple[str, ...]] = {
    "START_HERE_RU.txt": ("TunedImageSorter.exe", "TunedImageSorter_CLI.exe --runtime-preflight", "TunedImageSorter_CLI.exe --runtime-preflight --gpu", "SmartScreen", "input", "output", "--result-health", "--diagnostics-help"),
    "START_HERE_EN.txt": ("TunedImageSorter.exe", "TunedImageSorter_CLI.exe --runtime-preflight", "TunedImageSorter_CLI.exe --runtime-preflight --gpu", "SmartScreen", "input", "output", "--result-health", "--diagnostics-help"),
    "QUICK_START_RU.txt": ("TunedImageSorter.exe", "input", "output", "Проверка окружения", "Быстрый тест", "SmartScreen", "--result-health", "--support-bundle", "v69.6"),
    "QUICK_START_EN.txt": ("TunedImageSorter.exe", "input", "output", "Environment check", "Quick test", "SmartScreen", "--result-health", "--support-bundle", "v69.6"),
    "FIRST_RUN_RU.txt": ("TunedImageSorter.exe", "input", "output", "Проверка окружения", "Быстрый тест", "--support-bundle", "CUDAExecutionProvider", "v69.6"),
    "FIRST_RUN_EN.txt": ("TunedImageSorter.exe", "input", "output", "Environment check", "Quick test", "--support-bundle", "CUDAExecutionProvider", "v69.6"),
    "ERRORS_RU.txt": ("Статус / ошибки", "Что это значит", "Что сделать", "CUDAExecutionProvider", "problem_files.csv", "review_decisions.csv", "v69.6"),
    "ERRORS_EN.txt": ("Status / errors", "Meaning", "Action", "CUDAExecutionProvider", "problem_files.csv", "review_decisions.csv", "v69.6"),
    "TROUBLESHOOTING_RU.txt": ("TunedImageSorter.exe", "SmartScreen", "CUDAExecutionProvider", "NVIDIA driver", "problem_files.csv", "--runtime-preflight --gpu", "--result-health", "--support-bundle", "ordinary Start must run mode=all, not apply-names", "v69.6"),
    "TROUBLESHOOTING_EN.txt": ("TunedImageSorter.exe", "SmartScreen", "CUDAExecutionProvider", "NVIDIA driver", "problem_files.csv", "--runtime-preflight --gpu", "--result-health", "--support-bundle", "ordinary Start must run mode=all, not apply-names", "v69.6"),
    "RC_CHECKLIST_RU.txt": ("release_candidate_final_gate", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "package_identity_check: OK", "zip_integrity: OK", "ordinary Start must run mode=all, not apply-names", "v69.6"),
    "RC_CHECKLIST_EN.txt": ("release_candidate_final_gate", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "package_identity_check: OK", "zip_integrity: OK", "ordinary Start must run mode=all, not apply-names", "v69.6"),
    "RELEASE_GATE_RU.txt": ("PASS", "FAIL", "release-check", "friend-ready package verification", "portable_manifest.json", "package_identity_check", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "v69.6"),
    "RELEASE_GATE_EN.txt": ("PASS", "FAIL", "release-check", "friend-ready package verification", "portable_manifest.json", "package_identity_check", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "v69.6"),
    "RELEASE_FREEZE_RU.txt": ("release_freeze_final_package", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "package_identity_check: OK", "zip_integrity: OK", "_internal\\nvidia", "Первый запуск", "v69.6", "Этап 055"),
    "RELEASE_FREEZE_EN.txt": ("release_freeze_final_package", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "package_identity_check: OK", "zip_integrity: OK", "_internal\\nvidia", "First launch", "v69.6", "Stage 055"),
    "DOCS_I18N_HYGIENE_RU.txt": ("docs_i18n_hygiene_polish", "v69.6", "Этап 055", "release-check", "package_identity_check", "friend-ready package verification", "zip_integrity", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "ML", "не менялись"),
    "DOCS_I18N_HYGIENE_EN.txt": ("docs_i18n_hygiene_polish", "v69.6", "Stage 055", "release-check", "package_identity_check", "friend-ready package verification", "zip_integrity", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "ML", "unchanged"),
    "GPU_LITE_RU.txt": ("experimental_slim_gpu_package", "v69.6", "Этап 055", "TunedImageSorter_GPU_LITE_portable_v69_6.zip", "--gpu-lite-runtime-status", "--gpu-lite-runtime-setup --yes", "first-run", "NVIDIA driver", "локальную папку пользователя", "ML", "не меняет"),
    "GPU_LITE_EN.txt": ("experimental_slim_gpu_package", "v69.6", "Stage 055", "TunedImageSorter_GPU_LITE_portable_v69_6.zip", "--gpu-lite-runtime-status", "--gpu-lite-runtime-setup --yes", "first-run", "NVIDIA driver", "local user folder", "ML", "unchanged"),

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
    "README_RU.txt": ("TunedImageSorter.exe", "TunedImageSorter_CLI.exe", "--release-check", "CUDA Toolkit", "NVIDIA driver", "v69.6", "QUICK_START", "TROUBLESHOOTING", "RC_CHECKLIST", "RELEASE_GATE", "RELEASE_FREEZE", "DOCS_I18N_HYGIENE", "--result-health", "--diagnostics-help"),
    "README_EN.txt": ("TunedImageSorter.exe", "TunedImageSorter_CLI.exe", "--release-check", "CUDA Toolkit", "NVIDIA driver", "v69.6", "QUICK_START", "TROUBLESHOOTING", "RC_CHECKLIST", "RELEASE_GATE", "RELEASE_FREEZE", "DOCS_I18N_HYGIENE", "--result-health", "--diagnostics-help"),
    "VERSION.txt": ("version=v69.6", "refactor_stage=Этап 055", "ui_api_version=21", "QUICK_START_RU.txt", "TROUBLESHOOTING_RU.txt", "RC_CHECKLIST_RU.txt", "RELEASE_GATE_RU.txt", "RELEASE_FREEZE_RU.txt", "DOCS_I18N_HYGIENE_RU.txt", "--result-health", "--diagnostics-help"),
    "SUPPORT_BUNDLE_RU.txt": ("--support-bundle", "TunedImageSorter_CLI.exe", "исходные фотографии", "support-bundle", "--result-health", "result_health_check"),
    "SUPPORT_BUNDLE_EN.txt": ("--support-bundle", "TunedImageSorter_CLI.exe", "source photos", "support-bundle", "--result-health", "result_health_check"),
}


WINDOWS_PACKAGING_FILES: Tuple[WindowsPackagingFile, ...] = (
    WindowsPackagingFile("tools/windows_packaging/README_WINDOWS_PACKAGING_RU.md", "Russian Windows packaging instructions."),
    WindowsPackagingFile("tools/windows_packaging/README_WINDOWS_PACKAGING_EN.md", "English Windows packaging instructions."),
    WindowsPackagingFile("tools/windows_packaging/build_windows_gui.ps1", "Main PowerShell PyInstaller build script."),
    WindowsPackagingFile("tools/windows_packaging/build_windows_gui.bat", "cmd.exe wrapper for the PowerShell build script."),
    WindowsPackagingFile("tools/windows_packaging/run_gui_from_source.bat", "Convenience launcher for source-tree GUI smoke runs."),
    WindowsPackagingFile("tools/windows_packaging/smoke_test_packaging.py", "Import-safe packaging smoke-test."),
    WindowsPackagingFile("tools/windows_packaging/check_onnxruntime_provider.py", "Source-environment ONNX Runtime provider sanity check for GPU builds."),
    WindowsPackagingFile("tools/windows_packaging/extract_json_from_mixed_output.py", "Packaging helper that normalizes mixed diagnostic output into machine-parseable JSON."),
    WindowsPackagingFile("tools/windows_packaging/pyinstaller_gui_entry.py", "Shared PyInstaller entry point for the windowed GUI launcher and console CLI diagnostics launcher."),
    WindowsPackagingFile("tools/windows_packaging/pyinstaller_profile_common.py", "Shared PyInstaller profile collection rules for CPU/GPU specs."),
    WindowsPackagingFile("tools/windows_packaging/requirements-windows-common.txt", "Shared Windows dependency set."),
    WindowsPackagingFile("tools/windows_packaging/requirements-windows-cpu.txt", "CPU-oriented Windows dependency set."),
    WindowsPackagingFile("tools/windows_packaging/requirements-windows-gpu-cu12.txt", "CUDA 12 / NVIDIA GPU-oriented Windows dependency set."),
    WindowsPackagingFile("tools/windows_packaging/face_sorter_mvp_gui_cpu.spec", "PyInstaller one-folder CPU profile build with TunedImageSorter.exe windowed and TunedImageSorter_CLI.exe console diagnostics."),
    WindowsPackagingFile("tools/windows_packaging/face_sorter_mvp_gui_gpu_cuda12.spec", "PyInstaller one-folder NVIDIA GPU CUDA 12 profile build with TunedImageSorter.exe windowed and TunedImageSorter_CLI.exe console diagnostics."),
    WindowsPackagingFile("tools/windows_packaging/face_sorter_mvp_gui_console.spec", "Compatibility spec name for console diagnostics builds."),
    WindowsPackagingFile("tools/windows_packaging/face_sorter_mvp_gui_windowed.spec", "Compatibility spec name for windowed builds."),
    WindowsPackagingFile("face_sorter_mvp/ui/resources/app_icon.ico", "Application icon for PySide6/PyInstaller Windows builds."),
    WindowsPackagingFile("face_sorter_mvp/ui/resources/app_icon.png", "PNG application icon preview/source."),
    WindowsPackagingFile("face_sorter_mvp/core/frozen_diagnostics.py", "Frozen EXE diagnostic helpers and scan probe."),
    WindowsPackagingFile("face_sorter_mvp/core/diagnostics_help.py", "Diagnostics command-center help text."),
    WindowsPackagingFile("START_HERE_RU.txt", "Top-level Russian quick-start text copied next to the portable EXEs."),
    WindowsPackagingFile("START_HERE_EN.txt", "Top-level English quick-start text copied next to the portable EXEs."),
    WindowsPackagingFile("QUICK_START_RU.txt", "Top-level Russian one-page quick-start guide copied next to the portable EXEs."),
    WindowsPackagingFile("QUICK_START_EN.txt", "Top-level English one-page quick-start guide copied next to the portable EXEs."),
    WindowsPackagingFile("FIRST_RUN_RU.txt", "Top-level Russian first-run guide copied next to the portable EXEs."),
    WindowsPackagingFile("FIRST_RUN_EN.txt", "Top-level English first-run guide copied next to the portable EXEs."),
    WindowsPackagingFile("ERRORS_RU.txt", "Top-level Russian human-readable errors guide copied next to the portable EXEs."),
    WindowsPackagingFile("ERRORS_EN.txt", "Top-level English human-readable errors guide copied next to the portable EXEs."),
    WindowsPackagingFile("TROUBLESHOOTING_RU.txt", "Top-level Russian troubleshooting guide copied next to the portable EXEs."),
    WindowsPackagingFile("TROUBLESHOOTING_EN.txt", "Top-level English troubleshooting guide copied next to the portable EXEs."),
    WindowsPackagingFile("RC_CHECKLIST_RU.txt", "Top-level Russian release candidate checklist copied next to the portable EXEs."),
    WindowsPackagingFile("RC_CHECKLIST_EN.txt", "Top-level English release candidate checklist copied next to the portable EXEs."),
    WindowsPackagingFile("RELEASE_GATE_RU.txt", "Top-level Russian final release gate copied next to the portable EXEs."),
    WindowsPackagingFile("RELEASE_GATE_EN.txt", "Top-level English final release gate copied next to the portable EXEs."),
    WindowsPackagingFile("RELEASE_FREEZE_RU.txt", "Top-level Russian stable release packaging freeze note copied next to the portable EXEs."),
    WindowsPackagingFile("RELEASE_FREEZE_EN.txt", "Top-level English stable release packaging freeze note copied next to the portable EXEs."),
    WindowsPackagingFile("GPU_LITE_RU.txt", "Top-level Russian experimental GPU Lite first-run runtime setup note."),
    WindowsPackagingFile("GPU_LITE_EN.txt", "Top-level English experimental GPU Lite first-run runtime setup note."),
    WindowsPackagingFile("DUAL_GPU_PACKAGING_RU.txt", "Top-level Russian dual GPU packaging matrix and release docs."),
    WindowsPackagingFile("DUAL_GPU_PACKAGING_EN.txt", "Top-level English dual GPU packaging matrix and release docs."),
    WindowsPackagingFile("README_RU.txt", "Top-level Russian friend-ready portable package README."),
    WindowsPackagingFile("README_EN.txt", "Top-level English friend-ready portable package README."),
    WindowsPackagingFile("VERSION.txt", "Top-level portable package version marker."),
    WindowsPackagingFile("SUPPORT_BUNDLE_RU.txt", "Top-level Russian support-bundle instructions copied next to the portable EXEs."),
    WindowsPackagingFile("SUPPORT_BUNDLE_EN.txt", "Top-level English support-bundle instructions copied next to the portable EXEs."),
    WindowsPackagingFile("tools/windows_packaging/verify_friend_ready_package.py", "Friend-ready source/package/zip verification command."),
    WindowsPackagingFile("tools/windows_packaging/package_identity_report.py", "Static portable package identity report writer for CPU/GPU builds."),
    WindowsPackagingFile("tools/windows_packaging/make_release_bundle.py", "Create final public release bundle folder with SHA256SUMS and manifest."),
    WindowsPackagingFile("docs/USER_GUIDE_RU.md", "Russian quick GUI guide."),
    WindowsPackagingFile("docs/USER_GUIDE_EN.md", "English quick GUI guide."),
    WindowsPackagingFile("docs/HELP_RU.md", "Russian bilingual UI help."),
    WindowsPackagingFile("docs/HELP_EN.md", "English bilingual UI help."),
    WindowsPackagingFile("docs/DEVELOPER_NOTES_RU.md", "Russian developer notes for agents and maintainers."),
    WindowsPackagingFile("docs/DEVELOPER_NOTES_EN.md", "English developer notes for agents and maintainers."),
)


def default_project_root() -> Path:
    """Return the source tree root when running from the unpacked project."""
    return SCRIPT_DIR.parent


def _normalize_project_root(project_root: Optional[str | Path] = None) -> Path:
    return Path(project_root).expanduser().resolve() if project_root is not None else default_project_root().resolve()


def windows_packaging_plan(project_root: Optional[str | Path] = None) -> WindowsPackagingPlan:
    """Return the unified CPU/GPU Windows packaging plan without executing any build step."""
    root = _normalize_project_root(project_root)
    return WindowsPackagingPlan(
        version=SCRIPT_VERSION,
        refactor_stage="Этап 055",
        schema_version=WINDOWS_PACKAGING_SCHEMA_VERSION,
        project_root=root,
        packaging_dir=root / WINDOWS_PACKAGING_DIR,
        output_dir=root / WINDOWS_PACKAGING_OUTPUT_DIR,
        build_commands=(
            r"tools\windows_packaging\build_windows_gui.ps1 -Profile cpu -InstallRequirements",
            r"tools\windows_packaging\build_windows_gui.ps1 -Profile gpu -InstallRequirements",
            r"tools\windows_packaging\build_windows_gui.ps1 -Profile gpu-lite -InstallRequirements",
            r"tools\windows_packaging\build_windows_gui.ps1 -Profile cpu -SkipChecks",
        ),
        files=WINDOWS_PACKAGING_FILES,
        notes=(
            "Build from the project root one level above the face_sorter_mvp package; do not run from inside the package folder.",
            "The default outputs are one-folder PyInstaller folders under dist/windows/TunedImageSorter_CPU and dist/windows/TunedImageSorter_GPU_FULL.",
            "Successful builds also create adjacent portable ZIP archives under dist/windows unless -NoZipOutput is set.",
            "v69.6 default builds contain TunedImageSorter.exe as a no-console GUI launcher, TunedImageSorter_CLI.exe as the console diagnostics launcher and top-level START_HERE/QUICK_START/FIRST_RUN/ERRORS/TROUBLESHOOTING/RC_CHECKLIST/RELEASE_GATE/RELEASE_FREEZE/DOCS_I18N_HYGIENE/README/VERSION/SUPPORT_BUNDLE files for friend-ready sharing.",
            "The packaging layer is additive and does not change recognition, clustering, pipeline, project.json, resume or report formats.",
            "v69.6 keeps the unified CPU/GPU source baseline and adds pre-release polish verification on top of the stable release freeze; ML/pipeline/existing report formats are unchanged.",
            "v64.9 is the confirmed CPU fallback; v65.3 was confirmed as the stable Windows GPU portable one-folder EXE base; v65.4 consolidated CPU and GPU profiles into one stable source baseline.",
        ),
    )


def verify_friend_ready_source_layout(project_root: Optional[str | Path] = None) -> FriendReadySourceCheckResult:
    """Verify source-side files required for a friend-ready portable package."""
    root = _normalize_project_root(project_root)
    checked = []
    missing = []
    errors = []

    for rel in FRIEND_READY_TOP_LEVEL_FILES:
        checked.append(rel)
        if not (root / rel).exists():
            missing.append(rel)

    verifier = root / "tools" / "windows_packaging" / "verify_friend_ready_package.py"
    checked.append("tools/windows_packaging/verify_friend_ready_package.py")
    if not verifier.exists():
        missing.append("tools/windows_packaging/verify_friend_ready_package.py")

    for rel, tokens in FRIEND_READY_DOC_TOKEN_CHECKS.items():
        path = root / rel
        if not path.exists():
            continue
        checked.append(f"{rel}:content")
        text = path.read_text(encoding="utf-8", errors="replace")
        for token in tokens:
            if token not in text:
                errors.append(f"{rel} must mention {token!r}")

    return FriendReadySourceCheckResult(
        ok=not missing and not errors,
        version=SCRIPT_VERSION,
        refactor_stage="Этап 055",
        schema_version=WINDOWS_PACKAGING_SCHEMA_VERSION,
        project_root=root,
        checked_files=tuple(checked),
        missing_files=tuple(missing),
        warnings=(),
        errors=tuple(errors),
    )


def verify_windows_packaging(project_root: Optional[str | Path] = None) -> WindowsPackagingCheckResult:
    """Verify required Windows packaging files exist in the source tree."""
    plan = windows_packaging_plan(project_root)
    checked = []
    missing = []
    errors = []
    root = plan.project_root

    if not (root / "face_sorter_mvp" / "__init__.py").exists():
        errors.append("project_root must be the folder one level above the face_sorter_mvp package")

    for item in plan.files:
        checked.append(item.relative_path)
        if item.required and not (root / item.relative_path).exists():
            missing.append(item.relative_path)

    # v69.6 packaging contract: the default CPU/GPU profile specs must create
    # two launchers from one frozen app bundle.  TunedImageSorter.exe is windowed
    # for Explorer users; TunedImageSorter_CLI.exe keeps a console for diagnostics.
    # This is a source-level check only; it does not run PyInstaller.
    for rel in (
        "tools/windows_packaging/face_sorter_mvp_gui_cpu.spec",
        "tools/windows_packaging/face_sorter_mvp_gui_gpu_cuda12.spec",
    ):
        spec_path = root / rel
        if not spec_path.exists():
            continue
        spec_text = spec_path.read_text(encoding="utf-8")
        checked.append(f"{rel}:launcher_split")
        if 'name="TunedImageSorter"' not in spec_text or "console=False" not in spec_text:
            errors.append(f"{rel} must define TunedImageSorter.exe as a windowed/no-console launcher")
        if 'name="TunedImageSorter_CLI"' not in spec_text or "console=True" not in spec_text:
            errors.append(f"{rel} must define TunedImageSorter_CLI.exe as a console diagnostics launcher")

    build_script = root / "tools/windows_packaging/build_windows_gui.ps1"
    if build_script.exists():
        build_text = build_script.read_text(encoding="utf-8")
        checked.append("tools/windows_packaging/build_windows_gui.ps1:cli_diagnostics")
        if "TunedImageSorter_CLI.exe --runtime-preflight" not in build_text:
            errors.append("build_windows_gui.ps1 must direct frozen diagnostics through TunedImageSorter_CLI.exe")
        checked.append("tools/windows_packaging/build_windows_gui.ps1:friend_ready_docs")
        if "Copy-FriendReadyDocs" not in build_text or "verify_friend_ready_package.py" not in build_text:
            errors.append("build_windows_gui.ps1 must copy and verify friend-ready START_HERE/README/VERSION files")
        checked.append("tools/windows_packaging/build_windows_gui.ps1:pinned_gpu_runtime")
        for token in (
            "onnxruntime-gpu==1.26.0",
            "nvidia-cudnn-cu12==9.23.1.3",
            "--require-pinned-gpu-runtime",
            "--require-cuda-session",
            "pip uninstall -y onnxruntime onnxruntime-gpu",
            "--force-reinstall --no-deps",
        ):
            if token not in build_text:
                errors.append(f"build_windows_gui.ps1 must preserve pinned GPU runtime token {token!r}")
        checked.append("tools/windows_packaging/build_windows_gui.ps1:portable_zip_default")
        for token in (
            "$ShouldCreateZip = $ZipOutput -or (-not $NoZipOutput)",
            "Compress-Archive -Path $OutputDir -DestinationPath $ZipPath",
            "verify_friend_ready_package.py --zip $ZipPath",
            "Portable zip:",
        ):
            if token not in build_text:
                errors.append(f"build_windows_gui.ps1 must create and verify a portable zip by default; missing token {token!r}")
        checked.append("tools/windows_packaging/build_windows_gui.ps1:portable_manifest")
        for token in (
            "Write-PortableManifest",
            "portable_manifest.json",
            'package_kind = "friend-ready-portable"',
            "ordinary Start must run mode=all, not apply-names",
            'Write-Host "Portable manifest OK:',
        ):
            if token not in build_text:
                errors.append(f"build_windows_gui.ps1 must create portable_manifest.json; missing token {token!r}")
        checked.append("tools/windows_packaging/build_windows_gui.ps1:package_identity_report")
        checked.append("tools/windows_packaging/build_windows_gui.ps1:friend_ready_quick_start_troubleshooting")
        for token in ("QUICK_START_RU.txt", "QUICK_START_EN.txt", "TROUBLESHOOTING_RU.txt", "TROUBLESHOOTING_EN.txt"):
            if token not in build_text:
                errors.append(f"build_windows_gui.ps1 must copy friend-ready quick start/troubleshooting docs; missing token {token!r}")
        for token in (
            "package_identity_report.py",
            "package_identity_check.json",
            "package_identity_check.txt",
            'Invoke-Checked "package identity report"',
        ):
            if token not in build_text:
                errors.append(f"build_windows_gui.ps1 must write package identity reports; missing token {token!r}")

    verifier = root / "tools/windows_packaging/verify_friend_ready_package.py"
    if verifier.exists():
        verifier_text = verifier.read_text(encoding="utf-8")
        checked.append("tools/windows_packaging/verify_friend_ready_package.py:portable_manifest")
        for token in (
            "PORTABLE_MANIFEST_FILENAME",
            "portable_manifest.json",
            "_verify_manifest",
            "zip_package_layout",
            "ordinary Start must run mode=all, not apply-names",
            "PACKAGE_IDENTITY_JSON",
            "package_identity_check.json",
            "_verify_package_identity_report",
        ):
            if token not in verifier_text:
                errors.append(f"verify_friend_ready_package.py must validate portable_manifest.json and package identity reports; missing token {token!r}")

    identity_report = root / "tools/windows_packaging/package_identity_report.py"
    if identity_report.exists():
        identity_text = identity_report.read_text(encoding="utf-8")
        checked.append("tools/windows_packaging/package_identity_report.py:static_package_identity")
        for token in (
            "PACKAGE_IDENTITY_STAGE",
            "package_identity_check.json",
            "package_identity_check.txt",
            "ordinary Start must run mode=all, not apply-names",
            "runtime_preflight_gpu_build_check.json",
        ):
            if token not in identity_text:
                errors.append(f"package_identity_report.py must preserve static package identity token {token!r}")

    gpu_req = root / "tools/windows_packaging/requirements-windows-gpu-cu12.txt"
    if gpu_req.exists():
        req_text = gpu_req.read_text(encoding="utf-8")
        checked.append("tools/windows_packaging/requirements-windows-gpu-cu12.txt:pinned_gpu_runtime")
        for token in (
            "onnxruntime-gpu==1.26.0",
            "nvidia-cuda-runtime-cu12==12.9.79",
            "nvidia-cudnn-cu12==9.23.1.3",
            "nvidia-cublas-cu12==12.9.2.10",
            "nvidia-cuda-nvrtc-cu12==12.9.86",
            "nvidia-cufft-cu12==11.4.1.4",
            "nvidia-curand-cu12==10.3.10.19",
            "nvidia-nvjitlink-cu12==12.9.86",
        ):
            if token not in req_text:
                errors.append(f"GPU requirements must pin {token!r}")

    provider_check = root / "tools/windows_packaging/check_onnxruntime_provider.py"
    if provider_check.exists():
        provider_text = provider_check.read_text(encoding="utf-8")
        checked.append("tools/windows_packaging/check_onnxruntime_provider.py:cuda_session_smoke")
        for token in ("EXPECTED_GPU_RUNTIME_VERSIONS", "--require-pinned-gpu-runtime", "--require-cuda-session", "CUDAExecutionProvider session smoke-test"):
            if token not in provider_text:
                errors.append(f"ONNX Runtime provider check must include GPU runtime guard token {token!r}")

    entry_script = root / "tools/windows_packaging/pyinstaller_gui_entry.py"
    if entry_script.exists():
        entry_text = entry_script.read_text(encoding="utf-8")
        checked.append("tools/windows_packaging/pyinstaller_gui_entry.py:windowed_stdio_guard")
        if "_ensure_non_null_stdio()" not in entry_text or "_NullTextStream" not in entry_text:
            errors.append("pyinstaller GUI entry must install safe stdout/stderr sinks for windowed/no-console GUI runs")
        checked.append("tools/windows_packaging/pyinstaller_gui_entry.py:cli_app_dispatch")
        if "--result-health" not in entry_text or "--support-bundle" not in entry_text or "main_impl" not in entry_text:
            errors.append("pyinstaller CLI entry must dispatch --result-health/--support-bundle to the main CLI instead of falling back to diagnostics usage")
        checked.append("tools/windows_packaging/pyinstaller_gui_entry.py:console_encoding")
        if "GetConsoleOutputCP" not in entry_text or "GetOEMCP" in entry_text:
            errors.append("pyinstaller CLI entry must use the active console output code page, not the fixed OEM code page, to avoid Cyrillic mojibake")

    bug_report = root / "face_sorter_mvp" / "reports" / "bug_report.py"
    if bug_report.exists():
        bug_text = bug_report.read_text(encoding="utf-8")
        checked.append("face_sorter_mvp/reports/bug_report.py:result_health_in_support_bundle")
        required_tokens = (
            "_build_result_health_for_support_bundle",
            "build_result_health_summary",
            "result_health_summary",
            "reports/result_health_check.json",
            "reports/result_health_check.txt",
            "includes_result_health_check",
        )
        for token in required_tokens:
            if token not in bug_text:
                errors.append(f"support-bundle must include result-health diagnostics token {token!r}")

    legacy_core = root / "face_sorter_mvp/face_sorter_mvp.py"
    if legacy_core.exists():
        legacy_text = legacy_core.read_text(encoding="utf-8")
        checked.append("face_sorter_mvp/face_sorter_mvp.py:windowed_stdio_guard")
        if "def ensure_non_null_stdio" not in legacy_text or "class NullTextStream" not in legacy_text:
            errors.append("legacy core must expose ensure_non_null_stdio() so backend GUI jobs cannot crash when stdio is None")
        if "ensure_non_null_stdio()" not in legacy_text:
            errors.append("scan path must call ensure_non_null_stdio() before inline progress output")
        checked.append("face_sorter_mvp/face_sorter_mvp.py:support_bundle_alias")
        if "--support-bundle" not in legacy_text or "support-bundle" not in legacy_text:
            errors.append("CLI must expose --support-bundle / --mode support-bundle as a safe bug-report alias")
        checked.append("face_sorter_mvp/face_sorter_mvp.py:captured_subprocess_no_console")
        if "windows_no_window_creationflags" not in legacy_text or "creationflags=windows_no_window_creationflags()" not in legacy_text:
            errors.append("captured legacy subprocess diagnostics must use CREATE_NO_WINDOW to avoid terminal flashes from the windowed GUI")

    preflight = root / "face_sorter_mvp" / "core" / "preflight.py"
    if preflight.exists():
        preflight_text = preflight.read_text(encoding="utf-8")
        checked.append("face_sorter_mvp/core/preflight.py:captured_subprocess_no_console")
        if "_windows_no_window_creationflags" not in preflight_text or "creationflags=_windows_no_window_creationflags()" not in preflight_text:
            errors.append("runtime preflight subprocess probes must use CREATE_NO_WINDOW to avoid terminal flashes from the windowed GUI")

    main_window = root / "face_sorter_mvp" / "ui" / "main_window.py"
    if main_window.exists():
        main_window_text = main_window.read_text(encoding="utf-8")
        checked.append("face_sorter_mvp/ui/main_window.py:shell_open_no_console")
        if "ShellExecuteW" not in main_window_text or "_open_path_windows_no_console" not in main_window_text:
            errors.append("UI open-file/open-folder actions must use ShellExecuteW on Windows to avoid brief console flashes")
        if "self.open_final_dir()" not in main_window_text or "apply-names" not in main_window_text:
            # Keep the exact guard below simple and source-level only.
            errors.append("apply-names auto-open must target final/ instead of reports/")

    friend_ready = verify_friend_ready_source_layout(root)
    checked.extend(f"friend_ready:{item}" for item in friend_ready.checked_files)
    missing.extend(friend_ready.missing_files)
    errors.extend(friend_ready.errors)

    ok = not missing and not errors
    return WindowsPackagingCheckResult(
        ok=ok,
        version=SCRIPT_VERSION,
        refactor_stage="Этап 055",
        schema_version=WINDOWS_PACKAGING_SCHEMA_VERSION,
        project_root=root,
        checked_files=tuple(checked),
        missing_files=tuple(missing),
        warnings=(),
        errors=tuple(errors),
    )


__all__ = [
    "WINDOWS_PACKAGING_SCHEMA_VERSION",
    "WINDOWS_PACKAGING_DIR",
    "WINDOWS_PACKAGING_OUTPUT_DIR",
    "WINDOWS_PACKAGING_FILES",
    "FRIEND_READY_TOP_LEVEL_FILES",
    "FRIEND_READY_DOC_TOKEN_CHECKS",
    "WindowsPackagingFile",
    "WindowsPackagingPlan",
    "WindowsPackagingCheckResult",
    "FriendReadySourceCheckResult",
    "default_project_root",
    "windows_packaging_plan",
    "verify_windows_packaging",
    "verify_friend_ready_source_layout",
]
