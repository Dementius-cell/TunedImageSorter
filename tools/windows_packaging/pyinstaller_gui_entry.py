# -*- coding: utf-8 -*-
"""PyInstaller entry point for Tuned Image Sorter.

The wrapper stays tiny and calls ``multiprocessing.freeze_support()`` before any
Qt/UI imports.  In a frozen Windows app, ProcessPool workers are spawned by
re-executing ``TunedImageSorter.exe`` with multiprocessing flags; without
``freeze_support()``, every scan worker can open another GUI window.

v69.6 builds two launchers from the same entry point: ``TunedImageSorter.exe`` is
windowed for Explorer users, while ``TunedImageSorter_CLI.exe`` keeps the console
for diagnostics. Diagnostic JSON output is ASCII-safe by default; CLI app diagnostics
that write support/result files default to English console text in frozen builds
to avoid Windows code-page mojibake. v69.6 also provides a short diagnostics
command-center help command. UTF-8 RU/EN report files are still written where
applicable.
"""
from __future__ import annotations

import contextlib
import json
import multiprocessing
import io
import os
import sys
import warnings
from pathlib import Path
from typing import Any, Optional, Sequence


DIAGNOSTIC_FLAGS = (
    "--frozen-info",
    "--runtime-preflight",
    "--self-test",
    "--release-check",
    "--scan-probe",
    "--support-bundle",
    "--result-health",
    "--diagnostics-help",
    "--gpu-lite-runtime-status",
    "--gpu-lite-runtime-setup",
)
DIAGNOSTIC_MODES = {"make-bug-report", "bug-report", "support-bundle", "result-health"}


class _NullTextStream:
    encoding = "utf-8"
    errors = "replace"

    def write(self, data: str) -> int:
        return len(data or "")

    def flush(self) -> None:
        return None

    def isatty(self) -> bool:
        return False


def _ensure_non_null_stdio() -> None:
    """Keep windowed PyInstaller GUI launchers safe when stdio is absent."""
    if getattr(sys, "stdout", None) is None:
        sys.stdout = _NullTextStream()
    if getattr(sys, "stderr", None) is None:
        sys.stderr = _NullTextStream()


def _ensure_source_root_on_path() -> None:
    """Allow this wrapper to run both from PyInstaller and directly from source."""
    try:
        root = Path(__file__).resolve().parents[2]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
    except Exception:
        pass


def _json_default(value: Any) -> str:
    if hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
        return value.to_dict()
    return str(value)


def _windows_console_output_encoding() -> Optional[str]:
    """Return the active Windows console output code page, if available.

    v69.6 uses the active console output page.  This avoids the v67.5.1
    mojibake case where a UTF-8 Windows Terminal session was encoded with an
    unrelated legacy Cyrillic page.  Leave redirected streams alone.
    """
    if os.name != "nt":
        return None
    try:
        import ctypes

        codepage = int(ctypes.windll.kernel32.GetConsoleOutputCP())
        if codepage <= 0:
            return None
        return "utf-8" if codepage == 65001 else f"cp{codepage}"
    except Exception:
        return None


def _stream_is_console_like(stream: Any) -> bool:
    try:
        return bool(stream is not None and hasattr(stream, "isatty") and stream.isatty())
    except Exception:
        return False


def _configure_diagnostic_streams() -> None:
    """Keep frozen CLI text readable in the active Windows console.

    Only reconfigure real console streams.  For redirected output, preserve
    Python/PyInstaller's stream encoding so JSON/text files are not damaged by
    an unrelated terminal code page.
    """
    encoding = _windows_console_output_encoding()
    if not encoding:
        return
    for stream in (getattr(sys, "stdout", None), getattr(sys, "stderr", None)):
        if not _stream_is_console_like(stream):
            continue
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding=encoding, errors="replace")
        except Exception:
            pass


def _suppress_diagnostic_warnings() -> None:
    """Keep successful JSON diagnostics clean in PowerShell output files."""
    warnings.filterwarnings("ignore", category=FutureWarning, module=r"insightface(\.|$)")
    warnings.filterwarnings("ignore", message=r".*`estimate` is deprecated.*", category=FutureWarning)


def _payload_to_plain_dict(payload: Any) -> Any:
    if hasattr(payload, "to_dict") and callable(getattr(payload, "to_dict")):
        try:
            return payload.to_dict()
        except Exception:
            return payload
    return payload


def _attach_stream_capture(payload: Any, stdout_text: str, stderr_text: str) -> Any:
    """Keep diagnostic stdout JSON-only while preserving captured noisy output.

    Some third-party libraries print provider/warning text while diagnostics are
    being collected.  v65.4 captures Python-level stdout/stderr around the
    diagnostic call and stores a bounded copy inside the JSON payload instead of
    letting it corrupt command output.  Native process-level writes may still be
    handled by the packaging-side mixed-output parser.
    """
    payload = _payload_to_plain_dict(payload)
    stdout_text = stdout_text or ""
    stderr_text = stderr_text or ""
    if not stdout_text and not stderr_text:
        return payload
    capture = {
        "stdout_present": bool(stdout_text),
        "stderr_present": bool(stderr_text),
        "stdout_tail": stdout_text[-8000:],
        "stderr_tail": stderr_text[-8000:],
    }
    if isinstance(payload, dict):
        out = dict(payload)
        out["diagnostic_stream_capture"] = capture
        return out
    return {"ok": True, "payload": payload, "diagnostic_stream_capture": capture}


def _print_json(payload: Any) -> int:
    _configure_diagnostic_streams()
    # Frozen console diagnostics should remain readable/copy-safe regardless of
    # Windows console code page. JSON escapes keep Cyrillic metadata valid while
    # avoiding mojibake in PowerShell/Windows Terminal clipboard paths.
    print(json.dumps(payload, ensure_ascii=True, indent=2, default=_json_default))
    return 0


def _print_json_from_diagnostic(factory) -> int:
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
        payload = factory()
    payload = _attach_stream_capture(payload, stdout_buffer.getvalue(), stderr_buffer.getvalue())
    return _print_json(payload)


def _arg_mode(args: Sequence[str]) -> Optional[str]:
    if "--mode" not in args:
        return None
    try:
        return str(args[list(args).index("--mode") + 1])
    except Exception:
        return None


def _needs_cli_app_dispatch(args: Sequence[str]) -> bool:
    mode = _arg_mode(args)
    return "--support-bundle" in args or "--result-health" in args or mode in DIAGNOSTIC_MODES


def _has_lang_arg(args: Sequence[str]) -> bool:
    return any(arg == "--lang" or str(arg).startswith("--lang=") for arg in args)


def _with_frozen_console_defaults(args: Sequence[str]) -> list[str]:
    """Keep frozen CLI app-dispatch output readable on any Windows code page.

    v67.5.1/v67.5.2 proved that reconfiguring the stream to the detected
    console code page is not reliable across PowerShell, Windows Terminal and
    clipboard capture.  For frozen diagnostics that print human text, use
    English/ASCII by default unless the user explicitly requested --lang ru.
    UTF-8 report files written to disk are unchanged.
    """
    out = list(args)
    if not _has_lang_arg(out):
        out.extend(["--lang", "en"])
    return out


def _run_cli_app_dispatch(args: Sequence[str]) -> int:
    """Dispatch diagnostics-only commands that are implemented by the main CLI.

    The frozen launcher handles JSON diagnostics directly, but support-bundle
    and result-health reuse the regular argument parser because they need the
    normal --output validation and write files into an existing result folder.
    Console text is ASCII-safe by default in frozen builds; report files remain
    UTF-8 and still include Russian text where the report writer provides it.
    """
    _configure_diagnostic_streams()
    _suppress_diagnostic_warnings()
    from face_sorter_mvp.face_sorter_mvp import main_impl
    return int(main_impl(_with_frozen_console_defaults(args)))


def _handle_diagnostic_args(argv: Sequence[str]) -> Optional[int]:
    args = list(argv)
    if not args:
        return None

    if any(arg in args for arg in DIAGNOSTIC_FLAGS) or _needs_cli_app_dispatch(args):
        _configure_diagnostic_streams()
        _suppress_diagnostic_warnings()

    if _needs_cli_app_dispatch(args):
        return _run_cli_app_dispatch(args)

    if "--diagnostics-help" in args:
        from face_sorter_mvp.core.diagnostics_help import diagnostics_help_text, language_from_args
        # English is default in frozen CLI so copied console output is ASCII-safe.
        print(diagnostics_help_text(language_from_args(args, default="en")))
        return 0

    if "--gpu-lite-runtime-status" in args:
        from face_sorter_mvp.core.gpu_lite_runtime import activate_gpu_lite_runtime_paths, gpu_lite_runtime_status
        activate_gpu_lite_runtime_paths()
        return _print_json_from_diagnostic(lambda: gpu_lite_runtime_status().to_dict())

    if "--gpu-lite-runtime-setup" in args:
        from face_sorter_mvp.core.gpu_lite_runtime import activate_gpu_lite_runtime_paths, install_gpu_lite_runtime
        assume_yes = "--yes" in args or "-y" in args
        result = install_gpu_lite_runtime(assume_yes=assume_yes)
        activate_gpu_lite_runtime_paths()
        return _print_json(result.to_dict()) if result.ok else (_print_json(result.to_dict()) or 1)

    if "--frozen-info" in args:
        from face_sorter_mvp.core.frozen_runtime import frozen_runtime_summary
        return _print_json_from_diagnostic(lambda: frozen_runtime_summary())

    if "--runtime-preflight" in args:
        try:
            from face_sorter_mvp.core.gpu_lite_runtime import activate_gpu_lite_runtime_paths, is_gpu_lite_package
            if is_gpu_lite_package():
                activate_gpu_lite_runtime_paths()
        except Exception:
            pass
        from face_sorter_mvp.core.preflight import runtime_preflight, runtime_preflight_summary
        gpu_requested = "--gpu" in args
        gpu_smoke = "--gpu-smoke" in args
        if gpu_requested:
            return _print_json_from_diagnostic(lambda: runtime_preflight(include_gpu=True, import_check=True, run_gpu_smoke_test=gpu_smoke).to_dict())
        return _print_json_from_diagnostic(lambda: runtime_preflight_summary())

    if "--self-test" in args:
        from face_sorter_mvp.core.self_test import run_backend_self_test
        return _print_json_from_diagnostic(lambda: run_backend_self_test().to_dict())

    if "--release-check" in args:
        from face_sorter_mvp.core.release import run_release_check
        return _print_json_from_diagnostic(lambda: run_release_check().to_dict())

    if "--scan-probe" in args:
        try:
            idx = args.index("--scan-probe")
            input_dir = args[idx + 1]
        except Exception:
            print("Usage: TunedImageSorter_CLI.exe --scan-probe <input_dir> [--model buffalo_l] [--det-size 640] [--gpu]")
            return 2
        model = "buffalo_l"
        det_size = 640
        gpu = "--gpu" in args
        if "--model" in args:
            try:
                model = args[args.index("--model") + 1]
            except Exception:
                pass
        if "--det-size" in args:
            try:
                det_size = int(args[args.index("--det-size") + 1])
            except Exception:
                pass
        from face_sorter_mvp.core.frozen_diagnostics import run_scan_probe
        return _print_json_from_diagnostic(lambda: run_scan_probe(input_dir, model=model, det_size=det_size, use_gpu=gpu))

    return None



def _is_cli_launcher() -> bool:
    try:
        return Path(sys.executable).stem.lower().endswith("_cli")
    except Exception:
        return False


def _print_cli_usage() -> int:
    print("Tuned Image Sorter CLI diagnostics")
    print("")
    print("GUI launcher:")
    print("  TunedImageSorter.exe")
    print("")
    print("Diagnostics launcher:")
    print("  TunedImageSorter_CLI.exe --runtime-preflight")
    print("  TunedImageSorter_CLI.exe --runtime-preflight --gpu")
    print("  TunedImageSorter_CLI.exe --release-check")
    print("  TunedImageSorter_CLI.exe --self-test")
    print("  TunedImageSorter_CLI.exe --diagnostics-help")
    print("  TunedImageSorter_CLI.exe --gpu-lite-runtime-status")
    print("  TunedImageSorter_CLI.exe --gpu-lite-runtime-setup --yes")
    print("  TunedImageSorter_CLI.exe --scan-probe <input_dir> [--gpu]")
    print("  TunedImageSorter_CLI.exe --support-bundle --output <result_dir>")
    print("  TunedImageSorter_CLI.exe --result-health --output <result_dir>")
    print("")
    print("TunedImageSorter.exe is intentionally windowed and may not show/capture console diagnostics.")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Launch diagnostics or import and launch the UI in the real GUI process."""
    _ensure_source_root_on_path()
    actual_argv = list(sys.argv[1:] if argv is None else argv)
    if _is_cli_launcher() and (not actual_argv or any(arg in actual_argv for arg in ("--help", "-h", "/?"))):
        return _print_cli_usage()

    handled = _handle_diagnostic_args(actual_argv)
    if handled is not None:
        return int(handled)

    if _is_cli_launcher():
        return _print_cli_usage()

    _ensure_non_null_stdio()
    try:
        from face_sorter_mvp.core.gpu_lite_runtime import ensure_gpu_lite_runtime_interactive, is_gpu_lite_package
        if is_gpu_lite_package():
            ensure_gpu_lite_runtime_interactive()
    except Exception:
        # Do not block the GUI on a bootstrap diagnostic failure.  The normal
        # preflight/status panel will still expose the runtime problem.
        pass
    from face_sorter_mvp.ui.main_window import main as ui_main
    return int(ui_main(actual_argv if argv is not None else None))


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
