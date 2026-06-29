# -*- coding: utf-8 -*-
"""Stable constants for Tuned Image Sorter.

This module is intentionally lightweight and import-safe.  It contains values
that are useful to CLI, backend, future UI code, and project-state helpers.
Heavy ML/image packages must not be imported here.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff", ".heic", ".heif"
}
WINDOWS_FORBIDDEN_CHARS = r'<>:"/\\|?*'

KNOWN_MODELS = ["buffalo_l", "buffalo_s", "buffalo_m", "buffalo_sc", "antelopev2"]
DEFAULT_MODEL = "buffalo_l"
PROJECT_FILENAME = "project.json"
LEGACY_RUN_STATE_FILENAME = ".face_sorter_run.json"
RUN_STATE_FILENAME = PROJECT_FILENAME
PROJECT_DIRS = ("database", "reports", "people", "review", "final", "logs", "bug_reports")
RESULT_FOLDER_RE = re.compile(r"^result \d{2}-\d{2} \d{2}\.\d{2}\.\d{4}(?:_\d+)?$")

SCRIPT_VERSION = "v69.6"
SCRIPT_DIR = Path(__file__).resolve().parents[1]
ENV_STATE_FILE = SCRIPT_DIR / "face_sorter_mvp_env_state.json"
APP_LOG_FILE = SCRIPT_DIR / "face_sorter_mvp.log"
BUG_REPORTS_DIR = SCRIPT_DIR / "bug_reports"
PROBLEM_FILES_NAME = "problem_files.csv"
DIAGNOSTICS_DIR_NAME = "diagnostics"

DEFAULT_PROFILE: Dict[str, Any] = {
    "mode": "all",
    "model": "buffalo_l",
    "gpu": False,
    "det_size": 640,
    "max_side": 1800,
    "upscale_small_to": 640,
    "rescan": True,
    "commit_every": 50,
    "progress_every": 500,
    "algo": "hdbscan",
    "min_cluster_size": 5,
    "min_samples": None,
    "cluster_selection_method": "eom",
    "dbscan_eps": 0.55,
    "min_det_score": 0.30,
    "min_face_size": 12,
    "photo_assignment": "best-face",
    "copy_group_photos": False,
    "filename_fallback": True,
    "filename_max_distance": 3,
    "clean_folders": True,
    "clean_final": False,
    "overwrite_names": False,
    "report_faces_per_cluster": 36,
    "dry_run": False,
    "verbose": False,
    "file_timeout": "auto",
    "disable_scan_worker": False,
    "scan_workers": "auto",
    "copy_workers": "auto",
    "reuse_problem_cache": True,
    "duplicate_check": "exact",
    "duplicate_policy": "scan-one-copy-all",
    "strict_image_extensions": False,
}

PIPELINE_STAGES = ("scan", "cluster", "assign", "copy", "report", "review-clusters", "apply-names", "bug-report")
MODE_STAGE_MAP = {
    "all": ("scan", "cluster", "assign", "copy", "report"),
    "scan": ("scan",),
    # Re-clustering usually needs fresh assignments and reports, but must not copy files.
    "cluster": ("cluster", "assign", "report"),
    "assign": ("assign",),
    "copy": ("copy",),
    "report": ("report",),
    "review-clusters": ("review-clusters",),
    "apply-names": ("apply-names",),
    "bug-report": ("bug-report",),
    "make-bug-report": ("bug-report",),
    "support-bundle": ("bug-report",),
}
