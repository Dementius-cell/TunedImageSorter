# -*- coding: utf-8 -*-
"""Minimal PySide6 UI skeleton for Tuned Image Sorter.

v69.6 / Этап 055 keeps this package as an optional Windows/PySide6 GUI entry
point.  Importing this package must remain safe when PySide6 is not installed;
Qt is imported lazily only when ``launch_ui()`` is called.
"""
from __future__ import annotations

from .main_window import UI_SKELETON_VERSION, is_pyside6_available, launch_ui, main

__all__ = [
    "UI_SKELETON_VERSION",
    "is_pyside6_available",
    "launch_ui",
    "main",
]
