#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke-test the Windows packaging/release layer without running ML."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from face_sorter_mvp import backend_capabilities, run_backend_self_test, verify_ui_contract  # noqa: E402
from face_sorter_mvp.backend import frozen_runtime_info, run_release_check, verify_friend_ready_source_layout, verify_windows_packaging  # noqa: E402


def main() -> int:
    caps = backend_capabilities()
    contract = verify_ui_contract()
    self_test = run_backend_self_test()
    packaging = verify_windows_packaging(ROOT)
    friend_ready = verify_friend_ready_source_layout(ROOT)
    release = run_release_check(project_root=ROOT)
    payload = {
        "version": caps.get("version"),
        "refactor_stage": caps.get("refactor_stage"),
        "ui_api_version": caps.get("ui_api_version"),
        "supports_windows_packaging": caps.get("supports_windows_packaging"),
        "supports_ui_polish": caps.get("supports_ui_polish"),
        "supports_release_check": caps.get("supports_release_check"),
        "supports_ui_usability_pass": caps.get("supports_ui_usability_pass"),
        "supports_windows_onefolder_build_profiles": caps.get("supports_windows_onefolder_build_profiles"),
        "frozen_runtime": frozen_runtime_info().to_dict(),
        "contract_ok": contract.ok,
        "self_test_ok": self_test.ok,
        "self_test_checks": len(self_test.checks),
        "packaging_ok": packaging.ok,
        "packaging_checked_files": list(packaging.checked_files),
        "packaging_missing_files": list(packaging.missing_files),
        "friend_ready_source_ok": friend_ready.ok,
        "friend_ready_checked_files": list(friend_ready.checked_files),
        "friend_ready_missing_files": list(friend_ready.missing_files),
        "release_check_ok": release.ok,
        "release_check_warnings": list(release.warnings),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not contract.ok:
        print("verify_ui_contract() failed", file=sys.stderr)
        return 2
    if not self_test.ok:
        print("run_backend_self_test() failed", file=sys.stderr)
        return 3
    if not packaging.ok:
        print("verify_windows_packaging() failed", file=sys.stderr)
        return 4
    if not friend_ready.ok:
        print("verify_friend_ready_source_layout() failed", file=sys.stderr)
        return 6
    if not release.ok:
        print("run_release_check() failed", file=sys.stderr)
        return 5
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
