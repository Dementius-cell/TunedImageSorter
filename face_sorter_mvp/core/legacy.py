# -*- coding: utf-8 -*-
"""Internal resolver for legacy implementation functions.

v62 / Этап 021 keeps heavy recognition and clustering implementations in
``face_sorter_mvp.py`` while the stage dispatch layer moves into dedicated
``core.stage_*`` modules.  This helper avoids importing a second copy of the
legacy script when running ``python face_sorter_mvp.py`` in script mode.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional


def get_legacy_core(required_attr: Optional[str] = None) -> Any:
    """Return the legacy implementation module.

    In legacy script mode the implementation module is ``__main__``.  In
    package mode it is ``face_sorter_mvp.face_sorter_mvp``.  ``required_attr``
    lets callers prefer ``__main__`` only when it already contains the needed
    implementation function.
    """
    main_mod = sys.modules.get("__main__")
    main_file = getattr(main_mod, "__file__", None)
    if main_file and Path(main_file).name == "face_sorter_mvp.py":
        if required_attr is None or hasattr(main_mod, required_attr):
            return main_mod

    try:  # package mode
        from .. import face_sorter_mvp as legacy
    except ImportError:  # script-folder mode
        import face_sorter_mvp as legacy  # type: ignore
    return legacy


__all__ = ["get_legacy_core"]
