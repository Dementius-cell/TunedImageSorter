# -*- coding: utf-8 -*-
"""Structured UI status/error helpers for future Windows/PySide6 integration.

v69.6 / Этап 055 keeps this import-safe layer so UI code can display backend,
preflight, self-test and job problems with short human-readable explanations
and recommended actions, without parsing tracebacks or raw JSON structures.  The helpers here do not import ML/image runtimes and do
not touch user photo folders.
"""
from __future__ import annotations

import datetime as dt
import traceback as traceback_module
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .constants import SCRIPT_VERSION

UI_STATUS_SCHEMA_VERSION = 1
UI_SEVERITIES = ("info", "warning", "error")
UI_STATUS_SOURCES = (
    "backend",
    "config",
    "preflight",
    "self_test",
    "job",
    "project",
    "pipeline",
    "callback",
    "unknown",
)


@dataclass(frozen=True)
class UiIssue:
    """One UI-displayable issue.

    ``code`` is stable enough for UI icons/translations/filters. ``message`` is
    safe to show directly, while ``details`` may contain technical fields for an
    expandable diagnostics panel.
    """

    code: str
    severity: str
    source: str
    title: str
    message: str = ""
    action: str = ""
    stage: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class UiStatusReport:
    """Serializable status bundle for UI startup/run dialogs."""

    ok: bool
    version: str
    refactor_stage: str
    schema_version: int
    created_at: str
    summary: str
    issues: Tuple[UiIssue, ...] = ()
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["issues"] = [issue.to_dict() for issue in self.issues]
        return data

    @property
    def errors(self) -> Tuple[UiIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> Tuple[UiIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "warning")


@dataclass(frozen=True)
class UiStatusSummary:
    """Compact counts for badges/status bars."""

    ok: bool
    errors: int
    warnings: int
    infos: int
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _clean_severity(value: str) -> str:
    value = str(value or "info").lower()
    return value if value in UI_SEVERITIES else "info"


def _clean_source(value: str) -> str:
    value = str(value or "unknown")
    return value if value in UI_STATUS_SOURCES else value


def ui_issue(
    code: str,
    severity: str,
    source: str,
    title: str,
    message: str = "",
    *,
    action: str = "",
    stage: str = "",
    details: Optional[Dict[str, Any]] = None,
) -> UiIssue:
    """Create a normalized UI issue."""
    return UiIssue(
        code=str(code or "unknown"),
        severity=_clean_severity(severity),
        source=_clean_source(source),
        title=str(title or code or "Issue"),
        message=str(message or ""),
        action=str(action or ""),
        stage=str(stage or ""),
        details=dict(details or {}),
    )


def ui_status_report(
    issues: Sequence[UiIssue] = (),
    *,
    summary: str = "",
    details: Optional[Dict[str, Any]] = None,
    refactor_stage: str = "Этап 055",
) -> UiStatusReport:
    """Build a status report from normalized issues."""
    normalized = tuple(issues)
    ok = not any(issue.severity == "error" for issue in normalized)
    if not summary:
        if ok and not normalized:
            summary = "OK"
        elif ok:
            warnings = sum(1 for issue in normalized if issue.severity == "warning")
            summary = f"OK with {warnings} warning(s)" if warnings else "OK"
        else:
            errors = sum(1 for issue in normalized if issue.severity == "error")
            summary = f"{errors} error(s)"
    return UiStatusReport(
        ok=ok,
        version=SCRIPT_VERSION,
        refactor_stage=refactor_stage,
        schema_version=UI_STATUS_SCHEMA_VERSION,
        created_at=_now(),
        summary=summary,
        issues=normalized,
        details=dict(details or {}),
    )


def summarize_status_report(report: UiStatusReport) -> UiStatusSummary:
    """Return compact counts for a UI status badge."""
    errors = sum(1 for issue in report.issues if issue.severity == "error")
    warnings = sum(1 for issue in report.issues if issue.severity == "warning")
    infos = sum(1 for issue in report.issues if issue.severity == "info")
    return UiStatusSummary(ok=report.ok, errors=errors, warnings=warnings, infos=infos, summary=report.summary)


def merge_status_reports(*reports: UiStatusReport, summary: str = "") -> UiStatusReport:
    """Merge multiple status reports into one UI-facing report."""
    issues: List[UiIssue] = []
    details: Dict[str, Any] = {"merged_reports": []}
    for report in reports:
        issues.extend(report.issues)
        details["merged_reports"].append({
            "ok": report.ok,
            "summary": report.summary,
            "schema_version": report.schema_version,
            "created_at": report.created_at,
        })
    return ui_status_report(tuple(issues), summary=summary, details=details)



def _effective_language(language: Any = "auto") -> str:
    text = str(language or "auto").strip().lower()
    if text in {"ru", "russian", "русский"}:
        return "ru"
    if text in {"en", "english"}:
        return "en"
    return "en"


def _match_error_category(text: str, *, code: str = "", source: str = "") -> str:
    haystack = " ".join([str(code or ""), str(source or ""), str(text or "")]).lower()
    checks = (
        ("output_inside_input", ("output", "inside", "input")),
        ("output_inside_input", ("output", "внутри", "input")),
        ("input_missing", ("input", "required")),
        ("input_missing", ("input", "not found")),
        ("input_missing", ("исход", "пап", "не найден")),
        ("permission_denied", ("permission denied",)),
        ("permission_denied", ("access is denied",)),
        ("permission_denied", ("отказано", "доступ")),
        ("path_too_long", ("path", "too long")),
        ("path_too_long", ("слишком длин",)),
        ("gpu_unavailable", ("cudaexecutionprovider", "not available")),
        ("gpu_unavailable", ("cudaexecutionprovider", "missing")),
        ("gpu_unavailable", ("cuda", "provider", "unavailable")),
        ("gpu_unavailable", ("cublas",)),
        ("gpu_unavailable", ("cudnn",)),
        ("gpu_unavailable", ("cudart",)),
        ("missing_packages", ("missing required", "package")),
        ("missing_packages", ("no module named",)),
        ("no_embeddings", ("no embeddings",)),
        ("no_embeddings", ("sqlite", "нет", "embeddings")),
        ("no_embeddings", ("embeddings", "нет найденных лиц")),
        ("no_faces", ("no faces",)),
        ("no_faces", ("faces_total", "0")),
        ("no_faces", ("нет найденных лиц",)),
        ("no_faces", ("нет лиц",)),
        ("problem_file", ("decode", "error")),
        ("problem_file", ("read_open_error",)),
        ("problem_file", ("broken image",)),
        ("problem_file", ("бит", "изображ")),
        ("timeout", ("timeout",)),
        ("apply_names_missing", ("names.csv", "missing")),
        ("apply_names_missing", ("apply", "names.csv")),
        ("report_optional", ("review_decisions.csv",)),
        ("report_optional", ("problem_files.csv", "missing")),
        ("report_optional", ("final_review",)),
        ("report_optional", ("optional", "warning")),
        ("project_state", ("project.json",)),
        ("project_state", ("run_state",)),
    )
    for category, tokens in checks:
        if all(token in haystack for token in tokens):
            return category
    return "unknown"


def human_error_guidance(message: str = "", *, code: str = "", source: str = "", language: Any = "auto") -> Dict[str, str]:
    """Return a short user-facing meaning/action pair for a technical error.

    The helper is intentionally small and deterministic.  It does not inspect
    user folders, does not run ML and does not change backend behavior; it only
    maps common technical phrases/codes to safer UI wording.
    """
    lang = _effective_language(language)
    category = _match_error_category(message, code=code, source=source)
    ru: Dict[str, Tuple[str, str, str]] = {
        "output_inside_input": (
            "Папка результата выбрана внутри папки с фотографиями.",
            "Такой запуск может повторно обработать уже созданные файлы и засорить результат.",
            "Выберите output/result в отдельной папке, не внутри input.",
        ),
        "input_missing": (
            "Не выбрана или не найдена папка с исходными фотографиями.",
            "Программа не может начать обычную сортировку без существующей input-папки.",
            "Проверьте путь к input, подключение диска/OneDrive и права чтения.",
        ),
        "permission_denied": (
            "Нет доступа к файлу или папке.",
            "Windows, OneDrive, сетевой диск или антивирус могли запретить чтение/запись.",
            "Выберите папку с правами записи, закройте файл в других программах или запустите из доступного каталога.",
        ),
        "path_too_long": (
            "Путь к файлу слишком длинный для текущей среды Windows/Python.",
            "Глубокие вложенные папки и длинные имена могут мешать чтению или копированию файлов.",
            "Переместите input/output ближе к корню диска, например D:\\orig и D:\\result.",
        ),
        "gpu_unavailable": (
            "GPU-режим недоступен или CUDAExecutionProvider не поднялся.",
            "Видеокарта может быть видна Windows, но ONNX Runtime не получил рабочий CUDA runtime/provider.",
            "Используйте CPU-сборку/CPU-режим или проверьте NVIDIA driver и GPU portable package; CUDA Toolkit отдельно обычно не нужен для portable GPU build.",
        ),
        "missing_packages": (
            "В runtime не хватает Python-пакета.",
            "Это актуально для source-запуска или некорректной portable-сборки.",
            "Для portable используйте готовый ZIP; для source-запуска установите requirements именно в тот Python, которым запускаете приложение.",
        ),
        "no_faces": (
            "Лица не найдены.",
            "Это не обязательно поломка: фото могут быть без людей, лица могут быть маленькими, размытыми, закрытыми или повернутыми.",
            "Проверьте маленькую тестовую папку с 5-20 понятными портретными фото и затем откройте reports/diagnostics.",
        ),
        "no_embeddings": (
            "Нет найденных лиц/embeddings для следующего этапа.",
            "Следующие этапы требуют результата scan: SQLite должен содержать найденные лица и embeddings.",
            "Сначала запустите обычный Start/mode=all или scan на папке с фото, где реально есть лица.",
        ),
        "problem_file": (
            "Один или несколько файлов не удалось прочитать или декодировать.",
            "Обычно это битые изображения, неверное расширение, неподдерживаемый формат или файл, занятый другой программой.",
            "Откройте reports/problem_files.csv, проверьте конкретные пути и пересохраните/удалите проблемные файлы.",
        ),
        "timeout": (
            "Обработка отдельного файла заняла слишком много времени.",
            "Защита пропускает зависший файл, чтобы весь запуск не остановился.",
            "Проверьте файл из problem_files.csv, особенно очень большие, битые или сетевые файлы.",
        ),
        "apply_names_missing": (
            "Не хватает данных для применения имён.",
            "apply-names использует уже созданные assignments.csv и names.csv; он не пересканирует фотографии.",
            "Сначала выполните обычную сортировку, затем Review clusters → Сохранить names.csv → Применить имена.",
        ),
        "report_optional": (
            "Отсутствует необязательный файл отчёта или папка результата.",
            "Некоторые файлы появляются только в определённых workflow: review_decisions.csv после ручного review, problem_files.csv только при проблемных файлах, final/final_review после apply-names.",
            "Если основной запуск успешен, это обычно нормально; для проверки используйте result-health и reports.",
        ),
        "project_state": (
            "Есть проблема с project.json/run state выбранной result-папки.",
            "Папка может быть незавершённой, созданной другой версией или выбран не тот output.",
            "Откройте result-health/support-bundle или создайте новую result-папку для чистого запуска.",
        ),
        "unknown": (
            "Техническая ошибка без готовой короткой классификации.",
            "Детали сохранены в статусе, diagnostics или bug-report.",
            "Создайте support-bundle/bug-report и проверьте полный traceback только в диагностике, не в основном UI.",
        ),
    }
    en: Dict[str, Tuple[str, str, str]] = {
        "output_inside_input": (
            "The result folder is inside the photo input folder.",
            "This can make the app process its own generated files and pollute the result.",
            "Choose an output/result folder outside the input folder.",
        ),
        "input_missing": (
            "The source photo folder is missing or was not selected.",
            "The normal sorting run cannot start without an existing input folder.",
            "Check the input path, external/OneDrive drive state and read permissions.",
        ),
        "permission_denied": (
            "Access to a file or folder was denied.",
            "Windows, OneDrive, a network drive or antivirus may block read/write access.",
            "Choose a writable folder, close the file in other programs, or run from an accessible location.",
        ),
        "path_too_long": (
            "A file path is too long for the current Windows/Python environment.",
            "Deep folders and very long names can break reading or copying.",
            "Move input/output closer to the drive root, for example D:\\orig and D:\\result.",
        ),
        "gpu_unavailable": (
            "GPU mode is unavailable or CUDAExecutionProvider did not load.",
            "Windows may see the GPU while ONNX Runtime still has no working CUDA runtime/provider.",
            "Use the CPU build/CPU mode or check the NVIDIA driver and GPU portable package; a separate CUDA Toolkit is usually not needed for the portable GPU build.",
        ),
        "missing_packages": (
            "A required Python package is missing from the runtime.",
            "This usually applies to source runs or an incorrectly built portable package.",
            "Use the ready portable ZIP, or install requirements into the exact Python used to run the app.",
        ),
        "no_faces": (
            "No faces were found.",
            "This is not always a failure: photos may contain no people or faces may be too small, blurry, occluded or rotated.",
            "Try a 5-20 photo test folder with clear portraits, then open reports/diagnostics.",
        ),
        "no_embeddings": (
            "No detected faces/embeddings are available for the next stage.",
            "Later stages require scan output in SQLite: detected faces and embeddings must exist first.",
            "Run normal Start/mode=all or scan first on photos that clearly contain faces.",
        ),
        "problem_file": (
            "One or more files could not be read or decoded.",
            "The usual causes are broken images, wrong extensions, unsupported formats or files locked by another program.",
            "Open reports/problem_files.csv, inspect the exact paths, then re-save/convert or remove those files.",
        ),
        "timeout": (
            "A single file took too long to process.",
            "The safeguard skips a stuck file so the whole run can continue.",
            "Check the file listed in problem_files.csv, especially very large, broken or network files.",
        ),
        "apply_names_missing": (
            "Data needed for applying names is missing.",
            "apply-names uses existing assignments.csv and names.csv; it does not rescan photos.",
            "Run normal sorting first, then Review clusters → Save names.csv → Apply names.",
        ),
        "report_optional": (
            "An optional report file or result folder is absent.",
            "Some files appear only in specific workflows: review_decisions.csv after manual review, problem_files.csv only when problematic files exist, final/final_review after apply-names.",
            "If the main run succeeded, this is usually normal; use result-health and reports to verify.",
        ),
        "project_state": (
            "There is a project.json/run-state issue in the selected result folder.",
            "The folder may be unfinished, created by another version, or it may not be the intended output folder.",
            "Run result-health/support-bundle or choose a new result folder for a clean run.",
        ),
        "unknown": (
            "A technical error has no short classification yet.",
            "Details are preserved in Status, diagnostics or bug-report.",
            "Create a support-bundle/bug-report and inspect the full traceback only in diagnostics, not in the main UI.",
        ),
    }
    title, meaning, action = (ru if lang == "ru" else en).get(category, (ru if lang == "ru" else en)["unknown"])
    return {"category": category, "title": title, "meaning": meaning, "action": action}


def humanize_issue(issue: UiIssue, *, language: Any = "auto") -> UiIssue:
    """Return an issue with user-facing meaning/action details added."""
    guidance = human_error_guidance(issue.message or issue.title, code=issue.code, source=issue.source, language=language)
    details = dict(issue.details or {})
    details.setdefault("user_category", guidance["category"])
    details.setdefault("user_meaning", guidance["meaning"])
    details.setdefault("recommended_action", guidance["action"])
    title = issue.title or guidance["title"]
    action = issue.action or guidance["action"]
    return UiIssue(
        code=issue.code,
        severity=issue.severity,
        source=issue.source,
        title=title,
        message=issue.message,
        action=action,
        stage=issue.stage,
        details=details,
    )


def humanize_status_report(report: UiStatusReport, *, language: Any = "auto") -> UiStatusReport:
    """Add human-readable guidance to all issues in a status report."""
    return UiStatusReport(
        ok=report.ok,
        version=report.version,
        refactor_stage=report.refactor_stage,
        schema_version=report.schema_version,
        created_at=report.created_at,
        summary=report.summary,
        issues=tuple(humanize_issue(issue, language=language) for issue in report.issues),
        details=dict(report.details or {}),
    )


def build_error_guidance_text(language: Any = "auto") -> str:
    """Return a compact help text for the user-facing error categories."""
    lang = _effective_language(language)
    categories = (
        "input_missing", "output_inside_input", "permission_denied", "path_too_long",
        "gpu_unavailable", "no_faces", "problem_file", "apply_names_missing", "report_optional",
    )
    if lang == "ru":
        lines = [
            "Памятка по понятным ошибкам",
            "================================",
            "Статус / ошибки теперь показывает не только техническое сообщение, но и короткое объяснение: что значит проблема и что сделать дальше.",
            "",
        ]
    else:
        lines = [
            "Human-readable error guide",
            "==========================",
            "Status / errors now shows the technical message plus a short explanation: what the problem means and what to do next.",
            "",
        ]
    for category in categories:
        guidance = human_error_guidance(category, code=category, language=lang)
        if lang == "ru":
            lines.append(f"- {guidance['title']} Что сделать: {guidance['action']}")
        else:
            lines.append(f"- {guidance['title']} Action: {guidance['action']}")
    return "\n".join(lines)

def issue_from_exception(
    exc: BaseException,
    *,
    source: str = "backend",
    stage: str = "",
    code: str = "exception",
    include_traceback: bool = True,
) -> UiIssue:
    """Convert an exception to a UI-displayable issue."""
    details: Dict[str, Any] = {
        "exception_type": type(exc).__name__,
        "exception_message": str(exc),
    }
    if include_traceback:
        details["traceback"] = "".join(traceback_module.format_exception(type(exc), exc, exc.__traceback__))
    guidance = human_error_guidance(str(exc), code=code, source=source, language="en")
    details.setdefault("user_category", guidance["category"])
    details.setdefault("user_meaning", guidance["meaning"])
    details.setdefault("recommended_action", guidance["action"])
    return ui_issue(
        code=code,
        severity="error",
        source=source,
        title=f"{type(exc).__name__}",
        message=str(exc),
        action=guidance["action"],
        stage=stage,
        details=details,
    )


def status_from_validation_result(validation: Any, *, source: str = "config") -> UiStatusReport:
    """Convert ApiValidationResult-like objects to UiStatusReport."""
    issues: List[UiIssue] = []
    for message in tuple(getattr(validation, "errors", ()) or ()): 
        issues.append(ui_issue("validation_error", "error", source, "Validation error", str(message)))
    for message in tuple(getattr(validation, "warnings", ()) or ()): 
        issues.append(ui_issue("validation_warning", "warning", source, "Validation warning", str(message)))
    return ui_status_report(issues, summary="Validation OK" if not issues else "Validation has issues")


def status_from_preflight_result(preflight: Any) -> UiStatusReport:
    """Convert RuntimePreflightResult-like objects to a UI status report."""
    issues: List[UiIssue] = []
    missing_required = tuple(getattr(preflight, "missing_required", ()) or ())
    if missing_required:
        issues.append(ui_issue(
            "missing_required_packages",
            "error",
            "preflight",
            "Missing required Python packages",
            ", ".join(str(item) for item in missing_required),
            action="Install the missing packages in the same Python environment used to run Face Sorter.",
            details={"packages": list(missing_required)},
        ))
    for message in tuple(getattr(preflight, "errors", ()) or ()): 
        issues.append(ui_issue("runtime_preflight_error", "error", "preflight", "Runtime preflight error", str(message)))
    for message in tuple(getattr(preflight, "warnings", ()) or ()): 
        issues.append(ui_issue("runtime_preflight_warning", "warning", "preflight", "Runtime preflight warning", str(message)))
    gpu = getattr(preflight, "gpu", None)
    if gpu is not None:
        nvidia_found = bool(getattr(gpu, "nvidia_smi_found", False))
        cuda_available = bool(getattr(gpu, "cuda_provider_available", False))
        warning_text = "\n".join(str(item) for item in tuple(getattr(preflight, "warnings", ()) or ()))
        cpu_portable_expected = "CPU portable build" in warning_text
        if nvidia_found and not cuda_available and not cpu_portable_expected:
            issues.append(ui_issue(
                "cuda_provider_unavailable",
                "warning",
                "preflight",
                "CUDAExecutionProvider is not available",
                "NVIDIA GPU was detected, but ONNX Runtime did not expose CUDAExecutionProvider.",
                action="Use CPU mode or fix the ONNX Runtime GPU/CUDA/cuDNN environment before enabling GPU.",
                details={
                    "onnx_providers": list(getattr(gpu, "onnx_providers", ()) or ()),
                    "nvidia_gpu": getattr(gpu, "nvidia_gpu", ""),
                    "onnxruntime_version": getattr(gpu, "onnxruntime_version", ""),
                },
            ))
    summary = "Runtime preflight OK" if not issues else "Runtime preflight has issues"
    return ui_status_report(issues, summary=summary, details={"preflight_ok": bool(getattr(preflight, "ok", False))})


def status_from_self_test_result(result: Any) -> UiStatusReport:
    """Convert BackendSelfTestResult-like objects to a UI status report."""
    issues: List[UiIssue] = []
    for check in tuple(getattr(result, "checks", ()) or ()): 
        if not bool(getattr(check, "ok", False)):
            issues.append(ui_issue(
                "backend_self_test_check_failed",
                "error",
                "self_test",
                f"Self-test failed: {getattr(check, 'name', 'unknown')}",
                str(getattr(check, "message", "")),
                details=dict(getattr(check, "details", {}) or {}),
            ))
    for message in tuple(getattr(result, "warnings", ()) or ()): 
        issues.append(ui_issue("backend_self_test_warning", "warning", "self_test", "Backend self-test warning", str(message)))
    summary = "Backend self-test OK" if not issues else "Backend self-test has issues"
    return ui_status_report(issues, summary=summary, details={"self_test_ok": bool(getattr(result, "ok", False))})


def status_from_job_snapshot(snapshot: Any, events: Iterable[Any] = ()) -> UiStatusReport:
    """Convert BackendJobSnapshot-like objects and callback events to UI status."""
    issues: List[UiIssue] = []
    state = str(getattr(snapshot, "state", "") or "")
    error = str(getattr(snapshot, "error", "") or "")
    if state in {"error", "failed"} or error:
        issues.append(ui_issue(
            "backend_job_failed",
            "error",
            "job",
            "Backend job failed",
            error or f"Job ended with state: {state}",
            stage=str(getattr(snapshot, "current_stage", "") or ""),
            details={
                "state": state,
                "traceback": str(getattr(snapshot, "traceback", "") or ""),
                "result_status": str(getattr(snapshot, "result_status", "") or ""),
            },
        ))
    warnings_count = int(getattr(snapshot, "warnings_count", 0) or 0)
    errors_count = int(getattr(snapshot, "errors_count", 0) or 0)
    if warnings_count:
        issues.append(ui_issue(
            "backend_job_warning_events",
            "warning",
            "job",
            "Backend emitted warning events",
            f"{warnings_count} warning event(s) were captured during this job.",
            stage=str(getattr(snapshot, "current_stage", "") or ""),
            details={"warnings_count": warnings_count},
        ))
    if errors_count and not error:
        issues.append(ui_issue(
            "backend_job_error_events",
            "error",
            "job",
            "Backend emitted error events",
            f"{errors_count} error event(s) were captured during this job.",
            stage=str(getattr(snapshot, "current_stage", "") or ""),
            details={"errors_count": errors_count},
        ))
    if bool(getattr(snapshot, "cancel_requested", False)):
        issues.append(ui_issue(
            "backend_job_cancel_requested",
            "info",
            "job",
            "Cancel requested",
            "The UI requested cancellation. Hard cancellation is not supported in this build.",
            stage=str(getattr(snapshot, "current_stage", "") or ""),
        ))
    for event in events:
        kind = str(getattr(event, "kind", "") or "")
        if kind == "warning":
            issues.append(ui_issue("backend_event_warning", "warning", "job", "Backend warning", str(getattr(event, "message", "") or ""), stage=str(getattr(event, "stage", "") or ""), details=dict(getattr(event, "data", {}) or {})))
        elif kind in {"error", "callback_error"}:
            issues.append(ui_issue("backend_event_error", "error", "job", "Backend error", str(getattr(event, "message", "") or ""), stage=str(getattr(event, "stage", "") or ""), details=dict(getattr(event, "data", {}) or {})))
    if not issues:
        summary = "Backend job OK"
    elif any(issue.severity == "error" for issue in issues):
        summary = "Backend job has errors"
    else:
        summary = "Backend job OK with warnings"
    return ui_status_report(issues, summary=summary, details={"job_state": state, "events_total": int(getattr(snapshot, "events_total", 0) or 0), "last_event_kind": str(getattr(snapshot, "last_event_kind", "") or "")})


__all__ = [
    "UI_STATUS_SCHEMA_VERSION",
    "UI_SEVERITIES",
    "UI_STATUS_SOURCES",
    "UiIssue",
    "UiStatusReport",
    "UiStatusSummary",
    "ui_issue",
    "ui_status_report",
    "summarize_status_report",
    "merge_status_reports",
    "human_error_guidance",
    "humanize_issue",
    "humanize_status_report",
    "build_error_guidance_text",
    "issue_from_exception",
    "status_from_validation_result",
    "status_from_preflight_result",
    "status_from_self_test_result",
    "status_from_job_snapshot",
]
