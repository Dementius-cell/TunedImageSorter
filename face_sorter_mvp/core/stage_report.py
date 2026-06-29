# -*- coding: utf-8 -*-
"""Report stage facade for v58 / Этап 005-compatible facade."""
from __future__ import annotations

from typing import Any

from .legacy import get_legacy_core


def run_report_stage(*args: Any, **kwargs: Any) -> Any:
    return get_legacy_core("run_report_stage").run_report_stage(*args, **kwargs)


__all__ = ["run_report_stage"]
