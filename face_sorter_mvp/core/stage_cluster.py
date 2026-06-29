# -*- coding: utf-8 -*-
"""Cluster stage facade for v58 / Этап 005-compatible facade."""
from __future__ import annotations

from typing import Any

from .legacy import get_legacy_core


def run_cluster_stage(*args: Any, **kwargs: Any) -> Any:
    return get_legacy_core("run_cluster_stage").run_cluster_stage(*args, **kwargs)


__all__ = ["run_cluster_stage"]
