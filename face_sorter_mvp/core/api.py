# -*- coding: utf-8 -*-
"""Stable UI-facing backend API helpers.

v69.6 / Этап 055 keeps this import-safe module as the recommended boundary
for a future Windows/PySide6 UI and exposes session-state helpers.  The functions here do not start the console
wizard and do not import heavy ML packages at module import time.  When a helper
needs legacy defaults or validation rules, it loads the legacy implementation
lazily inside the function call.
"""
from __future__ import annotations

import copy
import datetime as dt
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import ProgressCallbacks, RunConfig, RunResult, stages_for_mode
from .constants import MODE_STAGE_MAP, PIPELINE_STAGES, PROJECT_FILENAME, SCRIPT_VERSION
from .project_state import (
    default_project_db_path,
    describe_run_state_for_user,
    ensure_project_structure,
    find_unfinished_result_dirs,
    project_json_path,
    read_legacy_run_state,
    read_run_state,
    resume_mode_from_state,
)
from .session import (
    UI_SESSION_SCHEMA_VERSION,
    UiRecentProject,
    UiSessionState,
    config_to_ui_session_state,
    default_ui_session_state,
    default_ui_state_path,
    load_ui_session_state,
    prune_recent_projects,
    remember_recent_project,
    save_ui_session_state,
    ui_session_state_from_dict,
    ui_session_to_run_config,
    update_ui_session_state,
)


@dataclass(frozen=True)
class ApiValidationResult:
    """Validation result that is convenient for GUI forms.

    Unlike the legacy CLI validators, this object does not terminate the
    process.  UI code can show ``errors`` and ``warnings`` in a dialog.
    """

    ok: bool
    errors: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QualityProfileInfo:
    """Stable description of one quality preset for UI controls."""

    key: str
    title: str
    short: str
    effect: str
    warning: str = ""
    settings: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectSummary:
    """Small, serializable summary of a Face Sorter project/result folder."""

    path: Path
    exists: bool
    has_project_json: bool = False
    has_legacy_state: bool = False
    status: str = "unknown"
    stage: str = "unknown"
    last_successful_stage: str = ""
    started_at: str = ""
    updated_at: str = ""
    finished_at: str = ""
    input_dir: str = ""
    output_dir: str = ""
    profile: str = ""
    mode: str = ""
    model: str = ""
    use_gpu: bool = False
    files_total: Optional[int] = None
    files_scanned: int = 0
    copy_total: Optional[int] = None
    files_copied: int = 0
    stages_completed: Tuple[str, ...] = ()
    error: str = ""
    db_path: Optional[Path] = None
    has_database: bool = False
    can_resume: bool = False
    resume_mode: str = "all"
    display_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["path"] = str(self.path)
        data["db_path"] = str(self.db_path) if self.db_path else None
        return data


@dataclass(frozen=True)
class CallbackEvent:
    """One callback event captured by RecordingProgressCallbacks."""

    kind: str
    stage: str
    message: str = ""
    done: Optional[int] = None
    total: Optional[int] = None
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RecordingProgressCallbacks(ProgressCallbacks):
    """Simple callback recorder useful for tests and UI adapters.

    A PySide6 adapter can either subclass ``ProgressCallbacks`` directly or use
    this recorder as a bridge and poll/drain captured events.
    """

    handles_console_output = True

    def __init__(self) -> None:
        self.events: List[CallbackEvent] = []

    def _append(self, event: CallbackEvent) -> None:
        self.events.append(event)

    def on_stage(self, stage: str, message: str = "", **data: Any) -> None:
        self._append(CallbackEvent("stage", stage, message, data=dict(data)))

    def on_progress(self, stage: str, done: int, total: Optional[int] = None, **data: Any) -> None:
        self._append(CallbackEvent("progress", stage, "", done=done, total=total, data=dict(data)))

    def on_warning(self, stage: str, message: str, **data: Any) -> None:
        self._append(CallbackEvent("warning", stage, message, data=dict(data)))

    def on_error(self, stage: str, message: str, **data: Any) -> None:
        self._append(CallbackEvent("error", stage, message, data=dict(data)))

    def on_info(self, stage: str, message: str, **data: Any) -> None:
        self._append(CallbackEvent("info", stage, message, data=dict(data)))

    def drain_events(self) -> List[CallbackEvent]:
        events = list(self.events)
        self.events.clear()
        return events

    def to_dicts(self) -> List[Dict[str, Any]]:
        return [event.to_dict() for event in self.events]


@dataclass(frozen=True)
class UiBackendApi:
    """Versioned API descriptor for a future UI integration."""

    version: str
    refactor_stage: str
    api_version: int
    recommended_entrypoint: str
    supports_cancel_request: bool
    supports_progress_callbacks: bool
    supports_project_inspection: bool
    supports_resume_candidates: bool
    supports_quality_profiles: bool
    supports_backend_self_test: bool = True
    supports_backend_job_runner: bool = True
    supports_ui_session_state: bool = True
    supports_ui_parameter_schema: bool = True
    supports_runtime_preflight: bool = True
    supports_ui_status_report: bool = True
    supports_ui_contract_freeze: bool = True
    supports_pyside6_ui_skeleton: bool = True
    supports_pyside6_ui_schema_session_form: bool = True
    supports_pyside6_job_progress_polish: bool = True
    supports_pyside6_resume_recent_ui: bool = True
    supports_pyside6_reports_review_ui: bool = True
    supports_windows_packaging: bool = True
    supports_ui_polish: bool = True
    supports_release_check: bool = True
    supports_ui_usability_pass: bool = True
    supports_ui_localization_help_pass: bool = True
    supports_windows_onefolder_build_profiles: bool = True
    supports_windows_no_console_gui_launcher: bool = True
    supports_cli_diagnostics_launcher: bool = True
    supports_result_health_check: bool = True
    supports_soft_cancel_request: bool = True
    supports_hard_cancel: bool = False
    notes: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def ui_backend_api() -> UiBackendApi:
    """Return stable UI API metadata without importing the legacy ML layer."""
    return UiBackendApi(
        version=SCRIPT_VERSION,
        refactor_stage="Этап 055",
        api_version=21,
        recommended_entrypoint="face_sorter_mvp.backend.run",
        supports_cancel_request=False,
        supports_progress_callbacks=True,
        supports_project_inspection=True,
        supports_resume_candidates=True,
        supports_quality_profiles=True,
        supports_backend_self_test=True,
        supports_backend_job_runner=True,
        supports_ui_session_state=True,
        supports_ui_parameter_schema=True,
        supports_runtime_preflight=True,
        supports_ui_status_report=True,
        supports_ui_contract_freeze=True,
        supports_pyside6_ui_skeleton=True,
        supports_pyside6_ui_schema_session_form=True,
        supports_pyside6_job_progress_polish=True,
        supports_pyside6_resume_recent_ui=True,
        supports_pyside6_reports_review_ui=True,
        supports_windows_packaging=True,
        supports_ui_polish=True,
        supports_release_check=True,
        supports_ui_usability_pass=True,
        supports_ui_localization_help_pass=True,
        supports_windows_onefolder_build_profiles=True,
        supports_windows_no_console_gui_launcher=True,
        supports_cli_diagnostics_launcher=True,
        supports_result_health_check=True,
        supports_soft_cancel_request=True,
        supports_hard_cancel=False,
        notes=(
            "Build RunConfig in the UI and call backend.run(config, callbacks).",
            "Do not call cli_wizard or parse CLI arguments from UI code.",
            "Use run_backend_self_test() before enabling UI start buttons when needed.",
            "Use create_backend_job() for threaded UI runs and structured progress snapshots.",
            "Use UiSessionState helpers to persist UI preferences and recent projects separately from project.json.",
            "Use get_ui_run_config_schema() to build Windows UI forms without importing the console wizard.",
            "Use runtime_preflight() to show startup/runtime/GPU readiness before running the backend.",
            "Use UI status reports to display validation/preflight/self-test/job issues without parsing CLI text.",
            "Use ui_contract_freeze_snapshot() and verify_ui_contract() before building UI-specific integrations on top of the backend API.",
            "v60 / Этап 019 added reproducible Windows packaging scripts, PyInstaller specs and packaging smoke-tests.",
            "v62 / Этап 021 added release-candidate stabilization: release_check, changelog, session compatibility checks and richer GUI bug-report diagnostics.",
            "Stabilization is additive: project.json, resume, reports, bug-report formats, ML algorithms and pipeline stage logic stay unchanged.",
            "Use run_release_check() or tools/release_check.py before Windows exe packaging/regression passes.",
            "v69.6 / Этап 055 adds first public polish / release identity pass on top of the stable release freeze; ML, pipeline and report CSV schemas stay unchanged.",
            "Cancellation is soft in Этап 055: request_cancel() records intent but does not interrupt processing yet.",
        ),
    )


def _legacy_core() -> Any:
    """Load the legacy implementation lazily for profile defaults and validators."""
    try:
        from .. import face_sorter_mvp as legacy
    except ImportError:  # script-folder mode
        import face_sorter_mvp as legacy  # type: ignore
    return legacy


def normalize_path(value: Optional[str | Path]) -> Optional[Path]:
    """Return a normalized Path or None for empty UI fields."""
    if value in (None, ""):
        return None
    return Path(value).expanduser()


def suggest_output_dir(input_dir: str | Path, *, now: Optional[dt.datetime] = None) -> Path:
    """Suggest the same timestamped result folder style used by the CLI wizard."""
    base = Path(input_dir).expanduser().resolve().parent
    timestamp = (now or dt.datetime.now()).strftime("%H-%M %d.%m.%Y")
    candidate = base / f"result {timestamp}"
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        numbered = base / f"result {timestamp}_{index}"
        if not numbered.exists():
            return numbered
        index += 1


def get_quality_profiles() -> Dict[str, QualityProfileInfo]:
    """Return UI-friendly quality profile metadata."""
    profiles = getattr(_legacy_core(), "QUALITY_PROFILES", {})
    result: Dict[str, QualityProfileInfo] = {}
    for key, payload in profiles.items():
        result[str(key)] = QualityProfileInfo(
            key=str(key),
            title=str(payload.get("title", key)),
            short=str(payload.get("short", "")),
            effect=str(payload.get("effect", "")),
            warning=str(payload.get("warning", "")),
            settings=copy.deepcopy(payload.get("settings", {})),
        )
    return result


def get_quality_profile_dicts() -> Dict[str, Dict[str, Any]]:
    """Return quality profiles as plain dictionaries for JSON/UI bridges."""
    return {key: item.to_dict() for key, item in get_quality_profiles().items()}


def create_run_config(
    *,
    input_dir: str | Path,
    output_dir: Optional[str | Path] = None,
    profile: str = "normal",
    mode: str = "all",
    language: str = "auto",
    use_gpu: bool = False,
    auto_cpu_fallback: bool = True,
    resume_existing_output: bool = False,
    make_bug_report: bool = False,
    overrides: Optional[Dict[str, Any]] = None,
) -> RunConfig:
    """Build a RunConfig from UI form values without using argparse directly."""
    input_path = Path(input_dir).expanduser()
    output_path = Path(output_dir).expanduser() if output_dir not in (None, "") else suggest_output_dir(input_path)
    extra = dict(overrides or {})
    extra.update(
        {
            "mode": mode,
            "lang": language,
            "gpu": use_gpu,
            "auto_cpu_fallback": auto_cpu_fallback,
            "resume_existing_output": resume_existing_output,
            "make_bug_report": make_bug_report,
        }
    )
    return _legacy_core().run_config_from_profile(profile, input_path, output_path, **extra)


def validate_config_for_ui(config: RunConfig) -> ApiValidationResult:
    """Validate config and return errors/warnings without filesystem mutation.

    The legacy validator creates the output directory as a side effect.  A GUI
    form validator should not do that, so this function mirrors the stable
    checks needed before run() and leaves directory creation to the pipeline.
    """
    errors: List[str] = []
    warnings: List[str] = []

    if config.mode not in MODE_STAGE_MAP and config.mode not in {"install-hint", "diagnose-gpu"}:
        errors.append(f"Unsupported mode: {config.mode}")

    needs_input = config.mode in {"scan", "cluster", "assign", "copy", "report", "all"}
    if needs_input and not config.input_dir:
        errors.append("Input folder is required for this mode.")
    if config.input_dir and (not Path(config.input_dir).exists() or not Path(config.input_dir).is_dir()):
        errors.append(f"Input folder does not exist: {config.input_dir}")

    if not config.output_dir and config.mode not in {"install-hint", "diagnose-gpu"}:
        errors.append("Output/project folder is required.")
    if config.output_dir and Path(config.output_dir).exists() and not config.resume_existing_output:
        warnings.append(f"Output folder already exists: {config.output_dir}")

    try:
        stages_for_mode(config.mode)
    except Exception as exc:
        if config.mode not in {"install-hint", "diagnose-gpu"}:
            errors.append(str(exc) or repr(exc))

    return ApiValidationResult(ok=not errors, errors=tuple(dict.fromkeys(errors)), warnings=tuple(dict.fromkeys(warnings)))


def inspect_project(project_dir: str | Path) -> ProjectSummary:
    """Inspect an output/result folder and return a stable summary for UI lists."""
    path = Path(project_dir).expanduser()
    state = read_run_state(path)
    exists = path.exists()
    status = str(state.get("status") or "unknown")
    stage = str(state.get("stage") or "unknown")
    last_successful = str(state.get("last_successful_stage") or "")
    db_path = default_project_db_path(path) if exists else None
    has_database = bool(db_path and db_path.exists())
    can_resume = status.lower() in {"", "running", "error", "interrupted"} and exists
    resume_mode = resume_mode_from_state(state) if state else "all"
    stages_completed_raw = state.get("stages_completed") if isinstance(state.get("stages_completed"), list) else []
    display = describe_run_state_for_user(path, state) if state else f"{path.name} | no project.json"
    return ProjectSummary(
        path=path,
        exists=exists,
        has_project_json=project_json_path(path).exists(),
        has_legacy_state=bool(read_legacy_run_state(path)),
        status=status,
        stage=stage,
        last_successful_stage=last_successful,
        started_at=str(state.get("started_at") or ""),
        updated_at=str(state.get("updated_at") or ""),
        finished_at=str(state.get("finished_at") or ""),
        input_dir=str(state.get("input_dir") or state.get("input") or ""),
        output_dir=str(state.get("output_dir") or state.get("output") or path),
        profile=str(state.get("profile") or ""),
        mode=str(state.get("mode") or ""),
        model=str(state.get("model") or ""),
        use_gpu=bool(state.get("use_gpu", state.get("gpu", False))),
        files_total=state.get("files_total"),
        files_scanned=int(state.get("files_scanned") or 0),
        copy_total=state.get("copy_total"),
        files_copied=int(state.get("files_copied") or 0),
        stages_completed=tuple(str(item) for item in stages_completed_raw),
        error=str(state.get("error") or ""),
        db_path=db_path,
        has_database=has_database,
        can_resume=can_resume,
        resume_mode=resume_mode,
        display_text=display,
    )


def find_resume_projects(input_dir: str | Path) -> List[ProjectSummary]:
    """Find unfinished result folders for the given input folder."""
    return [inspect_project(path) for path, _state in find_unfinished_result_dirs(Path(input_dir).expanduser())]


def prepare_project_folder(project_dir: str | Path) -> ProjectSummary:
    """Create the standard project folder structure and return its summary."""
    path = Path(project_dir).expanduser()
    ensure_project_structure(path)
    return inspect_project(path)


def pipeline_modes() -> Tuple[str, ...]:
    """Return supported public pipeline modes."""
    return tuple(MODE_STAGE_MAP.keys())


def pipeline_stages() -> Tuple[str, ...]:
    """Return supported pipeline stage names."""
    return tuple(PIPELINE_STAGES)


def mode_stages(mode: str) -> Tuple[str, ...]:
    """Return stages for one UI-selected mode."""
    return stages_for_mode(mode)


__all__ = [
    "ApiValidationResult",
    "QualityProfileInfo",
    "ProjectSummary",
    "CallbackEvent",
    "RecordingProgressCallbacks",
    "UiBackendApi",
    "ui_backend_api",
    "normalize_path",
    "suggest_output_dir",
    "get_quality_profiles",
    "get_quality_profile_dicts",
    "create_run_config",
    "validate_config_for_ui",
    "inspect_project",
    "find_resume_projects",
    "prepare_project_folder",
    "pipeline_modes",
    "pipeline_stages",
    "mode_stages",
    "UI_SESSION_SCHEMA_VERSION",
    "UiRecentProject",
    "UiSessionState",
    "default_ui_state_path",
    "default_ui_session_state",
    "ui_session_state_from_dict",
    "load_ui_session_state",
    "save_ui_session_state",
    "update_ui_session_state",
    "remember_recent_project",
    "prune_recent_projects",
    "config_to_ui_session_state",
    "ui_session_to_run_config",
]
