#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Package entry point: python -m face_sorter_mvp."""
from __future__ import annotations

import multiprocessing
from typing import Optional, Sequence


def main(argv: Optional[Sequence[str]] = None) -> int:
    from .cli import main as cli_main

    return int(cli_main(list(argv) if argv is not None else None))


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
