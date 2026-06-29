#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Console entry point for Tuned Image Sorter v69.6.

Kept separate from the backend facade so future Windows UI code can import the
core without pulling in the CLI/wizard entry point. The legacy command
``python face_sorter_mvp.py`` remains supported.
"""
from __future__ import annotations

import multiprocessing

from typing import Optional, Sequence

try:  # package mode: python -m face_sorter_mvp.cli
    from .face_sorter_mvp import main as _main
except ImportError:  # script-folder mode: python cli.py
    from face_sorter_mvp import main as _main  # type: ignore


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the existing console application."""
    return _main(argv)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
