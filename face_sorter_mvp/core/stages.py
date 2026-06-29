# -*- coding: utf-8 -*-
"""Stage dispatch facade for Tuned Image Sorter.

v62 / Этап 021 keeps the stage layer split into dedicated modules:
``stage_scan``, ``stage_cluster``, ``stage_assign``, ``stage_copy``,
``stage_report`` and ``stage_review``.  These modules are intentionally thin
facades for now: the heavy recognition/clustering/copy implementations remain
in the legacy algorithm module until this split is validated on real photo
sets.  Normal UI code should still call ``core.pipeline.run_pipeline()``.
"""
from __future__ import annotations

from .stage_assign import run_assign_stage
from .stage_cluster import run_cluster_stage
from .stage_copy import run_copy_stage
from .stage_report import run_report_stage
from .stage_review import run_apply_names_stage, run_review_clusters_stage
from .stage_scan import run_scan_stage

__all__ = [
    "run_scan_stage",
    "run_cluster_stage",
    "run_assign_stage",
    "run_copy_stage",
    "run_report_stage",
    "run_review_clusters_stage",
    "run_apply_names_stage",
]
