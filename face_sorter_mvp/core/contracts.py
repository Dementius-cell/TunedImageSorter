# -*- coding: utf-8 -*-
"""Import-safe data contracts shared by CLI, backend, and future UI."""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .constants import DEFAULT_PROFILE, MODE_STAGE_MAP, PIPELINE_STAGES


@dataclass(frozen=True)
class ImageRecord:
    """Immutable row-like object describing an input image stored in SQLite."""
    id: int
    path: str
    size: int
    mtime: float
    width: Optional[int]
    height: Optional[int]
    status: str
    error: Optional[str]


@dataclass(frozen=True)
class FaceRecord:
    """Immutable row-like object describing one detected face and its embedding."""
    id: int
    image_id: int
    image_path: str
    face_index: int
    det_score: float
    bbox: Tuple[int, int, int, int]
    embedding: Any
    crop_relpath: Optional[str]
    cluster_raw: Optional[int]
    cluster_key: Optional[str]


@dataclass(frozen=True)
class RunConfig:
    """Stable settings contract between CLI, future GUI and the processing core.

    CLI and the interactive wizard may still use argparse.Namespace internally for now,
    but they must be converted into RunConfig before the pipeline starts. Future UI code
    should build RunConfig directly and call run_pipeline(config).
    """

    input_dir: Optional[Path]
    output_dir: Optional[Path]
    project_dir: Optional[Path] = None
    mode: str = "all"
    profile: str = "normal"
    language: str = "auto"
    db_path: Optional[Path] = None
    names_path: Optional[Path] = None

    model: str = DEFAULT_PROFILE["model"]
    use_gpu: bool = False
    auto_cpu_fallback: bool = True
    det_size: int = DEFAULT_PROFILE["det_size"]
    max_side: int = DEFAULT_PROFILE["max_side"]
    upscale_small_to: int = DEFAULT_PROFILE["upscale_small_to"]
    min_det_score: float = DEFAULT_PROFILE["min_det_score"]
    min_face_size: int = DEFAULT_PROFILE["min_face_size"]

    rescan: bool = DEFAULT_PROFILE["rescan"]
    commit_every: int = DEFAULT_PROFILE["commit_every"]
    progress_every: int = DEFAULT_PROFILE["progress_every"]

    algorithm: str = DEFAULT_PROFILE["algo"]
    min_cluster_size: int = DEFAULT_PROFILE["min_cluster_size"]
    min_samples: Optional[int] = DEFAULT_PROFILE["min_samples"]
    cluster_selection_method: str = DEFAULT_PROFILE["cluster_selection_method"]
    dbscan_eps: float = DEFAULT_PROFILE["dbscan_eps"]

    photo_assignment: str = DEFAULT_PROFILE["photo_assignment"]
    copy_group_photos: bool = DEFAULT_PROFILE["copy_group_photos"]
    filename_fallback: bool = DEFAULT_PROFILE["filename_fallback"]
    filename_max_distance: int = DEFAULT_PROFILE["filename_max_distance"]

    clean_folders: bool = DEFAULT_PROFILE["clean_folders"]
    clean_final: bool = DEFAULT_PROFILE["clean_final"]
    overwrite_names: bool = DEFAULT_PROFILE["overwrite_names"]
    report_faces_per_cluster: int = DEFAULT_PROFILE["report_faces_per_cluster"]
    dry_run: bool = DEFAULT_PROFILE["dry_run"]
    verbose: bool = DEFAULT_PROFILE["verbose"]

    auto_install: bool = False
    auto_gpu_install: bool = False
    gpu_smoke_test: bool = False
    gpu_smoke_test_all: bool = False
    skip_gpu_smoke_test: bool = False
    force_env_check: bool = False
    make_bug_report: bool = False

    file_timeout: str = str(DEFAULT_PROFILE.get("file_timeout", "auto"))
    disable_scan_worker: bool = DEFAULT_PROFILE.get("disable_scan_worker", False)
    scan_workers: str = str(DEFAULT_PROFILE.get("scan_workers", "auto"))
    copy_workers: str = str(DEFAULT_PROFILE.get("copy_workers", "auto"))
    reuse_problem_cache: bool = DEFAULT_PROFILE.get("reuse_problem_cache", True)
    duplicate_check: str = DEFAULT_PROFILE.get("duplicate_check", "exact")
    duplicate_policy: str = DEFAULT_PROFILE.get("duplicate_policy", "scan-one-copy-all")
    strict_image_extensions: bool = DEFAULT_PROFILE.get("strict_image_extensions", False)

    resume_existing_output: bool = False
    gpu_allowed_models: Optional[List[str]] = None
    gpu_model_smoke_results: Optional[Dict[str, Any]] = None

    def to_namespace(self) -> argparse.Namespace:
        """Convert the stable config back to Namespace for the legacy core functions.

        This keeps CLI behavior compatible while moving the public contract to RunConfig.
        """
        data = {
            "input": str(self.input_dir) if self.input_dir else None,
            "output": str(self.output_dir) if self.output_dir else None,
            "project": str(self.project_dir) if self.project_dir else None,
            "mode": self.mode,
            "scan_profile": self.profile,
            "lang": self.language,
            "db": str(self.db_path) if self.db_path else None,
            "names": str(self.names_path) if self.names_path else None,
            "model": self.model,
            "gpu": self.use_gpu,
            "auto_cpu_fallback": self.auto_cpu_fallback,
            "no_auto_cpu_fallback": not self.auto_cpu_fallback,
            "det_size": self.det_size,
            "max_side": self.max_side,
            "upscale_small_to": self.upscale_small_to,
            "min_det_score": self.min_det_score,
            "min_face_size": self.min_face_size,
            "rescan": self.rescan,
            "commit_every": self.commit_every,
            "progress_every": self.progress_every,
            "algo": self.algorithm,
            "min_cluster_size": self.min_cluster_size,
            "min_samples": self.min_samples,
            "cluster_selection_method": self.cluster_selection_method,
            "dbscan_eps": self.dbscan_eps,
            "photo_assignment": self.photo_assignment,
            "copy_group_photos": self.copy_group_photos,
            "filename_fallback": self.filename_fallback,
            "filename_max_distance": self.filename_max_distance,
            "clean_folders": self.clean_folders,
            "clean_final": self.clean_final,
            "overwrite_names": self.overwrite_names,
            "report_faces_per_cluster": self.report_faces_per_cluster,
            "dry_run": self.dry_run,
            "verbose": self.verbose,
            "auto_install": self.auto_install,
            "auto_gpu_install": self.auto_gpu_install,
            "gpu_smoke_test": self.gpu_smoke_test,
            "gpu_smoke_test_all": self.gpu_smoke_test_all,
            "skip_gpu_smoke_test": self.skip_gpu_smoke_test,
            "force_env_check": self.force_env_check,
            "make_bug_report": self.make_bug_report,
            "file_timeout": self.file_timeout,
            "disable_scan_worker": self.disable_scan_worker,
            "scan_workers": self.scan_workers,
            "copy_workers": self.copy_workers,
            "reuse_problem_cache": self.reuse_problem_cache,
            "duplicate_check": self.duplicate_check,
            "duplicate_policy": self.duplicate_policy,
            "strict_image_extensions": self.strict_image_extensions,
            "resume_existing_output": self.resume_existing_output,
            "gpu_allowed_models": self.gpu_allowed_models,
            "gpu_model_smoke_results": self.gpu_model_smoke_results,
        }
        return argparse.Namespace(**data)

    def to_json_dict(self) -> Dict[str, Any]:
        data = self.to_namespace().__dict__.copy()
        data["input_dir"] = str(self.input_dir) if self.input_dir else None
        data["output_dir"] = str(self.output_dir) if self.output_dir else None
        data["project_dir"] = str(self.project_dir) if self.project_dir else None
        data["db_path"] = str(self.db_path) if self.db_path else None
        data["names_path"] = str(self.names_path) if self.names_path else None
        # Keep legacy aliases out of project-level JSON noise.
        data.pop("input", None)
        data.pop("output", None)
        data.pop("project", None)
        data.pop("db", None)
        data.pop("names", None)
        data.pop("algo", None)
        data.pop("gpu", None)
        return data

    def config_hash(self) -> str:
        """Stable hash of the normalized run configuration for resume checks."""
        data = self.to_json_dict().copy()
        # Runtime/diagnostic fields should not make an otherwise identical run incompatible.
        for key in ("gpu_model_smoke_results",):
            data.pop(key, None)
        blob = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode("utf-8", errors="replace")).hexdigest()[:16]


@dataclass(frozen=True)
class RunResult:
    """Pipeline result returned to CLI/GUI callers after run_pipeline()."""
    output_dir: Optional[Path]
    db_path: Optional[Path]
    status: str = "done"
    bug_report_path: Optional[Path] = None
    stages_completed: Tuple[str, ...] = ()


REVIEW_ACTIONS = {"keep", "merge", "review", "ignore"}


@dataclass(frozen=True)
class ReviewDecision:
    """User review decision for one face cluster.

    This is the stable review data model for future UI code. names.csv stores
    these fields and apply-names consumes them without requiring another scan.
    """

    cluster_key: str
    name: str = ""
    action: str = "keep"
    merge_into: str = ""
    confidence: Optional[float] = None
    notes: str = ""

    def normalized_action(self) -> str:
        action = (self.action or "keep").strip().lower()
        return action if action in REVIEW_ACTIONS else "review"


def stages_for_mode(mode: str) -> Tuple[str, ...]:
    """Return independent pipeline stages for a public mode.

    Future GUI buttons should call run_pipeline() with a RunConfig whose mode maps to
    these same stages. Keeping this mapping explicit prevents accidental coupling such
    as "cluster" secretly copying files.
    """
    if mode not in MODE_STAGE_MAP:
        raise ValueError(f"Unsupported pipeline mode: {mode}")
    return MODE_STAGE_MAP[mode]


class ProgressCallbacks:
    """UI-neutral progress contract for CLI, future GUI and packaged .exe.

    The processing core calls these hooks for stages, progress, warnings and errors.
    A console implementation prints text. A future GUI implementation should update
    labels/progress bars and may set ``handles_console_output=True`` to suppress the
    legacy direct console messages emitted by helper functions.
    """

    handles_console_output: bool = False

    def on_stage(self, stage: str, message: str = "", **data: Any) -> None:
        pass

    def on_progress(self, stage: str, done: int, total: Optional[int] = None, **data: Any) -> None:
        pass

    def on_warning(self, stage: str, message: str, **data: Any) -> None:
        pass

    def on_error(self, stage: str, message: str, **data: Any) -> None:
        pass

    def on_info(self, stage: str, message: str, **data: Any) -> None:
        pass


class NullProgressCallbacks(ProgressCallbacks):
    """No-op callbacks for tests or non-interactive embedding."""

    handles_console_output = False
