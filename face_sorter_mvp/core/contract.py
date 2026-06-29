# -*- coding: utf-8 -*-
"""Frozen backend/UI contract metadata and compatibility checks.

v69.6 / Этап 055 keeps this import-safe module as the place where future
Windows/PySide6 UI integrations can discover and verify the public backend API
surface that is expected to remain stable.  The checks here do not import ML
runtime packages, do not scan photos and do not mutate project folders.
"""
from __future__ import annotations

import importlib
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Tuple

from .constants import SCRIPT_VERSION

UI_CONTRACT_SCHEMA_VERSION = 1
UI_CONTRACT_NAME = "face_sorter_mvp_backend_ui_contract"
UI_CONTRACT_STAGE = "Этап 055"
UI_CONTRACT_API_VERSION = 21

RECOMMENDED_UI_ENTRYPOINTS: Tuple[str, ...] = (
    "face_sorter_mvp.backend.run",
    "face_sorter_mvp.backend.create_run_config",
    "face_sorter_mvp.backend.create_backend_job",
    "face_sorter_mvp.backend.runtime_preflight",
    "face_sorter_mvp.backend.run_backend_self_test",
    "face_sorter_mvp.backend.backend_capabilities",
    "face_sorter_mvp.ui.launch_ui",
)

REQUIRED_CAPABILITY_FLAGS: Tuple[str, ...] = (
    "supports_project_json",
    "supports_resume",
    "supports_review_clusters",
    "supports_progress_callbacks",
    "supports_package_main",
    "supports_diagnostics_report",
    "supports_cli_wizard_module",
    "supports_reports_modules",
    "supports_core_pipeline_owner",
    "supports_stage_modules",
    "supports_ui_api",
    "supports_backend_self_test",
    "supports_backend_job_runner",
    "supports_ui_session_state",
    "supports_ui_parameter_schema",
    "supports_runtime_preflight",
    "supports_ui_status_report",
    "supports_ui_contract_freeze",
    "supports_pyside6_ui_skeleton",
    "supports_pyside6_ui_schema_session_form",
    "supports_pyside6_job_progress_polish",
    "supports_pyside6_resume_recent_ui",
    "supports_pyside6_reports_review_ui",
    "supports_windows_packaging",
    "supports_ui_polish",
    "supports_release_check",
    "supports_ui_usability_pass",
    "supports_ui_localization_help_pass",
    "supports_windows_onefolder_build_profiles",
)

REQUIRED_CORE_MODULES: Tuple[str, ...] = (
    "core.constants",
    "core.config",
    "core.contracts",
    "core.project_state",
    "core.pipeline",
    "core.stages",
    "core.stage_scan",
    "core.stage_cluster",
    "core.stage_assign",
    "core.stage_copy",
    "core.stage_report",
    "core.stage_review",
    "core.api",
    "core.self_test",
    "core.job",
    "core.session",
    "core.ui_schema",
    "core.preflight",
    "core.status",
    "core.review_ui",
    "core.contract",
    "core.windows_packaging",
    "core.ui_polish",
    "core.release",
    "core.ui_usability",
    "core.frozen_runtime",
    "reports",
    "i18n",
    "cli_wizard",
    "ui",
    "ui.main_window",
)

# Stable public names a future UI may import from face_sorter_mvp.backend and,
# via package re-export, from face_sorter_mvp.  Internal/legacy stage helpers are
# intentionally not listed here as stable UI dependencies even if they remain
# exported for compatibility.
REQUIRED_UI_EXPORTS: Tuple[str, ...] = (
    "RunConfig",
    "RunResult",
    "ProgressCallbacks",
    "NullProgressCallbacks",
    "SilentProgressCallbacks",
    "ApiValidationResult",
    "QualityProfileInfo",
    "ProjectSummary",
    "CallbackEvent",
    "RecordingProgressCallbacks",
    "UiBackendApi",
    "ui_backend_api",
    "create_run_config",
    "validate_config_for_ui",
    "inspect_project",
    "find_resume_projects",
    "prepare_project_folder",
    "suggest_output_dir",
    "get_quality_profiles",
    "get_quality_profile_dicts",
    "pipeline_modes",
    "pipeline_stages",
    "mode_stages",
    "UiSessionState",
    "UiRecentProject",
    "default_ui_state_path",
    "default_ui_session_state",
    "load_ui_session_state",
    "save_ui_session_state",
    "update_ui_session_state",
    "remember_recent_project",
    "prune_recent_projects",
    "config_to_ui_session_state",
    "ui_session_to_run_config",
    "UI_SCHEMA_VERSION",
    "UiFieldOption",
    "UiParameterSpec",
    "UiFormSection",
    "UiRunConfigSchema",
    "get_ui_form_sections",
    "get_ui_parameter_schema",
    "get_ui_run_config_schema",
    "get_ui_run_config_schema_dict",
    "profile_settings_diff",
    "run_config_to_ui_values",
    "ui_values_to_overrides",
    "validate_ui_values_against_schema",
    "PREFLIGHT_SCHEMA_VERSION",
    "PackageStatus",
    "GpuPreflightStatus",
    "RuntimePreflightResult",
    "package_status",
    "collect_package_statuses",
    "gpu_preflight",
    "runtime_preflight",
    "runtime_preflight_summary",
    "UI_STATUS_SCHEMA_VERSION",
    "UiIssue",
    "UiStatusReport",
    "UiStatusSummary",
    "ui_issue",
    "ui_status_report",
    "summarize_status_report",
    "merge_status_reports",
    "issue_from_exception",
    "status_from_validation_result",
    "status_from_preflight_result",
    "status_from_self_test_result",
    "status_from_job_snapshot",
    "BackendSelfTestCheck",
    "BackendSelfTestResult",
    "run_backend_self_test",
    "ui_contract_snapshot",
    "BackendJob",
    "BackendJobSnapshot",
    "BackendRunner",
    "create_backend_job",
    "run_backend_job_sync",
    "backend_capabilities",
    "collect_ui_bug_report_diagnostics",
    "REVIEW_UI_SCHEMA_VERSION",
    "REVIEW_UI_ACTIONS",
    "ReviewUiReportFile",
    "ReviewUiClusterRow",
    "ReviewUiSnapshot",
    "ReviewUiSaveResult",
    "load_review_ui_snapshot",
    "save_review_ui_decisions",
    "WINDOWS_PACKAGING_SCHEMA_VERSION",
    "WINDOWS_PACKAGING_DIR",
    "WINDOWS_PACKAGING_OUTPUT_DIR",
    "WINDOWS_PACKAGING_FILES",
    "WindowsPackagingFile",
    "WindowsPackagingPlan",
    "WindowsPackagingCheckResult",
    "default_project_root",
    "windows_packaging_plan",
    "verify_windows_packaging",
    "UI_POLISH_SCHEMA_VERSION",
    "UI_POLISH_STAGE",
    "UI_ICON_RELATIVE_PATH",
    "UI_ICON_PNG_RELATIVE_PATH",
    "UI_LANGUAGE_CHOICES",
    "UI_THEME_CHOICES",
    "UI_DENSITY_CHOICES",
    "UiInstructionStep",
    "UiInstructionSection",
    "UiPolishSettings",
    "UiPolishSnapshot",
    "normalize_ui_language",
    "effective_ui_language",
    "normalize_ui_theme",
    "normalize_ui_density",
    "ui_text",
    "get_ui_instruction_sections",
    "ui_polish_settings_from_session",
    "apply_ui_polish_settings_to_session",
    "ui_polish_snapshot",
    "RELEASE_CHECK_SCHEMA_VERSION",
    "RELEASE_CHECK_STAGE",
    "ReleaseCheckItem",
    "ReleaseCheckResult",
    "run_release_check",
    "UI_USABILITY_SCHEMA_VERSION",
    "UI_USABILITY_STAGE",
    "UiUsabilityHint",
    "UiUsabilitySnapshot",
    "classify_path_state",
    "build_run_summary",
    "build_paths_summary",
    "get_ui_usability_hints",
    "ui_usability_snapshot",
    "UI_CONTRACT_SCHEMA_VERSION",
    "UI_CONTRACT_NAME",
    "UI_CONTRACT_API_VERSION",
    "UiContractSnapshot",
    "UiContractCheckResult",
    "ui_contract_freeze_snapshot",
    "verify_ui_contract",
    "UI_SKELETON_VERSION",
    "is_pyside6_available",
    "launch_ui",
)

@dataclass(frozen=True)
class UiContractSnapshot:
    """Serializable snapshot of the frozen backend/UI contract."""

    contract_name: str
    schema_version: int
    app_version: str
    refactor_stage: str
    ui_api_version: int
    recommended_entrypoints: Tuple[str, ...]
    required_exports: Tuple[str, ...]
    required_capability_flags: Tuple[str, ...]
    required_core_modules: Tuple[str, ...]
    notes: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class UiContractCheckResult:
    """Result of verifying the public backend/UI contract surface."""

    ok: bool
    version: str
    refactor_stage: str
    ui_api_version: int
    checked_exports: Tuple[str, ...]
    missing_backend_exports: Tuple[str, ...] = ()
    missing_package_exports: Tuple[str, ...] = ()
    missing_capability_flags: Tuple[str, ...] = ()
    missing_core_modules: Tuple[str, ...] = ()
    errors: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def ui_contract_freeze_snapshot() -> UiContractSnapshot:
    """Return the frozen UI/backend contract description without side effects."""
    return UiContractSnapshot(
        contract_name=UI_CONTRACT_NAME,
        schema_version=UI_CONTRACT_SCHEMA_VERSION,
        app_version=SCRIPT_VERSION,
        refactor_stage=UI_CONTRACT_STAGE,
        ui_api_version=UI_CONTRACT_API_VERSION,
        recommended_entrypoints=RECOMMENDED_UI_ENTRYPOINTS,
        required_exports=REQUIRED_UI_EXPORTS,
        required_capability_flags=REQUIRED_CAPABILITY_FLAGS,
        required_core_modules=REQUIRED_CORE_MODULES,
        notes=(
            "Treat these exports as the stable UI-facing backend API for the first PySide6 UI steps.",
            "Do not build UI code on cli_wizard internals or legacy face_sorter_mvp.py implementation details.",
            "Stage functions remain exported for compatibility, but the preferred UI entrypoints are backend.run() and create_backend_job().",
            "The optional PySide6 UI is launched with python -m face_sorter_mvp.ui and must stay import-safe when PySide6 is missing.",
            "v60 added Windows packaging scripts/specs/smoke-tests while keeping schema/session/job/resume/reports UI behavior unchanged.",
            "v62 adds UI polish settings, localized quick instructions and icon assets without changing backend algorithms or project formats.",
            "v63 adds usability-only PySide6 improvements without changing backend algorithms, CLI wizard or project/report formats.",
            "v64 adds the first real Windows one-folder packaging pass: CPU/GPU profile specs, build scripts, documentation and frozen runtime location helpers.",
        ),
    )


def _import_backend_module() -> Any:
    try:
        return importlib.import_module("face_sorter_mvp.backend")
    except ImportError:
        return importlib.import_module("backend")


def _import_package_module() -> Any:
    try:
        return importlib.import_module("face_sorter_mvp")
    except ImportError:
        return None


def verify_ui_contract() -> UiContractCheckResult:
    """Verify that backend and package exports satisfy the frozen UI contract.

    This is intended for self-tests and release checks.  It does not initialize
    ML runtimes and should be safe to call during GUI startup diagnostics.
    """
    errors = []
    warnings = []
    snapshot = ui_contract_freeze_snapshot()
    missing_backend_exports = []
    missing_package_exports = []
    missing_capability_flags = []
    missing_core_modules = []

    try:
        backend = _import_backend_module()
        backend_all = set(getattr(backend, "__all__", ()))
        for name in snapshot.required_exports:
            if name not in backend_all or not hasattr(backend, name):
                missing_backend_exports.append(name)

        capabilities = backend.backend_capabilities()
        for flag in snapshot.required_capability_flags:
            if capabilities.get(flag) is not True:
                missing_capability_flags.append(flag)
        for module_name in snapshot.required_core_modules:
            if module_name not in capabilities.get("core_modules", ()):  # type: ignore[operator]
                missing_core_modules.append(module_name)
        if capabilities.get("version") != SCRIPT_VERSION:
            errors.append(f"backend_capabilities version mismatch: {capabilities.get('version')!r} != {SCRIPT_VERSION!r}")
        if capabilities.get("ui_api_version") != UI_CONTRACT_API_VERSION:
            errors.append(f"ui_api_version mismatch: {capabilities.get('ui_api_version')!r} != {UI_CONTRACT_API_VERSION!r}")
        if capabilities.get("refactor_stage") != UI_CONTRACT_STAGE:
            errors.append(f"refactor_stage mismatch: {capabilities.get('refactor_stage')!r} != {UI_CONTRACT_STAGE!r}")
    except Exception as exc:  # pragma: no cover - defensive diagnostics path
        errors.append(f"backend contract verification failed: {type(exc).__name__}: {exc}")

    try:
        package = _import_package_module()
        if package is not None:
            package_all = set(getattr(package, "__all__", ()))
            for name in snapshot.required_exports:
                if name not in package_all or not hasattr(package, name):
                    missing_package_exports.append(name)
        else:
            warnings.append("Package root face_sorter_mvp is not importable in this mode; backend exports were still checked.")
    except Exception as exc:  # pragma: no cover - defensive diagnostics path
        warnings.append(f"package root contract verification skipped: {type(exc).__name__}: {exc}")

    ok = not (errors or missing_backend_exports or missing_package_exports or missing_capability_flags or missing_core_modules)
    return UiContractCheckResult(
        ok=ok,
        version=SCRIPT_VERSION,
        refactor_stage=UI_CONTRACT_STAGE,
        ui_api_version=UI_CONTRACT_API_VERSION,
        checked_exports=snapshot.required_exports,
        missing_backend_exports=tuple(missing_backend_exports),
        missing_package_exports=tuple(missing_package_exports),
        missing_capability_flags=tuple(missing_capability_flags),
        missing_core_modules=tuple(missing_core_modules),
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


__all__ = [
    "UI_CONTRACT_SCHEMA_VERSION",
    "UI_CONTRACT_NAME",
    "UI_CONTRACT_STAGE",
    "UI_CONTRACT_API_VERSION",
    "RECOMMENDED_UI_ENTRYPOINTS",
    "REQUIRED_CAPABILITY_FLAGS",
    "REQUIRED_CORE_MODULES",
    "REQUIRED_UI_EXPORTS",
    "UiContractSnapshot",
    "UiContractCheckResult",
    "ui_contract_freeze_snapshot",
    "verify_ui_contract",
]
