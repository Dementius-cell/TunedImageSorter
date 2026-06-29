# -*- coding: utf-8 -*-
"""Run the optional PySide6 UI skeleton with ``python -m face_sorter_mvp.ui``."""
from __future__ import annotations

import multiprocessing
from typing import Optional, Sequence


def main(argv: Optional[Sequence[str]] = None) -> int:
    from .main_window import main as ui_main

    return int(ui_main(list(argv) if argv is not None else None))


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
