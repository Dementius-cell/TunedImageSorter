# -*- coding: utf-8 -*-
"""Import-safe diagnostics command-center help.

v69.6 / Этап 055 keeps diagnostics guidance in one small, ASCII-safe helper so
both source CLI and frozen TunedImageSorter_CLI.exe can show the same decision tree
without importing Qt/ML packages.
"""
from __future__ import annotations

from typing import Sequence

from .constants import SCRIPT_VERSION

DIAGNOSTICS_HELP_STAGE = "Этап 055"


def _normalize_language(language: str | None) -> str:
    value = (language or "en").strip().lower()
    if value.startswith("ru"):
        return "ru"
    return "en"


def diagnostics_help_text(language: str | None = "en") -> str:
    """Return a short diagnostics decision tree.

    English output is intentionally ASCII-only. Frozen CLI uses English by
    default to avoid Windows console code-page mojibake; Russian docs on disk
    remain UTF-8.
    """
    if _normalize_language(language) == "ru":
        return "\n".join([
            f"Tuned Image Sorter diagnostics command center - {SCRIPT_VERSION} / {DIAGNOSTICS_HELP_STAGE}",
            "",
            "Запускайте diagnostics через TunedImageSorter_CLI.exe, не через TunedImageSorter.exe.",
            "GUI launcher TunedImageSorter.exe специально windowed и может не показывать консольный вывод.",
            "",
            "Что запускать:",
            "  1. Приложение не стартует или странно ведет себя:",
            "     TunedImageSorter_CLI.exe --runtime-preflight",
            "  2. GPU не используется или есть подозрение на CUDA/NVIDIA driver:",
            "     TunedImageSorter_CLI.exe --runtime-preflight --gpu",
            "  2a. GPU Lite: проверить/установить локальный runtime:",
            "     TunedImageSorter_CLI.exe --gpu-lite-runtime-status",
            "     TunedImageSorter_CLI.exe --gpu-lite-runtime-setup --yes",
            "  3. Нужно проверить, что portable package собран корректно:",
            "     TunedImageSorter_CLI.exe --release-check",
            "  4. Нужно проверить чтение конкретной input-папки:",
            "     TunedImageSorter_CLI.exe --scan-probe <input_dir> [--gpu]",
            "  5. Результат сортировки выглядит подозрительно:",
            "     TunedImageSorter_CLI.exe --result-health --output <result_dir>",
            "  6. Нужно отправить разработчику диагностический ZIP:",
            "     TunedImageSorter_CLI.exe --support-bundle --output <result_dir>",
            "",
            "Что отправлять при проблеме:",
            "  - support-bundle ZIP из папки bug_reports;",
            "  - кратко что нажали перед проблемой;",
            "  - вывод --runtime-preflight / --runtime-preflight --gpu, если проблема с запуском или GPU.",
        ])
    return "\n".join([
        f"Tuned Image Sorter diagnostics command center - {SCRIPT_VERSION} / Stage 055",
        "",
        "Run diagnostics through TunedImageSorter_CLI.exe, not TunedImageSorter.exe.",
        "TunedImageSorter.exe is intentionally windowed and may not show/capture console output.",
        "",
        "What to run:",
        "  1. App does not start or behaves strangely:",
        "     TunedImageSorter_CLI.exe --runtime-preflight",
        "  2. GPU is not used or CUDA/NVIDIA driver is suspicious:",
        "     TunedImageSorter_CLI.exe --runtime-preflight --gpu",
        "  2a. GPU Lite: check/install local runtime:",
        "     TunedImageSorter_CLI.exe --gpu-lite-runtime-status",
        "     TunedImageSorter_CLI.exe --gpu-lite-runtime-setup --yes",
        "  3. Check whether the portable package is built correctly:",
        "     TunedImageSorter_CLI.exe --release-check",
        "  4. Check whether a specific input folder can be scanned:",
        "     TunedImageSorter_CLI.exe --scan-probe <input_dir> [--gpu]",
        "  5. Sorting result looks wrong or incomplete:",
        "     TunedImageSorter_CLI.exe --result-health --output <result_dir>",
        "  6. Send a diagnostic ZIP to the developer:",
        "     TunedImageSorter_CLI.exe --support-bundle --output <result_dir>",
        "",
        "What to send when reporting a problem:",
        "  - the support-bundle ZIP from bug_reports;",
        "  - a short description of what was clicked before the problem;",
        "  - --runtime-preflight / --runtime-preflight --gpu output if startup or GPU is involved.",
    ])


def has_language_arg(args: Sequence[str]) -> bool:
    return any(arg == "--lang" or str(arg).startswith("--lang=") for arg in args)


def language_from_args(args: Sequence[str], default: str = "en") -> str:
    for idx, arg in enumerate(args):
        if arg == "--lang" and idx + 1 < len(args):
            return _normalize_language(str(args[idx + 1]))
        if str(arg).startswith("--lang="):
            return _normalize_language(str(arg).split("=", 1)[1])
    return _normalize_language(default)


__all__ = [
    "DIAGNOSTICS_HELP_STAGE",
    "diagnostics_help_text",
    "has_language_arg",
    "language_from_args",
]
