# -*- coding: utf-8 -*-
"""Import-safe UI usability helpers for the optional PySide6 shell.

v69.6 / Этап 055 keeps this usability-only layer additive on top of the stable
CPU/GPU portable packaging baseline.  The helpers here intentionally avoid Qt,
ML imports, pipeline execution and project-folder mutations.  They provide
small, serializable hints and summaries that the GUI can use for readiness
labels, confirm dialogs, CPU/GPU status blocks and copy-to-clipboard actions.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .constants import SCRIPT_VERSION

UI_USABILITY_SCHEMA_VERSION = 5
UI_USABILITY_STAGE = "Этап 055"


@dataclass(frozen=True)
class UiUsabilityHint:
    """One lightweight UI hint for tooltips, startup tips or empty states."""

    key: str
    title: str
    message: str
    severity: str = "info"
    action: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class UiUsabilitySnapshot:
    """Serializable description of the additive UI usability layer."""

    schema_version: int
    app_version: str
    stage: str
    features: Tuple[str, ...]
    hints: Tuple[UiUsabilityHint, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["hints"] = [hint.to_dict() for hint in self.hints]
        return data


def _value(source: Any, key: str, default: Any = "") -> Any:
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)



def _path_from_value(value: Any) -> Path:
    """Return a user path without touching the filesystem."""
    return Path(str(value or "").strip()).expanduser()


def _resolved_for_compare(path: Path) -> Path:
    """Resolve a path for containment checks without requiring it to exist."""
    try:
        return path.resolve(strict=False)
    except TypeError:  # pragma: no cover - old Python fallback
        return path.absolute()
    except Exception:
        return path.absolute()


def is_output_inside_input(input_dir: Any, output_dir: Any) -> bool:
    """Return True when output is equal to input or nested inside input.

    This is a first-run safety check only. It does not create folders and does
    not change the backend validation contract. The GUI can warn before a run
    because placing result/output under the source folder may make later scans
    pick up generated files.
    """
    input_text = str(input_dir or "").strip()
    output_text = str(output_dir or "").strip()
    if not input_text or not output_text:
        return False
    try:
        input_path = _resolved_for_compare(_path_from_value(input_text))
        output_path = _resolved_for_compare(_path_from_value(output_text))
        if output_path == input_path:
            return True
        output_path.relative_to(input_path)
        return True
    except Exception:
        return False


def classify_path_state(value: Any, *, required: bool = False, must_exist: bool = False) -> str:
    """Return a small path state string for UI readiness checks.

    The function is deliberately read-only.  It does not create folders.
    """
    text = str(value or "").strip()
    if not text:
        return "missing" if required else "empty_optional"
    path = Path(text).expanduser()
    if must_exist and not path.exists():
        return "not_found"
    return "ok"


def build_run_summary(values_or_config: Any, *, language: str = "auto") -> str:
    """Build a concise, localized run summary for confirm dialogs/clipboard."""
    ru = str(language or "auto").lower().startswith("ru") or language == "auto"
    labels = {
        "input_dir": "Input" if not ru else "Input-папка",
        "output_dir": "Output" if not ru else "Output-папка",
        "profile": "Profile" if not ru else "Профиль",
        "mode": "Mode" if not ru else "Режим",
        "language": "Language" if not ru else "Язык",
        "use_gpu": "GPU",
        "auto_cpu_fallback": "CPU fallback" if not ru else "Откат на CPU",
        "scan_workers": "Scan workers" if not ru else "Scan workers",
        "copy_workers": "Copy workers" if not ru else "Copy workers",
        "resume_existing_output": "Resume existing output" if not ru else "Продолжать существующий output",
    }
    title = "run summary" if not ru else "сводка запуска"
    stage_label = "Stage" if not ru else "Этап"
    lines = [f"Tuned Image Sorter {SCRIPT_VERSION} — {title}", f"{stage_label}: {UI_USABILITY_STAGE}", ""]
    for key in (
        "input_dir",
        "output_dir",
        "profile",
        "mode",
        "language",
        "use_gpu",
        "auto_cpu_fallback",
        "scan_workers",
        "copy_workers",
        "resume_existing_output",
    ):
        value = _value(values_or_config, key, "")
        if value not in (None, ""):
            lines.append(f"{labels[key]}: {value}")
    return "\n".join(lines)


def build_paths_summary(values_or_config: Any, *, output_dir: Any = None, bug_report_path: Any = None, language: str = "auto") -> str:
    """Build a concise localized paths-only summary for clipboard/debugging."""
    input_dir = _value(values_or_config, "input_dir", "")
    resolved_output = output_dir if output_dir not in (None, "") else _value(values_or_config, "output_dir", "")
    reports_dir = Path(str(resolved_output)) / "reports" if resolved_output else ""
    title = "paths" if not (str(language or "auto").lower().startswith("ru") or language == "auto") else "пути"
    lines = [f"Tuned Image Sorter {SCRIPT_VERSION} — {title}", ""]
    lines.append(f"input_dir: {input_dir or ''}")
    lines.append(f"output_dir: {resolved_output or ''}")
    lines.append(f"reports_dir: {reports_dir or ''}")
    lines.append(f"bug_report_path: {bug_report_path or ''}")
    return "\n".join(lines)



def build_runtime_status_text(values_or_config: Any, *, preflight_summary: Any = None, language: str = "auto") -> str:
    """Build a short CPU/GPU status block for the first-run UI.

    The helper is read-only and import-safe.  It does not run preflight itself;
    callers may pass the compact ``runtime_preflight_summary()`` payload after
    the user clicks the environment-check button.
    """
    ru = str(language or "auto").lower().startswith("ru") or language == "auto"
    use_gpu = bool(_value(values_or_config, "use_gpu", False))
    fallback = bool(_value(values_or_config, "auto_cpu_fallback", True))
    model = _value(values_or_config, "model", "") or "auto"
    lines = []
    if ru:
        lines.append("CPU/GPU статус")
        lines.append(f"Выбранный режим: {'GPU' if use_gpu else 'CPU'}; модель: {model}; fallback на CPU: {'включён' if fallback else 'выключен'}.")
    else:
        lines.append("CPU/GPU status")
        lines.append(f"Selected mode: {'GPU' if use_gpu else 'CPU'}; model: {model}; CPU fallback: {'on' if fallback else 'off'}.")

    summary = preflight_summary if isinstance(preflight_summary, dict) else None
    if summary:
        cuda_available = bool(summary.get("cuda_provider_available"))
        gpu_name = str(summary.get("nvidia_gpu") or "").strip()
        providers = ", ".join(str(item) for item in summary.get("onnx_providers") or ())
        warnings = summary.get("warnings") or []
        errors = summary.get("errors") or []
        if ru:
            lines.append(f"Проверка окружения: {'OK' if summary.get('ok') else 'есть ошибки'}; CUDAExecutionProvider: {'доступен' if cuda_available else 'не доступен'}.")
            if gpu_name:
                lines.append(f"GPU: {gpu_name}.")
            if providers:
                lines.append(f"ONNX providers: {providers}.")
            if use_gpu and cuda_available:
                lines.append("Рекомендация: можно запускать GPU-сборку/режим для больших папок.")
            elif use_gpu and fallback:
                lines.append("Рекомендация: GPU выбран, но если CUDAExecutionProvider не запустится, приложение откатится на CPU.")
            elif use_gpu:
                lines.append("Рекомендация: GPU выбран без fallback; проверьте окружение перед большим запуском.")
            elif cuda_available:
                lines.append("Подсказка: GPU доступен. Для больших папок можно включить GPU или использовать GPU EXE.")
            else:
                lines.append("Подсказка: CPU-режим является штатным fallback и не требует GPU verification files.")
            if warnings:
                lines.append("Предупреждения: " + "; ".join(str(item) for item in warnings[:2]))
            if errors:
                lines.append("Ошибки: " + "; ".join(str(item) for item in errors[:2]))
        else:
            lines.append(f"Environment check: {'OK' if summary.get('ok') else 'has errors'}; CUDAExecutionProvider: {'available' if cuda_available else 'not available'}.")
            if gpu_name:
                lines.append(f"GPU: {gpu_name}.")
            if providers:
                lines.append(f"ONNX providers: {providers}.")
            if use_gpu and cuda_available:
                lines.append("Recommendation: GPU mode/build is suitable for larger folders.")
            elif use_gpu and fallback:
                lines.append("Recommendation: GPU is selected; the app will fall back to CPU if CUDAExecutionProvider cannot start.")
            elif use_gpu:
                lines.append("Recommendation: GPU is selected without fallback; check the environment before a large run.")
            elif cuda_available:
                lines.append("Hint: GPU is available. For large folders, enable GPU or use the GPU EXE.")
            else:
                lines.append("Hint: CPU mode is the supported fallback and does not create GPU verification files.")
            if warnings:
                lines.append("Warnings: " + "; ".join(str(item) for item in warnings[:2]))
            if errors:
                lines.append("Errors: " + "; ".join(str(item) for item in errors[:2]))
    else:
        if ru:
            lines.append("Нажмите «Проверка окружения», чтобы увидеть CUDAExecutionProvider, ONNX providers и доступный GPU без запуска ML-прогона.")
            lines.append("CPU подходит для совместимости; GPU имеет смысл для больших папок при доступном CUDAExecutionProvider.")
        else:
            lines.append("Use Environment check to see CUDAExecutionProvider, ONNX providers and detected GPU without running ML.")
            lines.append("CPU is the compatibility fallback; GPU is useful for larger folders when CUDAExecutionProvider is available.")
    return "\n".join(lines)


def build_first_run_help_text(values_or_config: Any = None, *, language: str = "auto") -> str:
    """Return compact static onboarding text for the GUI start screen."""
    ru = str(language or "auto").lower().startswith("ru") or language == "auto"
    if ru:
        return "\n".join((
            "Быстрый старт для первого запуска",
            "1. Распакуйте portable ZIP в обычную папку и запускайте TunedImageSorter.exe, не EXE из архива.",
            "2. Input — папка только с исходными фотографиями.",
            "3. Output — отдельная result/project папка вне input; туда будут записаны people, review, reports и diagnostics.",
            "4. Нажмите «Проверка окружения». Для GPU нормальный признак — CUDAExecutionProvider доступен; для CPU CUDAExecutionProvider не нужен.",
            "5. Сначала сделайте быстрый тест на 20–50 фото, затем запускайте большой архив.",
            "6. После завершения сначала смотрите people, затем review, reports и diagnostics.",
            "7. review/no_faces — фото без найденных лиц; review/unknown_faces — лица найдены, но не попали в уверенный person cluster.",
        ))
    return "\n".join((
        "First-run quick start",
        "1. Extract the portable ZIP to a normal folder and run TunedImageSorter.exe from the extracted folder, not from inside the archive.",
        "2. Input is the source photo folder only.",
        "3. Output is a separate result/project folder outside input; it contains people, review, reports and diagnostics.",
        "4. Run Environment check. For GPU, CUDAExecutionProvider should be available; for CPU, CUDAExecutionProvider is not required.",
        "5. First test 20–50 photos, then run the large archive.",
        "6. After completion, inspect people first, then review, reports and diagnostics.",
        "7. review/no_faces means no face was found; review/unknown_faces means faces were found but not assigned to a confident person cluster.",
    ))


def build_onboarding_checklist_text(values_or_config: Any = None, *, preflight_summary: Any = None, language: str = "auto") -> str:
    """Build a dynamic first-run checklist from current UI values.

    This helper is read-only and import-safe. It is intentionally separate from
    backend validation so onboarding can warn users without changing pipeline
    stage logic, report formats or project metadata.
    """
    values = values_or_config or {}
    ru = str(language or "auto").lower().startswith("ru") or language == "auto"
    input_dir = _value(values, "input_dir", "")
    output_dir = _value(values, "output_dir", "")
    use_gpu = bool(_value(values, "use_gpu", False))
    fallback = bool(_value(values, "auto_cpu_fallback", True))
    summary = preflight_summary if isinstance(preflight_summary, dict) else None
    input_state = classify_path_state(input_dir, required=True, must_exist=True)
    output_state = classify_path_state(output_dir, required=False, must_exist=False)
    output_nested = is_output_inside_input(input_dir, output_dir)

    if ru:
        lines: List[str] = ["Первый запуск / checklist"]
        if input_state == "missing":
            lines.append("[1/5] Input: выберите папку с фотографиями.")
        elif input_state == "not_found":
            lines.append(f"[1/5] Input: папка не найдена — {input_dir}")
        else:
            lines.append(f"[1/5] Input: OK — {input_dir}")

        if output_state == "empty_optional":
            lines.append("[2/5] Output: нажмите «Авто» или выберите result-папку явно.")
        elif output_nested:
            lines.append("[2/5] Output: предупреждение — result/output находится внутри input. Лучше выбрать папку вне исходных фото.")
        else:
            lines.append(f"[2/5] Output: OK — {output_dir}")

        if summary:
            cuda_ok = bool(summary.get("cuda_provider_available"))
            ok = bool(summary.get("ok"))
            lines.append(f"[3/5] Окружение: {'OK' if ok else 'есть ошибки'}; CUDAExecutionProvider: {'доступен' if cuda_ok else 'не доступен'}.")
            if cuda_ok and not use_gpu:
                lines.append("[4/5] GPU: доступен — для больших папок можно включить GPU или запустить GPU EXE.")
            elif use_gpu and cuda_ok:
                lines.append("[4/5] GPU: выбран и доступен.")
            elif use_gpu and fallback:
                lines.append("[4/5] GPU: выбран, но при проблеме приложение сможет откатиться на CPU.")
            elif use_gpu:
                lines.append("[4/5] GPU: выбран без подтверждённого CUDAExecutionProvider; перед большим запуском проверьте окружение.")
            else:
                lines.append("[4/5] CPU: выбран совместимый fallback-режим.")
        else:
            lines.append("[3/5] Окружение: нажмите «Проверка окружения» перед первым большим запуском.")
            lines.append(f"[4/5] Режим: {'GPU' if use_gpu else 'CPU'}; fallback на CPU: {'включён' if fallback else 'выключен'}.")

        lines.append("[5/5] Быстрый тест: сначала запустите 20–50 фото в отдельную result-папку; затем проверьте people, review и reports.")
        return "\n".join(lines)

    lines = ["First run / checklist"]
    if input_state == "missing":
        lines.append("[1/5] Input: choose the source photo folder.")
    elif input_state == "not_found":
        lines.append(f"[1/5] Input: folder not found — {input_dir}")
    else:
        lines.append(f"[1/5] Input: OK — {input_dir}")

    if output_state == "empty_optional":
        lines.append("[2/5] Output: use Auto or choose an explicit result folder.")
    elif output_nested:
        lines.append("[2/5] Output: warning — result/output is inside input. Prefer a folder outside the source photos.")
    else:
        lines.append(f"[2/5] Output: OK — {output_dir}")

    if summary:
        cuda_ok = bool(summary.get("cuda_provider_available"))
        ok = bool(summary.get("ok"))
        lines.append(f"[3/5] Environment: {'OK' if ok else 'has errors'}; CUDAExecutionProvider: {'available' if cuda_ok else 'not available'}.")
        if cuda_ok and not use_gpu:
            lines.append("[4/5] GPU: available — for large folders, enable GPU or use the GPU EXE.")
        elif use_gpu and cuda_ok:
            lines.append("[4/5] GPU: selected and available.")
        elif use_gpu and fallback:
            lines.append("[4/5] GPU: selected; the app can fall back to CPU if needed.")
        elif use_gpu:
            lines.append("[4/5] GPU: selected without confirmed CUDAExecutionProvider; check the environment before a large run.")
        else:
            lines.append("[4/5] CPU: selected as the compatible fallback mode.")
    else:
        lines.append("[3/5] Environment: run Environment check before the first large job.")
        lines.append(f"[4/5] Mode: {'GPU' if use_gpu else 'CPU'}; CPU fallback: {'on' if fallback else 'off'}.")

    lines.append("[5/5] Quick test: first run 20–50 photos into a separate result folder; then inspect people, review and reports.")
    return "\n".join(lines)



def build_beginner_action_map_text(values_or_config: Any = None, *, language: str = "auto") -> str:
    """Return a compact do-this-next map for non-technical first-run users.

    The helper is read-only and import-safe. It does not inspect images, run
    preflight or mutate project/result folders.
    """
    values = values_or_config or {}
    ru = str(language or "auto").lower().startswith("ru") or language == "auto"
    input_dir = str(_value(values, "input_dir", "") or "").strip()
    output_dir = str(_value(values, "output_dir", "") or "").strip()
    output_nested = is_output_inside_input(input_dir, output_dir)
    use_gpu = bool(_value(values, "use_gpu", False))
    if ru:
        lines = [
            "Маршрут для новичка",
            "1. Откройте TunedImageSorter.exe из распакованной portable-папки.",
            "2. Выберите input: только исходные фото, без result/reports/final внутри.",
            "3. Выберите output: отдельная новая result-папка вне input.",
            "4. Нажмите «Проверка окружения»; для первого большого запуска не пропускайте этот шаг.",
            "5. Нажмите «Быстрый тест» и проверьте 20–50 фото перед полным архивом.",
            "6. После «Старт» смотрите раздел «Ход выполнения», после завершения — «Итог запуска».",
            "7. Если что-то непонятно, создайте bug-report/support-bundle и отправьте ZIP разработчику.",
        ]
        lines.append(f"Текущий режим: {'GPU' if use_gpu else 'CPU'}.")
        if not input_dir:
            lines.append("Сейчас не выбран input — это первый обязательный шаг.")
        if not output_dir:
            lines.append("Output пока пустой — нажмите «Авто» или выберите новую result-папку.")
        elif output_nested:
            lines.append("Предупреждение: output находится внутри input; выберите другую result-папку.")
        return "\n".join(lines)
    lines = [
        "Beginner action map",
        "1. Open TunedImageSorter.exe from the extracted portable folder.",
        "2. Choose input: source photos only, with no result/reports/final folder inside it.",
        "3. Choose output: a separate new result folder outside input.",
        "4. Run Environment check; do not skip it before the first large run.",
        "5. Use Quick test and verify 20–50 photos before processing the full archive.",
        "6. After Start, watch Progress; after completion, open Run result.",
        "7. If anything is unclear, create a bug-report/support-bundle ZIP for the developer.",
    ]
    lines.append(f"Current mode: {'GPU' if use_gpu else 'CPU'}.")
    if not input_dir:
        lines.append("Input is not selected yet — this is the first required step.")
    if not output_dir:
        lines.append("Output is empty — use Auto or choose a new result folder.")
    elif output_nested:
        lines.append("Warning: output is inside input; choose another result folder.")
    return "\n".join(lines)

def build_quick_test_help_text(values_or_config: Any = None, *, language: str = "auto") -> str:
    """Return a non-mutating quick-test guide for first-run users."""
    values = values_or_config or {}
    ru = str(language or "auto").lower().startswith("ru") or language == "auto"
    input_dir = str(_value(values, "input_dir", "") or "").strip()
    output_dir = str(_value(values, "output_dir", "") or "").strip()
    if ru:
        lines = [
            "Быстрый тест на маленькой папке",
            "1. Создайте отдельную папку с 20–50 фотографиями.",
            "2. Укажите её как input.",
            "3. Нажмите «Авто» для output или выберите новую result-папку вне input.",
            "4. Нажмите «Проверка окружения». Для GPU убедитесь, что CUDAExecutionProvider доступен.",
            "5. Запустите режим all. После завершения откройте result, reports и diagnostics кнопками UI.",
            "6. Для большого архива используйте те же настройки только после успешного малого теста.",
        ]
        if input_dir:
            lines.append(f"Текущий input: {input_dir}")
        if output_dir:
            lines.append(f"Текущий output: {output_dir}")
        return "\n".join(lines)
    lines = [
        "Quick test on a small folder",
        "1. Create a separate folder with 20–50 photos.",
        "2. Set that folder as input.",
        "3. Use Auto for output or choose a new result folder outside input.",
        "4. Run Environment check. For GPU, make sure CUDAExecutionProvider is available.",
        "5. Run mode=all. After completion, open output, reports and diagnostics with the UI buttons.",
        "6. Use the same settings for the large archive only after the small test succeeds.",
    ]
    if input_dir:
        lines.append(f"Current input: {input_dir}")
    if output_dir:
        lines.append(f"Current output: {output_dir}")
    return "\n".join(lines)

def get_ui_usability_hints(language: str = "auto") -> Tuple[UiUsabilityHint, ...]:
    """Return localized hints used by the optional UI without importing Qt."""
    ru = str(language or "auto").lower().startswith("ru") or language == "auto"
    if ru:
        return (
            UiUsabilityHint("input_required", "Input обязателен", "Выберите папку с фотографиями. Кнопка Старт будет недоступна, пока input пустой или не найден.", "info", "Нажмите «Выбрать…» рядом с input."),
            UiUsabilityHint("output_recommended", "Output рекомендуется", "Output можно оставить пустым, но удобнее нажать «Авто», чтобы заранее видеть result-папку.", "info", "Нажмите «Авто» рядом с output."),
            UiUsabilityHint("copy_summary", "Copy summary", "Кнопки Copy summary и Copy paths копируют текущую конфигурацию/пути без создания файлов.", "info", "Используйте их для быстрой диагностики."),
            UiUsabilityHint("cpu_gpu_status", "CPU/GPU статус", "Блок CPU/GPU объясняет выбранный режим, fallback и результат проверки окружения без запуска ML-прогона.", "info", "Нажмите «Проверка окружения» перед большим запуском."),
            UiUsabilityHint("output_inside_input", "Output внутри input", "Если result/output находится внутри input, последующие запуски могут начать видеть сгенерированные файлы как исходные.", "warning", "Выберите output вне папки с исходными фото."),
            UiUsabilityHint("quick_test", "Быстрый тест", "Перед первым большим запуском проверьте 20–50 фото в отдельной result-папке.", "info", "Нажмите «Быстрый тест» для памятки."),
            UiUsabilityHint("beginner_action_map", "Маршрут новичка", "Главный экран показывает безопасный порядок действий: input, output, проверка окружения, быстрый тест, старт, итог.", "info", "Идите по шагам сверху вниз."),
        )
    return (
        UiUsabilityHint("input_required", "Input is required", "Choose the folder with photos. Start remains disabled while input is empty or missing.", "info", "Use the Browse button next to input."),
        UiUsabilityHint("output_recommended", "Output is recommended", "Output can be empty, but Auto makes the result folder explicit before starting.", "info", "Use Auto next to output."),
        UiUsabilityHint("copy_summary", "Copy summary", "Copy summary and Copy paths copy current settings/paths without creating files.", "info", "Use them for quick diagnostics."),
        UiUsabilityHint("cpu_gpu_status", "CPU/GPU status", "The CPU/GPU block explains selected mode, fallback and environment-check results without running ML.", "info", "Run Environment check before a large job."),
        UiUsabilityHint("output_inside_input", "Output inside input", "If result/output is inside input, later runs may see generated files as source photos.", "warning", "Choose output outside the source photo folder."),
        UiUsabilityHint("quick_test", "Quick test", "Before the first large run, test 20–50 photos in a separate result folder.", "info", "Use the Quick test button for the checklist."),
        UiUsabilityHint("beginner_action_map", "Beginner action map", "The start screen shows the safe order: input, output, environment check, quick test, start, result.", "info", "Follow the steps from top to bottom."),
    )


def ui_usability_snapshot(language: str = "auto") -> UiUsabilitySnapshot:
    """Return the import-safe UI usability contract snapshot."""
    return UiUsabilitySnapshot(
        schema_version=UI_USABILITY_SCHEMA_VERSION,
        app_version=SCRIPT_VERSION,
        stage=UI_USABILITY_STAGE,
        features=(
            "form_readiness_label",
            "required_path_highlight",
            "disabled_start_until_input_ready",
            "copy_run_summary",
            "copy_paths",
            "richer_confirm_dialog",
            "empty_state_messages",
            "button_tooltips",
            "cpu_gpu_status_block",
            "first_run_onboarding_text",
            "richer_result_summary",
            "open_diagnostics_button",
            "output_inside_input_warning",
            "dynamic_first_run_checklist",
            "quick_test_help_button",
            "beginner_action_map_text",
            "portable_first_run_docs",
        ),
        hints=get_ui_usability_hints(language),
    )


__all__ = [
    "UI_USABILITY_SCHEMA_VERSION",
    "UI_USABILITY_STAGE",
    "UiUsabilityHint",
    "UiUsabilitySnapshot",
    "classify_path_state",
    "build_run_summary",
    "build_paths_summary",
    "build_runtime_status_text",
    "build_first_run_help_text",
    "build_onboarding_checklist_text",
    "build_beginner_action_map_text",
    "build_quick_test_help_text",
    "is_output_inside_input",
    "get_ui_usability_hints",
    "ui_usability_snapshot",
]
