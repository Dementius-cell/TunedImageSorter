# -*- coding: utf-8 -*-
"""Pipeline orchestration for Tuned Image Sorter.

Этап 004 / v45 made this module the owner of ``run_pipeline()``.
Этап 021 / v62 keeps stage dispatch from Этап 005 and dispatches individual stages through ``core.stages``.
The heavy scan/cluster/copy implementations are still kept in the legacy
algorithm module for safety, but orchestration and run-state transitions live
here while individual stage dispatch is routed through ``core.stages``.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, List, Optional

from .config import ProgressCallbacks, RunConfig, RunResult, stages_for_mode
from . import stages as core_stages


def _legacy_core() -> Any:
    """Return the legacy implementation module without importing it at module load.

    In ``python face_sorter_mvp.py`` script mode the legacy module is ``__main__``.
    Prefer that already-loaded module to avoid importing a second copy of the file.
    """
    main_mod = sys.modules.get("__main__")
    main_file = getattr(main_mod, "__file__", None)
    if main_file and Path(main_file).name == "face_sorter_mvp.py" and hasattr(main_mod, "run_scan_stage"):
        return main_mod
    try:  # package mode
        from .. import face_sorter_mvp as legacy
    except ImportError:  # script-folder mode
        import face_sorter_mvp as legacy  # type: ignore
    return legacy


def run_pipeline(config: RunConfig, callbacks: Optional[ProgressCallbacks] = None) -> RunResult:
    """Run independent pipeline stages from a stable RunConfig.

    Этап 021 / v62: this function remains owned by ``core.pipeline`` and dispatches
    lower-level scan/cluster/assign/copy/report stages via ``core.stages``.
    Heavy implementation details are still preserved in the legacy algorithm
    module through thin stage facades.
    """
    legacy = _legacy_core()
    try:
        legacy.ensure_non_null_stdio()
    except Exception:
        pass
    callbacks = callbacks or legacy.ConsoleProgressCallbacks()
    args = config.to_namespace()
    stages_completed: List[str] = []
    stages_to_run = list(stages_for_mode(config.mode))

    previous_callbacks = legacy.CURRENT_CALLBACKS
    previous_state_dir = legacy.CURRENT_RUN_STATE_DIR
    previous_config_hash = legacy.CURRENT_RUN_CONFIG_HASH
    legacy.CURRENT_CALLBACKS = callbacks
    legacy.CURRENT_CONFIG = config
    legacy.CURRENT_ARGS = args
    legacy.CURRENT_RUN_CONFIG_HASH = config.config_hash()

    output_dir: Optional[Path] = None
    db_path: Optional[Path] = None
    conn = None
    bug_report_path = None

    try:
        callbacks.on_stage("validate", legacy.lang_text("Проверка настроек запуска", "Validating run settings"))
        legacy.validate_run_config(config)
        stages_completed.append("validate")

        output_dir = config.output_dir.resolve() if config.output_dir else Path(args.output).resolve()
        legacy.ensure_project_structure(output_dir)
        legacy.ensure_dir(legacy.diagnostics_dir_for_output(output_dir))
        legacy.write_run_config_json(config, output_dir)
        legacy.CURRENT_RUN_STATE_DIR = output_dir
        legacy.write_runtime_diagnostics(args)
        legacy.record_module_event(
            args,
            "pipeline_start",
            module="pipeline",
            mode=config.mode,
            stages_to_run=stages_to_run,
            output_dir=str(output_dir),
            db_path=str(config.db_path) if config.db_path else None,
            pipeline_owner="core.pipeline",
            stage_dispatch_owner="core.stages",
        )
        legacy.write_run_state(output_dir, args, "running", config=config, stage="starting", stages_completed=stages_completed)

        callbacks.on_stage("environment", legacy.lang_text("Проверка окружения и зависимостей", "Checking environment and dependencies"))
        legacy.record_module_event(args, "environment_start", module="environment")
        legacy.ensure_dependencies(args)
        legacy.load_runtime_modules()
        legacy.record_module_event(args, "environment_ok", module="environment", providers=legacy.available_onnx_providers())
        stages_completed.append("environment")
        legacy.mark_run_stage(output_dir, "environment", "running", "environment", stages_completed)

        # bug-report can run without a database, but we still keep validate/environment for logs.
        if stages_to_run == ["bug-report"]:
            callbacks.on_stage("bug_report", legacy.lang_text("Создание bug report", "Creating bug report"))
            bug_report_path = legacy.create_bug_report(args)
            stages_completed.append("bug_report")
            legacy.write_run_state(output_dir, args, "done", config=config, stage="done", last_successful_stage="bug_report", stages_completed=stages_completed)
            callbacks.on_stage("done", legacy.tr("done"))
            return RunResult(output_dir=output_dir, db_path=None, status="done", bug_report_path=bug_report_path, stages_completed=tuple(stages_completed))

        callbacks.on_stage("database", legacy.lang_text("Подготовка SQLite-кэша", "Preparing SQLite cache"))
        legacy.record_module_event(args, "database_start", module="database")
        db_path = config.db_path.resolve() if config.db_path else legacy.default_project_db_path(output_dir)
        args.db = str(db_path)
        conn = legacy.init_db(db_path)
        legacy.record_module_event(args, "database_ok", module="database", db_path=str(db_path))
        stages_completed.append("database")
        legacy.mark_run_stage(output_dir, "database", "running", "database", stages_completed)

        for stage in stages_to_run:
            legacy.record_module_event(args, "stage_start", module=stage, stage=stage)
            try:
                if stage == "scan":
                    core_stages.run_scan_stage(args, conn, callbacks, stages_completed, output_dir)
                elif stage == "cluster":
                    core_stages.run_cluster_stage(args, conn, callbacks, stages_completed, output_dir)
                elif stage == "assign":
                    core_stages.run_assign_stage(args, conn, callbacks, stages_completed, output_dir)
                elif stage == "copy":
                    core_stages.run_copy_stage(args, conn, callbacks, stages_completed, output_dir)
                elif stage == "report":
                    core_stages.run_report_stage(args, conn, callbacks, stages_completed, output_dir)
                elif stage == "review-clusters":
                    core_stages.run_review_clusters_stage(args, conn, callbacks, stages_completed, output_dir)
                elif stage == "apply-names":
                    core_stages.run_apply_names_stage(args, conn, callbacks, stages_completed, output_dir)
                elif stage == "bug-report":
                    callbacks.on_stage("bug_report", legacy.lang_text("Создание bug report", "Creating bug report"))
                    bug_report_path = legacy.create_bug_report(args)
                    stages_completed.append("bug_report")
                    legacy.mark_run_stage(output_dir, "bug_report", "running", "bug_report", stages_completed)
                else:
                    raise RuntimeError(f"Unknown pipeline stage: {stage}")
                legacy.record_module_event(args, "stage_done", module=stage, stage=stage, stages_completed=list(stages_completed))
            except Exception as stage_exc:
                legacy.record_module_event(
                    args,
                    "stage_error",
                    module=stage,
                    stage=stage,
                    error=repr(stage_exc),
                    traceback="".join(legacy.traceback.format_exception(type(stage_exc), stage_exc, stage_exc.__traceback__))[-12000:],
                    stages_completed=list(stages_completed),
                )
                raise

        if conn is not None:
            legacy.record_module_event(args, "database_close_start", module="database")
            conn.close()
            conn = None
            legacy.record_module_event(args, "database_close_ok", module="database")

        legacy.write_run_state(output_dir, args, "done", config=config, stage="done", last_successful_stage=(stages_completed[-1] if stages_completed else None), stages_completed=stages_completed)
        legacy.record_module_event(args, "pipeline_done", module="pipeline", stages_completed=list(stages_completed), pipeline_owner="core.pipeline", stage_dispatch_owner="core.stages")
        if config.make_bug_report and "bug_report" not in stages_completed:
            callbacks.on_stage("bug_report", legacy.lang_text("Создание bug report", "Creating bug report"))
            bug_report_path = legacy.create_bug_report(args)
            stages_completed.append("bug_report")

        callbacks.on_stage("done", legacy.tr("done"))
        if not getattr(callbacks, "handles_console_output", False):
            print("\n" + legacy.tr("done"))
        return RunResult(output_dir=output_dir, db_path=db_path, status="done", bug_report_path=bug_report_path, stages_completed=tuple(stages_completed))

    except Exception as exc:
        callbacks.on_error("pipeline", str(exc), traceback="".join(legacy.traceback.format_exception(type(exc), exc, exc.__traceback__)))
        if output_dir is not None:
            legacy.record_module_event(
                args,
                "pipeline_error",
                module="pipeline",
                error=repr(exc),
                traceback="".join(legacy.traceback.format_exception(type(exc), exc, exc.__traceback__))[-12000:],
                stages_completed=list(stages_completed),
                diagnostics_summary=legacy.summarize_diagnostics(output_dir),
                pipeline_owner="core.pipeline",
                stage_dispatch_owner="core.stages",
            )
            try:
                legacy.write_run_state(output_dir, args, "error", str(exc), config=config, stage="error", last_successful_stage=(stages_completed[-1] if stages_completed else None), stages_completed=stages_completed)
            except Exception:
                pass
        raise
    finally:
        if conn is not None:
            try:
                if output_dir is not None:
                    legacy.record_module_event(args, "database_close_in_finally_start", module="database")
                conn.close()
                if output_dir is not None:
                    legacy.record_module_event(args, "database_close_in_finally_ok", module="database")
            except Exception as close_exc:
                if output_dir is not None:
                    legacy.record_module_event(args, "database_close_in_finally_error", module="database", error=repr(close_exc))
        legacy.CURRENT_CALLBACKS = previous_callbacks
        legacy.CURRENT_RUN_STATE_DIR = previous_state_dir
        legacy.CURRENT_RUN_CONFIG_HASH = previous_config_hash


def validate_run_config(config: RunConfig) -> None:
    """Validate a RunConfig using the current legacy rules."""
    return _legacy_core().validate_run_config(config)


def run_config_from_namespace(ns: argparse.Namespace) -> RunConfig:
    """Build RunConfig from CLI/legacy argparse namespace."""
    return _legacy_core().run_config_from_namespace(ns)


def run_config_from_profile(profile_key: str, input_dir: Path, output_dir: Path, **overrides: Any) -> RunConfig:
    """Build RunConfig from a named quality profile."""
    return _legacy_core().run_config_from_profile(profile_key, input_dir, output_dir, **overrides)


def write_run_config_json(config: RunConfig, output_dir: Path) -> Path:
    """Write reports/run_config.json using the current legacy implementation."""
    return _legacy_core().write_run_config_json(config, output_dir)


def model_param_schema(*args: Any, **kwargs: Any) -> Any:
    """Return model parameter schema for UI/profile forms."""
    return _legacy_core().model_param_schema(*args, **kwargs)


def model_default_params(*args: Any, **kwargs: Any) -> Any:
    """Return model default parameters for UI/profile forms."""
    return _legacy_core().model_default_params(*args, **kwargs)


__all__ = [
    "run_pipeline",
    "validate_run_config",
    "run_config_from_namespace",
    "run_config_from_profile",
    "write_run_config_json",
    "model_param_schema",
    "model_default_params",
]
