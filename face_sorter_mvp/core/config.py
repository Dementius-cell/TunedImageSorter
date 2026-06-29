# -*- coding: utf-8 -*-
"""Public configuration and data contracts for Tuned Image Sorter.

Этап 021 / v62 keeps config/data contracts in this dedicated import-safe
module. Pipeline orchestration lives in ``core.pipeline``; heavy ML stage
implementations are still extracted in later stages.

Do not import heavy ML/image packages here.
"""
from __future__ import annotations

from .contracts import (
    FaceRecord,
    ImageRecord,
    NullProgressCallbacks,
    ProgressCallbacks,
    REVIEW_ACTIONS,
    ReviewDecision,
    RunConfig,
    RunResult,
    stages_for_mode,
)

__all__ = [
    "ImageRecord",
    "FaceRecord",
    "RunConfig",
    "RunResult",
    "ReviewDecision",
    "ProgressCallbacks",
    "NullProgressCallbacks",
    "REVIEW_ACTIONS",
    "stages_for_mode",
]
