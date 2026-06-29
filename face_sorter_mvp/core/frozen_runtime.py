# -*- coding: utf-8 -*-
"""Import-safe frozen/portable runtime helpers.

v69.6 / Этап 055 keeps these helpers as the first packaging-facing runtime layer.
The functions are deliberately lightweight: they do not import PySide6, ML
packages or ONNX Runtime.  They only describe whether the current process is a
normal source-tree run or a PyInstaller frozen executable run.
"""
from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .constants import SCRIPT_DIR, SCRIPT_VERSION

FROZEN_RUNTIME_SCHEMA_VERSION = 1
FROZEN_RUNTIME_STAGE = "Этап 055"


@dataclass(frozen=True)
class FrozenRuntimeInfo:
    """Serializable description of source/frozen runtime locations."""

    version: str
    refactor_stage: str
    schema_version: int
    is_frozen: bool
    executable: str
    argv0: str
    app_base_dir: str
    bundle_internal_dir: str
    meipass_dir: str
    source_project_root: str
    cwd: str
    platform: str
    notes: tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def is_frozen_app() -> bool:
    """Return True when running from a PyInstaller-style frozen executable."""
    return bool(getattr(sys, "frozen", False))


def _safe_path(value: Optional[str | os.PathLike[str]]) -> str:
    if not value:
        return ""
    try:
        return str(Path(value).expanduser().resolve())
    except Exception:
        return str(value)


def app_base_dir() -> Path:
    """Return the portable app folder in frozen mode, or source root in source mode."""
    if is_frozen_app():
        return Path(sys.executable).resolve().parent
    return SCRIPT_DIR.parent.resolve()


def bundle_internal_dir() -> Path:
    """Return the PyInstaller _internal folder when it is expected to exist."""
    base = app_base_dir()
    candidate = base / "_internal"
    return candidate if candidate.exists() else base


def meipass_dir() -> str:
    """Return PyInstaller sys._MEIPASS when present, otherwise an empty string."""
    return _safe_path(getattr(sys, "_MEIPASS", ""))


def source_project_root() -> Path:
    """Return the unpacked source project root used by development checks."""
    return SCRIPT_DIR.parent.resolve()


def frozen_runtime_info() -> FrozenRuntimeInfo:
    """Return import-safe runtime location diagnostics for UI/release checks."""
    frozen = is_frozen_app()
    internal = bundle_internal_dir()
    notes = [
        "Source mode remains the development baseline; frozen mode is a build artifact produced from source.",
        "Portable builds do not auto-install Python packages from the executable; dependencies should be bundled at build time.",
    ]
    if frozen:
        notes.append("Running as a frozen executable. Use app_base_dir/_internal for portable bundle diagnostics.")
    else:
        notes.append("Running from source tree. PyInstaller output is expected under dist/windows after a Windows build.")
    return FrozenRuntimeInfo(
        version=SCRIPT_VERSION,
        refactor_stage=FROZEN_RUNTIME_STAGE,
        schema_version=FROZEN_RUNTIME_SCHEMA_VERSION,
        is_frozen=frozen,
        executable=_safe_path(sys.executable),
        argv0=_safe_path(sys.argv[0]) if sys.argv else "",
        app_base_dir=str(app_base_dir()),
        bundle_internal_dir=str(internal),
        meipass_dir=meipass_dir(),
        source_project_root=str(source_project_root()),
        cwd=_safe_path(Path.cwd()),
        platform=sys.platform,
        notes=tuple(notes),
    )


def frozen_runtime_summary() -> Dict[str, Any]:
    """Return a compact JSON-friendly summary for bug reports/release checks."""
    return frozen_runtime_info().to_dict()


__all__ = [
    "FROZEN_RUNTIME_SCHEMA_VERSION",
    "FROZEN_RUNTIME_STAGE",
    "FrozenRuntimeInfo",
    "is_frozen_app",
    "app_base_dir",
    "bundle_internal_dir",
    "meipass_dir",
    "source_project_root",
    "frozen_runtime_info",
    "frozen_runtime_summary",
]
