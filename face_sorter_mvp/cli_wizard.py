# -*- coding: utf-8 -*-
"""Interactive console wizard for Tuned Image Sorter.

Этап 021 / v62 keeps the interactive CLI wizard out of the legacy
``face_sorter_mvp.py`` monolith.  The heavy pipeline and ML algorithms still live
in the legacy module; this file contains only console prompts, profile selection,
input/output selection, resume menu, and CLI-wizard helpers.

The few runtime/dependency helpers that are still legacy-owned are accessed
lazily through ``_legacy_core()``.  This keeps imports safe for future UI code and
reduces Windows multiprocessing spawn risk.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:  # package mode
    from .core.constants import DEFAULT_PROFILE, KNOWN_MODELS
    from .core.project_state import (
        describe_run_state_for_user,
        ensure_dir,
        ensure_project_structure,
        find_unfinished_result_dirs,
        read_run_state,
        resume_mode_from_state,
        write_run_state,
    )
except ImportError:  # script-folder mode
    from core.constants import DEFAULT_PROFILE, KNOWN_MODELS  # type: ignore
    from core.project_state import (  # type: ignore
        describe_run_state_for_user,
        ensure_dir,
        ensure_project_structure,
        find_unfinished_result_dirs,
        read_run_state,
        resume_mode_from_state,
        write_run_state,
    )


def _legacy_core() -> Any:
    try:
        from . import face_sorter_mvp as legacy
    except ImportError:
        import face_sorter_mvp as legacy  # type: ignore
    return legacy


def tr(key: str, **kwargs: Any) -> str:
    return _legacy_core().tr(key, **kwargs)


def lang_text(ru: str, en: str) -> str:
    return _legacy_core().lang_text(ru, en)


def _current_lang() -> str:
    return str(getattr(_legacy_core(), "LANG", "en"))


def ask_yes_no_strict(prompt: str, default: Optional[bool] = None) -> bool:
    return _legacy_core().ask_yes_no_strict(prompt, default)


def ensure_dependencies(args: argparse.Namespace) -> None:
    return _legacy_core().ensure_dependencies(args)


def cached_env_state_valid(max_age_days: int = 14) -> Optional[Dict[str, Any]]:
    return _legacy_core().cached_env_state_valid(max_age_days=max_age_days)


def save_gpu_cache(has_nvidia: bool, providers: Optional[List[str]] = None, smoke_results: Optional[Dict[str, Dict[str, Any]]] = None, det_size: Optional[int] = None) -> None:
    return _legacy_core().save_gpu_cache(has_nvidia, providers=providers, smoke_results=smoke_results, det_size=det_size)


def available_onnx_providers() -> List[str]:
    return _legacy_core().available_onnx_providers()


def gpu_all_models_smoke_test(det_size: int = 640, models: Optional[Sequence[str]] = None, verbose: bool = True) -> Dict[str, Dict[str, Any]]:
    return _legacy_core().gpu_all_models_smoke_test(det_size=det_size, models=models, verbose=verbose)


def allowed_gpu_models_from_smoke_results(results: Optional[Dict[str, Dict[str, Any]]]) -> Optional[List[str]]:
    return _legacy_core().allowed_gpu_models_from_smoke_results(results)


def diagnose_gpu_environment(verbose: bool = True) -> Dict[str, Any]:
    return _legacy_core().diagnose_gpu_environment(verbose=verbose)


def install_onnxruntime_gpu_stack(force_reinstall: bool = False) -> bool:
    return _legacy_core().install_onnxruntime_gpu_stack(force_reinstall=force_reinstall)


class _LegacyMapping:
    """Lazy mapping proxy for legacy dictionaries not moved during Этап 003."""

    def __init__(self, attr_name: str):
        self.attr_name = attr_name

    def _mapping(self) -> Dict[str, Any]:
        return getattr(_legacy_core(), self.attr_name)

    def get(self, key: str, default: Any = None) -> Any:
        return self._mapping().get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self._mapping()[key]

    def keys(self):
        return self._mapping().keys()

    def items(self):
        return self._mapping().items()

    def __iter__(self):
        return iter(self._mapping())

    def __contains__(self, key: object) -> bool:
        return key in self._mapping()


MODEL_INFO = _LegacyMapping("MODEL_INFO")
QUALITY_PROFILES = _LegacyMapping("QUALITY_PROFILES")


def choose_folder_dialog(title: str) -> Optional[str]:
    """Open a native folder picker when tkinter is available."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(title=title)
        root.destroy()
        return selected or None
    except Exception:
        return None


def ask_text(prompt: str, default: Optional[str] = None) -> str:
    """Ask a text question in the console with an optional default."""
    suffix = f" [{default}]" if default is not None else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value if value else ("" if default is None else str(default))


def print_wrapped(text: str, indent: str = "  ") -> None:
    """Print a paragraph wrapped for console readability."""
    # Small dependency-free wrapper for Russian/English helper text.
    width = 96
    words = str(text).split()
    line = indent
    for word in words:
        if len(line) + len(word) + 1 > width:
            print(line.rstrip())
            line = indent + word + " "
        else:
            line += word + " "
    if line.strip():
        print(line.rstrip())


def ask_bool(prompt: str, default: bool, description: str = "") -> bool:
    """Ask a strict yes/no question through the shared parser."""
    if description:
        print_wrapped(description)
    return ask_yes_no_strict(prompt, default)


def choose_from_options(prompt: str, options: Sequence[Dict[str, Any]], default_value: Any) -> Any:
    """Numbered choice for parameters with a limited set of valid values."""
    print(f"\n{prompt}")
    default_index = None
    for idx, opt in enumerate(options, start=1):
        if opt.get("value") == default_value and default_index is None:
            default_index = idx
        marker = tr("default_marker") if opt.get("value") == default_value else ""
        print(f"  {idx}. {opt['label']}{marker}")
        if opt.get("help"):
            print_wrapped(str(opt["help"]), indent="     ")
    default_raw = str(default_index or default_value)
    while True:
        raw = ask_text(tr("enter_number"), default_raw).strip()
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(options):
                return options[idx - 1]["value"]
        for opt in options:
            if str(raw).lower() == str(opt.get("value", "")).lower():
                return opt["value"]
        print(tr("unknown_choice", raw=raw, max=len(options)))


def ask_int_range(prompt: str, default: Optional[int], min_value: Optional[int], max_value: Optional[int],
                  description: str, lower_effect: str, higher_effect: str,
                  allow_none: bool = False, none_label: str = "None") -> Optional[int]:
    """Prompt for an integer value with default, bounds and explanatory text."""
    print(f"\n{prompt}")
    print_wrapped(description)
    range_bits = []
    if min_value is not None:
        range_bits.append(tr("minimum", value=min_value))
    if max_value is not None:
        range_bits.append(tr("maximum", value=max_value))
    if range_bits:
        print_wrapped(tr("range", range=", ".join(range_bits)))
    if allow_none:
        print_wrapped(tr("can_enter_none", none_label=none_label))
    print_wrapped(tr("lower_value", text=lower_effect))
    print_wrapped(tr("higher_value", text=higher_effect))
    while True:
        default_text = none_label if default is None else str(default)
        raw = ask_text(tr("enter_value"), default_text).strip()
        if allow_none and raw.lower() in {"", "none", "null", "нет", "auto", "авто", none_label.lower()}:
            return None
        try:
            value = int(raw)
        except Exception:
            print(tr("enter_int"))
            continue
        if min_value is not None and value < min_value:
            print(lang_text("Значение ниже рекомендуемого минимума", "Value is below the recommended minimum"), min_value, lang_text("Можно оставить, но результат может быть нестабильным.", "You may keep it, but the result may be unstable."))
            if not ask_bool("Оставить это значение?", False):
                continue
        if max_value is not None and value > max_value:
            print(tr("above_max", max_value=max_value))
            if not ask_bool("Оставить это значение?", False):
                continue
        return value


def ask_float_range(prompt: str, default: float, min_value: float, max_value: float,
                    description: str, lower_effect: str, higher_effect: str) -> float:
    """Prompt for a float value with default, bounds and explanatory text."""
    print(f"\n{prompt}")
    print_wrapped(description)
    print_wrapped(f"Рекомендуемый диапазон: от {min_value} до {max_value}.")
    print_wrapped(tr("lower_value", text=lower_effect))
    print_wrapped(tr("higher_value", text=higher_effect))
    while True:
        raw = ask_text("Введите значение", str(default)).replace(",", ".").strip()
        try:
            value = float(raw)
        except Exception:
            print(lang_text("Введите число, например 0.55", "Enter a number, for example 0.55"))
            continue
        if value < min_value:
            print(tr("below_min", min_value=min_value))
            if not ask_bool("Оставить это значение?", False):
                continue
        if value > max_value:
            print(tr("above_max", max_value=max_value))
            if not ask_bool("Оставить это значение?", False):
                continue
        return value


def model_help_text(model: str, use_gpu: bool) -> str:
    """Return one-line model descriptions for the interactive model menu."""
    info = MODEL_INFO.get(model, {})
    device_text = (
        "GPU: выше скорость при рабочем CUDAExecutionProvider; если CUDA не настроена, будет диагностика и откат на CPU."
        if use_gpu else
        "CPU: медленнее, зато почти всегда запускается; для ускорения лучше закрыть браузер/игры/тяжёлые приложения."
    )
    parts = [
        str(info.get("short", "")),
        str(info.get("details", "")),
        "Скорость: " + str(info.get("speed", "зависит от ПК")),
        "Точность: " + str(info.get("accuracy", "см. таблицу InsightFace")),
        device_text,
    ]
    return " ".join(x for x in parts if x)


def print_model_reference() -> None:
    """Print model descriptions and CPU/GPU notes for users."""
    print("\n" + lang_text("Справка по model packs InsightFace:", "InsightFace model pack help:"))
    for model in KNOWN_MODELS:
        info = MODEL_INFO.get(model, {})
        print(f"  - {model}: {info.get('short', '')}")
        print_wrapped(str(info.get("details", "")), indent="      ")
        print_wrapped("Точность: " + str(info.get("accuracy", "")), indent="      ")
    print_wrapped("Для вашей задачи обычно лучший старт: buffalo_l на CPU/GPU. Если хочется чуть быстрее — buffalo_m. Если слабый ПК или быстрый тест — buffalo_s/buffalo_sc, но кластеры могут быть хуже.")


def choose_model_and_runtime(default_model: str, default_gpu: bool, allow_gpu: bool = True, gpu_allowed_models: Optional[Sequence[str]] = None) -> Tuple[str, bool]:
    """Ask user which model/runtime combination to use."""
    print("\n" + lang_text("Справка по CPU/GPU:", "CPU/GPU help:"))
    print_wrapped("CPU: работает почти на любом компьютере, но медленнее. На больших архивах лучше закрыть игры, браузер и тяжёлые приложения, чтобы ускорить процесс.")
    print_wrapped("GPU: обычно быстрее, но требуется NVIDIA-видеокарта, свежий драйвер и рабочий CUDAExecutionProvider в ONNX Runtime. Скрипт показывает GPU-варианты только если CUDAExecutionProvider уже найден.")
    if not allow_gpu:
        print_wrapped("Сейчас CUDAExecutionProvider не найден или ни одна модель не прошла smoke-test, поэтому в списке будут только CPU-варианты. Это сделано специально: чтобы пользователь не выбрал GPU, который фактически всё равно работает на CPU.")
    elif gpu_allowed_models is not None:
        good = set(gpu_allowed_models)
        print_wrapped("GPU smoke-test уже выполнен. GPU-варианты будут показаны только для моделей со статусом OK: " + (", ".join(gpu_allowed_models) if gpu_allowed_models else "нет"))
    print_model_reference()

    options: List[Dict[str, Any]] = []
    for model in KNOWN_MODELS:
        options.append({
            "label": f"модель распознавания {model}{' (экспериментальная)' if MODEL_INFO.get(model, {}).get('experimental') else ''} — выполняется на CPU",
            "value": (model, False),
            "help": model_help_text(model, False),
        })
        if allow_gpu and (gpu_allowed_models is None or model in set(gpu_allowed_models)):
            options.append({
                "label": f"модель распознавания {model}{' (экспериментальная)' if MODEL_INFO.get(model, {}).get('experimental') else ''} — выполняется на GPU",
                "value": (model, True),
                "help": model_help_text(model, True),
            })
        elif allow_gpu and gpu_allowed_models is not None:
            # Keep CPU option only; the model failed real GPU smoke-test.
            pass
    if gpu_allowed_models is not None and default_model not in set(gpu_allowed_models):
        default_gpu = False
    default_choice = (default_model, default_gpu if allow_gpu else False)
    selected = choose_from_options(
        "Выберите модель распознавания и устройство выполнения",
        options,
        default_choice,
    )
    return selected[0], bool(selected[1])


def interactive_gpu_startup_wizard(cfg: Dict[str, Any]) -> bool:
    """Ask about NVIDIA GPU, optionally install Python GPU packages, and return whether GPU options are usable.

    This intentionally does not install NVIDIA system drivers. It only manages Python packages and
    then checks whether ONNX Runtime exposes CUDAExecutionProvider.
    """
    print("\n" + tr("gpu_title"))
    print_wrapped(tr("gpu_intro"))

    cached = cached_env_state_valid()
    if cached and not bool(cfg.get("force_env_check", False)):
        cached_has_nvidia = cached.get("has_nvidia_answer")
        cached_allowed = cached.get("gpu_allowed_models")
        cached_results = cached.get("gpu_model_smoke_results")
        cached_det_size = cached.get("smoke_test_det_size")
        current_det_size = int(cfg.get("det_size", 640) or 640)
        updated = cached.get("updated_at", "?")
        if cached_has_nvidia is False:
            if ask_bool(
                lang_text("Использовать сохранённый результат: NVIDIA GPU ранее не выбиралась/не найдена?", "Use cached result: NVIDIA GPU was previously not selected/found?"),
                True,
                lang_text(f"Кэш окружения от {updated}. Для новой проверки ответьте 'нет'.", f"Environment cache from {updated}. Answer 'no' to recheck."),
            ):
                return False
        if cached_has_nvidia is True and cached_allowed and cached_det_size == current_det_size:
            if ask_bool(
                lang_text("Использовать сохранённые результаты GPU smoke-test?", "Use cached GPU smoke-test results?"),
                True,
                lang_text(f"Кэш от {updated}; GPU OK: {', '.join(cached_allowed)}. Для повторного smoke-test ответьте 'нет'.", f"Cache from {updated}; GPU OK: {', '.join(cached_allowed)}. Answer 'no' to run smoke-test again."),
            ):
                cfg["gpu_model_smoke_results"] = cached_results
                cfg["gpu_allowed_models"] = cached_allowed
                print(tr("gpu_options_for"), ", ".join(cached_allowed))
                return True

    has_nvidia = ask_bool(
        tr("has_nvidia"),
        False,
        tr("has_nvidia_help"),
    )
    if not has_nvidia:
        save_gpu_cache(False, providers=[])
        print(tr("gpu_skipped"))
        return False

    print("\n" + tr("check_cuda_no_install"))
    providers = available_onnx_providers()
    print(tr("onnx_providers"), providers or tr("cannot_determine"))
    if "CUDAExecutionProvider" in providers:
        print(tr("cuda_found_no_install"))
        print_wrapped("GPU-варианты будут доступны только после проверки конкретных моделей или, если проверку пропустить, с повторной проверкой выбранной модели перед сканированием.")
        cfg["auto_gpu_install"] = False
        if ask_bool(
            tr("check_all_models_gpu"),
            True,
            tr("check_all_models_help")
        ):
            results = gpu_all_models_smoke_test(det_size=int(cfg.get("det_size", 640) or 640), verbose=True)
            cfg["gpu_model_smoke_results"] = results
            cfg["gpu_allowed_models"] = allowed_gpu_models_from_smoke_results(results)
            save_gpu_cache(True, providers=providers, smoke_results=results, det_size=int(cfg.get("det_size", 640) or 640))
            if cfg["gpu_allowed_models"]:
                print(tr("gpu_options_for"), ", ".join(cfg["gpu_allowed_models"]))
                return True
            print(tr("no_gpu_models_ok"))
            return False
        cfg["gpu_model_smoke_results"] = None
        cfg["gpu_allowed_models"] = None
        save_gpu_cache(True, providers=providers, smoke_results=None, det_size=int(cfg.get("det_size", 640) or 640))
        return True

    print("\n" + tr("gpu_can_do"))
    print_wrapped(tr("gpu_can_1"))
    print_wrapped(tr("gpu_can_2"))
    print_wrapped(tr("gpu_cannot"))

    wants_install = ask_bool(
        tr("install_gpu_packages"),
        True,
        tr("install_gpu_help"),
    )
    if wants_install:
        cfg["auto_gpu_install"] = True
        ok = install_onnxruntime_gpu_stack()
        if not ok:
            print(tr("gpu_install_failed"))
        importlib.invalidate_caches()
    else:
        cfg["auto_gpu_install"] = False

    print("\n" + tr("recheck_cuda"))
    providers = available_onnx_providers()
    print(tr("onnx_providers"), providers or tr("cannot_determine"))
    if "CUDAExecutionProvider" in providers:
        print(tr("cuda_found"))
        if ask_bool(
            tr("check_all_models_gpu"),
            True,
            tr("check_all_models_help")
        ):
            results = gpu_all_models_smoke_test(det_size=int(cfg.get("det_size", 640) or 640), verbose=True)
            cfg["gpu_model_smoke_results"] = results
            cfg["gpu_allowed_models"] = allowed_gpu_models_from_smoke_results(results)
            save_gpu_cache(True, providers=providers, smoke_results=results, det_size=int(cfg.get("det_size", 640) or 640))
            if cfg["gpu_allowed_models"]:
                print(tr("gpu_options_for"), ", ".join(cfg["gpu_allowed_models"]))
                return True
            print(tr("no_gpu_models_ok"))
            return False
        cfg["gpu_model_smoke_results"] = None
        cfg["gpu_allowed_models"] = None
        save_gpu_cache(True, providers=providers, smoke_results=None, det_size=int(cfg.get("det_size", 640) or 640))
        print(tr("gpu_model_check_skipped"))
        return True

    save_gpu_cache(True, providers=providers, smoke_results=None, det_size=int(cfg.get("det_size", 640) or 640))
    print(tr("cuda_not_found_cpu_only"))
    if ask_bool(tr("show_gpu_diagnostics"), True):
        diagnose_gpu_environment(verbose=True)
    return False


def ask_folder(title: str, must_exist: bool) -> str:
    """Ask for a folder path using dialog or manual path input."""
    print(f"\n{title}")
    use_dialog = ask_bool(tr("open_folder_dialog"), True)
    selected = choose_folder_dialog(title) if use_dialog else None
    if not selected:
        selected = ask_text(tr("enter_folder_path"))
    path = Path(selected).expanduser()
    if must_exist:
        while not path.exists() or not path.is_dir():
            print(tr("folder_not_found", path=path))
            path = Path(ask_text(tr("enter_folder_again"))).expanduser()
    else:
        ensure_dir(path)
    return str(path)


def make_result_folder_name(started_at: Optional[dt.datetime] = None) -> str:
    """Return a Windows-safe human-readable result folder name.

    The user-facing idea was "result 13:23 12.06.2026", but ':' is forbidden in
    Windows folder names, so the safe form is "result 13-23 12.06.2026".
    """
    started_at = started_at or dt.datetime.now()
    return "result " + started_at.strftime("%H-%M %d.%m.%Y")


def create_auto_result_dir(input_dir: Path, started_at: Optional[dt.datetime] = None) -> Path:
    """Create a timestamped result/project folder next to the input folder."""
    base_dir = input_dir.resolve().parent
    base_name = make_result_folder_name(started_at)
    candidate = base_dir / base_name
    idx = 2
    while candidate.exists():
        candidate = base_dir / f"{base_name}_{idx}"
        idx += 1
    ensure_project_structure(candidate)
    return candidate


# ---------------------------------------------------------------------------
# Project/run-state wrappers using import-safe core.project_state helpers
# ---------------------------------------------------------------------------
def update_run_state_progress(stage: str, progress: Dict[str, Any]) -> None:
    """Update project.json progress from the running legacy pipeline.

    The owner of CURRENT_ARGS/CURRENT_CONFIG remains the legacy pipeline module
    until the later pipeline-transfer stage.  This helper is kept here because
    it belongs to the CLI/project-state boundary, not the ML algorithm.
    """
    legacy = _legacy_core()
    try:
        current_args = getattr(legacy, "CURRENT_ARGS", None)
        current_config = getattr(legacy, "CURRENT_CONFIG", None)
        output = Path(getattr(current_args, "output", None) or getattr(current_args, "output_dir", None))
        state_dir = getattr(legacy, "CURRENT_RUN_STATE_DIR", None) or output
        previous = read_run_state(Path(state_dir))
        previous.setdefault("progress", {})
        previous["progress"][stage] = dict(progress)
        write_run_state(Path(state_dir), current_config, current_args, previous)
    except Exception:
        # Progress writes must never break image processing.
        return


def mark_run_stage(output_dir: Path, stage: str, status: str = "running", last_successful_stage: Optional[str] = None, stages_completed: Optional[Sequence[str]] = None) -> None:
    """Write stage/status updates into project.json for resume and diagnostics."""
    legacy = _legacy_core()
    write_run_state(
        output_dir,
        getattr(legacy, "CURRENT_CONFIG", None),
        getattr(legacy, "CURRENT_ARGS", None),
        {"stage": stage, "status": status, "last_successful_stage": last_successful_stage, "stages_completed": list(stages_completed or [])},
    )


def ask_output_folder(input_dir: str) -> Tuple[str, bool]:
    """Ask output folder. If user skips it, create or resume an auto result folder.

    Return (output_path, resume_existing_output). When resume_existing_output=True,
    the wizard will use safer defaults (no rescan, no folder cleanup) and may choose
    a continuation mode based on the previous successful stage.
    """
    input_path = Path(input_dir).resolve()
    print("\n" + tr("output_title"))
    print_wrapped(tr("output_info"))
    use_dialog = ask_bool(tr("open_output_dialog"), True)
    selected = choose_folder_dialog(tr("output_title")) if use_dialog else None
    if not selected:
        selected = ask_text(tr("enter_output_or_auto"), "")
    if selected.strip():
        path = Path(selected).expanduser().resolve()
        ensure_dir(path)
        return str(path), False

    unfinished = find_unfinished_result_dirs(input_path)
    if unfinished:
        print("\n" + lang_text("Найден незавершённый запуск.", "Unfinished run found."))
        # If several unfinished result folders exist, let the user choose which one to inspect
        # or explicitly skip all found runs and create a fresh auto result folder.
        if len(unfinished) > 1:
            create_new_value = "__create_new_result__"
            run_options: List[Dict[str, Any]] = []
            for path, state in unfinished[:10]:
                run_options.append({
                    "label": describe_run_state_for_user(path, state),
                    "value": str(path),
                    "help": str(path),
                })
            run_options.append({
                "label": lang_text(
                    "Не продолжать найденные запуски — создать новую result-папку",
                    "Do not continue found runs — create a new result folder",
                ),
                "value": create_new_value,
                "help": lang_text(
                    "Все найденные result-папки останутся на диске без изменений.",
                    "All found result folders will remain on disk unchanged.",
                ),
            })
            chosen_path_s = choose_from_options(
                lang_text("Какой незавершённый запуск использовать?", "Which unfinished run should be used?"),
                run_options,
                run_options[0]["value"],
            )
            if chosen_path_s == create_new_value:
                auto_dir = create_auto_result_dir(input_path)
                print(tr("created_output", path=auto_dir))
                return str(auto_dir), False
            chosen = next((item for item in unfinished if str(item[0]) == str(chosen_path_s)), unfinished[0])
        else:
            chosen = unfinished[0]
        chosen_path, chosen_state = chosen
        print_wrapped(describe_run_state_for_user(chosen_path, chosen_state))
        last = chosen_state.get("last_successful_stage") or chosen_state.get("stage") or "unknown"
        print_wrapped(lang_text(
            f"Последний успешный этап: {last}. Можно продолжить, начать заново в той же папке или создать новую result-папку.",
            f"Last successful stage: {last}. You can continue, restart in the same folder, or create a new result folder.",
        ))
        action = choose_from_options(
            lang_text("Что сделать?", "What should be done?"),
            [
                {"label": lang_text("Продолжить с ближайшего безопасного этапа", "Continue from the nearest safe stage"), "value": "continue", "help": lang_text("Не пересканировать кэшированные фото и не очищать people/review.", "Do not rescan cached photos and do not clean people/review.")},
                {"label": lang_text("Начать заново в этой же result-папке", "Restart in the same result folder"), "value": "restart", "help": lang_text("Будут применены обычные настройки профиля. Очистка people/review зависит от выбранных параметров.", "Normal profile settings will be used. Cleaning people/review depends on selected options.")},
                {"label": lang_text("Не продолжать — создать новую result-папку", "Do not continue — create a new result folder"), "value": "new", "help": lang_text("Старый незавершённый результат останется на диске.", "The old unfinished result remains on disk.")},
            ],
            "continue",
        )
        if action == "continue":
            print_wrapped(lang_text("Продолжение: включаю безопасные настройки resume.", "Resume: enabling safe resume defaults."))
            return str(chosen_path), True
        if action == "restart":
            return str(chosen_path), False

    auto_dir = create_auto_result_dir(input_path)
    print(tr("created_output", path=auto_dir))
    return str(auto_dir), False


def profile_title(profile_key: str) -> str:
    """Return localized profile title for menus and reports."""
    if _current_lang() == "en":
        return {
            "minimum": "minimum quality",
            "normal": "normal quality",
            "high": "high quality",
            "maximum": "maximum quality",
            "recognition_max": "recognition maximum",
        }.get(profile_key, profile_key)
    return str(QUALITY_PROFILES.get(profile_key, QUALITY_PROFILES["normal"]).get("title", profile_key))


def profile_short(profile_key: str) -> str:
    """Return short localized profile description."""
    if _current_lang() == "en":
        return {
            "minimum": "fast, rough",
            "normal": "best starting point",
            "high": "stronger search for difficult faces",
            "maximum": "heaviest ready preset, not an absolute limit",
            "recognition_max": "extreme profile: the most aggressive ready face search",
        }.get(profile_key, "")
    return str(QUALITY_PROFILES.get(profile_key, QUALITY_PROFILES["normal"]).get("short", ""))


def profile_effect(profile_key: str) -> str:
    """Return detailed localized profile effect text."""
    if _current_lang() == "en":
        return {
            "minimum": "Fast and rough: minimum CPU/GPU and memory load, but it may miss small/difficult faces and produce worse clusters.",
            "normal": "Best starting point for most archives: buffalo_l, upscale 640, soft detector threshold and best-face assignment without duplicating photos across people folders.",
            "high": "Stronger search for difficult faces: slower than normal, but more likely to find weak/small faces. More false faces may go to review.",
            "maximum": "The heaviest ready preset, but not an absolute limit: aggressive pipeline settings for small and weak faces. Higher values are possible in manual mode, but time, memory and review noise grow sharply.",
            "recognition_max": "The most aggressive ready profile: does not downscale large photos, strongly upscales small ones and uses very soft thresholds. It can be very slow, hit VRAM/RAM limits and create many false faces in review.",
        }.get(profile_key, "")
    return str(QUALITY_PROFILES.get(profile_key, QUALITY_PROFILES["normal"]).get("effect", ""))


def profile_warning(profile_key: str) -> str:
    """Return localized warning text for heavy profiles."""
    if _current_lang() == "en":
        return {
            "recognition_max": "Warning: this profile can be very slow and may hit VRAM/RAM limits. If memory errors occur, use maximum or high quality instead.",
        }.get(profile_key, "")
    return str(QUALITY_PROFILES.get(profile_key, QUALITY_PROFILES["normal"]).get("warning", ""))

def show_quality_profile(profile_key: str, cfg: Dict[str, Any]) -> None:
    """Print the selected quality profile parameters."""
    profile = QUALITY_PROFILES.get(profile_key, QUALITY_PROFILES["normal"])
    print("\n" + tr("selected_profile", title=profile_title(profile_key)))
    print_wrapped(profile_short(profile_key))
    print_wrapped(profile_effect(profile_key))
    if profile.get("warning"):
        print("\n" + tr("profile_warning"))
        print_wrapped(profile_warning(profile_key))
    print("\n" + tr("profile_fixed_params"))
    rows = [
        ("mode", cfg["mode"], "полный цикл: scan + cluster + copy + report"),
        ("model/runtime", f"{cfg['model']} / {'GPU' if cfg.get('gpu') else 'CPU'}", "GPU используется только если CUDAExecutionProvider найден и модель прошла smoke-test"),
        ("det_size", cfg["det_size"], "размер детектора лиц"),
        ("max_side", cfg["max_side"], "0 = не уменьшать большие фото"),
        ("upscale_small_to", cfg["upscale_small_to"], "0 = не увеличивать маленькие фото"),
        ("min_face_size", cfg["min_face_size"], "минимальный размер лица после resize/upscale"),
        ("min_det_score", cfg["min_det_score"], "минимальная уверенность детектора"),
        ("algo", cfg["algo"], "алгоритм кластеризации"),
        ("min_cluster_size", cfg["min_cluster_size"], "минимальный размер person-группы"),
        ("cluster_selection", cfg["cluster_selection_method"], "метод выбора кластеров HDBSCAN"),
        ("rescan", cfg["rescan"], "пересканировать фото заново"),
        ("duplicate_check", cfg.get("duplicate_check", "exact"), "поиск точных дублей перед распознаванием"),
        ("duplicate_policy", cfg.get("duplicate_policy", "scan-one-copy-all"), "политика обработки найденных дублей"),
        ("scan_workers", cfg.get("scan_workers", "auto"), "worker-процессы для сканирования; GPU обычно 1"),
        ("copy_workers", cfg.get("copy_workers", "auto"), "потоки копирования файлов"),
        ("reuse_problem_cache", cfg.get("reuse_problem_cache", True), "пропускать уже известные проблемные файлы"),
    ]
    for key, value, note in rows:
        print(f"  {key:24} = {str(value):10}  — {note}")



def ask_file_timeout_safety_options(cfg: Dict[str, Any], *, include_worker_toggle: bool = False) -> None:
    """Ask user-facing safety options added after v20.

    This is intentionally separate from recognition-quality presets: profiles keep their
    recognition settings, while timeout protects the run from broken/locked files.
    """
    print_wrapped(
        "file_timeout — защита от зависания на одном файле. auto = рассчитать по профилю, CPU/GPU и примерному размеру файла; fixed = указать секунды вручную; off = отключить защиту timeout."
    )
    choice = choose_from_options(
        "file_timeout — как ограничивать обработку одного файла?",
        [
            {"label": "auto — рассчитать автоматически", "value": "auto", "help": "Рекомендуется: учитывает профиль качества, CPU/GPU и примерный размер изображения."},
            {"label": "fixed — указать фиксированный таймаут в секундах", "value": "fixed", "help": "Полезно для тестов или очень слабых/очень мощных компьютеров."},
            {"label": "off — отключить таймаут", "value": "off", "help": "Не рекомендуется: битый/заблокированный файл может надолго остановить обработку."},
        ],
        "auto" if str(cfg.get("file_timeout", "auto")).lower() not in {"0", "off", "none", "disabled", "disable"} else "off",
    )
    if choice == "auto":
        cfg["file_timeout"] = "auto"
    elif choice == "off":
        cfg["file_timeout"] = "off"
    else:
        cfg["file_timeout"] = str(ask_int_range(
            "file_timeout_seconds — фиксированный таймаут на один файл, сек.",
            300, 1, 7200,
            "Если файл обрабатывается дольше этого времени, он попадёт в problem_files.csv с reason=timeout.",
            "быстрее пропускает зависшие файлы, но может пропустить очень тяжёлые валидные фото",
            "меньше риск пропустить тяжёлое фото, но зависший файл задержит запуск дольше",
        ))
    if include_worker_toggle:
        cfg["disable_scan_worker"] = ask_bool(
            "disable_scan_worker — отключить worker-процесс и защиту timeout?",
            cfg.get("disable_scan_worker", False),
            "Обычно нет. Worker нужен, чтобы пропускать зависшие/битые файлы и продолжать обработку.",
        )
        ask_performance_options(cfg, ask_workers=True)

def ask_performance_options(cfg: Dict[str, Any], *, ask_workers: bool = True) -> None:
    """Ask scan/copy worker and problem-cache options."""
    if ask_workers:
        cfg["scan_workers"] = choose_from_options(
            "scan_workers — сколько worker-процессов использовать для сканирования лиц?",
            [
                {"label": "auto — GPU=1, CPU=до 4", "value": "auto", "help": "Рекомендуется: стабильно для GPU и быстрее на CPU."},
                {"label": "1 — максимально стабильно", "value": "1", "help": "Самый безопасный вариант, особенно для GPU/слабых ПК."},
                {"label": "2 — умеренный параллелизм CPU", "value": "2", "help": "Полезно на CPU, на GPU скрипт всё равно ограничит до 1."},
                {"label": "4 — быстрый CPU-режим", "value": "4", "help": "Может быстрее на многоядерном CPU, но требует больше RAM."},
            ],
            str(cfg.get("scan_workers", "auto")),
        )
        cfg["copy_workers"] = choose_from_options(
            "copy_workers — сколько потоков использовать для копирования файлов?",
            [
                {"label": "auto — обычно 4, сетевые пути 2", "value": "auto", "help": "Рекомендуется для SSD/HDD и обычных папок."},
                {"label": "1 — копировать последовательно", "value": "1", "help": "Максимально предсказуемо, но медленнее."},
                {"label": "4 — стандартный параллелизм", "value": "4", "help": "Хороший вариант для локального SSD/HDD."},
                {"label": "8 — агрессивное копирование", "value": "8", "help": "Может ускорить SSD, но на HDD/сети может мешать."},
            ],
            str(cfg.get("copy_workers", "auto")),
        )
    cfg["reuse_problem_cache"] = ask_bool(
        "reuse_problem_cache — пропускать уже известные битые/timeout файлы, если они не изменились?",
        bool(cfg.get("reuse_problem_cache", True)),
        "Рекомендуется: повторный запуск не будет снова зависать/тратить время на уже проблемные файлы.",
    )


def ask_preset_sorting_options(cfg: Dict[str, Any]) -> None:
    """Ask non-recognition options for quality presets."""
    print("\n" + tr("preset_sort_questions"))
    cfg["photo_assignment"] = choose_from_options(
        "Как назначать фото с несколькими лицами?",
        [
            {"label": "best-face — одно фото в один лучший кластер", "value": "best-face", "help": "Рекомендуется: не размножает одно фото по нескольким person-папкам."},
            {"label": "all-faces — копировать в папку каждого найденного человека", "value": "all-faces", "help": "Одно групповое фото может попасть в несколько папок людей."},
        ],
        cfg["photo_assignment"],
    )
    cfg["copy_group_photos"] = ask_bool(
        "copy_group_photos — дополнительно копировать групповые фото в review/group_photos?",
        cfg["copy_group_photos"],
        "Создаёт дополнительную копию для просмотра всех фото, где найдено несколько лиц.",
    )
    cfg["filename_fallback"] = ask_bool(
        "filename_fallback — назначать review-фото по похожему имени файла?",
        cfg["filename_fallback"],
        "Если распознавание не уверено, но имя файла почти совпадает с файлом из person-кластера, скрипт может назначить фото туда.",
    )
    if cfg["filename_fallback"]:
        cfg["filename_max_distance"] = ask_int_range(
            "filename_max_distance — допустимая разница символов в имени файла",
            cfg["filename_max_distance"], 0, 20,
            "Работает только при filename_fallback. 3 = разница до трёх символов.",
            "строже, меньше ошибочных назначений по имени",
            "мягче, больше спасённых файлов, но выше риск отправить не туда",
        )
    cfg["duplicate_check"] = choose_from_options(
        "duplicate_check — проверять точные дубли файлов перед распознаванием?",
        [
            {"label": "exact — искать только побайтно одинаковые файлы", "value": "exact", "help": "Быстро и безопасно: сначала группировка по размеру, потом partial/full hash только для подозрительных групп."},
            {"label": "off — не проверять дубли", "value": "off", "help": "Каждый файл распознаётся отдельно."},
        ],
        cfg.get("duplicate_check", "exact"),
    )
    if cfg.get("duplicate_check") == "exact":
        cfg["duplicate_policy"] = choose_from_options(
            "duplicate_policy — как обрабатывать точные дубли?",
            [
                {"label": "scan-one-copy-all — распознать один дубль, копировать все", "value": "scan-one-copy-all", "help": "Рекомендуется: экономит распознавание, но не теряет ни один исходный файл."},
                {"label": "scan-one-copy-first — распознать и копировать только canonical", "value": "scan-one-copy-first", "help": "Экономит место в people/review, остальные дубли останутся только в duplicates.csv."},
                {"label": "report-only — только отчёт о дублях", "value": "report-only", "help": "Не меняет обработку: все файлы будут распознаваться и копироваться как раньше."},
            ],
            cfg.get("duplicate_policy", "scan-one-copy-all"),
        )
    ask_file_timeout_safety_options(cfg, include_worker_toggle=False)
    ask_performance_options(cfg, ask_workers=True)

    cfg["clean_folders"] = ask_bool(
        "clean_folders — очистить output/people и output/review перед копированием?",
        cfg["clean_folders"],
        "Обычно да: иначе старые результаты могут смешаться с новым запуском.",
    )
    cfg["overwrite_names"] = ask_bool(
        "overwrite_names — перезаписать names.csv, если он уже есть?",
        cfg["overwrite_names"],
        "Обычно нет, чтобы не потерять вручную введённые имена людей.",
    )
    cfg["report_faces_per_cluster"] = ask_int_range(
        "report_faces_per_cluster — сколько превью лиц показывать в HTML",
        cfg["report_faces_per_cluster"], 1, 200,
        "Количество кропов лиц в отчёте clusters.html для каждого person-кластера.",
        "отчёт компактнее, но сложнее понять качество кластера",
        "лучше видно ошибки внутри кластера, но HTML становится тяжелее",
    )
    cfg["progress_every"] = ask_int_range(
        "progress_every — как часто печатать статистику",
        cfg["progress_every"], 1, 10000,
        "Например 500 = статистика каждые 500 фото и во время сканирования, и во время копирования.",
        "чаще видите прогресс, но больше текста в консоли",
        "реже сообщения, удобнее для больших архивов",
    )
    cfg["dry_run"] = ask_bool(
        "dry_run — только посчитать действия, не копировать файлы?",
        cfg["dry_run"],
        "Полезно для проверки профиля без записи новых копий фото.",
    )
    cfg["verbose"] = ask_bool(
        "verbose — показывать подробные traceback ошибок?",
        cfg["verbose"],
        "Нужно для отладки битых файлов/ошибок библиотек. В обычном режиме лучше оставить нет.",
    )


def interactive_args() -> argparse.Namespace:
    """Build argparse-like options from the interactive console wizard."""
    print("\n" + tr("app_title"))
    input_dir = ask_folder(tr("input_title"), must_exist=True)
    output_dir, resume_existing_output = ask_output_folder(input_dir)

    scan_profile = choose_from_options(
        tr("choose_profile"),
        [
            {"label": tr("profile_min_label"), "value": "minimum", "help": tr("profile_min_help")},
            {"label": tr("profile_normal_label"), "value": "normal", "help": tr("profile_normal_help")},
            {"label": tr("profile_high_label"), "value": "high", "help": tr("profile_high_help")},
            {"label": tr("profile_max_label"), "value": "maximum", "help": tr("profile_max_help")},
            {"label": tr("profile_recmax_label"), "value": "recognition_max", "help": tr("profile_recmax_help")},
            {"label": tr("profile_manual_label"), "value": "manual", "help": tr("profile_manual_help")},
        ],
        "normal",
    )

    cfg = dict(DEFAULT_PROFILE)
    cfg["input"] = input_dir
    cfg["output"] = output_dir
    cfg["db"] = None
    cfg["names"] = None
    cfg["auto_install"] = False
    cfg["auto_gpu_install"] = False
    cfg["auto_cpu_fallback"] = True
    cfg["force_env_check"] = False
    cfg["scan_profile"] = scan_profile

    print("\n" + tr("checking_deps"))
    ensure_dependencies(argparse.Namespace(**cfg))

    gpu_options_available = interactive_gpu_startup_wizard(cfg)

    if scan_profile != "manual":
        profile = QUALITY_PROFILES.get(scan_profile, QUALITY_PROFILES["normal"])
        profile_settings = dict(profile["settings"])
        profile_settings.update({
            "input": input_dir,
            "output": output_dir,
            "db": None,
            "names": None,
            "auto_install": False,
            "auto_gpu_install": False,
            "auto_cpu_fallback": True,
            "resume_existing_output": bool(resume_existing_output),
            "scan_profile": scan_profile,
        })
        if resume_existing_output:
            previous_state = read_run_state(Path(output_dir))
            profile_settings["mode"] = resume_mode_from_state(previous_state, profile_settings.get("mode", "all"))
            profile_settings["rescan"] = False
            profile_settings["clean_folders"] = False
            print_wrapped(lang_text(
                f"Resume: выбран ближайший безопасный режим продолжения: {profile_settings['mode']}",
                f"Resume: selected nearest safe continuation mode: {profile_settings['mode']}",
            ))
        # Preserve results of the startup GPU wizard, then decide runtime automatically.
        profile_settings["gpu_model_smoke_results"] = cfg.get("gpu_model_smoke_results")
        profile_settings["gpu_allowed_models"] = cfg.get("gpu_allowed_models")
        cfg = profile_settings

        allowed = cfg.get("gpu_allowed_models")
        if gpu_options_available and (allowed is None or cfg["model"] in set(allowed)):
            cfg["gpu"] = True
        else:
            cfg["gpu"] = False
            if gpu_options_available and allowed is not None:
                print_wrapped(f"Профиль использует {cfg['model']}, но эта модель не прошла GPU smoke-test. Профиль будет запущен на CPU.")

        show_quality_profile(scan_profile, cfg)
        ask_preset_sorting_options(cfg)
    else:
        cfg["mode"] = choose_from_options(
            lang_text("Что выполнить?", "What do you want to run?"),
            [
                {"label": lang_text("all — полный цикл", "all — full pipeline"), "value": "all", "help": lang_text("scan + cluster + copy + names.csv + summary.csv + HTML-отчёт.", "scan + cluster + copy + names.csv + summary.csv + HTML report.")},
                {"label": lang_text("scan — только найти лица и сохранить embeddings", "scan — detect faces and save embeddings only"), "value": "scan", "help": lang_text("Нужно для первичного анализа или пересканирования без раскладки.", "Useful for initial analysis or rescanning without folder creation.")},
                {"label": lang_text("cluster — пересобрать кластеры и отчёты", "cluster — rebuild clusters and reports"), "value": "cluster", "help": lang_text("Использует уже сохранённые embeddings в SQLite. Не копирует файлы.", "Uses saved embeddings in SQLite. Does not copy files.")},
                {"label": lang_text("assign — только подготовить assignments.csv", "assign — prepare assignments.csv only"), "value": "assign", "help": lang_text("Назначает целевые папки без копирования файлов.", "Assigns target folders without copying files.")},
                {"label": lang_text("copy — только заново скопировать фото по готовому assignments.csv", "copy — recopy photos from existing assignments.csv"), "value": "copy", "help": lang_text("Полезно после изменения настроек копирования. Не пересчитывает лица и кластеры.", "Useful after changing copy settings. Does not recalculate faces or clusters.")},
                {"label": lang_text("report — только пересоздать names.csv/summary/html", "report — recreate names.csv/summary/html only"), "value": "report", "help": lang_text("Не сканирует и не копирует фото.", "Does not scan or copy photos.")},
                {"label": lang_text("review-clusters — консольная проверка names.csv", "review-clusters — console review of names.csv"), "value": "review-clusters", "help": lang_text("По умолчанию ничего не объединяет и не переименовывает. Позволяет явно keep/merge/review/ignore.", "By default it does not merge or rename anything. Lets you explicitly choose keep/merge/review/ignore.")},
                {"label": lang_text("apply-names — создать final-папки по names.csv", "apply-names — create final folders from names.csv"), "value": "apply-names", "help": lang_text("После ручного заполнения names.csv.", "After editing names.csv.")},
                {"label": lang_text("bug-report — создать ZIP bug report", "bug-report — create ZIP bug report"), "value": "bug-report", "help": lang_text("Собирает логи и отчёты без оригинальных фото.", "Collects logs and reports without original photos.")},
                {"label": lang_text("diagnose-gpu — только диагностика GPU/CUDA/ONNX Runtime", "diagnose-gpu — GPU/CUDA/ONNX Runtime diagnostics only"), "value": "diagnose-gpu", "help": lang_text("Печатает Python, nvidia-smi, версии onnxruntime/onnxruntime-gpu и доступные providers.", "Prints Python, nvidia-smi, onnxruntime/onnxruntime-gpu versions, and available providers.")},
            ],
            cfg["mode"],
        )

        cfg["model"], cfg["gpu"] = choose_model_and_runtime(
            cfg["model"],
            cfg["gpu"] if gpu_options_available else False,
            allow_gpu=gpu_options_available,
            gpu_allowed_models=cfg.get("gpu_allowed_models"),
        )

        cfg["det_size"] = ask_int_range(
            "det_size — размер окна детектора InsightFace",
            cfg["det_size"], 320, 1280,
            "Основной размер детекции лиц. 640 — нормальный старт.",
            "быстрее и меньше расход памяти, но мелкие лица могут пропадать",
            "медленнее и тяжелее по памяти, иногда лучше на мелких/дальних лицах",
        )
        cfg["max_side"] = ask_int_range(
            "max_side — максимальная сторона изображения перед детекцией",
            cfg["max_side"], 0, 4000,
            "Скрипт уменьшает слишком большие фото до этого размера. 0 = не уменьшать.",
            "быстрее и экономнее, но меньше деталей для лиц",
            "больше деталей, но медленнее и выше риск нехватки памяти",
        )
        cfg["upscale_small_to"] = ask_int_range(
            "upscale_small_to — увеличение маленьких фото",
            cfg["upscale_small_to"], 0, 1600,
            "Если фото маленькое, скрипт увеличивает его до этой максимальной стороны. 640 помогает для фото около 200x200. 0 = не увеличивать.",
            "быстрее, меньше ложных лиц, но маленькие лица могут не найтись",
            "лучше шанс найти мелкие лица, но медленнее и иногда больше ложных срабатываний",
        )
        cfg["rescan"] = ask_bool(
            "rescan — пересканировать даже уже кэшированные фото?",
            cfg["rescan"],
            "Включайте после изменения upscale_small_to, min_face_size, min_det_score или модели. Иначе старый кэш может скрывать эффект новых настроек.",
        )
        cfg["commit_every"] = ask_int_range(
            "commit_every — как часто сохранять SQLite во время сканирования",
            cfg["commit_every"], 1, 1000,
            "Частота сохранения прогресса в базу данных.",
            "надёжнее при сбое, но чуть медленнее",
            "быстрее, но при сбое может потеряться больше несохранённого прогресса",
        )
        cfg["progress_every"] = ask_int_range(
            "progress_every — как часто печатать статистику",
            cfg["progress_every"], 1, 10000,
            "Например 500 = статистика каждые 500 фото.",
            "чаще видите прогресс, но больше текста в консоли",
            "реже сообщения, удобнее для больших архивов",
        )

        cfg["algo"] = choose_from_options(
            "Алгоритм кластеризации",
            [
                {"label": "hdbscan — рекомендуемый", "value": "hdbscan", "help": "Лучше для людей, которые встречаются разное число раз; обычно меньше ручной настройки."},
                {"label": "dbscan — запасной вариант", "value": "dbscan", "help": "Полезен, если hdbscan не установился. Требует настройки dbscan_eps."},
            ],
            cfg["algo"],
        )
        cfg["min_cluster_size"] = ask_int_range(
            "min_cluster_size — минимальный размер person-группы",
            cfg["min_cluster_size"], 2, 100,
            "Сколько лиц минимум нужно, чтобы группа стала отдельным person_XXX.",
            "найдёт больше редких людей, но будет больше мусорных/случайных групп",
            "группы будут чище, но редкие люди уйдут в unknown/review",
        )
        cfg["min_samples"] = ask_int_range(
            "min_samples — строгость HDBSCAN/DBSCAN",
            cfg["min_samples"], 1, 100,
            "None/auto = не задавать вручную. Обычно можно оставить None.",
            "мягче, больше лиц попадёт в группы, но выше риск смешивания людей",
            "строже, меньше смешиваний, но больше unknown",
            allow_none=True,
            none_label="None",
        )
        cfg["cluster_selection_method"] = choose_from_options(
            "cluster_selection_method для HDBSCAN",
            [
                {"label": "eom — стандартный стабильный режим", "value": "eom", "help": "Обычно лучше для автоматической сортировки фото."},
                {"label": "leaf — больше мелких кластеров", "value": "leaf", "help": "Может разделить одного человека на несколько групп, но иногда помогает не смешивать похожих людей."},
            ],
            cfg["cluster_selection_method"],
        )
        cfg["dbscan_eps"] = ask_float_range(
            "dbscan_eps — радиус похожести для DBSCAN",
            cfg["dbscan_eps"], 0.30, 0.80,
            "Используется только при выборе DBSCAN. Это главный параметр объединения лиц.",
            "строже: меньше смешивает разных людей, но чаще дробит одного человека и отправляет в unknown",
            "мягче: больше объединяет, но может смешать похожих людей",
        )
        cfg["min_det_score"] = ask_float_range(
            "min_det_score — минимальная уверенность детектора лица",
            cfg["min_det_score"], 0.10, 0.90,
            "Фильтр качества найденного лица. 0.30 — мягкий режим для сложных/маленьких фото.",
            "найдёт больше слабых лиц, но может добавить ложные лица",
            "оставит более уверенные лица, но может пропустить плохие/маленькие фото",
        )
        cfg["min_face_size"] = ask_int_range(
            "min_face_size — минимальный размер лица в пикселях",
            cfg["min_face_size"], 4, 100,
            "Минимальная сторона bounding box лица после resize/upscale. 12 помогает для маленьких фото.",
            "берёт очень мелкие лица, больше шума и ошибок",
            "фильтрует мелкие/сомнительные лица, но пропускает дальние лица",
        )
        cfg["photo_assignment"] = choose_from_options(
            "Как назначать фото с несколькими лицами?",
            [
                {"label": "best-face — одно фото в один лучший кластер", "value": "best-face", "help": "Рекомендуется для вашей задачи: не размножает одно фото по папкам person_001/person_003/person_005."},
                {"label": "all-faces — копировать в папку каждого найденного человека", "value": "all-faces", "help": "Удобно для семейных архивов, но одно фото может оказаться в нескольких папках."},
            ],
            cfg["photo_assignment"],
        )
        cfg["copy_group_photos"] = ask_bool(
            "copy_group_photos — дополнительно копировать групповые фото в review/group_photos?",
            cfg["copy_group_photos"],
            "Включайте, если хотите отдельную папку для фото, где найдено несколько лиц. Это создаёт дополнительную копию.",
        )
        cfg["filename_fallback"] = ask_bool(
            "filename_fallback — назначать review-фото по похожему имени файла?",
            cfg["filename_fallback"],
            "Если распознавание не уверено, но имя файла почти совпадает с файлом из person-кластера, скрипт может назначить фото туда.",
        )
        cfg["filename_max_distance"] = ask_int_range(
            "filename_max_distance — допустимая разница символов в имени файла",
            cfg["filename_max_distance"], 0, 20,
            "Работает только при filename_fallback. 3 = разница до трёх символов.",
            "строже, меньше ошибочных назначений по имени",
            "мягче, больше спасённых файлов, но выше риск отправить не туда",
        )
        cfg["clean_folders"] = ask_bool(
            "clean_folders — очистить output/people и output/review перед копированием?",
            cfg["clean_folders"],
            "Обычно да: иначе старые результаты могут смешаться с новым запуском.",
        )
        cfg["clean_final"] = ask_bool(
            "clean_final — очистить output/final и output/final_review при apply-names?",
            cfg["clean_final"],
            "Включайте, когда хотите полностью пересоздать финальные папки после правки names.csv.",
        )
        cfg["overwrite_names"] = ask_bool(
            "overwrite_names — перезаписать names.csv, если он уже есть?",
            cfg["overwrite_names"],
            "Обычно нет, чтобы не потерять вручную введённые имена людей.",
        )
        cfg["report_faces_per_cluster"] = ask_int_range(
            "report_faces_per_cluster — сколько превью лиц показывать в HTML",
            cfg["report_faces_per_cluster"], 1, 200,
            "Количество кропов лиц в отчёте clusters.html для каждого person-кластера.",
            "отчёт компактнее, но сложнее понять качество кластера",
            "лучше видно ошибки внутри кластера, но HTML становится тяжелее",
        )
        cfg["dry_run"] = ask_bool(
            "dry_run — только посчитать действия, не копировать файлы?",
            cfg["dry_run"],
            "Полезно для теста настроек без записи новых копий фото.",
        )
        cfg["verbose"] = ask_bool(
            "verbose — показывать подробные traceback ошибок?",
            cfg["verbose"],
            "Нужно для отладки битых файлов/ошибок библиотек. В обычном режиме лучше оставить нет.",
        )
        print_wrapped("file_timeout — таймаут обработки одного файла. auto = рассчитать по профилю, CPU/GPU и примерному размеру файла; 0/off = отключить; число = фиксированный таймаут в секундах.")
        while True:
            raw_timeout = input(f"file_timeout [auto]: ").strip() or "auto"
            if raw_timeout.lower() in {"auto", "automatic", "0", "off", "none", "disabled", "disable"}:
                cfg["file_timeout"] = raw_timeout
                break
            try:
                val = int(float(raw_timeout))
                if val < 0:
                    print(lang_text("Введите auto, 0/off или положительное число секунд.", "Enter auto, 0/off, or a positive number of seconds."))
                    continue
                cfg["file_timeout"] = str(val)
                break
            except Exception:
                print(lang_text("Введите auto, 0/off или число секунд, например 300.", "Enter auto, 0/off, or seconds, for example 300."))
        cfg["disable_scan_worker"] = ask_bool(
            "disable_scan_worker — отключить worker-процесс и защиту timeout?",
            cfg.get("disable_scan_worker", False),
            "Обычно нет. Worker нужен, чтобы пропускать зависшие/битые файлы и продолжать обработку.",
        )
        ask_performance_options(cfg, ask_workers=True)

    if resume_existing_output:
        previous_state = read_run_state(Path(output_dir))
        suggested_mode = resume_mode_from_state(previous_state, cfg.get("mode", "all"))
        if cfg.get("mode") == "all" and suggested_mode != "all":
            cfg["mode"] = suggested_mode
            cfg["rescan"] = False
            cfg["clean_folders"] = False
            print_wrapped(lang_text(
                f"Resume: выбран ближайший безопасный режим продолжения: {cfg['mode']}",
                f"Resume: selected nearest safe continuation mode: {cfg['mode']}",
            ))

    ns = argparse.Namespace(**cfg)
    return ns




__all__ = [
    'choose_folder_dialog',
    'ask_text',
    'print_wrapped',
    'ask_bool',
    'choose_from_options',
    'ask_int_range',
    'ask_float_range',
    'model_help_text',
    'print_model_reference',
    'choose_model_and_runtime',
    'interactive_gpu_startup_wizard',
    'ask_folder',
    'make_result_folder_name',
    'create_auto_result_dir',
    'update_run_state_progress',
    'mark_run_stage',
    'ask_output_folder',
    'profile_title',
    'profile_short',
    'profile_effect',
    'profile_warning',
    'show_quality_profile',
    'ask_file_timeout_safety_options',
    'ask_performance_options',
    'ask_preset_sorting_options',
    'interactive_args'
]
