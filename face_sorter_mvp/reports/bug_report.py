# -*- coding: utf-8 -*-
"""Bug-report implementation extracted during v44 / Этап 003."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional


def _legacy_core() -> Any:
    try:
        from .. import face_sorter_mvp as legacy
    except ImportError:
        import face_sorter_mvp as legacy  # type: ignore
    return legacy


def _ensure_legacy_globals() -> Any:
    """Bind legacy helper functions/constants lazily without overriding local implementations."""
    legacy = _legacy_core()
    for name, value in legacy.__dict__.items():
        if name.startswith("__"):
            continue
        globals().setdefault(name, value)
    return legacy



def _json_safe(value: Any) -> Any:
    if hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
        return _json_safe(value.to_dict())
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _safe_diag(name: str, fn: Any) -> Dict[str, Any]:
    try:
        return {"ok": True, "data": _json_safe(fn())}
    except Exception as exc:  # pragma: no cover - diagnostics path
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def collect_ui_bug_report_diagnostics(args: Any = None, error: Optional[BaseException] = None) -> Dict[str, Any]:
    """Collect import-safe GUI/release diagnostics for bug-report ZIPs.

    This helper is additive for v62 / Этап 021.  It does not include user
    photos, face crops or embeddings.  It may include UI logs, project paths and
    filenames already present in existing reports.
    """
    diagnostics: Dict[str, Any] = {
        "schema_version": 1,
        "source": "ui_bug_report_diagnostics",
        "error_present": error is not None,
    }

    def _imports() -> Dict[str, Any]:
        try:
            from ..core.api import ui_backend_api
            from ..core.contract import verify_ui_contract, ui_contract_freeze_snapshot
            from ..core.preflight import runtime_preflight, runtime_preflight_summary
            from ..core.self_test import run_backend_self_test
            from ..core.session import default_ui_state_path, load_ui_session_state
            from ..core.windows_packaging import windows_packaging_plan, verify_windows_packaging
            from ..core.release import run_release_check
        except ImportError:
            from core.api import ui_backend_api  # type: ignore
            from core.contract import verify_ui_contract, ui_contract_freeze_snapshot  # type: ignore
            from core.preflight import runtime_preflight, runtime_preflight_summary  # type: ignore
            from core.self_test import run_backend_self_test  # type: ignore
            from core.session import default_ui_state_path, load_ui_session_state  # type: ignore
            from core.windows_packaging import windows_packaging_plan, verify_windows_packaging  # type: ignore
            from core.release import run_release_check  # type: ignore
        return locals()

    try:
        ns = _imports()
    except Exception as exc:  # pragma: no cover - diagnostics path
        diagnostics["import_error"] = f"{type(exc).__name__}: {exc}"
        return diagnostics

    diagnostics["capabilities"] = _safe_diag("capabilities", lambda: ns["ui_backend_api"]().to_dict())
    diagnostics["ui_contract"] = _safe_diag("ui_contract", lambda: {
        "snapshot": ns["ui_contract_freeze_snapshot"]().to_dict(),
        "verification": ns["verify_ui_contract"]().to_dict(),
    })
    diagnostics["runtime_preflight"] = _safe_diag("runtime_preflight", lambda: ns["runtime_preflight_summary"](run_gpu_smoke_test=False))

    def _self_test_summary() -> Dict[str, Any]:
        result = ns["run_backend_self_test"]()
        return {
            "ok": result.ok,
            "version": result.version,
            "refactor_stage": result.refactor_stage,
            "ui_api_version": result.ui_api_version,
            "duration_ms": result.duration_ms,
            "check_count": len(result.checks),
            "checks": [{"name": check.name, "ok": check.ok, "message": check.message} for check in result.checks],
            "errors": list(result.errors),
            "warnings": list(result.warnings),
        }

    diagnostics["backend_self_test"] = _safe_diag("backend_self_test", _self_test_summary)
    diagnostics["windows_packaging"] = _safe_diag("windows_packaging", lambda: {
        "plan": ns["windows_packaging_plan"]().to_dict(),
        "verification": ns["verify_windows_packaging"]().to_dict(),
    })
    diagnostics["release_check"] = _safe_diag("release_check", lambda: ns["run_release_check"](include_self_test=False).to_dict())

    session_path_raw = getattr(args, "ui_session_path", None) if args is not None else None
    session_state = getattr(args, "ui_session_state", None) if args is not None else None
    if session_state is not None:
        diagnostics["ui_session_state_from_ui"] = _json_safe(session_state)
    diagnostics["ui_session_state_from_disk"] = _safe_diag(
        "ui_session_state_from_disk",
        lambda: {
            "path": str(Path(session_path_raw).expanduser() if session_path_raw else ns["default_ui_state_path"]()),
            "state": ns["load_ui_session_state"](Path(session_path_raw).expanduser() if session_path_raw else ns["default_ui_state_path"]()).to_dict(),
        },
    )

    for attr in (
        "ui_job_snapshot",
        "ui_last_events",
        "ui_status_log",
        "ui_result_log",
        "ui_reports_details",
        "ui_diagnostics_text",
    ):
        value = getattr(args, attr, None) if args is not None else None
        if value not in (None, ""):
            diagnostics[attr] = _json_safe(value)

    return diagnostics




SUPPORT_BUNDLE_README_RU = """Tuned Image Sorter support-bundle / bug-report

Назначение
----------
Этот ZIP предназначен для диагностики проблем запуска, сортировки, GPU runtime и UI. Его можно отправить разработчику вместо полной папки результата.

Что входит
----------
- system_info.json с параметрами запуска, окружением и краткой сводкой;
- ui/ui_diagnostics.json с UI/backend/release diagnostics;
- pip_freeze.txt или frozen package snapshot;
- face_sorter_mvp.log, если он есть;
- project.json / .face_sorter_run.json, если они есть;
- CSV-отчёты из output/reports;
- result-health summary: output/reports/result_health_check.json и .txt, если известна output папка;
- output/reports/diagnostics;
- support_bundle_manifest.json со списком файлов внутри ZIP.

Что не входит по умолчанию
--------------------------
- исходные фотографии;
- face crops / изображения лиц;
- SQLite embeddings;
- папки people, review, final, final_review.

Приватность
-----------
ZIP может содержать имена файлов, пути к папкам, тексты ошибок, сведения о системе и версии библиотек. Перед отправкой можно открыть ZIP и проверить содержимое.
""".strip()

SUPPORT_BUNDLE_README_EN = """Tuned Image Sorter support-bundle / bug-report

Purpose
-------
This ZIP is intended for diagnosing startup, sorting, GPU runtime and UI issues. Send it to the developer instead of the full result folder.

What it contains
----------------
- system_info.json with launch parameters, environment and a compact summary;
- ui/ui_diagnostics.json with UI/backend/release diagnostics;
- pip_freeze.txt or a frozen package snapshot;
- face_sorter_mvp.log, if present;
- project.json / .face_sorter_run.json, if present;
- CSV reports from output/reports;
- result-health summary: output/reports/result_health_check.json and .txt when an output folder is known;
- output/reports/diagnostics;
- support_bundle_manifest.json listing ZIP entries.

What is not included by default
-------------------------------
- source photos;
- face crops / face images;
- SQLite embeddings;
- people, review, final, final_review folders.

Privacy
-------
The ZIP may contain filenames, folder paths, error text, system information and package versions. You can open the ZIP before sending and inspect its contents.
""".strip()


def _support_bundle_manifest(zip_path: Path, zf: Any, system_info: Dict[str, Any], output_dir: Optional[Path], input_dir: Optional[Path]) -> Dict[str, Any]:
    """Return a compact manifest for the diagnostic ZIP without adding user media."""
    entries = sorted(set(zf.namelist()) | {"support_bundle_manifest.json"})
    return {
        "schema_version": 1,
        "kind": "face_sorter_support_bundle",
        "created_at": system_info.get("created_at"),
        "script_version": system_info.get("script_version"),
        "zip_name": zip_path.name,
        "output_dir": str(output_dir) if output_dir else "",
        "input_dir_present": bool(input_dir),
        "entry_count": len(entries),
        "entries": entries,
        "privacy_summary": {
            "includes_original_photos": False,
            "includes_face_crops": False,
            "includes_sqlite_embeddings": False,
            "may_include_file_names": True,
            "may_include_folder_paths": True,
            "may_include_system_information": True,
            "may_include_error_text": True,
        },
        "includes_result_health_check": any("result_health_check" in name for name in entries),
        "recommended_to_send": [
            "this ZIP file",
            "a short description of what the user clicked before the problem",
            "PowerShell output from runtime-preflight/release-check when available",
        ],
    }



def _build_result_health_for_support_bundle(output_dir: Optional[Path]) -> Optional[Dict[str, Any]]:
    """Run the lightweight result-health check before packaging diagnostics.

    The health check is additive: it writes only reports/result_health_check.*
    and never scans photos, opens embeddings, copies files or changes existing
    CSV schemas.  Failures are captured in system_info instead of aborting the
    support-bundle.
    """
    if output_dir is None or not output_dir.exists() or not output_dir.is_dir():
        return None
    try:
        try:
            from ..core.result_health import build_result_health_summary
        except ImportError:
            from face_sorter_mvp.core.result_health import build_result_health_summary  # type: ignore
        summary = build_result_health_summary(output_dir, write_reports=True)
        return _json_safe(summary)
    except Exception as exc:  # pragma: no cover - diagnostics path
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "note": "support-bundle continues even when result-health generation fails",
        }


def _write_if_exists(zf: Any, file_path: Path, arcname: str) -> bool:
    """Write a file into a ZIP if it exists, returning whether it was added."""
    try:
        if file_path.exists() and file_path.is_file():
            zf.write(file_path, arcname)
            return True
    except Exception:
        pass
    return False

def _pip_freeze_for_bug_report() -> str:
    """Return package inventory without spawning the frozen EXE as ``python -m pip``.

    In a PyInstaller build ``sys.executable`` is ``TunedImageSorter.exe``.  Running
    ``[sys.executable, "-m", "pip", "freeze"]`` would start another GUI
    process instead of pip.  Source mode keeps the traditional pip-freeze output;
    frozen mode writes a metadata/import snapshot that is safe and does not open
    another app window.
    """
    import json as _json
    import sys as _sys
    if bool(getattr(_sys, "frozen", False)):
        try:
            from ..core.frozen_diagnostics import package_import_snapshot
        except Exception:
            try:
                from face_sorter_mvp.core.frozen_diagnostics import package_import_snapshot  # type: ignore
            except Exception as exc:
                return f"frozen package snapshot failed: {type(exc).__name__}: {exc}"
        return _json.dumps({"frozen": True, "note": "pip freeze skipped in frozen EXE to avoid launching another GUI process", "packages": package_import_snapshot()}, ensure_ascii=False, indent=2)
    code, freeze = run_capture([_sys.executable, "-m", "pip", "freeze"], timeout=30)
    return freeze if freeze else f"pip freeze failed: code={code}"


def create_bug_report(args: Optional[argparse.Namespace] = None, error: Optional[BaseException] = None) -> Optional[Path]:
    """Create a ZIP bug report without including user photos.

    If an output/project folder is known, the report is saved into project/bug_reports.
    Otherwise it falls back to the script-level bug_reports directory.
    """
    _ensure_legacy_globals()
    try:
        output_dir = Path(getattr(args, "output", "") or "").resolve() if args and getattr(args, "output", None) else None
        input_dir = Path(getattr(args, "input", "") or "").resolve() if args and getattr(args, "input", None) else None
        if output_dir is not None:
            ensure_dir(diagnostics_dir_for_output(output_dir))
            write_runtime_diagnostics(args)
            record_module_event(args, "bug_report_create_start", module="bug_report", error_present=error is not None)
        reports_root = (output_dir / "bug_reports") if output_dir else BUG_REPORTS_DIR
        ensure_dir(reports_root)
        result_health_summary = _build_result_health_for_support_bundle(output_dir)
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = reports_root / f"tuned_image_sorter_bug_report_{stamp}.zip"
        system_info = {
            "created_at": now_iso(),
            "script_version": SCRIPT_VERSION,
            "script_path": str(Path(_legacy_core().__file__).resolve()),
            "python_exe": sys.executable,
            "python_version": sys.version.replace("\n", " "),
            "platform": platform.platform(),
            "args": vars(args) if args is not None else {},
            "environment_snapshot": environment_snapshot(include_providers=True),
            "input_summary": summarize_input_files(input_dir),
            "diagnostics_summary": summarize_diagnostics(output_dir),
            "result_health_summary": result_health_summary,
            "privacy_note": "The report does not include original photos, face crops, or SQLite embeddings by default. It may include file paths and filenames.",
            "model_registry": {k: {"engine": v.get("engine"), "default_params": v.get("default_params"), "param_schema": v.get("param_schema")} for k, v in MODEL_REGISTRY.items()},
        }
        ui_diagnostics = collect_ui_bug_report_diagnostics(args, error)
        system_info["ui_diagnostics_summary"] = {
            "available": bool(ui_diagnostics),
            "capabilities_ok": bool(ui_diagnostics.get("capabilities", {}).get("ok")),
            "self_test_ok": bool(ui_diagnostics.get("backend_self_test", {}).get("data", {}).get("ok")),
            "release_check_ok": bool(ui_diagnostics.get("release_check", {}).get("data", {}).get("ok")),
            "ui_events_count": len(ui_diagnostics.get("ui_last_events", []) or []),
        }
        if error is not None:
            system_info["error"] = {
                "type": type(error).__name__,
                "message": str(error),
                "traceback": "".join(traceback.format_exception(type(error), error, error.__traceback__))[-20000:],
            }

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("system_info.json", json.dumps(system_info, ensure_ascii=False, indent=2))
            zf.writestr("ui/ui_diagnostics.json", json.dumps(ui_diagnostics, ensure_ascii=False, indent=2))
            if ui_diagnostics.get("ui_session_state_from_ui") is not None:
                zf.writestr("ui/ui_session_state_from_ui.json", json.dumps(ui_diagnostics.get("ui_session_state_from_ui"), ensure_ascii=False, indent=2))
            if ui_diagnostics.get("ui_last_events") is not None:
                zf.writestr("ui/ui_last_events.json", json.dumps(ui_diagnostics.get("ui_last_events"), ensure_ascii=False, indent=2))
            zf.writestr("support_bundle/README_RU.txt", SUPPORT_BUNDLE_README_RU + "\n")
            zf.writestr("support_bundle/README_EN.txt", SUPPORT_BUNDLE_README_EN + "\n")
            zf.writestr("pip_freeze.txt", _pip_freeze_for_bug_report())
            for file_path, arcname in [
                (APP_LOG_FILE, "face_sorter_mvp.log"),
                (ENV_STATE_FILE, "face_sorter_mvp_env_state.json"),
            ]:
                if file_path.exists():
                    zf.write(file_path, arcname)
            if output_dir and output_dir.exists():
                project_file = output_dir / PROJECT_FILENAME
                if project_file.exists():
                    zf.write(project_file, f"output/{PROJECT_FILENAME}")
                legacy_state = output_dir / LEGACY_RUN_STATE_FILENAME
                if legacy_state.exists():
                    zf.write(legacy_state, f"output/{LEGACY_RUN_STATE_FILENAME}")
                for rel in [
                    f"reports/{PROBLEM_FILES_NAME}",
                    "reports/filename_map.csv",
                    "reports/duplicates.csv",
                    "reports/review_clusters.csv",
                    "reports/review_decisions.csv",
                    "reports/assignments.csv",
                    "reports/summary.csv",
                    "reports/result_health_check.json",
                    "reports/result_health_check.txt",
                    "names.csv",
                ]:
                    fp = output_dir / rel
                    if fp.exists() and fp.is_file():
                        zf.write(fp, f"output/{rel}")
                diag_dir = diagnostics_dir_for_output(output_dir)
                if diag_dir.exists():
                    for fp in sorted(diag_dir.rglob("*")):
                        if fp.is_file():
                            try:
                                rel = fp.relative_to(diag_dir)
                                zf.write(fp, f"output/reports/{DIAGNOSTICS_DIR_NAME}/{rel.as_posix()}")
                            except Exception:
                                pass
            manifest = _support_bundle_manifest(zip_path, zf, system_info, output_dir, input_dir)
            zf.writestr("support_bundle_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        if output_dir is not None:
            record_module_event(args, "bug_report_create_done", module="bug_report", zip_path=str(zip_path))
        print(lang_text("Bug report создан:", "Bug report created:"), zip_path)
        return zip_path
    except Exception as exc:
        print(lang_text("Не удалось создать bug report:", "Failed to create bug report:"), exc)
        return None


def summarize_diagnostics(*args: Any, **kwargs: Any) -> Any:
    return _legacy_core().summarize_diagnostics(*args, **kwargs)


def diagnostics_dir_for_output(*args: Any, **kwargs: Any) -> Any:
    return _legacy_core().diagnostics_dir_for_output(*args, **kwargs)


__all__ = ["create_bug_report", "collect_ui_bug_report_diagnostics", "summarize_diagnostics", "diagnostics_dir_for_output"]
