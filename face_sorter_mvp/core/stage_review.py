# -*- coding: utf-8 -*-
"""Review/apply-names stage facades for v58 / Этап 005-compatible facade."""
from __future__ import annotations

from typing import Any

from .legacy import get_legacy_core


def run_review_clusters_stage(*args: Any, **kwargs: Any) -> Any:
    return get_legacy_core("run_review_clusters_stage").run_review_clusters_stage(*args, **kwargs)


def run_apply_names_stage(*args: Any, **kwargs: Any) -> Any:
    return get_legacy_core("run_apply_names_stage").run_apply_names_stage(*args, **kwargs)


__all__ = ["run_review_clusters_stage", "run_apply_names_stage"]
