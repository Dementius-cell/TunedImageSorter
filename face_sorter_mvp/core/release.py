# -*- coding: utf-8 -*-
"""Import-safe release-candidate checks for Tuned Image Sorter.

v69.6 / Этап 055 keeps the confirmed Windows CPU/GPU portable packaging baseline and adds pre-release polish docs/verification. The checks here are deliberately non-destructive: they do not
run ML, do not scan photos, do not copy files and do not mutate project folders.
They collect the compatibility checks needed before a Windows exe / RC pass.
"""
from __future__ import annotations

import datetime as dt
import importlib
import json
import tempfile
import time
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .constants import SCRIPT_DIR, SCRIPT_VERSION
from .api import ui_backend_api
from .contract import UI_CONTRACT_API_VERSION, UI_CONTRACT_STAGE, verify_ui_contract
from .session import load_ui_session_state, save_ui_session_state, ui_session_state_from_dict
from .ui_polish import ui_polish_snapshot
from .ui_usability import ui_usability_snapshot
from .windows_packaging import FRIEND_READY_DOC_TOKEN_CHECKS, FRIEND_READY_TOP_LEVEL_FILES, verify_friend_ready_source_layout, verify_windows_packaging
from .frozen_runtime import is_frozen_app, app_base_dir, bundle_internal_dir, frozen_runtime_summary

RELEASE_CHECK_SCHEMA_VERSION = 1
RELEASE_CHECK_STAGE = "Этап 055"


@dataclass(frozen=True)
class ReleaseCheckItem:
    """One release-candidate check item."""

    name: str
    ok: bool
    severity: str = "error"  # error | warning | info
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReleaseCheckResult:
    """Serializable release-candidate check result."""

    ok: bool
    version: str
    refactor_stage: str
    ui_api_version: int
    schema_version: int
    created_at: str
    duration_ms: int
    checks: Tuple[ReleaseCheckItem, ...]
    errors: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["checks"] = [check.to_dict() for check in self.checks]
        return data


def _json_safe(value: Any) -> Any:
    """Best-effort conversion for JSON summaries used by release/bug reports."""
    if hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
        return _json_safe(value.to_dict())
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _root_from_here() -> Path:
    # SCRIPT_DIR is <root>/face_sorter_mvp.
    return SCRIPT_DIR.parent


def _ok(name: str, message: str = "", **details: Any) -> ReleaseCheckItem:
    return ReleaseCheckItem(name=name, ok=True, severity="info", message=message, details=_json_safe(details))


def _warn(name: str, message: str = "", **details: Any) -> ReleaseCheckItem:
    return ReleaseCheckItem(name=name, ok=True, severity="warning", message=message, details=_json_safe(details))


def _fail(name: str, message: str, **details: Any) -> ReleaseCheckItem:
    return ReleaseCheckItem(name=name, ok=False, severity="error", message=message, details=_json_safe(details))


def _module_import_check(module_name: str) -> Tuple[bool, str]:
    try:
        importlib.import_module(module_name)
        return True, "import ok"
    except Exception as exc:  # pragma: no cover - diagnostics path
        return False, f"{type(exc).__name__}: {exc}"


def _session_compatibility_check() -> ReleaseCheckItem:
    """Verify that older/newer UI session JSON shapes load and save safely."""
    try:
        old_shape = {
            "schema_version": 1,
            "app_version": "v50",
            "language": "ru",
            "selected_profile": "normal",
            "selected_mode": "all",
            "use_gpu": False,
            "last_input_dir": "",
            "last_output_dir": "",
            "recent_projects": [],
        }
        state = ui_session_state_from_dict(old_shape)
        if state.ui_theme != "system" or state.ui_density != "comfortable":
            raise AssertionError("v1 session compatibility did not fill polish defaults")
        with tempfile.TemporaryDirectory(prefix="face_sorter_release_session_") as tmp:
            path = Path(tmp) / "ui_session.json"
            saved = save_ui_session_state(state, path)
            loaded = load_ui_session_state(saved)
        if loaded.selected_profile != "normal" or loaded.selected_mode != "all":
            raise AssertionError("session round-trip changed selected profile/mode")
        return _ok(
            "session_compatibility",
            "UI session v1/v2 compatibility and polish defaults are preserved.",
            loaded=loaded.to_dict(),
        )
    except Exception as exc:
        return _fail("session_compatibility", f"{type(exc).__name__}: {exc}")


def run_release_check(*, project_root: Optional[str | Path] = None, include_self_test: bool = True) -> ReleaseCheckResult:
    """Run the non-destructive release-candidate checks.

    Parameters
    ----------
    project_root:
        Optional root folder to verify docs/tools/assets.  Defaults to the
        folder one level above the package.
    include_self_test:
        True for standalone release checks.  ``run_backend_self_test()`` calls
        this function with False to avoid recursive self-test execution.
    """
    started = time.perf_counter()
    root = Path(project_root).expanduser().resolve() if project_root else _root_from_here().resolve()
    checks: List[ReleaseCheckItem] = []
    api = ui_backend_api()

    try:
        if SCRIPT_VERSION != "v69.6":
            raise AssertionError(f"SCRIPT_VERSION is {SCRIPT_VERSION!r}, expected 'v69.6'")
        if api.refactor_stage != RELEASE_CHECK_STAGE:
            raise AssertionError(f"refactor_stage is {api.refactor_stage!r}, expected {RELEASE_CHECK_STAGE!r}")
        if api.api_version != UI_CONTRACT_API_VERSION or api.api_version != 21:
            raise AssertionError(f"ui_api_version is {api.api_version!r}, expected 21")
        checks.append(_ok(
            "version_capabilities",
            "Version, refactor stage and UI API version are aligned for v69.6 / Этап 055 release bundle / checksums / final public handoff.",
            api=api.to_dict(),
        ))
    except Exception as exc:
        checks.append(_fail("version_capabilities", f"{type(exc).__name__}: {exc}", api=getattr(api, "to_dict", lambda: {})()))

    try:
        contract = verify_ui_contract()
        if not contract.ok:
            raise AssertionError(contract.to_dict())
        checks.append(_ok("ui_contract", "Frozen backend/UI contract verifies successfully.", verification=contract.to_dict()))
    except Exception as exc:
        checks.append(_fail("ui_contract", f"{type(exc).__name__}: {exc}"))

    if include_self_test:
        try:
            from .self_test import run_backend_self_test

            result = run_backend_self_test()
            if not result.ok:
                raise AssertionError(result.to_dict())
            checks.append(_ok(
                "backend_self_test",
                "Import-safe backend self-test passes without ML.",
                checks=len(result.checks),
                duration_ms=result.duration_ms,
            ))
        except Exception as exc:
            checks.append(_fail("backend_self_test", f"{type(exc).__name__}: {exc}"))
    else:
        checks.append(_ok("backend_self_test", "Skipped inside backend self-test to avoid recursion.", skipped=True))

    try:
        from .preflight import runtime_preflight, runtime_preflight_summary

        summary = runtime_preflight_summary(run_gpu_smoke_test=False)
        if summary.get("errors", 0):
            checks.append(_warn("runtime_preflight", "Runtime preflight reports environment errors; package may still be import-safe.", summary=summary))
        else:
            checks.append(_ok("runtime_preflight", "Runtime preflight summary collected without GPU smoke-test.", summary=summary))
    except Exception as exc:
        checks.append(_fail("runtime_preflight", f"{type(exc).__name__}: {exc}"))

    try:
        if is_frozen_app():
            checks.append(_ok(
                "windows_packaging",
                "Frozen executable runtime detected; source packaging scripts/specs are not required inside the portable bundle.",
                frozen_runtime=frozen_runtime_summary(),
            ))
        else:
            packaging = verify_windows_packaging(root)
            if not packaging.ok:
                raise AssertionError(packaging.to_dict())
            checks.append(_ok("windows_packaging", "Windows packaging layer files are present and verified.", verification=packaging.to_dict()))
    except Exception as exc:
        checks.append(_fail("windows_packaging", f"{type(exc).__name__}: {exc}"))

    try:
        if is_frozen_app():
            checks.append(_ok("cpu_packaging_hygiene", "Frozen runtime: CPU packaging hygiene source-token check is skipped.", skipped=True))
        else:
            build_script = root / "tools" / "windows_packaging" / "build_windows_gui.ps1"
            provider_script = root / "tools" / "windows_packaging" / "check_onnxruntime_provider.py"
            build_text = build_script.read_text(encoding="utf-8", errors="replace")
            provider_text = provider_script.read_text(encoding="utf-8", errors="replace")
            required = (
                "Invoke-CpuRequirementsInstall",
                "onnxruntime-gpu onnxruntime",
                "--require-no-cuda",
                "--require-no-gpu-distribution",
                "Assert-FrozenCpuProvider",
                "onnxruntime_providers_cuda.dll",
                "onnxruntime_providers_tensorrt.dll",
            )
            missing = [token for token in required if token not in build_text and token not in provider_text]
            if missing:
                raise AssertionError({"missing": missing, "build_script": str(build_script)})
            checks.append(_ok("cpu_packaging_hygiene", "CPU packaging removes stale GPU/CPU ORT wheels, checks CPU-only providers and rejects GPU provider DLLs in the CPU portable build.", tokens=list(required)))
    except Exception as exc:
        checks.append(_fail("cpu_packaging_hygiene", f"{type(exc).__name__}: {exc}"))

    try:
        if is_frozen_app():
            package_root = app_base_dir()
            missing = [rel for rel in FRIEND_READY_TOP_LEVEL_FILES if not (package_root / rel).exists()]
            token_errors = []
            for rel, tokens in FRIEND_READY_DOC_TOKEN_CHECKS.items():
                path = package_root / rel
                if not path.exists():
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
                for token in tokens:
                    if token not in text:
                        token_errors.append(f"{rel} must mention {token!r}")

            for rel in ("package_identity_check.json", "package_identity_check.txt"):
                if not (package_root / rel).exists():
                    missing.append(rel)

            manifest_path = package_root / "portable_manifest.json"
            if not manifest_path.exists():
                missing.append("portable_manifest.json")
            else:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
                name_lower = package_root.name.lower()
                expected_profile = "gpu-lite" if ("gpu_lite" in name_lower or "gpu-lite" in name_lower) else ("gpu" if "gpu" in name_lower else "cpu")
                expected = {
                    "version": SCRIPT_VERSION,
                    "refactor_stage": RELEASE_CHECK_STAGE,
                    "ui_api_version": 21,
                    "package_kind": "friend-ready-portable",
                    "profile": expected_profile,
                }
                for key, value in expected.items():
                    if manifest.get(key) != value:
                        token_errors.append(f"portable_manifest.json field {key!r} must be {value!r}, got {manifest.get(key)!r}")
                diagnostics = manifest.get("diagnostics") if isinstance(manifest.get("diagnostics"), dict) else {}
                if "TunedImageSorter_CLI.exe --release-check" not in str(diagnostics.get("release_check", "")):
                    token_errors.append("portable_manifest.json must list release-check diagnostics")

            if missing or token_errors:
                raise AssertionError({"package_root": str(package_root), "missing": missing, "errors": token_errors})
            checks.append(_ok("friend_ready_package_docs", "Friend-ready top-level docs, portable_manifest.json and package identity reports are present next to the frozen EXEs.", package_root=str(package_root), files=list(FRIEND_READY_TOP_LEVEL_FILES) + ["portable_manifest.json", "package_identity_check.json", "package_identity_check.txt"]))
        else:
            friend_ready = verify_friend_ready_source_layout(root)
            if not friend_ready.ok:
                raise AssertionError(friend_ready.to_dict())
            checks.append(_ok("friend_ready_source_layout", "Friend-ready top-level START_HERE/README/VERSION files and verification command are present.", verification=friend_ready.to_dict()))
    except Exception as exc:
        checks.append(_fail("friend_ready_layout", f"{type(exc).__name__}: {exc}"))


    try:
        from .diagnostics_help import diagnostics_help_text

        help_text = diagnostics_help_text("en")
        required = ("--runtime-preflight", "--runtime-preflight --gpu", "--gpu-lite-runtime-status", "--gpu-lite-runtime-setup --yes", "--release-check", "--scan-probe", "--result-health", "--support-bundle")
        missing = [token for token in required if token not in help_text]
        if missing:
            raise AssertionError({"missing": missing, "text": help_text})
        checks.append(_ok("diagnostics_command_center", "Diagnostics command-center help lists the main CLI troubleshooting commands.", lines=len(help_text.splitlines())))
    except Exception as exc:
        checks.append(_fail("diagnostics_command_center", f"{type(exc).__name__}: {exc}"))

    try:
        from .result_health import build_result_health_summary

        with tempfile.TemporaryDirectory(prefix="face_sorter_result_health_") as tmp:
            output = Path(tmp) / "result"
            reports = output / "reports"
            reports.mkdir(parents=True)
            (output / "project.json").write_text("{}", encoding="utf-8")
            for name in ("summary.csv", "assignments.csv", "review_clusters.csv"):
                (reports / name).write_text("ok\n", encoding="utf-8")
            result_health = build_result_health_summary(output, write_reports=True)
        if not result_health.ok:
            raise AssertionError(result_health.to_dict())
        checks.append(_ok("result_health_check", "Diagnostics-only result-health check validates an existing output folder and writes additive reports/result_health_check files.", verification=result_health.to_dict()))
    except Exception as exc:
        checks.append(_fail("result_health_check", f"{type(exc).__name__}: {exc}"))

    try:
        if is_frozen_app():
            from ..ui import UI_SKELETON_VERSION

            checks.append(_ok("gui_diagnostics_support_panel", "GUI diagnostics/support panel is included in the frozen UI skeleton; source token check is skipped for PyInstaller bytecode builds.", ui_skeleton_version=UI_SKELETON_VERSION))
        else:
            ui_file = root / "face_sorter_mvp" / "ui" / "main_window.py"
            ui_text_raw = ui_file.read_text(encoding="utf-8")
            required = (
                "_build_diagnostics_support_tab",
                "run_result_health_from_ui",
                "create_support_bundle_from_ui",
                "copy_short_diagnostic_summary",
                "build_result_health_summary",
                "format_result_health_text",
            )
            missing = [token for token in required if token not in ui_text_raw]
            if missing:
                raise AssertionError({"missing": missing, "file": str(ui_file)})
            checks.append(_ok("gui_diagnostics_support_panel", "GUI diagnostics/support panel calls existing preflight, result-health and support-bundle helpers without adding a parallel pipeline.", tokens=list(required)))
    except Exception as exc:
        checks.append(_fail("gui_diagnostics_support_panel", f"{type(exc).__name__}: {exc}"))

    try:
        if is_frozen_app():
            from ..ui import UI_SKELETON_VERSION

            checks.append(_ok("gui_run_history_post_run_actions", "Frozen UI skeleton includes the v69.6 run history/post-run action polish; source token check is skipped.", ui_skeleton_version=UI_SKELETON_VERSION))
        else:
            ui_file = root / "face_sorter_mvp" / "ui" / "main_window.py"
            ui_text_raw = ui_file.read_text(encoding="utf-8")
            required = (
                "post_run_actions_label",
                "_result_action_lines",
                "_quick_result_state",
                "open_people_dir",
                "open_review_dir",
                "open_selected_resume_diagnostics",
                "open_selected_resume_bug_reports",
                "open_selected_resume_final",
                "open_selected_resume_final_review",
            )
            missing = [token for token in required if token not in ui_text_raw]
            if missing:
                raise AssertionError({"missing": missing, "file": str(ui_file)})
            checks.append(_ok("gui_run_history_post_run_actions", "GUI run history/recent and post-run actions are present without adding a backend workflow.", tokens=list(required)))
    except Exception as exc:
        checks.append(_fail("gui_run_history_post_run_actions", f"{type(exc).__name__}: {exc}"))

    try:
        if is_frozen_app():
            from ..ui import UI_SKELETON_VERSION

            checks.append(_ok("gui_beginner_first_run_ux", "Frozen UI skeleton includes the v69.6 beginner first-run action map; source token check is skipped.", ui_skeleton_version=UI_SKELETON_VERSION))
        else:
            ui_file = root / "face_sorter_mvp" / "ui" / "main_window.py"
            usability_file = root / "face_sorter_mvp" / "core" / "ui_usability.py"
            ui_text_raw = ui_file.read_text(encoding="utf-8")
            usability_text = usability_file.read_text(encoding="utf-8")
            docs = [root / "FIRST_RUN_RU.txt", root / "FIRST_RUN_EN.txt"]
            missing_docs = [str(path.name) for path in docs if not path.exists()]
            required_ui = (
                "beginner_action_label",
                "_update_beginner_action_block",
                "build_beginner_action_map_text",
            )
            required_helper = (
                "def build_beginner_action_map_text",
                "beginner_action_map_text",
                "portable_first_run_docs",
            )
            missing = [token for token in required_ui if token not in ui_text_raw]
            missing.extend(token for token in required_helper if token not in usability_text)
            if missing or missing_docs:
                raise AssertionError({"missing_tokens": missing, "missing_docs": missing_docs})
            checks.append(_ok("gui_beginner_first_run_ux", "GUI start screen and source docs include beginner first-run guidance without adding a backend workflow.", tokens=list(required_ui + required_helper), docs=[path.name for path in docs]))
    except Exception as exc:
        checks.append(_fail("gui_beginner_first_run_ux", f"{type(exc).__name__}: {exc}"))

    try:
        if is_frozen_app():
            from ..ui import UI_SKELETON_VERSION

            checks.append(_ok("human_readable_errors", "Frozen UI skeleton includes the v69.6 human-readable errors polish; source token check is skipped.", ui_skeleton_version=UI_SKELETON_VERSION))
        else:
            ui_file = root / "face_sorter_mvp" / "ui" / "main_window.py"
            status_file = root / "face_sorter_mvp" / "core" / "status.py"
            docs = [root / "ERRORS_RU.txt", root / "ERRORS_EN.txt"]
            ui_text_raw = ui_file.read_text(encoding="utf-8")
            status_text = status_file.read_text(encoding="utf-8")
            missing_docs = [path.name for path in docs if not path.exists()]
            required_ui = (
                "human_error_help_label",
                "humanize_status_report",
                "Что это значит",
                "Что сделать",
            )
            required_status = (
                "def human_error_guidance",
                "def humanize_status_report",
                "def build_error_guidance_text",
                "recommended_action",
                "CUDAExecutionProvider",
                "problem_files.csv",
            )
            missing = [token for token in required_ui if token not in ui_text_raw]
            missing.extend(token for token in required_status if token not in status_text)
            if missing or missing_docs:
                raise AssertionError({"missing_tokens": missing, "missing_docs": missing_docs})
            checks.append(_ok("human_readable_errors", "Status/errors UI and source docs include human-readable Meaning/Action guidance without changing backend workflows.", tokens=list(required_ui + required_status), docs=[path.name for path in docs]))
    except Exception as exc:
        checks.append(_fail("human_readable_errors", f"{type(exc).__name__}: {exc}"))


    try:
        docs = [
            root / "QUICK_START_RU.txt",
            root / "QUICK_START_EN.txt",
            root / "TROUBLESHOOTING_RU.txt",
            root / "TROUBLESHOOTING_EN.txt",
            root / "START_HERE_RU.txt",
            root / "START_HERE_EN.txt",
            root / "README_RU.txt",
            root / "README_EN.txt",
        ]
        missing_docs = [path.name for path in docs if not path.exists()]
        token_requirements = {
            "QUICK_START_RU.txt": ("TunedImageSorter.exe", "Проверка окружения", "Быстрый тест", "TROUBLESHOOTING_RU.txt", "--support-bundle", "v69.6"),
            "QUICK_START_EN.txt": ("TunedImageSorter.exe", "Environment check", "Quick test", "TROUBLESHOOTING_EN.txt", "--support-bundle", "v69.6"),
            "TROUBLESHOOTING_RU.txt": ("SmartScreen", "CUDAExecutionProvider", "NVIDIA driver", "problem_files.csv", "--result-health", "ordinary Start must run mode=all, not apply-names", "v69.6"),
            "TROUBLESHOOTING_EN.txt": ("SmartScreen", "CUDAExecutionProvider", "NVIDIA driver", "problem_files.csv", "--result-health", "ordinary Start must run mode=all, not apply-names", "v69.6"),
            "START_HERE_RU.txt": ("QUICK_START_RU.txt", "TROUBLESHOOTING_RU.txt"),
            "START_HERE_EN.txt": ("QUICK_START_EN.txt", "TROUBLESHOOTING_EN.txt"),
            "README_RU.txt": ("QUICK_START_RU.txt", "TROUBLESHOOTING_RU.txt"),
            "README_EN.txt": ("QUICK_START_EN.txt", "TROUBLESHOOTING_EN.txt"),
        }
        token_errors = []
        for path in docs:
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for token in token_requirements.get(path.name, ()):
                if token not in text:
                    token_errors.append(f"{path.name} must mention {token!r}")
        if missing_docs or token_errors:
            raise AssertionError({"missing_docs": missing_docs, "token_errors": token_errors})
        checks.append(_ok("friend_ready_quick_start_troubleshooting", "Friend-ready QUICK_START and TROUBLESHOOTING docs are present and linked from START_HERE/README without changing backend workflows.", docs=[path.name for path in docs]))
    except Exception as exc:
        checks.append(_fail("friend_ready_quick_start_troubleshooting", f"{type(exc).__name__}: {exc}"))

    try:
        docs = [
            root / "RC_CHECKLIST_RU.txt",
            root / "RC_CHECKLIST_EN.txt",
            root / "RELEASE_GATE_RU.txt",
            root / "RELEASE_GATE_EN.txt",
            root / "VERSION.txt",
            root / "README_RU.txt",
            root / "README_EN.txt",
        ]
        missing_docs = [path.name for path in docs if not path.exists()]
        token_requirements = {
            "RC_CHECKLIST_RU.txt": ("release_candidate_final_gate", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "package_identity_check: OK", "zip_integrity: OK", "ordinary Start must run mode=all, not apply-names", "v69.6"),
            "RC_CHECKLIST_EN.txt": ("release_candidate_final_gate", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "package_identity_check: OK", "zip_integrity: OK", "ordinary Start must run mode=all, not apply-names", "v69.6"),
            "RELEASE_GATE_RU.txt": ("PASS", "FAIL", "release-check", "friend-ready package verification", "portable_manifest.json", "package_identity_check", "v69.6"),
            "RELEASE_GATE_EN.txt": ("PASS", "FAIL", "release-check", "friend-ready package verification", "portable_manifest.json", "package_identity_check", "v69.6"),
            "VERSION.txt": ("RC_CHECKLIST_RU.txt", "RELEASE_GATE_RU.txt", "version=v69.6", "refactor_stage=Этап 055"),
            "README_RU.txt": ("RC_CHECKLIST_RU.txt", "RELEASE_GATE_RU.txt"),
            "README_EN.txt": ("RC_CHECKLIST_EN.txt", "RELEASE_GATE_EN.txt"),
        }
        token_errors = []
        for path in docs:
            if not path.exists():
                continue
            doc_text = path.read_text(encoding="utf-8", errors="replace")
            for token in token_requirements.get(path.name, ()): 
                if token not in doc_text:
                    token_errors.append(f"{path.name} must mention {token!r}")
        build_script = root / "tools" / "windows_packaging" / "build_windows_gui.ps1"
        build_text = build_script.read_text(encoding="utf-8", errors="replace") if build_script.exists() else ""
        for token in ("RC_CHECKLIST_RU.txt", "RELEASE_GATE_RU.txt", "_portable_v69_6.zip"):
            if token not in build_text:
                token_errors.append(f"build_windows_gui.ps1 must mention {token!r}")
        if missing_docs or token_errors:
            raise AssertionError({"missing_docs": missing_docs, "token_errors": token_errors})
        checks.append(_ok("release_candidate_final_gate", "RC checklist and final release gate docs are present, packaged and linked without adding a backend workflow.", docs=[path.name for path in docs]))
    except Exception as exc:
        checks.append(_fail("release_candidate_final_gate", f"{type(exc).__name__}: {exc}"))


    try:
        docs = [
            root / "RELEASE_FREEZE_RU.txt",
            root / "RELEASE_FREEZE_EN.txt",
            root / "RELEASE_GATE_RU.txt",
            root / "RELEASE_GATE_EN.txt",
            root / "VERSION.txt",
        ]
        missing_docs = [path.name for path in docs if not path.exists()]
        token_requirements = {
            "RELEASE_FREEZE_RU.txt": ("release_freeze_final_package", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "package_identity_check: OK", "zip_integrity: OK", "_internal\\nvidia", "Первый запуск", "v69.6", "Этап 055"),
            "RELEASE_FREEZE_EN.txt": ("release_freeze_final_package", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "package_identity_check: OK", "zip_integrity: OK", "_internal\\nvidia", "First launch", "v69.6", "Stage 055"),
            "RELEASE_GATE_RU.txt": ("RELEASE_FREEZE_RU.txt", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip"),
            "RELEASE_GATE_EN.txt": ("RELEASE_FREEZE_EN.txt", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip"),
            "VERSION.txt": ("version=v69.6", "refactor_stage=Этап 055", "RELEASE_FREEZE_RU.txt", "RELEASE_FREEZE_EN.txt"),
        }
        token_errors = []
        for path in docs:
            if not path.exists():
                continue
            doc_text = path.read_text(encoding="utf-8", errors="replace")
            for token in token_requirements.get(path.name, ()): 
                if token not in doc_text:
                    token_errors.append(f"{path.name} must mention {token!r}")
        build_script = root / "tools" / "windows_packaging" / "build_windows_gui.ps1"
        build_text = build_script.read_text(encoding="utf-8", errors="replace") if build_script.exists() else ""
        for token in ("RELEASE_FREEZE_RU.txt", "RELEASE_FREEZE_EN.txt", "_portable_v69_6.zip", " 055"):
            if token not in build_text:
                token_errors.append(f"build_windows_gui.ps1 must mention {token!r}")
        if missing_docs or token_errors:
            raise AssertionError({"missing_docs": missing_docs, "token_errors": token_errors})
        checks.append(_ok("release_freeze_final_package", "Stable release freeze docs and packaging tokens are present without changing backend workflows.", docs=[path.name for path in docs]))
    except Exception as exc:
        checks.append(_fail("release_freeze_final_package", f"{type(exc).__name__}: {exc}"))


    try:
        docs = [
            root / "DOCS_I18N_HYGIENE_RU.txt",
            root / "DOCS_I18N_HYGIENE_EN.txt",
            root / "docs" / "DEVELOPER_NOTES_RU.md",
            root / "docs" / "DEVELOPER_NOTES_EN.md",
            root / "face_sorter_mvp" / "ARCHITECTURE_FOR_AGENTS.md",
            root / "face_sorter_mvp" / "README_RU.md",
            root / "face_sorter_mvp" / "README_EN.md",
            root / "VERSION.txt",
        ]
        missing_docs = [path.name for path in docs if not path.exists()]
        token_requirements = {
            "DOCS_I18N_HYGIENE_RU.txt": ("docs_i18n_hygiene_polish", "v69.6", "Этап 055", "release-check", "package_identity_check", "friend-ready package verification", "zip_integrity", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "не менялись"),
            "DOCS_I18N_HYGIENE_EN.txt": ("docs_i18n_hygiene_polish", "v69.6", "Stage 055", "release-check", "package_identity_check", "friend-ready package verification", "zip_integrity", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "unchanged"),
            "DEVELOPER_NOTES_RU.md": ("GPU Lite", "v69.6 / Этап 055", "Запрещено менять", "CUDAExecutionProvider", "experimental_slim_gpu_package"),
            "DEVELOPER_NOTES_EN.md": ("GPU Lite", "v69.6 / Stage 055", "Do not change", "CUDAExecutionProvider", "experimental_slim_gpu_package"),
            "ARCHITECTURE_FOR_AGENTS.md": ("v69.6 / Этап 055", "GPU Lite", "Do not change", "Full GPU portable", "experimental_slim_gpu_package"),
            "README_RU.md": ("GPU Lite", "v69.6 / Этап 055", "GPU_LITE_RU.txt", "не меняет ML"),
            "README_EN.md": ("GPU Lite", "v69.6 / Stage 055", "GPU_LITE_EN.txt", "does not change ML"),
            "VERSION.txt": ("version=v69.6", "refactor_stage=Этап 055", "DOCS_I18N_HYGIENE_RU.txt", "DOCS_I18N_HYGIENE_EN.txt"),
        }
        token_errors = []
        for path in docs:
            if not path.exists():
                continue
            doc_text = path.read_text(encoding="utf-8", errors="replace")
            for token in token_requirements.get(path.name, ()): 
                if token not in doc_text:
                    token_errors.append(f"{path.name} must mention {token!r}")
        stale_patterns = (
            "v67.9 / Этап 055",
            "v67.9 / Stage 055",
            "v67.8.4 / Этап 039",
            "v67.8.4 / Stage 039",
        )
        stale_errors = []
        for path in docs:
            if not path.exists():
                continue
            doc_text = path.read_text(encoding="utf-8", errors="replace")
            for pattern in stale_patterns:
                if pattern in doc_text:
                    stale_errors.append(f"{path.name} still contains stale baseline reference {pattern!r}")
        if missing_docs or token_errors or stale_errors:
            raise AssertionError({"missing_docs": missing_docs, "token_errors": token_errors, "stale_errors": stale_errors})
        checks.append(_ok("docs_i18n_hygiene_polish", "Docs/i18n hygiene files and developer-facing notes are aligned without changing runtime behavior.", docs=[str(path.relative_to(root)) for path in docs]))
    except Exception as exc:
        checks.append(_fail("docs_i18n_hygiene_polish", f"{type(exc).__name__}: {exc}"))


    try:
        docs = [
            root / "GPU_LITE_RU.txt",
            root / "GPU_LITE_EN.txt",
            root / "tools" / "windows_packaging" / "build_windows_gui.ps1",
            root / "tools" / "windows_packaging" / "pyinstaller_gui_entry.py",
            root / "face_sorter_mvp" / "core" / "gpu_lite_runtime.py",
            root / "tools" / "windows_packaging" / "package_identity_report.py",
            root / "tools" / "windows_packaging" / "verify_friend_ready_package.py",
        ]
        missing_docs = [str(path.relative_to(root)) for path in docs if not path.exists()]
        token_requirements = {
            "GPU_LITE_RU.txt": ("experimental_slim_gpu_package", "v69.6", "Этап 055", "TunedImageSorter_GPU_LITE_portable_v69_6.zip", "--gpu-lite-runtime-status", "--gpu-lite-runtime-setup --yes", "локальную папку пользователя", "NVIDIA driver"),
            "GPU_LITE_EN.txt": ("experimental_slim_gpu_package", "v69.6", "Stage 055", "TunedImageSorter_GPU_LITE_portable_v69_6.zip", "--gpu-lite-runtime-status", "--gpu-lite-runtime-setup --yes", "local user folder", "NVIDIA driver"),
            "build_windows_gui.ps1": ("gpu-lite", "TunedImageSorter_GPU_LITE", "Remove-GpuLiteBundledRuntime", "Assert-GpuLitePackage", "--gpu-lite-runtime-status", "_portable_v69_6.zip"),
            "pyinstaller_gui_entry.py": ("--gpu-lite-runtime-status", "--gpu-lite-runtime-setup", "ensure_gpu_lite_runtime_interactive"),
            "gpu_lite_runtime.py": ("GPU_LITE_RUNTIME_PACKAGES", "install_gpu_lite_runtime", "ensure_gpu_lite_runtime_interactive", "PyPI", "LOCALAPPDATA"),
            "package_identity_report.py": ("gpu-lite", "GPU_LITE_VERIFICATION_FILES", "GPU Lite package must not bundle _internal/nvidia"),
            "verify_friend_ready_package.py": ("gpu-lite", "GPU_LITE_VERIFICATION_FILES", "GPU Lite package must not bundle _internal/nvidia"),
        }
        token_errors = []
        for path in docs:
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for token in token_requirements.get(path.name, ()): 
                if token not in text:
                    token_errors.append(f"{path.name} must mention {token!r}")
        if missing_docs or token_errors:
            raise AssertionError({"missing_docs": missing_docs, "token_errors": token_errors})
        checks.append(_ok("experimental_slim_gpu_package", "Experimental GPU Lite package profile is present without replacing CPU/full GPU portable builds.", docs=[str(path.relative_to(root)) for path in docs]))
    except Exception as exc:
        checks.append(_fail("experimental_slim_gpu_package", f"{type(exc).__name__}: {exc}"))


    try:
        docs = [
            root / "DUAL_GPU_PACKAGING_RU.txt",
            root / "DUAL_GPU_PACKAGING_EN.txt",
            root / "README_RU.txt",
            root / "README_EN.txt",
            root / "VERSION.txt",
            root / "RELEASE_GATE_RU.txt",
            root / "RELEASE_GATE_EN.txt",
        ]
        missing_docs = [path.name for path in docs if not path.exists()]
        token_requirements = {
            "DUAL_GPU_PACKAGING_RU.txt": ("dual_gpu_packaging_release_docs", "v69.6", "Этап 055", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip", "GPU_FULL", "GPU_LITE", "ordinary Start must run mode=all, not apply-names"),
            "DUAL_GPU_PACKAGING_EN.txt": ("dual_gpu_packaging_release_docs", "v69.6", "Stage 055", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip", "GPU_FULL", "GPU_LITE", "ordinary Start must run mode=all, not apply-names"),
            "README_RU.txt": ("DUAL_GPU_PACKAGING_RU.txt", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip"),
            "README_EN.txt": ("DUAL_GPU_PACKAGING_EN.txt", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip"),
            "VERSION.txt": ("dual_gpu_packaging_release_docs", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip"),
            "RELEASE_GATE_RU.txt": ("DUAL_GPU_PACKAGING_RU.txt", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip"),
            "RELEASE_GATE_EN.txt": ("DUAL_GPU_PACKAGING_EN.txt", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip"),
        }
        token_errors = []
        for path in docs:
            if not path.exists():
                continue
            doc_text = path.read_text(encoding="utf-8", errors="replace")
            for token in token_requirements.get(path.name, ()): 
                if token not in doc_text:
                    token_errors.append(f"{path.name} must mention {token!r}")
        build_script = root / "tools" / "windows_packaging" / "build_windows_gui.ps1"
        build_text = build_script.read_text(encoding="utf-8", errors="replace") if build_script.exists() else ""
        for token in ("gpu-full", "TunedImageSorter_GPU_FULL", "TunedImageSorter_GPU_LITE", "_portable_v69_6.zip"):
            if token not in build_text:
                token_errors.append(f"build_windows_gui.ps1 must mention {token!r}")
        if missing_docs or token_errors:
            raise AssertionError({"missing_docs": missing_docs, "token_errors": token_errors})
        checks.append(_ok("dual_gpu_packaging_release_docs", "Dual GPU packaging docs and official CPU/GPU_FULL/GPU_LITE artifact names are aligned without changing runtime behavior.", docs=[path.name for path in docs]))
    except Exception as exc:
        checks.append(_fail("dual_gpu_packaging_release_docs", f"{type(exc).__name__}: {exc}"))

    try:
        docs = [
            root / "PRODUCT_RENAME_RU.txt",
            root / "PRODUCT_RENAME_EN.txt",
            root / "README_RU.txt",
            root / "README_EN.txt",
            root / "VERSION.txt",
            root / "START_HERE_RU.txt",
            root / "START_HERE_EN.txt",
        ]
        missing_docs = [path.name for path in docs if not path.exists()]
        token_requirements = {
            "PRODUCT_RENAME_RU.txt": ("Tuned Image Sorter", "v69.6", "Этап 055", "TunedImageSorter.exe", "TunedImageSorter_CLI.exe", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip", "face_sorter_mvp", "compatibility fallback"),
            "PRODUCT_RENAME_EN.txt": ("Tuned Image Sorter", "v69.6", "Stage 055", "TunedImageSorter.exe", "TunedImageSorter_CLI.exe", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip", "face_sorter_mvp", "compatibility fallback"),
            "README_RU.txt": ("Tuned Image Sorter", "PRODUCT_RENAME_RU.txt", "TunedImageSorter.exe", "TunedImageSorter_CLI.exe"),
            "README_EN.txt": ("Tuned Image Sorter", "PRODUCT_RENAME_EN.txt", "TunedImageSorter.exe", "TunedImageSorter_CLI.exe"),
            "VERSION.txt": ("product_rename_package_identity", "Tuned Image Sorter", "TunedImageSorter.exe", "TunedImageSorter_CLI.exe"),
            "START_HERE_RU.txt": ("Tuned Image Sorter", "PRODUCT_RENAME_RU.txt", "TunedImageSorter.exe"),
            "START_HERE_EN.txt": ("Tuned Image Sorter", "PRODUCT_RENAME_EN.txt", "TunedImageSorter.exe"),
        }
        token_errors = []
        for path in docs:
            if not path.exists():
                continue
            doc_text = path.read_text(encoding="utf-8", errors="replace")
            for token in token_requirements.get(path.name, ()): 
                if token not in doc_text:
                    token_errors.append(f"{path.name} must mention {token!r}")
        build_script = root / "tools" / "windows_packaging" / "build_windows_gui.ps1"
        build_text = build_script.read_text(encoding="utf-8", errors="replace") if build_script.exists() else ""
        for token in ("TunedImageSorter_CPU", "TunedImageSorter_GPU_FULL", "TunedImageSorter_GPU_LITE", "TunedImageSorter.exe", "TunedImageSorter_CLI.exe"):
            if token not in build_text:
                token_errors.append(f"build_windows_gui.ps1 must mention {token!r}")
        if missing_docs or token_errors:
            raise AssertionError({"missing_docs": missing_docs, "token_errors": token_errors})
        checks.append(_ok("product_rename_package_identity", "Public product name and portable package identity are aligned for Tuned Image Sorter without renaming the internal Python package.", docs=[path.name for path in docs]))
    except Exception as exc:
        checks.append(_fail("product_rename_package_identity", f"{type(exc).__name__}: {exc}"))


    try:
        text_files = [
            root / "tools" / "windows_packaging" / "README_WINDOWS_PACKAGING_RU.md",
            root / "tools" / "windows_packaging" / "README_WINDOWS_PACKAGING_EN.md",
            root / "docs" / "DEVELOPER_NOTES_RU.md",
            root / "docs" / "DEVELOPER_NOTES_EN.md",
            root / "face_sorter_mvp" / "ARCHITECTURE_FOR_AGENTS.md",
            root / "face_sorter_mvp" / "README_RU.md",
            root / "face_sorter_mvp" / "README_EN.md",
        ]
        control_errors = []
        for path in text_files:
            if not path.exists():
                control_errors.append(f"missing text file {path.relative_to(root)}")
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if "\x08" in text:
                control_errors.append(f"{path.relative_to(root)} contains U+0008/backspace control character")
            if "windows_packaging\\build_windows_gui.ps1 -Profile gpu-lite" not in text:
                control_errors.append(f"{path.relative_to(root)} must contain the literal gpu-lite build command with a normal backslash")
        main_window = root / "face_sorter_mvp" / "ui" / "main_window.py"
        preflight = root / "face_sorter_mvp" / "core" / "preflight.py"
        gpu_lite_runtime = root / "face_sorter_mvp" / "core" / "gpu_lite_runtime.py"
        legacy = root / "face_sorter_mvp" / "face_sorter_mvp.py"
        main_text = main_window.read_text(encoding="utf-8", errors="replace") if main_window.exists() else ""
        preflight_text = preflight.read_text(encoding="utf-8", errors="replace") if preflight.exists() else ""
        gpu_lite_text = gpu_lite_runtime.read_text(encoding="utf-8", errors="replace") if gpu_lite_runtime.exists() else ""
        legacy_text = legacy.read_text(encoding="utf-8", errors="replace") if legacy.exists() else ""
        token_errors = []
        for token in (
            "ShellExecuteW",
            "_open_path_windows_no_console",
            "auto_open_reports_after_run",
            "self.open_reports_dir()",
            "self.open_final_dir()",
        ):
            if token not in main_text:
                token_errors.append(f"main_window.py must mention {token!r}")
        if "creationflags=_windows_no_window_creationflags()" not in preflight_text:
            token_errors.append("preflight subprocess probes must use CREATE_NO_WINDOW creation flags")
        if "creationflags=_windows_no_window_creationflags()" not in gpu_lite_text:
            token_errors.append("GPU Lite runtime setup probes/download helpers must use CREATE_NO_WINDOW creation flags")
        if "creationflags=windows_no_window_creationflags()" not in legacy_text:
            token_errors.append("legacy captured subprocess diagnostics must use CREATE_NO_WINDOW creation flags")
        if control_errors or token_errors:
            raise AssertionError({"control_errors": control_errors, "token_errors": token_errors})
        checks.append(_ok(
            "windows_no_console_post_run_open_actions",
            "Windows launcher/open-folder behavior is guarded: docs have normal backslashes, captured subprocesses use CREATE_NO_WINDOW, and UI open-folder actions use ShellExecuteW with post-run quick actions.",
            docs=[str(path.relative_to(root)) for path in text_files],
        ))
    except Exception as exc:
        checks.append(_fail("windows_no_console_post_run_open_actions", f"{type(exc).__name__}: {exc}"))


    try:
        doc_checks = {
            "PROFILE_GUIDE_RU.txt": ("CPU", "GPU_FULL", "GPU_LITE", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip", "не менялись"),
            "PROFILE_GUIDE_EN.txt": ("CPU", "GPU_FULL", "GPU_LITE", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip", "unchanged"),
            "PRIVACY_LOCAL_PROCESSING_RU.txt": ("privacy", "local processing", "исходные фотографии", "support-bundle", "known non-blocking UX issue"),
            "PRIVACY_LOCAL_PROCESSING_EN.txt": ("privacy", "local processing", "source photos", "support-bundle", "known non-blocking UX issue"),
            "KNOWN_LIMITATIONS_RU.txt": ("known limitations", "reports", "known non-blocking UX issue", "GPU_LITE", "review_decisions.csv"),
            "KNOWN_LIMITATIONS_EN.txt": ("known limitations", "reports", "known non-blocking UX issue", "GPU_LITE", "review_decisions.csv"),
            "PUBLIC_RELEASE_NOTES_RU.txt": ("TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip", "known non-blocking issue"),
            "PUBLIC_RELEASE_NOTES_EN.txt": ("TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip", "known non-blocking issue"),
            "RELEASE_BUNDLE_RU.txt": ("release bundle", "SHA256SUMS.txt", "RELEASE_BUNDLE_MANIFEST.json", "TunedImageSorter_v69_6_release", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip"),
            "RELEASE_BUNDLE_EN.txt": ("release bundle", "SHA256SUMS.txt", "RELEASE_BUNDLE_MANIFEST.json", "TunedImageSorter_v69_6_release", "TunedImageSorter_CPU_portable_v69_6.zip", "TunedImageSorter_GPU_FULL_portable_v69_6.zip", "TunedImageSorter_GPU_LITE_portable_v69_6.zip"),
            "WHICH_VERSION_TO_DOWNLOAD_RU.txt": ("CPU", "GPU_FULL", "GPU_LITE", "TunedImageSorter_CPU_portable_v69_6.zip", "known issue"),
            "WHICH_VERSION_TO_DOWNLOAD_EN.txt": ("CPU", "GPU_FULL", "GPU_LITE", "TunedImageSorter_CPU_portable_v69_6.zip", "Known issue"),
        }
        missing = []
        token_errors = []
        docs = []
        for rel_name, tokens in doc_checks.items():
            doc_path = root / rel_name
            docs.append(doc_path)
            if not doc_path.exists():
                missing.append(rel_name)
                continue
            text = doc_path.read_text(encoding="utf-8", errors="replace")
            for token in tokens:
                if token not in text:
                    token_errors.append(f"{rel_name} must mention {token!r}")
        for parent_name, tokens in {
            "README_RU.txt": ("PROFILE_GUIDE_RU.txt", "PRIVACY_LOCAL_PROCESSING_RU.txt", "KNOWN_LIMITATIONS_RU.txt", "PUBLIC_RELEASE_NOTES_RU.txt", "RELEASE_BUNDLE_RU.txt", "WHICH_VERSION_TO_DOWNLOAD_RU.txt"),
            "README_EN.txt": ("PROFILE_GUIDE_EN.txt", "PRIVACY_LOCAL_PROCESSING_EN.txt", "KNOWN_LIMITATIONS_EN.txt", "PUBLIC_RELEASE_NOTES_EN.txt", "RELEASE_BUNDLE_EN.txt", "WHICH_VERSION_TO_DOWNLOAD_EN.txt"),
            "VERSION.txt": ("public_release_handoff", "release_bundle", "PROFILE_GUIDE_RU.txt", "PRIVACY_LOCAL_PROCESSING_RU.txt", "KNOWN_LIMITATIONS_RU.txt", "PUBLIC_RELEASE_NOTES_RU.txt", "RELEASE_BUNDLE_RU.txt", "WHICH_VERSION_TO_DOWNLOAD_RU.txt"),
        }.items():
            parent_path = root / parent_name
            if not parent_path.exists():
                missing.append(parent_name)
                continue
            text = parent_path.read_text(encoding="utf-8", errors="replace")
            for token in tokens:
                if token not in text:
                    token_errors.append(f"{parent_name} must mention {token!r}")
        if missing or token_errors:
            raise AssertionError({"missing": missing, "token_errors": token_errors})
        checks.append(_ok("public_release_handoff_docs", "Profile guide, privacy/local-processing note, known limitations and public release notes are present without changing backend workflows.", docs=[path.name for path in docs]))
    except Exception as exc:
        checks.append(_fail("public_release_handoff_docs", f"{type(exc).__name__}: {exc}"))

    try:
        bundle_script = root / "tools" / "windows_packaging" / "make_release_bundle.py"
        script_text = bundle_script.read_text(encoding="utf-8", errors="replace") if bundle_script.exists() else ""
        required = (
            "RELEASE_ZIP_FILES",
            "TunedImageSorter_CPU_portable_v69_6.zip",
            "TunedImageSorter_GPU_FULL_portable_v69_6.zip",
            "TunedImageSorter_GPU_LITE_portable_v69_6.zip",
            "SHA256SUMS.txt",
            "RELEASE_BUNDLE_MANIFEST.json",
            "TunedImageSorter_v69_6_release",
            "ML/recognition unchanged",
        )
        missing_tokens = [token for token in required if token not in script_text]
        if not bundle_script.exists() or missing_tokens:
            raise AssertionError({"script_exists": bundle_script.exists(), "missing_tokens": missing_tokens})
        checks.append(_ok("release_bundle_checksums_handoff", "Release bundle script and docs are present for SHA256SUMS and final public handoff without changing runtime behavior.", script=str(bundle_script.relative_to(root))))
    except Exception as exc:
        checks.append(_fail("release_bundle_checksums_handoff", f"{type(exc).__name__}: {exc}"))

    try:
        polish = ui_polish_snapshot()
        usability = ui_usability_snapshot()
        asset_root = bundle_internal_dir() if is_frozen_app() else root
        icon = asset_root / "face_sorter_mvp" / "ui" / "resources" / "app_icon.ico"
        png = asset_root / "face_sorter_mvp" / "ui" / "resources" / "app_icon.png"
        missing = [str(path) for path in (icon, png) if not path.exists()]
        if missing:
            raise AssertionError(f"missing UI assets: {missing}")
        checks.append(_ok("ui_assets", "UI icon assets, polish snapshot and usability snapshot are available.", polish=polish.to_dict(), usability=usability.to_dict(), asset_root=str(asset_root)))
    except Exception as exc:
        checks.append(_fail("ui_assets", f"{type(exc).__name__}: {exc}"))

    # PyInstaller one-folder stores collected data files under _internal, not
    # next to the executable.  Source mode still verifies docs from project root.
    docs_root = bundle_internal_dir() if is_frozen_app() else root
    required_files = [
        docs_root / "CHANGELOG.md",
        docs_root / "docs" / "USER_GUIDE_RU.md",
        docs_root / "docs" / "USER_GUIDE_EN.md",
        docs_root / "docs" / "HELP_RU.md",
        docs_root / "docs" / "HELP_EN.md",
        docs_root / "docs" / "DEVELOPER_NOTES_RU.md",
        docs_root / "docs" / "DEVELOPER_NOTES_EN.md",
    ]
    if not is_frozen_app():
        required_files.extend([
            root / "tools" / "release_check.py",
            root / "tools" / "windows_packaging" / "README_WINDOWS_PACKAGING_RU.md",
            root / "tools" / "windows_packaging" / "README_WINDOWS_PACKAGING_EN.md",
        ])
    missing_docs = [str(path.relative_to(docs_root) if str(path).startswith(str(docs_root)) else path) for path in required_files if not path.exists()]
    if missing_docs:
        checks.append(_fail("release_docs", "Release/check documentation files are missing.", missing=missing_docs))
    else:
        checks.append(_ok("release_docs", "CHANGELOG, user guides, bilingual help and developer notes are present." + (" Source release/build docs are also present." if not is_frozen_app() else ""), files=[str(path.relative_to(docs_root) if str(path).startswith(str(docs_root)) else path) for path in required_files]))

    checks.append(_session_compatibility_check())

    for module_name in ("face_sorter_mvp.ui", "face_sorter_mvp.backend", "face_sorter_mvp.core.release", "face_sorter_mvp.core.ui_usability", "face_sorter_mvp.core.frozen_runtime", "face_sorter_mvp.core.frozen_diagnostics", "face_sorter_mvp.core.result_health", "face_sorter_mvp.core.diagnostics_help", "face_sorter_mvp.core.status"):
        ok, message = _module_import_check(module_name)
        checks.append(_ok(f"import_{module_name}", message) if ok else _fail(f"import_{module_name}", message))

    try:
        # Ensure the result is JSON-serializable.  This catches Path/dataclass
        # leaks before GUI bug reports or CI scripts try to write the result.
        json.dumps(_json_safe([check.to_dict() for check in checks]), ensure_ascii=False)
        checks.append(_ok("json_serializable", "Release check result payload is JSON-serializable."))
    except Exception as exc:
        checks.append(_fail("json_serializable", f"{type(exc).__name__}: {exc}"))

    errors = tuple(check.message for check in checks if not check.ok and check.severity == "error")
    warnings = tuple(check.message for check in checks if check.severity == "warning")
    duration_ms = int((time.perf_counter() - started) * 1000)
    return ReleaseCheckResult(
        ok=not errors,
        version=SCRIPT_VERSION,
        refactor_stage=api.refactor_stage,
        ui_api_version=api.api_version,
        schema_version=RELEASE_CHECK_SCHEMA_VERSION,
        created_at=dt.datetime.now().isoformat(timespec="seconds"),
        duration_ms=duration_ms,
        checks=tuple(checks),
        errors=errors,
        warnings=warnings,
    )


__all__ = [
    "RELEASE_CHECK_SCHEMA_VERSION",
    "RELEASE_CHECK_STAGE",
    "ReleaseCheckItem",
    "ReleaseCheckResult",
    "run_release_check",
]
