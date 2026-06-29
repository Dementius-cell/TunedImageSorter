# -*- coding: utf-8 -*-
"""Import-safe UI polish/settings/instructions helpers.

v69.6 / Этап 055 keeps the small polish contract for the optional PySide6 UI:
application icon metadata, UI-only settings, localized quick-start text,
first-run hints, post-run navigation and the diagnostics/support panel labels.  This module does not import Qt,
does not initialize ML runtimes and does not touch photo/project folders.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

from .constants import SCRIPT_DIR, SCRIPT_VERSION

UI_POLISH_SCHEMA_VERSION = 5
UI_POLISH_STAGE = "Этап 055"
UI_ICON_RELATIVE_PATH = "ui/resources/app_icon.ico"
UI_ICON_PNG_RELATIVE_PATH = "ui/resources/app_icon.png"

UI_LANGUAGE_CHOICES: Tuple[str, ...] = ("auto", "ru", "en")
UI_THEME_CHOICES: Tuple[str, ...] = ("system", "light", "dark")
UI_DENSITY_CHOICES: Tuple[str, ...] = ("comfortable", "compact")


@dataclass(frozen=True)
class UiInstructionStep:
    """One short user-facing instruction line for the optional GUI."""

    title: str
    body: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class UiInstructionSection:
    """A small localized instruction section for the Help/Settings UI tab."""

    key: str
    title: str
    steps: Tuple[UiInstructionStep, ...]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["steps"] = [step.to_dict() for step in self.steps]
        return data


@dataclass(frozen=True)
class UiPolishSettings:
    """UI-only preferences persisted in core.session extra/session fields."""

    language: str = "auto"
    theme: str = "system"
    density: str = "comfortable"
    show_startup_tips: bool = True
    confirm_before_run: bool = True
    auto_open_reports_after_run: bool = False
    show_advanced_fields: bool = False
    verbose_progress_events: bool = False
    auto_scroll_logs: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class UiPolishSnapshot:
    """Serializable polish contract snapshot for self-tests and diagnostics."""

    version: str
    refactor_stage: str
    schema_version: int
    icon_path: Path
    icon_png_path: Path
    language_choices: Tuple[str, ...]
    theme_choices: Tuple[str, ...]
    density_choices: Tuple[str, ...]
    instructions: Tuple[UiInstructionSection, ...]
    notes: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["icon_path"] = str(self.icon_path)
        data["icon_png_path"] = str(self.icon_png_path)
        data["instructions"] = [section.to_dict() for section in self.instructions]
        return data


def normalize_ui_language(value: Any) -> str:
    """Normalize a UI language code to auto/ru/en."""
    text = str(value or "auto").strip().lower()
    if text in {"ru", "russian", "русский"}:
        return "ru"
    if text in {"en", "english"}:
        return "en"
    return "auto"


def effective_ui_language(value: Any) -> str:
    """Return a concrete language for short GUI/help text."""
    normalized = normalize_ui_language(value)
    return "ru" if normalized == "auto" else normalized


def normalize_ui_theme(value: Any) -> str:
    text = str(value or "system").strip().lower()
    return text if text in UI_THEME_CHOICES else "system"


def normalize_ui_density(value: Any) -> str:
    text = str(value or "comfortable").strip().lower()
    return text if text in UI_DENSITY_CHOICES else "comfortable"


def _bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on", "да"}


_TEXT: Dict[str, Dict[str, str]] = {
    "ru": {
        "app_header_title": "Tuned Image Sorter v69.6 / Этап 055",
        "app_header_body": "v69.6 добавляет friend-ready QUICK_START и TROUBLESHOOTING документы; путь обычного пользователя стал понятнее. ML/pipeline/report formats не меняются.",
        "nav_run": "Запуск / настройки",
        "nav_progress": "Ход выполнения",
        "progress_page_help": "Ход выполнения: общий статус, progress bar и подробная таблица стадий вынесены в отдельный раздел, чтобы не занимать место на форме запуска.",
        "show_advanced_fields": "Показать расширенные поля",
        "preflight": "Проверка окружения",
        "quick_test": "Быстрый тест",
        "backend_self_test": "Самопроверка backend",
        "start": "Старт",
        "cancel_request": "Запрос отмены",
        "open_output": "Открыть результат",
        "open_reports": "Открыть отчёты",
        "open_diagnostics": "Открыть diagnostics",
        "open_bug_report": "Открыть bug-report",
        "create_bug_report": "Создать bug-report",
        "copy_summary": "Копировать сводку",
        "copy_paths": "Копировать пути",
        "readiness_initial": "Готовность формы: проверка ещё не выполнена.",
        "status_pending": "Статус: ожидание — готово к запуску.",
        "job_meta_initial": "Задача: — | события: 0 | предупреждения: 0 | ошибки: 0 | время: —",
        "stage_header_stage": "Этап",
        "stage_header_state": "Состояние",
        "stage_header_progress": "Прогресс",
        "stage_header_message": "Последнее сообщение",
        "show_stage_details": "Показать подробный прогресс по этапам",
        "hide_stage_details": "Скрыть подробный прогресс по этапам",
        "auto_scroll_logs": "Автопрокрутка логов",
        "verbose_progress_events": "Подробные события прогресса",
        "clear_logs": "Очистить логи",
        "copy_diagnostics": "Копировать диагностику",
        "events_placeholder": "Здесь появятся события после проверки окружения, самопроверки или запуска backend-задачи.",
        "events_tab": "События / логи",
        "status_placeholder": "Здесь появятся ошибки и предупреждения проверки формы, окружения, самопроверки и задачи.",
        "human_error_help": "v69.6: этот раздел показывает не только техническую ошибку, но и краткое объяснение: «Что это значит» и «Что сделать». Полный traceback остаётся в diagnostics/bug-report.",
        "status_tab": "Статус / ошибки",
        "result_placeholder": "Здесь появится итог запуска после завершения backend-задачи.",
        "result_tab": "Итог запуска",
        "resume_help": "Продолжение и recent-проекты: список берётся из UI session и unfinished result-папок рядом с выбранным input. Формат project.json не меняется; кнопка продолжения только подставляет output и resume-mode в форму запуска.",
        "refresh_resume": "Обновить продолжение/recent",
        "use_selected_resume": "Продолжить выбранный",
        "open_selected_result": "Открыть выбранный результат",
        "open_selected_reports": "Открыть отчёты выбранного",
        "prune_recent": "Очистить missing recent",
        "resume_tab": "Продолжение / recent",
        "reports_help": "Отчёты и review: слева выберите раздел, справа будет показана только нужная информация. Форматы reports, names.csv и review_decisions.csv не меняются.",
        "reports_nav_title": "Разделы отчётов",
        "reports_nav_overview": "Обзор",
        "reports_nav_files": "Файлы отчётов",
        "reports_nav_problems": "Проблемные файлы",
        "reports_nav_review": "Review clusters",
        "reports_nav_apply": "Имена / apply-names",
        "reports_nav_folders": "Папки результата",
        "reports_overview_placeholder": "Здесь появится сводка по выбранной result-папке.",
        "reports_files_help": "Файлы отчётов: выберите файл в таблице и нажмите «Открыть выбранный файл/папку» или используйте быстрые кнопки. Missing/не создан означает, что файл ещё не появился для текущего workflow; кнопки отсутствующих файлов отключены.",
        "problem_files_missing_hint": "problem_files.csv может отсутствовать после нормального успешного прогона — это означает, что проблемные файлы не зафиксированы.",
        "problem_files_help": "Проблемные файлы: read-only сводка по reports/problem_files.csv. Раздел объясняет, почему файл был пропущен: битое изображение, неподдерживаемый формат, read/open error, decode error, timeout или internal worker error. Формат CSV не меняется.",
        "problem_files_status_no_output": "Выберите result/output и обновите отчёты, чтобы увидеть состояние problem_files.csv.",
        "problem_files_status_missing": "Проблемных файлов не зафиксировано: problem_files.csv отсутствует. Для обычного успешного прогона это нормальное состояние.",
        "problem_files_status_present": "Есть проблемные файлы: проверьте категории ниже и откройте problem_files.csv для точных путей и ошибок.",
        "open_problem_files": "Открыть problem_files.csv",
        "review_decisions_missing_hint": "review_decisions.csv не обязан появляться после обычной сортировки. Он создаётся после «Сохранить names.csv» или «Применить имена из Review clusters».",
        "review_workflow_hint": "Мини-памятка: keep + Name создаёт именованную final-папку; keep без Name оставляет кластер без имени; merge требует Merge into; review отправляет в final_review; ignore исключает кластер из применения имени.",
        "review_workflow_status_no_output": "Выберите result/output и обновите отчёты, чтобы увидеть состояние Review clusters.",
        "review_workflow_status_no_rows": "Review clusters пуст: нет строк для ручных решений или review_clusters.csv ещё не создан.",
        "review_action_combo_tooltip": "Выберите действие для кластера: keep, merge, review или ignore.",
        "review_name_tooltip": "Name: имя будущей final-папки для action=keep. Пустое имя не создаёт именованную папку.",
        "review_merge_tooltip": "Merge into: cluster_key целевого кластера для action=merge, например person_001.",
        "review_notes_tooltip": "Notes: свободный комментарий; на ML и кластеризацию не влияет.",
        "reports_review_help": "Review clusters: таблица для просмотра и правки action/name/merge/notes. Работайте слева направо: выберите Action, при необходимости заполните Name или Merge into, затем сохраните names.csv или примените имена. Формат backend не меняется.",
        "review_action_help": "Столбец Action: keep — задать/оставить имя для кластера; merge — объединить с кластером из Merge into; review — отправить в ручную проверку/final_review; ignore — не применять имя к этому кластеру. После правок нажмите «Сохранить names.csv» или «Применить имена из Review clusters».",
        "review_edit_hint": "Порядок: 1) выберите Action; 2) для keep заполните Name, для merge заполните Merge into; 3) Notes используйте как комментарий; 4) сохраните names.csv или примените имена.",
        "apply_names_here": "Применить имена из Review clusters",
        "save_names_csv_tooltip": "Сохранить текущие решения таблицы в names.csv и reports/review_decisions.csv без запуска backend job. До этого review_decisions.csv может отсутствовать — это нормально.",
        "apply_names_tooltip": "Сохранить решения и запустить существующий backend mode=apply-names для выбранной result-папки. Это не пересканирует фото, а создаёт final/final_review из assignments.csv и names.csv.",
        "reports_apply_help": "Имена / apply-names: контрольный раздел для применения names.csv. Сначала сохраните решения, затем примените имена. То же действие доступно и прямо в Review clusters.",
        "reports_apply_details": "1. Проверьте Review clusters.\n2. Для keep укажите Name, если нужен человек/final folder. Пустое имя не создаёт person-name folder.\n3. Для merge укажите Merge into — cluster_key целевого кластера.\n4. Для review используйте сомнительные/смешанные кластеры; они уйдут в final_review.\n5. Нажмите «Сохранить names.csv», затем «Применить имена».\n\nApply-names не пересканирует фото и не меняет ML/clustering/reports schema; он создаёт final/final_review по существующим assignments.csv + names.csv.",
        "reports_folders_help": "Папки результата: быстрый доступ к output, reports, diagnostics, final и final_review.",
        "review_details_placeholder": "Выберите строку Review clusters, чтобы увидеть детали и thumbnails.",
        "refresh_reports": "Обновить отчёты/review",
        "open_reports_folder": "Открыть reports",
        "open_selected_report": "Открыть выбранный файл/папку",
        "copy_reports_summary": "Копировать сводку отчётов",
        "open_summary_csv": "Открыть summary.csv",
        "open_assignments_csv": "Открыть assignments.csv",
        "open_clusters_html": "Открыть clusters.html",
        "open_duplicates_csv": "Открыть duplicates.csv",
        "open_review_clusters_csv": "Открыть review_clusters.csv",
        "open_names_csv": "Открыть names.csv",
        "open_review_decisions": "Открыть review_decisions.csv",
        "save_names_csv": "Сохранить names.csv",
        "apply_names": "Применить имена",
        "open_final": "Открыть final",
        "open_final_review": "Открыть final_review",
        "reports_tab": "Отчёты / review",
        "settings_tab": "Помощь / настройки",
        "settings_title": "Настройки UI и быстрые инструкции",
        "settings_group": "Настройки UI",
        "language": "Язык UI",
        "theme": "Тема",
        "density": "Плотность",
        "show_tips": "Показывать подсказки при старте",
        "confirm_run": "Подтверждать запуск",
        "auto_open_reports": "Открывать отчёты после успешного запуска",
        "save_settings": "Сохранить UI-настройки",
        "open_session_folder": "Открыть папку session",
        "open_ru_guide": "Открыть инструкцию RU",
        "open_en_guide": "Открыть инструкцию EN",
        "open_help_ru": "Открыть справку RU",
        "open_help_en": "Открыть справку EN",
        "open_packaging_guide": "Открыть packaging guide",
        "settings_saved": "UI-настройки сохранены.",
        "run_confirm_title": "Подтверждение запуска",
        "run_confirm_body": "Запустить сортировку с текущими настройками?",
        "startup_tip_title": "Tuned Image Sorter v69.6",
        "startup_tip_body": "Выберите input/output, убедитесь что output не внутри input, нажмите «Проверка окружения» и сначала выполните быстрый тест на маленькой папке.",
        "browse": "Выбрать…",
        "auto": "Авто",
        "no_thumbnails": "Для этого кластера не найдены preview thumbnails. Полный preview доступен в clusters.html.",
        "tooltip_preflight": "Проверить runtime/GPU окружение без запуска ML-прогона.",
        "tooltip_quick_test": "Памятка для первого безопасного теста на маленькой папке без изменения настроек backend.",
        "tooltip_selftest": "Проверить backend/UI contract без запуска распознавания.",
        "tooltip_start": "Запустить backend job. Кнопка доступна только когда input-папка готова.",
        "tooltip_cancel": "Мягкий запрос отмены. Жёсткое прерывание pipeline в этой версии не включено.",
        "tooltip_open_output": "Открыть текущую result/output-папку, если она уже существует.",
        "tooltip_open_reports": "Открыть папку reports внутри текущего result/output.",
        "tooltip_open_diagnostics": "Открыть diagnostics внутри result/output или reports/diagnostics, если папка уже есть.",
        "tooltip_open_bug_report": "Открыть последний созданный bug-report zip.",
        "tooltip_create_bug_report": "Создать bug-report с дополнительным UI-контекстом и diagnostics.",
        "tooltip_copy_summary": "Скопировать краткое резюме текущих настроек или последнего результата.",
        "tooltip_copy_paths": "Скопировать input/output/reports/bug-report paths.",
        "support_panel_tab": "Диагностика / Support",
        "support_panel_help": "Диагностика / Support: безопасный раздел для проверки окружения, проверки уже созданной result/output папки, создания support-bundle и быстрого открытия diagnostics/reports/bug_reports. Сводка разделяет CPU/GPU runtime, result-health, support-bundle и optional warnings. Кнопки используют существующую backend/CLI diagnostics-логику и не запускают ML/pipeline/apply-names.",
        "support_check_environment": "Проверка окружения",
        "support_check_environment_tooltip": "Запустить тот же runtime-preflight, что и кнопка на форме запуска; пакеты не устанавливаются и фото не сканируются.",
        "support_check_result": "Проверка результата",
        "support_check_result_tooltip": "Запустить existing result-health для выбранной output/result папки и создать reports/result_health_check.json/txt.",
        "support_create_bundle": "Создать support-bundle",
        "support_create_bundle_tooltip": "Создать существующий bug-report/support-bundle ZIP с UI-контекстом и result-health; исходные фото и embeddings не добавляются.",
        "support_open_bug_reports": "Открыть bug_reports",
        "support_open_bug_reports_tooltip": "Открыть output/bug_reports, где сохраняются support-bundle ZIP-файлы.",
        "support_open_last_bundle": "Открыть последний ZIP",
        "support_open_last_bundle_tooltip": "Открыть последний созданный support-bundle/bug-report ZIP.",
        "support_copy_short_summary": "Скопировать короткую diagnostic summary",
        "support_copy_short_summary_tooltip": "Скопировать краткую сводку версии, output/reports/diagnostics, preflight и result-health без полного лога.",
        "support_refresh_summary": "Обновить сводку",
        "support_refresh_summary_tooltip": "Обновить текстовую сводку панели без запуска дополнительных проверок.",
        "support_summary_placeholder": "Здесь появится короткая diagnostic summary с отдельными блоками CPU/GPU runtime, result-health, support-bundle и optional warnings.",
        "support_warn_no_output": "Сначала выберите существующую result/output папку.",
        "support_warn_job_running": "Support-bundle лучше создавать после завершения текущей backend job.",
        "support_path_status": "Output: {output}\nReports: {reports}\nDiagnostics: {diagnostics}\nBug reports: {bug_reports}",
        "session_label": "Session",
        "session_saved": "Session saved",
        "readiness_running": "Готовность формы: backend job выполняется; изменение формы будет сохранено, но старт недоступен.",
        "readiness_ok": "Готовность формы: OK — можно запускать.",
        "readiness_warnings_prefix": "Готовность формы: можно запускать, есть предупреждения: ",
        "readiness_errors_prefix": "Готовность формы: старт недоступен — ",
        "readiness_input_required": "Выберите input-папку с фотографиями.",
        "readiness_input_not_found": "Input-папка не найдена: {path}",
        "readiness_output_empty": "Output пустой: будет предложен/создан backend-логикой, но для UI удобнее нажать «Авто».",
        "readiness_output_inside_input": "Output находится внутри input. Лучше выбрать result-папку вне исходных фотографий, чтобы будущие запуски не сканировали сгенерированные файлы.",
        "readiness_output_exists": "Output уже существует. Для продолжения включите resume_existing_output или выберите новую result-папку.",
        "readiness_mode_needs_existing": "Режим {mode} обычно продолжает существующий result/project; проверьте output-папку.",
        "path_input_required": "Input folder is required.",
        "path_input_not_found": "Input folder does not exist.",
        "path_input_ok": "Input folder exists.",
        "path_output_empty": "Output is empty. Use Auto to make the result folder explicit.",
        "path_output_inside_input": "Output is inside input. Choose a result folder outside the source photos.",
        "path_output_exists": "Output already exists. Enable resume_existing_output or choose a new folder.",
        "path_output_ok": "Output path is set.",
        "dialog_select_input": "Выберите папку с фото",
        "dialog_select_output": "Выберите result/output папку",
        "warn_select_input": "Сначала выберите input-папку.",
        "warn_suggest_output_failed": "Не удалось предложить output-папку: {error}",
        "warn_path_unknown": "Путь пока не известен.",
        "warn_path_not_found": "Путь не найден: {path}",
        "warn_report_not_selected": "Файл отчёта не выбран.",
        "warn_report_not_known": "Файл отчёта пока не известен.",
        "warn_resume_not_selected": "Сначала выберите recent/resume проект.",
        "warn_resume_result_missing": "Result-папка не найдена: {path}",
        "close_running_job": "Backend job всё ещё выглядит запущенным. Закрыть окно UI всё равно?\nВ этой сборке поддерживается только мягкая отмена.",
        "job_meta_empty": "Job: — | events: 0 | warnings: 0 | errors: 0 | duration: —",
        "job_meta_starting": "Job: starting | events: 0 | warnings: 0 | errors: 0 | duration: —",
        "status_starting": "Статус: starting — запуск backend job…",
        "status_cancel_requested": "Статус: cancel requested — {stage}",
        "status_line": "Статус: {state} — {stage}",
        "reports_summary_title": "сводка отчётов",
        "run_result_title": "итог запуска",
        "run_user_summary": "Пользовательская сводка",
        "problem_files_section": "Проблемные файлы",
        "explanations_section": "Пояснения",
        "technical_summary_section": "Техническая сводка",
        "project_json_not_read": "project.json пока не прочитан; технические пути указаны выше.",
        "photos_processed": "фото обработано: {count}",
        "summary_rows": "person clusters / строк summary.csv: {count}",
        "person_folders": "person folders создано: {count}",
        "review_files_total": "файлов в review всего: {count}",
        "assignments_rows": "строк assignments.csv: {count}",
        "review_clusters_rows": "строк review_clusters.csv: {count}",
        "duplicates_rows": "строк duplicates.csv: {count}",
        "problem_files_rows": "problem_files.csv строк: {count}",
        "explain_no_faces": "review/no_faces — фото, где лица не найдены.",
        "explain_unknown_faces": "review/unknown_faces — лица найдены, но не назначены в уверенный person cluster.",
        "explain_problem_files_missing": "problem_files.csv отсутствует — нормальное состояние, если ошибок чтения/декодирования/timeout/worker не было.",
        "explain_open_reports": "Открывайте result/reports/diagnostics кнопками над логами; форматы отчётов не менялись.",
        "confirm_readiness": "Готовность:",
        "confirm_warnings": "Предупреждения:",
        "confirm_errors": "Ошибки:",
        "confirm_pipeline_note": "Запускается существующий backend pipeline. ML-алгоритмы, CLI wizard и project/report formats не меняются.",
        "schema_prefix": "UI schema",
        "help_docs_note": "Справка доступна на русском и английском языках; v69.6 добавляет QUICK_START_RU/EN.txt и TROUBLESHOOTING_RU/EN.txt без изменения pipeline.",
    },
    "en": {
        "app_header_title": "Tuned Image Sorter v69.6 / Stage 055",
        "app_header_body": "v69.6 adds friend-ready QUICK_START and TROUBLESHOOTING documents; the non-technical user path is clearer. ML/pipeline/report formats are unchanged.",
        "nav_run": "Run / settings",
        "nav_progress": "Progress",
        "progress_page_help": "Progress: the overall status, progress bar and detailed stage table are moved into a separate section so they no longer consume launch-form space.",
        "show_advanced_fields": "Show advanced fields",
        "preflight": "Environment check",
        "quick_test": "Quick test",
        "backend_self_test": "Backend self-test",
        "start": "Start",
        "cancel_request": "Cancel request",
        "open_output": "Open output",
        "open_reports": "Open reports",
        "open_diagnostics": "Open diagnostics",
        "open_bug_report": "Open bug-report",
        "create_bug_report": "Create bug-report",
        "copy_summary": "Copy summary",
        "copy_paths": "Copy paths",
        "readiness_initial": "Form readiness: not checked yet.",
        "status_pending": "Status: pending — ready to start.",
        "job_meta_initial": "Job: — | events: 0 | warnings: 0 | errors: 0 | duration: —",
        "stage_header_stage": "Stage",
        "stage_header_state": "State",
        "stage_header_progress": "Progress",
        "stage_header_message": "Last message",
        "show_stage_details": "Show detailed stage progress",
        "hide_stage_details": "Hide detailed stage progress",
        "auto_scroll_logs": "Auto-scroll logs",
        "verbose_progress_events": "Verbose progress events",
        "clear_logs": "Clear logs",
        "copy_diagnostics": "Copy diagnostics",
        "events_placeholder": "Events will appear here after preflight, self-test or backend job start.",
        "events_tab": "Events / logs",
        "status_placeholder": "Validation, preflight, self-test and job issues will appear here.",
        "human_error_help": "v69.6: this section shows not only the technical error, but also a short Meaning and Action. Full tracebacks stay in diagnostics/bug-report.",
        "status_tab": "Status / errors",
        "result_placeholder": "RunResult summary will appear here after a backend job finishes.",
        "result_tab": "RunResult",
        "resume_help": "Resume and recent projects: the list comes from the UI session and unfinished result folders next to the selected input. project.json format is unchanged; continue only fills output and resume-mode in the run form.",
        "refresh_resume": "Refresh resume/recent",
        "use_selected_resume": "Use selected resume",
        "open_selected_result": "Open selected result",
        "open_selected_reports": "Open selected reports",
        "prune_recent": "Remove missing recent",
        "resume_tab": "Resume / recent",
        "reports_help": "Reports and review: choose a section on the left; the right side shows only the relevant information. reports, names.csv and review_decisions.csv formats are unchanged.",
        "reports_nav_title": "Report sections",
        "reports_nav_overview": "Overview",
        "reports_nav_files": "Report files",
        "reports_nav_problems": "Problem files",
        "reports_nav_review": "Review clusters",
        "reports_nav_apply": "Names / apply-names",
        "reports_nav_folders": "Result folders",
        "reports_overview_placeholder": "The summary for the selected result folder will appear here.",
        "reports_files_help": "Report files: select a row and press Open selected file/folder, or use the quick buttons. Missing/not created means the file is not expected for the current workflow yet; buttons for missing files are disabled.",
        "problem_files_missing_hint": "problem_files.csv may be absent after a normal successful run — this means no problem files were recorded.",
        "problem_files_help": "Problem files: read-only summary for reports/problem_files.csv. This section explains why a file was skipped: broken image, unsupported format, read/open error, decode error, timeout, or internal worker error. The CSV format is unchanged.",
        "problem_files_status_no_output": "Select a result/output folder and refresh reports to see the problem_files.csv state.",
        "problem_files_status_missing": "No problem files were recorded: problem_files.csv is absent. This is normal after a successful run.",
        "problem_files_status_present": "Problem files exist: check the categories below and open problem_files.csv for exact paths and errors.",
        "open_problem_files": "Open problem_files.csv",
        "review_decisions_missing_hint": "review_decisions.csv is not required after a normal sorting run. It is created after Save names.csv or Apply names from Review clusters.",
        "review_workflow_hint": "Quick guide: keep + Name creates a named final folder; keep without Name leaves the cluster unnamed; merge requires Merge into; review sends the cluster to final_review; ignore excludes the cluster from name application.",
        "review_workflow_status_no_output": "Select a result/output folder and refresh reports to see the Review clusters state.",
        "review_workflow_status_no_rows": "Review clusters is empty: there are no manual-decision rows, or review_clusters.csv has not been created yet.",
        "review_action_combo_tooltip": "Choose the cluster action: keep, merge, review or ignore.",
        "review_name_tooltip": "Name: future final-folder name for action=keep. Empty name does not create a named folder.",
        "review_merge_tooltip": "Merge into: target cluster_key for action=merge, for example person_001.",
        "review_notes_tooltip": "Notes: free-form comment; it does not affect ML or clustering.",
        "reports_review_help": "Review clusters: view and edit action/name/merge/notes. Work left to right: choose Action, fill Name or Merge into when needed, then save names.csv or apply names. Backend formats are unchanged.",
        "review_action_help": "Action column: keep — set/keep the name for this cluster; merge — merge into the cluster from Merge into; review — send to manual final_review; ignore — do not apply a name to this cluster. After editing, press Save names.csv or Apply names from Review clusters.",
        "review_edit_hint": "Workflow: 1) choose Action; 2) for keep fill Name, for merge fill Merge into; 3) use Notes as a comment; 4) save names.csv or apply names.",
        "apply_names_here": "Apply names from Review clusters",
        "save_names_csv_tooltip": "Save the current table decisions to names.csv and reports/review_decisions.csv without starting a backend job. Until then, review_decisions.csv may be missing; that is expected.",
        "apply_names_tooltip": "Save decisions and start the existing backend mode=apply-names for the selected result folder. This does not rescan photos; it creates final/final_review from assignments.csv and names.csv.",
        "reports_apply_help": "Names / apply-names: control page for applying names.csv. Save decisions first, then apply names. The same action is also available directly in Review clusters.",
        "reports_apply_details": "1. Check Review clusters.\n2. For keep, fill Name when you want a person/final folder. An empty name does not create a person-name folder.\n3. For merge, fill Merge into with the target cluster_key.\n4. Use review for uncertain/mixed clusters; they go to final_review.\n5. Press Save names.csv, then Apply names.\n\nApply-names does not rescan photos and does not change ML/clustering/report schema; it creates final/final_review from existing assignments.csv + names.csv.",
        "reports_folders_help": "Result folders: quick access to output, reports, diagnostics, final and final_review.",
        "review_details_placeholder": "Select a Review clusters row to see details and thumbnails.",
        "refresh_reports": "Refresh reports/review",
        "open_reports_folder": "Open reports",
        "open_selected_report": "Open selected file/folder",
        "copy_reports_summary": "Copy reports summary",
        "open_summary_csv": "Open summary.csv",
        "open_assignments_csv": "Open assignments.csv",
        "open_clusters_html": "Open clusters.html",
        "open_duplicates_csv": "Open duplicates.csv",
        "open_review_clusters_csv": "Open review_clusters.csv",
        "open_names_csv": "Open names.csv",
        "open_review_decisions": "Open review_decisions.csv",
        "save_names_csv": "Save names.csv",
        "apply_names": "Apply names",
        "open_final": "Open final",
        "open_final_review": "Open final_review",
        "reports_tab": "Reports / review",
        "settings_tab": "Help / settings",
        "settings_title": "UI settings and quick instructions",
        "settings_group": "UI settings",
        "language": "UI language",
        "theme": "Theme",
        "density": "Density",
        "show_tips": "Show startup tips",
        "confirm_run": "Confirm before run",
        "auto_open_reports": "Open reports after successful run",
        "save_settings": "Save UI settings",
        "open_session_folder": "Open session folder",
        "open_ru_guide": "Open RU guide",
        "open_en_guide": "Open EN guide",
        "open_help_ru": "Open RU help",
        "open_help_en": "Open EN help",
        "open_packaging_guide": "Open packaging guide",
        "settings_saved": "UI settings saved.",
        "run_confirm_title": "Confirm run",
        "run_confirm_body": "Start sorting with the current settings?",
        "startup_tip_title": "Tuned Image Sorter v69.6",
        "startup_tip_body": "Choose input/output, make sure output is not inside input, run Environment check and start with a small-folder quick test.",
        "browse": "Browse…",
        "auto": "Auto",
        "no_thumbnails": "No preview thumbnails were found for this cluster. Open clusters.html for the full report preview.",
        "tooltip_preflight": "Check the runtime/GPU environment without starting an ML run.",
        "tooltip_quick_test": "Checklist for the first safe small-folder test without changing backend settings.",
        "tooltip_selftest": "Check the backend/UI contract without running recognition.",
        "tooltip_start": "Start the backend job. The button is available only when the input folder is ready.",
        "tooltip_cancel": "Soft cancellation request. Hard pipeline interruption is not enabled in this build.",
        "tooltip_open_output": "Open the current result/output folder if it already exists.",
        "tooltip_open_reports": "Open the reports folder inside the current result/output.",
        "tooltip_open_diagnostics": "Open diagnostics inside result/output or reports/diagnostics if the folder exists.",
        "tooltip_open_bug_report": "Open the latest created bug-report zip.",
        "tooltip_create_bug_report": "Create a bug-report with additional UI context and diagnostics.",
        "tooltip_copy_summary": "Copy a short summary of current settings or the latest result.",
        "tooltip_copy_paths": "Copy input/output/reports/bug-report paths.",
        "support_panel_tab": "Diagnostics / Support",
        "support_panel_help": "Diagnostics / Support: a safe page for environment checks, existing result/output health-checks, support-bundle creation and quick access to diagnostics/reports/bug_reports. The summary separates CPU/GPU runtime, result-health, support-bundle and optional warnings. The buttons call the existing backend/CLI diagnostics helpers and do not start ML, the main pipeline or apply-names.",
        "support_check_environment": "Environment check",
        "support_check_environment_tooltip": "Run the same runtime-preflight as the launch page; no packages are installed and no photos are scanned.",
        "support_check_result": "Check result",
        "support_check_result_tooltip": "Run the existing result-health check for the selected output/result folder and create reports/result_health_check.json/txt.",
        "support_create_bundle": "Create support-bundle",
        "support_create_bundle_tooltip": "Create the existing bug-report/support-bundle ZIP with UI context and result-health; source photos and embeddings are not included.",
        "support_open_bug_reports": "Open bug_reports",
        "support_open_bug_reports_tooltip": "Open output/bug_reports, where support-bundle ZIP files are saved.",
        "support_open_last_bundle": "Open latest ZIP",
        "support_open_last_bundle_tooltip": "Open the latest created support-bundle/bug-report ZIP.",
        "support_copy_short_summary": "Copy short diagnostic summary",
        "support_copy_short_summary_tooltip": "Copy a compact version/output/reports/diagnostics/preflight/result-health summary without the full log.",
        "support_refresh_summary": "Refresh summary",
        "support_refresh_summary_tooltip": "Refresh the support-panel text summary without running another check.",
        "support_summary_placeholder": "A short diagnostic summary with separate CPU/GPU runtime, result-health, support-bundle and optional warning sections will appear here.",
        "support_warn_no_output": "Select an existing result/output folder first.",
        "support_warn_job_running": "Create the support-bundle after the current backend job finishes.",
        "support_path_status": "Output: {output}\nReports: {reports}\nDiagnostics: {diagnostics}\nBug reports: {bug_reports}",
        "session_label": "Session",
        "session_saved": "Session saved",
        "readiness_running": "Form readiness: backend job is running; form changes will be saved, but Start is disabled.",
        "readiness_ok": "Form readiness: OK — ready to start.",
        "readiness_warnings_prefix": "Form readiness: ready to start, with warnings: ",
        "readiness_errors_prefix": "Form readiness: Start is disabled — ",
        "readiness_input_required": "Choose the input folder with photos.",
        "readiness_input_not_found": "Input folder not found: {path}",
        "readiness_output_empty": "Output is empty: backend logic can suggest/create it, but using Auto is clearer in the UI.",
        "readiness_output_inside_input": "Output is inside input. Prefer a result folder outside the source photos so later runs do not scan generated files.",
        "readiness_output_exists": "Output already exists. Enable resume_existing_output to continue or choose a new result folder.",
        "readiness_mode_needs_existing": "Mode {mode} usually continues an existing result/project; check the output folder.",
        "path_input_required": "Input folder is required.",
        "path_input_not_found": "Input folder does not exist.",
        "path_input_ok": "Input folder exists.",
        "path_output_empty": "Output is empty. Use Auto to make the result folder explicit.",
        "path_output_inside_input": "Output is inside input. Choose a result folder outside the source photos.",
        "path_output_exists": "Output already exists. Enable resume_existing_output or choose a new folder.",
        "path_output_ok": "Output path is set.",
        "dialog_select_input": "Select the photo folder",
        "dialog_select_output": "Select the result/output folder",
        "warn_select_input": "Choose the input folder first.",
        "warn_suggest_output_failed": "Could not suggest the output folder: {error}",
        "warn_path_unknown": "Path is not known yet.",
        "warn_path_not_found": "Path not found: {path}",
        "warn_report_not_selected": "No report file is selected.",
        "warn_report_not_known": "The report file is not known yet.",
        "warn_resume_not_selected": "Select a recent/resume project first.",
        "warn_resume_result_missing": "Result folder not found: {path}",
        "close_running_job": "The backend job still appears to be running. Close the UI window anyway?\nThis build only supports soft cancellation.",
        "job_meta_empty": "Job: — | events: 0 | warnings: 0 | errors: 0 | duration: —",
        "job_meta_starting": "Job: starting | events: 0 | warnings: 0 | errors: 0 | duration: —",
        "status_starting": "Status: starting — launching backend job…",
        "status_cancel_requested": "Status: cancel requested — {stage}",
        "status_line": "Status: {state} — {stage}",
        "reports_summary_title": "reports summary",
        "run_result_title": "run result",
        "run_user_summary": "User summary",
        "problem_files_section": "Problem files",
        "explanations_section": "Explanations",
        "technical_summary_section": "Technical summary",
        "project_json_not_read": "project.json has not been read yet; technical paths are listed above.",
        "photos_processed": "photos processed: {count}",
        "summary_rows": "person clusters / summary.csv rows: {count}",
        "person_folders": "person folders created: {count}",
        "review_files_total": "review files total: {count}",
        "assignments_rows": "assignments.csv rows: {count}",
        "review_clusters_rows": "review_clusters.csv rows: {count}",
        "duplicates_rows": "duplicates.csv rows: {count}",
        "problem_files_rows": "problem_files.csv rows: {count}",
        "explain_no_faces": "review/no_faces — photos where no faces were found.",
        "explain_unknown_faces": "review/unknown_faces — faces were found, but were not assigned to a confident person cluster.",
        "explain_problem_files_missing": "problem_files.csv missing — normal when there were no read/decode/timeout/worker errors.",
        "explain_open_reports": "Open result/reports/diagnostics with the buttons above the logs; report formats are unchanged.",
        "confirm_readiness": "Readiness:",
        "confirm_warnings": "Warnings:",
        "confirm_errors": "Errors:",
        "confirm_pipeline_note": "This starts the existing backend pipeline. ML algorithms, CLI wizard and project/report formats are unchanged.",
        "schema_prefix": "UI schema",
        "help_docs_note": "Help is available in Russian and English; v69.6 adds QUICK_START_RU/EN.txt and TROUBLESHOOTING_RU/EN.txt without changing the pipeline.",
    },
}

_STAGE_TEXT: Dict[str, Dict[str, str]] = {
    "ru": {
        "validate": "Проверка настроек",
        "environment": "Проверка окружения",
        "database": "SQLite база",
        "scan": "Сканирование фото",
        "cluster": "Кластеризация",
        "assign": "Назначение фото",
        "copy": "Копирование",
        "report": "Отчёты",
        "review-clusters": "Review clusters",
        "apply-names": "Apply names",
        "bug_report": "Bug-report",
        "bug-report": "Bug-report",
        "support-bundle": "Support-bundle",
        "done": "Готово",
        "job": "Backend job",
    },
    "en": {
        "validate": "Settings validation",
        "environment": "Environment check",
        "database": "SQLite database",
        "scan": "Photo scan",
        "cluster": "Clustering",
        "assign": "Photo assignment",
        "copy": "Copy files",
        "report": "Reports",
        "review-clusters": "Review clusters",
        "apply-names": "Apply names",
        "bug_report": "Bug-report",
        "bug-report": "Bug-report",
        "support-bundle": "Support-bundle",
        "done": "Done",
        "job": "Backend job",
    },
}

def ui_text(key: str, language: Any = "auto") -> str:
    """Return a short localized UI string with English fallback."""
    lang = effective_ui_language(language)
    return _TEXT.get(lang, _TEXT["en"]).get(key, _TEXT["en"].get(key, key))


def ui_stage_text(stage: str, language: Any = "auto") -> str:
    """Return a localized short stage label for the optional GUI."""
    key = "bug_report" if stage in {"bug-report", "support-bundle"} else str(stage or "")
    lang = effective_ui_language(language)
    return _STAGE_TEXT.get(lang, _STAGE_TEXT["en"]).get(key, key or "—")


def get_ui_instruction_sections(language: Any = "auto") -> Tuple[UiInstructionSection, ...]:
    """Return localized compact instructions for the optional GUI."""
    lang = effective_ui_language(language)
    if lang == "en":
        return (
            UiInstructionSection("run", "Run workflow", (
                UiInstructionStep("1. Select input", "Pick the folder with photos. Run the app from the project root, one level above the package."),
                UiInstructionStep("2. Select output", "Use the suggested result folder or choose an existing result only when resuming."),
                UiInstructionStep("3. Check settings", "Profile, mode, GPU and workers come from the UI schema/session contract, not from duplicated wizard logic."),
                UiInstructionStep("4. Start and monitor", "Use the progress table, Events, Status and RunResult tabs. PowerShell logging stays unchanged."),
            )),
            UiInstructionSection("resume_reports", "Resume and reports", (
                UiInstructionStep("Resume", "Use Resume / recent to continue unfinished result folders without changing project.json format."),
                UiInstructionStep("Reports", "Use Reports / review to open generated reports, edit names.csv and run apply-names through the existing backend mode."),
                UiInstructionStep("Bug-report", "Create a bug-report/support-bundle from the UI or CLI when diagnostics are needed; v69.6 keeps support-bundle/result-health diagnostics intact."),
            )),
            UiInstructionSection("safe_boundaries", "Safe boundaries", (
                UiInstructionStep("No algorithm changes", "v69.6 friend-ready docs polish does not change recognition, clustering, pipeline stages, resume or existing reports formats."),
                UiInstructionStep("Windows packaging", "Packaging scripts remain in tools/windows_packaging; build from the project root."),
            )),
        )
    return (
        UiInstructionSection("run", "Запуск", (
            UiInstructionStep("1. Выберите input", "Укажите папку с фото. Запускайте приложение из корня проекта, на уровень выше пакета."),
            UiInstructionStep("2. Выберите output", "Используйте предложенную result-папку или существующую result-папку только при продолжении."),
            UiInstructionStep("3. Проверьте настройки", "Profile, mode, GPU и workers берутся из UI schema/session contract, без копирования console wizard."),
            UiInstructionStep("4. Запускайте и следите", "Используйте таблицу стадий, Events, Status и RunResult. Логи PowerShell остаются как раньше."),
        )),
        UiInstructionSection("resume_reports", "Resume и отчёты", (
            UiInstructionStep("Resume", "Вкладка Resume / recent продолжает unfinished result-папки без изменения формата project.json."),
            UiInstructionStep("Reports", "Вкладка Reports / review открывает отчёты, редактирует names.csv и запускает apply-names через существующий backend mode."),
            UiInstructionStep("Bug-report", "Создавайте bug-report/support-bundle из UI или CLI, если нужен диагностический zip; v69.6 сохраняет существующую result-health/support-bundle диагностику."),
        )),
        UiInstructionSection("safe_boundaries", "Границы безопасности", (
            UiInstructionStep("Алгоритмы не менялись", "v69.6 friend-ready docs polish не меняет распознавание, кластеризацию, pipeline stages, resume и существующие форматы reports."),
            UiInstructionStep("Windows packaging", "Скрипты упаковки остаются в tools/windows_packaging; сборку делать из корня проекта."),
        )),
    )


def ui_polish_settings_from_session(state: Any) -> UiPolishSettings:
    """Build UiPolishSettings from a UiSessionState-like object."""
    extra = getattr(state, "extra", {}) or {}
    return UiPolishSettings(
        language=normalize_ui_language(getattr(state, "language", extra.get("language", "auto"))),
        theme=normalize_ui_theme(getattr(state, "ui_theme", extra.get("ui_theme", "system"))),
        density=normalize_ui_density(getattr(state, "ui_density", extra.get("ui_density", "comfortable"))),
        show_startup_tips=_bool(getattr(state, "show_startup_tips", extra.get("show_startup_tips", True)), True),
        confirm_before_run=_bool(getattr(state, "confirm_before_run", extra.get("confirm_before_run", True)), True),
        auto_open_reports_after_run=_bool(getattr(state, "auto_open_reports_after_run", extra.get("auto_open_reports_after_run", False)), False),
        show_advanced_fields=_bool(getattr(state, "show_advanced_fields", extra.get("show_advanced_fields", False)), False),
        verbose_progress_events=_bool(getattr(state, "verbose_progress_events", extra.get("verbose_progress_events", False)), False),
        auto_scroll_logs=_bool(getattr(state, "auto_scroll_logs", extra.get("auto_scroll_logs", True)), True),
    )


def apply_ui_polish_settings_to_session(state: Any, settings: UiPolishSettings) -> Any:
    """Return a UiSessionState with UI-only polish settings persisted."""
    from .session import update_ui_session_state

    extra = dict(getattr(state, "extra", {}) or {})
    extra.update(settings.to_dict())
    return update_ui_session_state(
        state,
        language=settings.language,
        ui_theme=settings.theme,
        ui_density=settings.density,
        show_startup_tips=settings.show_startup_tips,
        confirm_before_run=settings.confirm_before_run,
        auto_open_reports_after_run=settings.auto_open_reports_after_run,
        show_advanced_fields=settings.show_advanced_fields,
        verbose_progress_events=settings.verbose_progress_events,
        auto_scroll_logs=settings.auto_scroll_logs,
        extra=extra,
    )


def ui_polish_snapshot(language: Any = "auto") -> UiPolishSnapshot:
    """Return an import-safe UI polish snapshot used by the stabilization checks."""
    return UiPolishSnapshot(
        version=SCRIPT_VERSION,
        refactor_stage=UI_POLISH_STAGE,
        schema_version=UI_POLISH_SCHEMA_VERSION,
        icon_path=SCRIPT_DIR / UI_ICON_RELATIVE_PATH,
        icon_png_path=SCRIPT_DIR / UI_ICON_PNG_RELATIVE_PATH,
        language_choices=UI_LANGUAGE_CHOICES,
        theme_choices=UI_THEME_CHOICES,
        density_choices=UI_DENSITY_CHOICES,
        instructions=get_ui_instruction_sections(language),
        notes=(
            "UI polish is additive and UI-only; it does not change ML algorithms or project/report formats.",
            "Settings are stored in UI session JSON, not in project.json.",
            "The icon asset is used by PySide6 and PyInstaller specs when available.",
        ),
    )


__all__ = [
    "UI_POLISH_SCHEMA_VERSION",
    "UI_POLISH_STAGE",
    "UI_ICON_RELATIVE_PATH",
    "UI_ICON_PNG_RELATIVE_PATH",
    "UI_LANGUAGE_CHOICES",
    "UI_THEME_CHOICES",
    "UI_DENSITY_CHOICES",
    "UiInstructionStep",
    "UiInstructionSection",
    "UiPolishSettings",
    "UiPolishSnapshot",
    "normalize_ui_language",
    "effective_ui_language",
    "normalize_ui_theme",
    "normalize_ui_density",
    "ui_text",
    "ui_stage_text",
    "get_ui_instruction_sections",
    "ui_polish_settings_from_session",
    "apply_ui_polish_settings_to_session",
    "ui_polish_snapshot",
]
