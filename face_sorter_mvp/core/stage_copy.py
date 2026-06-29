# -*- coding: utf-8 -*-
"""Copy stage facade for v58 / Этап 005-compatible facade."""
from __future__ import annotations

from typing import Any

from .legacy import get_legacy_core


def run_copy_stage(*args: Any, **kwargs: Any) -> Any:
    return get_legacy_core("run_copy_stage").run_copy_stage(*args, **kwargs)


__all__ = ["run_copy_stage"]
