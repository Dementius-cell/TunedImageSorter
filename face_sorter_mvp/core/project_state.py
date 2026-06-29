# -*- coding: utf-8 -*-
"""Project.json and resume-state helpers.

The functions here are intentionally independent of CLI parsing and ML runtime.
They preserve the existing project.json / legacy run-state format while making
that boundary importable for a future UI.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .constants import (
    LEGACY_RUN_STATE_FILENAME,
    PROJECT_DIRS,
    PROJECT_FILENAME,
    RESULT_FOLDER_RE,
    SCRIPT_VERSION,
)
from .contracts import RunConfig


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def project_json_path(project_dir: Path) -> Path:
    """Return the project.json path for a project/output directory."""
    return project_dir / PROJECT_FILENAME


def legacy_run_state_path(project_dir: Path) -> Path:
    """Return the legacy .face_sorter_run.json path for backward compatibility."""
    return project_dir / LEGACY_RUN_STATE_FILENAME


def ensure_project_structure(project_dir: Path) -> None:
    """Create the stable project folder layout used by CLI and future UI.

    A project is simply the result/output folder. Existing v17-v30 result folders are
    treated as projects and receive project.json on the next run.
    """
    ensure_dir(project_dir)
    for name in PROJECT_DIRS:
        ensure_dir(project_dir / name)


def project_dirs_payload(project_dir: Path) -> Dict[str, str]:
    """Return standard project subdirectory paths for project.json."""
    return {
        "root": str(project_dir),
        "database": str(project_dir / "database"),
        "reports": str(project_dir / "reports"),
        "people": str(project_dir / "people"),
        "review": str(project_dir / "review"),
        "final": str(project_dir / "final"),
        "logs": str(project_dir / "logs"),
        "bug_reports": str(project_dir / "bug_reports"),
    }


def default_project_db_path(project_dir: Path) -> Path:
    """Return the preferred SQLite path for a project.

    v31+ uses project/database/faces.sqlite. If a legacy v20-v30 project already has
    project/db/faces.sqlite and the new database path does not exist, keep using the
    legacy DB to avoid forcing a rescan.
    """
    new_path = project_dir / "database" / "faces.sqlite"
    legacy_path = project_dir / "db" / "faces.sqlite"
    if legacy_path.exists() and not new_path.exists():
        return legacy_path
    return new_path


def read_project_json(project_dir: Path) -> Dict[str, Any]:
    """Read project.json for an existing Face Sorter project."""
    path = project_json_path(project_dir)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_legacy_run_state(project_dir: Path) -> Dict[str, Any]:
    """Read legacy run-state data from older result folders."""
    path = legacy_run_state_path(project_dir)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_run_state(output_dir: Path) -> Dict[str, Any]:
    """Read primary project.json, falling back to legacy .face_sorter_run.json."""
    state = read_project_json(output_dir)
    if state:
        return state
    return read_legacy_run_state(output_dir)


def load_project_config(project_dir: Path) -> Dict[str, Any]:
    """Load a project created by v31+ or migrate enough data from a legacy run state."""
    state = read_run_state(project_dir)
    if not state:
        return {}
    cfg = state.get("config") if isinstance(state.get("config"), dict) else {}
    result: Dict[str, Any] = dict(cfg)
    # Legacy/top-level fields remain useful when reports/run_config.json is absent.
    for src, dst in [
        ("input_dir", "input"),
        ("input", "input"),
        ("output_dir", "output"),
        ("output", "output"),
        ("mode", "mode"),
        ("profile", "scan_profile"),
        ("model", "model"),
        ("use_gpu", "gpu"),
        ("gpu", "gpu"),
    ]:
        if src in state and state.get(src) not in (None, "") and dst not in result:
            result[dst] = state.get(src)
    # Normalize RunConfig JSON keys back to argparse-style keys.
    if result.get("input_dir") and not result.get("input"):
        result["input"] = result.get("input_dir")
    if result.get("output_dir") and not result.get("output"):
        result["output"] = result.get("output_dir")
    if result.get("db_path") and not result.get("db"):
        result["db"] = result.get("db_path")
    if result.get("names_path") and not result.get("names"):
        result["names"] = result.get("names_path")
    if result.get("language") and not result.get("lang"):
        result["lang"] = result.get("language")
    if "use_gpu" in result and "gpu" not in result:
        result["gpu"] = bool(result.get("use_gpu"))
    if result.get("algorithm") and not result.get("algo"):
        result["algo"] = result.get("algorithm")

    result.setdefault("output", str(project_dir))
    result.setdefault("project", str(project_dir))
    # Prefer the DB actually present in the project.
    result.setdefault("db", str(default_project_db_path(project_dir)))
    return result


def build_run_state_base(
    output_dir: Path,
    config: Optional[RunConfig] = None,
    args: Optional[argparse.Namespace] = None,
) -> Dict[str, Any]:
    """Build the formal project/run state saved into project.json."""
    now = dt.datetime.now().isoformat(timespec="seconds")
    if config is not None:
        input_dir = str(config.input_dir or "")
        output_value = str(output_dir)
        profile = config.profile
        mode = config.mode
        model = config.model
        use_gpu = config.use_gpu
        cfg_hash = config.config_hash()
    else:
        input_dir = str(getattr(args, "input", "") or "")
        output_value = str(output_dir)
        profile = str(getattr(args, "scan_profile", getattr(args, "profile", "")) or "")
        mode = str(getattr(args, "mode", "") or "")
        model = str(getattr(args, "model", "") or "")
        use_gpu = bool(getattr(args, "gpu", False))
        try:
            cfg_hash = hashlib.sha256(json.dumps(vars(args or argparse.Namespace()), ensure_ascii=False, sort_keys=True, default=str).encode("utf-8", errors="replace")).hexdigest()[:16]
        except Exception:
            cfg_hash = ""
    return {
        "app": "face_sorter_mvp",
        "version": SCRIPT_VERSION,
        "status": "running",
        "started_at": now,
        "finished_at": None,
        "updated_at": now,
        "input_dir": input_dir,
        "output_dir": output_value,
        "project_dir": output_value,
        "project": {
            "format_version": 1,
            "root": output_value,
            "dirs": project_dirs_payload(output_dir),
        },
        "profile": profile,
        "mode": mode,
        "model": model,
        "use_gpu": use_gpu,
        "config_hash": cfg_hash,
        "stage": "created",
        "last_successful_stage": None,
        "files_total": None,
        "files_scanned": 0,
        "copy_total": None,
        "files_copied": 0,
        "stages_completed": [],
        "config": config.to_json_dict() if config is not None else {},
    }


def write_run_state(
    output_dir: Path,
    args: Optional[argparse.Namespace] = None,
    status: str = "running",
    error: Optional[str] = None,
    *,
    config: Optional[RunConfig] = None,
    stage: Optional[str] = None,
    last_successful_stage: Optional[str] = None,
    progress: Optional[Dict[str, Any]] = None,
    stages_completed: Optional[Sequence[str]] = None,
) -> None:
    """Write formal run state for resume-aware CLI/GUI flows.

    This file is a comfort/recovery feature. Any error while writing it must not break
    the real photo sorting work.
    """
    try:
        ensure_project_structure(output_dir)
        now = dt.datetime.now().isoformat(timespec="seconds")
        existing = read_run_state(output_dir)
        state = existing or build_run_state_base(output_dir, config=config, args=args)
        base = build_run_state_base(output_dir, config=config, args=args)
        for key in ("app", "version", "input_dir", "output_dir", "profile", "mode", "model", "use_gpu", "config_hash"):
            if base.get(key) not in (None, ""):
                state[key] = base[key]
        state.setdefault("started_at", now)
        state["status"] = status
        state["updated_at"] = now
        if status in {"done", "error", "interrupted"}:
            state["finished_at"] = now
        else:
            state.setdefault("finished_at", None)
        if stage:
            state["stage"] = stage
        if last_successful_stage:
            state["last_successful_stage"] = last_successful_stage
        if stages_completed is not None:
            state["stages_completed"] = list(stages_completed)
        if progress:
            state.update(progress)
        if error:
            state["error"] = str(error)[-4000:]
        elif status == "running":
            state.pop("error", None)
        state["project_dir"] = str(output_dir)
        state["project"] = {
            "format_version": 1,
            "root": str(output_dir),
            "dirs": project_dirs_payload(output_dir),
        }
        if config is not None:
            state["config"] = config.to_json_dict()
        # Legacy aliases kept for v17-v30 compatibility and external tools.
        state["input"] = state.get("input_dir", "")
        state["output"] = state.get("output_dir", str(output_dir))
        state["gpu"] = bool(state.get("use_gpu", False))
        payload = json.dumps(state, ensure_ascii=False, indent=2)
        project_json_path(output_dir).write_text(payload, encoding="utf-8")
        # Compatibility mirror. Future UI should use project.json, but old scripts/tools
        # may still look for .face_sorter_run.json.
        legacy_run_state_path(output_dir).write_text(payload, encoding="utf-8")
    except Exception:
        pass


def find_unfinished_result_dirs(input_dir: Path) -> List[Tuple[Path, Dict[str, Any]]]:
    """Find timestamped result folders that appear unfinished for resume prompts."""
    base_dir = input_dir.resolve().parent
    candidates: List[Tuple[Path, Dict[str, Any]]] = []
    if not base_dir.exists():
        return candidates
    try:
        for child in base_dir.iterdir():
            if not child.is_dir() or not RESULT_FOLDER_RE.match(child.name):
                continue
            state = read_run_state(child)
            status = str(state.get("status", "")).lower()
            state_input = state.get("input_dir") or state.get("input")
            same_input = not state_input or str(Path(str(state_input)).resolve()) == str(input_dir.resolve())
            if same_input and status in {"", "running", "error", "interrupted"}:
                candidates.append((child, state))
    except Exception:
        return candidates
    candidates.sort(key=lambda item: item[0].stat().st_mtime if item[0].exists() else 0, reverse=True)
    return candidates


def resume_mode_from_state(state: Dict[str, Any], default_mode: str = "all") -> str:
    """Choose the nearest safe continuation mode from formal run state."""
    last = str(state.get("last_successful_stage") or "").lower()
    stage = str(state.get("stage") or "").lower()
    marker = last or stage
    if marker in {"scan"}:
        return "cluster"
    if marker in {"cluster"}:
        return "copy"
    if marker in {"copy"}:
        return "report"
    if marker in {"reports", "apply_names", "done"}:
        return default_mode
    return default_mode


def describe_run_state_for_user(path: Path, state: Dict[str, Any]) -> str:
    """Format run-state data into a concise console summary."""
    status = state.get("status", "unknown")
    stage = state.get("stage", "unknown")
    last = state.get("last_successful_stage") or "none"
    updated = state.get("updated_at", "unknown")
    scanned = state.get("files_scanned", 0)
    total = state.get("files_total")
    files_part = f"; files={scanned}/{total}" if total not in (None, "") else f"; files_scanned={scanned}"
    return f"{path.name} | status={status}; stage={stage}; last_successful_stage={last}; updated={updated}{files_part}"
