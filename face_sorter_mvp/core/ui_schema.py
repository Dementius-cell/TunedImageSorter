# -*- coding: utf-8 -*-
"""Import-safe UI parameter/schema contract for future Windows/PySide6 forms.

v69.6 / Этап 055 keeps the machine-readable description of the public run form.
The schema is intentionally separate from the console wizard: a UI can render
sections, fields, defaults and allowed values without importing CLI prompts and
without starting InsightFace/ONNX/scan/cluster/copy.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .config import RunConfig, stages_for_mode
from .constants import (
    DEFAULT_MODEL,
    DEFAULT_PROFILE,
    KNOWN_MODELS,
    MODE_STAGE_MAP,
    PIPELINE_STAGES,
    SCRIPT_VERSION,
)

UI_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class UiFieldOption:
    """One selectable option for a UI field."""

    value: Any
    label: str
    description: str = ""
    warning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class UiParameterSpec:
    """Machine-readable description of one RunConfig/UI field."""

    name: str
    label: str
    kind: str
    default: Any = None
    description: str = ""
    section: str = "general"
    required: bool = False
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    step: Optional[float] = None
    options: Tuple[UiFieldOption, ...] = ()
    advanced: bool = False
    cli_name: str = ""
    config_name: str = ""
    notes: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["options"] = [option.to_dict() for option in self.options]
        return data


@dataclass(frozen=True)
class UiFormSection:
    """Logical group of UI parameters for rendering a settings form."""

    key: str
    title: str
    description: str = ""
    fields: Tuple[str, ...] = ()
    advanced: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class UiRunConfigSchema:
    """Versioned form schema for RunConfig-like UI screens."""

    version: str
    refactor_stage: str
    schema_version: int
    ui_api_version: int
    sections: Tuple[UiFormSection, ...]
    parameters: Tuple[UiParameterSpec, ...]
    default_profile: str
    default_mode: str
    notes: Tuple[str, ...] = ()

    def parameter_map(self) -> Dict[str, UiParameterSpec]:
        return {parameter.name: parameter for parameter in self.parameters}

    def section_map(self) -> Dict[str, UiFormSection]:
        return {section.key: section for section in self.sections}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "refactor_stage": self.refactor_stage,
            "schema_version": self.schema_version,
            "ui_api_version": self.ui_api_version,
            "sections": [section.to_dict() for section in self.sections],
            "parameters": [parameter.to_dict() for parameter in self.parameters],
            "default_profile": self.default_profile,
            "default_mode": self.default_mode,
            "notes": list(self.notes),
        }


def _legacy_core() -> Any:
    """Load legacy metadata lazily; does not start ML processing."""
    try:
        from .. import face_sorter_mvp as legacy
    except ImportError:  # script-folder mode
        import face_sorter_mvp as legacy  # type: ignore
    return legacy


def _options(values: Iterable[Any], *, labels: Optional[Dict[Any, str]] = None, descriptions: Optional[Dict[Any, str]] = None) -> Tuple[UiFieldOption, ...]:
    labels = labels or {}
    descriptions = descriptions or {}
    return tuple(UiFieldOption(value=value, label=str(labels.get(value, value)), description=str(descriptions.get(value, ""))) for value in values)


def _is_ru_language(language: Any = "auto") -> bool:
    text = str(language or "auto").strip().lower()
    return text == "auto" or text.startswith("ru") or text in {"russian", "русский"}


def _lt(language: Any, ru: str, en: str) -> str:
    return ru if _is_ru_language(language) else en


_PROFILE_LABELS: Dict[str, Dict[str, str]] = {
    "minimum": {"ru": "минимальное качество", "en": "minimum quality"},
    "normal": {"ru": "нормальное качество", "en": "normal quality"},
    "high": {"ru": "высокое качество", "en": "high quality"},
    "maximum": {"ru": "максимальное качество", "en": "maximum quality"},
    "recognition_max": {"ru": "максимум распознавания", "en": "maximum recognition"},
}

_PROFILE_DESCRIPTIONS: Dict[str, Dict[str, str]] = {
    "minimum": {"ru": "Быстро, грубо: минимальная нагрузка на CPU/GPU и память, но чаще пропускает мелкие/сложные лица.", "en": "Fast and rough: minimal CPU/GPU and memory load, but more small/difficult faces may be missed."},
    "normal": {"ru": "Лучший старт для большинства архивов: сбалансированные настройки и best-face без размножения фото по папкам.", "en": "Best starting point for most archives: balanced settings and best-face assignment without duplicating photos across folders."},
    "high": {"ru": "Медленнее normal, но повышает шанс найти слабые/маленькие лица; возможен дополнительный мусор в review.", "en": "Slower than normal, but improves the chance of finding weak/small faces; may add extra review items."},
    "maximum": {"ru": "Тяжёлый готовый пресет для сложных архивов; выше время, память и риск ложных лиц.", "en": "Heavy preset for difficult archives; increases runtime, memory use and false-positive risk."},
    "recognition_max": {"ru": "Экстремальный профиль для экспериментов; может быть очень медленным и упереться в VRAM/RAM.", "en": "Extreme experimental profile; may be very slow and can hit VRAM/RAM limits."},
}

_PROFILE_WARNINGS: Dict[str, Dict[str, str]] = {
    "recognition_max": {"ru": "Внимание: профиль может быть очень медленным и может упереться в VRAM/RAM.", "en": "Warning: this profile can be very slow and may hit VRAM/RAM limits."},
}


def _profile_options(language: Any = "auto") -> Tuple[UiFieldOption, ...]:
    profiles = getattr(_legacy_core(), "QUALITY_PROFILES", {})
    lang = "ru" if _is_ru_language(language) else "en"
    result: List[UiFieldOption] = []
    for key, payload in profiles.items():
        key_text = str(key)
        labels = _PROFILE_LABELS.get(key_text, {})
        descriptions = _PROFILE_DESCRIPTIONS.get(key_text, {})
        warnings = _PROFILE_WARNINGS.get(key_text, {})
        result.append(UiFieldOption(
            value=key_text,
            label=labels.get(lang) or str(payload.get("title", key_text)),
            description=descriptions.get(lang) or str(payload.get("effect") or payload.get("short") or ""),
            warning=warnings.get(lang) or str(payload.get("warning") or ""),
        ))
    return tuple(result)

def _model_options() -> Tuple[UiFieldOption, ...]:
    legacy = _legacy_core()
    registry = getattr(legacy, "MODEL_REGISTRY", {})
    result: List[UiFieldOption] = []
    for model in KNOWN_MODELS:
        info = registry.get(model, {}).get("info", {}) if isinstance(registry, dict) else {}
        description = str(info.get("description") or "")
        warning = "experimental" if info.get("experimental") else ""
        result.append(UiFieldOption(value=model, label=model, description=description, warning=warning))
    return tuple(result)


def _model_schema_defaults(model_name: str) -> Dict[str, Dict[str, Any]]:
    try:
        return dict(_legacy_core().model_param_schema(model_name))
    except Exception:
        return {}


def _param_default(name: str, fallback: Any = None) -> Any:
    if name in DEFAULT_PROFILE:
        return DEFAULT_PROFILE[name]
    try:
        return getattr(RunConfig, name)
    except Exception:
        return fallback


def get_ui_form_sections(language: Any = "auto") -> Tuple[UiFormSection, ...]:
    """Return stable localized UI form sections."""
    t = lambda ru, en: _lt(language, ru, en)
    return (
        UiFormSection("paths", t("Папки", "Folders"), t("Input/output/result project folders.", "Input/output/result project folders."), ("input_dir", "output_dir", "resume_existing_output")),
        UiFormSection("preset", t("Профиль и режим", "Profile and mode"), t("Профиль качества, режим pipeline и язык.", "High-level preset, pipeline mode and language."), ("profile", "mode", "language")),
        UiFormSection("runtime", t("Модель и ускорение", "Model and acceleration"), t("Модель распознавания, выбор GPU/CPU и fallback.", "Recognition model, GPU/CPU choice and fallback behavior."), ("model", "use_gpu", "auto_cpu_fallback", "skip_gpu_smoke_test")),
        UiFormSection("recognition", t("Распознавание", "Recognition"), t("Detector size, resize/upscale и пороги лиц.", "Detector size, resize/upscale and face thresholds."), ("det_size", "max_side", "upscale_small_to", "min_det_score", "min_face_size"), advanced=True),
        UiFormSection("clustering", t("Кластеризация", "Clustering"), t("Алгоритм группировки и пороги кластеров.", "Clustering algorithm and grouping thresholds."), ("algorithm", "min_cluster_size", "min_samples", "cluster_selection_method", "dbscan_eps"), advanced=True),
        UiFormSection("copying", t("Копирование", "Copying"), t("Назначение фото и поведение output-папок.", "Photo assignment and output folder behavior."), ("photo_assignment", "copy_group_photos", "clean_folders", "clean_final", "overwrite_names")),
        UiFormSection("performance", t("Производительность", "Performance"), t("Workers, timeout и cache-настройки.", "Worker, timeout and cache settings."), ("scan_workers", "copy_workers", "file_timeout", "reuse_problem_cache", "duplicate_check", "duplicate_policy"), advanced=True),
        UiFormSection("reports", t("Отчёты", "Reports"), t("Настройки отчётов и review.", "Report and review settings."), ("report_faces_per_cluster", "make_bug_report", "strict_image_extensions"), advanced=True),
    )

def get_ui_parameter_schema(*, profile: str = "normal", model: Optional[str] = None, language: Any = "auto") -> Tuple[UiParameterSpec, ...]:
    """Return machine-readable specs for public RunConfig fields.

    ``profile`` and ``model`` are used only to expose sensible defaults and
    model-specific min/max values for fields such as ``det_size``.
    """
    legacy = _legacy_core()
    t = lambda ru, en: _lt(language, ru, en)
    profiles = getattr(legacy, "QUALITY_PROFILES", {})
    profile_settings = dict(profiles.get(profile, profiles.get("normal", {})).get("settings", {})) if isinstance(profiles, dict) else {}
    selected_model = str(model or profile_settings.get("model") or DEFAULT_MODEL)
    model_params = _model_schema_defaults(selected_model)

    def default(name: str, fallback: Any = None) -> Any:
        if name in profile_settings:
            return profile_settings[name]
        return _param_default(name, fallback)

    def model_min(name: str, fallback: Optional[float] = None) -> Optional[float]:
        value = model_params.get(name, {}).get("min", fallback)
        return float(value) if value is not None else None

    def model_max(name: str, fallback: Optional[float] = None) -> Optional[float]:
        value = model_params.get(name, {}).get("max", fallback)
        return float(value) if value is not None else None

    return (
        UiParameterSpec("input_dir", t("Input-папка", "Input folder"), "path", None, t("Папка с исходными фотографиями.", "Folder with source photos."), "paths", True, config_name="input_dir"),
        UiParameterSpec("output_dir", t("Output/result папка", "Output/result folder"), "path", None, t("Result/project папка. UI может использовать Auto/suggest_output_dir().", "Result/project folder. UI may use Auto/suggest_output_dir()."), "paths", False, config_name="output_dir"),
        UiParameterSpec("resume_existing_output", t("Продолжить существующий result", "Resume existing result"), "bool", False, t("Продолжить незавершённую result-папку, если включено.", "Continue an unfinished result folder when selected."), "paths", config_name="resume_existing_output"),
        UiParameterSpec("profile", t("Профиль качества", "Quality profile"), "choice", profile, t("Готовый пресет, который заполняет значения по умолчанию.", "High-level preset used to fill defaults."), "preset", False, options=_profile_options(language), cli_name="--scan-profile", config_name="profile"),
        UiParameterSpec("mode", t("Режим pipeline", "Pipeline mode"), "choice", default("mode", "all"), t("Какие этапы pipeline выполнить.", "Which pipeline stages to execute."), "preset", False, options=_options(MODE_STAGE_MAP.keys(), descriptions={key: ", ".join(stages_for_mode(key)) for key in MODE_STAGE_MAP}), cli_name="--mode", config_name="mode"),
        UiParameterSpec("language", t("Язык", "Language"), "choice", "auto", t("Предпочтение языка UI/CLI.", "UI/CLI language preference."), "preset", options=_options(("auto", "ru", "en"), labels={"auto": t("Авто", "Auto"), "ru": t("Русский", "Russian"), "en": t("English", "English")}), cli_name="--lang", config_name="language"),
        UiParameterSpec("model", t("Модель распознавания", "Recognition model"), "choice", selected_model, "InsightFace model name.", "runtime", False, options=_model_options(), cli_name="--model", config_name="model"),
        UiParameterSpec("use_gpu", t("Использовать GPU", "Use GPU"), "bool", bool(default("gpu", False)), t("Использовать CUDAExecutionProvider, если он доступен.", "Use CUDAExecutionProvider when available."), "runtime", cli_name="--gpu", config_name="use_gpu"),
        UiParameterSpec("auto_cpu_fallback", t("Авто fallback на CPU", "Auto CPU fallback"), "bool", True, t("Откатиться на CPU, если GPU startup/smoke-test не прошёл.", "Fallback to CPU if GPU startup/smoke-test fails."), "runtime", config_name="auto_cpu_fallback"),
        UiParameterSpec("skip_gpu_smoke_test", t("Пропустить GPU smoke-test", "Skip GPU smoke-test"), "bool", False, t("Advanced: не проверять старт GPU-модели перед запуском.", "Advanced: do not validate GPU model startup before run."), "runtime", advanced=True, cli_name="--skip-gpu-smoke-test", config_name="skip_gpu_smoke_test"),
        UiParameterSpec("det_size", t("Размер detector", "Detector size"), "int", default("det_size", 640), t("Входной размер face detector.", "Face detector input size."), "recognition", False, model_min("det_size", 160), model_max("det_size", 4096), 64, cli_name="--det-size", config_name="det_size"),
        UiParameterSpec("max_side", t("Максимальная сторона фото", "Max image side"), "int", default("max_side", 1800), t("0 означает не уменьшать большие фото.", "0 means do not downscale large photos."), "recognition", False, 0, 20000, 100, cli_name="--max-side", config_name="max_side"),
        UiParameterSpec("upscale_small_to", t("Увеличивать маленькие фото до", "Upscale small images to"), "int", default("upscale_small_to", 640), t("0 означает не увеличивать маленькие фото.", "0 means do not upscale small photos."), "recognition", False, 0, 4096, 64, cli_name="--upscale-small-to", config_name="upscale_small_to"),
        UiParameterSpec("min_det_score", t("Минимальный detector score", "Minimum detector score"), "float", default("min_det_score", 0.30), t("Ниже — больше слабых лиц, но больше ложных срабатываний.", "Lower finds more weak faces but may add false positives."), "recognition", False, model_min("min_det_score", 0.01), model_max("min_det_score", 0.99), 0.01, cli_name="--min-det-score", config_name="min_det_score"),
        UiParameterSpec("min_face_size", t("Минимальный размер лица", "Minimum face size"), "int", default("min_face_size", 12), t("Минимальный размер найденного лица после resize/upscale.", "Minimum detected face size after resize/upscale."), "recognition", False, model_min("min_face_size", 1), model_max("min_face_size", 1000), 1, cli_name="--min-face-size", config_name="min_face_size"),
        UiParameterSpec("algorithm", t("Алгоритм кластеризации", "Clustering algorithm"), "choice", default("algo", "hdbscan"), t("Алгоритм группировки embeddings.", "Algorithm for grouping embeddings."), "clustering", False, options=_options(("hdbscan", "dbscan")), cli_name="--algo", config_name="algorithm"),
        UiParameterSpec("min_cluster_size", t("Минимальный размер кластера", "Minimum cluster size"), "int", default("min_cluster_size", 5), t("Минимальный размер person-группы для HDBSCAN.", "Minimum person-group size for HDBSCAN."), "clustering", False, 2, 1000, 1, cli_name="--min-cluster-size", config_name="min_cluster_size"),
        UiParameterSpec("min_samples", t("Minimum samples", "Minimum samples"), "int_or_none", default("min_samples", None), t("None позволяет HDBSCAN выбрать значение из min_cluster_size.", "None lets HDBSCAN choose from min_cluster_size."), "clustering", False, 1, 1000, 1, cli_name="--min-samples", config_name="min_samples", advanced=True),
        UiParameterSpec("cluster_selection_method", "Cluster selection", "choice", default("cluster_selection_method", "eom"), "HDBSCAN cluster selection strategy.", "clustering", False, options=_options(("eom", "leaf")), cli_name="--cluster-selection-method", config_name="cluster_selection_method", advanced=True),
        UiParameterSpec("dbscan_eps", "DBSCAN eps", "float", default("dbscan_eps", 0.55), "Distance threshold for DBSCAN mode.", "clustering", False, 0.01, 2.0, 0.01, cli_name="--dbscan-eps", config_name="dbscan_eps", advanced=True),
        UiParameterSpec("photo_assignment", t("Назначение фото", "Photo assignment"), "choice", default("photo_assignment", "best-face"), t("Как назначать групповые фото с несколькими лицами.", "How to assign group photos with several faces."), "copying", False, options=_options(("best-face", "all-faces")), cli_name="--photo-assignment", config_name="photo_assignment"),
        UiParameterSpec("copy_group_photos", t("Копировать групповые фото", "Copy group photos"), "bool", bool(default("copy_group_photos", False)), t("Также копировать multi-face фото в group/review outputs, если включено.", "Also copy multi-face photos to group/review outputs when enabled."), "copying", config_name="copy_group_photos"),
        UiParameterSpec("clean_folders", t("Очищать people/review folders", "Clean people/review folders"), "bool", bool(default("clean_folders", True)), t("Очищать сгенерированные output-папки перед копированием.", "Clean generated output folders before copying."), "copying", config_name="clean_folders"),
        UiParameterSpec("clean_final", t("Очищать final folder", "Clean final folder"), "bool", bool(default("clean_final", False)), t("Очищать final/named output перед apply-names.", "Clean final/named output before apply-names."), "copying", config_name="clean_final", advanced=True),
        UiParameterSpec("overwrite_names", t("Перезаписать names.csv", "Overwrite names.csv"), "bool", bool(default("overwrite_names", False)), t("Перезаписать существующие names.csv/review decisions.", "Overwrite existing names.csv/review decisions."), "copying", config_name="overwrite_names", advanced=True),
        UiParameterSpec("scan_workers", t("Scan workers", "Scan workers"), "string", str(default("scan_workers", "auto")), t("auto или положительное число. GPU обычно использует 1 worker.", "auto or a positive integer. GPU usually uses 1 worker."), "performance", config_name="scan_workers", advanced=True),
        UiParameterSpec("copy_workers", t("Copy workers", "Copy workers"), "string", str(default("copy_workers", "auto")), t("auto или положительное число для потоков копирования файлов.", "auto or a positive integer for file copy threads."), "performance", config_name="copy_workers", advanced=True),
        UiParameterSpec("file_timeout", t("Timeout файла", "File timeout"), "string", str(default("file_timeout", "auto")), t("auto или секунды на один image file.", "auto or seconds per image file."), "performance", config_name="file_timeout", advanced=True),
        UiParameterSpec("reuse_problem_cache", t("Использовать cache проблемных файлов", "Reuse problem-file cache"), "bool", bool(default("reuse_problem_cache", True)), t("Пропускать уже известные проблемные файлы при resume/rescan.", "Skip files already known as problematic during resume/rescan."), "performance", config_name="reuse_problem_cache", advanced=True),
        UiParameterSpec("duplicate_check", t("Проверка дублей", "Duplicate check"), "choice", default("duplicate_check", "exact"), t("Режим поиска дублей перед сканированием лиц.", "Duplicate detection mode before face scanning."), "performance", options=_options(("off", "exact")), config_name="duplicate_check", advanced=True),
        UiParameterSpec("duplicate_policy", t("Политика дублей", "Duplicate policy"), "choice", default("duplicate_policy", "scan-one-copy-all"), t("Как сканируются/копируются точные дубли.", "How exact duplicates are scanned/copied."), "performance", options=_options(("scan-one-copy-all", "scan-all")), config_name="duplicate_policy", advanced=True),
        UiParameterSpec("report_faces_per_cluster", t("Лиц в отчёте на кластер", "Report faces per cluster"), "int", default("report_faces_per_cluster", 36), t("Максимум face thumbnails на кластер в HTML/report outputs.", "Maximum face thumbnails per cluster in HTML/report outputs."), "reports", False, 1, 1000, 1, config_name="report_faces_per_cluster"),
        UiParameterSpec("make_bug_report", t("Создать bug-report", "Create bug-report"), "bool", False, t("Создать bug-report zip после запуска/ошибки.", "Create bug-report zip after run/error."), "reports", config_name="make_bug_report"),
        UiParameterSpec("strict_image_extensions", t("Строгие расширения изображений", "Strict image extensions"), "bool", bool(default("strict_image_extensions", False)), t("Отклонять valid images при несовпадении extension/header.", "Reject valid images when extension/header mismatch is detected."), "reports", config_name="strict_image_extensions", advanced=True),
    )


def get_ui_run_config_schema(*, profile: str = "normal", model: Optional[str] = None, language: Any = "auto") -> UiRunConfigSchema:
    """Return the full UI form schema."""
    return UiRunConfigSchema(
        version=SCRIPT_VERSION,
        refactor_stage="Этап 055",
        schema_version=UI_SCHEMA_VERSION,
        ui_api_version=21,
        sections=get_ui_form_sections(language),
        parameters=get_ui_parameter_schema(profile=profile, model=model, language=language),
        default_profile="normal",
        default_mode="all",
        notes=(
            "This schema is for UI rendering and validation hints; run_pipeline remains the source of execution behavior.",
            "CLI wizard text/prompts are deliberately not imported by this module.",
            "Advanced fields should be hidden by default in a first Windows UI.",
        ),
    )


def get_ui_run_config_schema_dict(*, profile: str = "normal", model: Optional[str] = None, language: Any = "auto") -> Dict[str, Any]:
    """Return the full UI schema as plain JSON-serializable dictionaries."""
    return get_ui_run_config_schema(profile=profile, model=model, language=language).to_dict()


def profile_settings_diff(profile: str, *, base_profile: str = "normal") -> Dict[str, Dict[str, Any]]:
    """Return changed settings for one profile compared with another profile.

    Useful for UI tooltips such as "high quality changes these values".
    """
    profiles = getattr(_legacy_core(), "QUALITY_PROFILES", {})
    selected = dict(profiles.get(profile, profiles.get("normal", {})).get("settings", {})) if isinstance(profiles, dict) else {}
    base = dict(profiles.get(base_profile, profiles.get("normal", {})).get("settings", {})) if isinstance(profiles, dict) else {}
    keys = sorted(set(selected.keys()).union(base.keys()))
    result: Dict[str, Dict[str, Any]] = {}
    for key in keys:
        old = base.get(key)
        new = selected.get(key)
        if old != new:
            result[key] = {"base": old, "value": new}
    return result


def run_config_to_ui_values(config: RunConfig) -> Dict[str, Any]:
    """Flatten RunConfig to a dict keyed by UI schema field names."""
    data: Dict[str, Any] = {}
    field_names = {item.name for item in fields(RunConfig)}
    for spec in get_ui_parameter_schema(profile=config.profile, model=config.model):
        name = spec.config_name or spec.name
        if name in field_names:
            value = getattr(config, name)
            if isinstance(value, Path):
                value = str(value)
            data[spec.name] = value
    return data


def ui_values_to_overrides(values: Dict[str, Any]) -> Dict[str, Any]:
    """Convert UI field names to create_run_config() override keys.

    The resulting dict is intended for ``create_run_config(..., overrides=...)``.
    Top-level fields such as input/output/profile/mode are intentionally omitted
    because create_run_config() already accepts them explicitly.
    """
    schema = get_ui_run_config_schema()
    param_map = schema.parameter_map()
    skip = {"input_dir", "output_dir", "profile", "mode", "language", "use_gpu", "auto_cpu_fallback", "resume_existing_output", "make_bug_report"}
    overrides: Dict[str, Any] = {}
    for ui_name, value in values.items():
        if ui_name in skip or ui_name not in param_map:
            continue
        config_name = param_map[ui_name].config_name or ui_name
        overrides[config_name] = value
    return overrides


def validate_ui_values_against_schema(values: Dict[str, Any], *, profile: str = "normal", model: Optional[str] = None) -> Tuple[str, ...]:
    """Lightweight UI-value validation independent from filesystem checks."""
    errors: List[str] = []
    for spec in get_ui_parameter_schema(profile=profile, model=model):
        if spec.name not in values:
            if spec.required:
                errors.append(f"Missing required field: {spec.name}")
            continue
        value = values.get(spec.name)
        if value in (None, ""):
            if spec.required:
                errors.append(f"Empty required field: {spec.name}")
            continue
        if spec.options:
            allowed = {option.value for option in spec.options}
            if value not in allowed:
                errors.append(f"Unsupported value for {spec.name}: {value!r}")
        if spec.kind in {"int", "float", "int_or_none"} and value is not None:
            try:
                number = float(value)
            except Exception:
                errors.append(f"Invalid numeric value for {spec.name}: {value!r}")
                continue
            if spec.minimum is not None and number < spec.minimum:
                errors.append(f"Value for {spec.name} is below minimum {spec.minimum}: {value!r}")
            if spec.maximum is not None and number > spec.maximum:
                errors.append(f"Value for {spec.name} is above maximum {spec.maximum}: {value!r}")
    return tuple(errors)


__all__ = [
    "UI_SCHEMA_VERSION",
    "UiFieldOption",
    "UiParameterSpec",
    "UiFormSection",
    "UiRunConfigSchema",
    "get_ui_form_sections",
    "get_ui_parameter_schema",
    "get_ui_run_config_schema",
    "get_ui_run_config_schema_dict",
    "profile_settings_diff",
    "run_config_to_ui_values",
    "ui_values_to_overrides",
    "validate_ui_values_against_schema",
]
