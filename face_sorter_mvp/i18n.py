# -*- coding: utf-8 -*-
"""Import-safe i18n facade.

Этап 021 / v62 keeps a stable module for translation helpers.  The message
catalog and active language state remain in ``face_sorter_mvp.py`` for now to
avoid a risky bulk move of CLI text.
"""
from __future__ import annotations

from typing import Any


def _legacy_core() -> Any:
    try:
        from . import face_sorter_mvp as legacy
    except ImportError:
        import face_sorter_mvp as legacy  # type: ignore
    return legacy


def detect_system_language() -> str:
    return _legacy_core().detect_system_language()


def set_language(lang: str = "auto") -> str:
    return _legacy_core().set_language(lang)


def get_language() -> str:
    return str(getattr(_legacy_core(), "LANG", "en"))


def tr(key: str, **kwargs: Any) -> str:
    return _legacy_core().tr(key, **kwargs)


def lang_text(ru: str, en: str) -> str:
    return _legacy_core().lang_text(ru, en)


__all__ = ["detect_system_language", "set_language", "get_language", "tr", "lang_text"]
