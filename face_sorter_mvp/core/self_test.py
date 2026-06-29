# -*- coding: utf-8 -*-
"""Import-safe backend/UI contract self-test helpers.

v62 / Этап 021 keeps this module for future Windows/PySide6 integration.
The checks here are intentionally lightweight: they validate the public backend
contract, project-inspection helpers, callbacks and configuration builders
without running InsightFace, ONNX Runtime, clustering, scan or copy stages.
It also verifies the v62 / Этап 021 UI session-state JSON contract.
"""
from __future__ import annotations

import datetime as dt
import tempfile
import time
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .api import (
    RecordingProgressCallbacks,
    create_run_config,
    find_resume_projects,
    get_quality_profiles,
    inspect_project,
    mode_stages,
    pipeline_modes,
    pipeline_stages,
    prepare_project_folder,
    suggest_output_dir,
    ui_backend_api,
    validate_config_for_ui,
)
from .session import (
    config_to_ui_session_state,
    default_ui_session_state,
    load_ui_session_state,
    remember_recent_project,
    save_ui_session_state,
    ui_session_to_run_config,
)
from .config import RunConfig, RunResult
from .job import create_backend_job
from .preflight import runtime_preflight, runtime_preflight_summary
from .ui_schema import (
    UI_SCHEMA_VERSION,
    get_ui_run_config_schema,
    profile_settings_diff,
    validate_ui_values_against_schema,
)
from .review_ui import (
    REVIEW_UI_SCHEMA_VERSION,
    load_problem_files_summary,
    load_review_ui_snapshot,
    save_review_ui_decisions,
)
from .status import (
    UI_STATUS_SCHEMA_VERSION,
    UiIssue,
    status_from_validation_result,
    status_from_preflight_result,
    status_from_job_snapshot,
    summarize_status_report,
    ui_issue,
    ui_status_report,
)
from .constants import MODE_STAGE_MAP, PIPELINE_STAGES, PROJECT_FILENAME, SCRIPT_VERSION
from .project_state import write_run_state
from .windows_packaging import (
    WINDOWS_PACKAGING_SCHEMA_VERSION,
    windows_packaging_plan,
    verify_windows_packaging,
)
from .ui_polish import (
    UI_POLISH_SCHEMA_VERSION,
    UI_THEME_CHOICES,
    UI_DENSITY_CHOICES,
    UI_LANGUAGE_CHOICES,
    UI_ICON_RELATIVE_PATH,
    ui_polish_snapshot,
    ui_polish_settings_from_session,
    apply_ui_polish_settings_to_session,
    get_ui_instruction_sections,
    ui_text,
)
from .ui_usability import (
    UI_USABILITY_SCHEMA_VERSION,
    UI_USABILITY_STAGE,
    build_paths_summary,
    build_run_summary,
    build_beginner_action_map_text,
    classify_path_state,
    get_ui_usability_hints,
    ui_usability_snapshot,
)
from .frozen_runtime import (
    FROZEN_RUNTIME_SCHEMA_VERSION,
    is_frozen_app,
    frozen_runtime_info,
    frozen_runtime_summary,
)
from .contract import (
    UI_CONTRACT_API_VERSION,
    UI_CONTRACT_SCHEMA_VERSION,
    ui_contract_freeze_snapshot,
    verify_ui_contract,
)


@dataclass(frozen=True)
class BackendSelfTestCheck:
    """One lightweight backend/API self-test check."""

    name: str
    ok: bool
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BackendSelfTestResult:
    """Serializable result of the import-safe backend self-test."""

    ok: bool
    version: str
    refactor_stage: str
    ui_api_version: int
    created_at: str
    duration_ms: int
    checks: Tuple[BackendSelfTestCheck, ...]
    errors: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["checks"] = [check.to_dict() for check in self.checks]
        return data


def ui_contract_snapshot() -> Dict[str, Any]:
    """Return a small JSON-friendly snapshot of the UI/backend contract."""
    api = ui_backend_api()
    return {
        "version": SCRIPT_VERSION,
        "refactor_stage": api.refactor_stage,
        "ui_api_version": api.api_version,
        "project_filename": PROJECT_FILENAME,
        "pipeline_modes": list(pipeline_modes()),
        "pipeline_stages": list(pipeline_stages()),
        "quality_profiles": sorted(get_quality_profiles().keys()),
        "supports_backend_self_test": True,
        "supports_backend_job_runner": api.supports_backend_job_runner,
        "supports_ui_session_state": api.supports_ui_session_state,
        "supports_runtime_preflight": api.supports_runtime_preflight,
        "supports_ui_status_report": api.supports_ui_status_report,
        "supports_ui_contract_freeze": api.supports_ui_contract_freeze,
        "supports_pyside6_ui_skeleton": getattr(api, "supports_pyside6_ui_skeleton", False),
        "supports_pyside6_ui_schema_session_form": getattr(api, "supports_pyside6_ui_schema_session_form", False),
        "supports_pyside6_job_progress_polish": getattr(api, "supports_pyside6_job_progress_polish", False),
        "supports_pyside6_resume_recent_ui": getattr(api, "supports_pyside6_resume_recent_ui", False),
        "supports_pyside6_reports_review_ui": getattr(api, "supports_pyside6_reports_review_ui", False),
        "supports_windows_packaging": getattr(api, "supports_windows_packaging", False),
        "supports_ui_polish": getattr(api, "supports_ui_polish", False),
        "supports_release_check": getattr(api, "supports_release_check", False),
        "supports_ui_usability_pass": getattr(api, "supports_ui_usability_pass", False),
        "supports_ui_localization_help_pass": getattr(api, "supports_ui_localization_help_pass", False),
        "supports_windows_onefolder_build_profiles": getattr(api, "supports_windows_onefolder_build_profiles", False),
        "supports_soft_cancel_request": api.supports_soft_cancel_request,
        "supports_hard_cancel": api.supports_hard_cancel,
        "recommended_entrypoint": api.recommended_entrypoint,
    }


def _ok(name: str, message: str = "", **details: Any) -> BackendSelfTestCheck:
    return BackendSelfTestCheck(name=name, ok=True, message=message, details=dict(details))


def _fail(name: str, exc: BaseException | str, **details: Any) -> BackendSelfTestCheck:
    message = str(exc) if not isinstance(exc, BaseException) else f"{type(exc).__name__}: {exc}"
    return BackendSelfTestCheck(name=name, ok=False, message=message, details=dict(details))


def run_backend_self_test() -> BackendSelfTestResult:
    """Run import-safe backend/UI contract checks without ML processing.

    This function is suitable for a future GUI startup diagnostics screen.  It
    may create a temporary directory during the check, but it does not touch the
    user's photo folders and does not import or initialize heavy ML runtimes.
    """
    started = time.perf_counter()
    checks: List[BackendSelfTestCheck] = []

    api = ui_backend_api()

    try:
        snapshot = ui_contract_snapshot()
        checks.append(_ok("ui_contract_snapshot", "UI contract snapshot created.", snapshot=snapshot))
    except Exception as exc:  # pragma: no cover - defensive for field diagnostics
        checks.append(_fail("ui_contract_snapshot", exc))

    try:
        freeze_snapshot = ui_contract_freeze_snapshot()
        contract_check = verify_ui_contract()
        if freeze_snapshot.schema_version != UI_CONTRACT_SCHEMA_VERSION:
            raise AssertionError("UI contract schema version mismatch")
        if freeze_snapshot.ui_api_version != UI_CONTRACT_API_VERSION:
            raise AssertionError("UI contract API version mismatch")
        if not contract_check.ok:
            raise AssertionError(f"UI contract verification failed: {contract_check.to_dict()}")
        checks.append(_ok(
            "ui_contract_freeze",
            "Frozen backend/UI public API contract is present and verified.",
            snapshot=freeze_snapshot.to_dict(),
            verification=contract_check.to_dict(),
        ))
    except Exception as exc:
        checks.append(_fail("ui_contract_freeze", exc))

    try:
        try:
            from ..ui import UI_SKELETON_VERSION, is_pyside6_available, launch_ui
        except ImportError:
            from ui import UI_SKELETON_VERSION, is_pyside6_available, launch_ui  # type: ignore
        if UI_SKELETON_VERSION <= 0:
            raise AssertionError("invalid UI skeleton version")
        if not callable(launch_ui):
            raise AssertionError("launch_ui is not callable")
        checks.append(_ok(
            "pyside6_ui_skeleton",
            "Optional PySide6 UI imports without requiring PySide6 and exposes schema/session forms plus resume/recent-project controls.",
            ui_skeleton_version=UI_SKELETON_VERSION,
            pyside6_available=bool(is_pyside6_available()),
            launch_entrypoint="python -m face_sorter_mvp.ui",
        ))
    except Exception as exc:
        checks.append(_fail("pyside6_ui_skeleton", exc))

    try:
        modes = pipeline_modes()
        stages = pipeline_stages()
        if tuple(stages) != tuple(PIPELINE_STAGES):
            raise AssertionError("pipeline_stages() does not match PIPELINE_STAGES")
        for mode in modes:
            expected = tuple(MODE_STAGE_MAP[mode])
            actual = tuple(mode_stages(mode))
            if actual != expected:
                raise AssertionError(f"mode {mode!r}: {actual!r} != {expected!r}")
        checks.append(_ok("pipeline_modes_and_stages", "Pipeline modes map to stable stage lists.", modes=list(modes), stages=list(stages)))
    except Exception as exc:
        checks.append(_fail("pipeline_modes_and_stages", exc))

    try:
        profiles = get_quality_profiles()
        required = {"minimum", "normal", "high", "maximum", "recognition_max"}
        missing = sorted(required.difference(profiles.keys()))
        if missing:
            raise AssertionError(f"missing quality profiles: {missing}")
        checks.append(_ok("quality_profiles", "Quality profiles are available for UI controls.", profiles=sorted(profiles.keys())))
    except Exception as exc:
        checks.append(_fail("quality_profiles", exc))

    try:
        schema = get_ui_run_config_schema(profile="normal")
        parameter_map = schema.parameter_map()
        required_fields = {"input_dir", "output_dir", "profile", "mode", "model", "det_size", "min_det_score"}
        missing = sorted(required_fields.difference(parameter_map.keys()))
        if missing:
            raise AssertionError(f"missing UI schema fields: {missing}")
        if schema.schema_version != UI_SCHEMA_VERSION or schema.ui_api_version != ui_backend_api().api_version:
            raise AssertionError("UI schema version does not match public API metadata")
        errors = validate_ui_values_against_schema({
            "input_dir": "C:/photos",
            "profile": "normal",
            "mode": "all",
            "model": "buffalo_l",
            "det_size": 640,
            "min_det_score": 0.3,
            "min_face_size": 12,
        })
        if errors:
            raise AssertionError(f"UI schema validation returned unexpected errors: {errors}")
        diff = profile_settings_diff("high")
        if not diff:
            raise AssertionError("profile_settings_diff('high') returned an empty diff")
        checks.append(_ok(
            "ui_parameter_schema",
            "UI form schema exposes sections, fields, defaults and profile diffs without ML.",
            schema_version=schema.schema_version,
            ui_api_version=schema.ui_api_version,
            sections=[section.key for section in schema.sections],
            parameters=sorted(parameter_map.keys()),
            high_profile_changed_fields=sorted(diff.keys()),
        ))
    except Exception as exc:
        checks.append(_fail("ui_parameter_schema", exc))


    try:
        preflight = runtime_preflight(include_optional=True, include_gpu=True, import_check=False, run_gpu_smoke_test=False)
        summary = runtime_preflight_summary(include_optional=False, include_gpu=True, import_check=False, run_gpu_smoke_test=False)
        if preflight.schema_version <= 0:
            raise AssertionError("invalid runtime preflight schema version")
        if not preflight.python_executable:
            raise AssertionError("runtime preflight did not report python executable")
        checks.append(_ok(
            "runtime_preflight",
            "Runtime/environment preflight reports Python, package and ONNX/GPU readiness without ML.",
            schema_version=preflight.schema_version,
            python_executable=preflight.python_executable,
            missing_required=list(preflight.missing_required),
            onnx_providers=list(preflight.gpu.onnx_providers),
            cuda_provider_available=preflight.gpu.cuda_provider_available,
            summary=summary,
        ))
    except Exception as exc:
        checks.append(_fail("runtime_preflight", exc))


    try:
        from . import preflight as preflight_module

        original_distribution_version = preflight_module._distribution_version

        def fake_distribution_version(name: str):
            if name == "nvidia-cuda-runtime-cu12":
                return True, "0.test", "<self-test>"
            return original_distribution_version(name)

        preflight_module._distribution_version = fake_distribution_version
        try:
            native_status = preflight_module.package_status("nvidia-cuda-runtime-cu12", import_check=True)
        finally:
            preflight_module._distribution_version = original_distribution_version
        if not native_status.installed or native_status.version != "0.test":
            raise AssertionError(f"native wheel metadata check failed: {native_status.to_dict()}")
        if native_status.import_ok is False:
            raise AssertionError(f"native wheel was incorrectly treated as an import failure: {native_status.to_dict()}")
        checks.append(_ok(
            "native_cuda_wheel_metadata",
            "nvidia-*-cu12 native-library wheels are metadata-checked and not treated as Python import failures.",
            status=native_status.to_dict(),
        ))
    except Exception as exc:
        checks.append(_fail("native_cuda_wheel_metadata", exc))

    try:
        validation = validate_config_for_ui(create_run_config(input_dir="C:/photos", output_dir="C:/result", profile="normal", use_gpu=False))
        validation_status = status_from_validation_result(validation)
        manual_status = ui_status_report((ui_issue("selftest_info", "info", "self_test", "Self-test info", "Status layer works."),), summary="Manual status OK")
        preflight_for_status = runtime_preflight(include_optional=False, include_gpu=False, import_check=False, run_gpu_smoke_test=False)
        preflight_status = status_from_preflight_result(preflight_for_status)
        status_summary = summarize_status_report(manual_status)
        if UI_STATUS_SCHEMA_VERSION <= 0:
            raise AssertionError("invalid UI status schema version")
        if not isinstance(manual_status.issues[0], UiIssue):
            raise AssertionError("ui_status_report did not preserve UiIssue")
        if status_summary.infos != 1:
            raise AssertionError("unexpected UI status summary counts")
        checks.append(_ok(
            "ui_status_report",
            "UI status/error report helpers convert validation/preflight/job diagnostics without parsing CLI text.",
            schema_version=UI_STATUS_SCHEMA_VERSION,
            validation_status=validation_status.to_dict(),
            preflight_status=preflight_status.to_dict(),
            manual_status=manual_status.to_dict(),
            summary=status_summary.to_dict(),
        ))
    except Exception as exc:
        checks.append(_fail("ui_status_report", exc))

    try:
        callbacks = RecordingProgressCallbacks()
        callbacks.on_stage("scan", "started")
        callbacks.on_progress("scan", 1, 2)
        drained = callbacks.drain_events()
        if len(drained) != 2 or callbacks.events:
            raise AssertionError("RecordingProgressCallbacks did not capture/drain events correctly")
        checks.append(_ok("recording_callbacks", "Progress callback recorder captures and drains events.", events=[event.to_dict() for event in drained]))
    except Exception as exc:
        checks.append(_fail("recording_callbacks", exc))

    try:
        with tempfile.TemporaryDirectory(prefix="face_sorter_backend_selftest_") as tmp:
            tmp_path = Path(tmp)
            input_dir = tmp_path / "input"
            input_dir.mkdir()
            output_dir = suggest_output_dir(input_dir, now=dt.datetime(2026, 1, 2, 3, 4, 5))
            config = create_run_config(input_dir=input_dir, output_dir=output_dir, profile="normal", use_gpu=False)
            if not isinstance(config, RunConfig):
                raise AssertionError("create_run_config() did not return RunConfig")
            validation = validate_config_for_ui(config)
            if not validation.ok:
                raise AssertionError(f"validate_config_for_ui() returned errors: {validation.errors}")
            checks.append(_ok(
                "create_and_validate_run_config",
                "RunConfig can be built and validated for UI without running the pipeline.",
                input_dir=str(input_dir),
                output_dir=str(output_dir),
                profile=config.profile,
                mode=config.mode,
            ))
    except Exception as exc:
        checks.append(_fail("create_and_validate_run_config", exc))



    try:
        with tempfile.TemporaryDirectory(prefix="face_sorter_job_selftest_") as tmp:
            tmp_path = Path(tmp)
            input_dir = tmp_path / "input"
            input_dir.mkdir()
            output_dir = tmp_path / "output"
            config = create_run_config(input_dir=input_dir, output_dir=output_dir, profile="normal", use_gpu=False)

            def fake_runner(fake_config: RunConfig, fake_callbacks: Any) -> RunResult:
                fake_callbacks.on_stage("fake", "Fake backend job started.")
                fake_callbacks.on_progress("fake", 1, 2)
                fake_callbacks.on_progress("fake", 2, 2)
                return RunResult(output_dir=fake_config.output_dir, db_path=None, status="done", stages_completed=("fake",))

            job = create_backend_job(config, runner=fake_runner)
            before = job.snapshot()
            if before.state != "pending":
                raise AssertionError(f"unexpected initial job state: {before.state}")
            final_snapshot = job.run_sync()
            events = job.drain_events()
            if final_snapshot.state != "done" or final_snapshot.result_status != "done":
                raise AssertionError(f"unexpected final job snapshot: {final_snapshot.to_dict()}")
            if not any(event.kind == "progress" for event in events):
                raise AssertionError("backend job did not capture progress events")
            job_status = status_from_job_snapshot(final_snapshot, events)
            if not job_status.ok:
                raise AssertionError(f"status_from_job_snapshot() unexpectedly reported issues: {job_status.to_dict()}")
            checks.append(_ok(
                "backend_job_runner",
                "BackendJob captures progress and final result using a fake runner without ML.",
                before=before.to_dict(),
                after=final_snapshot.to_dict(),
                events=[event.to_dict() for event in events],
                job_status=job_status.to_dict(),
            ))
    except Exception as exc:
        checks.append(_fail("backend_job_runner", exc))

    try:
        with tempfile.TemporaryDirectory(prefix="face_sorter_session_selftest_") as tmp:
            tmp_path = Path(tmp)
            input_dir = tmp_path / "input"
            input_dir.mkdir()
            output_dir = tmp_path / "output"
            config = create_run_config(input_dir=input_dir, output_dir=output_dir, profile="normal", use_gpu=False)
            state = config_to_ui_session_state(config, default_ui_session_state(language="ru"))
            state = remember_recent_project(
                state,
                output_dir,
                input_dir=str(input_dir),
                output_dir=str(output_dir),
                status="done",
                display_text="Self-test project",
            )
            session_path = tmp_path / "ui_session.json"
            written = save_ui_session_state(state, session_path)
            loaded = load_ui_session_state(written)
            rebuilt = ui_session_to_run_config(loaded)
            if loaded.selected_profile != config.profile or loaded.selected_mode != config.mode:
                raise AssertionError("UI session state did not preserve selected profile/mode")
            if not loaded.recent_projects or loaded.recent_projects[0].path != output_dir:
                raise AssertionError("UI session state did not preserve recent projects")
            if rebuilt.input_dir != input_dir or rebuilt.output_dir != output_dir:
                raise AssertionError("ui_session_to_run_config() did not rebuild expected paths")
            checks.append(_ok(
                "ui_session_state",
                "UI session state saves, loads, remembers recent projects and rebuilds RunConfig without ML.",
                session_path=str(written),
                state=loaded.to_dict(),
                rebuilt_profile=rebuilt.profile,
                rebuilt_mode=rebuilt.mode,
            ))
    except Exception as exc:
        checks.append(_fail("ui_session_state", exc))


    try:
        with tempfile.TemporaryDirectory(prefix="face_sorter_project_selftest_") as tmp:
            project_dir = Path(tmp) / "result 03-04 02.01.2026"
            summary_before = inspect_project(project_dir)
            if summary_before.exists:
                raise AssertionError("inspect_project() reported a nonexistent project as existing")
            summary_after = prepare_project_folder(project_dir)
            if not summary_after.exists:
                raise AssertionError("prepare_project_folder() did not create an inspectable project folder")
            checks.append(_ok(
                "project_inspection",
                "Project folder preparation and inspection work for UI lists.",
                before=summary_before.to_dict(),
                after=summary_after.to_dict(),
            ))
    except Exception as exc:
        checks.append(_fail("project_inspection", exc))

    try:
        with tempfile.TemporaryDirectory(prefix="face_sorter_review_ui_selftest_") as tmp:
            output_dir = Path(tmp) / "result 03-04 02.01.2026"
            reports_dir = output_dir / "reports"
            reports_dir.mkdir(parents=True)
            review_clusters_path = reports_dir / "review_clusters.csv"
            review_clusters_path.write_text(
                "cluster_key,faces,files,confidence,avg_det_score,min_det_score,max_det_score\n"
                "person_001,10,8,0.9500,0.9500,0.9000,0.9900\n"
                "person_002,4,3,0.8700,0.8700,0.8000,0.9300\n",
                encoding="utf-8-sig",
            )
            problem_path = reports_dir / "problem_files.csv"
            problem_path.write_text(
                "time,stage,path,name,suffix,size_bytes,error\n"
                "2026-01-02T03:04:05,scan_timeout,/tmp/bad.jpg,bad.jpg,.jpg,12,worker timeout\n"
                "2026-01-02T03:04:06,unsupported_extension,/tmp/file.raw,file.raw,.raw,99,unsupported extension: .raw\n",
                encoding="utf-8-sig",
            )
            snapshot = load_review_ui_snapshot(output_dir)
            if REVIEW_UI_SCHEMA_VERSION <= 0:
                raise AssertionError("invalid review UI schema version")
            if len(snapshot.rows) != 2:
                raise AssertionError(f"unexpected review row count: {len(snapshot.rows)}")
            problem_summary = load_problem_files_summary(problem_path)
            if problem_summary.total_rows != 2 or problem_summary.category_counts.get("timeout") != 1:
                raise AssertionError(f"unexpected problem_files summary: {problem_summary.to_dict()}")
            if snapshot.problem_summary.total_rows != 2:
                raise AssertionError("review UI snapshot did not include problem_files summary")
            save_result = save_review_ui_decisions(output_dir, [
                {"cluster_key": "person_001", "faces": 10, "files": 8, "confidence": 0.95, "action": "keep", "name": "Alice", "merge_into": "", "notes": "self-test"},
                {"cluster_key": "person_002", "faces": 4, "files": 3, "confidence": 0.87, "action": "merge", "name": "", "merge_into": "person_001", "notes": "self-test merge"},
            ])
            if not save_result.names_path.exists() or not save_result.review_decisions_path.exists():
                raise AssertionError("review UI save did not create names/review_decisions files")
            snapshot_after = load_review_ui_snapshot(output_dir)
            row_by_key = {row.cluster_key: row for row in snapshot_after.rows}
            if row_by_key["person_001"].name != "Alice" or row_by_key["person_002"].action != "merge":
                raise AssertionError("review UI snapshot did not preserve saved decisions")
            checks.append(_ok(
                "reports_review_ui",
                "Reports/review UI helpers load review_clusters.csv, explain problem_files.csv, save names.csv and write review_decisions.csv without ML or format changes.",
                schema_version=REVIEW_UI_SCHEMA_VERSION,
                problem_summary=problem_summary.to_dict(),
                before=snapshot.to_dict(),
                save_result=save_result.to_dict(),
                after=snapshot_after.to_dict(),
            ))
    except Exception as exc:
        checks.append(_fail("reports_review_ui", exc))

    try:
        if WINDOWS_PACKAGING_SCHEMA_VERSION <= 0:
            raise AssertionError("invalid Windows packaging schema version")
        if is_frozen_app():
            checks.append(_ok(
                "windows_packaging",
                "Frozen executable runtime detected; source packaging scripts/specs are not required inside the portable bundle.",
                schema_version=WINDOWS_PACKAGING_SCHEMA_VERSION,
                frozen_runtime=frozen_runtime_summary(),
            ))
        else:
            plan = windows_packaging_plan()
            check = verify_windows_packaging()
            if not check.ok:
                raise AssertionError(f"Windows packaging verification failed: {check.to_dict()}")
            checks.append(_ok(
                "windows_packaging",
                "Windows packaging scripts/specs/requirements are present and import-safe to verify without running PyInstaller or ML.",
                schema_version=WINDOWS_PACKAGING_SCHEMA_VERSION,
                plan=plan.to_dict(),
                verification=check.to_dict(),
            ))
    except Exception as exc:
        checks.append(_fail("windows_packaging", exc))

    try:
        info = frozen_runtime_info()
        summary = frozen_runtime_summary()
        if info.schema_version != FROZEN_RUNTIME_SCHEMA_VERSION:
            raise AssertionError("Frozen runtime schema version mismatch")
        checks.append(_ok(
            "frozen_runtime",
            "Frozen/source runtime location helpers are import-safe.",
            info=info.to_dict(),
            summary=summary,
        ))
    except Exception as exc:
        checks.append(_fail("frozen_runtime", exc))


    try:
        with tempfile.TemporaryDirectory(prefix="face_sorter_polish_selftest_") as tmp:
            state = default_ui_session_state(language="ru")
            settings_type = ui_polish_settings_from_session(state).__class__
            updated = apply_ui_polish_settings_to_session(
                state,
                settings_type(
                    language="en",
                    theme="dark",
                    density="compact",
                    show_startup_tips=False,
                    confirm_before_run=True,
                    auto_open_reports_after_run=False,
                    show_advanced_fields=True,
                    verbose_progress_events=True,
                    auto_scroll_logs=False,
                ),
            )
            roundtrip_path = Path(tmp) / "ui_session.json"
            save_ui_session_state(updated, roundtrip_path)
            loaded = load_ui_session_state(roundtrip_path)
            loaded_settings = ui_polish_settings_from_session(loaded)
            snapshot = ui_polish_snapshot(language=loaded.language)
            if snapshot.schema_version != UI_POLISH_SCHEMA_VERSION:
                raise AssertionError("UI polish schema version mismatch")
            if loaded_settings.language != "en" or loaded_settings.theme != "dark" or loaded_settings.density != "compact":
                raise AssertionError(f"UI polish settings did not round-trip: {loaded_settings.to_dict()}")
            expected_icon_parts = Path(UI_ICON_RELATIVE_PATH).parts
            actual_icon_parts = snapshot.icon_path.parts[-len(expected_icon_parts):]
            if not snapshot.icon_path.name.endswith(".ico") or tuple(actual_icon_parts) != tuple(expected_icon_parts):
                raise AssertionError("UI polish icon path is not stable")
            if not UI_THEME_CHOICES or not UI_DENSITY_CHOICES or not UI_LANGUAGE_CHOICES:
                raise AssertionError("UI polish choices are empty")
            instructions = get_ui_instruction_sections("en")
            if not instructions or not instructions[0].steps:
                raise AssertionError("UI polish instructions are empty")
            sample_keys = (
                "start",
                "tooltip_start",
                "readiness_ok",
                "problem_files_help",
                "reports_apply_details",
                "close_running_job",
            )
            en_text = "\n".join(ui_text(key, "en") for key in sample_keys)
            ru_text = "\n".join(ui_text(key, "ru") for key in sample_keys)
            if re.search(r"[А-Яа-яЁё]", en_text):
                raise AssertionError(f"English UI polish text contains Cyrillic: {en_text}")
            if not re.search(r"[А-Яа-яЁё]", ru_text):
                raise AssertionError("Russian UI polish text does not contain Cyrillic")
            schema_en = get_ui_run_config_schema(language="en")
            schema_ru = get_ui_run_config_schema(language="ru")
            schema_en_text = "\n".join(
                [section.title + " " + section.description for section in schema_en.sections]
                + [param.label + " " + param.description for param in schema_en.parameters]
                + [option.label + " " + option.description + " " + option.warning for param in schema_en.parameters for option in param.options]
            )
            schema_ru_text = "\n".join(
                [section.title + " " + section.description for section in schema_ru.sections]
                + [param.label + " " + param.description for param in schema_ru.parameters]
                + [option.label + " " + option.description + " " + option.warning for param in schema_ru.parameters for option in param.options]
            )
            if re.search(r"[А-Яа-яЁё]", schema_en_text):
                raise AssertionError("English UI schema contains Cyrillic text")
            if not re.search(r"[А-Яа-яЁё]", schema_ru_text):
                raise AssertionError("Russian UI schema does not contain Cyrillic text")
            checks.append(_ok(
                "ui_polish",
                "UI polish settings, icon metadata and localized instructions round-trip without Qt/ML.",
                settings=loaded_settings.to_dict(),
                snapshot=snapshot.to_dict(),
                instruction_sections=[section.to_dict() for section in instructions],
            ))
            checks.append(_ok(
                "ui_localization_coverage",
                "RU/EN UI text and UI schema samples are localized without leaking Cyrillic into English mode.",
                checked_keys=sample_keys,
                schema_en_sections=[section.to_dict() for section in schema_en.sections],
                schema_ru_sections=[section.to_dict() for section in schema_ru.sections],
            ))
    except Exception as exc:
        checks.append(_fail("ui_polish", exc))


    try:
        snapshot = ui_usability_snapshot("ru")
        if snapshot.schema_version != UI_USABILITY_SCHEMA_VERSION or snapshot.stage != UI_USABILITY_STAGE:
            raise AssertionError("UI usability snapshot schema/stage mismatch")
        if not snapshot.features or not get_ui_usability_hints("en"):
            raise AssertionError("UI usability hints/features are empty")
        if classify_path_state("", required=True) != "missing":
            raise AssertionError("required empty path classification failed")
        summary = build_run_summary({"input_dir": "input", "output_dir": "output", "profile": "normal", "mode": "all", "use_gpu": True})
        paths = build_paths_summary({"input_dir": "input", "output_dir": "output"}, bug_report_path="bug.zip")
        beginner = build_beginner_action_map_text({"input_dir": "input", "output_dir": "output", "use_gpu": True}, language="en")
        if "input" not in summary or "bug.zip" not in paths or "Beginner action map" not in beginner:
            raise AssertionError("UI usability summary helpers returned unexpected text")
        checks.append(_ok(
            "ui_usability",
            "UI usability helpers provide readiness/path summaries and copyable hints without Qt/ML.",
            snapshot=snapshot.to_dict(),
            run_summary=summary,
            paths_summary=paths,
            beginner_action_map=beginner,
        ))
    except Exception as exc:
        checks.append(_fail("ui_usability", exc))


    try:
        with tempfile.TemporaryDirectory(prefix="face_sorter_resume_selftest_") as tmp:
            tmp_path = Path(tmp)
            input_dir = tmp_path / "input"
            input_dir.mkdir()
            project_dir = tmp_path / "result 03-04 02.01.2026"
            config = create_run_config(input_dir=input_dir, output_dir=project_dir, profile="normal", use_gpu=False)
            write_run_state(project_dir, status="error", config=config, stage="scan", last_successful_stage="scan")
            candidates = find_resume_projects(input_dir)
            if not candidates:
                raise AssertionError("find_resume_projects() did not find unfinished project")
            first = candidates[0]
            if first.path != project_dir or first.resume_mode != "cluster":
                raise AssertionError(f"unexpected resume candidate: {first.to_dict()}")
            checks.append(_ok(
                "resume_recent_projects",
                "Resume candidate discovery works for the PySide6 Resume / recent tab without changing project.json format.",
                candidates=[candidate.to_dict() for candidate in candidates],
            ))
    except Exception as exc:
        checks.append(_fail("resume_recent_projects", exc))


    try:
        from .. import face_sorter_mvp as legacy

        old_stdout = getattr(sys, "stdout", None)
        old_stderr = getattr(sys, "stderr", None)
        try:
            sys.stdout = None  # type: ignore[assignment]
            sys.stderr = None  # type: ignore[assignment]
            legacy.ensure_non_null_stdio()
            if getattr(sys, "stdout", None) is None or getattr(sys, "stderr", None) is None:
                raise AssertionError("ensure_non_null_stdio() left stdout/stderr as None")
            written = sys.stderr.write("windowed stdio self-test")
            if written <= 0:
                raise AssertionError("NullTextStream.write() returned an invalid length")
            sys.stderr.flush()
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
        checks.append(_ok(
            "windowed_stdio_safeguard",
            "Windowed PyInstaller GUI processes with sys.stdout/sys.stderr=None get safe text sinks, preventing CPU inline scan/tqdm crashes without reopening a console.",
        ))
    except Exception as exc:
        checks.append(_fail("windowed_stdio_safeguard", exc))


    try:
        from .release import RELEASE_CHECK_SCHEMA_VERSION, run_release_check

        release = run_release_check(include_self_test=False)
        if RELEASE_CHECK_SCHEMA_VERSION <= 0:
            raise AssertionError("invalid release check schema version")
        if not release.ok:
            raise AssertionError(f"release check failed: {release.to_dict()}")
        checks.append(_ok(
            "release_check",
            "Release-candidate check layer is import-safe and verifies contract/preflight/packaging/docs/session without recursive self-test.",
            schema_version=RELEASE_CHECK_SCHEMA_VERSION,
            result=release.to_dict(),
        ))
    except Exception as exc:
        checks.append(_fail("release_check", exc))

    errors = tuple(check.message for check in checks if not check.ok)
    duration_ms = int((time.perf_counter() - started) * 1000)
    return BackendSelfTestResult(
        ok=not errors,
        version=SCRIPT_VERSION,
        refactor_stage=api.refactor_stage,
        ui_api_version=api.api_version,
        created_at=dt.datetime.now().isoformat(timespec="seconds"),
        duration_ms=duration_ms,
        checks=tuple(checks),
        errors=errors,
        warnings=(),
    )


__all__ = [
    "BackendSelfTestCheck",
    "BackendSelfTestResult",
    "ui_contract_snapshot",
    "run_backend_self_test",
]
