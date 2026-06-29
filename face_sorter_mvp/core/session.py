# -*- coding: utf-8 -*-
"""Import-safe UI session/state helpers for future Windows UI.

v62 / Этап 021 adds a small JSON-serializable session contract for a future
PySide6 shell.  This module stores UI preferences such as the selected profile,
last folders, GPU/CPU choice and recent projects.  It does not start the CLI
wizard, does not modify ``project.json`` and does not import ML/runtime modules.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from .config import RunConfig
from .constants import DEFAULT_PROFILE, SCRIPT_VERSION

UI_SESSION_SCHEMA_VERSION = 2


def _now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _path_or_none(value: Any) -> Optional[Path]:
    if value in (None, ""):
        return None
    return Path(value).expanduser()


@dataclass(frozen=True)
class UiRecentProject:
    """One recent project/result folder entry for UI start screens."""

    path: Path
    input_dir: str = ""
    output_dir: str = ""
    status: str = ""
    last_successful_stage: str = ""
    updated_at: str = ""
    display_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["path"] = str(self.path)
        return data


@dataclass(frozen=True)
class UiSessionState:
    """Serializable UI preferences/state independent from ``project.json``.

    This is intentionally separate from run/project state.  A UI can save it in
    a user configuration directory and use it to pre-fill controls next time the
    application starts.
    """

    schema_version: int = UI_SESSION_SCHEMA_VERSION
    app_version: str = SCRIPT_VERSION
    language: str = "auto"
    selected_profile: str = "normal"
    selected_mode: str = "all"
    use_gpu: bool = False
    auto_cpu_fallback: bool = True
    photo_assignment: str = str(DEFAULT_PROFILE.get("photo_assignment", "best-face"))
    copy_group_photos: bool = bool(DEFAULT_PROFILE.get("copy_group_photos", False))
    scan_workers: str = str(DEFAULT_PROFILE.get("scan_workers", "auto"))
    copy_workers: str = str(DEFAULT_PROFILE.get("copy_workers", "auto"))
    ui_theme: str = "system"
    ui_density: str = "comfortable"
    show_startup_tips: bool = True
    confirm_before_run: bool = True
    auto_open_reports_after_run: bool = False
    show_advanced_fields: bool = False
    verbose_progress_events: bool = False
    auto_scroll_logs: bool = True
    last_input_dir: Optional[Path] = None
    last_output_dir: Optional[Path] = None
    recent_projects: Tuple[UiRecentProject, ...] = ()
    extra: Dict[str, Any] = field(default_factory=dict)
    updated_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["last_input_dir"] = str(self.last_input_dir) if self.last_input_dir else None
        data["last_output_dir"] = str(self.last_output_dir) if self.last_output_dir else None
        data["recent_projects"] = [item.to_dict() for item in self.recent_projects]
        data["extra"] = copy.deepcopy(self.extra)
        return data


# Backwards-friendly alias for UI code that wants to show a schema number.
UI_SESSION_DEFAULTS = UiSessionState()


def default_ui_state_path(*, app_name: str = "TunedImageSorter") -> Path:
    """Return the recommended per-user UI session JSON path without creating it."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / app_name / "ui_session.json"
    return Path.home() / ".config" / app_name / "ui_session.json"


def default_ui_session_state(**overrides: Any) -> UiSessionState:
    """Create a fresh UI session state, optionally replacing simple fields."""
    state = UiSessionState(updated_at=_now_iso())
    if overrides:
        state = update_ui_session_state(state, **overrides)
    return state


def ui_recent_project_from_dict(data: Dict[str, Any]) -> UiRecentProject:
    """Parse a recent project entry from JSON-like data."""
    return UiRecentProject(
        path=Path(str(data.get("path") or "")).expanduser(),
        input_dir=str(data.get("input_dir") or ""),
        output_dir=str(data.get("output_dir") or ""),
        status=str(data.get("status") or ""),
        last_successful_stage=str(data.get("last_successful_stage") or ""),
        updated_at=str(data.get("updated_at") or ""),
        display_text=str(data.get("display_text") or ""),
    )


def ui_session_state_from_dict(data: Dict[str, Any]) -> UiSessionState:
    """Parse UI session state from JSON-like data with safe defaults."""
    recent_raw = data.get("recent_projects") or []
    recent = tuple(
        ui_recent_project_from_dict(item)
        for item in recent_raw
        if isinstance(item, dict) and item.get("path")
    )
    extra = data.get("extra") if isinstance(data.get("extra"), dict) else {}
    return UiSessionState(
        schema_version=int(data.get("schema_version") or UI_SESSION_SCHEMA_VERSION),
        app_version=str(data.get("app_version") or SCRIPT_VERSION),
        language=str(data.get("language") or "auto"),
        selected_profile=str(data.get("selected_profile") or "normal"),
        selected_mode=str(data.get("selected_mode") or "all"),
        use_gpu=bool(data.get("use_gpu", False)),
        auto_cpu_fallback=bool(data.get("auto_cpu_fallback", True)),
        photo_assignment=str(data.get("photo_assignment") or DEFAULT_PROFILE.get("photo_assignment", "best-face")),
        copy_group_photos=bool(data.get("copy_group_photos", DEFAULT_PROFILE.get("copy_group_photos", False))),
        scan_workers=str(data.get("scan_workers") or DEFAULT_PROFILE.get("scan_workers", "auto")),
        copy_workers=str(data.get("copy_workers") or DEFAULT_PROFILE.get("copy_workers", "auto")),
        ui_theme=str(data.get("ui_theme") or (extra.get("ui_theme") if isinstance(extra, dict) else None) or "system"),
        ui_density=str(data.get("ui_density") or (extra.get("ui_density") if isinstance(extra, dict) else None) or "comfortable"),
        show_startup_tips=bool(data.get("show_startup_tips", (extra.get("show_startup_tips", True) if isinstance(extra, dict) else True))),
        confirm_before_run=bool(data.get("confirm_before_run", (extra.get("confirm_before_run", True) if isinstance(extra, dict) else True))),
        auto_open_reports_after_run=bool(data.get("auto_open_reports_after_run", (extra.get("auto_open_reports_after_run", False) if isinstance(extra, dict) else False))),
        show_advanced_fields=bool(data.get("show_advanced_fields", (extra.get("show_advanced_fields", False) if isinstance(extra, dict) else False))),
        verbose_progress_events=bool(data.get("verbose_progress_events", (extra.get("verbose_progress_events", False) if isinstance(extra, dict) else False))),
        auto_scroll_logs=bool(data.get("auto_scroll_logs", (extra.get("auto_scroll_logs", True) if isinstance(extra, dict) else True))),
        last_input_dir=_path_or_none(data.get("last_input_dir")),
        last_output_dir=_path_or_none(data.get("last_output_dir")),
        recent_projects=recent,
        extra=copy.deepcopy(extra),
        updated_at=str(data.get("updated_at") or _now_iso()),
    )


def load_ui_session_state(path: str | Path, *, missing_ok: bool = True) -> UiSessionState:
    """Load UI session state from JSON.

    ``missing_ok=True`` returns defaults when the file does not exist.  Invalid
    JSON or an incompatible shape raises ``ValueError`` with the original error
    attached as context so the UI can show a clear diagnostics message.
    """
    session_path = Path(path).expanduser()
    if not session_path.exists():
        if missing_ok:
            return default_ui_session_state()
        raise FileNotFoundError(str(session_path))
    try:
        data = json.loads(session_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError("UI session JSON root must be an object")
        return ui_session_state_from_dict(data)
    except Exception as exc:
        raise ValueError(f"Failed to load UI session state from {session_path}: {exc}") from exc


def save_ui_session_state(state: UiSessionState, path: str | Path) -> Path:
    """Save UI session state as UTF-8 JSON and return the written path."""
    session_path = Path(path).expanduser()
    session_path.parent.mkdir(parents=True, exist_ok=True)
    payload = replace(state, app_version=SCRIPT_VERSION, updated_at=_now_iso()).to_dict()
    session_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return session_path


def update_ui_session_state(state: UiSessionState, **changes: Any) -> UiSessionState:
    """Return a new state with selected fields replaced and ``updated_at`` refreshed."""
    normalized = dict(changes)
    if "last_input_dir" in normalized:
        normalized["last_input_dir"] = _path_or_none(normalized["last_input_dir"])
    if "last_output_dir" in normalized:
        normalized["last_output_dir"] = _path_or_none(normalized["last_output_dir"])
    normalized["updated_at"] = _now_iso()
    normalized["app_version"] = SCRIPT_VERSION
    return replace(state, **normalized)


def remember_recent_project(
    state: UiSessionState,
    project_dir: str | Path,
    *,
    input_dir: str = "",
    output_dir: str = "",
    status: str = "",
    last_successful_stage: str = "",
    updated_at: str = "",
    display_text: str = "",
    max_items: int = 10,
) -> UiSessionState:
    """Return a state with a project/result folder moved to the recent list top."""
    path = Path(project_dir).expanduser()
    key = str(path).lower()
    entry = UiRecentProject(
        path=path,
        input_dir=input_dir,
        output_dir=output_dir,
        status=status,
        last_successful_stage=last_successful_stage,
        updated_at=updated_at or _now_iso(),
        display_text=display_text,
    )
    kept = tuple(item for item in state.recent_projects if str(item.path).lower() != key)
    return update_ui_session_state(state, recent_projects=(entry,) + kept[: max(0, max_items - 1)])


def prune_recent_projects(state: UiSessionState, *, existing_only: bool = True, max_items: int = 10) -> UiSessionState:
    """Trim recent projects for UI display."""
    items: Iterable[UiRecentProject] = state.recent_projects
    if existing_only:
        items = (item for item in items if item.path.exists())
    return update_ui_session_state(state, recent_projects=tuple(items)[:max_items])


def config_to_ui_session_state(config: RunConfig, state: Optional[UiSessionState] = None) -> UiSessionState:
    """Capture the UI-relevant parts of a RunConfig into session state."""
    base = state or default_ui_session_state()
    return update_ui_session_state(
        base,
        language=config.language,
        selected_profile=config.profile,
        selected_mode=config.mode,
        use_gpu=config.use_gpu,
        auto_cpu_fallback=config.auto_cpu_fallback,
        photo_assignment=config.photo_assignment,
        copy_group_photos=config.copy_group_photos,
        scan_workers=config.scan_workers,
        copy_workers=config.copy_workers,
        last_input_dir=config.input_dir,
        last_output_dir=config.output_dir,
    )


def ui_session_to_run_config(state: UiSessionState, *, overrides: Optional[Dict[str, Any]] = None) -> RunConfig:
    """Build RunConfig from saved UI state plus optional explicit form overrides."""
    data = dict(overrides or {})
    input_dir = data.pop("input_dir", state.last_input_dir)
    if not input_dir:
        raise ValueError("input_dir is required to build RunConfig from UI session state")
    output_dir = data.pop("output_dir", state.last_output_dir)
    data.setdefault("profile", state.selected_profile)
    data.setdefault("mode", state.selected_mode)
    data.setdefault("language", state.language)
    data.setdefault("use_gpu", state.use_gpu)
    data.setdefault("auto_cpu_fallback", state.auto_cpu_fallback)
    extra_overrides = dict(data.pop("overrides", {}) or {})
    extra_overrides.setdefault("photo_assignment", state.photo_assignment)
    extra_overrides.setdefault("copy_group_photos", state.copy_group_photos)
    extra_overrides.setdefault("scan_workers", state.scan_workers)
    extra_overrides.setdefault("copy_workers", state.copy_workers)
    data["overrides"] = extra_overrides

    # Lazy import avoids a module-level cycle: core.api imports this module for
    # public re-exports, and this helper only needs create_run_config on demand.
    from .api import create_run_config

    return create_run_config(input_dir=input_dir, output_dir=output_dir, **data)


__all__ = [
    "UI_SESSION_SCHEMA_VERSION",
    "UI_SESSION_DEFAULTS",
    "UiRecentProject",
    "UiSessionState",
    "default_ui_state_path",
    "default_ui_session_state",
    "ui_recent_project_from_dict",
    "ui_session_state_from_dict",
    "load_ui_session_state",
    "save_ui_session_state",
    "update_ui_session_state",
    "remember_recent_project",
    "prune_recent_projects",
    "config_to_ui_session_state",
    "ui_session_to_run_config",
]
