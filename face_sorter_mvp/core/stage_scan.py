# -*- coding: utf-8 -*-
"""Scan stage facade.

v58 / Этап 005-compatible facade keeps stage dispatch into dedicated modules.  The actual image
scan/face detection implementation is still the legacy implementation for
stability and will be moved only after real-photo tests confirm this stage
split.
"""
from __future__ import annotations

from typing import Any

from .legacy import get_legacy_core


def run_scan_stage(*args: Any, **kwargs: Any) -> Any:
    return get_legacy_core("run_scan_stage").run_scan_stage(*args, **kwargs)


__all__ = ["run_scan_stage"]
