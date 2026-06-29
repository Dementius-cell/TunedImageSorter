#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tuned Image Sorter v67.2.

Local, privacy-first photo sorter based on face clustering.

High-level pipeline
-------------------
1. Collect candidate image files from an input folder or project.
2. Optionally detect exact file duplicates and select canonical files.
3. Scan images with InsightFace to extract faces and embeddings.
4. Cluster embeddings with HDBSCAN/DBSCAN into person_XXX groups.
5. Assign each source image to people/review targets.
6. Copy files using hardened Windows-safe path handling.
7. Generate CSV/HTML reports, names.csv, review data and bug reports.

Architecture notes for AI agents and contributors
-------------------------------------------------
- RunConfig is the stable contract between CLI, future GUI and the pipeline.
- run_pipeline(config, callbacks) is the central entry point.
- ProgressCallbacks decouple console output from future UI progress bars.
- face recognition, clustering, assignment, copy and report are independent stages.
- file_ops.py owns path normalization, safe names and collision-safe copying.
- SQLite writes happen in the main process to avoid cross-process DB locking.
- GPU inference defaults to one scan worker for CUDA/cuDNN stability.

Safety
------
The script does not delete or move original photos. It copies results into a project/output
folder and records file-name changes, problems and run state for reproducibility.
"""
from __future__ import annotations

import argparse
import atexit
import concurrent.futures
import io
import csv
import datetime as dt
import faulthandler
import hashlib
import html
import importlib
import locale
import importlib.metadata
import json
import math
import multiprocessing
import os
import platform
import re
import shutil
import site
import sqlite3
import subprocess
import sys
import time
import threading
import traceback
import warnings
import zipfile
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:  # Package import for future UI: from face_sorter_mvp import backend
    from .file_ops import (
        CopyResult as FileCopyResult,
        DestinationPlan as FileDestinationPlan,
        copy_with_collision_handling as file_copy_with_collision_handling,
        image_magic_status as file_image_magic_status,
        iter_supported_images as file_iter_supported_images,
        normalize_path as file_normalize_path,
        path_diagnostics as file_path_diagnostics,
        plan_safe_destination as file_plan_safe_destination,
        safe_file_stem as file_safe_file_stem,
        safe_filename as file_safe_filename,
        safe_folder_name as file_safe_folder_name,
    )
except ImportError:  # Backward compatible script mode: python face_sorter_mvp.py
    from file_ops import (
        CopyResult as FileCopyResult,
        DestinationPlan as FileDestinationPlan,
        copy_with_collision_handling as file_copy_with_collision_handling,
        image_magic_status as file_image_magic_status,
        iter_supported_images as file_iter_supported_images,
        normalize_path as file_normalize_path,
        path_diagnostics as file_path_diagnostics,
        plan_safe_destination as file_plan_safe_destination,
        safe_file_stem as file_safe_file_stem,
        safe_filename as file_safe_filename,
        safe_folder_name as file_safe_folder_name,
    )


try:  # package mode: import face_sorter_mvp.face_sorter_mvp
    from .core import (
        APP_LOG_FILE,
        BUG_REPORTS_DIR,
        DEFAULT_MODEL,
        DEFAULT_PROFILE,
        DIAGNOSTICS_DIR_NAME,
        ENV_STATE_FILE,
        FaceRecord,
        ImageRecord,
        IMAGE_EXTENSIONS,
        KNOWN_MODELS,
        LEGACY_RUN_STATE_FILENAME,
        MODE_STAGE_MAP,
        NullProgressCallbacks,
        PIPELINE_STAGES,
        PROBLEM_FILES_NAME,
        PROJECT_DIRS,
        PROJECT_FILENAME,
        ProgressCallbacks,
        RESULT_FOLDER_RE,
        REVIEW_ACTIONS,
        RUN_STATE_FILENAME,
        ReviewDecision,
        RunConfig,
        RunResult,
        SCRIPT_DIR,
        SCRIPT_VERSION,
        WINDOWS_FORBIDDEN_CHARS,
        build_run_state_base,
        default_project_db_path,
        describe_run_state_for_user,
        ensure_project_structure,
        find_unfinished_result_dirs,
        legacy_run_state_path,
        load_project_config,
        project_dirs_payload,
        project_json_path,
        read_legacy_run_state,
        read_project_json,
        read_run_state,
        resume_mode_from_state,
        stages_for_mode,
        write_run_state,
    )
except ImportError:  # backward-compatible script mode: python face_sorter_mvp.py
    from core import (
        APP_LOG_FILE,
        BUG_REPORTS_DIR,
        DEFAULT_MODEL,
        DEFAULT_PROFILE,
        DIAGNOSTICS_DIR_NAME,
        ENV_STATE_FILE,
        FaceRecord,
        ImageRecord,
        IMAGE_EXTENSIONS,
        KNOWN_MODELS,
        LEGACY_RUN_STATE_FILENAME,
        MODE_STAGE_MAP,
        NullProgressCallbacks,
        PIPELINE_STAGES,
        PROBLEM_FILES_NAME,
        PROJECT_DIRS,
        PROJECT_FILENAME,
        ProgressCallbacks,
        RESULT_FOLDER_RE,
        REVIEW_ACTIONS,
        RUN_STATE_FILENAME,
        ReviewDecision,
        RunConfig,
        RunResult,
        SCRIPT_DIR,
        SCRIPT_VERSION,
        WINDOWS_FORBIDDEN_CHARS,
        build_run_state_base,
        default_project_db_path,
        describe_run_state_for_user,
        ensure_project_structure,
        find_unfinished_result_dirs,
        legacy_run_state_path,
        load_project_config,
        project_dirs_payload,
        project_json_path,
        read_legacy_run_state,
        read_project_json,
        read_run_state,
        resume_mode_from_state,
        stages_for_mode,
        write_run_state,
    )

# Runtime imports are intentionally lazy, so the script can check/install dependencies first.
# ---------------------------------------------------------------------------
# Lazy runtime dependencies
# ---------------------------------------------------------------------------
# Heavy ML/image packages are imported only after dependency checks complete.
np = None
Image = None
ImageOps = None
tqdm = None
pillow_heif = None

# Keep DLL directory handles alive on Windows. If handles are garbage-collected,
# directories added by os.add_dll_directory may stop participating in DLL search.
_DLL_DIRECTORY_HANDLES: List[Any] = []
_GPU_RUNTIME_PATHS_ADDED = False



def _python_runtime_roots_for_native_libs() -> List[Path]:
    """Return source and frozen roots that may contain native runtime DLLs."""
    roots: List[Path] = []
    try:
        for sp in site.getsitepackages():
            roots.append(Path(sp))
    except Exception:
        pass
    try:
        usp = site.getusersitepackages()
        if usp:
            roots.append(Path(usp))
    except Exception:
        pass
    try:
        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).resolve().parent
            roots.extend([exe_dir / "_internal", exe_dir])
            meipass = getattr(sys, "_MEIPASS", "")
            if meipass:
                roots.append(Path(meipass))
    except Exception:
        pass
    try:
        # GPU Lite stores CUDA 12 runtime DLLs in a local user cache instead of
        # bundling _internal\nvidia.  Include that cache in the legacy runtime
        # search so Start can use GPU immediately after first-run setup, even if
        # the user did not press the UI Environment check button first.
        from .core.gpu_lite_runtime import gpu_lite_runtime_dir, is_gpu_lite_package
        if is_gpu_lite_package():
            roots.append(gpu_lite_runtime_dir())
    except Exception:
        try:
            from face_sorter_mvp.core.gpu_lite_runtime import gpu_lite_runtime_dir, is_gpu_lite_package
            if is_gpu_lite_package():
                roots.append(gpu_lite_runtime_dir())
        except Exception:
            pass
    out: List[Path] = []
    seen = set()
    for root in roots:
        try:
            key = str(root.resolve())
        except Exception:
            key = str(root)
        if key in seen:
            continue
        seen.add(key)
        out.append(root)
    return out

def add_nvidia_cuda_dll_directories(verbose: bool = False) -> List[str]:
    """Add NVIDIA CUDA/cuDNN package DLL directories to Windows DLL search path.

    onnxruntime.get_available_providers() may show CUDAExecutionProvider even when a later
    real convolution fails because cuDNN sublibraries such as cudnn_engines_tensor_ir64_9.dll
    are not discoverable. This helper searches Python site-packages for NVIDIA CUDA/cuDNN
    wheels and adds directories containing relevant DLLs via os.add_dll_directory and PATH.
    """
    global _GPU_RUNTIME_PATHS_ADDED
    added: List[str] = []
    if os.name != "nt":
        return added

    # Re-adding is harmless, but noisy. Keep it idempotent for normal flow.
    if _GPU_RUNTIME_PATHS_ADDED:
        return added

    roots = _python_runtime_roots_for_native_libs()

    patterns = [
        "cudnn*.dll",
        "cublas*.dll",
        "cudart*.dll",
        "nvrtc*.dll",
        "cufft*.dll",
        "curand*.dll",
        "nvjitlink*.dll",
        "onnxruntime_providers_cuda.dll",
        "onnxruntime_providers_tensorrt.dll",
    ]
    dirs = set()
    for root in roots:
        if not root.exists():
            continue
        # Limit recursive search mainly to known package roots to avoid scanning entire env too deeply.
        candidate_roots = [root / "nvidia", root / "onnxruntime"]
        for base in candidate_roots:
            if not base.exists():
                continue
            for pat in patterns:
                try:
                    for dll in base.rglob(pat):
                        if dll.is_file():
                            dirs.add(dll.parent.resolve())
                except Exception:
                    continue

    # Add parent directories first, then deeper ones. This helps dependent sublibraries.
    for d in sorted(dirs, key=lambda x: (len(str(x)), str(x).lower())):
        ds = str(d)
        try:
            if hasattr(os, "add_dll_directory"):
                _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(ds))
            os.environ["PATH"] = ds + os.pathsep + os.environ.get("PATH", "")
            added.append(ds)
        except Exception:
            continue

    _GPU_RUNTIME_PATHS_ADDED = True
    if verbose:
        if added:
            print(lang_text("Добавлены каталоги CUDA/cuDNN DLL в DLL search path:", "CUDA/cuDNN DLL directories added to DLL search path:"))
            for d in added[:30]:
                print("  ", d)
            if len(added) > 30:
                print(f"  ... и ещё {len(added) - 30}")
        else:
            print(lang_text("Каталоги NVIDIA CUDA/cuDNN DLL в site-packages не найдены.", "NVIDIA CUDA/cuDNN DLL directories in site-packages were not found."))
    return added


def find_cuda_runtime_dlls() -> Dict[str, List[str]]:
    """Return locations of key CUDA/cuDNN DLLs useful for diagnostics."""
    result: Dict[str, List[str]] = {}
    if os.name != "nt":
        return result
    roots = _python_runtime_roots_for_native_libs()

    wanted = [
        "cudnn64_9.dll",
        "cudnn_engines_tensor_ir64_9.dll",
        "cudnn_ops64_9.dll",
        "cublas64_12.dll",
        "cublasLt64_12.dll",
        "cudart64_12.dll",
        "nvrtc64_*.dll",
        "cufft64_*.dll",
        "curand64_*.dll",
        "nvJitLink*.dll",
        "nvjitlink*.dll",
    ]
    for pat in wanted:
        hits: List[str] = []
        for root in roots:
            base = root / "nvidia"
            if not base.exists():
                continue
            try:
                hits.extend(str(p.resolve()) for p in base.rglob(pat) if p.is_file())
            except Exception:
                pass
        result[pat] = hits
    return result


def looks_like_cuda_runtime_error(exc: BaseException) -> bool:
    """Return True when an exception message looks like a CUDA/cuDNN runtime failure."""
    msg = str(exc).lower()
    needles = [
        "cudaexecutionprovider",
        "cudnn",
        "cudnn_status",
        "cudnn_backend",
        "cudnn_engines",
        "ep_fail",
        "failed to initialize cudnn",
        "onnxruntimeerror",
        "loadlibrary failed",
    ]
    return any(n in msg for n in needles)

# ---------------------------------------------------------------------------
# Runtime globals owned by the legacy pipeline module
# ---------------------------------------------------------------------------
CURRENT_ARGS: Optional[argparse.Namespace] = None
CURRENT_CONFIG: Optional[RunConfig] = None
CURRENT_CALLBACKS: Optional[ProgressCallbacks] = None
CURRENT_RUN_STATE_DIR: Optional[Path] = None
CURRENT_RUN_CONFIG_HASH: Optional[str] = None
_LOG_FILE_HANDLE = None
_LOGGING_SETUP = False
_SAFE_COPY_COUNTER = 0
_WORKER_FACE_APP = None
_WORKER_GPU_RUNTIME_FAILED = False
_WORKER_DIAGNOSTICS_DIR: Optional[Path] = None
_WORKER_RUN_ID: Optional[str] = None
_WORKER_FAULT_LOG_HANDLE = None
_WORKER_START_TIME = 0.0
_FILENAME_MAP_LOCK = threading.Lock()
_COPY_LOCKS_GUARD = threading.Lock()
_COPY_LOCKS: Dict[str, threading.Lock] = {}


# ---------------------------------------------------------------------------
# Internationalized UI messages
# ---------------------------------------------------------------------------
# Keep user-visible console text here when possible. Low-level library logs from
# Python/ONNX/CUDA are intentionally not translated.
MESSAGES: Dict[str, Dict[str, str]] = {
    "ru": {
        "yes_no": "[да/нет]",
        "yes": "да",
        "no": "нет",
        "invalid_yes_no": "Не понял ответ. Введите 'да' или 'нет' (можно: y/yes или n/no).",
        "default_marker": " ← по умолчанию",
        "enter_number": "Введите номер",
        "unknown_choice": "Неизвестный выбор '{raw}'. Введите номер из списка: 1-{max}.",
        "enter_int": "Введите целое число.",
        "enter_float": "Введите число, например 0.55.",
        "below_min": "Значение ниже рекомендуемого минимума {min_value}.",
        "above_max": "Значение выше рекомендуемого максимума {max_value}. Возможны тормоза/ошибки памяти.",
        "use_anyway": "Оставить это значение всё равно?",
        "range": "Диапазон: {range}.",
        "minimum": "минимум {value}",
        "maximum": "максимум {value}",
        "lower_value": "Меньше значение: {text}",
        "higher_value": "Больше значение: {text}",
        "can_enter_none": "Можно ввести {none_label}: автоматический/пустой режим.",
        "enter_value": "Введите значение",
        "app_title": "=== Tuned Image Sorter v69.6: интерактивный режим ===",
        "language_auto": "Язык интерфейса выбран автоматически по языку системы: русский.",
        "input_title": "Выбор input-папки с исходными фото",
        "output_title": "Выбор output-папки для результата",
        "open_folder_dialog": "Открыть окно выбора папки?",
        "enter_folder_path": "Введите путь к папке",
        "folder_not_found": "Папка не найдена: {path}",
        "enter_folder_again": "Введите путь ещё раз",
        "checking_deps": "Проверяю базовые Python-компоненты для работы скрипта...",
        "choose_profile": "Выберите профиль качества или ручную настройку",
        "profile_min_label": "минимальное качество — быстро, грубо",
        "profile_min_help": "buffalo_sc, det_size 320, без upscale. Минимальная нагрузка, но хуже на маленьких/сложных лицах.",
        "profile_normal_label": "нормальное качество — лучший старт",
        "profile_normal_help": "Сбалансированный дефолт: buffalo_l, upscale 640, мягкий порог лица, best-face.",
        "profile_high_label": "высокое качество — усиленный поиск сложных лиц",
        "profile_high_help": "antelopev2, больший det_size и upscale, ниже пороги. Медленнее, но внимательнее к сложным фото.",
        "profile_max_label": "максимальное качество — самый тяжёлый готовый пресет, но не абсолютный предел",
        "profile_max_help": "antelopev2, det_size 1280, без уменьшения больших фото, сильный upscale. Тяжёлый, но ещё разумный пресет.",
        "profile_recmax_label": "максимум распознавания — экстремальный профиль, может упереться в VRAM/RAM",
        "profile_recmax_help": "antelopev2, det_size 2048, без уменьшения больших фото, очень мягкие пороги. Очень медленно, много памяти, больше review-мусора.",
        "profile_manual_label": "ручной режим — для экспериментов выше/ниже готовых профилей",
        "profile_manual_help": "Скрипт будет объяснять каждый параметр, диапазон и эффект меньшего/большего значения.",
        "gpu_title": "=== Проверка ускорения на GPU ===",
        "gpu_intro": "Этот шаг нужен только для ускорения. Если GPU не настроен, сортировка всё равно будет работать на CPU.",
        "has_nvidia": "На компьютере есть видеокарта NVIDIA?",
        "has_nvidia_help": "Если не уверены, можно ответить 'да': скрипт проверит nvidia-smi и ONNX Runtime. Системный драйвер NVIDIA скрипт не устанавливает.",
        "gpu_skipped": "GPU-мастер пропущен. Варианты моделей будут только для CPU.",
        "check_cuda_no_install": "Сначала проверяю CUDAExecutionProvider без установки/удаления пакетов...",
        "onnx_providers": "ONNX providers:",
        "cannot_determine": "не удалось определить",
        "cuda_found_no_install": "CUDAExecutionProvider найден. Ничего не устанавливаю и не удаляю.",
        "check_all_models_gpu": "Проверить все модели InsightFace на GPU сейчас?",
        "check_all_models_help": "Рекомендуется: так меню не покажет GPU-варианты для моделей, которые падают на smoke-test. Может скачать недостающие model packs и занять время.",
        "gpu_options_for": "GPU-варианты будут доступны для моделей:",
        "no_gpu_models_ok": "Ни одна модель не прошла GPU smoke-test. Варианты моделей будут только для CPU.",
        "gpu_can_do": "Что может сделать скрипт:",
        "gpu_can_1": "1. Установить/обновить Python-пакет onnxruntime-gpu[cuda,cudnn].",
        "gpu_can_2": "2. Проверить, появился ли CUDAExecutionProvider в ONNX Runtime.",
        "gpu_cannot": "Что скрипт НЕ делает: не устанавливает системный NVIDIA-драйвер и не меняет настройки Windows.",
        "install_gpu_packages": "CUDAExecutionProvider не найден. Скачать и установить Python-пакеты для ускорения на GPU?",
        "install_gpu_help": "Если пакеты уже настроены, этот вопрос обычно не появится. Установка удаляет только CPU-only пакет onnxruntime, если он реально установлен и мешает GPU wheel.",
        "gpu_install_failed": "Не удалось автоматически установить GPU-пакеты. Продолжаю диагностику; при необходимости дальше будут только CPU-варианты.",
        "recheck_cuda": "Повторно проверяю CUDAExecutionProvider...",
        "cuda_found": "CUDAExecutionProvider найден.",
        "gpu_model_check_skipped": "Проверка моделей пропущена. GPU-варианты будут доступны, но выбранная модель всё равно пройдёт smoke-test перед сканированием.",
        "cuda_not_found_cpu_only": "CUDAExecutionProvider не найден. Покажу только CPU-варианты моделей, чтобы не создавать ложное ощущение работы на GPU.",
        "show_gpu_diagnostics": "Показать подробную диагностику GPU сейчас?",
        "output_info": "Можно выбрать папку вручную. Если папку не выбрать, скрипт создаст рядом с input папку вида 'result 13-23 12.06.2026'. Двоеточие заменено на '-' потому что Windows не разрешает ':' в имени папки.",
        "open_output_dialog": "Открыть окно выбора output-папки?",
        "enter_output_or_auto": "Введите путь к output-папке или нажмите Enter для автосоздания",
        "unfinished_found": "Найдены незавершённые result-папки рядом с input:",
        "continue_run": "продолжить {name}",
        "create_new_result": "создать новую result-папку",
        "new_result_help": "Будет создана новая папка рядом с input, например: {name}",
        "continue_or_new": "Продолжить незавершённый запуск или создать новый результат?",
        "continue_soft_defaults": "Выбрана существующая result-папка. Для аккуратного продолжения defaults будут мягче: rescan=False и clean_folders=False, если вы не измените это в ручном режиме.",
        "created_output": "Создана output-папка: {path}",
        "selected_profile": "Выбран профиль: {title}.",
        "profile_warning": "Предупреждение профиля:",
        "profile_fixed_params": "Параметры распознавания зафиксированы профилем и не будут спрашиваться отдельно:",
        "preset_sort_questions": "Теперь вопросы только про сортировку, копирование, отчёты и создаваемые файлы.",
        "done": "Готово.",
    },
    "en": {
        "yes_no": "[yes/no]",
        "yes": "yes",
        "no": "no",
        "invalid_yes_no": "I did not understand the answer. Enter 'yes' or 'no' (also accepted: y/n).",
        "default_marker": " ← default",
        "enter_number": "Enter a number",
        "unknown_choice": "Unknown choice '{raw}'. Enter a number from the list: 1-{max}.",
        "enter_int": "Enter an integer.",
        "enter_float": "Enter a number, for example 0.55.",
        "below_min": "Value is below the recommended minimum {min_value}.",
        "above_max": "Value is above the recommended maximum {max_value}. This may slow down or cause memory errors.",
        "use_anyway": "Use this value anyway?",
        "range": "Range: {range}.",
        "minimum": "minimum {value}",
        "maximum": "maximum {value}",
        "lower_value": "Lower value: {text}",
        "higher_value": "Higher value: {text}",
        "can_enter_none": "You can enter {none_label}: automatic/empty mode.",
        "enter_value": "Enter value",
        "app_title": "=== Tuned Image Sorter v69.6: interactive mode ===",
        "language_auto": "Interface language selected automatically from system locale: English.",
        "input_title": "Select the input folder with source photos",
        "output_title": "Select the output folder for results",
        "open_folder_dialog": "Open folder picker window?",
        "enter_folder_path": "Enter folder path",
        "folder_not_found": "Folder not found: {path}",
        "enter_folder_again": "Enter the path again",
        "checking_deps": "Checking required Python components...",
        "choose_profile": "Choose a quality profile or manual setup",
        "profile_min_label": "minimum quality — fast, rough",
        "profile_min_help": "buffalo_sc, det_size 320, no upscaling. Lowest load, but worse for small/difficult faces.",
        "profile_normal_label": "normal quality — best starting point",
        "profile_normal_help": "Balanced default: buffalo_l, upscale 640, soft face threshold, best-face assignment.",
        "profile_high_label": "high quality — stronger search for difficult faces",
        "profile_high_help": "antelopev2, larger det_size and upscale, lower thresholds. Slower, but more attentive to difficult photos.",
        "profile_max_label": "maximum quality — heaviest ready preset, not an absolute limit",
        "profile_max_help": "antelopev2, det_size 1280, no downscaling of large photos, strong upscale. Heavy but still reasonably bounded.",
        "profile_recmax_label": "recognition maximum — extreme profile, may hit VRAM/RAM limits",
        "profile_recmax_help": "antelopev2, det_size 2048, no downscaling of large photos, very soft thresholds. Very slow, memory-heavy, more review noise.",
        "profile_manual_label": "manual mode — experiments above/below ready profiles",
        "profile_manual_help": "The script will explain every parameter, range, and the effect of lower/higher values.",
        "gpu_title": "=== GPU acceleration check ===",
        "gpu_intro": "This step is only for acceleration. If GPU is not configured, sorting will still work on CPU.",
        "has_nvidia": "Does this computer have an NVIDIA GPU?",
        "has_nvidia_help": "If unsure, answer 'yes': the script will check nvidia-smi and ONNX Runtime. The script does not install the NVIDIA system driver.",
        "gpu_skipped": "GPU wizard skipped. Only CPU model options will be shown.",
        "check_cuda_no_install": "Checking CUDAExecutionProvider first, without installing/removing packages...",
        "onnx_providers": "ONNX providers:",
        "cannot_determine": "could not determine",
        "cuda_found_no_install": "CUDAExecutionProvider found. Nothing will be installed or removed.",
        "check_all_models_gpu": "Check all InsightFace models on GPU now?",
        "check_all_models_help": "Recommended: the menu will hide GPU options for models that fail the smoke-test. This may download missing model packs and take time.",
        "gpu_options_for": "GPU options will be available for models:",
        "no_gpu_models_ok": "No model passed the GPU smoke-test. Only CPU model options will be shown.",
        "gpu_can_do": "What the script can do:",
        "gpu_can_1": "1. Install/upgrade the Python package onnxruntime-gpu[cuda,cudnn].",
        "gpu_can_2": "2. Check whether CUDAExecutionProvider appears in ONNX Runtime.",
        "gpu_cannot": "What the script does NOT do: it does not install the NVIDIA system driver and does not change Windows settings.",
        "install_gpu_packages": "CUDAExecutionProvider was not found. Download and install Python packages for GPU acceleration?",
        "install_gpu_help": "If packages are already configured, this question usually will not appear. Installation removes only the CPU-only onnxruntime package if it is actually installed and conflicts with the GPU wheel.",
        "gpu_install_failed": "Automatic GPU package installation failed. Continuing diagnostics; CPU-only options may be shown.",
        "recheck_cuda": "Checking CUDAExecutionProvider again...",
        "cuda_found": "CUDAExecutionProvider found.",
        "gpu_model_check_skipped": "Model check skipped. GPU options will be available, but the selected model will still run a smoke-test before scanning.",
        "cuda_not_found_cpu_only": "CUDAExecutionProvider was not found. Only CPU options will be shown to avoid pretending that GPU is working.",
        "show_gpu_diagnostics": "Show detailed GPU diagnostics now?",
        "output_info": "You can choose a folder manually. If you do not choose one, the script creates a folder next to input named like 'result 13-23 12.06.2026'. Colon is replaced with '-' because Windows does not allow ':' in folder names.",
        "open_output_dialog": "Open output folder picker window?",
        "enter_output_or_auto": "Enter output folder path or press Enter to create one automatically",
        "unfinished_found": "Unfinished result folders were found next to input:",
        "continue_run": "continue {name}",
        "create_new_result": "create a new result folder",
        "new_result_help": "A new folder will be created next to input, for example: {name}",
        "continue_or_new": "Continue an unfinished run or create a new result?",
        "continue_soft_defaults": "Existing result folder selected. For safe continuation, defaults will be softer: rescan=False and clean_folders=False unless you change them in manual mode.",
        "created_output": "Created output folder: {path}",
        "selected_profile": "Selected profile: {title}.",
        "profile_warning": "Profile warning:",
        "profile_fixed_params": "Recognition parameters are fixed by the profile and will not be asked separately:",
        "preset_sort_questions": "Now only sorting, copying, reports, and file-creation settings will be asked.",
        "done": "Done.",
    },
}

# Import-safe default. CLI/wizard calls set_language() before user interaction,
# while backend/UI imports can still use tr()/lang_text() safely.
LANG = "en"


def detect_system_language() -> str:
    """Detect the preferred UI language from environment variables and OS locale."""
    env_lang = (os.environ.get("FACE_SORTER_LANG") or "").strip().lower()
    if env_lang in {"ru", "en"}:
        return env_lang
    candidates: List[str] = []
    try:
        loc = locale.getlocale()[0]
        if loc:
            candidates.append(loc)
    except Exception:
        pass
    try:
        # locale.getdefaultlocale() is deprecated in Python 3.15, but remains a
        # useful fallback on some Windows setups. Keep --help output clean.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            loc = locale.getdefaultlocale()[0]
        if loc:
            candidates.append(loc)
    except Exception:
        pass
    for item in candidates:
        if str(item).lower().startswith("ru"):
            return "ru"
    return "en"


def set_language(lang: str = "auto") -> str:
    """Set the active UI language used by tr() and console prompts."""
    global LANG
    text = (lang or "auto").strip().lower()
    if text == "auto":
        text = detect_system_language()
    if text not in MESSAGES:
        text = "en"
    LANG = text
    return LANG


def tr(key: str, **kwargs: Any) -> str:
    """Translate a message key using the active language, falling back to English/key."""
    catalog = MESSAGES.get(LANG, MESSAGES["en"])
    template = catalog.get(key, MESSAGES["en"].get(key, key))
    try:
        return template.format(**kwargs)
    except Exception:
        return template


def lang_text(ru: str, en: str) -> str:
    """Return a language-specific string from a ru/en mapping."""
    return ru if LANG == "ru" else en

MODEL_INFO = {
    "buffalo_l": {
        "short": "рекомендуемая точность, средняя/высокая нагрузка",
        "details": "RetinaFace-10GF + ResNet50@WebFace600K, размер около 326 MB. Лучший старт для качества кластеров.",
        "speed": "медленнее buffalo_s/sc, но обычно стабильнее для сортировки архива",
        "accuracy": "MR-ALL 91.25; LFW 99.83; IJB-C(E4) 97.25",
    },
    "buffalo_m": {
        "short": "качество как buffalo_l, детектор легче",
        "details": "RetinaFace-2.5GF + ResNet50@WebFace600K, размер около 313 MB. Может быть быстрее на детекции, при этом recognition-качество заявлено как у buffalo_l.",
        "speed": "часто быстрее buffalo_l на поиске лиц",
        "accuracy": "официально: same accuracy with buffalo_l",
    },
    "buffalo_s": {
        "short": "быстрее и легче, но заметно ниже точность",
        "details": "RetinaFace-500MF + MobileFaceNet@WebFace600K, размер около 159 MB. Подходит для быстрых тестов и слабого ПК, но чаще дробит/путает людей.",
        "speed": "быстрее buffalo_l/m",
        "accuracy": "MR-ALL 71.87; LFW 99.70; IJB-C(E4) 95.02",
    },
    "buffalo_sc": {
        "short": "самая лёгкая модель, только detection+recognition",
        "details": "RetinaFace-500MF + MobileFaceNet@WebFace600K, размер около 16 MB, без alignment/age/gender. Для нашей задачи может работать, но качество как у buffalo_s.",
        "speed": "обычно самый лёгкий вариант",
        "accuracy": "официально: same accuracy with buffalo_s",
    },
    "antelopev2": {
        "short": "экспериментальный для этого скрипта; часто ломается из-за model-pack структуры",
        "details": "Тяжёлый альтернативный pack. В некоторых установках InsightFace пакет antelopev2 распаковывается не так, как ожидает FaceAnalysis, и возникает assert 'detection' in self.models. Для обычной сортировки фото рекомендую buffalo_l или buffalo_m.",
        "speed": "тяжелее по размеру и не обязательно быстрее/стабильнее buffalo_l",
        "accuracy": "может быть полезен как эксперимент, но не является дефолтным выбором для этого MVP",
        "experimental": True,
    },
}



# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------
# Model-specific defaults and schemas live here so future engines can add
# parameters without polluting the global RunConfig namespace.
MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    name: {
        "engine": "insightface",
        "display_name": name,
        "supports_gpu": True,
        "supports_detection": True,
        "supports_embeddings": True,
        "info": MODEL_INFO.get(name, {}),
        "default_params": {
            "det_size": 640 if name not in {"buffalo_s", "buffalo_sc"} else 320,
            "min_det_score": 0.30 if name not in {"buffalo_s", "buffalo_sc"} else 0.45,
            "min_face_size": 12 if name not in {"buffalo_s", "buffalo_sc"} else 28,
        },
        "param_schema": {
            "det_size": {
                "type": "int",
                "min": 320,
                "max": 2048,
                "default": 640 if name not in {"buffalo_s", "buffalo_sc"} else 320,
                "description_ru": "Размер окна детектора лиц InsightFace.",
                "description_en": "InsightFace face detector window size.",
            },
            "min_det_score": {
                "type": "float",
                "min": 0.05,
                "max": 0.90,
                "default": 0.30 if name not in {"buffalo_s", "buffalo_sc"} else 0.45,
                "description_ru": "Минимальная уверенность детектора лица.",
                "description_en": "Minimum face detector confidence.",
            },
            "min_face_size": {
                "type": "int",
                "min": 2,
                "max": 100,
                "default": 12 if name not in {"buffalo_s", "buffalo_sc"} else 28,
                "description_ru": "Минимальный размер лица после resize/upscale.",
                "description_en": "Minimum face size after resize/upscale.",
            },
        },
    }
    for name in KNOWN_MODELS
}

# Per-model overrides make future engines safer: a new model can add its own
# parameters without polluting the global config or hiding a model-specific knob.
MODEL_REGISTRY["antelopev2"]["info"] = {**MODEL_REGISTRY["antelopev2"].get("info", {}), "experimental": True}
MODEL_REGISTRY["antelopev2"]["default_params"].update({"det_size": 768, "min_det_score": 0.25, "min_face_size": 8})
MODEL_REGISTRY["antelopev2"]["param_schema"]["det_size"].update({"default": 768, "max": 2048})
MODEL_REGISTRY["antelopev2"]["param_schema"]["min_det_score"].update({"default": 0.25})
MODEL_REGISTRY["antelopev2"]["param_schema"]["min_face_size"].update({"default": 8})


def model_param_schema(model_name: str) -> Dict[str, Dict[str, Any]]:
    """Return the parameter schema for a registered recognition model."""
    return dict(MODEL_REGISTRY.get(normalize_model_name(model_name), {}).get("param_schema", {}))


def model_default_params(model_name: str) -> Dict[str, Any]:
    """Return model-specific default parameters from MODEL_REGISTRY."""
    return dict(MODEL_REGISTRY.get(normalize_model_name(model_name), {}).get("default_params", {}))


QUALITY_PROFILES = {
    "minimum": {
        "title": "минимальное качество",
        "short": "быстро, грубо",
        "settings": {
            **DEFAULT_PROFILE,
            "model": "buffalo_sc",
            "det_size": 320,
            "max_side": 1200,
            "upscale_small_to": 0,
            "min_det_score": 0.45,
            "min_face_size": 28,
            "min_cluster_size": 8,
            "report_faces_per_cluster": 20,
        },
        "effect": "Быстро, грубо: минимальная нагрузка на CPU/GPU и память, но чаще пропускает мелкие/сложные лица и может хуже группировать похожие фото.",
    },
    "normal": {
        "title": "нормальное качество",
        "short": "лучший старт",
        "settings": dict(DEFAULT_PROFILE),
        "effect": "Лучший старт для большинства архивов: buffalo_l, upscale 640, мягкий порог детектора и best-face без размножения фото по папкам.",
    },
    "high": {
        "title": "высокое качество",
        "short": "усиленный поиск сложных лиц",
        "settings": {
            **DEFAULT_PROFILE,
            "model": "antelopev2",
            "det_size": 768,
            "max_side": 2200,
            "upscale_small_to": 960,
            "min_det_score": 0.25,
            "min_face_size": 8,
            "min_cluster_size": 4,
            "report_faces_per_cluster": 60,
        },
        "effect": "Усиленный поиск сложных лиц: медленнее нормального профиля, зато выше шанс найти слабые/маленькие лица. Возможны дополнительные ложные лица, которые уйдут в review.",
    },
    "maximum": {
        "title": "максимальное качество",
        "short": "самый тяжёлый готовый пресет, но не абсолютный предел",
        "settings": {
            **DEFAULT_PROFILE,
            "model": "antelopev2",
            "det_size": 1280,
            "max_side": 0,
            "upscale_small_to": 1280,
            "min_det_score": 0.15,
            "min_face_size": 4,
            "min_cluster_size": 3,
            "cluster_selection_method": "leaf",
            "report_faces_per_cluster": 100,
        },
        "effect": "Самый тяжёлый готовый пресет, но не абсолютный предел: агрессивные настройки пайплайна для поиска мелких и слабых лиц. Выше можно пробовать вручную, но резко растут время, память и мусор в review.",
    },
    "recognition_max": {
        "title": "максимум распознавания",
        "short": "экстремальный профиль: максимально агрессивный готовый поиск лиц",
        "settings": {
            **DEFAULT_PROFILE,
            "model": "antelopev2",
            # Практический максимум готового профиля в этом скрипте. Жёсткий предел зависит
            # от модели, драйвера, ONNX Runtime, VRAM/RAM и размера конкретных фото.
            "det_size": 2048,
            "max_side": 0,
            "upscale_small_to": 2048,
            "min_det_score": 0.08,
            "min_face_size": 2,
            "min_cluster_size": 2,
            "cluster_selection_method": "leaf",
            "report_faces_per_cluster": 150,
        },
        "effect": "Максимально агрессивный готовый профиль: не уменьшает большие фото, сильно увеличивает маленькие, ставит очень мягкие пороги поиска лиц. Может работать очень медленно, упереться в VRAM/RAM и дать много ложных лиц в review. Это режим для сложных архивов и экспериментов, а не безопасный дефолт.",
        "warning": "Внимание: профиль может быть очень медленным и может упереться в VRAM/RAM. При ошибках памяти используйте максимальное или высокое качество.",
    },
}


PIP_PACKAGES = {
    "numpy": "numpy",
    "PIL": "Pillow",
    "tqdm": "tqdm",
    "cv2": "opencv-python",
    "sklearn": "scikit-learn",
    "insightface": "insightface",
    "onnxruntime": "onnxruntime",
}
OPTIONAL_PIP_PACKAGES = {
    "pillow_heif": "pillow-heif",
}


# ---------------------------------------------------------------------------
# Console progress callbacks
# ---------------------------------------------------------------------------
class ConsoleProgressCallbacks(ProgressCallbacks):
    """Console callback implementation used by CLI.

    It intentionally owns console output for stage/progress events generated through
    ``print_stage`` / ``print_*_progress`` so a future GUI callback can swap behavior
    without changing the pipeline.
    """

    handles_console_output = True

    def on_stage(self, stage: str, message: str = "", **data: Any) -> None:
        print("\n" + "=" * 72)
        print(stage)
        if message:
            print_wrapped(message)
        print("=" * 72)

    def on_progress(self, stage: str, done: int, total: Optional[int] = None, **data: Any) -> None:
        stats = data.get("stats") or {}
        elapsed = max(0.001, float(data.get("elapsed") or 0.001))
        unit = data.get("unit") or "items"
        rate_label = data.get("rate_label") or f"{unit}/мин"
        per_min = done / elapsed * 60.0
        if stage == "scan":
            print(
                "\n[Статистика] "
                f"{done}/{total} фото | "
                f"новых/пересканировано: {stats.get('scanned', 0)} | "
                f"кэш: {stats.get('skipped_cached', 0)} | "
                f"дубли: {stats.get('skipped_duplicates', 0)} | "
                f"с лицами: {stats.get('images_with_faces', 0)} | "
                f"без лиц: {stats.get('no_faces', 0)} | "
                f"лиц сохранено: {stats.get('faces_saved', 0)} | "
                f"ошибок: {stats.get('errors', 0)} | "
                f"timeout: {stats.get('timeouts', 0)} | "
                f"скорость: {per_min:.1f} фото/мин"
            )
            return
        if stage == "copy":
            print(
                "\n[Сортировка/копирование] "
                f"{done}/{total} файлов | "
                f"people: {stats.get('copied_people', 0)} | "
                f"review: {stats.get('copied_review', 0)} | "
                f"group_photos: {stats.get('copied_group', 0)} | "
                f"пропущено: {stats.get('missing_sources', 0)} | "
                f"дубли-skip: {stats.get('skipped_duplicates', 0)} | "
                f"ошибок: {stats.get('copy_errors', 0)} | "
                f"скорость: {per_min:.1f} файлов/мин"
            )
            return
        total_text = f"/{total}" if total is not None else ""
        print(f"\n[{stage}] {done}{total_text} | скорость: {per_min:.1f} {rate_label}")

    def on_warning(self, stage: str, message: str, **data: Any) -> None:
        print(f"\n[warning:{stage}] {message}")

    def on_error(self, stage: str, message: str, **data: Any) -> None:
        print(f"\n[error:{stage}] {message}")

    def on_info(self, stage: str, message: str, **data: Any) -> None:
        print(message)


def active_callbacks() -> ProgressCallbacks:
    """Return the currently installed progress callbacks or a null implementation."""
    return CURRENT_CALLBACKS or ProgressCallbacks()


def emit_stage(stage: str, message: str = "", **data: Any) -> None:
    """Notify callbacks that the pipeline entered a new stage."""
    cb = active_callbacks()
    cb.on_stage(stage, message, **data)


def emit_progress(stage: str, done: int, total: Optional[int] = None, **data: Any) -> None:
    """Notify callbacks about stage progress without binding to console output."""
    cb = active_callbacks()
    cb.on_progress(stage, done, total, **data)


def emit_warning(stage: str, message: str, **data: Any) -> None:
    """Notify callbacks about a non-fatal warning."""
    cb = active_callbacks()
    cb.on_warning(stage, message, **data)


def emit_error(stage: str, message: str, **data: Any) -> None:
    """Notify callbacks about an error that should be visible to users."""
    cb = active_callbacks()
    cb.on_error(stage, message, **data)


def run_config_from_namespace(ns: argparse.Namespace) -> RunConfig:
    """Build RunConfig from either CLI args or the interactive wizard namespace."""
    d = vars(ns)
    return RunConfig(
        input_dir=file_normalize_path(d["input"], must_exist=False) if d.get("input") else None,
        output_dir=file_normalize_path(d["output"], must_exist=False) if d.get("output") else None,
        project_dir=file_normalize_path(d["project"], must_exist=False) if d.get("project") else (file_normalize_path(d["output"], must_exist=False) if d.get("output") else None),
        mode=d.get("mode", "all"),
        profile=d.get("scan_profile", d.get("profile", "normal")),
        language=d.get("lang", "auto"),
        db_path=file_normalize_path(d["db"], must_exist=False) if d.get("db") else None,
        names_path=file_normalize_path(d["names"], must_exist=False) if d.get("names") else None,
        model=normalize_model_name(d.get("model", DEFAULT_PROFILE["model"])),
        use_gpu=bool(d.get("gpu", False)),
        auto_cpu_fallback=bool(d.get("auto_cpu_fallback", not d.get("no_auto_cpu_fallback", False))),
        det_size=int(d.get("det_size", DEFAULT_PROFILE["det_size"])),
        max_side=int(d.get("max_side", DEFAULT_PROFILE["max_side"])),
        upscale_small_to=int(d.get("upscale_small_to", DEFAULT_PROFILE["upscale_small_to"])),
        min_det_score=float(d.get("min_det_score", DEFAULT_PROFILE["min_det_score"])),
        min_face_size=int(d.get("min_face_size", DEFAULT_PROFILE["min_face_size"])),
        rescan=bool(d.get("rescan", DEFAULT_PROFILE["rescan"])),
        commit_every=int(d.get("commit_every", DEFAULT_PROFILE["commit_every"])),
        progress_every=int(d.get("progress_every", DEFAULT_PROFILE["progress_every"])),
        algorithm=d.get("algo", d.get("algorithm", DEFAULT_PROFILE["algo"])),
        min_cluster_size=int(d.get("min_cluster_size", DEFAULT_PROFILE["min_cluster_size"])),
        min_samples=d.get("min_samples", DEFAULT_PROFILE["min_samples"]),
        cluster_selection_method=d.get("cluster_selection_method", DEFAULT_PROFILE["cluster_selection_method"]),
        dbscan_eps=float(d.get("dbscan_eps", DEFAULT_PROFILE["dbscan_eps"])),
        photo_assignment=d.get("photo_assignment", DEFAULT_PROFILE["photo_assignment"]),
        copy_group_photos=bool(d.get("copy_group_photos", DEFAULT_PROFILE["copy_group_photos"])),
        filename_fallback=bool(d.get("filename_fallback", DEFAULT_PROFILE["filename_fallback"])),
        filename_max_distance=int(d.get("filename_max_distance", DEFAULT_PROFILE["filename_max_distance"])),
        clean_folders=bool(d.get("clean_folders", DEFAULT_PROFILE["clean_folders"])),
        clean_final=bool(d.get("clean_final", DEFAULT_PROFILE["clean_final"])),
        overwrite_names=bool(d.get("overwrite_names", DEFAULT_PROFILE["overwrite_names"])),
        report_faces_per_cluster=int(d.get("report_faces_per_cluster", DEFAULT_PROFILE["report_faces_per_cluster"])),
        dry_run=bool(d.get("dry_run", DEFAULT_PROFILE["dry_run"])),
        verbose=bool(d.get("verbose", DEFAULT_PROFILE["verbose"])),
        auto_install=bool(d.get("auto_install", False)),
        auto_gpu_install=bool(d.get("auto_gpu_install", False)),
        gpu_smoke_test=bool(d.get("gpu_smoke_test", False)),
        gpu_smoke_test_all=bool(d.get("gpu_smoke_test_all", False)),
        skip_gpu_smoke_test=bool(d.get("skip_gpu_smoke_test", False)),
        force_env_check=bool(d.get("force_env_check", False)),
        make_bug_report=bool(d.get("make_bug_report", False)),
        file_timeout=str(d.get("file_timeout", DEFAULT_PROFILE.get("file_timeout", "auto"))),
        disable_scan_worker=bool(d.get("disable_scan_worker", DEFAULT_PROFILE.get("disable_scan_worker", False))),
        scan_workers=str(d.get("scan_workers", DEFAULT_PROFILE.get("scan_workers", "auto"))),
        copy_workers=str(d.get("copy_workers", DEFAULT_PROFILE.get("copy_workers", "auto"))),
        reuse_problem_cache=bool(d.get("reuse_problem_cache", DEFAULT_PROFILE.get("reuse_problem_cache", True))),
        duplicate_check=d.get("duplicate_check", DEFAULT_PROFILE.get("duplicate_check", "exact")),
        duplicate_policy=d.get("duplicate_policy", DEFAULT_PROFILE.get("duplicate_policy", "scan-one-copy-all")),
        strict_image_extensions=bool(d.get("strict_image_extensions", DEFAULT_PROFILE.get("strict_image_extensions", False))),
        resume_existing_output=bool(d.get("resume_existing_output", False)),
        gpu_allowed_models=d.get("gpu_allowed_models"),
        gpu_model_smoke_results=d.get("gpu_model_smoke_results"),
    )


def run_config_from_profile(profile_key: str, input_dir: Path, output_dir: Path, **overrides: Any) -> RunConfig:
    """Build RunConfig from a quality profile plus explicit overrides.

    This is the intended entry point for a future GUI preset button.
    """
    profile = QUALITY_PROFILES.get(profile_key, QUALITY_PROFILES["normal"])
    cfg = dict(profile["settings"])
    cfg.update(overrides)
    cfg.update({
        "input": str(input_dir),
        "output": str(output_dir),
        "scan_profile": profile_key,
    })
    return run_config_from_namespace(argparse.Namespace(**cfg))


def validate_run_config(config: RunConfig) -> None:
    """Validate a normalized RunConfig before executing pipeline stages."""
    if config.mode in {"install-hint", "diagnose-gpu", "make-bug-report", "bug-report", "support-bundle", "result-health"}:
        return
    if config.mode in {"scan", "cluster", "assign", "copy", "report", "all"} and not config.input_dir:
        raise SystemExit("Для этого режима нужен input_dir/--input или запустите без параметров для интерактивного режима.")
    if not config.output_dir:
        raise SystemExit("Нужен output_dir/--output или input_dir/--input для автосоздания result-папки.")
    if config.input_dir and (not config.input_dir.exists() or not config.input_dir.is_dir()):
        raise SystemExit(f"Не найдена input-папка: {config.input_dir}")
    ensure_dir(config.output_dir)


def write_run_config_json(config: RunConfig, output_dir: Path) -> Path:
    """Persist the normalized RunConfig used for a run.

    This file is the future UI/API contract artifact and is also useful for bug reports.
    """
    reports_dir = output_dir / "reports"
    ensure_dir(reports_dir)
    path = reports_dir / "run_config.json"
    payload = {
        "script_version": SCRIPT_VERSION,
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        "config": config.to_json_dict(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# -----------------------------------------------------------------------------
# Dependency and environment helpers
# -----------------------------------------------------------------------------

def is_interactive_terminal() -> bool:
    """Return True when stdin/stdout look suitable for interactive prompts."""
    try:
        return sys.stdin.isatty()
    except Exception:
        return False


def module_available(module_name: str) -> bool:
    """Return True if a Python module can be imported without actually importing heavy deps."""
    try:
        importlib.import_module(module_name)
        return True
    except Exception:
        return False


def pip_install(packages: Sequence[str]) -> bool:
    """Install packages into the current Python environment using python -m pip."""
    cmd = [sys.executable, "-m", "pip", "install", *packages]
    print("\n" + lang_text("Устанавливаю:", "Installing:"), " ".join(packages))
    print(lang_text("Команда:", "Command:"), " ".join(cmd))
    proc = subprocess.run(cmd)
    return proc.returncode == 0


def pip_uninstall(packages: Sequence[str]) -> bool:
    """Uninstall packages from the current Python environment using python -m pip."""
    cmd = [sys.executable, "-m", "pip", "uninstall", "-y", *packages]
    print("\n" + lang_text("Удаляю конфликтующие пакеты:", "Removing conflicting packages:"), " ".join(packages))
    print(lang_text("Команда:", "Command:"), " ".join(cmd))
    proc = subprocess.run(cmd)
    return proc.returncode == 0


def pip_show(package: str) -> str:
    """Return pip show output for diagnostics, or None when unavailable."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "show", package],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=30,
            creationflags=windows_no_window_creationflags(),
        )
        return proc.stdout.strip() if proc.returncode == 0 else ""
    except Exception:
        return ""


def install_onnxruntime_gpu_stack(force_reinstall: bool = False) -> bool:
    """Install/update ONNX Runtime GPU packages and CUDA/cuDNN wheel extras."""
    print("\n" + lang_text("Будет выполнена установка/проверка GPU-сборки ONNX Runtime.", "Installing/checking the GPU build of ONNX Runtime."))
    print(lang_text("Это НЕ ставит драйвер NVIDIA. Драйвер должен быть установлен в системе заранее.", "This does NOT install the NVIDIA driver. The driver must already be installed."))
    print(lang_text("Начиная с новых версий onnxruntime-gpu можно ставить CUDA/cuDNN DLL через extra [cuda,cudnn].", "Recent onnxruntime-gpu versions can install CUDA/cuDNN DLLs via the [cuda,cudnn] extras."))

    # Do not uninstall anything if CUDAExecutionProvider is already visible. In v8 the wizard asked
    # about installation before the provider check, which created the impression that default mode
    # 'removes GPU packages'. The only uninstall we ever do is CPU-only onnxruntime, and only when
    # CUDA provider is not visible or user explicitly requests reinstall.
    providers_before = available_onnx_providers()
    if "CUDAExecutionProvider" in providers_before and not force_reinstall:
        print(lang_text("CUDAExecutionProvider уже найден. Пакеты не переустанавливаю и ничего не удаляю.", "CUDAExecutionProvider already found. Packages will not be reinstalled and nothing will be removed."))
        print("ONNX providers:", providers_before)
        return True

    # CPU and GPU wheels expose the same Python module name `onnxruntime`, so CPU wheel can shadow/conflict.
    if installed_distribution_version("onnxruntime") != "не установлен":
        pip_uninstall(["onnxruntime"])
    else:
        print(lang_text("CPU-only пакет onnxruntime не установлен — удалять нечего.", "CPU-only onnxruntime is not installed — nothing to remove."))
    return pip_install(["--upgrade", "onnxruntime-gpu[cuda,cudnn]"])


# ---------------------------------------------------------------------------
# Dependency and environment checks
# ---------------------------------------------------------------------------
def ensure_dependencies(args: argparse.Namespace) -> None:
    """Check required packages and optionally install missing dependencies."""
    if getattr(args, "mode", "all") == "install-hint":
        return

    required = dict(PIP_PACKAGES)
    if getattr(args, "gpu", False):
        # Same import name, but GPU mode needs the GPU wheel, not CPU-only onnxruntime.
        required["onnxruntime"] = "onnxruntime-gpu[cuda,cudnn]"
    if getattr(args, "algo", "hdbscan") == "hdbscan":
        required["hdbscan"] = "hdbscan"

    missing = []
    for module_name, package_name in required.items():
        if not module_available(module_name):
            missing.append(package_name)

    # pillow-heif is useful but not fatal; install prompt includes it only if missing.
    optional_missing = []
    for module_name, package_name in OPTIONAL_PIP_PACKAGES.items():
        if not module_available(module_name):
            optional_missing.append(package_name)

    if missing:
        print("\n" + lang_text("Не найдены необходимые компоненты:", "Required components are missing:"))
        for p in missing:
            print(f"  - {p}")
        if optional_missing:
            print("\n" + lang_text("Дополнительно для HEIC/HEIF можно установить:", "Additionally, for HEIC/HEIF you can install:"))
            for p in optional_missing:
                print(f"  - {p}")

        install_list = list(dict.fromkeys(missing))
        if getattr(args, "auto_install", False):
            ok = pip_install(install_list)
            if not ok:
                raise SystemExit("Не удалось установить зависимости автоматически. Попробуйте: python -m pip install -r requirements.txt")
        elif is_interactive_terminal():
            if ask_yes_no_strict("\nУстановить отсутствующие компоненты сейчас?", True):
                ok = pip_install(install_list)
                if not ok:
                    raise SystemExit("Не удалось установить зависимости автоматически. Попробуйте: python -m pip install -r requirements.txt")
            else:
                raise SystemExit("Остановка: не хватает зависимостей.")
        else:
            raise SystemExit("Не хватает зависимостей. Выполните: python -m pip install -r requirements.txt")

    if getattr(args, "gpu", False):
        check_gpu_runtime(args)


def load_runtime_modules() -> None:
    """Import heavy runtime modules after dependencies have been checked."""
    global np, Image, ImageOps, tqdm, pillow_heif
    if np is not None:
        return
    import numpy as _np
    from PIL import Image as _Image, ImageOps as _ImageOps
    from tqdm import tqdm as _tqdm

    np = _np
    Image = _Image
    ImageOps = _ImageOps
    tqdm = _tqdm
    try:
        import pillow_heif as _pillow_heif  # type: ignore
        _pillow_heif.register_heif_opener()
        pillow_heif = _pillow_heif
    except Exception:
        pillow_heif = None


def windows_no_window_creationflags() -> int:
    """Return CREATE_NO_WINDOW for captured Windows subprocess diagnostics.

    In a PyInstaller windowed GUI, launching console helpers such as nvidia-smi
    without this flag can flash a terminal window for a fraction of a second.
    Console diagnostics launched through TunedImageSorter_CLI.exe remain visible;
    this flag is only used for captured child-process probes.
    """
    if os.name != "nt":
        return 0
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))


def run_capture(cmd: Sequence[str], timeout: int = 20) -> Tuple[int, str]:
    """Run a subprocess and return stdout/stderr text for diagnostics."""
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            creationflags=windows_no_window_creationflags(),
        )
        return int(proc.returncode), (proc.stdout or "").strip()
    except FileNotFoundError:
        return 127, "command not found"
    except Exception as exc:
        return 1, str(exc)


def installed_distribution_version(name: str) -> str:
    """Return an installed package version using importlib.metadata."""
    try:
        return importlib.metadata.version(name)
    except Exception:
        return "не установлен"


def preload_onnxruntime_cuda_dlls(verbose: bool = False) -> None:
    """Best-effort preload for CUDA/cuDNN DLLs provided by onnxruntime-gpu or PyTorch."""
    try:
        # Important on Windows: add directories containing cuDNN sublibraries before importing ORT.
        # Otherwise provider may be listed, but real Conv execution can fail with
        # 'Could not locate cudnn_engines_tensor_ir64_9.dll'.
        add_nvidia_cuda_dll_directories(verbose=verbose)
        import onnxruntime as ort
        preload = getattr(ort, "preload_dlls", None)
        if callable(preload):
            # directory="" means: search NVIDIA site-packages first, as recommended by ORT docs.
            try:
                preload(cuda=True, cudnn=True, msvc=True, directory="")
            except TypeError:
                try:
                    preload(directory="")
                except TypeError:
                    preload()
            except Exception:
                pass
            try:
                preload()
            except Exception:
                pass
            if verbose:
                print(lang_text("ONNX Runtime preload_dlls: выполнено", "ONNX Runtime preload_dlls: done"))
        elif verbose:
            print(lang_text("ONNX Runtime preload_dlls: функция недоступна в этой версии", "ONNX Runtime preload_dlls: unavailable in this version"))
    except Exception as exc:
        if verbose:
            print(lang_text("ONNX Runtime preload_dlls: ошибка:", "ONNX Runtime preload_dlls error:"), exc)


def available_onnx_providers() -> List[str]:
    """Return ONNX Runtime execution providers after CUDA DLL preload attempts."""
    try:
        preload_onnxruntime_cuda_dlls(verbose=False)
        import onnxruntime as ort
        return list(ort.get_available_providers())
    except Exception:
        return []


def diagnose_gpu_environment(verbose: bool = True) -> Dict[str, Any]:
    """Print and return a compact CUDA/ONNX Runtime diagnostic report."""
    info: Dict[str, Any] = {}
    print("\n" + lang_text("=== Диагностика GPU/ONNX Runtime ===", "=== GPU/ONNX Runtime diagnostics ==="))
    print("Python:", sys.version.replace("\n", " "))
    print("Python exe:", sys.executable)
    print("OS:", platform.platform())
    print("onnxruntime:", installed_distribution_version("onnxruntime"))
    print("onnxruntime-gpu:", installed_distribution_version("onnxruntime-gpu"))

    code, out = run_capture(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"], timeout=15)
    if code == 0 and out:
        print("NVIDIA GPU:")
        for line in out.splitlines():
            print("  ", line)
        info["nvidia_smi"] = out
    else:
        print(lang_text("NVIDIA GPU: nvidia-smi не найден или драйвер не отвечает", "NVIDIA GPU: nvidia-smi was not found or the driver did not respond"))
        info["nvidia_smi"] = None

    try:
        import onnxruntime as ort
        print("ONNX Runtime module version:", getattr(ort, "__version__", "unknown"))
        try:
            preload_onnxruntime_cuda_dlls(verbose=True)
        except Exception:
            pass
        providers = list(ort.get_available_providers())
        print("ONNX providers:", providers)
        info["providers"] = providers
        if verbose and os.name == "nt":
            print("\n" + lang_text("Проверка ключевых CUDA/cuDNN DLL в Python site-packages:", "Checking key CUDA/cuDNN DLLs in Python site-packages:"))
            dlls = find_cuda_runtime_dlls()
            for name, hits in dlls.items():
                if hits:
                    print(f"  {name}: " + lang_text("найдено", "found") + f" {len(hits)}")
                    for h in hits[:3]:
                        print("    ", h)
                else:
                    print(f"  {name}: " + lang_text("НЕ НАЙДЕНО", "NOT FOUND"))
        if verbose and hasattr(ort, "print_debug_info"):
            print("\nONNX Runtime debug info:")
            try:
                ort.print_debug_info()
            except Exception as exc:
                print(lang_text("  print_debug_info не сработал:", "  print_debug_info failed:"), exc)
    except Exception as exc:
        print("ONNX Runtime import/check error:", exc)
        info["providers"] = []

    if "CUDAExecutionProvider" in info.get("providers", []):
        print("\n" + lang_text("Итог: CUDAExecutionProvider доступен. Можно пробовать GPU-режим.", "Result: CUDAExecutionProvider is available. GPU mode can be tested."))
    else:
        print("\n" + lang_text("Итог: CUDAExecutionProvider недоступен. Скрипт будет использовать CPU, пока GPU-стек не настроен.", "Result: CUDAExecutionProvider is unavailable. The script will use CPU until the GPU stack is configured."))
    return info


def gpu_real_inference_smoke_test(model_name: str = DEFAULT_MODEL, det_size: int = 640, verbose: bool = True) -> bool:
    """Run a tiny real InsightFace inference on CUDA.

    get_available_providers() only proves that ONNX Runtime can *see* CUDAExecutionProvider.
    It does not prove that cuDNN sublibraries can execute a Conv node. This test creates
    InsightFace sessions on CUDA and runs the detector on a synthetic image. No user photos
    are read. It may download the selected InsightFace model pack if it is not cached yet.
    """
    if verbose:
        print("\n" + lang_text("=== Реальная проверка GPU-инференса InsightFace ===", "=== Real InsightFace GPU inference smoke-test ==="))
        print(lang_text("Проверяю не только наличие CUDAExecutionProvider, а реальный запуск модели на GPU.", "Checking not only CUDAExecutionProvider presence, but a real model run on GPU."))
        print(lang_text("Фото пользователя не используются: создаётся пустое тестовое изображение.", "User photos are not used: an empty test image is created."))
    providers = available_onnx_providers()
    if "CUDAExecutionProvider" not in providers:
        if verbose:
            print(lang_text("CUDAExecutionProvider не найден, smoke-test невозможен.", "CUDAExecutionProvider was not found; smoke-test is impossible."))
        return False
    try:
        preload_onnxruntime_cuda_dlls(verbose=False)
        import numpy as _np
        from insightface.app import FaceAnalysis
        model_name = normalize_model_name(model_name)
        det_size = int(det_size or 640)
        det_size = max(128, min(1280, det_size))
        app = FaceAnalysis(name=model_name, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        app.prepare(ctx_id=0, det_size=(det_size, det_size))
        used = insightface_session_providers(app)
        if "CUDAExecutionProvider" not in used:
            if verbose:
                print(lang_text("InsightFace session providers не содержат CUDAExecutionProvider:", "InsightFace session providers do not include CUDAExecutionProvider:"), used or lang_text("не удалось определить", "could not determine"))
            return False
        # Uniform gray image is enough to force the detector's convolution graph to execute.
        img = _np.full((det_size, det_size, 3), 127, dtype=_np.uint8)
        _ = app.get(img)
        if verbose:
            print(lang_text("OK: реальная модель InsightFace выполнилась на CUDA без ошибки cuDNN.", "OK: the real InsightFace model ran on CUDA without a cuDNN error."))
            print("Session providers:", used)
        return True
    except Exception as exc:
        if looks_like_missing_detection_assertion(exc):
            repaired = repair_nested_model_pack(model_name, verbose=verbose)
            if repaired:
                try:
                    from insightface.app import FaceAnalysis
                    app = FaceAnalysis(name=model_name, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
                    app.prepare(ctx_id=0, det_size=(det_size, det_size))
                    used = insightface_session_providers(app)
                    img = _np.full((det_size, det_size, 3), 127, dtype=_np.uint8)
                    _ = app.get(img)
                    if verbose:
                        print(lang_text("OK: после исправления model-pack модель выполнилась на CUDA.", "OK: after fixing the model-pack, the model ran on CUDA."))
                        print("Session providers:", used)
                    return True
                except Exception as exc2:
                    exc = exc2
        if verbose:
            print(lang_text("GPU smoke-test НЕ ПРОЙДЕН.", "GPU smoke-test FAILED."))
            if looks_like_missing_detection_assertion(exc):
                print(lang_text("Это не похоже на проблему CUDA. InsightFace не нашёл detection-модель в выбранном model-pack.", "This does not look like a CUDA problem. InsightFace did not find a detection model in the selected model-pack."))
                print_model_pack_hint(model_name)
            else:
                print(lang_text("Это значит: CUDAExecutionProvider виден, но реальное выполнение модели на GPU падает.", "This means CUDAExecutionProvider is visible, but real GPU model execution fails."))
            print(lang_text("Ошибка:", "Error:"), (repr(exc) + " " + str(exc))[:2500])
            if looks_like_cuda_runtime_error(exc):
                print(lang_text("Похоже на проблему CUDA/cuDNN runtime или загрузки cuDNN sublibrary DLL.", "This looks like a CUDA/cuDNN runtime or cuDNN sublibrary DLL loading problem."))
        return False




def gpu_model_smoke_test_details(model_name: str = DEFAULT_MODEL, det_size: int = 640) -> Dict[str, Any]:
    """Return structured GPU smoke-test result for a single InsightFace model pack.

    This is intentionally separate from gpu_real_inference_smoke_test(), because the
    multi-model checker needs a compact machine-readable result: OK, error kind,
    session providers and a short error message. No user photos are used.
    """
    result: Dict[str, Any] = {
        "model": normalize_model_name(model_name),
        "ok": False,
        "kind": "unknown",
        "message": "",
        "providers": [],
    }
    providers = available_onnx_providers()
    if "CUDAExecutionProvider" not in providers:
        result["kind"] = "no-cuda-provider"
        result["message"] = "CUDAExecutionProvider не найден в ONNX Runtime."
        result["providers"] = providers
        return result

    try:
        preload_onnxruntime_cuda_dlls(verbose=False)
        import numpy as _np
        from insightface.app import FaceAnalysis

        model = result["model"]
        size = int(det_size or 640)
        size = max(128, min(1280, size))
        app = FaceAnalysis(name=model, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        app.prepare(ctx_id=0, det_size=(size, size))
        used = insightface_session_providers(app)
        result["providers"] = used
        if "CUDAExecutionProvider" not in used:
            result["kind"] = "provider-not-applied"
            result["message"] = f"InsightFace session providers не содержат CUDAExecutionProvider: {used}"
            return result
        img = _np.full((size, size, 3), 127, dtype=_np.uint8)
        _ = app.get(img)
        result["ok"] = True
        result["kind"] = "ok"
        result["message"] = "Модель реально выполнилась на CUDA."
        return result
    except Exception as exc:
        model = result["model"]
        if looks_like_missing_detection_assertion(exc):
            repaired = repair_nested_model_pack(model, verbose=False)
            if repaired:
                try:
                    import numpy as _np
                    from insightface.app import FaceAnalysis
                    size = int(det_size or 640)
                    size = max(128, min(1280, size))
                    app = FaceAnalysis(name=model, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
                    app.prepare(ctx_id=0, det_size=(size, size))
                    used = insightface_session_providers(app)
                    result["providers"] = used
                    img = _np.full((size, size, 3), 127, dtype=_np.uint8)
                    _ = app.get(img)
                    result["ok"] = True
                    result["kind"] = "ok-after-repair"
                    result["message"] = "Model-pack был исправлен, после этого модель выполнилась на CUDA."
                    return result
                except Exception as exc2:
                    exc = exc2

        result["ok"] = False
        if looks_like_missing_detection_assertion(exc):
            result["kind"] = "model-pack"
            result["message"] = "InsightFace не нашёл detection-модель в model-pack. Возможно, пакет повреждён или распакован не в ту структуру."
        elif looks_like_cuda_runtime_error(exc):
            result["kind"] = "cuda-runtime"
            result["message"] = "CUDAExecutionProvider виден, но реальный запуск модели падает на CUDA/cuDNN."
        else:
            result["kind"] = "other"
            result["message"] = "Неизвестная ошибка при реальном запуске модели на GPU."
        result["error"] = (repr(exc) + " " + str(exc))[:2500]
        return result


def gpu_all_models_smoke_test(det_size: int = 640, models: Optional[Sequence[str]] = None, verbose: bool = True) -> Dict[str, Dict[str, Any]]:
    """Run real CUDA smoke-test for every requested InsightFace model pack."""
    models = list(models or KNOWN_MODELS)
    results: Dict[str, Dict[str, Any]] = {}
    if verbose:
        print("\n" + lang_text("=== Smoke-test всех моделей InsightFace на GPU ===", "=== GPU smoke-test for all InsightFace models ==="))
        print_wrapped("Проверка прогоняет каждую model-pack на синтетическом изображении через CUDAExecutionProvider. Фото пользователя не используются. Если модели нет в кэше, InsightFace может скачать её автоматически.")
        print_wrapped("После этой проверки GPU-варианты в ручном меню можно ограничить только моделями со статусом OK.")
    for idx, model in enumerate(models, start=1):
        print(f"\n[{idx}/{len(models)}] " + lang_text("Проверяю", "Testing") + f" {model} " + lang_text("на GPU...", "on GPU..."))
        result = gpu_model_smoke_test_details(model, det_size=det_size)
        results[model] = result
        if result.get("ok"):
            print(f"  OK: {result.get('message')}")
            if result.get("providers"):
                print(f"  Providers: {result.get('providers')}")
        else:
            print(lang_text("  ОШИБКА", "  ERROR") + f" [{result.get('kind')}]: {result.get('message')}")
            err = str(result.get("error", "")).strip()
            if err:
                print_wrapped("  Подробность: " + err[:800], indent="  ")
            if result.get("kind") == "model-pack":
                print_model_pack_hint(model)
    ok_models = [m for m, r in results.items() if r.get("ok")]
    bad_models = [m for m, r in results.items() if not r.get("ok")]
    print("\n" + lang_text("=== Итог smoke-test моделей ===", "=== Model smoke-test summary ==="))
    print("GPU OK:", ", ".join(ok_models) if ok_models else lang_text("нет", "none"))
    print("GPU problem:", ", ".join(bad_models) if bad_models else lang_text("нет", "none"))
    if ok_models:
        print_wrapped("Рекомендация: в ручном выборе показывать GPU-варианты только для этих моделей: " + ", ".join(ok_models))
    else:
        print_wrapped("Рекомендация: использовать CPU, пока GPU-запуск моделей не заработает стабильно.")
    return results


def allowed_gpu_models_from_smoke_results(results: Optional[Dict[str, Dict[str, Any]]]) -> Optional[List[str]]:
    """Extract model names that passed GPU smoke tests."""
    if not results:
        return None
    return [m for m, r in results.items() if r.get("ok")]

def check_gpu_runtime(args: argparse.Namespace) -> None:
    """Check whether CUDAExecutionProvider is available for model selection."""
    providers = available_onnx_providers()
    if "CUDAExecutionProvider" in providers:
        print("\n" + lang_text("GPU-режим: CUDAExecutionProvider найден. Доступные providers:", "GPU mode: CUDAExecutionProvider found. Available providers:"), providers)
        if not getattr(args, "skip_gpu_smoke_test", False):
            ok = gpu_real_inference_smoke_test(args.model, args.det_size, verbose=True)
            if ok:
                return
            print("\n" + lang_text("CUDAExecutionProvider виден, но реальная GPU-проверка выбранной модели не прошла.", "CUDAExecutionProvider is visible, but the selected model failed the real GPU check."))
            # If an experimental/non-default model pack is broken, keep GPU and fall back to buffalo_l.
            if normalize_model_name(getattr(args, "model", DEFAULT_MODEL)) != DEFAULT_MODEL:
                print(lang_text("Пробую контрольную GPU-проверку с", "Trying a control GPU check with"), DEFAULT_MODEL + ".")
                if gpu_real_inference_smoke_test(DEFAULT_MODEL, args.det_size, verbose=True):
                    print(lang_text("Модель", "Model"), args.model, lang_text("недоступна/повреждена для FaceAnalysis. Продолжаю на", "is unavailable/corrupt for FaceAnalysis. Continuing with"), DEFAULT_MODEL, "+ GPU.")
                    args.model = DEFAULT_MODEL
                    args.gpu = True
                    return
            if getattr(args, "auto_cpu_fallback", True):
                args.gpu = False
                print(lang_text("Продолжаю на CPU, чтобы сортировка не зависла и не ушла в скрытый fallback.", "Continuing on CPU so sorting does not hang or silently fall back."))
                print(lang_text("Для пропуска этой проверки используйте --skip-gpu-smoke-test, но это может снова дать ошибки cuDNN во время сканирования.", "Use --skip-gpu-smoke-test to skip this check, but cuDNN errors may appear again during scanning."))
                return
            raise SystemExit("GPU smoke-test не прошёл. Уберите --no-auto-cpu-fallback или настройте CUDA/cuDNN.")
        print(lang_text("GPU smoke-test пропущен по параметру --skip-gpu-smoke-test.", "GPU smoke-test skipped by --skip-gpu-smoke-test."))
        return

    print("\n" + lang_text("GPU-режим выбран, но ONNX Runtime не видит CUDAExecutionProvider.", "GPU mode was selected, but ONNX Runtime does not see CUDAExecutionProvider."))
    print(lang_text("Доступные providers:", "Available providers:"), providers or lang_text("не удалось определить", "could not determine"))
    print(lang_text("Обычно это значит одно из трёх:", "This usually means one of three things:"))
    print(lang_text("  1) установлен CPU-only пакет onnxruntime;", "  1) the CPU-only onnxruntime package is installed;"))
    print(lang_text("  2) установлен onnxruntime-gpu, но не хватает CUDA/cuDNN/MSVC DLL;", "  2) onnxruntime-gpu is installed, but CUDA/cuDNN/MSVC DLLs are missing;"))
    print(lang_text("  3) нет совместимой NVIDIA-видеокарты или драйвера.", "  3) there is no compatible NVIDIA GPU or driver."))
    diagnose_gpu_environment(verbose=False)
    if getattr(args, "auto_cpu_fallback", True):
        args.gpu = False
        print(lang_text("Продолжаю на CPU. Когда CUDAExecutionProvider появится, GPU-варианты снова станут доступны.", "Continuing on CPU. GPU options will be available again once CUDAExecutionProvider appears."))
        return
    raise SystemExit("CUDAExecutionProvider недоступен.")


# -----------------------------------------------------------------------------
# Small utility helpers
# -----------------------------------------------------------------------------

def now_iso() -> str:
    """Return current local timestamp as an ISO-like string without timezone conversion."""
    return dt.datetime.now().replace(microsecond=0).isoformat()


class NullTextStream:
    """Small text stream used when Windows windowed/frozen apps expose no console.

    PyInstaller ``console=False`` processes can have ``sys.stdout`` and
    ``sys.stderr`` set to ``None``.  CPU portable GUI scanning runs inline and
    some progress helpers, especially tqdm, expect a stream-like object with a
    ``write()`` method.  This sink keeps those helpers safe without reopening a
    black console window or changing pipeline behavior.
    """

    encoding = "utf-8"
    errors = "replace"

    def write(self, data: str) -> int:
        return len(data or "")

    def flush(self) -> None:
        return None

    def isatty(self) -> bool:
        return False


class TeeStream:
    """Write console output both to the terminal and to face_sorter_mvp.log."""

    def __init__(self, primary: Any, secondary: Any):
        self.primary = primary if primary is not None else NullTextStream()
        self.secondary = secondary if secondary is not None else NullTextStream()

    def write(self, data: str) -> int:
        try:
            self.primary.write(data)
        except Exception:
            pass
        try:
            self.secondary.write(data)
        except Exception:
            pass
        return len(data or "")

    def flush(self) -> None:
        try:
            self.primary.flush()
        except Exception:
            pass
        try:
            self.secondary.flush()
        except Exception:
            pass

    def isatty(self) -> bool:
        try:
            return bool(self.primary.isatty())
        except Exception:
            return False

    def __getattr__(self, name: str) -> Any:
        return getattr(self.primary, name)


def ensure_non_null_stdio() -> None:
    """Install harmless text sinks when stdout/stderr are missing.

    This is a v69.6 CPU GUI no-console safeguard.  It is intentionally tiny:
    it does not change logging, diagnostics, pipeline stages, reports, or the
    CPU/GPU provider selection.  It only prevents libraries that write progress
    output from crashing a windowed PyInstaller GUI process where stdio is None.
    """
    if getattr(sys, "stdout", None) is None:
        sys.stdout = NullTextStream()
    if getattr(sys, "stderr", None) is None:
        sys.stderr = NullTextStream()


# ---------------------------------------------------------------------------
# Logging, environment cache and bug report helpers
# ---------------------------------------------------------------------------
def setup_app_logging() -> None:
    """Append a unified console log next to the script.

    This is intentionally dependency-free and captures normal print(), tqdm stderr,
    Python tracebacks and low-level library messages that go through stdout/stderr.
    """
    global _LOGGING_SETUP, _LOG_FILE_HANDLE
    if _LOGGING_SETUP:
        return
    try:
        _LOG_FILE_HANDLE = APP_LOG_FILE.open("a", encoding="utf-8", buffering=1)
        sys.stdout = TeeStream(getattr(sys, "__stdout__", None) or getattr(sys, "stdout", None), _LOG_FILE_HANDLE)
        sys.stderr = TeeStream(getattr(sys, "__stderr__", None) or getattr(sys, "stderr", None), _LOG_FILE_HANDLE)
        _LOGGING_SETUP = True
        print("\n" + "=" * 88)
        print(f"Tuned Image Sorter {SCRIPT_VERSION} log started: {now_iso()}")
        print(f"Script: {Path(__file__).resolve()}")
        print(f"Python: {sys.version.replace(chr(10), ' ')}")
        print("=" * 88)
    except Exception:
        # Logging must never prevent the sorter from running.
        _LOGGING_SETUP = False


def read_json_file(path: Path) -> Dict[str, Any]:
    """Read a JSON file and return an empty dict on parse/read failure."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def write_json_file(path: Path, data: Dict[str, Any]) -> None:
    """Write JSON atomically enough for small project/env state files."""
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def diagnostics_dir_for_output(output_dir: Path) -> Path:
    """Return the diagnostics folder included in bug reports."""
    return output_dir.resolve() / "reports" / DIAGNOSTICS_DIR_NAME


def diagnostics_dir_from_args(args: Any) -> Optional[Path]:
    """Best-effort diagnostics folder resolver for CLI/pipeline args."""
    try:
        out = getattr(args, "output", None)
        if not out:
            return None
        return diagnostics_dir_for_output(Path(out))
    except Exception:
        return None


def _safe_json_value(value: Any, max_text: int = 4000) -> Any:
    """Make diagnostic values JSON-safe and bounded."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _safe_json_value(v, max_text=max_text) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe_json_value(v, max_text=max_text) for v in list(value)[:200]]
    text = str(value)
    return text if len(text) <= max_text else text[:max_text] + "...[truncated]"


def append_jsonl_event(path: Path, event: Dict[str, Any]) -> None:
    """Append one JSONL diagnostic event with immediate flush.

    This is intentionally defensive: diagnostics must never break the sorter.
    Flushing each event is useful when a native CUDA/ONNX/OpenCV crash kills a
    worker before Python can raise a normal exception.
    """
    try:
        ensure_dir(path.parent)
        payload = {
            "time": now_iso(),
            "pid": os.getpid(),
            "ppid": os.getppid() if hasattr(os, "getppid") else None,
            "process_name": multiprocessing.current_process().name,
        }
        payload.update({str(k): _safe_json_value(v) for k, v in event.items()})
        with path.open("a", encoding="utf-8", buffering=1) as f:
            f.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
            f.flush()
    except Exception:
        pass


def record_module_event(args: Any, event: str, module: str = "pipeline", **fields: Any) -> None:
    """Record main-process lifecycle events for bug-report diagnostics."""
    diag_dir = diagnostics_dir_from_args(args)
    if diag_dir is None:
        return
    append_jsonl_event(diag_dir / "module_events.jsonl", {"event": event, "module": module, **fields})


def record_worker_pool_event(args: Any, event: str, **fields: Any) -> None:
    """Record scan ProcessPool lifecycle/fallback events from the main process."""
    diag_dir = diagnostics_dir_from_args(args)
    if diag_dir is None:
        return
    append_jsonl_event(diag_dir / "worker_pool_events.jsonl", {"event": event, "module": "scan_worker_pool", **fields})


def _worker_event(event: str, **fields: Any) -> None:
    """Record a diagnostic event from inside a scan worker process."""
    if _WORKER_DIAGNOSTICS_DIR is None:
        return
    append_jsonl_event(_WORKER_DIAGNOSTICS_DIR / "worker_events.jsonl", {
        "event": event,
        "module": "scan_worker",
        "worker_run_id": _WORKER_RUN_ID,
        **fields,
    })


def _worker_shutdown_event() -> None:
    """Best-effort worker shutdown breadcrumb."""
    try:
        uptime = round(time.time() - float(_WORKER_START_TIME or time.time()), 3)
        _worker_event("worker_shutdown", uptime_seconds=uptime)
    except Exception:
        pass
    try:
        global _WORKER_FAULT_LOG_HANDLE
        if _WORKER_FAULT_LOG_HANDLE is not None:
            try:
                faulthandler.disable()
            except Exception:
                pass
            _WORKER_FAULT_LOG_HANDLE.flush()
            _WORKER_FAULT_LOG_HANDLE.close()
            _WORKER_FAULT_LOG_HANDLE = None
    except Exception:
        pass


def enable_worker_fault_handler() -> None:
    """Enable faulthandler in a worker so native crashes may leave a trace."""
    global _WORKER_FAULT_LOG_HANDLE
    if _WORKER_DIAGNOSTICS_DIR is None:
        return
    try:
        ensure_dir(_WORKER_DIAGNOSTICS_DIR)
        fault_path = _WORKER_DIAGNOSTICS_DIR / f"worker_faults_pid{os.getpid()}.log"
        _WORKER_FAULT_LOG_HANDLE = fault_path.open("a", encoding="utf-8", buffering=1)
        faulthandler.enable(file=_WORKER_FAULT_LOG_HANDLE, all_threads=True)
        _worker_event("faulthandler_enabled", fault_log=str(fault_path))
    except Exception as exc:
        _worker_event("faulthandler_enable_failed", error=repr(exc))


def collect_runtime_diagnostics(args: Optional[Any] = None) -> Dict[str, Any]:
    """Collect startup/runtime facts that help diagnose module bootstrap issues."""
    env_keys = [
        "PATH", "PYTHONPATH", "CUDA_PATH", "CUDA_HOME", "CUDNN_PATH",
        "ORT_LOGGING_LEVEL", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
        "TEMP", "TMP", "USERNAME", "USERPROFILE",
    ]
    env_summary = {}
    for key in env_keys:
        val = os.environ.get(key)
        if val is None:
            env_summary[key] = None
        elif key == "PATH":
            parts = val.split(os.pathsep)
            env_summary[key] = {"length": len(val), "entries_count": len(parts), "first_entries": parts[:20]}
        else:
            env_summary[key] = val[:1000]
    return {
        "created_at": now_iso(),
        "script_version": SCRIPT_VERSION,
        "pid": os.getpid(),
        "python_exe": sys.executable,
        "python_version": sys.version.replace("\n", " "),
        "platform": platform.platform(),
        "cwd": os.getcwd(),
        "script_path": str(Path(__file__).resolve()),
        "module_name": __name__,
        "package_name": __package__,
        "argv": sys.argv[:],
        "args": vars(args) if args is not None else {},
        "sys_path_first_entries": sys.path[:20],
        "environment_variables": env_summary,
        "packages": collect_package_versions(),
        "onnx_providers": available_onnx_providers(),
    }


def write_runtime_diagnostics(args: Any) -> None:
    """Write a snapshot used by bug reports before heavy modules start."""
    diag_dir = diagnostics_dir_from_args(args)
    if diag_dir is None:
        return
    try:
        ensure_dir(diag_dir)
        (diag_dir / "runtime_diagnostics.json").write_text(
            json.dumps(collect_runtime_diagnostics(args), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def tail_text_file(path: Path, lines: int = 40, max_chars: int = 12000) -> List[str]:
    """Return a bounded tail of a text file for summaries."""
    try:
        if not path.exists() or not path.is_file():
            return []
        data = path.read_text(encoding="utf-8", errors="replace")[-max_chars:]
        return data.splitlines()[-lines:]
    except Exception:
        return []


def summarize_diagnostics(output_dir: Optional[Path]) -> Dict[str, Any]:
    """Summarize diagnostics files and last events for system_info.json."""
    if output_dir is None:
        return {}
    diag_dir = diagnostics_dir_for_output(output_dir)
    if not diag_dir.exists():
        return {"diagnostics_dir": str(diag_dir), "exists": False}
    files = []
    try:
        for fp in sorted(diag_dir.rglob("*")):
            if fp.is_file():
                try:
                    files.append({"path": str(fp.relative_to(diag_dir)), "size_bytes": fp.stat().st_size})
                except Exception:
                    files.append({"path": str(fp), "size_bytes": None})
    except Exception:
        pass
    return {
        "diagnostics_dir": str(diag_dir),
        "exists": True,
        "files": files[:200],
        "last_module_events": tail_text_file(diag_dir / "module_events.jsonl", lines=20),
        "last_worker_pool_events": tail_text_file(diag_dir / "worker_pool_events.jsonl", lines=20),
        "last_worker_events": tail_text_file(diag_dir / "worker_events.jsonl", lines=30),
    }


def collect_package_versions() -> Dict[str, str]:
    """Collect package versions relevant to debugging user environments."""
    packages = [
        "insightface", "onnxruntime", "onnxruntime-gpu", "numpy", "Pillow",
        "opencv-python", "scikit-learn", "hdbscan", "pillow-heif", "psutil",
        "nvidia-cuda-runtime-cu12", "nvidia-cudnn-cu12", "nvidia-cublas-cu12",
        "nvidia-cufft-cu12", "nvidia-curand-cu12", "nvidia-cuda-nvrtc-cu12",
        "nvidia-nvjitlink-cu12",
    ]
    return {name: installed_distribution_version(name) for name in packages}


def environment_snapshot(include_providers: bool = True) -> Dict[str, Any]:
    """Build a small diagnostic snapshot of OS, Python and important packages."""
    code, nvidia = run_capture(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"], timeout=15)
    snapshot: Dict[str, Any] = {
        "script_version": SCRIPT_VERSION,
        "created_at": now_iso(),
        "python_exe": sys.executable,
        "python_version": sys.version.replace("\n", " "),
        "platform": platform.platform(),
        "packages": collect_package_versions(),
        "nvidia_smi_ok": code == 0,
        "nvidia_smi": nvidia if code == 0 else None,
    }
    if include_providers:
        snapshot["onnx_providers"] = available_onnx_providers()
    return snapshot


def environment_fingerprint(snapshot: Optional[Dict[str, Any]] = None) -> str:
    """Hash stable environment facts to detect when cached smoke tests are stale."""
    snap = snapshot or environment_snapshot(include_providers=False)
    relevant = {
        "python_exe": snap.get("python_exe"),
        "python_version": snap.get("python_version"),
        "platform": snap.get("platform"),
        "packages": snap.get("packages"),
        "nvidia_smi": snap.get("nvidia_smi"),
    }
    raw = json.dumps(relevant, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


def read_env_state() -> Dict[str, Any]:
    """Read cached environment/smoke-test state stored next to the script."""
    return read_json_file(ENV_STATE_FILE)


def write_env_state(extra: Dict[str, Any]) -> Dict[str, Any]:
    """Persist cached environment/smoke-test state next to the script."""
    snapshot = environment_snapshot(include_providers=True)
    state = {
        "app": "face_sorter_mvp",
        "script_version": SCRIPT_VERSION,
        "updated_at": now_iso(),
        "environment_fingerprint": environment_fingerprint(snapshot),
        "environment": snapshot,
    }
    state.update(extra or {})
    write_json_file(ENV_STATE_FILE, state)
    return state


def cached_env_state_valid(max_age_days: int = 14) -> Optional[Dict[str, Any]]:
    """Return True when cached environment data matches the current fingerprint."""
    state = read_env_state()
    if not state:
        return None
    try:
        current = environment_fingerprint(environment_snapshot(include_providers=False))
        if state.get("environment_fingerprint") != current:
            return None
        updated = dt.datetime.fromisoformat(str(state.get("updated_at")))
        if (dt.datetime.now() - updated).days > max_age_days:
            return None
        return state
    except Exception:
        return None


def save_gpu_cache(has_nvidia: bool, providers: Optional[List[str]] = None, smoke_results: Optional[Dict[str, Dict[str, Any]]] = None, det_size: Optional[int] = None) -> None:
    """Store GPU smoke-test results for reuse on later runs."""
    extra: Dict[str, Any] = {
        "has_nvidia_answer": bool(has_nvidia),
        "providers": providers if providers is not None else available_onnx_providers(),
        "smoke_test_det_size": det_size,
        "gpu_model_smoke_results": smoke_results,
        "gpu_allowed_models": allowed_gpu_models_from_smoke_results(smoke_results) if smoke_results else None,
    }
    write_env_state(extra)


def record_problem_file(args: Any, path: Path, stage: str, error: str, extra: Optional[Dict[str, Any]] = None) -> None:
    """Append a privacy-conscious CSV row for files that need attention.

    The CSV contains paths and metadata, but never copies image bytes. It is intended
    for bug reports: broken images, unsupported formats, copy errors, too-long paths,
    odd Unicode names, etc.
    """
    try:
        output = Path(getattr(args, "output", "") or ".").resolve()
        report_dir = output / "reports"
        ensure_dir(report_dir)
        csv_path = report_dir / PROBLEM_FILES_NAME
        exists = csv_path.exists()
        stat = None
        try:
            stat = path.stat()
        except Exception:
            stat = None
        name = path.name
        try:
            diag = file_path_diagnostics(path)
        except Exception:
            diag = {}
        row = {
            "time": now_iso(),
            "stage": stage,
            "path": str(path),
            "name": name,
            "suffix": path.suffix.lower(),
            "path_length": len(str(path)),
            "name_length": len(name),
            "size_bytes": "" if stat is None else int(stat.st_size),
            "mtime": "" if stat is None else dt.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            "has_non_ascii": any(ord(ch) > 127 for ch in str(path)),
            "windows_forbidden_chars_in_name": any(ch in name for ch in WINDOWS_FORBIDDEN_CHARS),
            "source_path_too_long": diag.get("source_path_too_long", ""),
            "is_network_path": diag.get("is_network_path", ""),
            "is_cloud_placeholder": diag.get("is_cloud_placeholder", ""),
            "has_control_chars": diag.get("has_control_chars", ""),
            "error": str(error)[-2000:],
        }
        for k, v in (extra or {}).items():
            row[str(k)] = v
        fields = list(row.keys())
        if exists:
            try:
                with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
                    header = next(csv.reader(f), [])
                fields = header or fields
                for k in row.keys():
                    if k not in fields:
                        fields.append(k)
            except Exception:
                pass
        with csv_path.open("a", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            if not exists:
                writer.writeheader()
            writer.writerow({k: row.get(k, "") for k in fields})
    except Exception:
        pass


def summarize_input_files(input_dir: Optional[Path], limit: int = 200) -> Dict[str, Any]:
    """Summarize input tree extensions and path edge cases for bug reports."""
    if not input_dir or not input_dir.exists():
        return {}
    ext_counts: Dict[str, int] = defaultdict(int)
    unsupported_samples: List[str] = []
    long_path_samples: List[str] = []
    non_ascii_samples: List[str] = []
    network_path_samples: List[str] = []
    cloud_placeholder_samples: List[str] = []
    forbidden_name_samples: List[str] = []
    total_files = 0
    try:
        for p in input_dir.rglob("*"):
            if not p.is_file():
                continue
            total_files += 1
            suffix = p.suffix.lower() or "<no extension>"
            ext_counts[suffix] += 1
            sp = str(p)
            if suffix not in IMAGE_EXTENSIONS and len(unsupported_samples) < limit:
                unsupported_samples.append(sp)
            if len(sp) >= 240 and len(long_path_samples) < limit:
                long_path_samples.append(sp)
            if any(ord(ch) > 127 for ch in sp) and len(non_ascii_samples) < limit:
                non_ascii_samples.append(sp)
            try:
                diag = file_path_diagnostics(p)
                if diag.get("is_network_path") and len(network_path_samples) < limit:
                    network_path_samples.append(sp)
                if diag.get("is_cloud_placeholder") and len(cloud_placeholder_samples) < limit:
                    cloud_placeholder_samples.append(sp)
                if diag.get("has_forbidden_chars_in_name") and len(forbidden_name_samples) < limit:
                    forbidden_name_samples.append(sp)
            except Exception:
                pass
    except Exception as exc:
        return {"error": str(exc)}
    return {
        "total_files": total_files,
        "extension_counts": dict(sorted(ext_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "supported_image_extensions": sorted(IMAGE_EXTENSIONS),
        "unsupported_samples": unsupported_samples,
        "long_path_samples": long_path_samples,
        "non_ascii_samples": non_ascii_samples,
        "network_path_samples": network_path_samples,
        "cloud_placeholder_samples": cloud_placeholder_samples,
        "forbidden_name_samples": forbidden_name_samples,
    }


def create_bug_report(*args: Any, **kwargs: Any) -> Any:
    """Compatibility wrapper moved to reports/bug_report.py in v44 / Этап 003."""
    try:
        from .reports.bug_report import create_bug_report as _impl
    except ImportError:
        from reports.bug_report import create_bug_report as _impl  # type: ignore
    return _impl(*args, **kwargs)

# ---------------------------------------------------------------------------
# Compatibility wrappers around file_ops.py
# ---------------------------------------------------------------------------
def short_hash(text: str, n: int = 10) -> str:
    """Return a short deterministic hash for file names, paths and IDs."""
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:n]


def sanitize_folder_name(name: str, fallback: str = "unnamed") -> str:
    """Compatibility wrapper around file_ops.safe_folder_name()."""
    return file_safe_folder_name(name, fallback=fallback)


def sanitize_file_stem(name: str, fallback: str = "photo") -> Tuple[str, List[str]]:
    """Compatibility wrapper around file_ops.safe_file_stem()."""
    return file_safe_file_stem(name, fallback=fallback)


def next_safe_copy_counter() -> int:
    """Return a process-local counter used in fallback safe-copy file names."""
    global _SAFE_COPY_COUNTER
    _SAFE_COPY_COUNTER += 1
    return _SAFE_COPY_COUNTER


def safe_timestamp_for_filename() -> str:
    """Return a Windows-safe timestamp for generated file names."""
    return dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def write_filename_map(args: Any, original_path: Path, target_path: Path, reason: str, original_name: str, safe_name: str, path_hash: str, extra: Optional[Dict[str, Any]] = None) -> None:
    """Append file-name mapping rows that make safe renames reversible."""
    try:
        output = Path(getattr(args, "output", "") or ".").resolve()
        report_dir = output / "reports"
        ensure_dir(report_dir)
        csv_path = report_dir / "filename_map.csv"
        fields = [
            "time", "original_path", "target_path", "stage", "reason",
            "original_name", "safe_name", "hash", "path_len", "is_network_path",
            "is_cloud_placeholder", "has_unicode", "has_forbidden_chars_in_name",
        ]
        extra = extra or {}
        with _FILENAME_MAP_LOCK:
            exists = csv_path.exists()
            with csv_path.open("a", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                if not exists:
                    writer.writeheader()
                writer.writerow({
                    "time": now_iso(),
                    "original_path": str(original_path),
                    "target_path": str(target_path),
                    "stage": "copy",
                    "reason": reason,
                    "original_name": original_name,
                    "safe_name": safe_name,
                    "hash": path_hash,
                    "path_len": extra.get("path_len", ""),
                    "is_network_path": extra.get("is_network_path", ""),
                    "is_cloud_placeholder": extra.get("is_cloud_placeholder", ""),
                    "has_unicode": extra.get("has_unicode", ""),
                    "has_forbidden_chars_in_name": extra.get("has_forbidden_chars_in_name", ""),
                })
    except Exception:
        pass


def unique_destination(src: Path, dst_dir: Path, args: Any = None, max_path_len: int = 240) -> Path:
    """Compatibility wrapper: ask file_ops.py for a safe destination path."""
    plan = file_plan_safe_destination(src, dst_dir, max_path_len=max_path_len)
    if args is not None and plan.reason != "unchanged":
        write_filename_map(
            args,
            plan.source_path,
            plan.target_path,
            plan.reason,
            plan.original_name,
            plan.safe_name,
            plan.path_hash,
            extra=plan.flags,
        )
    return plan.target_path


def iter_images(root: Path) -> Iterable[Path]:
    """Yield supported image files from an input tree using file_ops filtering."""
    return file_iter_supported_images(root, allow_header_only=False)


# -----------------------------------------------------------------------------
# Exact duplicate detection
# -----------------------------------------------------------------------------

PARTIAL_HASH_CHUNK_SIZE = 64 * 1024
FULL_HASH_CHUNK_SIZE = 1024 * 1024


def file_stat_signature(path: Path) -> Optional[Tuple[int, float]]:
    """Return file size and modification timestamp for cache invalidation."""
    try:
        st = path.stat()
        return int(st.st_size), float(st.st_mtime)
    except Exception:
        return None


def hash_bytes(data: bytes) -> str:
    """Return SHA-1 hash for bytes-like data."""
    return hashlib.sha256(data).hexdigest()


def compute_partial_hash(path: Path) -> str:
    """Hash start/middle/end chunks. Used only after same-size grouping."""
    size = path.stat().st_size
    h = hashlib.sha256()
    with path.open("rb") as f:
        if size <= PARTIAL_HASH_CHUNK_SIZE * 3:
            h.update(f.read())
        else:
            h.update(f.read(PARTIAL_HASH_CHUNK_SIZE))
            f.seek(max(0, size // 2 - PARTIAL_HASH_CHUNK_SIZE // 2))
            h.update(f.read(PARTIAL_HASH_CHUNK_SIZE))
            f.seek(max(0, size - PARTIAL_HASH_CHUNK_SIZE))
            h.update(f.read(PARTIAL_HASH_CHUNK_SIZE))
    return h.hexdigest()


def compute_full_hash(path: Path) -> str:
    """Compute a full content hash for exact duplicate detection."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(FULL_HASH_CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def cached_fingerprint(conn: sqlite3.Connection, path: Path, size: int, mtime: float) -> Tuple[Optional[str], Optional[str]]:
    """Read a cached file fingerprint when size/mtime still match."""
    row = conn.execute(
        "SELECT size, mtime, partial_hash, full_hash FROM file_fingerprints WHERE path=?",
        (str(path),),
    ).fetchone()
    if not row:
        return None, None
    old_size, old_mtime, partial_hash, full_hash = row
    if int(old_size) == int(size) and abs(float(old_mtime) - float(mtime)) < 0.01:
        return partial_hash, full_hash
    return None, None


def upsert_fingerprint(conn: sqlite3.Connection, path: Path, size: int, mtime: float,
                       partial_hash: Optional[str], full_hash: Optional[str]) -> None:
    """Insert or update cached file hash data for exact duplicate detection."""
    conn.execute(
        """
        INSERT INTO file_fingerprints(path, size, mtime, partial_hash, full_hash, hash_algo, checked_at)
        VALUES (?, ?, ?, ?, ?, 'sha256', ?)
        ON CONFLICT(path) DO UPDATE SET
            size=excluded.size,
            mtime=excluded.mtime,
            partial_hash=COALESCE(excluded.partial_hash, file_fingerprints.partial_hash),
            full_hash=COALESCE(excluded.full_hash, file_fingerprints.full_hash),
            hash_algo='sha256',
            checked_at=excluded.checked_at
        """,
        (str(path), int(size), float(mtime), partial_hash, full_hash, now_iso()),
    )


def duplicate_canonical_sort_key(path: Path) -> Tuple[int, int, float, str]:
    """Sort duplicates so the most natural original becomes canonical."""
    name = path.name.lower()
    duplicate_markers = ["copy", "копия", "duplicate", "дубликат", " (1)", "_1", "- copy"]
    marker_penalty = 1 if any(m in name for m in duplicate_markers) else 0
    try:
        mtime = float(path.stat().st_mtime)
    except Exception:
        mtime = 0.0
    return (marker_penalty, len(str(path)), mtime, str(path).lower())


def duplicate_group_id(index: int) -> str:
    """Build a stable group ID from a full file hash."""
    return f"dup_{index:06d}"


def clear_duplicate_links(conn: sqlite3.Connection) -> None:
    """Clear duplicate link rows before rebuilding duplicate relationships."""
    conn.execute("DELETE FROM duplicate_links")


def load_duplicate_links(conn: sqlite3.Connection) -> Dict[str, Dict[str, str]]:
    """Load duplicate-to-canonical mapping from SQLite."""
    rows = conn.execute(
        "SELECT path, canonical_path, duplicate_group_id, role, action FROM duplicate_links"
    ).fetchall()
    return {
        str(r[0]): {
            "canonical_path": str(r[1]),
            "duplicate_group_id": str(r[2]),
            "role": str(r[3]),
            "action": str(r[4]),
        }
        for r in rows
    }


def write_duplicates_csv(args: Any, rows: List[Dict[str, Any]]) -> Path:
    """Write exact duplicate groups for user review and bug reports."""
    report_dir = Path(getattr(args, "output", ".")).resolve() / "reports"
    ensure_dir(report_dir)
    path = report_dir / "duplicates.csv"
    fields = [
        "duplicate_group_id", "role", "original_path", "canonical_path", "size_bytes",
        "partial_hash", "full_hash", "action", "reason",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})
    return path


def detect_exact_duplicates(args: argparse.Namespace, conn: sqlite3.Connection, photos: List[Path]) -> Dict[str, Dict[str, str]]:
    """Detect exact byte-for-byte duplicates with minimal IO.

    Algorithm: size groups -> partial hash for same-size groups -> full hash only for
    same-size + same-partial groups. Returns a map path -> duplicate link metadata.
    """
    check = str(getattr(args, "duplicate_check", "exact") or "off")
    policy = str(getattr(args, "duplicate_policy", "scan-one-copy-all") or "scan-one-copy-all")
    clear_duplicate_links(conn)
    if check == "off" or not photos:
        path = write_duplicates_csv(args, [])
        print(lang_text("Проверка дублей отключена. Пустой отчёт дублей:", "Duplicate check disabled. Empty duplicates report:"), path)
        conn.commit()
        return {}

    print_stage(
        "Этап проверки точных дублей",
        "Скрипт ищет только побайтно одинаковые файлы. Для скорости сначала группирует по размеру, затем считает partial hash, и только для подозрительных групп — полный hash."
    )
    by_size: Dict[int, List[Path]] = defaultdict(list)
    stat_cache: Dict[str, Tuple[int, float]] = {}
    for p in photos:
        sig = file_stat_signature(p)
        if sig is None:
            record_problem_file(args, p, "duplicate_stat_error", "cannot stat file")
            continue
        size, mtime = sig
        stat_cache[str(p)] = (size, mtime)
        by_size[size].append(p)

    candidates = [group for group in by_size.values() if len(group) >= 2]
    if not candidates:
        path = write_duplicates_csv(args, [])
        print(lang_text("Точных дублей не найдено: все размеры файлов уникальны. Отчёт:", "No exact duplicates found: all file sizes are unique. Report:"), path)
        conn.commit()
        return {}

    by_partial: Dict[Tuple[int, str], List[Path]] = defaultdict(list)
    partial_count = 0
    for group in candidates:
        for p in group:
            try:
                size, mtime = stat_cache[str(p)]
                partial, full = cached_fingerprint(conn, p, size, mtime)
                if not partial:
                    partial = compute_partial_hash(p)
                    upsert_fingerprint(conn, p, size, mtime, partial, None)
                by_partial[(size, partial)].append(p)
                partial_count += 1
            except Exception as exc:
                record_problem_file(args, p, "duplicate_partial_hash_error", str(exc))

    by_full: Dict[Tuple[int, str], List[Path]] = defaultdict(list)
    full_count = 0
    for (size, partial), group in by_partial.items():
        if len(group) < 2:
            continue
        for p in group:
            try:
                size, mtime = stat_cache[str(p)]
                _partial, full = cached_fingerprint(conn, p, size, mtime)
                if not full:
                    full = compute_full_hash(p)
                    upsert_fingerprint(conn, p, size, mtime, partial, full)
                by_full[(size, full)].append(p)
                full_count += 1
            except Exception as exc:
                record_problem_file(args, p, "duplicate_full_hash_error", str(exc))

    rows: List[Dict[str, Any]] = []
    duplicate_map: Dict[str, Dict[str, str]] = {}
    group_idx = 0
    duplicate_files = 0
    canonical_files = 0
    for (size, full), group in sorted(by_full.items(), key=lambda kv: (-len(kv[1]), kv[0][0], kv[0][1])):
        if len(group) < 2:
            continue
        group_idx += 1
        gid = duplicate_group_id(group_idx)
        canonical = sorted(group, key=duplicate_canonical_sort_key)[0]
        canonical_files += 1
        try:
            partial, _full = cached_fingerprint(conn, canonical, int(size), float(canonical.stat().st_mtime))
        except Exception:
            partial = ""
        for p in sorted(group, key=lambda x: str(x).lower()):
            role = "canonical" if p == canonical else "duplicate"
            action = "scanned" if role == "canonical" else (
                "linked_to_canonical" if policy == "scan-one-copy-all" else
                "skip_copy_duplicate" if policy == "scan-one-copy-first" else
                "report_only"
            )
            if role == "duplicate":
                duplicate_files += 1
            row = {
                "duplicate_group_id": gid,
                "role": role,
                "original_path": str(p),
                "canonical_path": str(canonical),
                "size_bytes": int(size),
                "partial_hash": partial or "",
                "full_hash": full,
                "action": action,
                "reason": "exact_sha256_duplicate",
            }
            rows.append(row)
            duplicate_map[str(p)] = {
                "canonical_path": str(canonical),
                "duplicate_group_id": gid,
                "role": role,
                "action": action,
            }
            conn.execute(
                """
                INSERT INTO duplicate_links(path, canonical_path, duplicate_group_id, role, size, partial_hash, full_hash, action, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    canonical_path=excluded.canonical_path,
                    duplicate_group_id=excluded.duplicate_group_id,
                    role=excluded.role,
                    size=excluded.size,
                    partial_hash=excluded.partial_hash,
                    full_hash=excluded.full_hash,
                    action=excluded.action,
                    created_at=excluded.created_at
                """,
                (str(p), str(canonical), gid, role, int(size), partial or "", full, action, now_iso()),
            )

    conn.commit()
    report_path = write_duplicates_csv(args, rows)
    print(lang_text("Проверка точных дублей завершена.", "Exact duplicate check finished."))
    print(lang_text("Групп дублей:", "Duplicate groups:"), group_idx)
    print(lang_text("Файлов-дублей без canonical:", "Duplicate files excluding canonical:"), duplicate_files)
    print(lang_text("Partial hash рассчитан/получен для:", "Partial hash calculated/reused for:"), partial_count)
    print(lang_text("Full hash рассчитан/получен для:", "Full hash calculated/reused for:"), full_count)
    print(lang_text("Отчёт дублей:", "Duplicates report:"), report_path)
    if group_idx and policy == "scan-one-copy-all":
        print(lang_text("Политика дублей: распознаётся только canonical-файл, но при копировании будут сохранены все точные дубли.", "Duplicate policy: only the canonical file is scanned, but all exact duplicates will be copied."))
    elif group_idx and policy == "scan-one-copy-first":
        print(lang_text("Политика дублей: распознаётся и копируется только canonical-файл; остальные дубли только в duplicates.csv.", "Duplicate policy: only the canonical file is scanned and copied; other duplicates stay only in duplicates.csv."))
    elif group_idx and policy == "report-only":
        print(lang_text("Политика дублей: только отчёт, обработка файлов не меняется.", "Duplicate policy: report only, file processing is unchanged."))
    return duplicate_map


def ensure_dir(path: Path) -> None:
    """Create a directory and all missing parents."""
    path.mkdir(parents=True, exist_ok=True)


def reset_dir(path: Path) -> None:
    """Delete and recreate a directory when clean output was requested."""
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


YES_ANSWERS = {"y", "yes", "д", "да"}
NO_ANSWERS = {"n", "no", "н", "нет"}


def parse_bool_answer(value: str, default: Optional[bool] = None) -> Optional[bool]:
    """Strict parser for yes/no prompts.

    Important: keyboard-layout mistakes such as "lf" ("да" typed on an English
    layout) or "ytn" ("нет" typed on an English layout) are intentionally not
    accepted. The user is asked the same question again instead of silently choosing
    the wrong option.
    """
    text = str(value or "").strip().lower()
    if not text:
        return default
    if text in YES_ANSWERS:
        return True
    if text in NO_ANSWERS:
        return False
    return None


def normalize_bool_answer(value: str, default: bool = False) -> bool:
    """Normalize localized yes/no text to True/False or None."""
    # Backward-compatible helper for non-interactive/internal calls. Interactive
    # prompts must use ask_bool(), which repeats the question on invalid input.
    parsed = parse_bool_answer(value, default)
    return bool(default if parsed is None else parsed)


def ask_yes_no_strict(prompt: str, default: Optional[bool] = None) -> bool:
    """Ask a yes/no question until the user gives a recognizable answer."""
    if default is True:
        suffix = f" {tr('yes_no')} [{tr('yes')}]"
    elif default is False:
        suffix = f" {tr('yes_no')} [{tr('no')}]"
    else:
        suffix = f" {tr('yes_no')}"
    while True:
        raw = input(f"{prompt}{suffix}: ").strip()
        parsed = parse_bool_answer(raw, default)
        if parsed is not None:
            return parsed
        print(tr("invalid_yes_no"))


def safe_float(value: Any, default: float) -> float:
    """Convert a value to float, returning a default when conversion fails."""
    try:
        return float(value)
    except Exception:
        return default


def safe_int(value: Any, default: int) -> int:
    """Convert a value to int, returning a default when conversion fails."""
    try:
        return int(value)
    except Exception:
        return default


def normalize_model_name(raw: Any) -> str:
    """Convert menu shortcuts/aliases to a valid InsightFace model name."""
    text = str(raw or "").strip()
    if not text:
        return DEFAULT_MODEL
    # Fix the exact problem from v3: user/menu value "1" became model name "1".
    if text.isdigit():
        idx = int(text)
        if 1 <= idx <= len(KNOWN_MODELS):
            return KNOWN_MODELS[idx - 1]
        print(lang_text("Предупреждение: модель не существует. Использую", "Warning: model does not exist. Using"), DEFAULT_MODEL + ".")
        return DEFAULT_MODEL
    if text in KNOWN_MODELS:
        return text
    print(lang_text("Предупреждение: неизвестная модель. Использую", "Warning: unknown model. Using"), DEFAULT_MODEL + ".")
    print(lang_text("Доступные варианты:", "Available options:"), ", ".join(KNOWN_MODELS))
    return DEFAULT_MODEL


def insightface_model_dir(model_name: str) -> Path:
    """Return the local InsightFace model-pack directory for a given model."""
    return Path.home() / ".insightface" / "models" / normalize_model_name(model_name)


def list_model_pack_onnx_files(model_name: str, recursive: bool = False) -> List[Path]:
    """List ONNX files in a downloaded InsightFace model pack."""
    root = insightface_model_dir(model_name)
    if not root.exists():
        return []
    pattern = "**/*.onnx" if recursive else "*.onnx"
    try:
        return sorted(root.glob(pattern))
    except Exception:
        return []


def has_top_level_onnx_files(model_name: str) -> bool:
    """Return True when a model pack has ONNX files at the expected level."""
    return bool(list_model_pack_onnx_files(model_name, recursive=False))


def looks_like_detection_model_path(path: Path) -> bool:
    """Heuristically identify detection ONNX files inside model packs."""
    name = path.name.lower()
    return any(token in name for token in ("det", "scrfd", "retinaface"))


def model_pack_has_detection_file(model_name: str, recursive: bool = False) -> bool:
    """Return True when a model pack appears to include face detection."""
    return any(looks_like_detection_model_path(p) for p in list_model_pack_onnx_files(model_name, recursive=recursive))


def looks_like_missing_detection_assertion(exc: BaseException) -> bool:
    """Detect InsightFace errors caused by model packs without detection models."""
    text = (repr(exc) + " " + str(exc)).lower()
    return "assertionerror" in text or ("detection" in text and "self.models" in text)


def repair_nested_model_pack(model_name: str, verbose: bool = True) -> bool:
    """Fix common InsightFace unpacking problem: ~/.insightface/models/<name>/<name>/*.onnx."""
    model_name = normalize_model_name(model_name)
    root = insightface_model_dir(model_name)
    nested = root / model_name
    if not nested.exists() or not nested.is_dir():
        return False
    if has_top_level_onnx_files(model_name):
        return False
    nested_files = sorted(nested.glob("*.onnx"))
    if not nested_files:
        return False
    if verbose:
        print("\n" + lang_text("Обнаружена вероятная проблема model-pack InsightFace:", "A probable InsightFace model-pack problem was detected:"))
        print(lang_text("  ONNX-файлы лежат во вложенной папке:", "  ONNX files are in a nested folder:"), nested)
        print(lang_text("  FaceAnalysis ожидает их напрямую в:", "  FaceAnalysis expects them directly in:"), root)
        print(lang_text("Пробую автоматически перенести файлы на один уровень выше.", "Trying to move files one level higher automatically."))
    try:
        for item in list(nested.iterdir()):
            dst = root / item.name
            if dst.exists():
                continue
            shutil.move(str(item), str(dst))
        try:
            nested.rmdir()
        except Exception:
            pass
        if verbose:
            print(lang_text("Model-pack исправлен: вложенные файлы перенесены.", "Model-pack fixed: nested files were moved."))
        return True
    except Exception as move_exc:
        if verbose:
            print(lang_text("Не удалось автоматически исправить model-pack:", "Could not automatically fix model-pack:"), move_exc)
        return False


def print_model_pack_hint(model_name: str) -> None:
    """Print troubleshooting guidance for broken or nested InsightFace model packs."""
    root = insightface_model_dir(model_name)
    print("\n" + lang_text("Проблема с model-pack", "Problem with model-pack"), model_name)
    print(lang_text("Папка модели:", "Model folder:"), root)
    top = list_model_pack_onnx_files(model_name, recursive=False)
    rec = list_model_pack_onnx_files(model_name, recursive=True)
    print(lang_text("ONNX-файлов на верхнем уровне:", "ONNX files at top level:"), len(top))
    print(lang_text("ONNX-файлов рекурсивно:", "ONNX files recursively:"), len(rec))
    if rec and not top:
        print(lang_text("Похоже, файлы лежат слишком глубоко. Их нужно переместить в папку модели на один уровень выше.", "It looks like files are nested too deeply. Move them one level higher into the model folder."))
    if rec and not model_pack_has_detection_file(model_name, recursive=True):
        print(lang_text("Не вижу detection-модели вроде det_10g.onnx/scrfd/retinaface. FaceAnalysis без неё не запустится.", "No detection model like det_10g.onnx/scrfd/retinaface was found. FaceAnalysis cannot start without it."))
    print(lang_text("Для сортировки архива лучше выбрать buffalo_l или buffalo_m: они стабильнее в этом MVP.", "For archive sorting, buffalo_l or buffalo_m are safer choices in this MVP."))


def levenshtein_distance(a: str, b: str, max_distance: Optional[int] = None) -> int:
    """Compute edit distance for filename fallback matching."""
    a = a.lower()
    b = b.lower()
    if a == b:
        return 0
    if max_distance is not None and abs(len(a) - len(b)) > max_distance:
        return max_distance + 1
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        row_min = current[0]
        for j, cb in enumerate(b, start=1):
            insert = current[j - 1] + 1
            delete = previous[j] + 1
            replace = previous[j - 1] + (ca != cb)
            val = min(insert, delete, replace)
            current.append(val)
            row_min = min(row_min, val)
        if max_distance is not None and row_min > max_distance:
            return max_distance + 1
        previous = current
    return previous[-1]


# -----------------------------------------------------------------------------
# SQLite
# -----------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# SQLite storage layer
# ---------------------------------------------------------------------------
def init_db(db_path: Path) -> sqlite3.Connection:
    """Open SQLite, enable performance pragmas and create/update schema tables."""
    ensure_dir(db_path.parent)
    conn = sqlite3.connect(str(db_path), timeout=60)
    # v32: SQLite tuning for large console runs. Writes still happen in the main process.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA busy_timeout=60000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL UNIQUE,
            size INTEGER NOT NULL,
            mtime REAL NOT NULL,
            width INTEGER,
            height INTEGER,
            status TEXT NOT NULL,
            error TEXT,
            scanned_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS faces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_id INTEGER NOT NULL,
            face_index INTEGER NOT NULL,
            det_score REAL NOT NULL,
            bbox_x1 INTEGER NOT NULL,
            bbox_y1 INTEGER NOT NULL,
            bbox_x2 INTEGER NOT NULL,
            bbox_y2 INTEGER NOT NULL,
            embedding BLOB NOT NULL,
            crop_relpath TEXT,
            cluster_raw INTEGER,
            cluster_key TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(image_id) REFERENCES images(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_faces_image_id ON faces(image_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_faces_cluster_key ON faces(cluster_key)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS file_fingerprints (
            path TEXT PRIMARY KEY,
            size INTEGER NOT NULL,
            mtime REAL NOT NULL,
            partial_hash TEXT,
            full_hash TEXT,
            hash_algo TEXT NOT NULL DEFAULT 'sha256',
            checked_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS duplicate_links (
            path TEXT PRIMARY KEY,
            canonical_path TEXT NOT NULL,
            duplicate_group_id TEXT NOT NULL,
            role TEXT NOT NULL,
            size INTEGER NOT NULL,
            partial_hash TEXT,
            full_hash TEXT,
            action TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_duplicate_links_canonical ON duplicate_links(canonical_path)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_duplicate_links_group ON duplicate_links(duplicate_group_id)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS file_problem_cache (
            path TEXT PRIMARY KEY,
            size INTEGER NOT NULL,
            mtime REAL NOT NULL,
            stage TEXT NOT NULL,
            reason TEXT NOT NULL,
            error TEXT,
            cached_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def problem_cache_is_current(conn: sqlite3.Connection, path: Path, size: int, mtime: float) -> Optional[Dict[str, Any]]:
    """Return True when a cached problem still matches current file size/mtime."""
    try:
        row = conn.execute(
            "SELECT stage, reason, error FROM file_problem_cache WHERE path=? AND size=? AND mtime=?",
            (str(path), int(size), float(mtime)),
        ).fetchone()
        if not row:
            return None
        return {"stage": row[0], "reason": row[1], "error": row[2] or ""}
    except Exception:
        return None


def upsert_problem_cache(conn: sqlite3.Connection, path: Path, size: int, mtime: float, stage: str, reason: str, error: str = "") -> None:
    """Store a repeatable per-file problem so later scans can skip it safely."""
    try:
        conn.execute(
            """
            INSERT INTO file_problem_cache(path, size, mtime, stage, reason, error, cached_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                size=excluded.size,
                mtime=excluded.mtime,
                stage=excluded.stage,
                reason=excluded.reason,
                error=excluded.error,
                cached_at=excluded.cached_at
            """,
            (str(path), int(size), float(mtime), str(stage), str(reason), str(error)[-2000:], now_iso()),
        )
    except Exception:
        pass


def image_cache_is_current(conn: sqlite3.Connection, path: Path, size: int, mtime: float) -> bool:
    """Return True when cached image scan data matches current file size/mtime."""
    row = conn.execute("SELECT size, mtime FROM images WHERE path = ?", (str(path),)).fetchone()
    if row is None:
        return False
    old_size, old_mtime = row
    return int(old_size) == int(size) and abs(float(old_mtime) - float(mtime)) < 0.01


def upsert_image(conn: sqlite3.Connection, path: Path, size: int, mtime: float,
                 width: Optional[int], height: Optional[int], status: str,
                 error: Optional[str]) -> int:
    """Insert/update one image metadata row and return its database ID."""
    existing = conn.execute("SELECT id FROM images WHERE path = ?", (str(path),)).fetchone()
    if existing:
        image_id = int(existing[0])
        conn.execute("DELETE FROM faces WHERE image_id = ?", (image_id,))
        conn.execute(
            """
            UPDATE images
            SET size=?, mtime=?, width=?, height=?, status=?, error=?, scanned_at=?
            WHERE id=?
            """,
            (size, mtime, width, height, status, error, now_iso(), image_id),
        )
        return image_id
    cur = conn.execute(
        """
        INSERT INTO images(path, size, mtime, width, height, status, error, scanned_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (str(path), size, mtime, width, height, status, error, now_iso()),
    )
    return int(cur.lastrowid)


def insert_face(conn: sqlite3.Connection, image_id: int, face_index: int, det_score: float,
                bbox: Tuple[int, int, int, int], embedding: Any, crop_relpath: Optional[str]) -> None:
    """Insert one face detection, crop metadata and embedding into SQLite."""
    x1, y1, x2, y2 = bbox
    emb = np.asarray(embedding, dtype=np.float32)
    norm = float(np.linalg.norm(emb))
    if norm > 0:
        emb = emb / norm
    conn.execute(
        """
        INSERT INTO faces(image_id, face_index, det_score, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
                          embedding, crop_relpath, cluster_raw, cluster_key, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?)
        """,
        (image_id, face_index, det_score, x1, y1, x2, y2, emb.tobytes(), now_iso()),
    )
    if crop_relpath:
        face_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("UPDATE faces SET crop_relpath=? WHERE id=?", (crop_relpath, int(face_id)))


def decode_embedding(blob: bytes) -> Any:
    """Decode a SQLite embedding BLOB into a numpy vector."""
    arr = np.frombuffer(blob, dtype=np.float32).copy()
    norm = float(np.linalg.norm(arr))
    if norm > 0:
        arr = arr / norm
    return arr


def load_faces(conn: sqlite3.Connection, clustered_only: bool = False) -> List[FaceRecord]:
    """Load detected faces from SQLite for clustering/assignment."""
    where = "WHERE f.cluster_key IS NOT NULL" if clustered_only else ""
    rows = conn.execute(
        f"""
        SELECT f.id, f.image_id, i.path, f.face_index, f.det_score,
               f.bbox_x1, f.bbox_y1, f.bbox_x2, f.bbox_y2,
               f.embedding, f.crop_relpath, f.cluster_raw, f.cluster_key
        FROM faces f
        JOIN images i ON i.id = f.image_id
        {where}
        ORDER BY f.id
        """
    ).fetchall()
    result = []
    for row in rows:
        result.append(
            FaceRecord(
                id=int(row[0]),
                image_id=int(row[1]),
                image_path=str(row[2]),
                face_index=int(row[3]),
                det_score=float(row[4]),
                bbox=(int(row[5]), int(row[6]), int(row[7]), int(row[8])),
                embedding=decode_embedding(row[9]),
                crop_relpath=row[10],
                cluster_raw=None if row[11] is None else int(row[11]),
                cluster_key=row[12],
            )
        )
    return result


def load_images(conn: sqlite3.Connection) -> List[ImageRecord]:
    """Load image rows from SQLite keyed by image_id."""
    rows = conn.execute(
        "SELECT id, path, size, mtime, width, height, status, error FROM images ORDER BY id"
    ).fetchall()
    return [
        ImageRecord(
            id=int(r[0]), path=str(r[1]), size=int(r[2]), mtime=float(r[3]),
            width=r[4], height=r[5], status=str(r[6]), error=r[7]
        )
        for r in rows
    ]


# -----------------------------------------------------------------------------
# Image validation, timeout and worker helpers
# -----------------------------------------------------------------------------

def image_magic_status(path: Path, *, strict_extension: bool = False) -> Tuple[bool, str, str]:
    """Compatibility wrapper around file_ops.image_magic_status().

    v37 keeps the scan tolerant by default: files with wrong extensions but
    recognizable image headers are decoded instead of being skipped.
    """
    return file_image_magic_status(path, allow_header_only=False, strict_extension=strict_extension)


def estimate_file_megapixels(path: Path) -> float:
    """Cheap MP estimate for timeout calculation. Uses file size to avoid pre-decode hangs."""
    try:
        size = max(1, int(path.stat().st_size))
    except Exception:
        return 1.0
    # Rough JPEG/HEIC estimate. Clamp prevents absurd network/RAW values from producing days-long timeouts.
    return max(1.0, min(80.0, size / 3_000_000.0))


FILE_TIMEOUT_TABLE = {
    False: {
        "minimum": (120, 6, 600),
        "normal": (240, 10, 900),
        "high": (420, 16, 1500),
        "maximum": (600, 24, 2400),
        "recognition_max": (900, 36, 3600),
    },
    True: {
        "minimum": (45, 2, 180),
        "normal": (90, 3, 300),
        "high": (180, 5, 600),
        "maximum": (300, 8, 900),
        "recognition_max": (600, 12, 1800),
    },
}


def compute_file_timeout_seconds(args: argparse.Namespace, path: Path) -> Optional[int]:
    """Compute adaptive per-file timeout from profile, GPU/CPU and megapixels."""
    raw = str(getattr(args, "file_timeout", "auto") or "auto").strip().lower()
    if raw in {"0", "off", "none", "disabled", "disable"}:
        return None
    if raw not in {"auto", "automatic"}:
        try:
            val = int(float(raw))
            return None if val <= 0 else val
        except Exception:
            raw = "auto"
    profile = str(getattr(args, "scan_profile", "normal") or "normal")
    if profile == "manual":
        profile = "normal"
    table = FILE_TIMEOUT_TABLE[bool(getattr(args, "gpu", False))]
    base, per_mp, max_timeout = table.get(profile, table["normal"])
    mp = estimate_file_megapixels(path)
    return int(min(max_timeout, max(base + mp * per_mp, base)))


# ---------------------------------------------------------------------------
# Scan worker process functions
# ---------------------------------------------------------------------------
def worker_scan_init(model_name: str, use_gpu: bool, det_size: int, diagnostics_dir: Optional[str] = None, worker_run_id: Optional[str] = None) -> None:
    """Initialize one scan worker process with model/runtime configuration."""
    global _WORKER_FACE_APP, _WORKER_GPU_RUNTIME_FAILED, _WORKER_DIAGNOSTICS_DIR, _WORKER_RUN_ID, _WORKER_START_TIME
    _WORKER_START_TIME = time.time()
    _WORKER_DIAGNOSTICS_DIR = Path(diagnostics_dir) if diagnostics_dir else None
    _WORKER_RUN_ID = worker_run_id or f"worker-{os.getpid()}"
    try:
        atexit.register(_worker_shutdown_event)
    except Exception:
        pass

    _worker_event(
        "worker_start",
        python_exe=sys.executable,
        python_version=sys.version.replace("\n", " "),
        cwd=os.getcwd(),
        module_name=__name__,
        package_name=__package__,
        model=model_name,
        gpu=bool(use_gpu),
        det_size=int(det_size),
        sys_path_first_entries=sys.path[:10],
    )
    enable_worker_fault_handler()

    _worker_event("load_runtime_modules_start")
    try:
        load_runtime_modules()
        _worker_event(
            "load_runtime_modules_ok",
            packages=collect_package_versions(),
            onnx_providers=available_onnx_providers(),
        )
    except Exception as exc:
        _worker_event(
            "load_runtime_modules_error",
            error=repr(exc),
            traceback="".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-12000:],
        )
        raise

    _WORKER_GPU_RUNTIME_FAILED = False
    _worker_event("create_face_app_start", model=model_name, gpu=bool(use_gpu), det_size=int(det_size))
    try:
        _WORKER_FACE_APP = create_face_app(model_name, use_gpu, det_size)
        _worker_event("create_face_app_ok", model=model_name, gpu=bool(use_gpu), providers=available_onnx_providers())
    except Exception as exc:
        _worker_event(
            "create_face_app_error",
            model=model_name,
            gpu=bool(use_gpu),
            error=repr(exc),
            traceback="".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-12000:],
        )
        raise


def worker_scan_one_photo(path_str: str, max_side: int, upscale_small_to: int, strict_image_extensions: bool = False) -> Dict[str, Any]:
    """Run image decode + InsightFace in a worker process.

    Returned data is picklable and intentionally contains no original image bytes except
    small JPEG face crops for reports.
    """
    global _WORKER_FACE_APP
    load_runtime_modules()
    path = Path(path_str)
    task_id = short_hash(path_str + str(time.time()), 12)
    _worker_event(
        "task_start",
        task_id=task_id,
        path=str(path),
        path_hash=short_hash(str(path)),
        suffix=path.suffix.lower(),
        path_length=len(str(path)),
        name_length=len(path.name),
        max_side=max_side,
        upscale_small_to=upscale_small_to,
        strict_image_extensions=bool(strict_image_extensions),
    )
    ok, reason, message = image_magic_status(path, strict_extension=strict_image_extensions)
    try:
        stat = path.stat()
        size = int(stat.st_size)
        mtime = float(stat.st_mtime)
    except Exception:
        size = 0
        mtime = 0.0
    if not ok:
        _worker_event("task_magic_rejected", task_id=task_id, path_hash=short_hash(str(path)), reason=reason, message=message, size=size)
        return {"ok": False, "status": reason, "error": message, "size": size, "mtime": mtime, "width": None, "height": None, "faces": []}
    try:
        _worker_event("task_decode_start", task_id=task_id, path_hash=short_hash(str(path)), size=size)
        rgb, original_w, original_h = load_image_rgb(path, max_side=max_side, upscale_small_to=upscale_small_to)
        _worker_event("task_decode_ok", task_id=task_id, path_hash=short_hash(str(path)), width=original_w, height=original_h)
        bgr = rgb_to_bgr(rgb)
        _worker_event("task_inference_start", task_id=task_id, path_hash=short_hash(str(path)), image_shape=list(rgb.shape))
        faces = _WORKER_FACE_APP.get(bgr)
        _worker_event("task_inference_ok", task_id=task_id, path_hash=short_hash(str(path)), raw_faces=len(faces or []))
        image_h, image_w = rgb.shape[:2]
        out_faces: List[Dict[str, Any]] = []
        for face_index, face in enumerate(faces):
            det_score = float(getattr(face, "det_score", 0.0) or 0.0)
            emb = getattr(face, "normed_embedding", None)
            if emb is None:
                emb = getattr(face, "embedding", None)
            if emb is None:
                continue
            bbox = padded_bbox(getattr(face, "bbox"), image_w=image_w, image_h=image_h)
            x1, y1, x2, y2 = bbox
            crop_jpeg = None
            if x2 > x1 and y2 > y1:
                try:
                    crop = rgb[y1:y2, x1:x2]
                    buf = io.BytesIO()
                    Image.fromarray(crop).save(buf, format="JPEG", quality=88)
                    crop_jpeg = buf.getvalue()
                except Exception:
                    crop_jpeg = None
            out_faces.append({
                "face_index": face_index,
                "det_score": det_score,
                "bbox": bbox,
                "embedding": np.asarray(emb, dtype=np.float32).tolist(),
                "crop_jpeg": crop_jpeg,
            })
        _worker_event("task_ok", task_id=task_id, path_hash=short_hash(str(path)), faces_saved=len(out_faces), status="ok" if out_faces else "no_faces")
        return {"ok": True, "status": "ok" if out_faces else "no_faces", "error": None, "size": size, "mtime": mtime, "width": original_w, "height": original_h, "faces": out_faces}
    except PermissionError as exc:
        _worker_event("task_error", task_id=task_id, path_hash=short_hash(str(path)), kind="locked_or_permission_denied", error=repr(exc))
        return {"ok": False, "status": "locked_or_permission_denied", "error": str(exc), "size": size, "mtime": mtime, "width": None, "height": None, "faces": []}
    except Exception as exc:
        kind = "cuda_runtime" if looks_like_cuda_runtime_error(exc) else "decode_or_recognition_error"
        _worker_event(
            "task_error",
            task_id=task_id,
            path_hash=short_hash(str(path)),
            kind=kind,
            error=repr(exc),
            traceback="".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-12000:],
        )
        return {"ok": False, "status": kind, "error": (repr(exc) + " " + str(exc))[:4000], "size": size, "mtime": mtime, "width": None, "height": None, "faces": []}


def resolve_scan_workers(args: argparse.Namespace) -> int:
    """Resolve auto/manual scan worker count with conservative GPU defaults."""
    raw = str(getattr(args, "scan_workers", "auto") or "auto").strip().lower()
    if raw in {"0", "off", "none", "disabled", "disable"}:
        return 1
    if raw in {"auto", "automatic"}:
        if bool(getattr(args, "gpu", False)):
            return 1
        cpu = os.cpu_count() or 2
        return max(1, min(4, cpu // 2 or 1))
    try:
        val = int(float(raw))
    except Exception:
        val = 1
    if bool(getattr(args, "gpu", False)) and val > 1:
        print(lang_text("GPU-режим: scan_workers > 1 может вызвать нехватку VRAM/cuDNN. Использую 1 worker для стабильности.", "GPU mode: scan_workers > 1 may cause VRAM/cuDNN issues. Using 1 worker for stability."))
        return 1
    return max(1, min(16, val))


def resolve_copy_workers(args: argparse.Namespace) -> int:
    """Resolve auto/manual copy worker count for I/O-bound file copying."""
    raw = str(getattr(args, "copy_workers", "auto") or "auto").strip().lower()
    if raw in {"0", "off", "none", "disabled", "disable"}:
        return 1
    if raw in {"auto", "automatic"}:
        out = Path(getattr(args, "output", "") or ".")
        try:
            diag = file_path_diagnostics(out)
            if diag.get("is_network_path"):
                return 2
        except Exception:
            pass
        return 4
    try:
        return max(1, min(32, int(float(raw))))
    except Exception:
        return 4


def make_scan_executor(args: argparse.Namespace) -> concurrent.futures.ProcessPoolExecutor:
    """Create a ProcessPoolExecutor used for isolated image scanning."""
    diag_dir = diagnostics_dir_from_args(args)
    if diag_dir is not None:
        ensure_dir(diag_dir)
    workers = resolve_scan_workers(args)
    worker_run_id = f"scan-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    record_worker_pool_event(
        args,
        "executor_create",
        workers=workers,
        model=getattr(args, "model", None),
        gpu=bool(getattr(args, "gpu", False)),
        det_size=getattr(args, "det_size", None),
        worker_run_id=worker_run_id,
        diagnostics_dir=str(diag_dir) if diag_dir else None,
    )
    return concurrent.futures.ProcessPoolExecutor(
        max_workers=workers,
        initializer=worker_scan_init,
        initargs=(args.model, bool(getattr(args, "gpu", False)), int(args.det_size), str(diag_dir) if diag_dir else None, worker_run_id),
    )


def restart_scan_executor(executor: Optional[concurrent.futures.ProcessPoolExecutor], args: argparse.Namespace) -> concurrent.futures.ProcessPoolExecutor:
    """Restart the scan worker pool after timeout or fatal worker failure."""
    record_worker_pool_event(args, "executor_restart_start")
    if executor is not None:
        try:
            executor.shutdown(wait=False, cancel_futures=True)
            record_worker_pool_event(args, "executor_shutdown_after_restart_request_ok")
        except Exception as exc:
            record_worker_pool_event(args, "executor_shutdown_after_restart_request_error", error=repr(exc))
    return make_scan_executor(args)


# -----------------------------------------------------------------------------
# Image and face analysis
# -----------------------------------------------------------------------------

def load_image_rgb(path: Path, max_side: int = 1800, upscale_small_to: int = 0) -> Tuple[Any, int, int]:
    """Load one image as RGB, applying EXIF orientation and optional resizing/upscaling.

    The legacy module keeps Pillow/numpy imports lazy so dependency checks can run
    before heavy packages are imported.  Frozen diagnostic entry points and some
    PyInstaller call paths can reach this helper without going through the normal
    pipeline environment stage, so make the image loader self-healing instead of
    failing with ``Image is None``.
    """
    if Image is None or ImageOps is None or np is None:
        load_runtime_modules()
    if Image is None or ImageOps is None or np is None:
        raise RuntimeError("Image runtime modules are not loaded")
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        im = im.convert("RGB")
        original_w, original_h = im.size
        w, h = im.size
        if max_side and max(w, h) > max_side:
            scale = max_side / float(max(w, h))
            new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
            im = im.resize(new_size, Image.Resampling.LANCZOS)
            w, h = im.size
        if upscale_small_to and max(w, h) < upscale_small_to:
            scale = upscale_small_to / float(max(w, h))
            new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
            im = im.resize(new_size, Image.Resampling.LANCZOS)
        rgb = np.asarray(im)
        return rgb, original_w, original_h


def rgb_to_bgr(rgb: Any) -> Any:
    """Convert RGB numpy image to BGR for OpenCV/InsightFace."""
    return rgb[:, :, ::-1].copy()


def padded_bbox(bbox: Sequence[float], image_w: int, image_h: int, padding: float = 0.25) -> Tuple[int, int, int, int]:
    """Return a face crop box padded and clipped to image bounds."""
    x1, y1, x2, y2 = [float(v) for v in bbox]
    w = x2 - x1
    h = y2 - y1
    pad_x = w * padding
    pad_y = h * padding
    x1 = max(0, int(x1 - pad_x))
    y1 = max(0, int(y1 - pad_y))
    x2 = min(image_w, int(x2 + pad_x))
    y2 = min(image_h, int(y2 + pad_y))
    return x1, y1, x2, y2


def insightface_session_providers(app: Any) -> List[str]:
    """Return ONNX Runtime providers for requested CPU/GPU inference."""
    providers = []
    try:
        for model in getattr(app, "models", {}).values():
            session = getattr(model, "session", None)
            if session is not None and hasattr(session, "get_providers"):
                for p in session.get_providers():
                    if p not in providers:
                        providers.append(p)
    except Exception:
        pass
    return providers


def _build_face_app(model_name: str, providers: List[str], ctx_id: int, det_size: int):
    """Create and prepare an InsightFace FaceAnalysis object."""
    from insightface.app import FaceAnalysis
    app = FaceAnalysis(name=model_name, providers=providers)
    app.prepare(ctx_id=ctx_id, det_size=(det_size, det_size))
    return app


def create_face_app(model_name: str, use_gpu: bool, det_size: int):
    """Create FaceAnalysis with GPU fallback, model-pack repair and smoke-test protections."""
    model_name = normalize_model_name(model_name)
    try:
        from insightface.app import FaceAnalysis  # noqa: F401
    except Exception as exc:
        raise RuntimeError("Не удалось импортировать insightface. Выполните: python -m pip install insightface") from exc

    if use_gpu:
        preload_onnxruntime_cuda_dlls(verbose=False)
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        ctx_id = 0
    else:
        providers = ["CPUExecutionProvider"]
        ctx_id = -1

    def report_gpu_usage(app_obj):
        used = insightface_session_providers(app_obj)
        if use_gpu:
            if "CUDAExecutionProvider" in used:
                print(lang_text("InsightFace реально использует GPU/CUDA. Session providers:", "InsightFace is actually using GPU/CUDA. Session providers:"), used)
            else:
                print(lang_text("Предупреждение: InsightFace запущен, но CUDAExecutionProvider в session providers не виден.", "Warning: InsightFace started, but CUDAExecutionProvider is not visible in session providers."))
                print("Session providers:", used or lang_text("не удалось определить", "could not determine"))
                print(lang_text("Возможен скрытый откат на CPU. Запустите --mode diagnose-gpu для подробной проверки.", "A hidden CPU fallback is possible. Run --mode diagnose-gpu for a detailed check."))

    try:
        app = _build_face_app(model_name, providers, ctx_id, det_size)
        report_gpu_usage(app)
        return app
    except Exception as exc:
        if looks_like_missing_detection_assertion(exc):
            repaired = repair_nested_model_pack(model_name, verbose=True)
            if repaired:
                try:
                    app = _build_face_app(model_name, providers, ctx_id, det_size)
                    report_gpu_usage(app)
                    return app
                except Exception as exc2:
                    exc = exc2
            print_model_pack_hint(model_name)
            if model_name != DEFAULT_MODEL:
                print("\n" + lang_text("Откатываюсь с", "Falling back from"), model_name, lang_text("на стабильную модель", "to stable model"), DEFAULT_MODEL + ".")
                try:
                    app = _build_face_app(DEFAULT_MODEL, providers, ctx_id, det_size)
                    report_gpu_usage(app)
                    return app
                except Exception as default_exc:
                    if use_gpu:
                        print(lang_text("Не удалось запустить даже стабильную модель на GPU. Пробую CPU.", "Could not run even the stable model on GPU. Trying CPU."))
                        app = _build_face_app(DEFAULT_MODEL, ["CPUExecutionProvider"], -1, det_size)
                        return app
                    raise RuntimeError(f"Не удалось запустить model-pack {model_name} и fallback {DEFAULT_MODEL}.") from default_exc

        message = str(exc)
        if use_gpu:
            print("\n" + lang_text("Не удалось создать InsightFace в GPU-режиме. Пробую откат на CPU.", "Could not create InsightFace in GPU mode. Trying CPU fallback."))
            print(lang_text("GPU-ошибка:", "GPU error:"), (repr(exc) + " " + message)[:1000])
            try:
                app = _build_face_app(model_name, ["CPUExecutionProvider"], -1, det_size)
                return app
            except Exception as cpu_exc:
                if looks_like_missing_detection_assertion(cpu_exc) and model_name != DEFAULT_MODEL:
                    print_model_pack_hint(model_name)
                    print(lang_text("Откатываюсь на", "Falling back to"), DEFAULT_MODEL, "+ CPU.")
                    app = _build_face_app(DEFAULT_MODEL, ["CPUExecutionProvider"], -1, det_size)
                    return app
                raise
        if "Failed downloading url" in message or "download" in message.lower():
            model_root = Path.home() / ".insightface" / "models"
            raise RuntimeError(
                f"Не удалось скачать модель InsightFace '{model_name}'.\n"
                f"Проверьте интернет или скачайте model pack вручную в: {model_root}\n"
                f"Для стабильного старта используйте --model {DEFAULT_MODEL}."
            ) from exc
        raise



def _probe_float_scalar(value: Any, default: float = 0.0) -> float:
    """Convert scalar-like diagnostic values without numpy boolean coercion."""
    if value is None:
        return float(default)
    try:
        if hasattr(value, "tolist"):
            value = value.tolist()
        if isinstance(value, (list, tuple)):
            value = value[0] if value else default
        return float(value)
    except Exception:
        return float(default)


def _probe_float_list(value: Any, *, max_items: Optional[int] = None) -> List[float]:
    """Convert numpy arrays/lists for frozen diagnostics without ``value or []``."""
    if value is None:
        return []
    try:
        if hasattr(value, "tolist"):
            value = value.tolist()
        if isinstance(value, (str, bytes)):
            return []
        try:
            items = list(value)
        except TypeError:
            items = [value]
        out: List[float] = []
        for item in items:
            if max_items is not None and len(out) >= int(max_items):
                break
            try:
                out.append(float(item))
            except Exception:
                continue
        return out
    except Exception:
        return []


def _probe_face_sequence(value: Any) -> List[Any]:
    """Return a list of InsightFace faces without truth-testing numpy objects."""
    if value is None:
        return []
    try:
        return list(value)
    except TypeError:
        return [value]


def write_frozen_scan_probe(args: argparse.Namespace, app: Any, photos: Sequence[Path], output_dir: Path, *, max_images: int = 5) -> None:
    """Write a bounded real-image InsightFace probe for frozen CPU diagnostics.

    This does not change recognition data.  It only checks whether the same
    frozen process can decode a few input files, run ``app.get()``, and obtain
    embeddings.  The JSON goes into reports/diagnostics and is included in
    bug-reports.
    """
    if not bool(getattr(sys, "frozen", False)):
        return
    try:
        from .core.frozen_diagnostics import _face_app_summary, _model_pack_snapshot, package_import_snapshot, frozen_runtime_summary
    except Exception:
        try:
            from face_sorter_mvp.core.frozen_diagnostics import _face_app_summary, _model_pack_snapshot, package_import_snapshot, frozen_runtime_summary  # type: ignore
        except Exception as import_exc:
            record_module_event(args, "frozen_scan_probe_import_error", module="scan", error=repr(import_exc))
            return
    diag_dir = diagnostics_dir_for_output(output_dir)
    ensure_dir(diag_dir)
    probe: Dict[str, Any] = {
        "created_at": now_iso(),
        "script_version": SCRIPT_VERSION,
        "schema_version": 2,
        "frozen_runtime": frozen_runtime_summary(),
        "model": getattr(args, "model", None),
        "gpu": bool(getattr(args, "gpu", False)),
        "det_size": getattr(args, "det_size", None),
        "packages": package_import_snapshot(),
        "onnx_providers": available_onnx_providers(),
        "model_pack": _model_pack_snapshot(str(getattr(args, "model", DEFAULT_MODEL) or DEFAULT_MODEL)),
        "face_app": _face_app_summary(app),
        "photos": [],
        "faces_total": 0,
    }
    for path in list(photos)[:max(1, int(max_images or 5))]:
        row: Dict[str, Any] = {"path": str(path), "ok": False}
        try:
            ok, reason, message = image_magic_status(path, strict_extension=bool(getattr(args, "strict_image_extensions", False)))
            row["magic"] = {"ok": bool(ok), "reason": reason, "message": message}
            if not ok:
                row["error"] = message
                probe["photos"].append(row)
                continue
            rgb, original_w, original_h = load_image_rgb(path, max_side=args.max_side, upscale_small_to=args.upscale_small_to)
            row["image"] = {"width": int(original_w), "height": int(original_h), "array_shape": list(getattr(rgb, "shape", ())) }
            faces = _probe_face_sequence(app.get(rgb_to_bgr(rgb)))
            face_rows = []
            for face in faces:
                emb = getattr(face, "normed_embedding", None)
                if emb is None:
                    emb = getattr(face, "embedding", None)
                face_rows.append({
                    "det_score": _probe_float_scalar(getattr(face, "det_score", 0.0), 0.0),
                    "bbox": _probe_float_list(getattr(face, "bbox", None), max_items=4),
                    "embedding_present": emb is not None,
                    "embedding_shape": list(getattr(emb, "shape", ())) if emb is not None else [],
                })
            row["faces_count"] = len(faces)
            row["faces"] = face_rows[:10]
            row["ok"] = True
            probe["faces_total"] = int(probe.get("faces_total", 0) or 0) + len(faces)
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
            row["traceback"] = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-8000:]
        probe["photos"].append(row)
    try:
        (diag_dir / "frozen_scan_probe.json").write_text(json.dumps(probe, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as write_exc:
        record_module_event(args, "frozen_scan_probe_write_error", module="scan", error=repr(write_exc))
    record_module_event(args, "frozen_scan_probe_done", module="scan", faces_total=probe.get("faces_total"), photos=len(probe.get("photos", [])), path=str(diag_dir / "frozen_scan_probe.json"))

def face_size(face: FaceRecord) -> int:
    """Return max(width, height) for a detected face bounding box."""
    x1, y1, x2, y2 = face.bbox
    return min(max(0, x2 - x1), max(0, y2 - y1))


def print_scan_progress(stats: Dict[str, Any], total: int, start_time: float) -> None:
    """Print scan progress and emit callback progress events."""
    elapsed = max(0.001, time.time() - start_time)
    processed = int(stats.get("processed", 0))
    emit_progress("scan", processed, total, stats=dict(stats), elapsed=elapsed, unit="фото", rate_label="фото/мин")
    update_run_state_progress("scan", {
        "files_total": total,
        "files_scanned": processed,
        "scan_stats": dict(stats),
    })
    if active_callbacks().handles_console_output:
        return
    per_min = stats["processed"] / elapsed * 60.0
    print(
        "\n" + lang_text("[Статистика] ", "[Stats] ")
        + f"{stats['processed']}/{total} " + lang_text("фото", "photos") + " | "
        + lang_text("новых/пересканировано", "new/rescanned") + f": {stats['scanned']} | "
        + lang_text("кэш", "cache") + f": {stats['skipped_cached']} | "
        + lang_text("дубли", "duplicates") + f": {stats.get('skipped_duplicates', 0)} | "
        + f"problem-cache: {stats.get('skipped_problem_cache', 0)} | "
        + lang_text("с лицами", "with faces") + f": {stats['images_with_faces']} | "
        + lang_text("без лиц", "no faces") + f": {stats['no_faces']} | "
        + lang_text("лиц сохранено", "faces saved") + f": {stats['faces_saved']} | "
        + lang_text("ошибок", "errors") + f": {stats['errors']} | "
        + f"timeout: {stats.get('timeouts', 0)} | "
        + lang_text("скорость", "speed") + f": {per_min:.1f} " + lang_text("фото/мин", "photos/min")
    )


def print_stage(title: str, description: str = "") -> None:
    """Print a visible console stage separator and emit callback stage event."""
    emit_stage(title, description)
    if active_callbacks().handles_console_output:
        return
    print("\n" + "=" * 72)
    print(title)
    if description:
        print_wrapped(description)
    print("=" * 72)


def print_copy_progress(stats: Dict[str, Any], total: int, start_time: float) -> None:
    """Print copy progress and emit callback progress events."""
    elapsed = max(0.001, time.time() - start_time)
    processed = int(stats.get("processed", 0))
    emit_progress("copy", processed, total, stats=dict(stats), elapsed=elapsed, unit="файлов", rate_label="файлов/мин")
    update_run_state_progress("copy", {
        "copy_total": total,
        "files_copied": processed,
        "copy_stats": dict(stats),
    })
    if active_callbacks().handles_console_output:
        return
    per_min = stats["processed"] / elapsed * 60.0
    print(
        "\n" + lang_text("[Сортировка/копирование] ", "[Sorting/copying] ")
        + f"{stats['processed']}/{total} " + lang_text("файлов", "files") + " | "
        + f"people: {stats['copied_people']} | "
        + f"review: {stats['copied_review']} | "
        + f"group_photos: {stats['copied_group']} | "
        + lang_text("пропущено", "skipped") + f": {stats['missing_sources']} | "
        + f"duplicate-skip: {stats.get('skipped_duplicates', 0)} | "
        + lang_text("ошибок", "errors") + f": {stats['copy_errors']} | "
        + lang_text("скорость", "speed") + f": {per_min:.1f} " + lang_text("файлов/мин", "files/min")
    )


def save_worker_faces_to_db(args: argparse.Namespace, conn: sqlite3.Connection, path: Path, result: Dict[str, Any], crops_dir: Path) -> int:
    """Persist one worker result to SQLite and face crop files. Returns faces saved."""
    size = int(result.get("size") or 0)
    mtime = float(result.get("mtime") or 0.0)
    width = result.get("width")
    height = result.get("height")
    status = str(result.get("status") or "error")
    error = result.get("error")
    image_id = upsert_image(conn, path, size, mtime, width, height, status, error)
    faces_saved = 0
    for face in result.get("faces", []) or []:
        face_index = int(face.get("face_index") or 0)
        det_score = float(face.get("det_score") or 0.0)
        bbox_raw = face.get("bbox") or (0, 0, 0, 0)
        bbox = tuple(int(x) for x in bbox_raw)
        emb = face.get("embedding")
        crop_relpath = None
        crop_jpeg = face.get("crop_jpeg")
        if crop_jpeg:
            crop_name = f"img{image_id:08d}_face{face_index:02d}_{short_hash(str(path))}.jpg"
            crop_path = crops_dir / crop_name
            try:
                with crop_path.open("wb") as f:
                    f.write(crop_jpeg)
                crop_relpath = str(Path("reports") / "face_crops" / crop_name)
            except Exception:
                crop_relpath = None
        insert_face(conn, image_id, face_index, det_score, bbox, emb, crop_relpath)
        faces_saved += 1
    return faces_saved


# ---------------------------------------------------------------------------
# Pipeline stage implementations
# ---------------------------------------------------------------------------
def scan_photos(args: argparse.Namespace, conn: sqlite3.Connection) -> None:
    """Scan images, detect faces, cache embeddings and log problem files."""
    input_dir = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()
    crops_dir = output_dir / "reports" / "face_crops"
    ensure_dir(crops_dir)
    ensure_dir(diagnostics_dir_for_output(output_dir))
    write_runtime_diagnostics(args)
    record_module_event(
        args,
        "scan_start",
        module="scan",
        input_dir=str(input_dir),
        output_dir=str(output_dir),
        model=getattr(args, "model", None),
        gpu=bool(getattr(args, "gpu", False)),
        disable_scan_worker=bool(getattr(args, "disable_scan_worker", False)),
        scan_workers=getattr(args, "scan_workers", None),
    )

    use_worker = not bool(getattr(args, "disable_scan_worker", False))
    worker_count = resolve_scan_workers(args) if use_worker else 0

    # v65.4 CPU portable policy: the one-folder CPU EXE runs scan inline in
    # the main process.  This is now the official CPU portable mode, not a
    # temporary warning path.  It avoids the frozen Windows worker-runtime
    # mismatch found during v64.3-v65.4 packaging validation while keeping
    # recognition semantics unchanged; only the process boundary differs.
    frozen_runtime = bool(getattr(sys, "frozen", False))
    if frozen_runtime and use_worker and not bool(getattr(args, "gpu", False)):
        record_module_event(
            args,
            "frozen_cpu_portable_inline_scan",
            module="scan",
            requested_scan_workers=getattr(args, "scan_workers", None),
            resolved_scan_workers=worker_count,
            executable=sys.executable,
        )
        use_worker = False
        worker_count = 0

    app = None
    executor: Optional[concurrent.futures.ProcessPoolExecutor] = None
    if use_worker:
        print_stage(
            "Защита обработки файлов включена",
            f"Файлы обрабатываются через worker-процесс(ы) с таймаутом. scan_workers={worker_count}. "
            "Если файл с расширением изображения окажется битым, заблокированным или зависнет внутри Pillow/OpenCV/ONNX, "
            "worker будет перезапущен, файл попадёт в problem_files.csv, а обработка продолжится. "
            "В GPU-режиме по умолчанию используется 1 worker для стабильности VRAM/cuDNN."
        )
        executor = make_scan_executor(args)
    else:
        if frozen_runtime and not bool(getattr(args, "gpu", False)):
            print_stage(
                "CPU portable scan mode",
                "CPU portable EXE обрабатывает scan в основном процессе, без ProcessPool worker. "
                "Это штатный режим CPU one-folder сборки: он сохраняет стабильность frozen runtime и не меняет алгоритм распознавания."
            )
        else:
            print_stage(
                "Защита timeout отключена",
                "Файлы будут обрабатываться в основном процессе. Если C-библиотека зависнет на конкретном файле, скрипт может зависнуть. Используйте это только для отладки."
            )
        record_module_event(args, "inline_face_app_create_start", module="scan", model=args.model, gpu=bool(args.gpu), det_size=args.det_size)
        app = create_face_app(args.model, args.gpu, args.det_size)
        record_module_event(args, "inline_face_app_create_ok", module="scan", model=args.model, gpu=bool(args.gpu), providers=available_onnx_providers())

    photos = list(iter_images(input_dir))
    record_module_event(args, "scan_input_enumerated", module="scan", photos_count=len(photos))
    if frozen_runtime and app is not None:
        write_frozen_scan_probe(args, app, photos, output_dir)
    print(lang_text("Найдено файлов изображений:", "Image files found:"), len(photos))
    duplicate_map = detect_exact_duplicates(args, conn, photos)
    record_module_event(args, "scan_duplicates_checked", module="scan", duplicate_entries=len(duplicate_map))
    duplicate_policy = str(getattr(args, "duplicate_policy", "scan-one-copy-all") or "scan-one-copy-all")

    stats = {
        "processed": 0,
        "skipped_cached": 0,
        "skipped_duplicates": 0,
        "skipped_problem_cache": 0,
        "scanned": 0,
        "errors": 0,
        "timeouts": 0,
        "faces_saved": 0,
        "images_with_faces": 0,
        "no_faces": 0,
    }
    start_time = time.time()
    progress_every = max(1, int(getattr(args, "progress_every", 500) or 500))
    commit_every = max(1, int(getattr(args, "commit_every", 50) or 50))
    total = len(photos)

    def after_processed() -> None:
        if stats["processed"] % commit_every == 0:
            conn.commit()
        if stats["processed"] % progress_every == 0:
            print_scan_progress(stats, total, start_time)

    def mark_problem(path: Path, stage: str, reason: str, error: str, size: int = 0, mtime: float = 0.0, extra: Optional[Dict[str, Any]] = None) -> None:
        record_problem_file(args, path, reason, error, extra)
        try:
            upsert_problem_cache(conn, path, int(size), float(mtime), stage, reason, error)
        except Exception:
            pass

    def switch_scan_pool_to_inline(reason: BaseException) -> None:
        """Disable ProcessPool scanning after a worker-pool failure and continue inline."""
        nonlocal use_worker, executor, app
        if not use_worker and app is not None:
            return
        diag_summary = summarize_diagnostics(output_dir)
        record_worker_pool_event(
            args,
            "worker_pool_failed_switch_to_inline",
            reason_type=type(reason).__name__,
            reason=str(reason)[:4000],
            traceback="".join(traceback.format_exception_only(type(reason), reason)).strip(),
            last_worker_events=diag_summary.get("last_worker_events", [])[-10:],
        )
        print("\n" + lang_text(
            "[worker-pool] Worker-процесс сканирования упал. Переключаюсь на безопасное сканирование в основном процессе и продолжаю.",
            "[worker-pool] Scan worker process failed. Switching to safe in-process scanning and continuing."
        ))
        print(lang_text("Причина:", "Reason:"), str(reason)[:1500])
        try:
            if executor is not None:
                executor.shutdown(wait=False, cancel_futures=True)
                record_worker_pool_event(args, "executor_shutdown_after_failure_ok")
        except Exception as shutdown_exc:
            record_worker_pool_event(args, "executor_shutdown_after_failure_error", error=repr(shutdown_exc))
        executor = None
        use_worker = False
        if app is None:
            record_module_event(args, "inline_face_app_create_after_worker_failure_start", module="scan", model=args.model, gpu=bool(args.gpu), det_size=args.det_size)
            try:
                app = create_face_app(args.model, args.gpu, args.det_size)
                record_module_event(args, "inline_face_app_create_after_worker_failure_ok", module="scan", model=args.model, gpu=bool(args.gpu), providers=available_onnx_providers())
            except Exception as app_exc:
                record_module_event(
                    args,
                    "inline_face_app_create_after_worker_failure_error",
                    module="scan",
                    error=repr(app_exc),
                    traceback="".join(traceback.format_exception(type(app_exc), app_exc, app_exc.__traceback__))[-12000:],
                )
                raise

    def precheck_or_submit(path: Path, inflight: Dict[Any, Dict[str, Any]]) -> None:
        """Either skip/cache a file immediately or submit it to a worker."""
        nonlocal use_worker, executor, app
        try:
            stat = path.stat()
            size = int(stat.st_size)
            mtime = float(stat.st_mtime)
        except Exception as exc:
            stats["processed"] += 1
            stats["errors"] += 1
            mark_problem(path, "stat", "stat_error", str(exc))
            after_processed()
            return

        dup_info = duplicate_map.get(str(path))
        if dup_info and dup_info.get("role") == "duplicate" and duplicate_policy in {"scan-one-copy-all", "scan-one-copy-first"}:
            stats["processed"] += 1
            stats["skipped_duplicates"] += 1
            upsert_image(
                conn, path, size, mtime, None, None, "duplicate",
                f"canonical={dup_info.get('canonical_path', '')}; group={dup_info.get('duplicate_group_id', '')}; action={dup_info.get('action', '')}"
            )
            after_processed()
            return

        if bool(getattr(args, "reuse_problem_cache", True)):
            cached_problem = problem_cache_is_current(conn, path, size, mtime)
            if cached_problem:
                stats["processed"] += 1
                stats["errors"] += 1
                stats["skipped_problem_cache"] += 1
                upsert_image(conn, path, size, mtime, None, None, cached_problem.get("reason") or "cached_problem", cached_problem.get("error") or "cached problem")
                after_processed()
                return

        if not args.rescan and image_cache_is_current(conn, path, size, mtime):
            stats["processed"] += 1
            stats["skipped_cached"] += 1
            after_processed()
            return

        if use_worker:
            timeout_seconds = compute_file_timeout_seconds(args, path)
            try:
                if executor is None:
                    executor = make_scan_executor(args)
                future = executor.submit(
                    worker_scan_one_photo,
                    str(path),
                    int(args.max_side),
                    int(args.upscale_small_to),
                    bool(getattr(args, "strict_image_extensions", False)),
                )
                inflight[future] = {"path": path, "size": size, "mtime": mtime, "started": time.time(), "timeout": timeout_seconds}
                return
            except concurrent.futures.process.BrokenProcessPool as pool_exc:
                record_worker_pool_event(args, "submit_broken_process_pool", path=str(path), path_hash=short_hash(str(path)), error=repr(pool_exc))
                switch_scan_pool_to_inline(pool_exc)
            except Exception as submit_exc:
                # submit() can fail before the future exists when Windows spawn/import,
                # CUDA worker initialization, or process creation fails. Treat this as
                # a pool-level failure and continue inline instead of aborting the run.
                record_worker_pool_event(args, "submit_exception", path=str(path), path_hash=short_hash(str(path)), error=repr(submit_exc))
                switch_scan_pool_to_inline(submit_exc)

        # Synchronous debug / worker-fallback mode.
        try:
            ok, reason, message = image_magic_status(path, strict_extension=bool(getattr(args, "strict_image_extensions", False)))
            if not ok:
                stats["processed"] += 1
                stats["errors"] += 1
                mark_problem(path, "magic", reason, message, size, mtime)
                upsert_image(conn, path, size, mtime, None, None, reason, message)
                after_processed()
                return
            rgb, original_w, original_h = load_image_rgb(path, max_side=args.max_side, upscale_small_to=args.upscale_small_to)
            bgr = rgb_to_bgr(rgb)
            try:
                faces = app.get(bgr)
            except Exception as infer_exc:
                if getattr(args, "gpu", False) and getattr(args, "auto_cpu_fallback", True) and looks_like_cuda_runtime_error(infer_exc):
                    print_stage(
                        "GPU/CUDA дал ошибку во время реального распознавания",
                        "CUDAExecutionProvider был виден, но cuDNN/CUDA упали при выполнении модели. Скрипт переключается на CPU и продолжает с текущего фото."
                    )
                    print(lang_text("GPU-ошибка:", "GPU error:"), str(infer_exc)[:1500])
                    args.gpu = False
                    app = create_face_app(args.model, False, args.det_size)
                    faces = app.get(bgr)
                else:
                    raise

            status = "ok" if faces else "no_faces"
            image_id = upsert_image(conn, path, size, mtime, original_w, original_h, status, None)
            stats["processed"] += 1
            stats["scanned"] += 1
            if faces:
                stats["images_with_faces"] += 1
            else:
                stats["no_faces"] += 1

            image_h, image_w = rgb.shape[:2]
            for face_index, face in enumerate(faces):
                det_score = float(getattr(face, "det_score", 0.0) or 0.0)
                emb = getattr(face, "normed_embedding", None)
                if emb is None:
                    emb = getattr(face, "embedding", None)
                if emb is None:
                    continue
                bbox = padded_bbox(getattr(face, "bbox"), image_w=image_w, image_h=image_h)
                x1, y1, x2, y2 = bbox
                crop_relpath = None
                if x2 > x1 and y2 > y1:
                    crop = rgb[y1:y2, x1:x2]
                    crop_name = f"img{image_id:08d}_face{face_index:02d}_{short_hash(str(path))}.jpg"
                    crop_path = crops_dir / crop_name
                    try:
                        Image.fromarray(crop).save(crop_path, quality=88)
                        crop_relpath = str(Path("reports") / "face_crops" / crop_name)
                    except Exception:
                        crop_relpath = None
                insert_face(conn, image_id, face_index, det_score, bbox, emb, crop_relpath)
                stats["faces_saved"] += 1
            after_processed()
        except Exception as exc:
            stats["processed"] += 1
            stats["errors"] += 1
            mark_problem(path, "scan", "scan", str(exc), size, mtime, {"traceback": "".join(traceback.format_exception_only(type(exc), exc)).strip()})
            try:
                upsert_image(conn, path, size, mtime, None, None, "error", str(exc))
            except Exception:
                pass
            if args.verbose:
                traceback.print_exc()
            after_processed()

    try:
        ensure_non_null_stdio()
        if use_worker:
            index = 0
            inflight: Dict[Any, Dict[str, Any]] = {}
            while index < len(photos) or inflight:
                while index < len(photos) and len(inflight) < worker_count:
                    precheck_or_submit(photos[index], inflight)
                    index += 1

                if not inflight:
                    continue

                done, _pending = concurrent.futures.wait(inflight.keys(), timeout=1.0, return_when=concurrent.futures.FIRST_COMPLETED)
                now = time.time()
                timed_out = []
                if not done:
                    for fut, meta in list(inflight.items()):
                        timeout_seconds = meta.get("timeout")
                        if timeout_seconds is not None and now - float(meta.get("started", now)) > float(timeout_seconds):
                            timed_out.append(fut)
                            break

                if timed_out:
                    timeout_future = timed_out[0]
                    meta = inflight.pop(timeout_future)
                    path = meta["path"]
                    size = int(meta.get("size") or 0)
                    mtime = float(meta.get("mtime") or 0.0)
                    timeout_seconds = meta.get("timeout")
                    stats["processed"] += 1
                    stats["errors"] += 1
                    stats["timeouts"] += 1
                    record_worker_pool_event(args, "worker_timeout", path=str(path), path_hash=short_hash(str(path)), timeout_seconds=timeout_seconds or "disabled")
                    mark_problem(path, "scan", "scan_timeout", "worker timeout", size, mtime, {"timeout_seconds": timeout_seconds or "disabled"})
                    try:
                        upsert_image(conn, path, size, mtime, None, None, "timeout", f"file timeout after {timeout_seconds} seconds")
                    except Exception:
                        pass
                    print("\n[timeout] " + lang_text("Файл пропущен после", "File skipped after"), timeout_seconds, lang_text("сек:", "sec:"), path)
                    # Restart the whole pool. Re-queue other in-flight files because Windows cannot safely kill one stuck process inside a pool.
                    requeue = [m["path"] for m in inflight.values()]
                    inflight.clear()
                    executor = restart_scan_executor(executor, args)
                    photos = requeue + photos[index:]
                    index = 0
                    after_processed()
                    continue

                for fut in list(done):
                    meta = inflight.pop(fut)
                    path = meta["path"]
                    size = int(meta.get("size") or 0)
                    mtime = float(meta.get("mtime") or 0.0)
                    stats["processed"] += 1
                    try:
                        result = fut.result()
                    except concurrent.futures.process.BrokenProcessPool as worker_exc:
                        stats["processed"] -= 1
                        record_worker_pool_event(args, "future_result_broken_process_pool", path=str(path), path_hash=short_hash(str(path)), error=repr(worker_exc))
                        switch_scan_pool_to_inline(worker_exc)
                        # Re-queue any other in-flight work and process the current file
                        # in the main process so one dead child cannot stop the pipeline.
                        requeue = [m["path"] for m in inflight.values()]
                        inflight.clear()
                        photos = [path] + requeue + photos[index:]
                        index = 0
                        continue
                    except Exception as worker_exc:
                        stats["errors"] += 1
                        record_worker_pool_event(args, "future_result_exception", path=str(path), path_hash=short_hash(str(path)), error=repr(worker_exc))
                        mark_problem(path, "scan", "scan_worker", str(worker_exc), size, mtime, {"traceback": "".join(traceback.format_exception_only(type(worker_exc), worker_exc)).strip()})
                        if getattr(args, "verbose", False):
                            traceback.print_exc()
                        after_processed()
                        continue

                    if not result.get("ok"):
                        reason = str(result.get("status") or "error")
                        error = str(result.get("error") or reason)
                        stats["errors"] += 1
                        mark_problem(path, "scan", reason, error, int(result.get("size") or size), float(result.get("mtime") or mtime))
                        upsert_image(conn, path, int(result.get("size") or size), float(result.get("mtime") or mtime), None, None, reason, error)
                        after_processed()
                        continue

                    faces_saved = save_worker_faces_to_db(args, conn, path, result, crops_dir)
                    stats["scanned"] += 1
                    stats["faces_saved"] += faces_saved
                    if faces_saved:
                        stats["images_with_faces"] += 1
                    else:
                        stats["no_faces"] += 1
                    after_processed()
        else:
            iterator = tqdm(photos, desc="Scan", unit="photo") if tqdm else photos
            for path in iterator:
                precheck_or_submit(path, {})

        conn.commit()
        print_scan_progress(stats, total, start_time)
        record_module_event(args, "scan_done", module="scan", stats=dict(stats), used_worker=bool(use_worker), total=total, frozen_runtime=frozen_runtime)
        if total and int(stats.get("faces_saved", 0) or 0) <= 0:
            record_module_event(
                args,
                "scan_done_zero_faces",
                module="scan",
                stats=dict(stats),
                used_worker=bool(use_worker),
                frozen_runtime=frozen_runtime,
                hint="No faces/embeddings were saved after scan. Check problem_files.csv, model cache and frozen/source runtime differences.",
            )
            print(lang_text(
                "Сканирование завершено, но лица/embeddings не сохранены. Проверьте reports/problem_files.csv и diagnostics; если source-запуск на той же папке находит лица, это проблема frozen runtime/model cache.",
                "Scanning finished, but no faces/embeddings were saved. Check reports/problem_files.csv and diagnostics; if source mode finds faces on the same folder, this is a frozen runtime/model-cache issue."
            ))
        print(lang_text("Сканирование завершено.", "Scanning finished."))
        if stats.get("timeouts"):
            print(lang_text("Файлов пропущено по timeout:", "Files skipped by timeout:"), stats["timeouts"], lang_text("— подробности в reports/", "— details in reports/") + PROBLEM_FILES_NAME)
        if stats.get("skipped_problem_cache"):
            print(lang_text("Пропущено по кэшу проблемных файлов:", "Skipped by problem-file cache:"), stats["skipped_problem_cache"])
    except Exception as scan_exc:
        record_module_event(
            args,
            "scan_error",
            module="scan",
            error=repr(scan_exc),
            traceback="".join(traceback.format_exception(type(scan_exc), scan_exc, scan_exc.__traceback__))[-12000:],
            stats=dict(stats),
        )
        raise
    finally:
        if executor is not None:
            try:
                executor.shutdown(wait=False, cancel_futures=True)
                record_worker_pool_event(args, "executor_shutdown_at_scan_end_ok")
            except Exception as shutdown_exc:
                record_worker_pool_event(args, "executor_shutdown_at_scan_end_error", error=repr(shutdown_exc))

def filtered_faces_for_clustering(args: argparse.Namespace, conn: sqlite3.Connection) -> List[FaceRecord]:
    """Return faces eligible for clustering after quality/size filters."""
    faces = load_faces(conn)
    result = []
    for f in faces:
        if f.det_score < float(args.min_det_score):
            continue
        if face_size(f) < int(args.min_face_size):
            continue
        result.append(f)
    return result


def small_set_single_person_labels(args: argparse.Namespace, faces: List[FaceRecord]) -> Optional[List[int]]:
    """Return one-cluster labels for a tiny set that is clearly one person.

    HDBSCAN cannot create a cluster when the number of eligible faces is below
    min_cluster_size.  For friend/family folders this is too harsh: one or a few
    photos of the same person should still produce person_001 instead of an
    error or review-only output.  Keep the fallback conservative: a single face is
    trivially one person; multiple faces must all be mutually similar enough.
    """
    if not faces:
        return None
    if len(faces) == 1:
        return [0]
    X = np.vstack([f.embedding for f in faces]).astype(np.float32)
    # Embeddings are normalized; cosine similarity is a direct dot product.
    cosine_threshold = float(os.environ.get("FACE_SORTER_SMALL_SET_COSINE_THRESHOLD", "0.58") or "0.58")
    min_cosine = 1.0
    for i in range(len(faces)):
        for j in range(i + 1, len(faces)):
            sim = float(np.dot(X[i], X[j]))
            if sim < min_cosine:
                min_cosine = sim
            if sim < cosine_threshold:
                record_module_event(
                    args,
                    "cluster_small_set_not_compact",
                    module="cluster",
                    faces=len(faces),
                    min_pairwise_cosine=min_cosine,
                    cosine_threshold=cosine_threshold,
                    behavior="continue_with_review_unknown_faces",
                )
                return None
    record_module_event(
        args,
        "cluster_small_set_single_person_fallback",
        module="cluster",
        faces=len(faces),
        min_pairwise_cosine=min_cosine,
        cosine_threshold=cosine_threshold,
        behavior="create_person_001",
    )
    return [0 for _ in faces]


def cluster_faces(args: argparse.Namespace, conn: sqlite3.Connection) -> None:
    """Cluster face embeddings into person_XXX groups using HDBSCAN or DBSCAN."""
    print_stage(
        "Этап кластеризации лиц",
        "Сейчас скрипт группирует похожие лица в person_001/person_002/... Это может занять заметное время на больших архивах. Папки people могут появиться только после завершения кластеризации и начала копирования."
    )
    faces = filtered_faces_for_clustering(args, conn)
    print(lang_text("Лиц для кластеризации после фильтров:", "Faces for clustering after filters:"), len(faces))
    conn.execute("UPDATE faces SET cluster_raw=NULL, cluster_key=NULL")
    min_cluster_size = max(2, int(args.min_cluster_size))
    if len(faces) < min_cluster_size:
        labels = small_set_single_person_labels(args, faces)
        if labels is None:
            conn.commit()
            record_module_event(
                args,
                "cluster_too_few_faces",
                module="cluster",
                faces=len(faces),
                min_cluster_size=min_cluster_size,
                behavior="continue_with_review_unknown_faces",
            )
            print(lang_text(
                "Слишком мало лиц для устойчивой кластеризации, и они не выглядят как один человек; фото будут отправлены в review/unknown_faces, запуск продолжится.",
                "Too few faces for stable clustering, and they do not look like one person; photos will be sent to review/unknown_faces and the run will continue.",
            ))
            return
        label_to_key = {0: "person_001"}
        for face, label in zip(faces, labels):
            conn.execute(
                "UPDATE faces SET cluster_raw=?, cluster_key=? WHERE id=?",
                (int(label), label_to_key[int(label)], face.id),
            )
        conn.commit()
        print(lang_text(
            "Маленький набор распознан как один человек: создан кластер person_001.",
            "Small set recognized as one person: created cluster person_001.",
        ))
        print(lang_text("Кластеров найдено:", "Clusters found:"), 1)
        print("Noise/unknown faces: 0")
        return

    X = np.vstack([f.embedding for f in faces]).astype(np.float32)
    # Embeddings already normalized. Euclidean distance on normalized vectors is stable here.
    if args.algo == "hdbscan":
        try:
            import hdbscan
        except Exception as exc:
            raise RuntimeError("Не удалось импортировать hdbscan. Установите hdbscan или используйте --algo dbscan.") from exc
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=int(args.min_cluster_size),
            min_samples=args.min_samples,
            metric="euclidean",
            cluster_selection_method=args.cluster_selection_method,
        )
        print(lang_text("Запускаю HDBSCAN. Ожидайте завершения расчёта кластеров...", "Running HDBSCAN. Wait for clustering to finish..."))
        labels = clusterer.fit_predict(X)
    else:
        from sklearn.cluster import DBSCAN
        min_samples = int(args.min_samples) if args.min_samples is not None else max(2, int(args.min_cluster_size))
        clusterer = DBSCAN(eps=float(args.dbscan_eps), min_samples=min_samples, metric="euclidean")
        print(lang_text("Запускаю DBSCAN. Ожидайте завершения расчёта кластеров...", "Running DBSCAN. Wait for clustering to finish..."))
        labels = clusterer.fit_predict(X)

    label_counts = Counter(int(x) for x in labels if int(x) >= 0)
    sorted_labels = [label for label, _count in label_counts.most_common()]
    label_to_key = {label: f"person_{idx:03d}" for idx, label in enumerate(sorted_labels, start=1)}
    if not label_to_key:
        record_module_event(
            args,
            "cluster_no_clusters_found",
            module="cluster",
            faces=len(faces),
            algorithm=str(getattr(args, "algo", "")),
            min_cluster_size=int(getattr(args, "min_cluster_size", 0) or 0),
            behavior="continue_with_review_unknown_faces",
        )

    for face, label in zip(faces, labels):
        label = int(label)
        if label >= 0:
            conn.execute(
                "UPDATE faces SET cluster_raw=?, cluster_key=? WHERE id=?",
                (label, label_to_key[label], face.id),
            )
    conn.commit()

    print(lang_text("Кластеров найдено:", "Clusters found:"), len(label_to_key))
    print(f"Noise/unknown faces: {sum(1 for x in labels if int(x) < 0)}")


# -----------------------------------------------------------------------------
# Assigning and copying photos
# -----------------------------------------------------------------------------

def build_centroids(faces: List[FaceRecord]) -> Dict[str, Any]:
    """Compute normalized cluster centroids for best-face assignment scoring."""
    grouped = defaultdict(list)
    for f in faces:
        if f.cluster_key:
            grouped[f.cluster_key].append(f.embedding)
    centroids = {}
    for key, embs in grouped.items():
        centroid = np.mean(np.vstack(embs), axis=0)
        norm = float(np.linalg.norm(centroid))
        if norm > 0:
            centroid = centroid / norm
        centroids[key] = centroid.astype(np.float32)
    return centroids


def compute_image_assignments(args: argparse.Namespace, conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Assign each image to people/review buckets using cluster scores and policies."""
    images = load_images(conn)
    faces = load_faces(conn)
    faces_by_image = defaultdict(list)
    for f in faces:
        faces_by_image[f.image_id].append(f)
    centroids = build_centroids([f for f in faces if f.cluster_key])

    assignments = []
    assigned_name_index: List[Tuple[str, str, str]] = []  # stem, cluster_key, path

    # First pass: normal recognition assignment.
    for img in images:
        img_faces = faces_by_image.get(img.id, [])
        clustered = [f for f in img_faces if f.cluster_key]
        all_cluster_keys = sorted({f.cluster_key for f in clustered if f.cluster_key})
        selected_cluster = None
        reason = None
        score = None
        competing = []
        review_bucket = None

        if not img_faces:
            review_bucket = "no_faces" if img.status == "no_faces" else ("errors" if img.status == "error" else "unknown")
            reason = img.status
        elif not clustered:
            review_bucket = "unknown_faces"
            reason = "faces_detected_but_not_clustered"
        elif args.photo_assignment == "all-faces":
            selected_cluster = ";".join(all_cluster_keys)
            reason = "all_faces"
        else:
            best = None
            for f in clustered:
                centroid = centroids.get(f.cluster_key)
                if centroid is None:
                    continue
                sim = float(np.dot(f.embedding, centroid))
                s = 0.80 * sim + 0.20 * float(f.det_score)
                competing.append(f"{f.cluster_key}:{s:.4f}")
                if best is None or s > best[0]:
                    best = (s, f.cluster_key)
            if best is not None:
                score, selected_cluster = best
                reason = "best_face"
            else:
                review_bucket = "unknown_faces"
                reason = "no_centroid"

        if selected_cluster and args.photo_assignment != "all-faces":
            assigned_name_index.append((Path(img.path).stem, selected_cluster, img.path))

        assignments.append({
            "image_id": img.id,
            "image_path": img.path,
            "status": img.status,
            "selected_cluster": selected_cluster or "",
            "review_bucket": review_bucket or "",
            "reason": reason or "",
            "score": "" if score is None else f"{score:.6f}",
            "all_clusters": ";".join(all_cluster_keys),
            "competing": " | ".join(competing),
            "duplicate_group_id": "",
            "canonical_path": "",
            "duplicate_role": "",
            "duplicate_action": "",
            "skip_copy": "",
        })

    # Second pass: propagate exact duplicate assignments from canonical images.
    duplicate_links = load_duplicate_links(conn)
    duplicate_policy = str(getattr(args, "duplicate_policy", "scan-one-copy-all") or "scan-one-copy-all")
    by_path = {item["image_path"]: item for item in assignments}
    if duplicate_policy in {"scan-one-copy-all", "scan-one-copy-first"}:
        for item in assignments:
            link = duplicate_links.get(item["image_path"])
            if not link:
                continue
            item["duplicate_group_id"] = link.get("duplicate_group_id", "")
            item["canonical_path"] = link.get("canonical_path", "")
            item["duplicate_role"] = link.get("role", "")
            item["duplicate_action"] = link.get("action", "")
            if link.get("role") != "duplicate":
                continue
            canonical = by_path.get(link.get("canonical_path", ""))
            if not canonical:
                item["review_bucket"] = "duplicate_without_canonical_assignment"
                item["reason"] = "duplicate_canonical_missing"
                continue
            if duplicate_policy == "scan-one-copy-first":
                item["selected_cluster"] = ""
                item["review_bucket"] = ""
                item["reason"] = "duplicate_skip_copy_first"
                item["score"] = ""
                item["all_clusters"] = canonical.get("all_clusters", "")
                item["competing"] = f"canonical={link.get('canonical_path', '')}; canonical_reason={canonical.get('reason', '')}"
                item["skip_copy"] = "1"
            else:
                item["selected_cluster"] = canonical.get("selected_cluster", "")
                item["review_bucket"] = canonical.get("review_bucket", "")
                item["reason"] = "duplicate_same_as_canonical:" + str(canonical.get("reason", ""))
                item["score"] = canonical.get("score", "")
                item["all_clusters"] = canonical.get("all_clusters", "")
                item["competing"] = f"canonical={link.get('canonical_path', '')}; canonical_reason={canonical.get('reason', '')}"

    # Third pass: filename fallback only for review images.
    if getattr(args, "filename_fallback", False) and assigned_name_index:
        max_dist = int(args.filename_max_distance)
        for item in assignments:
            if item.get("skip_copy") or item["selected_cluster"]:
                continue
            stem = Path(item["image_path"]).stem
            best = None
            for known_stem, cluster_key, known_path in assigned_name_index:
                d = levenshtein_distance(stem, known_stem, max_distance=max_dist)
                if d <= max_dist and (best is None or d < best[0]):
                    best = (d, cluster_key, known_path)
                    if d == 0:
                        break
            if best is not None:
                d, cluster_key, known_path = best
                item["selected_cluster"] = cluster_key
                item["review_bucket"] = ""
                item["reason"] = f"filename_fallback_distance_{d}"
                item["score"] = ""
                item["competing"] = f"matched_filename={Path(known_path).name}"
    return assignments


def write_assignments_csv(args: argparse.Namespace, assignments: List[Dict[str, Any]]) -> Path:
    """Write the assignment plan consumed by the copy stage."""
    report_dir = Path(args.output).resolve() / "reports"
    ensure_dir(report_dir)
    path = report_dir / "assignments.csv"
    fields = ["image_id", "image_path", "status", "selected_cluster", "review_bucket", "reason", "score", "all_clusters", "competing", "duplicate_group_id", "canonical_path", "duplicate_role", "duplicate_action", "skip_copy"]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in assignments:
            writer.writerow({k: row.get(k, "") for k in fields})
    return path



def assignments_csv_path(args: argparse.Namespace) -> Path:
    """Return the canonical assignments.csv path for the current project."""
    return Path(args.output).resolve() / "reports" / "assignments.csv"


def assign_photos(args: argparse.Namespace, conn: sqlite3.Connection) -> Path:
    """Compute image -> target assignment without copying files.

    This is the independent "assign" stage for future UI buttons. It writes
    reports/assignments.csv and can be re-run after changing photo_assignment or
    filename_fallback without re-scanning faces or re-clustering embeddings.
    """
    print_stage(
        "Этап назначения файлов",
        "Сейчас скрипт выбирает целевую папку для каждого фото, но ещё не копирует файлы. Результат будет записан в reports/assignments.csv."
    )
    print(lang_text("Готовлю назначения файлов по лучшим лицевым совпадениям...", "Preparing file assignments by best face matches..."))
    assignments = compute_image_assignments(args, conn)
    path = write_assignments_csv(args, assignments)
    print(lang_text("Назначений подготовлено:", "Assignments prepared:"), len(assignments))
    print(lang_text("Отчёт назначений:", "Assignments report:"), path)
    return path


def read_assignments_csv(path: Path) -> List[Dict[str, Any]]:
    """Read assignment rows created by the assign stage."""
    if not path.exists():
        raise FileNotFoundError(f"Не найден assignments.csv: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def copy_from_assignments(args: argparse.Namespace, assignments: List[Dict[str, Any]], assignments_path: Path) -> None:
    """Copy files according to a previously generated assignments.csv.

    v32 uses a small ThreadPoolExecutor for copy operations. Copying is I/O-bound and
    safe to parallelize; recognition/SQLite writes remain in the main process.
    """
    print_stage(
        "Этап копирования файлов",
        "Сейчас скрипт копирует файлы по уже подготовленному reports/assignments.csv в output/people или output/review."
    )
    output_dir = Path(args.output).resolve()
    people_dir = output_dir / "people"
    review_dir = output_dir / "review"
    if args.clean_folders:
        print(lang_text("Очищаю старые папки people/review перед новым копированием...", "Cleaning old people/review folders before copying..."))
        reset_dir(people_dir)
        reset_dir(review_dir)
    else:
        ensure_dir(people_dir)
        ensure_dir(review_dir)

    total = len(assignments)
    print(lang_text("Назначений для копирования:", "Assignments to copy:"), total)
    print(lang_text("Источник назначений:", "Assignments source:"), assignments_path)
    if total == 0:
        print(lang_text("Нет файлов для копирования.", "No files to copy."))
        return

    progress_every = max(1, int(getattr(args, "progress_every", 500) or 500))
    copy_workers = resolve_copy_workers(args)
    stats = {
        "processed": 0,
        "copied_people": 0,
        "copied_review": 0,
        "copied_group": 0,
        "missing_sources": 0,
        "copy_errors": 0,
        "skipped_duplicates": 0,
    }
    start_time = time.time()

    print(lang_text("Начинаю копирование. copy_workers=", "Starting copy. copy_workers=") + f"{copy_workers}. " + lang_text("Промежуточная статистика будет выводиться каждые ", "Intermediate stats will be printed every ") + f"{progress_every} " + lang_text("файлов.", "files."))

    def copy_one(item: Dict[str, Any]) -> Dict[str, Any]:
        result = {
            "copied_people": 0,
            "copied_review": 0,
            "copied_group": 0,
            "missing_sources": 0,
            "copy_errors": 0,
            "skipped_duplicates": 0,
            "errors": [],
        }
        if str(item.get("skip_copy", "")).strip() in {"1", "true", "True", "yes"}:
            result["skipped_duplicates"] += 1
            return result
        src = Path(item.get("image_path", ""))
        if not src.exists():
            result["missing_sources"] += 1
            result["errors"].append((src, "copy_missing_source", "source file does not exist", {}))
            return result
        try:
            selected = item.get("selected_cluster", "")
            if selected:
                clusters = [c for c in selected.split(";") if c]
                for cluster_key in clusters:
                    copy_file(src, people_dir / cluster_key, args.dry_run, args=args)
                    result["copied_people"] += 1
            else:
                bucket = item.get("review_bucket") or "unknown"
                copy_file(src, review_dir / bucket, args.dry_run, args=args)
                result["copied_review"] += 1

            if getattr(args, "copy_group_photos", False):
                all_clusters = [c for c in str(item.get("all_clusters", "")).split(";") if c]
                if len(all_clusters) >= 2:
                    copy_file(src, review_dir / "group_photos", args.dry_run, args=args)
                    result["copied_group"] += 1
        except Exception as exc:
            result["copy_errors"] += 1
            result["errors"].append((src, "copy", str(exc), {"selected_cluster": item.get("selected_cluster", ""), "review_bucket": item.get("review_bucket", "")}))
        return result

    def apply_copy_result(res: Dict[str, Any]) -> None:
        for key in ("copied_people", "copied_review", "copied_group", "missing_sources", "copy_errors", "skipped_duplicates"):
            stats[key] += int(res.get(key, 0) or 0)
        for src, stage, error, extra in res.get("errors", []) or []:
            record_problem_file(args, Path(src), stage, error, extra)

    if copy_workers <= 1:
        for item in assignments:
            stats["processed"] += 1
            apply_copy_result(copy_one(item))
            if stats["processed"] % progress_every == 0:
                print_copy_progress(stats, total, start_time)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=copy_workers) as pool:
            futures = [pool.submit(copy_one, item) for item in assignments]
            for fut in concurrent.futures.as_completed(futures):
                stats["processed"] += 1
                try:
                    apply_copy_result(fut.result())
                except Exception as exc:
                    stats["copy_errors"] += 1
                    record_problem_file(args, Path("<copy-worker>"), "copy_worker", str(exc))
                    if getattr(args, "verbose", False):
                        traceback.print_exc()
                if stats["processed"] % progress_every == 0:
                    print_copy_progress(stats, total, start_time)

    print_copy_progress(stats, total, start_time)
    print(lang_text("Копирование по кластерам завершено.", "Cluster-based copying finished."))
    print(lang_text("Копий в people:", "Copies in people:"), stats["copied_people"])
    print(lang_text("Копий в review:", "Copies in review:"), stats["copied_review"])
    if args.copy_group_photos:
        print(lang_text("Дополнительных копий в review/group_photos:", "Additional copies in review/group_photos:"), stats["copied_group"])
    if stats.get("skipped_duplicates"):
        print(lang_text("Пропущено копий точных дублей по политике scan-one-copy-first:", "Exact duplicate copies skipped by scan-one-copy-first:"), stats["skipped_duplicates"])
    if stats["missing_sources"]:
        print(lang_text("Пропущено отсутствующих исходных файлов:", "Missing source files skipped:"), stats["missing_sources"])
    if stats["copy_errors"]:
        print(lang_text("Ошибок копирования:", "Copy errors:"), stats["copy_errors"], lang_text("— запустите с --verbose для подробностей.", "— run with --verbose for details."))
    print(lang_text("Отчёт назначений:", "Assignments report:"), assignments_path)


def copy_file(src: Path, dst_dir: Path, dry_run: bool = False, args: Any = None) -> Optional[Path]:
    """Copy one file using hardened file_ops logic.

    v32 serializes copy planning per destination folder so parallel copy workers do
    not race when two source files have the same name and target directory.
    """
    lock_key = str(Path(dst_dir).resolve())
    with _COPY_LOCKS_GUARD:
        lock = _COPY_LOCKS.get(lock_key)
        if lock is None:
            lock = threading.Lock()
            _COPY_LOCKS[lock_key] = lock
    with lock:
        result = file_copy_with_collision_handling(src, dst_dir, dry_run=dry_run, max_path_len=240)
        if result.plan is not None and args is not None and result.plan.reason != "unchanged":
            write_filename_map(
                args,
                result.plan.source_path,
                result.plan.target_path,
                result.plan.reason,
                result.plan.original_name,
                result.plan.safe_name,
                result.plan.path_hash,
                extra=result.plan.flags,
            )
        if not result.ok:
            raise OSError(f"{result.reason}: {result.error or 'copy failed'}")
        return result.target_path


def copy_clustered_photos(args: argparse.Namespace, conn: sqlite3.Connection) -> None:
    """Compatibility wrapper for older CLI behavior: assign, then copy.

    v27 exposes assign and copy as independent stages, but keeping this wrapper helps
    external scripts that imported copy_clustered_photos directly.
    """
    assignments_path = assign_photos(args, conn)
    assignments = read_assignments_csv(assignments_path)
    copy_from_assignments(args, assignments, assignments_path)

def cluster_keys(conn: sqlite3.Connection) -> List[str]:
    """Return known person_XXX cluster keys sorted for stable reports."""
    rows = conn.execute(
        "SELECT cluster_key, COUNT(*) AS n FROM faces WHERE cluster_key IS NOT NULL GROUP BY cluster_key ORDER BY cluster_key"
    ).fetchall()
    return [str(r[0]) for r in rows]


def compute_cluster_review_rows(*args: Any, **kwargs: Any) -> Any:
    """Compatibility wrapper moved to reports/review_clusters.py in v44 / Этап 003."""
    try:
        from .reports.review_clusters import compute_cluster_review_rows as _impl
    except ImportError:
        from reports.review_clusters import compute_cluster_review_rows as _impl  # type: ignore
    return _impl(*args, **kwargs)

def generate_names_csv(*args: Any, **kwargs: Any) -> Any:
    """Compatibility wrapper moved to reports/review_clusters.py in v44 / Этап 003."""
    try:
        from .reports.review_clusters import generate_names_csv as _impl
    except ImportError:
        from reports.review_clusters import generate_names_csv as _impl  # type: ignore
    return _impl(*args, **kwargs)

def generate_review_clusters_csv(*args: Any, **kwargs: Any) -> Any:
    """Compatibility wrapper moved to reports/review_clusters.py in v44 / Этап 003."""
    try:
        from .reports.review_clusters import generate_review_clusters_csv as _impl
    except ImportError:
        from reports.review_clusters import generate_review_clusters_csv as _impl  # type: ignore
    return _impl(*args, **kwargs)

def parse_review_confidence(*args: Any, **kwargs: Any) -> Any:
    """Compatibility wrapper moved to reports/review_clusters.py in v44 / Этап 003."""
    try:
        from .reports.review_clusters import parse_review_confidence as _impl
    except ImportError:
        from reports.review_clusters import parse_review_confidence as _impl  # type: ignore
    return _impl(*args, **kwargs)

def normalize_review_action(*args: Any, **kwargs: Any) -> Any:
    """Compatibility wrapper moved to reports/review_clusters.py in v44 / Этап 003."""
    try:
        from .reports.review_clusters import normalize_review_action as _impl
    except ImportError:
        from reports.review_clusters import normalize_review_action as _impl  # type: ignore
    return _impl(*args, **kwargs)

def load_review_decisions(*args: Any, **kwargs: Any) -> Any:
    """Compatibility wrapper moved to reports/review_clusters.py in v44 / Этап 003."""
    try:
        from .reports.review_clusters import load_review_decisions as _impl
    except ImportError:
        from reports.review_clusters import load_review_decisions as _impl  # type: ignore
    return _impl(*args, **kwargs)

def resolve_review_decision(*args: Any, **kwargs: Any) -> Any:
    """Compatibility wrapper moved to reports/review_clusters.py in v44 / Этап 003."""
    try:
        from .reports.review_clusters import resolve_review_decision as _impl
    except ImportError:
        from reports.review_clusters import resolve_review_decision as _impl  # type: ignore
    return _impl(*args, **kwargs)

def write_review_decisions_report(*args: Any, **kwargs: Any) -> Any:
    """Compatibility wrapper moved to reports/review_clusters.py in v44 / Этап 003."""
    try:
        from .reports.review_clusters import write_review_decisions_report as _impl
    except ImportError:
        from reports.review_clusters import write_review_decisions_report as _impl  # type: ignore
    return _impl(*args, **kwargs)


def ensure_review_decisions_for_rows(*args: Any, **kwargs: Any) -> Any:
    """Compatibility wrapper moved to reports/review_clusters.py in v44 / Этап 003."""
    try:
        from .reports.review_clusters import ensure_review_decisions_for_rows as _impl
    except ImportError:
        from reports.review_clusters import ensure_review_decisions_for_rows as _impl  # type: ignore
    return _impl(*args, **kwargs)

def write_names_csv_from_decisions(*args: Any, **kwargs: Any) -> Any:
    """Compatibility wrapper moved to reports/review_clusters.py in v44 / Этап 003."""
    try:
        from .reports.review_clusters import write_names_csv_from_decisions as _impl
    except ImportError:
        from reports.review_clusters import write_names_csv_from_decisions as _impl  # type: ignore
    return _impl(*args, **kwargs)

def print_review_cluster_help(*args: Any, **kwargs: Any) -> Any:
    """Compatibility wrapper moved to reports/review_clusters.py in v44 / Этап 003."""
    try:
        from .reports.review_clusters import print_review_cluster_help as _impl
    except ImportError:
        from reports.review_clusters import print_review_cluster_help as _impl  # type: ignore
    return _impl(*args, **kwargs)

def ask_review_action(*args: Any, **kwargs: Any) -> Any:
    """Compatibility wrapper moved to reports/review_clusters.py in v44 / Этап 003."""
    try:
        from .reports.review_clusters import ask_review_action as _impl
    except ImportError:
        from reports.review_clusters import ask_review_action as _impl  # type: ignore
    return _impl(*args, **kwargs)

def review_clusters_console(*args: Any, **kwargs: Any) -> Any:
    """Compatibility wrapper moved to reports/review_clusters.py in v44 / Этап 003."""
    try:
        from .reports.review_clusters import review_clusters_console as _impl
    except ImportError:
        from reports.review_clusters import review_clusters_console as _impl  # type: ignore
    return _impl(*args, **kwargs)
def generate_summary_csv(*args: Any, **kwargs: Any) -> Any:
    """Compatibility wrapper moved to reports/html_report.py in v44 / Этап 003."""
    try:
        from .reports.html_report import generate_summary_csv as _impl
    except ImportError:
        from reports.html_report import generate_summary_csv as _impl  # type: ignore
    return _impl(*args, **kwargs)

def generate_html_report(*args: Any, **kwargs: Any) -> Any:
    """Compatibility wrapper moved to reports/html_report.py in v44 / Этап 003."""
    try:
        from .reports.html_report import generate_html_report as _impl
    except ImportError:
        from reports.html_report import generate_html_report as _impl  # type: ignore
    return _impl(*args, **kwargs)

def apply_names(*args: Any, **kwargs: Any) -> Any:
    """Compatibility wrapper moved to reports/review_clusters.py in v44 / Этап 003."""
    try:
        from .reports.review_clusters import apply_names as _impl
    except ImportError:
        from reports.review_clusters import apply_names as _impl  # type: ignore
    return _impl(*args, **kwargs)

# -----------------------------------------------------------------------------
# Interactive wizard
# -----------------------------------------------------------------------------
# Этап 003 / v44: the interactive console wizard lives in cli_wizard.py.
# Keep these names re-exported here so legacy CLI, backend imports, and older
# automation scripts that referenced face_sorter_mvp.<wizard_func> keep working.
try:  # package mode
    from .cli_wizard import (
        choose_folder_dialog,
        ask_text,
        print_wrapped,
        ask_bool,
        choose_from_options,
        ask_int_range,
        ask_float_range,
        model_help_text,
        print_model_reference,
        choose_model_and_runtime,
        interactive_gpu_startup_wizard,
        ask_folder,
        make_result_folder_name,
        create_auto_result_dir,
        update_run_state_progress,
        mark_run_stage,
        ask_output_folder,
        profile_title,
        profile_short,
        profile_effect,
        profile_warning,
        show_quality_profile,
        ask_file_timeout_safety_options,
        ask_performance_options,
        ask_preset_sorting_options,
        interactive_args
    )
except ImportError:  # script-folder mode
    from cli_wizard import (  # type: ignore
        choose_folder_dialog,
        ask_text,
        print_wrapped,
        ask_bool,
        choose_from_options,
        ask_int_range,
        ask_float_range,
        model_help_text,
        print_model_reference,
        choose_model_and_runtime,
        interactive_gpu_startup_wizard,
        ask_folder,
        make_result_folder_name,
        create_auto_result_dir,
        update_run_state_progress,
        mark_run_stage,
        ask_output_folder,
        profile_title,
        profile_short,
        profile_effect,
        profile_warning,
        show_quality_profile,
        ask_file_timeout_safety_options,
        ask_performance_options,
        ask_preset_sorting_options,
        interactive_args
    )


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def print_install_hint() -> None:
    """Print quick installation instructions for missing dependencies."""
    print(lang_text(
        """
CPU-режим:
  python -m pip install -r requirements.txt

GPU-режим:
  python -m pip install -r requirements-gpu.txt
  или напрямую:
  python -m pip uninstall -y onnxruntime
  python -m pip install --upgrade onnxruntime-gpu[cuda,cudnn]

Диагностика GPU без сканирования:
  python face_sorter_mvp.py --mode diagnose-gpu

Реальная проверка InsightFace на GPU без сканирования архива:
  python face_sorter_mvp.py --mode diagnose-gpu --gpu-smoke-test-all

Проверить только выбранную модель:
  python face_sorter_mvp.py --mode diagnose-gpu --gpu-smoke-test

Если hdbscan не ставится на Windows:
  используйте --algo dbscan --dbscan-eps 0.55

Модели InsightFace должны называться вроде buffalo_l, buffalo_s, antelopev2.
Если в ошибке появилось models\\1.zip, значит вместо имени модели попало значение "1".
""".strip(),
        """
CPU mode:
  python -m pip install -r requirements.txt

GPU mode:
  python -m pip install -r requirements-gpu.txt
  or directly:
  python -m pip uninstall -y onnxruntime
  python -m pip install --upgrade onnxruntime-gpu[cuda,cudnn]

GPU diagnostics without scanning:
  python face_sorter_mvp.py --mode diagnose-gpu

Real InsightFace GPU check without scanning the archive:
  python face_sorter_mvp.py --mode diagnose-gpu --gpu-smoke-test-all

Check only the selected model:
  python face_sorter_mvp.py --mode diagnose-gpu --gpu-smoke-test

If hdbscan does not install on Windows:
  use --algo dbscan --dbscan-eps 0.55

InsightFace models should be named like buffalo_l, buffalo_s, antelopev2.
If an error mentions models\\1.zip, then "1" was passed instead of a model name.
""".strip(),
    ))

# ---------------------------------------------------------------------------
# CLI parser and application entry point
# ---------------------------------------------------------------------------

def preselect_language_from_argv(argv: Sequence[str]) -> str:
    """Select UI language before argparse builds localized --help text."""
    lang = "auto"
    for idx, item in enumerate(argv):
        if item == "--lang" and idx + 1 < len(argv):
            lang = str(argv[idx + 1])
            break
        if item.startswith("--lang="):
            lang = item.split("=", 1)[1]
            break
    return set_language(lang)

def build_arg_parser() -> argparse.ArgumentParser:
    """Build a localized CLI parser.

    argparse renders --help before parse_args() returns, so main_impl() pre-selects
    LANG from --lang/auto before calling this function. Keep user-facing help text
    bilingual here; low-level third-party errors remain untouched.
    """
    mode_choices = [
        "scan", "cluster", "assign", "copy", "report", "all", "review-clusters",
        "apply-names", "bug-report", "support-bundle", "result-health", "diagnose-gpu", "make-bug-report", "install-hint",
    ]
    p = argparse.ArgumentParser(
        description=lang_text(
            "Локальный сортировщик фото по лицам: InsightFace -> кластеры -> папки.",
            "Local face-clustering photo sorter: InsightFace -> clusters -> folders.",
        ),
        epilog=lang_text(
            "Примеры: python face_sorter_mvp.py --input D:\\Photos --mode all | "
            "python face_sorter_mvp.py --project D:\\Photos\\result --mode review-clusters | "
            "python face_sorter_mvp.py --mode diagnose-gpu --gpu-smoke-test-all | "
            "для диагностики путей: python file_ops.py --self-test",
            "Examples: python face_sorter_mvp.py --input D:\\Photos --mode all | "
            "python face_sorter_mvp.py --project D:\\Photos\\result --mode review-clusters | "
            "python face_sorter_mvp.py --mode diagnose-gpu --gpu-smoke-test-all | "
            "for path diagnostics: python file_ops.py --self-test",
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--lang", choices=["auto", "ru", "en"], default="auto", help=lang_text("Язык интерфейса: auto/ru/en.", "Interface language: auto/ru/en."))
    p.add_argument("--input", required=False, help=lang_text("Папка с исходными фото.", "Folder with source photos."))
    p.add_argument("--output", required=False, help=lang_text("Папка проекта/результата. Если не указана при наличии --input, будет создана result-папка рядом с input.", "Project/result folder. If omitted with --input, a result folder is created next to input."))
    p.add_argument("--project", required=False, help=lang_text("Открыть существующую папку проекта с project.json. Если указан, input/output/db берутся из проекта, если не переопределены явно.", "Open an existing project folder containing project.json. input/output/db are loaded from the project unless explicitly overridden."))
    p.add_argument("--mode", choices=mode_choices, default="all", help=lang_text("Этап запуска: all, scan, cluster, assign, copy, report, review-clusters, apply-names, bug-report/support-bundle, result-health, diagnose-gpu.", "Run stage: all, scan, cluster, assign, copy, report, review-clusters, apply-names, bug-report/support-bundle, result-health, diagnose-gpu."))
    p.add_argument("--db", default=None, help=lang_text("Путь к SQLite. По умолчанию: project/database/faces.sqlite; legacy: project/db/faces.sqlite.", "SQLite path. Default: project/database/faces.sqlite; legacy: project/db/faces.sqlite."))
    p.add_argument("--model", default=DEFAULT_PROFILE["model"], help=lang_text("Модель InsightFace: buffalo_l/buffalo_s/buffalo_m/buffalo_sc/antelopev2. Числа 1..5 преобразуются в варианты списка.", "InsightFace model: buffalo_l/buffalo_s/buffalo_m/buffalo_sc/antelopev2. Numbers 1..5 are mapped to the list options."))
    p.add_argument("--gpu", action="store_true", help=lang_text("Пробовать CUDAExecutionProvider вместо CPU.", "Try CUDAExecutionProvider instead of CPU."))
    p.add_argument("--no-auto-cpu-fallback", action="store_true", help=lang_text("Не откатываться автоматически на CPU, если CUDA недоступна.", "Do not automatically fall back to CPU if CUDA is unavailable."))
    p.add_argument("--det-size", type=int, default=DEFAULT_PROFILE["det_size"], help=lang_text("Размер окна детектора лиц InsightFace.", "InsightFace face-detector window size."))
    p.add_argument("--max-side", type=int, default=DEFAULT_PROFILE["max_side"], help=lang_text("Максимальная сторона изображения перед детекцией. 0 = не уменьшать.", "Maximum image side before detection. 0 = do not downscale."))
    p.add_argument("--upscale-small-to", type=int, default=DEFAULT_PROFILE["upscale_small_to"], help=lang_text("Увеличивать маленькие фото до этой максимальной стороны. 0 = не увеличивать.", "Upscale small photos to this maximum side. 0 = do not upscale."))
    p.add_argument("--rescan", action="store_true", help=lang_text("Пересканировать даже уже кэшированные фото.", "Rescan photos even if cached."))
    p.add_argument("--commit-every", type=int, default=DEFAULT_PROFILE["commit_every"], help=lang_text("Как часто сохранять прогресс в SQLite во время scan.", "How often to commit scan progress to SQLite."))
    p.add_argument("--progress-every", type=int, default=DEFAULT_PROFILE["progress_every"], help=lang_text("Как часто печатать статистику прогресса.", "How often to print progress statistics."))
    p.add_argument("--algo", choices=["hdbscan", "dbscan"], default=DEFAULT_PROFILE["algo"], help=lang_text("Алгоритм кластеризации лиц.", "Face clustering algorithm."))
    p.add_argument("--min-cluster-size", type=int, default=DEFAULT_PROFILE["min_cluster_size"], help=lang_text("Минимальный размер person-кластера.", "Minimum size of a person cluster."))
    p.add_argument("--min-samples", type=int, default=None, help=lang_text("Строгость HDBSCAN/DBSCAN. None = auto.", "HDBSCAN/DBSCAN strictness. None = auto."))
    p.add_argument("--cluster-selection-method", choices=["eom", "leaf"], default=DEFAULT_PROFILE["cluster_selection_method"], help=lang_text("Метод выбора кластеров HDBSCAN: eom стабильнее, leaf даёт больше мелких кластеров.", "HDBSCAN cluster selection: eom is more stable, leaf creates more small clusters."))
    p.add_argument("--dbscan-eps", type=float, default=DEFAULT_PROFILE["dbscan_eps"], help=lang_text("Радиус похожести для DBSCAN.", "Similarity radius for DBSCAN."))
    p.add_argument("--min-det-score", type=float, default=DEFAULT_PROFILE["min_det_score"], help=lang_text("Минимальная уверенность детектора лица.", "Minimum face detector confidence."))
    p.add_argument("--min-face-size", type=int, default=DEFAULT_PROFILE["min_face_size"], help=lang_text("Минимальный размер лица в пикселях после resize/upscale.", "Minimum face size in pixels after resize/upscale."))
    p.add_argument("--photo-assignment", choices=["best-face", "all-faces"], default=DEFAULT_PROFILE["photo_assignment"], help=lang_text("Как назначать фото с несколькими лицами: один лучший кластер или все найденные лица.", "How to assign photos with multiple faces: one best cluster or all found faces."))
    p.add_argument("--copy-group-photos", action="store_true", help=lang_text("Дополнительно копировать групповые фото в review/group_photos.", "Also copy group photos to review/group_photos."))
    p.add_argument("--filename-fallback", action="store_true", help=lang_text("Назначать спорные review-фото по похожему имени файла.", "Assign uncertain review photos by similar filename."))
    p.add_argument("--filename-max-distance", type=int, default=DEFAULT_PROFILE["filename_max_distance"], help=lang_text("Максимальная разница символов для filename fallback.", "Maximum character distance for filename fallback."))
    p.add_argument("--clean-folders", action="store_true", help=lang_text("Очистить people/review перед копированием.", "Clear people/review before copying."))
    p.add_argument("--clean-final", action="store_true", help=lang_text("Очистить final/final_review при apply-names.", "Clear final/final_review during apply-names."))
    p.add_argument("--overwrite-names", action="store_true", help=lang_text("Перезаписать names.csv, если он уже есть.", "Overwrite names.csv if it already exists."))
    p.add_argument("--names", default=None, help=lang_text("Путь к names.csv. По умолчанию: project/names.csv.", "Path to names.csv. Default: project/names.csv."))
    p.add_argument("--report-faces-per-cluster", type=int, default=DEFAULT_PROFILE["report_faces_per_cluster"], help=lang_text("Сколько превью лиц показывать в HTML на кластер.", "How many face previews to show per cluster in HTML."))
    p.add_argument("--dry-run", action="store_true", help=lang_text("Посчитать действия без копирования файлов.", "Compute actions without copying files."))
    p.add_argument("--verbose", action="store_true", help=lang_text("Показывать подробные traceback и диагностические детали.", "Show detailed tracebacks and diagnostic details."))
    p.add_argument("--auto-install", action="store_true", help=lang_text("Автоматически устанавливать отсутствующие зависимости без вопроса.", "Automatically install missing dependencies without asking."))
    p.add_argument("--auto-gpu-install", action="store_true", help=lang_text("Если выбран --gpu и CUDAExecutionProvider не найден, попробовать поставить onnxruntime-gpu[cuda,cudnn].", "If --gpu is selected and CUDAExecutionProvider is missing, try installing onnxruntime-gpu[cuda,cudnn]."))
    p.add_argument("--gpu-smoke-test", action="store_true", help=lang_text("В diagnose-gpu запустить реальный тест выбранной модели InsightFace на CUDA.", "In diagnose-gpu, run a real CUDA smoke-test for the selected InsightFace model."))
    p.add_argument("--gpu-smoke-test-all", action="store_true", help=lang_text("В diagnose-gpu проверить на CUDA все известные model packs.", "In diagnose-gpu, test all known model packs on CUDA."))
    p.add_argument("--skip-gpu-smoke-test", action="store_true", help=lang_text("Не проверять реальный запуск InsightFace на CUDA перед scan. Только для отладки.", "Skip real InsightFace CUDA smoke-test before scan. Debug only."))
    p.add_argument("--force-env-check", action="store_true", help=lang_text("Игнорировать сохранённый env_state и заново проверить GPU/окружение.", "Ignore saved env_state and re-check GPU/environment."))
    p.add_argument("--make-bug-report", action="store_true", help=lang_text("Создать ZIP bug report после завершения или при ошибке.", "Create a ZIP bug report after completion or on error."))
    p.add_argument("--support-bundle", action="store_true", help=lang_text("Создать диагностический support-bundle ZIP и выйти. Эквивалентно --mode support-bundle.", "Create a diagnostic support-bundle ZIP and exit. Equivalent to --mode support-bundle."))
    p.add_argument("--result-health", action="store_true", help=lang_text("Проверить существующую output/result папку и создать reports/result_health_check.*. Эквивалентно --mode result-health.", "Check an existing output/result folder and create reports/result_health_check.*. Equivalent to --mode result-health."))
    p.add_argument("--diagnostics-help", action="store_true", help=lang_text("Показать короткую карту диагностических команд и выйти.", "Show a short diagnostics command map and exit."))
    p.add_argument("--file-timeout", default=DEFAULT_PROFILE.get("file_timeout", "auto"), help=lang_text("Таймаут обработки одного файла: auto, 0/off или число секунд.", "Single-file processing timeout: auto, 0/off, or seconds."))
    p.add_argument("--disable-scan-worker", action="store_true", help=lang_text("Отключить scan worker и таймауты. Только для отладки.", "Disable scan worker and timeouts. Debug only."))
    p.add_argument("--scan-workers", default=DEFAULT_PROFILE.get("scan_workers", "auto"), help=lang_text("Количество worker-процессов для scan: auto или число. GPU auto = 1.", "Number of scan worker processes: auto or number. GPU auto = 1."))
    p.add_argument("--copy-workers", default=DEFAULT_PROFILE.get("copy_workers", "auto"), help=lang_text("Количество потоков копирования: auto или число.", "Number of copy threads: auto or number."))
    p.add_argument("--no-reuse-problem-cache", action="store_true", help=lang_text("Не использовать кэш проблемных файлов.", "Do not reuse the problem-file cache."))
    p.add_argument("--duplicate-check", choices=["off", "exact"], default=DEFAULT_PROFILE.get("duplicate_check", "exact"), help=lang_text("Минимальная проверка дублей: off или exact. exact ищет только побайтные дубли.", "Minimal duplicate check: off or exact. exact finds byte-identical duplicates only."))
    p.add_argument("--duplicate-policy", choices=["scan-one-copy-all", "scan-one-copy-first", "report-only"], default=DEFAULT_PROFILE.get("duplicate_policy", "scan-one-copy-all"), help=lang_text("Политика точных дублей: распознать один и копировать все, копировать только canonical или только отчёт.", "Exact duplicate policy: scan one and copy all, copy canonical only, or report only."))
    p.add_argument("--strict-image-extensions", action="store_true", help=lang_text("Считать ошибкой несовпадение расширения и реального формата файла. По умолчанию такие файлы распознаются по заголовку.", "Treat extension/header mismatches as errors. By default, such files are decoded by header."))
    return p

def apply_cli_defaults(args: argparse.Namespace) -> argparse.Namespace:
    """Fill missing CLI options with safe defaults."""
    args.model = normalize_model_name(args.model)
    args.auto_cpu_fallback = not getattr(args, "no_auto_cpu_fallback", False)
    if not hasattr(args, "scan_profile"):
        args.scan_profile = "normal"
    if not hasattr(args, "scan_workers"):
        args.scan_workers = DEFAULT_PROFILE.get("scan_workers", "auto")
    if not hasattr(args, "copy_workers"):
        args.copy_workers = DEFAULT_PROFILE.get("copy_workers", "auto")
    args.reuse_problem_cache = not bool(getattr(args, "no_reuse_problem_cache", False))
    if not hasattr(args, "duplicate_check"):
        args.duplicate_check = DEFAULT_PROFILE.get("duplicate_check", "exact")
    if not hasattr(args, "duplicate_policy"):
        args.duplicate_policy = DEFAULT_PROFILE.get("duplicate_policy", "scan-one-copy-all")
    if not hasattr(args, "strict_image_extensions"):
        args.strict_image_extensions = DEFAULT_PROFILE.get("strict_image_extensions", False)
    # For CLI, do not force default-profile rescan/clean unless flags are present. But preserve v4 defaults for scan quality.
    # If user runs explicit CLI without --filename-fallback, it stays False; interactive default enables it.
    return args


def apply_project_defaults(args: argparse.Namespace) -> argparse.Namespace:
    """Open an existing project folder and fill missing CLI settings from project.json.

    Explicit CLI arguments win. This lets future UI or console users do:
      python face_sorter_mvp.py --project D:/Photos/result ... --mode report
    without re-entering input/output/db paths.
    """
    project_value = getattr(args, "project", None)
    if not project_value:
        return args
    project_dir = Path(project_value).expanduser().resolve()
    state = load_project_config(project_dir)
    if not state:
        raise SystemExit(lang_text(f"Не найден project.json или legacy .face_sorter_run.json в проекте: {project_dir}", f"No project.json or legacy .face_sorter_run.json found in project: {project_dir}"))

    def missing(name: str) -> bool:
        return not bool(getattr(args, name, None))

    # Always bind output/project to the selected project unless explicitly overridden.
    if missing("output"):
        args.output = str(project_dir)
    args.project = str(project_dir)

    for key in ("input", "db", "names"):
        if missing(key) and state.get(key):
            setattr(args, key, state.get(key))

    # Fill soft settings only when the parser still has its default-like values.
    # This keeps explicit CLI overrides predictable.
    for key in (
        "scan_profile", "model", "det_size", "max_side", "upscale_small_to",
        "min_det_score", "min_face_size", "algo", "min_cluster_size", "min_samples",
        "cluster_selection_method", "dbscan_eps", "photo_assignment",
        "filename_max_distance", "report_faces_per_cluster", "file_timeout",
        "duplicate_check", "duplicate_policy", "scan_workers", "copy_workers",
        "reuse_problem_cache", "progress_every", "commit_every",
    ):
        if hasattr(args, key) and state.get(key) not in (None, ""):
            # argparse cannot tell whether a default was explicitly passed, so keep CLI
            # numeric/default values as-is unless the current value is None.
            if getattr(args, key, None) is None:
                setattr(args, key, state.get(key))

    if state.get("gpu") is True and not getattr(args, "gpu", False):
        args.gpu = True
    return args


def validate_args(args: argparse.Namespace) -> None:
    """Validate argparse namespace before converting to RunConfig."""
    if args.mode in {"install-hint", "diagnose-gpu", "make-bug-report", "bug-report", "support-bundle", "result-health"}:
        return
    if args.mode in {"scan", "cluster", "assign", "copy", "report", "all"} and not args.input:
        raise SystemExit("Для этого режима нужен --input или запустите без параметров для интерактивного режима.")
    if not args.output:
        if args.input:
            args.output = str(create_auto_result_dir(Path(args.input)))
            print(lang_text("--output не указан. Создана output-папка:", "--output was not specified. Created output folder:"), args.output)
        else:
            raise SystemExit("Нужна --output или --input для автосоздания result-папки.")
    if args.input:
        input_dir = Path(args.input)
        if not input_dir.exists() or not input_dir.is_dir():
            raise SystemExit(f"Не найдена input-папка: {input_dir}")
    ensure_dir(Path(args.output))



def table_count(conn: sqlite3.Connection, table: str, where: str = "") -> int:
    """Return row count for a SQLite table, or zero if unavailable."""
    try:
        sql = f"SELECT COUNT(*) FROM {table}"
        if where:
            sql += " WHERE " + where
        return int(conn.execute(sql).fetchone()[0] or 0)
    except Exception:
        return 0


def require_scan_data(conn: sqlite3.Connection) -> None:
    """Raise a friendly error when scan data is missing for a later stage."""
    if table_count(conn, "faces") <= 0:
        raise RuntimeError("Нельзя выполнить этот этап: в SQLite нет найденных лиц/embeddings. Сначала запустите --mode scan или --mode all.")


def require_cluster_data(conn: sqlite3.Connection) -> None:
    """Raise a friendly error when cluster data is missing for assignment/copy."""
    require_scan_data(conn)
    if table_count(conn, "faces", "cluster_key IS NOT NULL") <= 0:
        raise RuntimeError("Нельзя выполнить этот этап: кластеры ещё не созданы. Сначала запустите --mode cluster или --mode all.")


def require_assignments(args: argparse.Namespace) -> Path:
    """Raise a friendly error when assignments.csv is missing for copy."""
    path = assignments_csv_path(args)
    if not path.exists():
        raise RuntimeError(f"Нельзя выполнить copy: не найден {path}. Сначала запустите --mode assign, --mode cluster или --mode all.")
    return path


def run_scan_stage(args: argparse.Namespace, conn: sqlite3.Connection, callbacks: ProgressCallbacks, stages_completed: List[str], output_dir: Path) -> None:
    """Run only the scan stage and record project state."""
    callbacks.on_stage("scan", lang_text("Сканирование фотографий и извлечение лиц", "Scanning photos and extracting faces"))
    scan_photos(args, conn)
    stages_completed.append("scan")
    mark_run_stage(output_dir, "scan", "running", "scan", stages_completed)


def run_cluster_stage(args: argparse.Namespace, conn: sqlite3.Connection, callbacks: ProgressCallbacks, stages_completed: List[str], output_dir: Path) -> None:
    """Run clustering and refresh names/review reports."""
    callbacks.on_stage("cluster", lang_text("Кластеризация лиц", "Clustering faces"))
    require_scan_data(conn)
    cluster_faces(args, conn)
    stages_completed.append("cluster")
    mark_run_stage(output_dir, "cluster", "running", "cluster", stages_completed)


def run_assign_stage(args: argparse.Namespace, conn: sqlite3.Connection, callbacks: ProgressCallbacks, stages_completed: List[str], output_dir: Path) -> None:
    """Run assignment planning without copying files."""
    callbacks.on_stage("assign", lang_text("Назначение целевых папок", "Assigning target folders"))
    require_scan_data(conn)
    clustered_faces = table_count(conn, "faces", "cluster_key IS NOT NULL")
    if clustered_faces <= 0:
        record_module_event(
            args,
            "assign_without_clusters",
            module="assign",
            behavior="write_assignments_to_review_unknown_faces",
        )
        print(lang_text(
            "Кластеры не найдены. Это нормально для очень маленьких наборов или если алгоритм не нашёл устойчивые группы; фото будут помещены в review/unknown_faces.",
            "No clusters were found. This is normal for very small sets or when the algorithm finds no stable groups; photos will be placed in review/unknown_faces.",
        ))
    assign_photos(args, conn)
    stages_completed.append("assign")
    mark_run_stage(output_dir, "assign", "running", "assign", stages_completed)


def run_copy_stage(args: argparse.Namespace, conn: sqlite3.Connection, callbacks: ProgressCallbacks, stages_completed: List[str], output_dir: Path) -> None:
    """Copy files according to assignments.csv."""
    callbacks.on_stage("copy", lang_text("Копирование файлов по assignments.csv", "Copying files from assignments.csv"))
    assignments_path = require_assignments(args)
    assignments = read_assignments_csv(assignments_path)
    copy_from_assignments(args, assignments, assignments_path)
    stages_completed.append("copy")
    mark_run_stage(output_dir, "copy", "running", "copy", stages_completed)


def run_report_stage(args: argparse.Namespace, conn: sqlite3.Connection, callbacks: ProgressCallbacks, stages_completed: List[str], output_dir: Path) -> None:
    """Generate reports without changing recognition data."""
    callbacks.on_stage("report", lang_text("Создание CSV/HTML-отчётов", "Generating CSV/HTML reports"))
    # Reports can be regenerated even for an empty DB, but a missing DB/table will surface as a clear SQL error.
    generate_names_csv(args, conn)
    generate_review_clusters_csv(args, conn)
    generate_summary_csv(args, conn)
    generate_html_report(args, conn)
    stages_completed.append("report")
    mark_run_stage(output_dir, "report", "running", "report", stages_completed)


def run_review_clusters_stage(args: argparse.Namespace, conn: sqlite3.Connection, callbacks: ProgressCallbacks, stages_completed: List[str], output_dir: Path) -> None:
    """Run the console review assistant for names.csv decisions."""
    callbacks.on_stage("review_clusters", lang_text("Консольная проверка кластеров", "Console cluster review"))
    require_cluster_data(conn)
    review_clusters_console(args, conn)
    stages_completed.append("review_clusters")
    mark_run_stage(output_dir, "review_clusters", "running", "review_clusters", stages_completed)


def run_apply_names_stage(args: argparse.Namespace, conn: sqlite3.Connection, callbacks: ProgressCallbacks, stages_completed: List[str], output_dir: Path) -> None:
    """Apply names.csv decisions into final named folders."""
    callbacks.on_stage("apply_names", lang_text("Создание финальных папок по names.csv", "Creating final folders from names.csv"))
    apply_names(args, conn)
    stages_completed.append("apply_names")
    mark_run_stage(output_dir, "apply_names", "running", "apply_names", stages_completed)


def run_pipeline(config: RunConfig, callbacks: Optional[ProgressCallbacks] = None) -> RunResult:
    """Compatibility wrapper for the pipeline now owned by core.pipeline.

    Этап 024 / v65.4 keeps orchestration to ``face_sorter_mvp.core.pipeline``.
    Keep this symbol for legacy imports and ``python face_sorter_mvp.py``.
    """
    try:  # package mode
        from .core.pipeline import run_pipeline as core_run_pipeline
    except ImportError:  # script-folder mode
        from core.pipeline import run_pipeline as core_run_pipeline  # type: ignore
    return core_run_pipeline(config, callbacks)

def main_impl(argv: Optional[Sequence[str]] = None) -> int:
    """Main application implementation with logging and bug-report safeguards."""
    if argv is None:
        argv = sys.argv[1:]

    preselect_language_from_argv(argv)
    if not argv:
        raw_args = interactive_args()
    else:
        parser = build_arg_parser()
        raw_args = apply_cli_defaults(parser.parse_args(argv))
        raw_args = apply_project_defaults(raw_args)
        set_language(getattr(raw_args, "lang", "auto"))
        if bool(getattr(raw_args, "support_bundle", False)):
            raw_args.mode = "support-bundle"
        if bool(getattr(raw_args, "result_health", False)):
            raw_args.mode = "result-health"

    global CURRENT_ARGS, CURRENT_CONFIG
    CURRENT_ARGS = raw_args

    if bool(getattr(raw_args, "diagnostics_help", False)):
        try:
            from .core.diagnostics_help import diagnostics_help_text
        except ImportError:
            from core.diagnostics_help import diagnostics_help_text  # type: ignore
        print(diagnostics_help_text(getattr(raw_args, "lang", "auto")))
        return 0

    if getattr(raw_args, "mode", None) == "install-hint":
        print_install_hint()
        return 0
    if getattr(raw_args, "mode", None) in {"make-bug-report", "bug-report", "support-bundle"}:
        validate_args(raw_args)
        config = run_config_from_namespace(raw_args)
        CURRENT_CONFIG = config
        CURRENT_ARGS = config.to_namespace()
        create_bug_report(CURRENT_ARGS)
        return 0
    if getattr(raw_args, "mode", None) == "result-health":
        validate_args(raw_args)
        if not getattr(raw_args, "output", None):
            raise SystemExit(lang_text("Для result-health нужен --output с папкой результата.", "result-health requires --output with the result folder."))
        try:
            from .core.result_health import build_result_health_summary, format_result_health_text
        except ImportError:
            from core.result_health import build_result_health_summary, format_result_health_text  # type: ignore
        summary = build_result_health_summary(raw_args.output, write_reports=True)
        print(format_result_health_text(summary, language=getattr(raw_args, "lang", "auto")))
        return 0 if summary.ok else 2
    if getattr(raw_args, "mode", None) == "diagnose-gpu":
        info = diagnose_gpu_environment(verbose=True)
        run_all = bool(getattr(raw_args, "gpu_smoke_test_all", False))
        run_smoke = bool(getattr(raw_args, "gpu_smoke_test", False))
        if not (run_all or run_smoke) and is_interactive_terminal() and "CUDAExecutionProvider" in info.get("providers", []):
            run_all = ask_bool(
                "Проверить все модели InsightFace на GPU?",
                True,
                "Рекомендуется: будет понятно, какие model packs реально работают на CUDA. Может скачать отсутствующие модели."
            )
            if not run_all:
                run_smoke = ask_bool(
                    "Проверить только выбранную модель на GPU?",
                    True,
                    "Создаст пустое тестовое изображение и проверит, падает ли cuDNN при реальной свёртке."
                )
        if run_all:
            results = gpu_all_models_smoke_test(getattr(raw_args, "det_size", 640), verbose=True)
            ok_models = allowed_gpu_models_from_smoke_results(results) or []
            save_gpu_cache(True, providers=info.get("providers", []), smoke_results=results, det_size=getattr(raw_args, "det_size", 640))
            if ok_models:
                print("\nИтог: GPU реально готов для моделей:", ", ".join(ok_models))
            else:
                print("\nИтог: ни одна модель не прошла реальный GPU smoke-test. Для сортировки лучше использовать CPU или чинить CUDA/cuDNN/model packs.")
        elif run_smoke:
            ok = gpu_real_inference_smoke_test(getattr(raw_args, "model", DEFAULT_MODEL), getattr(raw_args, "det_size", 640), verbose=True)
            if not ok:
                print("\nИтог smoke-test: GPU виден, но реальный запуск выбранной модели на CUDA не прошёл. Для сортировки лучше использовать CPU или другую модель.")
            else:
                print("\nИтог smoke-test: выбранная модель реально готова к запуску InsightFace на GPU.")
        return 0

    validate_args(raw_args)  # keeps old CLI behavior such as auto result folder creation
    config = run_config_from_namespace(raw_args)
    CURRENT_CONFIG = config
    run_pipeline(config, ConsoleProgressCallbacks())
    return 0

def main(argv: Optional[Sequence[str]] = None) -> int:
    """Small entry wrapper that returns a process exit code.

    Keep --help output clean: argparse help should not be preceded by the log
    header. Normal runs still tee stdout/stderr to face_sorter_mvp.log.
    """
    argv_for_check = list(sys.argv[1:] if argv is None else argv)
    quiet_help_flags = {"-h", "--help", "--diagnostics-help"}
    if not any(item in quiet_help_flags for item in argv_for_check):
        setup_app_logging()
    try:
        return main_impl(argv)
    except KeyboardInterrupt as exc:
        print("\n" + lang_text("Работа прервана пользователем.", "Interrupted by user."))
        if CURRENT_ARGS is not None and getattr(CURRENT_ARGS, "output", None):
            write_run_state(Path(CURRENT_ARGS.output).resolve(), CURRENT_ARGS, "interrupted", "KeyboardInterrupt")
            create_bug_report(CURRENT_ARGS, exc)
        return 130
    except SystemExit:
        raise
    except Exception as exc:
        print("\n" + lang_text("Произошла ошибка. Создаю bug report рядом со скриптом.", "An error occurred. Creating a bug report next to the script."))
        traceback.print_exc()
        if CURRENT_ARGS is not None and getattr(CURRENT_ARGS, "output", None):
            write_run_state(Path(CURRENT_ARGS.output).resolve(), CURRENT_ARGS, "error", str(exc))
        create_bug_report(CURRENT_ARGS, exc)
        return 1


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
