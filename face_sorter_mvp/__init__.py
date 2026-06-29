# -*- coding: utf-8 -*-
"""Tuned Image Sorter v69.6 public backend API.

Recommended imports for future UI code:

    from face_sorter_mvp import RunConfig, ProgressCallbacks, run_pipeline
    from face_sorter_mvp.backend import backend_capabilities
"""
from __future__ import annotations

from .backend import *  # noqa: F401,F403
from .backend import __all__ as _backend_all

from .core import SCRIPT_VERSION as __version__
__all__ = list(_backend_all) + ["__version__"]
