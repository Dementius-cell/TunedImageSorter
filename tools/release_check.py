#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run Tuned Image Sorter release-candidate checks.

This script is intentionally lightweight.  It does not run ML, scan photos,
copy files, build PyInstaller output or modify project folders.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from face_sorter_mvp.backend import run_release_check  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Tuned Image Sorter release-candidate checks.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON result.")
    parser.add_argument("--no-self-test", action="store_true", help="Skip run_backend_self_test() to avoid recursion in embedded checks.")
    args = parser.parse_args()

    result = run_release_check(project_root=ROOT, include_self_test=not args.no_self_test)
    if args.json:
        # ASCII-safe JSON avoids Windows redirection/codepage corruption such
        # as "Этап 021" becoming mojibake after ``> release_check.json``.
        # Tools reading JSON decode the escapes back to Unicode normally.
        sys.stdout.write(json.dumps(result.to_dict(), ensure_ascii=True, indent=2))
        sys.stdout.write("\n")
        return 0 if result.ok else 1

    print(f"Tuned Image Sorter release check: {'OK' if result.ok else 'ERROR'}")
    print(f"version={result.version} refactor_stage={result.refactor_stage} ui_api_version={result.ui_api_version}")
    print(f"checks={len(result.checks)} warnings={len(result.warnings)} errors={len(result.errors)} duration_ms={result.duration_ms}")
    for check in result.checks:
        marker = "OK" if check.ok else "ERROR"
        if check.severity == "warning":
            marker = "WARN"
        print(f"[{marker}] {check.name}: {check.message}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
