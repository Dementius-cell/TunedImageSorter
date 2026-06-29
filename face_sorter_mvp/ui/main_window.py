# -*- coding: utf-8 -*-
"""Optional PySide6 UI integration shell.

v69.6 / Этап 055 keeps the UI import-safe and still uses the existing backend
pipeline without changing recognition, clustering, project.json or report
formats.  The run form is rendered from ``core.ui_schema`` and persisted through
``core.session``; progress, events, results and errors are displayed through the
stable job/status layers.
"""
from __future__ import annotations

import csv
import importlib.util
import os
import sys
import traceback
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional, Tuple

UI_SKELETON_VERSION = 31


TOP_LEVEL_CONFIG_FIELDS = {
    "input_dir",
    "output_dir",
    "profile",
    "mode",
    "language",
    "use_gpu",
    "auto_cpu_fallback",
    "resume_existing_output",
    "make_bug_report",
}

SESSION_FIELD_NAMES = {
    "input_dir",
    "output_dir",
    "profile",
    "mode",
    "language",
    "use_gpu",
    "auto_cpu_fallback",
    "photo_assignment",
    "copy_group_photos",
    "scan_workers",
    "copy_workers",
}

STAGE_LABELS = {
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
    "done": "Готово",
    "job": "Backend job",
}

# v69.6 UI completion polish: the legacy backend still emits some
# descriptive print_stage() titles as callback stages.  Keep them as messages
# for the canonical pipeline rows instead of creating extra stale rows that can
# remain "running" after the job is already done.
STAGE_ALIASES = {
    "bug-report": "bug_report",
    "review_clusters": "review-clusters",
    "apply_names": "apply-names",
    "CPU portable scan mode": "scan",
    "Защита обработки файлов включена": "scan",
    "Защита timeout отключена": "scan",
    "Этап проверки точных дублей": "scan",
    "GPU/CUDA дал ошибку во время реального распознавания": "scan",
    "Этап кластеризации лиц": "cluster",
    "Этап назначения файлов": "assign",
    "Этап копирования файлов": "copy",
    "Готово": "done",
    "Done": "done",
}


# ---------------------------------------------------------------------------
# Import-safe helpers
# ---------------------------------------------------------------------------
def is_pyside6_available() -> bool:
    """Return True when PySide6 can be imported in the current environment."""
    return importlib.util.find_spec("PySide6") is not None


def _load_qt() -> Any:
    """Import and return the Qt modules used by the UI window."""
    try:
        from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on user environment
        raise RuntimeError(
            "PySide6 is not installed or cannot be imported. "
            "Install it with: py -m pip install PySide6"
        ) from exc
    return QtCore, QtGui, QtWidgets


def _backend() -> Any:
    """Import the stable backend facade lazily."""
    try:
        from .. import backend
    except ImportError:  # script-folder fallback, useful for manual dev runs
        import backend  # type: ignore
    return backend


def _path_text(value: Any) -> str:
    return str(value) if value not in (None, "") else ""


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on", "да"}


def _stage_key(stage: str) -> str:
    raw = str(stage or "").strip()
    return STAGE_ALIASES.get(raw, raw)


def _human_stage(stage: str) -> str:
    stage = _stage_key(stage)
    return STAGE_LABELS.get(stage, stage or "—")


# ---------------------------------------------------------------------------
# Main window factory
# ---------------------------------------------------------------------------
def create_main_window() -> Any:
    """Create and return the PySide6 main window instance.

    The class is defined inside this factory so importing ``face_sorter_mvp.ui``
    remains safe on systems without PySide6.
    """
    QtCore, QtGui, QtWidgets = _load_qt()
    backend = _backend()

    class MainWindow(QtWidgets.QMainWindow):  # type: ignore[misc]
        def __init__(self) -> None:
            super().__init__()
            self.backend = backend
            self.job = None
            self.current_config = None
            self.last_result_snapshot = None
            self.last_preflight_summary: Optional[Dict[str, Any]] = None
            self.last_preflight_result: Optional[Any] = None
            self.last_result_health_summary: Optional[Any] = None
            self.last_bug_report_path: Optional[Path] = None
            self.last_output_dir: Optional[Path] = None
            self._loading_form = False
            self._stage_rows: Dict[str, int] = {}
            self._stage_status: Dict[str, str] = {}
            self._stage_messages: Dict[str, str] = {}
            self._event_counts: Dict[str, int] = {}
            self._progress_log_state: Dict[str, Tuple[float, float, int, Optional[int]]] = {}
            self._last_status_report: Optional[Any] = None
            self._stage_order: List[str] = []
            self._last_stage_progress: Dict[str, float] = {}
            self._sections: Dict[str, Any] = {}
            self._field_specs: Dict[str, Any] = {}
            self._field_widgets: Dict[str, Any] = {}
            self._main_page_indices: Dict[str, int] = {}
            self._resume_items: List[Dict[str, Any]] = []
            self._review_snapshot: Optional[Any] = None
            self._review_rows: List[Dict[str, Any]] = []
            self._problem_rows: List[Dict[str, Any]] = []
            self._preview_thumbnail_paths: List[Path] = []
            self._ui_log_tail: List[str] = []

            self.session_path = backend.default_ui_state_path()
            try:
                self.session = backend.load_ui_session_state(self.session_path)
            except Exception as exc:
                self.session = backend.default_ui_session_state()
                self._deferred_session_error = exc
            else:
                self._deferred_session_error = None
            self.polish_settings = backend.ui_polish_settings_from_session(self.session)

            caps = backend.backend_capabilities()
            self.setWindowTitle(f"Tuned Image Sorter {caps.get('version', '')} — PySide6 UI")
            self.resize(1120, 820)
            self._apply_window_icon()

            central = QtWidgets.QWidget()
            self.setCentralWidget(central)
            root = QtWidgets.QVBoxLayout(central)
            root.setContentsMargins(6, 6, 6, 6)

            self.shell_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
            root.addWidget(self.shell_splitter, stretch=1)

            self.main_nav = QtWidgets.QListWidget()
            self.main_nav.setObjectName("mainNavigationList")
            self.main_nav.setMinimumWidth(190)
            self.main_nav.setMaximumWidth(260)
            self.main_nav.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            self.main_nav.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.main_nav.setAlternatingRowColors(False)
            self.main_nav.currentRowChanged.connect(self._on_main_nav_changed)
            self.shell_splitter.addWidget(self.main_nav)

            self.main_stack = QtWidgets.QStackedWidget()
            self.shell_splitter.addWidget(self.main_stack)
            self.shell_splitter.setStretchFactor(0, 0)
            self.shell_splitter.setStretchFactor(1, 1)
            self.shell_splitter.setCollapsible(0, False)
            self.shell_splitter.setCollapsible(1, False)
            self.shell_splitter.setSizes([220, 900])

            # Page 1: launch form and first-run guidance.
            run_page = QtWidgets.QWidget()
            run_layout = QtWidgets.QVBoxLayout(run_page)
            run_layout.setContentsMargins(8, 8, 8, 8)

            header = QtWidgets.QLabel(f"{self._t('app_header_title')}\n{self._t('app_header_body')}")
            header.setWordWrap(True)
            header.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            run_layout.addWidget(header)

            self.beginner_action_label = QtWidgets.QLabel(backend.build_beginner_action_map_text({}, language=self._ui_language()))
            self.beginner_action_label.setWordWrap(True)
            self.beginner_action_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            self.beginner_action_label.setStyleSheet("QLabel { padding: 6px; border: 1px solid #cfd8dc; border-radius: 4px; }")
            run_layout.addWidget(self.beginner_action_label)

            self.onboarding_label = QtWidgets.QLabel(backend.build_onboarding_checklist_text({}, language=self._ui_language()))
            self.onboarding_label.setWordWrap(True)
            self.onboarding_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            self.onboarding_label.setStyleSheet("QLabel { padding: 6px; border: 1px solid #d0d0d0; border-radius: 4px; }")
            run_layout.addWidget(self.onboarding_label)

            self.runtime_status_label = QtWidgets.QLabel("")
            self.runtime_status_label.setWordWrap(True)
            self.runtime_status_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            self.runtime_status_label.setStyleSheet("QLabel { padding: 6px; border: 1px solid #cfd8dc; border-radius: 4px; }")
            run_layout.addWidget(self.runtime_status_label)

            toolbar = QtWidgets.QHBoxLayout()
            run_layout.addLayout(toolbar)
            self.show_advanced_check = QtWidgets.QCheckBox(self._t("show_advanced_fields"))
            self.show_advanced_check.setChecked(bool(self.polish_settings.show_advanced_fields))
            self.show_advanced_check.stateChanged.connect(lambda *_: self._update_advanced_visibility())
            self.show_advanced_check.stateChanged.connect(lambda *_: self._schedule_session_save())
            toolbar.addWidget(self.show_advanced_check)
            toolbar.addStretch(1)
            self.session_label = QtWidgets.QLabel(f"{self._t('session_label')}: {self.session_path}")
            self.session_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            toolbar.addWidget(self.session_label)

            self.form_scroll = QtWidgets.QScrollArea()
            self.form_scroll.setWidgetResizable(True)
            self.form_widget = QtWidgets.QWidget()
            self.form_layout = QtWidgets.QVBoxLayout(self.form_widget)
            self.form_layout.setContentsMargins(4, 4, 4, 4)
            self.form_scroll.setWidget(self.form_widget)
            run_layout.addWidget(self.form_scroll, stretch=1)
            self._build_schema_form()
            self._apply_gpu_lite_default_acceleration()
            self._update_runtime_status_block()

            buttons = QtWidgets.QHBoxLayout()
            run_layout.addLayout(buttons)
            self.preflight_button = QtWidgets.QPushButton(self._t("preflight"))
            self.preflight_button.setToolTip(self._t("tooltip_preflight"))
            self.preflight_button.clicked.connect(lambda *_: self.run_preflight())
            buttons.addWidget(self.preflight_button)
            self.quick_test_button = QtWidgets.QPushButton(self._t("quick_test"))
            self.quick_test_button.setToolTip(self._t("tooltip_quick_test"))
            self.quick_test_button.clicked.connect(lambda *_: self.show_quick_test_help())
            buttons.addWidget(self.quick_test_button)
            self.selftest_button = QtWidgets.QPushButton(self._t("backend_self_test"))
            self.selftest_button.setToolTip(self._t("tooltip_selftest"))
            self.selftest_button.clicked.connect(lambda *_: self.run_self_test())
            buttons.addWidget(self.selftest_button)
            self.start_button = QtWidgets.QPushButton(self._t("start"))
            self.start_button.setToolTip(self._t("tooltip_start"))
            self.start_button.clicked.connect(lambda *_: self.start_job())
            buttons.addWidget(self.start_button)
            self.cancel_button = QtWidgets.QPushButton(self._t("cancel_request"))
            self.cancel_button.setToolTip(self._t("tooltip_cancel"))
            self.cancel_button.setEnabled(False)
            self.cancel_button.clicked.connect(lambda *_: self.cancel_job())
            buttons.addWidget(self.cancel_button)
            buttons.addStretch(1)
            self.open_output_button = QtWidgets.QPushButton(self._t("open_output"))
            self.open_output_button.setToolTip(self._t("tooltip_open_output"))
            self.open_output_button.clicked.connect(lambda *_: self.open_output_dir())
            buttons.addWidget(self.open_output_button)
            self.open_reports_button = QtWidgets.QPushButton(self._t("open_reports"))
            self.open_reports_button.setToolTip(self._t("tooltip_open_reports"))
            self.open_reports_button.clicked.connect(lambda *_: self.open_reports_dir())
            buttons.addWidget(self.open_reports_button)
            self.open_diagnostics_button = QtWidgets.QPushButton(self._t("open_diagnostics"))
            self.open_diagnostics_button.setToolTip(self._t("tooltip_open_diagnostics"))
            self.open_diagnostics_button.clicked.connect(lambda *_: self.open_diagnostics_dir())
            buttons.addWidget(self.open_diagnostics_button)
            self.open_bug_button = QtWidgets.QPushButton(self._t("open_bug_report"))
            self.open_bug_button.setToolTip(self._t("tooltip_open_bug_report"))
            self.open_bug_button.clicked.connect(lambda *_: self.open_bug_report())
            buttons.addWidget(self.open_bug_button)
            self.create_bug_button = QtWidgets.QPushButton(self._t("create_bug_report"))
            self.create_bug_button.setToolTip(self._t("tooltip_create_bug_report"))
            self.create_bug_button.clicked.connect(lambda *_: self.create_bug_report_from_ui())
            buttons.addWidget(self.create_bug_button)
            self.copy_summary_button = QtWidgets.QPushButton(self._t("copy_summary"))
            self.copy_summary_button.setToolTip(self._t("tooltip_copy_summary"))
            self.copy_summary_button.clicked.connect(lambda *_: self.copy_run_summary())
            buttons.addWidget(self.copy_summary_button)
            self.copy_paths_button = QtWidgets.QPushButton(self._t("copy_paths"))
            self.copy_paths_button.setToolTip(self._t("tooltip_copy_paths"))
            self.copy_paths_button.clicked.connect(lambda *_: self.copy_paths_summary())
            buttons.addWidget(self.copy_paths_button)

            self.readiness_label = QtWidgets.QLabel(self._t("readiness_initial"))
            self.readiness_label.setWordWrap(True)
            self.readiness_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            run_layout.addWidget(self.readiness_label)
            self._add_main_page(self._t("nav_run"), run_page)

            # Page 2: progress and stage details.
            progress_page = QtWidgets.QWidget()
            progress_layout = QtWidgets.QVBoxLayout(progress_page)
            progress_layout.setContentsMargins(8, 8, 8, 8)
            progress_intro = QtWidgets.QLabel(self._t("progress_page_help"))
            progress_intro.setWordWrap(True)
            progress_layout.addWidget(progress_intro)

            self.stage_label = QtWidgets.QLabel(self._t("status_pending"))
            progress_layout.addWidget(self.stage_label)
            self.progress = QtWidgets.QProgressBar()
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            progress_layout.addWidget(self.progress)

            self.job_meta_label = QtWidgets.QLabel(self._t("job_meta_initial"))
            self.job_meta_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            progress_layout.addWidget(self.job_meta_label)

            stage_details_controls = QtWidgets.QHBoxLayout()
            progress_layout.addLayout(stage_details_controls)
            self.stage_details_toggle = QtWidgets.QToolButton()
            self.stage_details_toggle.setCheckable(True)
            self.stage_details_toggle.setChecked(True)
            self.stage_details_toggle.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
            self.stage_details_toggle.clicked.connect(lambda checked: self._set_stage_details_visible(bool(checked)))
            stage_details_controls.addWidget(self.stage_details_toggle)
            stage_details_controls.addStretch(1)

            self.stage_details_container = QtWidgets.QWidget()
            stage_details_layout = QtWidgets.QVBoxLayout(self.stage_details_container)
            stage_details_layout.setContentsMargins(0, 0, 0, 0)
            self.stage_table = QtWidgets.QTableWidget(0, 4)
            self.stage_table.setHorizontalHeaderLabels([self._t("stage_header_stage"), self._t("stage_header_state"), self._t("stage_header_progress"), self._t("stage_header_message")])
            self.stage_table.verticalHeader().setVisible(False)
            self.stage_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self.stage_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.stage_table.horizontalHeader().setStretchLastSection(True)
            stage_details_layout.addWidget(self.stage_table)
            progress_layout.addWidget(self.stage_details_container, stretch=1)
            self._set_stage_details_visible(True)
            self._add_main_page(self._t("nav_progress"), progress_page)

            # Page 3: events and log controls.
            events_page = QtWidgets.QWidget()
            events_layout = QtWidgets.QVBoxLayout(events_page)
            events_layout.setContentsMargins(8, 8, 8, 8)
            log_controls = QtWidgets.QHBoxLayout()
            events_layout.addLayout(log_controls)
            self.auto_scroll_check = QtWidgets.QCheckBox(self._t("auto_scroll_logs"))
            self.auto_scroll_check.setChecked(bool(self.polish_settings.auto_scroll_logs))
            self.auto_scroll_check.stateChanged.connect(lambda *_: self._schedule_session_save())
            log_controls.addWidget(self.auto_scroll_check)
            self.verbose_progress_check = QtWidgets.QCheckBox(self._t("verbose_progress_events"))
            self.verbose_progress_check.setChecked(bool(self.polish_settings.verbose_progress_events))
            self.verbose_progress_check.stateChanged.connect(lambda *_: self._schedule_session_save())
            log_controls.addWidget(self.verbose_progress_check)
            self.clear_logs_button = QtWidgets.QPushButton(self._t("clear_logs"))
            self.clear_logs_button.clicked.connect(lambda *_: self.clear_logs())
            log_controls.addWidget(self.clear_logs_button)
            self.copy_diagnostics_button = QtWidgets.QPushButton(self._t("copy_diagnostics"))
            self.copy_diagnostics_button.clicked.connect(lambda *_: self.copy_diagnostics())
            log_controls.addWidget(self.copy_diagnostics_button)
            log_controls.addStretch(1)
            self.events_log = QtWidgets.QTextEdit()
            self.events_log.setReadOnly(True)
            self.events_log.setPlaceholderText(self._t("events_placeholder"))
            events_layout.addWidget(self.events_log, stretch=1)
            self._add_main_page(self._t("events_tab"), events_page)

            # Page 4: status/errors.
            status_page = QtWidgets.QWidget()
            status_layout = QtWidgets.QVBoxLayout(status_page)
            status_layout.setContentsMargins(8, 8, 8, 8)
            self.human_error_help_label = QtWidgets.QLabel(self._t("human_error_help"))
            self.human_error_help_label.setWordWrap(True)
            self.human_error_help_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            self.human_error_help_label.setStyleSheet("QLabel { padding: 6px; border: 1px solid #d0d0d0; border-radius: 4px; }")
            status_layout.addWidget(self.human_error_help_label)
            self.status_log = QtWidgets.QTextEdit()
            self.status_log.setReadOnly(True)
            self.status_log.setPlaceholderText(self._t("status_placeholder"))
            status_layout.addWidget(self.status_log, stretch=1)
            self._add_main_page(self._t("status_tab"), status_page)

            # Page 5: run result summary and post-run actions.
            result_page = QtWidgets.QWidget()
            result_layout = QtWidgets.QVBoxLayout(result_page)
            result_layout.setContentsMargins(8, 8, 8, 8)
            self.post_run_actions_label = QtWidgets.QLabel(self._tx(
                "После запуска здесь появятся быстрые действия: people, review, reports, diagnostics, final/final_review и support-bundle.",
                "After a run this area will show quick actions: people, review, reports, diagnostics, final/final_review and support-bundle.",
            ))
            self.post_run_actions_label.setWordWrap(True)
            self.post_run_actions_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            self.post_run_actions_label.setStyleSheet("QLabel { padding: 6px; border: 1px solid #d0d0d0; border-radius: 4px; }")
            result_layout.addWidget(self.post_run_actions_label)
            result_actions = QtWidgets.QGridLayout()
            result_layout.addLayout(result_actions)
            self.open_people_button = QtWidgets.QPushButton(self._tx("Открыть people", "Open people"))
            self.open_people_button.clicked.connect(lambda *_: self.open_people_dir())
            result_actions.addWidget(self.open_people_button, 0, 0)
            self.open_review_button = QtWidgets.QPushButton(self._tx("Открыть review", "Open review"))
            self.open_review_button.clicked.connect(lambda *_: self.open_review_dir())
            result_actions.addWidget(self.open_review_button, 0, 1)
            self.open_reports_from_result_button = QtWidgets.QPushButton(self._t("open_reports"))
            self.open_reports_from_result_button.clicked.connect(lambda *_: self.open_reports_dir())
            result_actions.addWidget(self.open_reports_from_result_button, 0, 2)
            self.open_diagnostics_from_result_button = QtWidgets.QPushButton(self._t("open_diagnostics"))
            self.open_diagnostics_from_result_button.clicked.connect(lambda *_: self.open_diagnostics_dir())
            result_actions.addWidget(self.open_diagnostics_from_result_button, 0, 3)
            self.open_bug_reports_from_result_button = QtWidgets.QPushButton(self._t("support_open_bug_reports"))
            self.open_bug_reports_from_result_button.clicked.connect(lambda *_: self.open_bug_reports_dir())
            result_actions.addWidget(self.open_bug_reports_from_result_button, 1, 0)
            self.open_latest_zip_from_result_button = QtWidgets.QPushButton(self._t("support_open_last_bundle"))
            self.open_latest_zip_from_result_button.clicked.connect(lambda *_: self.open_bug_report())
            result_actions.addWidget(self.open_latest_zip_from_result_button, 1, 1)
            self.open_final_from_result_button = QtWidgets.QPushButton(self._t("open_final"))
            self.open_final_from_result_button.clicked.connect(lambda *_: self.open_final_dir())
            result_actions.addWidget(self.open_final_from_result_button, 1, 2)
            self.open_final_review_from_result_button = QtWidgets.QPushButton(self._t("open_final_review"))
            self.open_final_review_from_result_button.clicked.connect(lambda *_: self.open_final_review_dir())
            result_actions.addWidget(self.open_final_review_from_result_button, 1, 3)
            self.result_log = QtWidgets.QTextEdit()
            self.result_log.setReadOnly(True)
            self.result_log.setPlaceholderText(self._t("result_placeholder"))
            result_layout.addWidget(self.result_log, stretch=1)
            self._add_main_page(self._t("result_tab"), result_page)

            self._build_resume_recent_tab()
            self._build_reports_review_tab()
            self._build_diagnostics_support_tab()
            self._build_help_settings_tab()
            if self.main_nav.count() > 0:
                self.main_nav.setCurrentRow(0)

            self.session_save_timer = QtCore.QTimer(self)
            self.session_save_timer.setSingleShot(True)
            self.session_save_timer.setInterval(350)
            self.session_save_timer.timeout.connect(self.save_session_from_form)

            self.timer = QtCore.QTimer(self)
            self.timer.setInterval(350)
            self.timer.timeout.connect(self.poll_job)

            self._log_event("UI loaded. PySide6 is active; backend API is importable.")
            self._log_event(
                f"Backend: {caps.get('version')} / {caps.get('refactor_stage')} / "
                f"ui_api_version={caps.get('ui_api_version')}"
            )
            if self._deferred_session_error is not None:
                self._log_status_report(
                    backend.ui_status_report(
                        (backend.issue_from_exception(self._deferred_session_error, source="backend", code="ui_session_load_error", include_traceback=False),),
                        summary="UI session was reset to defaults",
                    )
                )
            self._init_stage_table([])
            self.refresh_resume_projects(initial=True)
            self.refresh_reports_review(initial=True)
            self.update_result_buttons()
            self._update_form_readiness()
            self._apply_ui_theme_density()
            self._update_runtime_status_block()
            self._update_beginner_action_block()
            self._update_onboarding_block()
            if bool(self.polish_settings.show_startup_tips):
                self._log_event(f"[tip] {backend.ui_text('startup_tip_body', self.polish_settings.language)}")

        def _add_main_page(self, label: str, widget: Any) -> int:
            """Add a page to the left-navigation shell and return its stack index."""
            index = self.main_stack.addWidget(widget)
            item = QtWidgets.QListWidgetItem(str(label))
            item.setData(QtCore.Qt.UserRole, index)
            item.setToolTip(str(label))
            self.main_nav.addItem(item)
            self._main_page_indices[str(label)] = index
            return index

        def _on_main_nav_changed(self, row: int) -> None:
            if not hasattr(self, "main_nav") or not hasattr(self, "main_stack"):
                return
            item = self.main_nav.item(row)
            if item is None:
                return
            index = item.data(QtCore.Qt.UserRole)
            try:
                self.main_stack.setCurrentIndex(int(index))
            except Exception:
                self.main_stack.setCurrentIndex(0)

        def _select_main_page(self, label: str) -> None:
            """Select a left-navigation page by its visible label."""
            if not hasattr(self, "main_nav"):
                return
            for row in range(self.main_nav.count()):
                item = self.main_nav.item(row)
                if item is not None and item.text() == str(label):
                    self.main_nav.setCurrentRow(row)
                    return

        def eventFilter(self, obj: Any, event: Any) -> bool:  # noqa: N802 - Qt override name
            if hasattr(self, "preview_scroll") and obj is self.preview_scroll.viewport():
                if event.type() == QtCore.QEvent.Resize and getattr(self, "_preview_thumbnail_paths", None):
                    QtCore.QTimer.singleShot(0, self._rebuild_preview_grid)
            return super().eventFilter(obj, event)

        # ------------------------------------------------------------------
        # Resume/recent projects UI
        # ------------------------------------------------------------------
        def _build_resume_recent_tab(self) -> None:
            self.resume_tab = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(self.resume_tab)

            help_label = QtWidgets.QLabel(self._t("resume_help"))
            help_label.setWordWrap(True)
            layout.addWidget(help_label)

            controls = QtWidgets.QHBoxLayout()
            layout.addLayout(controls)
            self.refresh_resume_button = QtWidgets.QPushButton(self._t("refresh_resume"))
            self.refresh_resume_button.clicked.connect(lambda *_: self.refresh_resume_projects())
            controls.addWidget(self.refresh_resume_button)
            self.use_resume_button = QtWidgets.QPushButton(self._t("use_selected_resume"))
            self.use_resume_button.clicked.connect(lambda *_: self.use_selected_resume_project())
            controls.addWidget(self.use_resume_button)
            self.open_selected_project_button = QtWidgets.QPushButton(self._t("open_selected_result"))
            self.open_selected_project_button.clicked.connect(lambda *_: self.open_selected_resume_project())
            controls.addWidget(self.open_selected_project_button)
            self.open_selected_reports_button = QtWidgets.QPushButton(self._t("open_selected_reports"))
            self.open_selected_reports_button.clicked.connect(lambda *_: self.open_selected_resume_reports())
            controls.addWidget(self.open_selected_reports_button)
            self.open_selected_diagnostics_button = QtWidgets.QPushButton(self._t("open_diagnostics"))
            self.open_selected_diagnostics_button.clicked.connect(lambda *_: self.open_selected_resume_diagnostics())
            controls.addWidget(self.open_selected_diagnostics_button)
            self.open_selected_bug_reports_button = QtWidgets.QPushButton(self._t("support_open_bug_reports"))
            self.open_selected_bug_reports_button.clicked.connect(lambda *_: self.open_selected_resume_bug_reports())
            controls.addWidget(self.open_selected_bug_reports_button)
            self.open_selected_final_button = QtWidgets.QPushButton(self._t("open_final"))
            self.open_selected_final_button.clicked.connect(lambda *_: self.open_selected_resume_final())
            controls.addWidget(self.open_selected_final_button)
            self.open_selected_final_review_button = QtWidgets.QPushButton(self._t("open_final_review"))
            self.open_selected_final_review_button.clicked.connect(lambda *_: self.open_selected_resume_final_review())
            controls.addWidget(self.open_selected_final_review_button)
            self.prune_recent_button = QtWidgets.QPushButton(self._t("prune_recent"))
            self.prune_recent_button.clicked.connect(lambda *_: self.prune_missing_recent_projects())
            controls.addWidget(self.prune_recent_button)
            controls.addStretch(1)

            self.resume_table = QtWidgets.QTableWidget(0, 7)
            self.resume_table.setHorizontalHeaderLabels(self._headers("resume"))
            self.resume_table.verticalHeader().setVisible(False)
            self.resume_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self.resume_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.resume_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.resume_table.horizontalHeader().setStretchLastSection(True)
            self.resume_table.itemSelectionChanged.connect(self._on_resume_selection_changed)
            layout.addWidget(self.resume_table, stretch=2)

            self.resume_details = QtWidgets.QTextEdit()
            self.resume_details.setReadOnly(True)
            layout.addWidget(self.resume_details, stretch=1)
            self._add_main_page(self._t("resume_tab"), self.resume_tab)

        def _current_input_path_from_form(self) -> Optional[Path]:
            try:
                text = str(self._read_widget_value("input_dir") or "").strip()
                return Path(text) if text else None
            except Exception:
                return None

        def _summary_to_resume_item(self, summary: Any, source: str) -> Dict[str, Any]:
            output_path = Path(summary.output_dir or summary.path or "")
            use_gpu = bool(getattr(summary, "use_gpu", False))
            return {
                "source": source,
                "path": Path(summary.path),
                "summary": summary,
                "exists": bool(summary.exists),
                "input_dir": str(summary.input_dir or ""),
                "output_dir": str(summary.output_dir or summary.path or ""),
                "status": str(summary.status or "unknown"),
                "stage": str(summary.stage or summary.last_successful_stage or ""),
                "resume_mode": str(summary.resume_mode or "all"),
                "profile": str(getattr(summary, "profile", "") or ("gpu" if use_gpu else "cpu")),
                "runtime": "GPU" if use_gpu else "CPU",
                "updated_at": str(summary.updated_at or summary.finished_at or summary.started_at or ""),
                "started_at": str(getattr(summary, "started_at", "") or ""),
                "finished_at": str(getattr(summary, "finished_at", "") or ""),
                "display_text": str(summary.display_text or ""),
                "quick_state": self._quick_result_state(output_path),
                "can_resume": bool(summary.can_resume),
            }

        def _recent_to_resume_item(self, recent: Any) -> Dict[str, Any]:
            path = Path(recent.path)
            if path.exists():
                try:
                    return self._summary_to_resume_item(backend.inspect_project(path), "recent")
                except Exception:
                    pass
            return {
                "source": "recent missing",
                "path": path,
                "summary": None,
                "exists": bool(path.exists()),
                "input_dir": str(getattr(recent, "input_dir", "") or ""),
                "output_dir": str(getattr(recent, "output_dir", "") or path),
                "status": str(getattr(recent, "status", "missing") or "missing"),
                "stage": str(getattr(recent, "last_successful_stage", "") or ""),
                "resume_mode": "all",
                "profile": "",
                "runtime": "—",
                "updated_at": str(getattr(recent, "updated_at", "") or ""),
                "started_at": "",
                "finished_at": "",
                "display_text": str(getattr(recent, "display_text", "") or ""),
                "quick_state": self._quick_result_state(path),
                "can_resume": False,
            }

        def refresh_resume_projects(self, *, initial: bool = False) -> None:
            items: List[Dict[str, Any]] = []
            seen: Dict[str, int] = {}

            def add_item(item: Dict[str, Any]) -> None:
                key = str(Path(item["path"]).expanduser()).lower()
                if key in seen:
                    existing = items[seen[key]]
                    if item["source"] not in str(existing.get("source", "")):
                        existing["source"] = f"{existing['source']} + {item['source']}"
                    if not existing.get("can_resume") and item.get("can_resume"):
                        existing.update(item)
                    return
                seen[key] = len(items)
                items.append(item)

            for recent in getattr(self.session, "recent_projects", ()):
                add_item(self._recent_to_resume_item(recent))

            input_path = self._current_input_path_from_form()
            if input_path:
                try:
                    for summary in backend.find_resume_projects(input_path):
                        add_item(self._summary_to_resume_item(summary, "resume candidate"))
                except Exception as exc:
                    if not initial:
                        self._log_status_report(
                            backend.ui_status_report(
                                (backend.issue_from_exception(exc, source="resume", code="resume_scan_failed", include_traceback=False),),
                                summary="Resume candidate scan failed",
                            )
                        )

            items.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
            self._resume_items = items
            self._render_resume_table()
            if not initial:
                self._log_event(self._tx(f"[resume] Обновлено: {len(items)} recent/resume project(s).", f"[resume] Refreshed: {len(items)} recent/resume project(s)."))

        def _render_resume_table(self) -> None:
            self.resume_table.setRowCount(0)
            for item in self._resume_items:
                row = self.resume_table.rowCount()
                self.resume_table.insertRow(row)
                values = [
                    item.get("source", ""),
                    str(item.get("path") or ""),
                    item.get("status", ""),
                    item.get("stage", ""),
                    item.get("profile", ""),
                    item.get("runtime", ""),
                    item.get("updated_at", ""),
                    item.get("quick_state", ""),
                    item.get("input_dir", ""),
                ]
                for column, value in enumerate(values):
                    cell = QtWidgets.QTableWidgetItem(str(value))
                    if column == 0 and not item.get("exists", False):
                        cell.setText(str(value) + " ⚠")
                    self.resume_table.setItem(row, column, cell)
            self.resume_table.resizeColumnsToContents()
            self._update_resume_buttons()
            if self._resume_items and self.resume_table.currentRow() < 0:
                self.resume_table.selectRow(0)
            elif not self._resume_items:
                self.resume_details.setPlainText(self._tx("Нет recent/resume проектов. Выберите input-папку и нажмите «Обновить resume/recent».", "No recent/resume projects. Choose an input folder and press Refresh resume/recent."))

        def _selected_resume_item(self) -> Optional[Dict[str, Any]]:
            row = self.resume_table.currentRow()
            if row < 0 or row >= len(self._resume_items):
                return None
            return self._resume_items[row]

        def _on_resume_selection_changed(self) -> None:
            item = self._selected_resume_item()
            self._update_resume_buttons()
            if item is None:
                self.resume_details.setPlainText(self._tx("Проект не выбран.", "No project selected."))
                return
            self.resume_details.setPlainText(self._format_resume_item_details(item))

        def _update_resume_buttons(self) -> None:
            item = self._selected_resume_item()
            exists = bool(item and item.get("exists"))
            self.use_resume_button.setEnabled(bool(item and exists))
            self.open_selected_project_button.setEnabled(exists)
            output = Path(item["path"]) if item and item.get("path") else None
            reports = output / "reports" if output else None
            diagnostics = self._diagnostics_candidate_for_output(output) if output else None
            bug_reports = output / "bug_reports" if output else None
            final = output / "final" if output else None
            final_review = output / "final_review" if output else None
            self.open_selected_reports_button.setEnabled(bool(reports and reports.exists()))
            self.open_selected_diagnostics_button.setEnabled(bool(diagnostics and diagnostics.exists()))
            self.open_selected_bug_reports_button.setEnabled(bool(bug_reports and bug_reports.exists()))
            self.open_selected_final_button.setEnabled(bool(final and final.exists()))
            self.open_selected_final_review_button.setEnabled(bool(final_review and final_review.exists()))

        def _diagnostics_candidate_for_output(self, output: Optional[Path]) -> Optional[Path]:
            if not output:
                return None
            output = Path(output)
            for candidate in (output / "diagnostics", output / "reports" / "diagnostics"):
                if candidate.exists():
                    return candidate
            return output / "diagnostics"

        def _quick_result_state(self, output: Optional[Path]) -> str:
            if not output:
                return "—"
            output = Path(output)
            if not output.exists():
                return self._tx("missing", "missing")
            reports = output / "reports"
            people = output / "people"
            final = output / "final"
            final_review = output / "final_review"
            parts = []
            parts.append("reports OK" if reports.exists() else self._tx("reports нет", "reports missing"))
            parts.append("people OK" if people.exists() else self._tx("people нет", "people missing"))
            parts.append("final OK" if final.exists() else self._tx("final после apply-names", "final after apply-names"))
            parts.append("final_review OK" if final_review.exists() else self._tx("final_review опционально", "final_review optional"))
            return "; ".join(parts)

        def _result_action_lines(self, output: Optional[Path]) -> List[str]:
            if not output:
                return [self._tx("result/output пока не выбран.", "No result/output folder is selected yet.")]
            output = Path(output)
            lines: List[str] = [f"output: {output}"]
            if not output.exists():
                lines.append(self._tx("- result/output папка отсутствует: быстрые действия будут доступны после создания результата.", "- result/output folder is missing: quick actions become available after a run creates it."))
                return lines
            reports = output / "reports"
            diagnostics = self._diagnostics_candidate_for_output(output)
            entries = [
                ("people", output / "people", self._tx("создаётся обычной сортировкой", "created by the regular sort")),
                ("review", output / "review", self._tx("создаётся обычной сортировкой", "created by the regular sort")),
                ("reports", reports, self._tx("создаётся на этапе report", "created by the report stage")),
                ("diagnostics", diagnostics, self._tx("может быть в output/diagnostics или reports/diagnostics", "may be in output/diagnostics or reports/diagnostics")),
                ("bug_reports", output / "bug_reports", self._tx("появляется после создания support-bundle/bug-report", "appears after creating a support-bundle/bug-report")),
                ("final", output / "final", self._tx("появляется после apply-names", "appears after apply-names")),
                ("final_review", output / "final_review", self._tx("может отсутствовать нормально, если нет action=review", "may be absent normally when no rows use action=review")),
            ]
            for label, path, missing_note in entries:
                state = self._tx("есть", "exists") if path and path.exists() else missing_note
                lines.append(f"- {label}: {state} — {path}")
            problem = reports / "problem_files.csv"
            review_decisions = reports / "review_decisions.csv"
            lines.append("- problem_files.csv: " + (self._tx("есть", "exists") if problem.exists() else self._t("problem_files_status_missing")))
            lines.append("- review_decisions.csv: " + (self._tx("есть", "exists") if review_decisions.exists() else self._t("review_decisions_missing_hint")))
            if self.last_bug_report_path:
                lines.append(f"- latest support-bundle ZIP: {self.last_bug_report_path}")
                lines.append(self._tx("  note: support-bundle не содержит исходные фото/embeddings.", "  note: the support-bundle does not include source photos or embeddings."))
            return lines

        def _post_run_action_status_text(self) -> str:
            output = self.output_path_from_ui_or_result()
            mode = str(getattr(self.current_config, "mode", "") or "")
            lines: List[str] = []
            if self.last_result_snapshot is not None:
                state = str(getattr(self.last_result_snapshot, "state", "") or "")
                result_status = str(getattr(self.last_result_snapshot, "result_status", "") or state)
                lines.append(self._tx(f"Последний запуск: {result_status}.", f"Last run: {result_status}."))
            else:
                lines.append(self._tx("Быстрые действия обновляются по выбранной result/output папке.", "Quick actions follow the selected result/output folder."))
            if mode == "apply-names":
                lines.append(self._tx("Workflow: apply-names. Главные следующие папки — final и, если были review-решения, final_review.", "Workflow: apply-names. The main next folders are final and, if review decisions existed, final_review."))
            else:
                lines.append(self._tx("Workflow: обычная сортировка. Сначала проверяйте people/review/reports/diagnostics; final/final_review появляются только после apply-names.", "Workflow: regular sort. Check people/review/reports/diagnostics first; final/final_review appear only after apply-names."))
            lines.extend(self._result_action_lines(output))
            return "\n".join(lines)

        def _update_post_run_actions_label(self) -> None:
            if hasattr(self, "post_run_actions_label"):
                self.post_run_actions_label.setText(self._post_run_action_status_text())

        def _format_resume_item_details(self, item: Dict[str, Any]) -> str:
            summary = item.get("summary")
            lines = [
                f"source: {item.get('source', '')}",
                f"path: {item.get('path', '')}",
                f"exists: {item.get('exists', False)}",
                f"status: {item.get('status', '')}",
                f"stage: {item.get('stage', '')}",
                f"resume_mode: {item.get('resume_mode', '')}",
                f"input_dir: {item.get('input_dir', '')}",
                f"output_dir: {item.get('output_dir', '')}",
                f"updated_at: {item.get('updated_at', '')}",
            ]
            if summary is not None:
                lines.extend([
                    f"last_successful_stage: {summary.last_successful_stage}",
                    f"profile: {summary.profile}",
                    f"use_gpu: {summary.use_gpu}",
                    f"started_at: {summary.started_at}",
                    f"finished_at: {summary.finished_at}",
                    f"files_total: {summary.files_total if summary.files_total is not None else ''}",
                    f"files_scanned: {summary.files_scanned}",
                    f"copy_total: {summary.copy_total if summary.copy_total is not None else ''}",
                    f"files_copied: {summary.files_copied}",
                    f"has_database: {summary.has_database}",
                    f"can_resume: {summary.can_resume}",
                ])
                if summary.error:
                    lines.extend(["", "error:", summary.error])
            output = Path(item.get("path")) if item.get("path") else None
            lines.extend(["", self._tx("Быстрые действия / состояния:", "Quick actions / states:"), *self._result_action_lines(output)])
            if item.get("display_text"):
                lines.extend(["", "display:", str(item.get("display_text"))])
            return "\n".join(lines)

        def use_selected_resume_project(self) -> None:
            item = self._selected_resume_item()
            if item is None:
                self._warn(self._t("warn_resume_not_selected"))
                return
            path = Path(item["path"])
            if not path.exists():
                self._warn(self._t("warn_resume_result_missing", path=path))
                return
            if item.get("input_dir") and "input_dir" in self._field_widgets:
                self._set_widget_value("input_dir", item.get("input_dir"))
            if "output_dir" in self._field_widgets:
                self._set_widget_value("output_dir", str(path))
            if "mode" in self._field_widgets:
                self._set_widget_value("mode", item.get("resume_mode") or "all")
            if "resume_existing_output" in self._field_widgets:
                self._set_widget_value("resume_existing_output", True)
            self.last_output_dir = path
            self._schedule_session_save()
            self.update_result_buttons()
            self._log_event(self._tx(f"[resume] Выбран для продолжения: {path} (mode={item.get('resume_mode') or 'all'})", f"[resume] Selected for resume: {path} (mode={item.get('resume_mode') or 'all'})"))

        def open_selected_resume_project(self) -> None:
            item = self._selected_resume_item()
            self._open_path(Path(item["path"]) if item else None)

        def open_selected_resume_reports(self) -> None:
            item = self._selected_resume_item()
            self._open_path((Path(item["path"]) / "reports") if item else None)

        def open_selected_resume_diagnostics(self) -> None:
            item = self._selected_resume_item()
            output = Path(item["path"]) if item else None
            self._open_path(self._diagnostics_candidate_for_output(output) if output else None)

        def open_selected_resume_bug_reports(self) -> None:
            item = self._selected_resume_item()
            self._open_path((Path(item["path"]) / "bug_reports") if item else None)

        def open_selected_resume_final(self) -> None:
            item = self._selected_resume_item()
            self._open_path((Path(item["path"]) / "final") if item else None)

        def open_selected_resume_final_review(self) -> None:
            item = self._selected_resume_item()
            self._open_path((Path(item["path"]) / "final_review") if item else None)

        def prune_missing_recent_projects(self) -> None:
            try:
                before = len(getattr(self.session, "recent_projects", ()))
                self.session = backend.prune_recent_projects(self.session, existing_only=True)
                backend.save_ui_session_state(self.session, self.session_path)
                after = len(getattr(self.session, "recent_projects", ()))
                self.refresh_resume_projects()
                self._log_event(f"[session] Missing recent projects removed: {before - after}")
            except Exception as exc:
                self._log_status_report(
                    backend.ui_status_report(
                        (backend.issue_from_exception(exc, source="session", code="recent_prune_failed", include_traceback=False),),
                        summary="Recent project pruning failed",
                    )
                )

        # ------------------------------------------------------------------
        # Reports / review UI
        # ------------------------------------------------------------------
        def _build_reports_review_tab(self) -> None:
            self.reports_tab = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(self.reports_tab)

            help_label = QtWidgets.QLabel(self._t("reports_help"))
            help_label.setWordWrap(True)
            layout.addWidget(help_label)

            reports_split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
            layout.addWidget(reports_split, stretch=1)

            nav_panel = QtWidgets.QWidget()
            nav_layout = QtWidgets.QVBoxLayout(nav_panel)
            nav_layout.setContentsMargins(0, 0, 6, 0)
            nav_title = QtWidgets.QLabel(self._t("reports_nav_title"))
            nav_title.setWordWrap(True)
            nav_layout.addWidget(nav_title)
            self.reports_nav_tree = QtWidgets.QTreeWidget()
            self.reports_nav_tree.setHeaderHidden(True)
            self.reports_nav_tree.setRootIsDecorated(False)
            self.reports_nav_tree.setMaximumWidth(240)
            self.reports_nav_tree.setMinimumWidth(180)
            nav_layout.addWidget(self.reports_nav_tree, stretch=1)
            reports_split.addWidget(nav_panel)

            self.reports_stack = QtWidgets.QStackedWidget()
            reports_split.addWidget(self.reports_stack)
            reports_split.setStretchFactor(0, 0)
            reports_split.setStretchFactor(1, 1)
            reports_split.setSizes([210, 850])

            # Page 0: compact overview and report summary.
            overview_page = QtWidgets.QWidget()
            overview_layout = QtWidgets.QVBoxLayout(overview_page)
            overview_layout.setContentsMargins(0, 0, 0, 0)
            overview_controls = QtWidgets.QHBoxLayout()
            overview_layout.addLayout(overview_controls)
            self.refresh_reports_button = QtWidgets.QPushButton(self._t("refresh_reports"))
            self.refresh_reports_button.clicked.connect(lambda *_: self.refresh_reports_review())
            overview_controls.addWidget(self.refresh_reports_button)
            self.open_reports_folder_button = QtWidgets.QPushButton(self._t("open_reports_folder"))
            self.open_reports_folder_button.clicked.connect(lambda *_: self.open_reports_dir())
            overview_controls.addWidget(self.open_reports_folder_button)
            self.open_diagnostics_from_reports_button = QtWidgets.QPushButton(self._t("open_diagnostics"))
            self.open_diagnostics_from_reports_button.clicked.connect(lambda *_: self.open_diagnostics_dir())
            overview_controls.addWidget(self.open_diagnostics_from_reports_button)
            self.copy_reports_summary_button = QtWidgets.QPushButton(self._t("copy_reports_summary"))
            self.copy_reports_summary_button.clicked.connect(lambda *_: self.copy_reports_summary())
            overview_controls.addWidget(self.copy_reports_summary_button)
            overview_controls.addStretch(1)
            self.reports_details = QtWidgets.QTextEdit()
            self.reports_details.setReadOnly(True)
            self.reports_details.setPlaceholderText(self._t("reports_overview_placeholder"))
            overview_layout.addWidget(self.reports_details, stretch=1)
            self.reports_stack.addWidget(overview_page)

            # Page 1: generated report files.  This replaces the dense row of
            # file buttons from v69.6 with a labeled section and a table.
            files_page = QtWidgets.QWidget()
            files_layout = QtWidgets.QVBoxLayout(files_page)
            files_layout.setContentsMargins(0, 0, 0, 0)
            file_help = QtWidgets.QLabel(self._t("reports_files_help"))
            file_help.setWordWrap(True)
            files_layout.addWidget(file_help)
            self.review_decisions_files_note = QtWidgets.QLabel(self._t("review_decisions_missing_hint"))
            self.review_decisions_files_note.setWordWrap(True)
            self.review_decisions_files_note.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            self.review_decisions_files_note.setStyleSheet("QLabel { padding: 6px; border: 1px solid #d0d0d0; border-radius: 4px; }")
            files_layout.addWidget(self.review_decisions_files_note)
            file_controls = QtWidgets.QGridLayout()
            files_layout.addLayout(file_controls)
            self.open_summary_csv_button = QtWidgets.QPushButton(self._t("open_summary_csv"))
            self.open_summary_csv_button.clicked.connect(lambda *_: self._open_review_report_file("summary_csv"))
            file_controls.addWidget(self.open_summary_csv_button, 0, 0)
            self.open_assignments_csv_button = QtWidgets.QPushButton(self._t("open_assignments_csv"))
            self.open_assignments_csv_button.clicked.connect(lambda *_: self._open_review_report_file("assignments_csv"))
            file_controls.addWidget(self.open_assignments_csv_button, 0, 1)
            self.open_clusters_html_button = QtWidgets.QPushButton(self._t("open_clusters_html"))
            self.open_clusters_html_button.clicked.connect(lambda *_: self._open_review_report_file("clusters_html"))
            file_controls.addWidget(self.open_clusters_html_button, 1, 0)
            self.open_duplicates_csv_button = QtWidgets.QPushButton(self._t("open_duplicates_csv"))
            self.open_duplicates_csv_button.clicked.connect(lambda *_: self._open_review_report_file("duplicates_csv"))
            file_controls.addWidget(self.open_duplicates_csv_button, 1, 1)
            self.open_review_clusters_csv_button = QtWidgets.QPushButton(self._t("open_review_clusters_csv"))
            self.open_review_clusters_csv_button.clicked.connect(lambda *_: self._open_review_report_file("review_clusters_csv"))
            file_controls.addWidget(self.open_review_clusters_csv_button, 2, 0)
            self.open_names_csv_button = QtWidgets.QPushButton(self._t("open_names_csv"))
            self.open_names_csv_button.clicked.connect(lambda *_: self._open_review_report_file("names_csv"))
            file_controls.addWidget(self.open_names_csv_button, 2, 1)
            self.open_review_decisions_button = QtWidgets.QPushButton(self._t("open_review_decisions"))
            self.open_review_decisions_button.clicked.connect(lambda *_: self._open_review_report_file("review_decisions_csv"))
            file_controls.addWidget(self.open_review_decisions_button, 3, 0)
            self.open_problem_files_button = QtWidgets.QPushButton(self._t("open_problem_files"))
            self.open_problem_files_button.clicked.connect(lambda *_: self._open_review_report_file("problem_files_csv"))
            file_controls.addWidget(self.open_problem_files_button, 3, 1)
            self.open_selected_report_button = QtWidgets.QPushButton(self._t("open_selected_report"))
            self.open_selected_report_button.clicked.connect(lambda *_: self._open_selected_report_file())
            file_controls.addWidget(self.open_selected_report_button, 4, 0)
            self.report_files_table = QtWidgets.QTableWidget(0, 5)
            self.report_files_table.setHorizontalHeaderLabels(self._headers("report_files"))
            self.report_files_table.verticalHeader().setVisible(False)
            self.report_files_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self.report_files_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.report_files_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.report_files_table.horizontalHeader().setStretchLastSection(True)
            self.report_files_table.itemDoubleClicked.connect(lambda item: self._open_review_report_file_from_row(item.row()))
            self.report_files_table.itemSelectionChanged.connect(self._on_report_file_selection_changed)
            files_layout.addWidget(self.report_files_table, stretch=1)
            self.reports_stack.addWidget(files_page)

            # Page 2: problem_files.csv read-only explanation.
            problems_page = QtWidgets.QWidget()
            problems_layout = QtWidgets.QVBoxLayout(problems_page)
            problems_layout.setContentsMargins(0, 0, 0, 0)
            problems_help = QtWidgets.QLabel(self._t("problem_files_help"))
            problems_help.setWordWrap(True)
            problems_layout.addWidget(problems_help)
            self.problem_files_status = QtWidgets.QLabel(self._t("problem_files_status_no_output"))
            self.problem_files_status.setWordWrap(True)
            self.problem_files_status.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            self.problem_files_status.setStyleSheet("QLabel { padding: 6px; border: 1px solid #d0d0d0; border-radius: 4px; }")
            problems_layout.addWidget(self.problem_files_status)
            problem_controls = QtWidgets.QHBoxLayout()
            problems_layout.addLayout(problem_controls)
            self.open_problem_files_button_2 = QtWidgets.QPushButton(self._t("open_problem_files"))
            self.open_problem_files_button_2.clicked.connect(lambda *_: self._open_review_report_file("problem_files_csv"))
            problem_controls.addWidget(self.open_problem_files_button_2)
            problem_controls.addStretch(1)
            self.problem_files_table = QtWidgets.QTableWidget(0, 8)
            self.problem_files_table.setHorizontalHeaderLabels(self._headers("problem_files"))
            self.problem_files_table.verticalHeader().setVisible(False)
            self.problem_files_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self.problem_files_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.problem_files_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.problem_files_table.horizontalHeader().setStretchLastSection(True)
            problems_layout.addWidget(self.problem_files_table, stretch=1)
            self.reports_stack.addWidget(problems_page)

            # Page 3: review clusters table and thumbnails.
            review_page = QtWidgets.QWidget()
            review_layout = QtWidgets.QVBoxLayout(review_page)
            review_layout.setContentsMargins(0, 0, 0, 0)
            review_help = QtWidgets.QLabel(self._t("reports_review_help"))
            review_help.setWordWrap(True)
            review_layout.addWidget(review_help)
            action_help = QtWidgets.QLabel(self._t("review_action_help"))
            action_help.setWordWrap(True)
            action_help.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            action_help.setStyleSheet("QLabel { padding: 6px; border: 1px solid #d0d0d0; border-radius: 4px; }")
            review_layout.addWidget(action_help)
            workflow_help = QtWidgets.QLabel(self._t("review_workflow_hint"))
            workflow_help.setWordWrap(True)
            workflow_help.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            workflow_help.setStyleSheet("QLabel { padding: 6px; border: 1px solid #d0d0d0; border-radius: 4px; }")
            review_layout.addWidget(workflow_help)
            self.review_decisions_review_note = QtWidgets.QLabel(self._t("review_decisions_missing_hint"))
            self.review_decisions_review_note.setWordWrap(True)
            self.review_decisions_review_note.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            review_layout.addWidget(self.review_decisions_review_note)
            review_controls = QtWidgets.QHBoxLayout()
            review_layout.addLayout(review_controls)
            self.save_review_button_review = QtWidgets.QPushButton(self._t("save_names_csv"))
            self.save_review_button_review.setToolTip(self._t("save_names_csv_tooltip"))
            self.save_review_button_review.clicked.connect(lambda *_: self.save_review_decisions_from_ui())
            review_controls.addWidget(self.save_review_button_review)
            self.apply_names_button_review = QtWidgets.QPushButton(self._t("apply_names_here"))
            self.apply_names_button_review.setToolTip(self._t("apply_names_tooltip"))
            self.apply_names_button_review.clicked.connect(lambda *_: self.start_apply_names_from_review_ui())
            review_controls.addWidget(self.apply_names_button_review)
            self.open_names_from_review_button = QtWidgets.QPushButton(self._t("open_names_csv"))
            self.open_names_from_review_button.clicked.connect(lambda *_: self._open_review_report_file("names_csv"))
            review_controls.addWidget(self.open_names_from_review_button)
            review_controls.addStretch(1)
            self.review_workflow_status = QtWidgets.QLabel(self._t("review_workflow_status_no_output"))
            self.review_workflow_status.setWordWrap(True)
            self.review_workflow_status.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            self.review_workflow_status.setStyleSheet("QLabel { padding: 6px; border: 1px solid #d0d0d0; border-radius: 4px; }")
            review_layout.addWidget(self.review_workflow_status)
            review_split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
            review_layout.addWidget(review_split, stretch=1)

            table_panel = QtWidgets.QWidget()
            table_layout = QtWidgets.QVBoxLayout(table_panel)
            table_layout.setContentsMargins(0, 0, 0, 0)
            self.review_table = QtWidgets.QTableWidget(0, 9)
            self.review_table.setHorizontalHeaderLabels(self._headers("review_rows"))
            self.review_table.verticalHeader().setVisible(False)
            self.review_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.review_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.review_table.horizontalHeader().setStretchLastSection(True)
            self.review_table.itemSelectionChanged.connect(self._on_review_selection_changed)
            self.review_table.itemChanged.connect(lambda *_: self._update_review_workflow_status())
            table_layout.addWidget(self.review_table)
            review_split.addWidget(table_panel)

            details_panel = QtWidgets.QWidget()
            details_layout = QtWidgets.QVBoxLayout(details_panel)
            details_layout.setContentsMargins(0, 0, 0, 0)
            self.review_details = QtWidgets.QTextEdit()
            self.review_details.setReadOnly(True)
            self.review_details.setPlaceholderText(self._t("review_details_placeholder"))
            details_layout.addWidget(self.review_details, stretch=1)
            self.preview_scroll = QtWidgets.QScrollArea()
            self.preview_scroll.setWidgetResizable(True)
            self.preview_widget = QtWidgets.QWidget()
            self.preview_layout = QtWidgets.QGridLayout(self.preview_widget)
            self.preview_layout.setContentsMargins(4, 4, 4, 4)
            self.preview_layout.setHorizontalSpacing(8)
            self.preview_layout.setVerticalSpacing(8)
            self.preview_scroll.setWidget(self.preview_widget)
            self.preview_scroll.viewport().installEventFilter(self)
            details_layout.addWidget(self.preview_scroll, stretch=1)
            review_split.addWidget(details_panel)
            review_split.setSizes([720, 360])
            self.reports_stack.addWidget(review_page)

            # Page 4: apply names and final folders.
            apply_page = QtWidgets.QWidget()
            apply_layout = QtWidgets.QVBoxLayout(apply_page)
            apply_layout.setContentsMargins(0, 0, 0, 0)
            apply_help = QtWidgets.QLabel(self._t("reports_apply_help"))
            apply_help.setWordWrap(True)
            apply_layout.addWidget(apply_help)
            self.apply_names_status = QtWidgets.QLabel(self._t("review_workflow_status_no_output"))
            self.apply_names_status.setWordWrap(True)
            self.apply_names_status.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            self.apply_names_status.setStyleSheet("QLabel { padding: 6px; border: 1px solid #d0d0d0; border-radius: 4px; }")
            apply_layout.addWidget(self.apply_names_status)
            apply_controls = QtWidgets.QHBoxLayout()
            apply_layout.addLayout(apply_controls)
            self.save_review_button = QtWidgets.QPushButton(self._t("save_names_csv"))
            self.save_review_button.clicked.connect(lambda *_: self.save_review_decisions_from_ui())
            apply_controls.addWidget(self.save_review_button)
            self.apply_names_button = QtWidgets.QPushButton(self._t("apply_names"))
            self.apply_names_button.clicked.connect(lambda *_: self.start_apply_names_from_review_ui())
            apply_controls.addWidget(self.apply_names_button)
            self.open_final_button = QtWidgets.QPushButton(self._t("open_final"))
            self.open_final_button.clicked.connect(lambda *_: self.open_final_dir())
            apply_controls.addWidget(self.open_final_button)
            self.open_final_review_button = QtWidgets.QPushButton(self._t("open_final_review"))
            self.open_final_review_button.clicked.connect(lambda *_: self.open_final_review_dir())
            apply_controls.addWidget(self.open_final_review_button)
            apply_controls.addStretch(1)
            self.apply_names_details = QtWidgets.QTextEdit()
            self.apply_names_details.setReadOnly(True)
            self.apply_names_details.setPlainText(self._t("reports_apply_details"))
            apply_layout.addWidget(self.apply_names_details, stretch=1)
            self.reports_stack.addWidget(apply_page)

            # Page 5: folder shortcuts.
            folders_page = QtWidgets.QWidget()
            folders_layout = QtWidgets.QVBoxLayout(folders_page)
            folders_layout.setContentsMargins(0, 0, 0, 0)
            folders_help = QtWidgets.QLabel(self._t("reports_folders_help"))
            folders_help.setWordWrap(True)
            folders_layout.addWidget(folders_help)
            folders_controls = QtWidgets.QGridLayout()
            folders_layout.addLayout(folders_controls)
            self.open_output_from_reports_button = QtWidgets.QPushButton(self._t("open_output"))
            self.open_output_from_reports_button.clicked.connect(lambda *_: self.open_output_dir())
            folders_controls.addWidget(self.open_output_from_reports_button, 0, 0)
            self.open_reports_folder_button_2 = QtWidgets.QPushButton(self._t("open_reports_folder"))
            self.open_reports_folder_button_2.clicked.connect(lambda *_: self.open_reports_dir())
            folders_controls.addWidget(self.open_reports_folder_button_2, 0, 1)
            self.open_diagnostics_from_reports_button_2 = QtWidgets.QPushButton(self._t("open_diagnostics"))
            self.open_diagnostics_from_reports_button_2.clicked.connect(lambda *_: self.open_diagnostics_dir())
            folders_controls.addWidget(self.open_diagnostics_from_reports_button_2, 1, 0)
            self.open_final_button_2 = QtWidgets.QPushButton(self._t("open_final"))
            self.open_final_button_2.clicked.connect(lambda *_: self.open_final_dir())
            folders_controls.addWidget(self.open_final_button_2, 1, 1)
            self.open_final_review_button_2 = QtWidgets.QPushButton(self._t("open_final_review"))
            self.open_final_review_button_2.clicked.connect(lambda *_: self.open_final_review_dir())
            folders_controls.addWidget(self.open_final_review_button_2, 2, 0)
            folders_layout.addStretch(1)
            self.reports_stack.addWidget(folders_page)

            nav_items = [
                (self._t("reports_nav_overview"), 0),
                (self._t("reports_nav_files"), 1),
                (self._t("reports_nav_problems"), 2),
                (self._t("reports_nav_review"), 3),
                (self._t("reports_nav_apply"), 4),
                (self._t("reports_nav_folders"), 5),
            ]
            for label, index in nav_items:
                item = QtWidgets.QTreeWidgetItem([label])
                item.setData(0, QtCore.Qt.UserRole, index)
                self.reports_nav_tree.addTopLevelItem(item)
            self.reports_nav_tree.currentItemChanged.connect(self._on_reports_nav_changed)
            if self.reports_nav_tree.topLevelItemCount() > 0:
                self.reports_nav_tree.setCurrentItem(self.reports_nav_tree.topLevelItem(0))

            self._add_main_page(self._t("reports_tab"), self.reports_tab)

        def _on_reports_nav_changed(self, current: Any, previous: Any = None) -> None:
            if current is None or not hasattr(self, "reports_stack"):
                return
            index = current.data(0, QtCore.Qt.UserRole)
            try:
                self.reports_stack.setCurrentIndex(int(index))
            except Exception:
                self.reports_stack.setCurrentIndex(0)

        # ------------------------------------------------------------------
        # v62 polish: app icon, UI-only settings and quick instructions
        # ------------------------------------------------------------------
        def _resource_path(self, relative: str) -> Path:
            return Path(__file__).resolve().parents[1] / relative

        def _apply_window_icon(self) -> None:
            try:
                icon_path = self._resource_path(backend.UI_ICON_RELATIVE_PATH)
                if icon_path.exists():
                    icon = QtGui.QIcon(str(icon_path))
                    if not icon.isNull():
                        self.setWindowIcon(icon)
                        app = QtWidgets.QApplication.instance()
                        if app is not None:
                            app.setWindowIcon(icon)
            except Exception:
                # Icon polish must never prevent the backend UI from starting.
                return

        def _apply_ui_theme_density(self) -> None:
            try:
                settings = getattr(self, "polish_settings", backend.ui_polish_settings_from_session(self.session))
                app = QtWidgets.QApplication.instance()
                if app is None:
                    return
                font = app.font()
                if settings.density == "compact":
                    font.setPointSize(max(8, font.pointSize() - 1 if font.pointSize() > 0 else 9))
                else:
                    font.setPointSize(max(9, font.pointSize() if font.pointSize() > 0 else 10))
                app.setFont(font)
                if settings.theme == "dark":
                    app.setStyleSheet(
                        "QWidget { background: #1f232a; color: #e8edf3; } "
                        "QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTableWidget { "
                        "background: #2b3038; color: #f1f4f8; selection-background-color: #3d6ea8; } "
                        "QPushButton { background: #344050; color: #f1f4f8; border: 1px solid #536174; padding: 4px 8px; } "
                        "QPushButton:disabled { color: #87909a; } "
                        "QHeaderView::section { background: #303844; color: #f1f4f8; }"
                    )
                elif settings.theme == "light":
                    app.setStyleSheet(
                        "QWidget { background: #fafafa; color: #202124; } "
                        "QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTableWidget { background: white; color: #202124; } "
                        "QPushButton { padding: 4px 8px; }"
                    )
                else:
                    app.setStyleSheet("")
            except Exception as exc:
                self._log_event(f"[ui polish warning] theme/density not applied: {type(exc).__name__}: {exc}")


        def _ui_language(self) -> str:
            """Return the current UI language preference used by localized labels."""
            return str(getattr(getattr(self, "polish_settings", None), "language", "auto") or "auto")

        def _t(self, key: str, **kwargs: Any) -> str:
            """Translate a short UI label through the import-safe polish layer."""
            text = backend.ui_text(key, self._ui_language())
            if kwargs:
                try:
                    return text.format(**kwargs)
                except Exception:
                    return text
            return text

        def _is_ru(self) -> bool:
            return backend.effective_ui_language(self._ui_language()) == "ru"

        def _tx(self, ru: str, en: str) -> str:
            return ru if self._is_ru() else en

        def _set_stage_details_visible(self, visible: bool) -> None:
            """Show or hide the detailed per-stage table without affecting backend state."""
            if hasattr(self, "stage_details_container"):
                self.stage_details_container.setVisible(bool(visible))
            if hasattr(self, "stage_details_toggle"):
                self.stage_details_toggle.setChecked(bool(visible))
                self.stage_details_toggle.setText(self._t("hide_stage_details") if visible else self._t("show_stage_details"))
                self.stage_details_toggle.setArrowType(QtCore.Qt.DownArrow if visible else QtCore.Qt.RightArrow)

        def _update_runtime_status_block(self) -> None:
            if not hasattr(self, "runtime_status_label"):
                return
            try:
                values = self.collect_ui_values() if self._field_widgets else {}
            except Exception:
                values = {}
            text = backend.build_runtime_status_text(values, preflight_summary=self.last_preflight_summary, language=self._ui_language())
            self.runtime_status_label.setText(text)
            if self.last_preflight_summary:
                cuda_ok = bool(self.last_preflight_summary.get("cuda_provider_available"))
                use_gpu = bool(values.get("use_gpu", False))
                if use_gpu and cuda_ok:
                    self.runtime_status_label.setStyleSheet("QLabel { padding: 6px; border: 1px solid #2e7d32; border-radius: 4px; }")
                elif use_gpu:
                    self.runtime_status_label.setStyleSheet("QLabel { padding: 6px; border: 1px solid #f9a825; border-radius: 4px; }")
                else:
                    self.runtime_status_label.setStyleSheet("QLabel { padding: 6px; border: 1px solid #cfd8dc; border-radius: 4px; }")

        def _update_beginner_action_block(self) -> None:
            if not hasattr(self, "beginner_action_label"):
                return
            try:
                values = self.collect_ui_values() if self._field_widgets else {}
            except Exception:
                values = {}
            text = backend.build_beginner_action_map_text(values, language=self._ui_language())
            self.beginner_action_label.setText(text)
            try:
                input_dir = values.get("input_dir", "")
                output_dir = values.get("output_dir", "")
                if backend.is_output_inside_input(input_dir, output_dir):
                    self.beginner_action_label.setStyleSheet("QLabel { padding: 6px; border: 1px solid #f9a825; border-radius: 4px; background: #fff8e1; }")
                else:
                    self.beginner_action_label.setStyleSheet("QLabel { padding: 6px; border: 1px solid #cfd8dc; border-radius: 4px; }")
            except Exception:
                self.beginner_action_label.setStyleSheet("QLabel { padding: 6px; border: 1px solid #cfd8dc; border-radius: 4px; }")

        def _update_onboarding_block(self) -> None:
            if not hasattr(self, "onboarding_label"):
                return
            try:
                values = self.collect_ui_values() if self._field_widgets else {}
            except Exception:
                values = {}
            text = backend.build_onboarding_checklist_text(values, preflight_summary=self.last_preflight_summary, language=self._ui_language())
            self.onboarding_label.setText(text)
            try:
                input_dir = values.get("input_dir", "")
                output_dir = values.get("output_dir", "")
                if backend.is_output_inside_input(input_dir, output_dir):
                    self.onboarding_label.setStyleSheet("QLabel { padding: 6px; border: 1px solid #f9a825; border-radius: 4px; background: #fff8e1; }")
                else:
                    self.onboarding_label.setStyleSheet("QLabel { padding: 6px; border: 1px solid #d0d0d0; border-radius: 4px; }")
            except Exception:
                self.onboarding_label.setStyleSheet("QLabel { padding: 6px; border: 1px solid #d0d0d0; border-radius: 4px; }")

        def _human_stage_label(self, stage: str) -> str:
            """Translate backend stage keys without changing backend event payloads."""
            return backend.ui_stage_text(_stage_key(stage), self._ui_language())

        def _headers(self, group: str) -> List[str]:
            """Return localized table headers; technical file names remain unchanged."""
            ru = backend.effective_ui_language(self._ui_language()) == "ru"
            if group == "resume":
                return (["Источник", "Result-папка", "Статус", "Этап", "Профиль", "Runtime", "Обновлено", "Быстрые состояния", "Input"]
                        if ru else ["Source", "Result folder", "Status", "Stage", "Profile", "Runtime", "Updated", "Quick states", "Input"])
            if group == "report_files":
                return (["Ключ", "Статус", "Размер", "Путь", "Описание"]
                        if ru else ["Key", "Status", "Size", "Path", "Description"])
            if group == "problem_files":
                return (["#", "Категория", "Stage/reason", "Имя", "Расширение", "Размер", "Время", "Ошибка / что сделать"]
                        if ru else ["#", "Category", "Stage/reason", "Name", "Suffix", "Size", "Time", "Error / what to do"])
            if group == "review_rows":
                return (["Кластер", "Лица", "Файлы", "Confidence", "Action", "Name", "Merge into", "Notes", "Previews"]
                        if ru else ["Cluster", "Faces", "Files", "Confidence", "Action", "Name", "Merge into", "Notes", "Previews"])
            return []

        # ------------------------------------------------------------------
        # Diagnostics / support UI
        # ------------------------------------------------------------------
        def _build_diagnostics_support_tab(self) -> None:
            """Build a safe command-center page for existing diagnostics actions.

            The page is intentionally additive: it calls the same preflight,
            result-health and support-bundle helpers that CLI/Reports already
            use.  It does not start ML, does not mutate report CSV schemas and
            does not touch the apply-names workflow.
            """
            self.diagnostics_support_tab = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(self.diagnostics_support_tab)
            layout.setContentsMargins(8, 8, 8, 8)

            help_label = QtWidgets.QLabel(self._t("support_panel_help"))
            help_label.setWordWrap(True)
            help_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            layout.addWidget(help_label)

            self.support_path_label = QtWidgets.QLabel("")
            self.support_path_label.setWordWrap(True)
            self.support_path_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            self.support_path_label.setStyleSheet("QLabel { padding: 6px; border: 1px solid #d0d0d0; border-radius: 4px; }")
            layout.addWidget(self.support_path_label)

            controls = QtWidgets.QGridLayout()
            layout.addLayout(controls)

            self.support_preflight_button = QtWidgets.QPushButton(self._t("support_check_environment"))
            self.support_preflight_button.setToolTip(self._t("support_check_environment_tooltip"))
            self.support_preflight_button.clicked.connect(lambda *_: self.run_support_preflight())
            controls.addWidget(self.support_preflight_button, 0, 0)

            self.support_result_health_button = QtWidgets.QPushButton(self._t("support_check_result"))
            self.support_result_health_button.setToolTip(self._t("support_check_result_tooltip"))
            self.support_result_health_button.clicked.connect(lambda *_: self.run_result_health_from_ui())
            controls.addWidget(self.support_result_health_button, 0, 1)

            self.support_bundle_button = QtWidgets.QPushButton(self._t("support_create_bundle"))
            self.support_bundle_button.setToolTip(self._t("support_create_bundle_tooltip"))
            self.support_bundle_button.clicked.connect(lambda *_: self.create_support_bundle_from_ui())
            controls.addWidget(self.support_bundle_button, 0, 2)

            self.support_open_reports_button = QtWidgets.QPushButton(self._t("open_reports"))
            self.support_open_reports_button.setToolTip(self._t("tooltip_open_reports"))
            self.support_open_reports_button.clicked.connect(lambda *_: self.open_reports_dir())
            controls.addWidget(self.support_open_reports_button, 1, 0)

            self.support_open_bug_reports_button = QtWidgets.QPushButton(self._t("support_open_bug_reports"))
            self.support_open_bug_reports_button.setToolTip(self._t("support_open_bug_reports_tooltip"))
            self.support_open_bug_reports_button.clicked.connect(lambda *_: self.open_bug_reports_dir())
            controls.addWidget(self.support_open_bug_reports_button, 1, 1)

            self.support_open_diagnostics_button = QtWidgets.QPushButton(self._t("open_diagnostics"))
            self.support_open_diagnostics_button.setToolTip(self._t("tooltip_open_diagnostics"))
            self.support_open_diagnostics_button.clicked.connect(lambda *_: self.open_diagnostics_dir())
            controls.addWidget(self.support_open_diagnostics_button, 1, 2)

            self.support_open_last_bundle_button = QtWidgets.QPushButton(self._t("support_open_last_bundle"))
            self.support_open_last_bundle_button.setToolTip(self._t("support_open_last_bundle_tooltip"))
            self.support_open_last_bundle_button.clicked.connect(lambda *_: self.open_bug_report())
            controls.addWidget(self.support_open_last_bundle_button, 2, 0)

            self.support_copy_summary_button = QtWidgets.QPushButton(self._t("support_copy_short_summary"))
            self.support_copy_summary_button.setToolTip(self._t("support_copy_short_summary_tooltip"))
            self.support_copy_summary_button.clicked.connect(lambda *_: self.copy_short_diagnostic_summary())
            controls.addWidget(self.support_copy_summary_button, 2, 1)

            self.support_refresh_summary_button = QtWidgets.QPushButton(self._t("support_refresh_summary"))
            self.support_refresh_summary_button.setToolTip(self._t("support_refresh_summary_tooltip"))
            self.support_refresh_summary_button.clicked.connect(lambda *_: self._render_support_panel_summary())
            controls.addWidget(self.support_refresh_summary_button, 2, 2)

            self.support_summary_text = QtWidgets.QTextEdit()
            self.support_summary_text.setReadOnly(True)
            self.support_summary_text.setPlaceholderText(self._t("support_summary_placeholder"))
            layout.addWidget(self.support_summary_text, stretch=1)

            self._add_main_page(self._t("support_panel_tab"), self.diagnostics_support_tab)
            self._render_support_panel_summary()

        def _build_help_settings_tab(self) -> None:
            self.help_tab = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(self.help_tab)

            title = QtWidgets.QLabel(backend.ui_text("settings_title", self.polish_settings.language))
            title.setWordWrap(True)
            layout.addWidget(title)

            settings_box = QtWidgets.QGroupBox(self._t("settings_group"))
            form = QtWidgets.QFormLayout(settings_box)
            layout.addWidget(settings_box)

            self.ui_language_combo = QtWidgets.QComboBox()
            for value in backend.UI_LANGUAGE_CHOICES:
                label = {"auto": "Auto / default", "ru": "Русский", "en": "English"}.get(value, value)
                self.ui_language_combo.addItem(label, value)
            self._set_combo_data(self.ui_language_combo, self.polish_settings.language)
            form.addRow(backend.ui_text("language", self.polish_settings.language), self.ui_language_combo)

            self.ui_theme_combo = QtWidgets.QComboBox()
            for value in backend.UI_THEME_CHOICES:
                self.ui_theme_combo.addItem(value, value)
            self._set_combo_data(self.ui_theme_combo, self.polish_settings.theme)
            form.addRow(backend.ui_text("theme", self.polish_settings.language), self.ui_theme_combo)

            self.ui_density_combo = QtWidgets.QComboBox()
            for value in backend.UI_DENSITY_CHOICES:
                self.ui_density_combo.addItem(value, value)
            self._set_combo_data(self.ui_density_combo, self.polish_settings.density)
            form.addRow(backend.ui_text("density", self.polish_settings.language), self.ui_density_combo)

            self.startup_tips_check = QtWidgets.QCheckBox(backend.ui_text("show_tips", self.polish_settings.language))
            self.startup_tips_check.setChecked(bool(self.polish_settings.show_startup_tips))
            form.addRow("", self.startup_tips_check)
            self.confirm_run_check = QtWidgets.QCheckBox(backend.ui_text("confirm_run", self.polish_settings.language))
            self.confirm_run_check.setChecked(bool(self.polish_settings.confirm_before_run))
            form.addRow("", self.confirm_run_check)
            self.auto_open_reports_check = QtWidgets.QCheckBox(backend.ui_text("auto_open_reports", self.polish_settings.language))
            self.auto_open_reports_check.setChecked(bool(self.polish_settings.auto_open_reports_after_run))
            form.addRow("", self.auto_open_reports_check)

            row = QtWidgets.QHBoxLayout()
            layout.addLayout(row)
            self.save_ui_settings_button = QtWidgets.QPushButton(backend.ui_text("save_settings", self.polish_settings.language))
            self.save_ui_settings_button.clicked.connect(lambda *_: self._apply_ui_settings_from_controls(show_message=True))
            row.addWidget(self.save_ui_settings_button)
            self.open_session_folder_button = QtWidgets.QPushButton(backend.ui_text("open_session_folder", self.polish_settings.language))
            self.open_session_folder_button.clicked.connect(lambda *_: self.open_session_folder())
            row.addWidget(self.open_session_folder_button)
            self.open_ru_guide_button = QtWidgets.QPushButton(backend.ui_text("open_ru_guide", self.polish_settings.language))
            self.open_ru_guide_button.clicked.connect(lambda *_: self.open_user_guide("ru"))
            row.addWidget(self.open_ru_guide_button)
            self.open_en_guide_button = QtWidgets.QPushButton(backend.ui_text("open_en_guide", self.polish_settings.language))
            self.open_en_guide_button.clicked.connect(lambda *_: self.open_user_guide("en"))
            row.addWidget(self.open_en_guide_button)
            self.open_help_ru_button = QtWidgets.QPushButton(backend.ui_text("open_help_ru", self.polish_settings.language))
            self.open_help_ru_button.clicked.connect(lambda *_: self.open_help_doc("ru"))
            row.addWidget(self.open_help_ru_button)
            self.open_help_en_button = QtWidgets.QPushButton(backend.ui_text("open_help_en", self.polish_settings.language))
            self.open_help_en_button.clicked.connect(lambda *_: self.open_help_doc("en"))
            row.addWidget(self.open_help_en_button)
            self.open_packaging_guide_button = QtWidgets.QPushButton(backend.ui_text("open_packaging_guide", self.polish_settings.language))
            self.open_packaging_guide_button.clicked.connect(lambda *_: self.open_packaging_guide())
            row.addWidget(self.open_packaging_guide_button)
            row.addStretch(1)

            self.instructions_text = QtWidgets.QTextEdit()
            self.instructions_text.setReadOnly(True)
            layout.addWidget(self.instructions_text, stretch=1)

            for widget in (self.ui_language_combo, self.ui_theme_combo, self.ui_density_combo):
                widget.currentIndexChanged.connect(lambda *_: self._on_ui_settings_changed())
            for widget in (self.startup_tips_check, self.confirm_run_check, self.auto_open_reports_check):
                widget.stateChanged.connect(lambda *_: self._on_ui_settings_changed())

            self._render_instruction_text()
            self._add_main_page(backend.ui_text("settings_tab", self.polish_settings.language), self.help_tab)

        def _collect_polish_settings(self) -> Any:
            language = self.ui_language_combo.currentData() if hasattr(self, "ui_language_combo") else self.polish_settings.language
            theme = self.ui_theme_combo.currentData() if hasattr(self, "ui_theme_combo") else self.polish_settings.theme
            density = self.ui_density_combo.currentData() if hasattr(self, "ui_density_combo") else self.polish_settings.density
            return backend.UiPolishSettings(
                language=backend.normalize_ui_language(language),
                theme=backend.normalize_ui_theme(theme),
                density=backend.normalize_ui_density(density),
                show_startup_tips=bool(self.startup_tips_check.isChecked()) if hasattr(self, "startup_tips_check") else bool(self.polish_settings.show_startup_tips),
                confirm_before_run=bool(self.confirm_run_check.isChecked()) if hasattr(self, "confirm_run_check") else bool(self.polish_settings.confirm_before_run),
                auto_open_reports_after_run=bool(self.auto_open_reports_check.isChecked()) if hasattr(self, "auto_open_reports_check") else bool(self.polish_settings.auto_open_reports_after_run),
                show_advanced_fields=bool(self.show_advanced_check.isChecked()) if hasattr(self, "show_advanced_check") else bool(self.polish_settings.show_advanced_fields),
                verbose_progress_events=bool(self.verbose_progress_check.isChecked()) if hasattr(self, "verbose_progress_check") else bool(self.polish_settings.verbose_progress_events),
                auto_scroll_logs=bool(self.auto_scroll_check.isChecked()) if hasattr(self, "auto_scroll_check") else bool(self.polish_settings.auto_scroll_logs),
            )

        def _render_instruction_text(self) -> None:
            if not hasattr(self, "instructions_text"):
                return
            settings = getattr(self, "polish_settings", backend.ui_polish_settings_from_session(self.session))
            lines: List[str] = []
            snapshot = backend.ui_polish_snapshot(settings.language)
            lines.append(f"Tuned Image Sorter {snapshot.version} / {snapshot.refactor_stage}")
            lines.append(f"UI polish schema: {snapshot.schema_version}")
            lines.append(f"Icon: {snapshot.icon_path}")
            lines.append("")
            for section in snapshot.instructions:
                lines.append(section.title)
                lines.append("-" * len(section.title))
                for step in section.steps:
                    lines.append(f"• {step.title}: {step.body}")
                lines.append("")
            self.instructions_text.setPlainText("\n".join(lines).strip())

        def _apply_ui_settings_from_controls(self, *, show_message: bool = False) -> None:
            try:
                self.polish_settings = self._collect_polish_settings()
                self.session = backend.apply_ui_polish_settings_to_session(self.session, self.polish_settings)
                backend.save_ui_session_state(self.session, self.session_path)
                self._apply_ui_theme_density()
                self._render_instruction_text()
                if hasattr(self, "onboarding_label"):
                    self.onboarding_label.setText(backend.build_first_run_help_text(language=self._ui_language()))
                self._update_runtime_status_block()
                self.session_label.setText(f"{self._t('session_saved')}: {self.session_path}")
                if show_message:
                    self._log_event(f"[ui] {backend.ui_text('settings_saved', self.polish_settings.language)}")
            except Exception as exc:
                self._log_status_report(backend.ui_status_report((backend.issue_from_exception(exc, source="ui", code="ui_settings_save_failed", include_traceback=False),), summary="UI settings save failed"))

        def _on_ui_settings_changed(self) -> None:
            self._apply_ui_settings_from_controls(show_message=False)

        def open_session_folder(self) -> None:
            self._open_path(Path(self.session_path).parent)

        def open_user_guide(self, language: str) -> None:
            root = Path(__file__).resolve().parents[2]
            name = "USER_GUIDE_EN.md" if language == "en" else "USER_GUIDE_RU.md"
            self._open_path(root / "docs" / name)

        def open_help_doc(self, language: str) -> None:
            root = Path(__file__).resolve().parents[2]
            name = "HELP_EN.md" if language == "en" else "HELP_RU.md"
            self._open_path(root / "docs" / name)

        def open_packaging_guide(self) -> None:
            root = Path(__file__).resolve().parents[2]
            self._open_path(root / "tools" / "windows_packaging" / "README_WINDOWS_PACKAGING_RU.md")

        def refresh_reports_review(self, *, initial: bool = False) -> None:
            output = self.output_path_from_ui_or_result() if hasattr(self, "output_path_from_ui_or_result") else None
            if not output:
                self._review_snapshot = None
                self._review_rows = []
                self._problem_rows = []
                self._render_report_files_table([])
                self._render_problem_files_table(None)
                self._render_review_rows_table([])
                if hasattr(self, "reports_details"):
                    self.reports_details.setPlainText(self._tx("Output/result папка пока не выбрана.", "Output/result folder is not selected yet."))
                self._update_review_workflow_status()
                self._update_reports_review_buttons()
                return
            try:
                snapshot = backend.load_review_ui_snapshot(output)
                self._review_snapshot = snapshot
                self._review_rows = [row.to_dict() for row in snapshot.rows]
                self._problem_rows = [row.to_dict() for row in getattr(snapshot.problem_summary, "rows", ())]
                self._render_report_files_table(snapshot.report_files)
                self._render_problem_files_table(getattr(snapshot, "problem_summary", None))
                self._render_review_rows_table(self._review_rows)
                self._update_review_workflow_status()
                counts = self._report_counts(Path(snapshot.output_dir))
                problem_summary = getattr(snapshot, "problem_summary", None)
                lines = [
                    f"output_dir: {snapshot.output_dir}",
                    f"reports_dir: {snapshot.reports_dir}",
                    f"diagnostics_dir: {snapshot.diagnostics_dir}",
                    f"db_path: {snapshot.db_path}",
                    f"clusters shown: {len(snapshot.rows)}",
                    f"can_apply_names: {snapshot.can_apply_names}",
                    "",
                    "counts:",
                    f"- summary.csv rows: {counts.get('summary_rows', 0)}",
                    f"- assignments.csv rows: {counts.get('assignment_rows', 0)}",
                    f"- review_clusters.csv rows: {counts.get('review_cluster_rows', 0)}",
                    f"- duplicates.csv rows: {counts.get('duplicate_rows', 0)}",
                    f"- problem_files.csv rows: {self._problem_files_count(Path(snapshot.output_dir))}",
                    f"- problem_files status: {self._problem_summary_status_line(problem_summary)}",
                    "",
                    "problem files:",
                    *self._problem_summary_lines(problem_summary),
                    "",
                    "warnings:",
                ]
                lines.extend([f"- {warning}" for warning in snapshot.warnings] or ["- none"])
                self.reports_details.setPlainText("\n".join(lines))
                if snapshot.warnings and not initial:
                    issues = tuple(
                        backend.ui_issue("review_ui_warning", "warning", "reports", "Reports/review warning", warning, action="Check generated reports or run mode=report/copy first.")
                        for warning in snapshot.warnings
                    )
                    self._log_status_report(backend.ui_status_report(issues, summary="Reports/review warnings"))
                if not initial:
                    self._log_event(f"[reports] Loaded {len(snapshot.rows)} review cluster row(s) from {snapshot.output_dir}")
            except Exception as exc:
                self._review_snapshot = None
                self._review_rows = []
                self._problem_rows = []
                self._render_report_files_table([])
                self._render_problem_files_table(None)
                self._render_review_rows_table([])
                self._update_review_workflow_status()
                self._log_status_report(backend.ui_status_report((backend.issue_from_exception(exc, source="reports", code="review_ui_load_failed", include_traceback=False),), summary="Reports/review load failed"))
            self._update_reports_review_buttons()

        def _render_report_files_table(self, files: Iterable[Any]) -> None:
            self.report_files_table.setRowCount(0)
            for report_file in files:
                row = self.report_files_table.rowCount()
                self.report_files_table.insertRow(row)
                exists = bool(getattr(report_file, "exists", False))
                status = self._report_file_status_text(report_file)
                note = self._report_file_missing_note(report_file) if not exists else ""
                description = str(getattr(report_file, "description", ""))
                if note:
                    description = f"{description} — {note}" if description else note
                values = [
                    getattr(report_file, "key", ""),
                    status,
                    "" if getattr(report_file, "size_bytes", None) is None else str(getattr(report_file, "size_bytes")),
                    str(getattr(report_file, "path", "")),
                    description,
                ]
                for col, value in enumerate(values):
                    item = QtWidgets.QTableWidgetItem(str(value))
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                    tooltip = str(getattr(report_file, "path", ""))
                    if note:
                        tooltip = f"{note}\n{tooltip}"
                    item.setToolTip(tooltip)
                    self.report_files_table.setItem(row, col, item)
            self.report_files_table.resizeColumnsToContents()

        def _problem_category_label(self, category: str) -> str:
            ru = backend.effective_ui_language(self._ui_language()) == "ru"
            labels_ru = {
                "unsupported_format": "Неподдерживаемый формат",
                "read_open_error": "Read/open error",
                "decode_error": "Decode error / битое изображение",
                "timeout": "Timeout",
                "internal_worker_error": "Internal worker error",
                "other": "Другое",
            }
            labels_en = {
                "unsupported_format": "Unsupported format",
                "read_open_error": "Read/open error",
                "decode_error": "Decode error / broken image",
                "timeout": "Timeout",
                "internal_worker_error": "Internal worker error",
                "other": "Other",
            }
            labels = labels_ru if ru else labels_en
            return labels.get(str(category or "other"), labels["other"])

        def _problem_category_action(self, category: str) -> str:
            ru = backend.effective_ui_language(self._ui_language()) == "ru"
            actions_ru = {
                "unsupported_format": "Что сделать: конвертировать файл в JPG/PNG/WebP/TIFF/HEIC или убрать его из input.",
                "read_open_error": "Что сделать: проверить доступ к файлу, путь, OneDrive/сетевой диск, длину пути и права чтения.",
                "decode_error": "Что сделать: открыть файл в просмотрщике, пересохранить/конвертировать или удалить битую копию.",
                "timeout": "Что сделать: файл пропущен защитой timeout; можно отдельно проверить/конвертировать его и повторить прогон.",
                "internal_worker_error": "Что сделать: сохранить bug-report и проверить diagnostics; worker/job должен завершиться, а не зависнуть.",
                "other": "Что сделать: открыть problem_files.csv и diagnostics, затем проверить конкретную ошибку.",
            }
            actions_en = {
                "unsupported_format": "Action: convert the file to JPG/PNG/WebP/TIFF/HEIC or remove it from input.",
                "read_open_error": "Action: check file access, path, OneDrive/network drive state, path length and read permissions.",
                "decode_error": "Action: open the file in a viewer, re-save/convert it, or remove the broken copy.",
                "timeout": "Action: the file was skipped by timeout protection; check/convert it separately and rerun if needed.",
                "internal_worker_error": "Action: create a bug-report and check diagnostics; the worker/job should finish instead of hanging.",
                "other": "Action: open problem_files.csv and diagnostics, then inspect the exact error.",
            }
            actions = actions_ru if ru else actions_en
            return actions.get(str(category or "other"), actions["other"])

        def _problem_summary_status_line(self, summary: Any) -> str:
            if summary is None:
                return self._t("problem_files_status_no_output")
            if not bool(getattr(summary, "exists", False)):
                return self._t("problem_files_status_missing")
            total = int(getattr(summary, "total_rows", 0) or 0)
            return f"{self._t('problem_files_status_present')} rows={total}"

        def _problem_summary_lines(self, summary: Any) -> List[str]:
            if summary is None:
                return [self._t("problem_files_status_no_output")]
            if not bool(getattr(summary, "exists", False)):
                return [self._t("problem_files_status_missing")]
            counts = dict(getattr(summary, "category_counts", {}) or {})
            if not counts:
                return ["problem_files.csv exists but has no data rows."]
            return [f"- {self._problem_category_label(key)}: {value}" for key, value in sorted(counts.items())]

        def _render_problem_files_table(self, summary: Any) -> None:
            if hasattr(self, "problem_files_status"):
                self.problem_files_status.setText(self._problem_summary_status_line(summary))
            if not hasattr(self, "problem_files_table"):
                return
            self.problem_files_table.setRowCount(0)
            if summary is None or not bool(getattr(summary, "exists", False)):
                return
            rows = list(getattr(summary, "rows", ()) or [])
            for data in rows:
                if hasattr(data, "to_dict"):
                    data = data.to_dict()
                row = self.problem_files_table.rowCount()
                self.problem_files_table.insertRow(row)
                category = str(data.get("category") or "other")
                error = str(data.get("error") or "")
                action = self._problem_category_action(category)
                error_text = f"{error}\n{action}" if error else action
                size = data.get("size_bytes")
                size_text = "" if size in (None, "") else str(size)
                values = [
                    data.get("index", row + 1),
                    self._problem_category_label(category),
                    data.get("stage", ""),
                    data.get("name", ""),
                    data.get("suffix", ""),
                    size_text,
                    data.get("time", ""),
                    error_text,
                ]
                tooltip = str(data.get("path", ""))
                if error:
                    tooltip = f"{tooltip}\n{error}" if tooltip else error
                tooltip = f"{tooltip}\n{action}" if tooltip else action
                for col, value in enumerate(values):
                    item = QtWidgets.QTableWidgetItem(str(value))
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                    item.setToolTip(tooltip)
                    self.problem_files_table.setItem(row, col, item)
            self.problem_files_table.resizeColumnsToContents()

        def _render_review_rows_table(self, rows: List[Dict[str, Any]]) -> None:
            self.review_table.setRowCount(0)
            for data in rows:
                row = self.review_table.rowCount()
                self.review_table.insertRow(row)
                readonly_values = [
                    data.get("cluster_key", ""),
                    data.get("faces", ""),
                    data.get("files", ""),
                    "" if data.get("confidence") is None else f"{float(data.get('confidence')):.4f}",
                ]
                for col, value in enumerate(readonly_values):
                    item = QtWidgets.QTableWidgetItem(str(value))
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                    self.review_table.setItem(row, col, item)

                combo = QtWidgets.QComboBox()
                combo.setToolTip(self._t("review_action_combo_tooltip"))
                for action in getattr(backend, "REVIEW_UI_ACTIONS", ("keep", "merge", "review", "ignore")):
                    combo.addItem(str(action), str(action))
                action = str(data.get("action") or "keep")
                index = combo.findData(action)
                combo.setCurrentIndex(index if index >= 0 else 0)
                combo.currentIndexChanged.connect(lambda *_: self._update_review_workflow_status())
                self.review_table.setCellWidget(row, 4, combo)

                for col, key in ((5, "name"), (6, "merge_into"), (7, "notes")):
                    item = QtWidgets.QTableWidgetItem(str(data.get(key) or ""))
                    tooltip_key = {"name": "review_name_tooltip", "merge_into": "review_merge_tooltip", "notes": "review_notes_tooltip"}.get(key)
                    if tooltip_key:
                        item.setToolTip(self._t(tooltip_key))
                    self.review_table.setItem(row, col, item)

                previews = data.get("thumbnails") or []
                item = QtWidgets.QTableWidgetItem(str(len(previews)))
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                self.review_table.setItem(row, 8, item)
            self.review_table.resizeColumnsToContents()
            if rows and self.review_table.currentRow() < 0:
                self.review_table.selectRow(0)
            elif not rows:
                self._clear_preview_layout()
            self._update_review_workflow_status()

        def _selected_review_row_index(self) -> int:
            row = self.review_table.currentRow()
            return row if 0 <= row < len(self._review_rows) else -1

        def _on_review_selection_changed(self) -> None:
            row = self._selected_review_row_index()
            if row < 0:
                return
            data = self._review_rows[row]
            thumbnails = [Path(path) for path in data.get("thumbnails", [])]
            lines = [
                f"cluster_key: {data.get('cluster_key', '')}",
                f"faces: {data.get('faces', '')}",
                f"files: {data.get('files', '')}",
                f"confidence: {data.get('confidence', '')}",
                f"avg_det_score: {data.get('avg_det_score', '')}",
                f"thumbnails: {len(thumbnails)}",
                "",
                self._t("review_edit_hint"),
            ]
            target = self.review_details if hasattr(self, "review_details") else self.reports_details
            target.setPlainText("\n".join(lines))
            self._show_review_thumbnails(thumbnails)
            self._update_review_workflow_status()

        def _clear_preview_layout(self) -> None:
            while self.preview_layout.count():
                item = self.preview_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

        def _preview_grid_columns(self) -> int:
            try:
                width = max(160, int(self.preview_scroll.viewport().width()))
            except Exception:
                width = 360
            cell = 132
            return max(1, min(6, width // cell))

        def _show_review_thumbnails(self, paths: Iterable[Path]) -> None:
            self._preview_thumbnail_paths = list(paths)[:48]
            self._rebuild_preview_grid()

        def _rebuild_preview_grid(self) -> None:
            if not hasattr(self, "preview_layout"):
                return
            self._clear_preview_layout()
            paths = list(getattr(self, "_preview_thumbnail_paths", []))
            columns = self._preview_grid_columns()
            if not paths:
                label = QtWidgets.QLabel(self._t("no_thumbnails"))
                label.setWordWrap(True)
                self.preview_layout.addWidget(label, 0, 0, 1, max(1, columns))
                return
            for index, path in enumerate(paths):
                label = QtWidgets.QLabel()
                label.setAlignment(QtCore.Qt.AlignCenter)
                label.setMinimumSize(116, 116)
                label.setMaximumSize(132, 148)
                label.setToolTip(str(path))
                pixmap = QtGui.QPixmap(str(path))
                if pixmap.isNull():
                    label.setText(path.name)
                    label.setWordWrap(True)
                else:
                    label.setPixmap(pixmap.scaled(112, 112, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
                row = index // columns
                column = index % columns
                self.preview_layout.addWidget(label, row, column)
            self.preview_layout.setRowStretch((len(paths) + columns - 1) // columns, 1)
            self.preview_layout.setColumnStretch(columns, 1)


        def _report_file_missing_note(self, report_file: Any) -> str:
            key = str(getattr(report_file, "key", ""))
            ru = backend.effective_ui_language(self._ui_language()) == "ru"
            if key == "review_decisions_csv":
                return ("не создан — появится после сохранения names.csv или применения решений Review clusters"
                        if ru else "not created — appears after saving names.csv or applying Review clusters decisions")
            if key == "names_csv":
                return ("не создан — появится после сохранения решений Review clusters"
                        if ru else "not created — appears after saving Review clusters decisions")
            if key == "review_clusters_csv":
                return ("отсутствует — обычный отчёт может не содержать review-кластеров"
                        if ru else "missing — the normal report may contain no review clusters")
            if key == "problem_files_csv":
                return ("нет проблемных файлов — problem_files.csv создаётся только при ошибках чтения/декодирования/timeout/worker"
                        if ru else "no problem files — problem_files.csv is created only for read/decode/timeout/worker issues")
            if key == "duplicates_csv":
                return ("отсутствует — файл создаётся только если для него есть данные"
                        if ru else "missing — this file is created only when there is data for it")
            if key in {"diagnostics_dir", "runtime_diagnostics_json"}:
                return ("отсутствует — diagnostics ещё не создана"
                        if ru else "missing — diagnostics has not been created yet")
            return "отсутствует" if ru else "missing"

        def _report_file_status_text(self, report_file: Any) -> str:
            ru = backend.effective_ui_language(self._ui_language()) == "ru"
            if bool(getattr(report_file, "exists", False)):
                return "есть" if ru else "present"
            key = str(getattr(report_file, "key", ""))
            if key in {"review_decisions_csv", "names_csv"}:
                return "не создан" if ru else "not created"
            if key == "problem_files_csv":
                return "нет проблем" if ru else "no problems"
            return "отсутствует" if ru else "missing"

        def _report_file_by_key(self, key: str) -> Optional[Any]:
            snapshot = self._review_snapshot
            if snapshot is None:
                return None
            for report_file in snapshot.report_files:
                if report_file.key == key:
                    return report_file
            return None

        def _selected_report_file(self) -> Optional[Any]:
            snapshot = self._review_snapshot
            if snapshot is None:
                return None
            row = self.report_files_table.currentRow() if hasattr(self, "report_files_table") else -1
            if row < 0 or row >= len(snapshot.report_files):
                return None
            return snapshot.report_files[row]

        def _on_report_file_selection_changed(self) -> None:
            if hasattr(self, "open_selected_report_button"):
                report_file = self._selected_report_file()
                self.open_selected_report_button.setEnabled(bool(report_file and report_file.exists))

        def _open_selected_report_file(self) -> None:
            report_file = self._selected_report_file()
            if not report_file:
                self._warn(self._t("warn_report_not_selected"))
                return
            if not bool(getattr(report_file, "exists", False)):
                self._warn(self._report_file_missing_note(report_file))
                return
            self._open_path(Path(report_file.path))

        def _reports_summary_text(self) -> str:
            output = self.output_path_from_ui_or_result()
            if not output:
                return self._tx("Tuned Image Sorter: output/result папка пока не выбрана.", "Tuned Image Sorter reports summary: output/result folder is not selected yet.")
            reports = output / "reports"
            diagnostics = self.diagnostics_path_from_ui_or_result()
            counts = self._report_counts(output)
            problem_summary = backend.load_problem_files_summary(reports / "problem_files.csv")
            lines = [
                f"Tuned Image Sorter {backend.SCRIPT_VERSION} — {self._t('reports_summary_title')}",
                "=" * 44,
                f"output_dir: {output}",
                f"reports_dir: {reports}",
                f"diagnostics_dir: {diagnostics or ''}",
                "",
                self._tx("Файлы отчётов", "Report files"),
                "------------",
            ]
            if self._review_snapshot is not None:
                for item in self._review_snapshot.report_files:
                    state = self._tx("да", "yes") if getattr(item, "exists", False) else self._tx("нет", "no")
                    size = getattr(item, "size_bytes", None)
                    size_text = "" if size is None else f" ({size} bytes)"
                    note = "" if getattr(item, "exists", False) else f" — {self._report_file_missing_note(item)}"
                    lines.append(f"{item.key}: {state}{size_text}{note} — {item.path}")
            else:
                for key, path in (
                    ("summary_csv", reports / "summary.csv"),
                    ("assignments_csv", reports / "assignments.csv"),
                    ("clusters_html", reports / "clusters.html"),
                    ("duplicates_csv", reports / "duplicates.csv"),
                    ("review_clusters_csv", reports / "review_clusters.csv"),
                    ("problem_files_csv", reports / "problem_files.csv"),
                ):
                    lines.append(f"{key}: {self._tx('да', 'yes') if path.exists() else self._tx('нет', 'no')} — {path}")
            lines.extend([
                "",
                self._tx("Счётчики", "Counts"),
                "------",
                f"summary.csv rows: {counts.get('summary_rows', 0)}",
                f"assignments.csv rows: {counts.get('assignment_rows', 0)}",
                f"review_clusters.csv rows: {counts.get('review_cluster_rows', 0)}",
                f"duplicates.csv rows: {counts.get('duplicate_rows', 0)}",
                f"problem_files.csv rows: {self._problem_files_count(output)}",
                f"problem_files status: {self._problem_summary_status_line(problem_summary)}",
                f"person folders: {counts.get('person_folders', 0)}",
                f"review/no_faces files: {counts.get('review_no_faces_files', 0)}",
                f"review/unknown_faces files: {counts.get('review_unknown_faces_files', 0)}",
                "",
                self._t("problem_files_section"),
                "-------------",
                *self._problem_summary_lines(problem_summary),
                "",
                self._tx("Форматы не менялись. Это read-only UI-сводка отчётов, если вы явно не сохраняете names.csv в review-таблице.", "Formats are unchanged. This is a UI/read-only reports summary unless you explicitly save names.csv in the review table."),
            ])
            return "\n".join(lines)

        def copy_reports_summary(self) -> None:
            QtWidgets.QApplication.clipboard().setText(self._reports_summary_text())
            self._log_event("[reports] Reports summary copied to clipboard.")

        def _open_review_report_file(self, key: str) -> None:
            report_file = self._report_file_by_key(key)
            if not report_file:
                self._warn(self._t("warn_report_not_known"))
                return
            if not bool(getattr(report_file, "exists", False)):
                self._warn(self._report_file_missing_note(report_file))
                return
            self._open_path(Path(report_file.path))

        def _open_review_report_file_from_row(self, row: int) -> None:
            if self._review_snapshot is None or row < 0 or row >= len(self._review_snapshot.report_files):
                return
            report_file = self._review_snapshot.report_files[row]
            if not bool(getattr(report_file, "exists", False)):
                self._warn(self._report_file_missing_note(report_file))
                return
            self._open_path(Path(report_file.path))

        def _review_workflow_status_text(self) -> str:
            ru = backend.effective_ui_language(self._ui_language()) == "ru"
            output = self.output_path_from_ui_or_result()
            if not output:
                return self._t("review_workflow_status_no_output")
            if not hasattr(self, "review_table") or self.review_table.rowCount() <= 0:
                return self._t("review_workflow_status_no_rows")
            rows = self._collect_review_rows_from_table()
            total = len(rows)
            counts = {"keep": 0, "merge": 0, "review": 0, "ignore": 0}
            merge_without_target = 0
            keep_without_name = 0
            for row in rows:
                action = str(row.get("action") or "keep").strip().lower()
                counts[action] = counts.get(action, 0) + 1
                if action == "merge" and not str(row.get("merge_into") or "").strip():
                    merge_without_target += 1
                if action == "keep" and not str(row.get("name") or "").strip():
                    keep_without_name += 1
            names_item = self._report_file_by_key("names_csv")
            decisions_item = self._report_file_by_key("review_decisions_csv")
            names_state = ("есть" if (names_item and names_item.exists) else "не создан") if ru else ("present" if (names_item and names_item.exists) else "not created")
            decisions_state = ("есть" if (decisions_item and decisions_item.exists) else "не создан") if ru else ("present" if (decisions_item and decisions_item.exists) else "not created")
            if ru:
                parts = [
                    f"Review workflow: строк={total}; keep={counts.get('keep', 0)}, merge={counts.get('merge', 0)}, review={counts.get('review', 0)}, ignore={counts.get('ignore', 0)}.",
                    f"names.csv: {names_state}; review_decisions.csv: {decisions_state}.",
                ]
                if keep_without_name:
                    parts.append(f"keep без Name: {keep_without_name} — такие строки не создадут именованные final-папки.")
                if merge_without_target:
                    parts.append(f"merge без Merge into: {merge_without_target} — перед применением лучше заполнить целевой cluster_key.")
                parts.append("Безопасный порядок: Сохранить names.csv → проверить статусы файлов → Применить имена.")
            else:
                parts = [
                    f"Review workflow: rows={total}; keep={counts.get('keep', 0)}, merge={counts.get('merge', 0)}, review={counts.get('review', 0)}, ignore={counts.get('ignore', 0)}.",
                    f"names.csv: {names_state}; review_decisions.csv: {decisions_state}.",
                ]
                if keep_without_name:
                    parts.append(f"keep without Name: {keep_without_name} — these rows will not create named final folders.")
                if merge_without_target:
                    parts.append(f"merge without Merge into: {merge_without_target} — fill the target cluster_key before applying.")
                parts.append("Safe order: Save names.csv → check file states → Apply names.")
            return "\n".join(parts)

        def _update_review_workflow_status(self) -> None:
            text = self._review_workflow_status_text()
            for attr in ("review_workflow_status", "apply_names_status"):
                if hasattr(self, attr):
                    getattr(self, attr).setText(text)

        def _collect_review_rows_from_table(self) -> List[Dict[str, Any]]:
            rows: List[Dict[str, Any]] = []
            for row in range(self.review_table.rowCount()):
                original = self._review_rows[row] if row < len(self._review_rows) else {}
                action_widget = self.review_table.cellWidget(row, 4)
                action = action_widget.currentData() if action_widget is not None else "keep"
                confidence_text = self.review_table.item(row, 3).text() if self.review_table.item(row, 3) else ""
                try:
                    confidence = float(confidence_text.replace(",", ".")) if confidence_text else None
                except ValueError:
                    confidence = original.get("confidence")
                rows.append({
                    "cluster_key": self.review_table.item(row, 0).text() if self.review_table.item(row, 0) else "",
                    "faces": self.review_table.item(row, 1).text() if self.review_table.item(row, 1) else "0",
                    "files": self.review_table.item(row, 2).text() if self.review_table.item(row, 2) else "0",
                    "confidence": confidence,
                    "avg_det_score": original.get("avg_det_score"),
                    "min_det_score": original.get("min_det_score"),
                    "max_det_score": original.get("max_det_score"),
                    "action": action,
                    "name": self.review_table.item(row, 5).text() if self.review_table.item(row, 5) else "",
                    "merge_into": self.review_table.item(row, 6).text() if self.review_table.item(row, 6) else "",
                    "notes": self.review_table.item(row, 7).text() if self.review_table.item(row, 7) else "",
                    "thumbnails": original.get("thumbnails", []),
                })
            return rows

        def save_review_decisions_from_ui(self) -> Optional[Any]:
            output = self.output_path_from_ui_or_result()
            if not output:
                self._warn(self._tx("Сначала выберите output/result папку.", "Choose the output/result folder first."))
                return None
            try:
                result = backend.save_review_ui_decisions(output, self._collect_review_rows_from_table())
                self._log_event(f"[reports] Saved {result.rows_saved} review decision row(s): {result.names_path}")
                if result.warnings:
                    issues = tuple(
                        backend.ui_issue("review_save_warning", "warning", "reports", "Review save warning", warning, action="Fix merge rules before apply-names if needed.")
                        for warning in result.warnings
                    )
                    self._log_status_report(backend.ui_status_report(issues, summary="Review decisions saved with warnings"))
                self.refresh_reports_review(initial=True)
                self.update_result_buttons()
                self._update_post_run_actions_label()
                self._log_event(self._tx("[reports] Следующий шаг: примените имена, чтобы создать final/final_review.", "[reports] Next step: apply names to create final/final_review."))
                return result
            except Exception as exc:
                self._log_status_report(backend.ui_status_report((backend.issue_from_exception(exc, source="reports", code="review_save_failed", include_traceback=False),), summary="Review decision save failed"))
                return None

        def start_apply_names_from_review_ui(self) -> None:
            """Run apply-names as an isolated job without changing the main run form.

            v66.6 changed the visible ``mode`` field to ``apply-names`` before
            calling ``start_job()``.  That made the normal Start button inherit
            the advanced apply-names mode on later runs.  Keep the dedicated
            Review clusters/apply-names workflow, but build its RunConfig from a
            temporary value dict so the main form and saved session remain on
            the user's normal pipeline mode.
            """
            if self.job is not None and self.job.is_alive():
                self._warn(self._tx("Задача уже выполняется.", "A job is already running."))
                return
            output = self.output_path_from_ui_or_result()
            if not output:
                self._warn(self._tx("Сначала выберите output/result папку.", "Choose the output/result folder first."))
                return
            saved = self.save_review_decisions_from_ui()
            if saved is None:
                return

            try:
                values = dict(self.collect_ui_values())
                values["output_dir"] = str(output)
                values["mode"] = "apply-names"
                values["resume_existing_output"] = True
                if not str(values.get("input_dir") or "").strip():
                    try:
                        summary = backend.inspect_project(output)
                        values["input_dir"] = str(summary.input_dir or output)
                    except Exception:
                        values["input_dir"] = str(output)
                config = self.build_config_from_values(values)
            except Exception as exc:
                self._log_status_report(backend.ui_status_report((backend.issue_from_exception(exc, source="config", include_traceback=False),), summary="Apply-names config validation failed"))
                self._warn(str(exc))
                return

            self._log_event("[reports] Starting isolated backend mode=apply-names from Reports / review UI; main Start mode is unchanged.")
            self.start_job(config_override=config, save_session=False)

        def open_final_dir(self) -> None:
            output = self.output_path_from_ui_or_result()
            self._open_path((output / "final") if output else None)

        def open_final_review_dir(self) -> None:
            output = self.output_path_from_ui_or_result()
            self._open_path((output / "final_review") if output else None)

        def _update_reports_review_buttons(self) -> None:
            snapshot = self._review_snapshot
            def exists(key: str) -> bool:
                item = self._report_file_by_key(key)
                return bool(item and item.exists)
            output = self.output_path_from_ui_or_result()
            reports = output / "reports" if output else None
            diagnostics = self.diagnostics_path_from_ui_or_result() if output else None
            for attr in ("open_reports_folder_button", "open_reports_folder_button_2"):
                if hasattr(self, attr):
                    getattr(self, attr).setEnabled(bool(reports and reports.exists()))
            for attr in ("open_diagnostics_from_reports_button", "open_diagnostics_from_reports_button_2"):
                if hasattr(self, attr):
                    getattr(self, attr).setEnabled(bool(diagnostics and diagnostics.exists()))
            if hasattr(self, "open_output_from_reports_button"):
                self.open_output_from_reports_button.setEnabled(bool(output and output.exists()))
            if hasattr(self, "copy_reports_summary_button"):
                self.copy_reports_summary_button.setEnabled(bool(output))
            if hasattr(self, "open_selected_report_button"):
                selected = self._selected_report_file()
                self.open_selected_report_button.setEnabled(bool(selected and selected.exists))
            self.open_summary_csv_button.setEnabled(exists("summary_csv"))
            self.open_assignments_csv_button.setEnabled(exists("assignments_csv"))
            self.open_clusters_html_button.setEnabled(exists("clusters_html"))
            self.open_duplicates_csv_button.setEnabled(exists("duplicates_csv"))
            self.open_review_clusters_csv_button.setEnabled(exists("review_clusters_csv"))
            self.open_names_csv_button.setEnabled(exists("names_csv"))
            self.open_review_decisions_button.setEnabled(exists("review_decisions_csv"))
            for attr in ("open_problem_files_button", "open_problem_files_button_2"):
                if hasattr(self, attr):
                    getattr(self, attr).setEnabled(exists("problem_files_csv"))
                    item = self._report_file_by_key("problem_files_csv")
                    getattr(self, attr).setToolTip("" if (item and item.exists) else self._report_file_missing_note(item) if item else self._t("problem_files_missing_hint"))
            if hasattr(self, "open_review_decisions_button"):
                item = self._report_file_by_key("review_decisions_csv")
                self.open_review_decisions_button.setToolTip("" if (item and item.exists) else self._report_file_missing_note(item) if item else self._t("review_decisions_missing_hint"))
            can_review = bool(snapshot and snapshot.rows)
            for attr in ("save_review_button", "apply_names_button", "save_review_button_review", "apply_names_button_review"):
                if hasattr(self, attr):
                    getattr(self, attr).setEnabled(can_review)
            if hasattr(self, "open_names_from_review_button"):
                self.open_names_from_review_button.setEnabled(exists("names_csv"))
            final_exists = bool(output and (output / "final").exists())
            final_review_exists = bool(output and (output / "final_review").exists())
            for attr in ("open_final_button", "open_final_button_2"):
                if hasattr(self, attr):
                    getattr(self, attr).setEnabled(final_exists)
            for attr in ("open_final_review_button", "open_final_review_button_2"):
                if hasattr(self, attr):
                    getattr(self, attr).setEnabled(final_review_exists)

        # ------------------------------------------------------------------
        # Schema-driven form
        # ------------------------------------------------------------------
        def _session_value(self, name: str, default: Any = None) -> Any:
            if name == "input_dir":
                return getattr(self.session, "last_input_dir", None) or default
            if name == "output_dir":
                return getattr(self.session, "last_output_dir", None) or default
            attr_map = {
                "profile": "selected_profile",
                "mode": "selected_mode",
                "language": "language",
                "use_gpu": "use_gpu",
                "auto_cpu_fallback": "auto_cpu_fallback",
                "photo_assignment": "photo_assignment",
                "copy_group_photos": "copy_group_photos",
                "scan_workers": "scan_workers",
                "copy_workers": "copy_workers",
            }
            attr = attr_map.get(name)
            if attr:
                value = getattr(self.session, attr, None)
                if value not in (None, ""):
                    return value
            return default

        def _schema(self) -> Any:
            profile = str(self._session_value("profile", "normal") or "normal")
            model = None
            if "model" in self._field_widgets:
                try:
                    model = self._read_widget_value("model")
                except Exception:
                    model = None
            return backend.get_ui_run_config_schema(profile=profile, model=model, language=self._ui_language())

        def _clear_layout(self, layout: Any) -> None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                child_layout = item.layout()
                if widget is not None:
                    widget.deleteLater()
                elif child_layout is not None:
                    self._clear_layout(child_layout)

        def _build_schema_form(self) -> None:
            self._loading_form = True
            self._clear_layout(self.form_layout)
            self._sections.clear()
            self._field_specs.clear()
            self._field_widgets.clear()

            schema = self._schema()
            self._field_specs = {spec.name: spec for spec in schema.parameters}
            self.schema_label = QtWidgets.QLabel(
                f"UI schema v{schema.schema_version}; backend UI API v{schema.ui_api_version}; "
                f"profile={self._session_value('profile', schema.default_profile)}"
            )
            self.form_layout.addWidget(self.schema_label)

            for section in schema.sections:
                group = QtWidgets.QGroupBox(section.title + (("  · " + self._tx("расширенные", "advanced")) if section.advanced else ""))
                group.setToolTip(section.description)
                group.setProperty("advanced", bool(section.advanced))
                form = QtWidgets.QFormLayout(group)
                form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
                for field_name in section.fields:
                    spec = self._field_specs.get(field_name)
                    if spec is None:
                        continue
                    row_widget = self._create_field_row(spec)
                    label = spec.label + (" *" if spec.required else "")
                    form.addRow(label, row_widget)
                self._sections[section.key] = group
                self.form_layout.addWidget(group)

            self.form_layout.addStretch(1)
            self._loading_form = False
            self._connect_special_signals()
            self._update_advanced_visibility()

        def _initial_value_for_spec(self, spec: Any) -> Any:
            default = self._session_value(spec.name, spec.default)
            if spec.kind == "bool":
                return _as_bool(default)
            return default

        def _create_field_row(self, spec: Any) -> Any:
            if spec.kind == "path":
                container = QtWidgets.QWidget()
                row = QtWidgets.QHBoxLayout(container)
                row.setContentsMargins(0, 0, 0, 0)
                edit = QtWidgets.QLineEdit(_path_text(self._initial_value_for_spec(spec)))
                edit.setObjectName(spec.name)
                edit.setToolTip(spec.description)
                edit.editingFinished.connect(self._schedule_session_save)
                self._field_widgets[spec.name] = edit
                row.addWidget(edit)
                choose_button = QtWidgets.QPushButton(self._t("browse"))
                choose_button.clicked.connect(lambda _checked=False, name=spec.name: self.choose_path_field(name))
                row.addWidget(choose_button)
                if spec.name == "output_dir":
                    auto_button = QtWidgets.QPushButton(self._t("auto"))
                    auto_button.clicked.connect(self.suggest_output_dir)
                    row.addWidget(auto_button)
                return container

            if spec.kind == "bool":
                widget = QtWidgets.QCheckBox(spec.description or spec.label)
                widget.setObjectName(spec.name)
                widget.setChecked(bool(self._initial_value_for_spec(spec)))
                widget.stateChanged.connect(lambda *_: self._schedule_session_save())
                self._field_widgets[spec.name] = widget
                return widget

            if spec.kind == "choice":
                widget = QtWidgets.QComboBox()
                widget.setObjectName(spec.name)
                for option in spec.options:
                    label = str(option.label)
                    if option.warning:
                        label += " ⚠"
                    widget.addItem(label, option.value)
                    idx = widget.count() - 1
                    tooltip = str(option.description or "")
                    if option.warning:
                        tooltip = (tooltip + "\n" if tooltip else "") + str(option.warning)
                    if tooltip:
                        widget.setItemData(idx, tooltip, QtCore.Qt.ToolTipRole)
                self._set_combo_data(widget, self._initial_value_for_spec(spec))
                widget.currentIndexChanged.connect(lambda *_: self._schedule_session_save())
                self._field_widgets[spec.name] = widget
                return widget

            if spec.kind == "int":
                widget = QtWidgets.QSpinBox()
                widget.setObjectName(spec.name)
                widget.setRange(int(spec.minimum if spec.minimum is not None else -2147483648), int(spec.maximum if spec.maximum is not None else 2147483647))
                widget.setSingleStep(int(spec.step if spec.step is not None else 1))
                widget.setValue(int(self._initial_value_for_spec(spec) or 0))
                widget.valueChanged.connect(lambda *_: self._schedule_session_save())
                self._field_widgets[spec.name] = widget
                return widget

            if spec.kind == "float":
                widget = QtWidgets.QDoubleSpinBox()
                widget.setObjectName(spec.name)
                widget.setDecimals(4)
                widget.setRange(float(spec.minimum if spec.minimum is not None else -1e9), float(spec.maximum if spec.maximum is not None else 1e9))
                widget.setSingleStep(float(spec.step if spec.step is not None else 0.01))
                widget.setValue(float(self._initial_value_for_spec(spec) or 0.0))
                widget.valueChanged.connect(lambda *_: self._schedule_session_save())
                self._field_widgets[spec.name] = widget
                return widget

            widget = QtWidgets.QLineEdit("" if self._initial_value_for_spec(spec) is None else str(self._initial_value_for_spec(spec)))
            widget.setObjectName(spec.name)
            widget.setToolTip(spec.description)
            widget.editingFinished.connect(self._schedule_session_save)
            self._field_widgets[spec.name] = widget
            return widget

        def _connect_special_signals(self) -> None:
            for name, widget in self._field_widgets.items():
                spec = self._field_specs.get(name)
                if spec is None:
                    continue
                try:
                    if spec.kind in {"path", "str", "int_or_none"}:
                        widget.textChanged.connect(lambda *_args: self._on_form_value_changed())
                    elif spec.kind == "choice":
                        widget.currentIndexChanged.connect(lambda *_args: self._on_form_value_changed())
                    elif spec.kind == "bool":
                        widget.stateChanged.connect(lambda *_args: self._on_form_value_changed())
                    elif spec.kind in {"int", "float"}:
                        widget.valueChanged.connect(lambda *_args: self._on_form_value_changed())
                except Exception:
                    pass

            profile_widget = self._field_widgets.get("profile")
            if profile_widget is not None:
                profile_widget.currentIndexChanged.connect(lambda *_: self._on_profile_changed())
            model_widget = self._field_widgets.get("model")
            if model_widget is not None:
                model_widget.currentIndexChanged.connect(lambda *_: self._on_model_changed())
            input_widget = self._field_widgets.get("input_dir")
            if input_widget is not None:
                input_widget.editingFinished.connect(self._suggest_output_if_empty)
                input_widget.editingFinished.connect(lambda *_: self.refresh_resume_projects())

        def _set_combo_data(self, combo: Any, value: Any) -> None:
            for index in range(combo.count()):
                if combo.itemData(index) == value:
                    combo.setCurrentIndex(index)
                    return

        def _set_widget_value(self, name: str, value: Any) -> None:
            widget = self._field_widgets.get(name)
            spec = self._field_specs.get(name)
            if widget is None or spec is None:
                return
            if spec.kind == "bool":
                widget.setChecked(_as_bool(value))
            elif spec.kind == "choice":
                self._set_combo_data(widget, value)
            elif spec.kind in {"int", "float"}:
                widget.setValue(value if value is not None else 0)
            else:
                widget.setText("" if value is None else str(value))

        def _read_widget_value(self, name: str) -> Any:
            widget = self._field_widgets[name]
            spec = self._field_specs[name]
            if spec.kind == "bool":
                return bool(widget.isChecked())
            if spec.kind == "choice":
                return widget.currentData()
            if spec.kind == "int":
                return int(widget.value())
            if spec.kind == "float":
                return float(widget.value())
            if spec.kind == "int_or_none":
                text = widget.text().strip()
                return None if text.lower() in {"", "none", "null", "auto"} else int(text)
            return widget.text().strip()

        def collect_ui_values(self) -> Dict[str, Any]:
            return {name: self._read_widget_value(name) for name in self._field_widgets}

        def _on_profile_changed(self) -> None:
            if self._loading_form:
                return
            profile = str(self._read_widget_value("profile") or "normal")
            model = self._read_widget_value("model") if "model" in self._field_widgets else None
            schema = backend.get_ui_run_config_schema(profile=profile, model=model, language=self._ui_language())
            new_specs = {spec.name: spec for spec in schema.parameters}
            self._field_specs.update(new_specs)
            preserve = {"input_dir", "output_dir", "profile", "mode", "language", "use_gpu", "auto_cpu_fallback", "resume_existing_output", "make_bug_report"}
            self._loading_form = True
            try:
                for name, spec in new_specs.items():
                    if name in preserve:
                        continue
                    self._set_widget_value(name, self._session_value(name, spec.default))
                self.schema_label.setText(f"UI schema v{schema.schema_version}; backend UI API v{schema.ui_api_version}; profile={profile}")
            finally:
                self._loading_form = False
            self._schedule_session_save()

        def _on_model_changed(self) -> None:
            if self._loading_form:
                return
            # Model-specific min/max hints are kept in ui_schema. Re-reading the
            # schema here keeps future UI validation aligned without rebuilding
            # the whole form or importing console wizard logic.
            profile = str(self._read_widget_value("profile") or "normal")
            model = str(self._read_widget_value("model") or "")
            self._field_specs.update({spec.name: spec for spec in backend.get_ui_parameter_schema(profile=profile, model=model, language=self._ui_language())})
            self._schedule_session_save()

        def _update_advanced_visibility(self) -> None:
            show = self.show_advanced_check.isChecked()
            for group in self._sections.values():
                if bool(group.property("advanced")):
                    group.setVisible(show)

        # ------------------------------------------------------------------
        # v63+ usability helpers: form readiness, highlights and copy actions
        # ------------------------------------------------------------------
        def _on_form_value_changed(self) -> None:
            if self._loading_form:
                return
            self._schedule_session_save()
            self._update_form_readiness()
            self.update_result_buttons()
            self._update_runtime_status_block()
            self._update_beginner_action_block()
            self._update_onboarding_block()

        def _set_path_widget_state(self, name: str, state: str, message: str = "") -> None:
            widget = self._field_widgets.get(name)
            if widget is None:
                return
            if state == "error":
                widget.setStyleSheet("QLineEdit { border: 1px solid #c62828; background: #ffebee; }")
            elif state == "warning":
                widget.setStyleSheet("QLineEdit { border: 1px solid #f9a825; background: #fff8e1; }")
            elif state == "ok":
                widget.setStyleSheet("QLineEdit { border: 1px solid #2e7d32; }")
            else:
                widget.setStyleSheet("")
            if message:
                widget.setToolTip(message)

        def _form_readiness(self) -> Tuple[bool, List[str], List[str]]:
            errors: List[str] = []
            warnings: List[str] = []
            input_text = str(self._read_widget_value("input_dir") or "").strip() if "input_dir" in self._field_widgets else ""
            output_text = str(self._read_widget_value("output_dir") or "").strip() if "output_dir" in self._field_widgets else ""
            mode = str(self._read_widget_value("mode") or "all") if "mode" in self._field_widgets else "all"
            resume_existing = bool(self._read_widget_value("resume_existing_output")) if "resume_existing_output" in self._field_widgets else False

            if not input_text:
                errors.append(self._t("readiness_input_required"))
                self._set_path_widget_state("input_dir", "error", self._t("path_input_required"))
            elif not Path(input_text).expanduser().exists():
                errors.append(self._t("readiness_input_not_found", path=input_text))
                self._set_path_widget_state("input_dir", "error", self._t("path_input_not_found"))
            else:
                self._set_path_widget_state("input_dir", "ok", self._t("path_input_ok"))

            if not output_text:
                warnings.append(self._t("readiness_output_empty"))
                self._set_path_widget_state("output_dir", "warning", self._t("path_output_empty"))
            else:
                output_path = Path(output_text).expanduser()
                if backend.is_output_inside_input(input_text, output_text):
                    warnings.append(self._t("readiness_output_inside_input"))
                    self._set_path_widget_state("output_dir", "warning", self._t("path_output_inside_input"))
                elif output_path.exists() and not resume_existing and mode in {"all", "scan"}:
                    warnings.append(self._t("readiness_output_exists"))
                    self._set_path_widget_state("output_dir", "warning", self._t("path_output_exists"))
                else:
                    self._set_path_widget_state("output_dir", "ok", self._t("path_output_ok"))

            if mode in {"apply-names", "review-clusters", "report", "copy", "cluster", "assign"} and output_text and not Path(output_text).expanduser().exists():
                warnings.append(self._t("readiness_mode_needs_existing", mode=mode))
            return not errors, errors, warnings

        def _update_form_readiness(self) -> None:
            if not hasattr(self, "readiness_label"):
                return
            if self.job is not None and self.job.is_alive():
                self.start_button.setEnabled(False)
                self.readiness_label.setText(self._t("readiness_running"))
                self.readiness_label.setStyleSheet("QLabel { color: #555; }")
                return
            ok, errors, warnings = self._form_readiness()
            if ok and not warnings:
                self.readiness_label.setText(self._t("readiness_ok"))
                self.readiness_label.setStyleSheet("QLabel { color: #2e7d32; font-weight: 600; }")
            elif ok:
                self.readiness_label.setText(self._t("readiness_warnings_prefix") + " ".join(warnings[:2]))
                self.readiness_label.setStyleSheet("QLabel { color: #8a5a00; font-weight: 600; }")
            else:
                self.readiness_label.setText(self._t("readiness_errors_prefix") + " ".join(errors[:2]))
                self.readiness_label.setStyleSheet("QLabel { color: #b00020; font-weight: 600; }")
            self.start_button.setEnabled(ok)

        def _run_summary_text(self) -> str:
            if self.last_result_snapshot is not None and self.result_log.toPlainText().strip():
                return self.result_log.toPlainText().strip()
            try:
                return backend.build_run_summary(self.collect_ui_values(), language=getattr(self.polish_settings, "language", "auto"))
            except Exception:
                return "Tuned Image Sorter run summary is not available yet."

        def copy_run_summary(self) -> None:
            QtWidgets.QApplication.clipboard().setText(self._run_summary_text())
            self._log_event("[ui] Run summary copied to clipboard.")

        def copy_paths_summary(self) -> None:
            try:
                values = self.collect_ui_values()
            except Exception:
                values = {}
            text = backend.build_paths_summary(values, output_dir=self.output_path_from_ui_or_result(), bug_report_path=self.last_bug_report_path, language=getattr(self.polish_settings, "language", "auto"))
            QtWidgets.QApplication.clipboard().setText(text)
            self._log_event("[ui] Paths summary copied to clipboard.")

        def _confirm_run_summary_text(self, config: Any) -> str:
            values = self.collect_ui_values()
            summary = backend.build_run_summary(values, language=getattr(self.polish_settings, "language", "auto"))
            ok, errors, warnings = self._form_readiness()
            lines = [summary, "", self._t("confirm_readiness"), "OK" if ok else "ERROR"]
            if warnings:
                lines.extend(["", self._t("confirm_warnings")] + [f"- {warning}" for warning in warnings])
            if errors:
                lines.extend(["", self._t("confirm_errors")] + [f"- {error}" for error in errors])
            lines.extend(["", self._t("confirm_pipeline_note")])
            return "\n".join(lines)

        # ------------------------------------------------------------------
        # Session persistence and path helpers
        # ------------------------------------------------------------------
        def _schedule_session_save(self) -> None:
            if self._loading_form:
                return
            self.session_save_timer.start()

        def save_session_from_form(self) -> None:
            try:
                values = self.collect_ui_values()
                changes: Dict[str, Any] = {}
                mapping = {
                    "input_dir": "last_input_dir",
                    "output_dir": "last_output_dir",
                    "profile": "selected_profile",
                    "mode": "selected_mode",
                    "language": "language",
                    "use_gpu": "use_gpu",
                    "auto_cpu_fallback": "auto_cpu_fallback",
                    "photo_assignment": "photo_assignment",
                    "copy_group_photos": "copy_group_photos",
                    "scan_workers": "scan_workers",
                    "copy_workers": "copy_workers",
                }
                for ui_name, state_name in mapping.items():
                    if ui_name in values:
                        changes[state_name] = values[ui_name]
                self.session = backend.update_ui_session_state(self.session, **changes)
                if hasattr(self, "ui_language_combo"):
                    self.polish_settings = self._collect_polish_settings()
                    self.session = backend.apply_ui_polish_settings_to_session(self.session, self.polish_settings)
                backend.save_ui_session_state(self.session, self.session_path)
                self.session_label.setText(f"{self._t('session_saved')}: {self.session_path}")
            except Exception as exc:
                self._log_event(f"[session warning] {type(exc).__name__}: {exc}")

        def choose_path_field(self, name: str) -> None:
            current = _path_text(self._read_widget_value(name)) if name in self._field_widgets else ""
            if not current and name == "output_dir" and "input_dir" in self._field_widgets:
                current = _path_text(self._read_widget_value("input_dir"))
            start = current or str(Path.home())
            title = self._t("dialog_select_input") if name == "input_dir" else self._t("dialog_select_output")
            path = QtWidgets.QFileDialog.getExistingDirectory(self, title, start)
            if path:
                self._set_widget_value(name, path)
                if name == "input_dir":
                    self._suggest_output_if_empty()
                    self.refresh_resume_projects()
                if name == "output_dir":
                    self.refresh_reports_review()
                    if hasattr(self, "support_summary_text"):
                        self._render_support_panel_summary()
                self._schedule_session_save()

        def _suggest_output_if_empty(self) -> None:
            try:
                if "output_dir" not in self._field_widgets:
                    return
                if str(self._read_widget_value("output_dir") or "").strip():
                    return
                self.suggest_output_dir()
            except Exception:
                return

        def _apply_gpu_lite_default_acceleration(self) -> None:
            """Prefer GPU mode by default in the GPU Lite SKU once local runtime is ready."""
            try:
                from face_sorter_mvp.core.gpu_lite_runtime import activate_gpu_lite_runtime_paths, gpu_lite_runtime_status, is_gpu_lite_package
                if not is_gpu_lite_package():
                    return
                widget = self._field_widgets.get("use_gpu")
                if widget is None or bool(widget.isChecked()):
                    return
                activate_gpu_lite_runtime_paths()
                status = gpu_lite_runtime_status()
                if not bool(getattr(status, "ok", False)):
                    return
                self._set_widget_value("use_gpu", True)
                self._log_event("[gpu-lite] Local CUDA runtime is ready; GPU mode enabled by default for GPU Lite.")
                self._schedule_session_save()
            except Exception as exc:
                try:
                    self._log_event(f"[gpu-lite warning] Could not apply GPU Lite default acceleration: {type(exc).__name__}: {exc}")
                except Exception:
                    pass

        def _promote_gpu_lite_config_if_ready(self, config: Any) -> Any:
            """Turn on GPU for GPU Lite before Start when runtime is installed but the session still says CPU."""
            try:
                if bool(getattr(config, "use_gpu", False)):
                    return config
                from face_sorter_mvp.core.gpu_lite_runtime import activate_gpu_lite_runtime_paths, gpu_lite_runtime_status, is_gpu_lite_package
                if not is_gpu_lite_package():
                    return config
                activate_gpu_lite_runtime_paths()
                status = gpu_lite_runtime_status()
                if not bool(getattr(status, "ok", False)):
                    return config
                if "use_gpu" in self._field_widgets:
                    self._set_widget_value("use_gpu", True)
                values = dict(self.collect_ui_values())
                values["use_gpu"] = True
                self._log_event("[gpu-lite] Start requested with GPU Lite runtime ready; switching this run to GPU automatically.")
                self._schedule_session_save()
                return self.build_config_from_values(values)
            except Exception as exc:
                try:
                    self._log_event(f"[gpu-lite warning] Could not auto-enable GPU before Start: {type(exc).__name__}: {exc}")
                except Exception:
                    pass
                return config

        def suggest_output_dir(self) -> None:
            input_path = str(self._read_widget_value("input_dir") or "").strip() if "input_dir" in self._field_widgets else ""
            if not input_path:
                self._warn(self._t("warn_select_input"))
                return
            try:
                self._set_widget_value("output_dir", str(backend.suggest_output_dir(input_path)))
                self._schedule_session_save()
            except Exception as exc:
                self._warn(self._t("warn_suggest_output_failed", error=exc))

        # ------------------------------------------------------------------
        # Config, validation and diagnostics actions
        # ------------------------------------------------------------------
        def build_config_from_values(self, values: Dict[str, Any]) -> Any:
            """Create a backend RunConfig from an explicit values dict.

            This keeps advanced actions, such as apply-names from Reports /
            review, from mutating the visible main form just to launch a job.
            """
            profile = str(values.get("profile") or "normal")
            model = str(values.get("model") or "") or None
            schema_errors = backend.validate_ui_values_against_schema(values, profile=profile, model=model)
            if schema_errors:
                raise ValueError("\n".join(schema_errors))
            input_dir = str(values.get("input_dir") or "").strip()
            if not input_dir:
                raise ValueError("Input folder is required.")
            output_dir = str(values.get("output_dir") or "").strip() or None
            overrides = backend.ui_values_to_overrides(values)
            return backend.create_run_config(
                input_dir=input_dir,
                output_dir=output_dir,
                profile=profile,
                mode=str(values.get("mode") or "all"),
                language=str(values.get("language") or "auto"),
                use_gpu=bool(values.get("use_gpu", False)),
                auto_cpu_fallback=bool(values.get("auto_cpu_fallback", True)),
                resume_existing_output=bool(values.get("resume_existing_output", False)),
                make_bug_report=bool(values.get("make_bug_report", False)),
                overrides=overrides,
            )

        def build_config(self) -> Any:
            return self.build_config_from_values(dict(self.collect_ui_values()))

        def run_preflight(self) -> None:
            self._log_event("\n" + self._tx("[preflight] Проверяю runtime без установки пакетов…", "[preflight] Checking runtime without installing packages…"))
            try:
                result = backend.runtime_preflight(run_gpu_smoke_test=False)
                status = backend.status_from_preflight_result(result)
                summary = backend.runtime_preflight_summary(run_gpu_smoke_test=False)
                self.last_preflight_result = result
                self.last_preflight_summary = dict(summary)
                self._update_runtime_status_block()
                self._update_onboarding_block()
                self._log_event(str(summary))
                self._log_status_report(status)
            except Exception as exc:
                self._log_status_report(backend.ui_status_report((backend.issue_from_exception(exc, source="preflight"),), summary="Preflight failed"))

        def show_quick_test_help(self) -> None:
            try:
                values = self.collect_ui_values()
            except Exception:
                values = {}
            text = backend.build_quick_test_help_text(values, language=self._ui_language())
            self._log_event("\n[onboarding] " + text.replace("\n", " | "))
            box = QtWidgets.QMessageBox(self)
            box.setIcon(QtWidgets.QMessageBox.Information)
            box.setWindowTitle(self._t("quick_test"))
            box.setText(text)
            box.setStandardButtons(QtWidgets.QMessageBox.Ok)
            box.exec()

        def run_self_test(self) -> None:
            self._log_event("\n" + self._tx("[self-test] Проверяю backend/UI contract без запуска ML…", "[self-test] Checking backend/UI contract without running ML…"))
            try:
                result = backend.run_backend_self_test()
                self._log_event(f"[self-test] ok={result.ok}, checks={len(result.checks)}, duration_ms={result.duration_ms}")
                for check in result.checks:
                    marker = "OK" if check.ok else "FAIL"
                    self._log_event(f"  [{marker}] {check.name}: {check.message}")
                self._log_status_report(backend.status_from_self_test_result(result))
            except Exception as exc:
                self._log_status_report(backend.ui_status_report((backend.issue_from_exception(exc, source="self_test"),), summary="Self-test failed"))

        def run_support_preflight(self) -> None:
            """Run the existing preflight action and refresh the support page."""
            self.run_preflight()
            self._render_support_panel_summary()

        def _maybe_refresh_gpu_lite_preflight_before_start(self, config: Any) -> None:
            """Prime GPU Lite runtime state before Start when the user skipped Environment check.

            GPU Lite installs CUDA runtime DLLs into a local per-user cache.  The
            first-run bootstrap activates that cache for the GUI process, but the
            legacy GPU runtime check is also primed by the normal preflight path.
            Running this lightweight preflight automatically prevents the first
            Start after setup from falling back to CPU until the user clicks
            ``Проверка окружения`` manually.
            """
            try:
                if not bool(getattr(config, "use_gpu", False)):
                    return
                from face_sorter_mvp.core.gpu_lite_runtime import activate_gpu_lite_runtime_paths, is_gpu_lite_package
                if not is_gpu_lite_package():
                    return
                activate_gpu_lite_runtime_paths()
                summary = backend.runtime_preflight_summary(run_gpu_smoke_test=False)
                self.last_preflight_summary = dict(summary)
                self._update_runtime_status_block()
                self._update_onboarding_block()
                cuda_ok = bool(self.last_preflight_summary.get("cuda_provider_available"))
                self._log_event("[gpu-lite] Auto preflight before Start: CUDAExecutionProvider=" + ("available" if cuda_ok else "not available"))
            except Exception as exc:
                self._log_event(f"[gpu-lite warning] Auto preflight before Start failed: {type(exc).__name__}: {exc}")

        def _result_health_status_report(self, summary: Any) -> Any:
            """Convert result-health into UI status without treating expected optional files as failures."""
            issues = []
            for message in tuple(getattr(summary, "errors", ()) or ()):  # required files/folders missing
                issues.append(backend.ui_issue(
                    "result_health_error",
                    "error",
                    "diagnostics",
                    self._tx("Result-health: проблема результата", "Result-health: result problem"),
                    str(message),
                    action=self._tx("Проверьте result/output папку и reports.", "Check the result/output folder and reports."),
                ))
            for message in tuple(getattr(summary, "warnings", ()) or ()):  # optional files/folders missing
                issues.append(backend.ui_issue(
                    "result_health_optional",
                    "info",
                    "diagnostics",
                    self._tx("Result-health: необязательный файл/папка", "Result-health: optional file/folder"),
                    str(message),
                    action=self._tx(
                        "Это нормальное состояние для части workflow: review_decisions.csv появляется после ручного review, "
                        "problem_files.csv — только при проблемных файлах, final/final_review — после apply-names.",
                        "This is normal for some workflows: review_decisions.csv appears after manual review, "
                        "problem_files.csv only when problematic files exist, and final/final_review after apply-names.",
                    ),
                ))
            return backend.ui_status_report(tuple(issues), summary="Result-health completed")

        def run_result_health_from_ui(self) -> None:
            """Check an existing output/result folder using core.result_health."""
            output = self.output_path_from_ui_or_result()
            if not output:
                self._warn(self._t("support_warn_no_output"))
                return
            output = Path(output)
            if not output.exists() or not output.is_dir():
                self._warn(self._t("warn_path_not_found", path=output))
                return
            try:
                self._log_event(f"[result-health] Checking output: {output}")
                summary = backend.build_result_health_summary(output, write_reports=True)
                self.last_result_health_summary = summary
                text = backend.format_result_health_text(summary, language=self._ui_language())
                if hasattr(self, "support_summary_text"):
                    self.support_summary_text.setPlainText(text)
                self._log_event(f"[result-health] Done. ok={summary.ok}, checked={summary.files_checked}, output={summary.output_dir}")
                for written in tuple(getattr(summary, "written_files", ()) or ()):  # additive reports/result_health_check.*
                    self._log_event(f"[result-health] Written: {written}")
                self._log_status_report(self._result_health_status_report(summary))
                self.refresh_reports_review(initial=True)
                self.update_result_buttons()
                self._render_support_panel_summary()
            except Exception as exc:
                self._log_status_report(backend.ui_status_report((backend.issue_from_exception(exc, source="diagnostics", code="result_health_failed"),), summary="Result-health failed"))

        def create_support_bundle_from_ui(self) -> None:
            """Create the existing bug-report/support-bundle ZIP from the GUI page."""
            if self.job is not None and self.job.is_alive():
                self._warn(self._t("support_warn_job_running"))
                return
            before = self.last_bug_report_path
            self._log_event("[support-bundle] Creating support-bundle through existing bug-report API…")
            self.create_bug_report_from_ui()
            if self.last_bug_report_path and self.last_bug_report_path != before:
                self._log_event(f"[support-bundle] Created: {self.last_bug_report_path}")
            self._render_support_panel_summary()
            self.update_result_buttons()

        def _preflight_package_line(self, package: Any) -> str:
            if not package:
                return "metadata: not visible"
            if hasattr(package, "to_dict"):
                package = package.to_dict()
            if isinstance(package, dict):
                installed = bool(package.get("installed"))
                version = str(package.get("version") or "")
                location = str(package.get("location") or "")
                status = "installed" if installed else "metadata not visible"
                if version:
                    status += f" ({version})"
                if location:
                    status += f" @ {location}"
                return status
            return str(package)

        def _support_runtime_section_lines(self) -> List[str]:
            lines: List[str] = ["", "runtime:"]
            summary = dict(self.last_preflight_summary or {})
            try:
                frozen = dict(summary.get("frozen") or backend.frozen_runtime_summary())
            except Exception:
                frozen = {}
            if not summary:
                lines.extend([
                    "  status: not checked yet",
                    f"  frozen: {frozen.get('is_frozen', False)}",
                    f"  executable: {frozen.get('executable') or '—'}",
                ])
                return lines

            providers = list(summary.get("onnx_providers") or [])
            cuda_active = bool(summary.get("cuda_provider_available"))
            effective = dict(summary.get("onnxruntime_effective") or {})
            cpu_pkg = summary.get("onnxruntime_package") or summary.get("onnxruntime")
            gpu_pkg = summary.get("onnxruntime_gpu_package")
            profile = "gpu-cuda" if cuda_active else "cpu"
            lines.extend([
                f"  status: {'OK' if summary.get('ok') else 'CHECK'}",
                f"  profile_detected: {profile}",
                f"  frozen: {frozen.get('is_frozen', False)}",
                f"  python: {summary.get('python_version') or '—'} | {summary.get('python_executable') or frozen.get('executable') or '—'}",
                f"  providers: {providers or '—'}",
            ])
            lines.extend([
                "",
                "cpu_runtime:",
                f"  onnxruntime metadata: {self._preflight_package_line(cpu_pkg)}",
                f"  onnxruntime import/module: {'OK' if effective.get('import_ok') else 'not confirmed'}"
                + (f" ({effective.get('module_version')})" if effective.get('module_version') else ""),
            ])
            lines.extend([
                "",
                "gpu_runtime:",
                f"  CUDAExecutionProvider: {cuda_active}",
                f"  NVIDIA GPU: {summary.get('nvidia_gpu') or '—'}",
                f"  onnxruntime-gpu metadata: {self._preflight_package_line(gpu_pkg)}",
            ])
            metadata_note = str(summary.get("metadata_note") or "")
            if metadata_note:
                lines.append(f"  note: {metadata_note}")
            if cuda_active:
                lines.append("  TensorRT: optional; PyInstaller warnings about nvinfer_10.dll/nvonnxparser_10.dll do not block CUDAExecutionProvider.")
            return lines

        def _support_result_health_section_lines(self) -> List[str]:
            lines: List[str] = ["", "result_health:"]
            summary = self.last_result_health_summary
            if summary is None:
                lines.append("  status: not checked yet")
                return lines
            warnings = tuple(getattr(summary, "warnings", ()) or ())
            errors = tuple(getattr(summary, "errors", ()) or ())
            lines.extend([
                f"  ok: {getattr(summary, 'ok', None)}",
                f"  files_checked: {getattr(summary, 'files_checked', None)}",
                f"  required_errors: {len(errors)}",
                f"  optional_warnings: {len(warnings)}",
                f"  written_files: {tuple(getattr(summary, 'written_files', ()) or ())}",
            ])
            if warnings:
                lines.append("  optional_warnings_meaning: review_decisions.csv/problem_files.csv/final/final_review/bug_reports may be absent in a normal run.")
            return lines

        def _support_bundle_section_lines(self) -> List[str]:
            output = self.output_path_from_ui_or_result()
            bug_reports = self.bug_reports_path_from_ui_or_result()
            lines: List[str] = ["", "support_bundle:"]
            lines.append(f"  bug_reports_exists: {bool(bug_reports and bug_reports.exists())}")
            lines.append(f"  last_support_bundle: {self.last_bug_report_path or '—'}")
            if output:
                lines.append("  note: support-bundle uses existing bug-report API and does not include source photos or embeddings.")
            return lines

        def _support_optional_warning_section_lines(self) -> List[str]:
            if self._ui_language().lower().startswith("en"):
                notes = [
                    "review_decisions.csv may be missing after a regular sort; it is created after saving Review clusters decisions.",
                    "problem_files.csv may be missing after a successful run with no bad/read-timeout files.",
                    "final and final_review may be missing until apply-names is used.",
                    "TensorRT DLL warnings in GPU PyInstaller output are optional when CUDAExecutionProvider works.",
                    "Frozen package metadata can be incomplete; provider visibility and CUDA smoke-test are more important than metadata alone.",
                ]
                title = "optional_warnings_reference:"
            else:
                notes = [
                    "review_decisions.csv может отсутствовать после обычной сортировки; он создаётся после сохранения решений Review clusters.",
                    "problem_files.csv может отсутствовать после успешного запуска без битых/timeout/read-error файлов.",
                    "final и final_review могут отсутствовать до применения apply-names.",
                    "TensorRT DLL warnings в GPU PyInstaller output необязательны, если CUDAExecutionProvider работает.",
                    "В frozen-сборке package metadata может быть неполной; важнее provider visibility и CUDA smoke-test.",
                ]
                title = "optional_warnings_reference:"
            return ["", title, *[f"  - {note}" for note in notes]]

        def _short_diagnostic_summary_text(self) -> str:
            output = self.output_path_from_ui_or_result()
            reports = output / "reports" if output else None
            diagnostics = self.diagnostics_path_from_ui_or_result()
            caps = backend.backend_capabilities()
            lines = [
                "Tuned Image Sorter diagnostic summary",
                f"version: {caps.get('version')}",
                f"refactor_stage: {caps.get('refactor_stage')}",
                f"ui_api_version: {caps.get('ui_api_version')}",
                f"output: {output or '—'}",
                f"reports_exists: {bool(reports and reports.exists())}",
                f"diagnostics_exists: {bool(diagnostics and diagnostics.exists())}",
            ]
            lines.extend(self._support_runtime_section_lines())
            lines.extend(self._support_result_health_section_lines())
            lines.extend(self._support_bundle_section_lines())
            lines.extend(self._support_optional_warning_section_lines())
            return "\n".join(lines)

        def _render_support_panel_summary(self) -> None:
            if not hasattr(self, "support_summary_text"):
                return
            output = self.output_path_from_ui_or_result()
            reports = output / "reports" if output else None
            diagnostics = self.diagnostics_path_from_ui_or_result()
            bug_reports = self.bug_reports_path_from_ui_or_result()
            if hasattr(self, "support_path_label"):
                self.support_path_label.setText(self._t(
                    "support_path_status",
                    output=output or "—",
                    reports=(reports if reports else "—"),
                    diagnostics=(diagnostics if diagnostics else "—"),
                    bug_reports=(bug_reports if bug_reports else "—"),
                ))
            parts = [self._short_diagnostic_summary_text()]
            if self.last_result_health_summary is not None:
                parts.extend([
                    "",
                    "--- result_health_check.txt ---",
                    backend.format_result_health_text(self.last_result_health_summary, language=self._ui_language()).strip(),
                ])
            self.support_summary_text.setPlainText("\n".join(parts).strip() + "\n")
            self.update_result_buttons()

        def copy_short_diagnostic_summary(self) -> None:
            text = self._short_diagnostic_summary_text()
            QtWidgets.QApplication.clipboard().setText(text)
            self._log_event("[support] Short diagnostic summary copied to clipboard.")

        def start_job(self, config_override: Any = None, *, save_session: bool = True) -> None:
            if self.job is not None and self.job.is_alive():
                self._warn(self._tx("Задача уже выполняется.", "A job is already running."))
                return
            try:
                config = config_override if config_override is not None else self.build_config()
                if config_override is None:
                    config = self._promote_gpu_lite_config_if_ready(config)
                if config_override is None and str(getattr(config, "mode", "") or "") == "apply-names":
                    # Regression guard for sessions saved by v66.6: the normal
                    # Start button must not unexpectedly run only apply-names.
                    # Dedicated Reports / review buttons still use apply-names
                    # through config_override.
                    self._log_event("[guard] Main Start had stale mode=apply-names; switching to mode=all. Use Reports / review to apply names only.")
                    if "mode" in self._field_widgets:
                        self._set_widget_value("mode", "all")
                    config = self.build_config()
            except Exception as exc:
                self._log_status_report(backend.ui_status_report((backend.issue_from_exception(exc, source="config", include_traceback=False),), summary="Form validation failed"))
                self._warn(str(exc))
                return

            self._maybe_refresh_gpu_lite_preflight_before_start(config)

            validation = backend.validate_config_for_ui(config)
            validation_status = backend.status_from_validation_result(validation)
            self._log_status_report(validation_status)
            if not validation.ok:
                self._warn("\n".join(validation.errors))
                return
            for warning in validation.warnings:
                self._log_event(f"[validation warning] {warning}")

            if bool(getattr(self.polish_settings, "confirm_before_run", True)):
                summary = self._confirm_run_summary_text(config)
                box = QtWidgets.QMessageBox(self)
                box.setIcon(QtWidgets.QMessageBox.Question)
                box.setWindowTitle(backend.ui_text('run_confirm_title', self.polish_settings.language))
                box.setText(backend.ui_text('run_confirm_body', self.polish_settings.language))
                box.setDetailedText(summary)
                box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                box.setDefaultButton(QtWidgets.QMessageBox.No)
                answer = box.exec()
                if answer != QtWidgets.QMessageBox.Yes:
                    self._log_event("[job] Start cancelled by user confirmation dialog.")
                    return

            if save_session:
                try:
                    self.session = backend.config_to_ui_session_state(config, self.session)
                    backend.save_ui_session_state(self.session, self.session_path)
                except Exception as exc:
                    self._log_event(f"[session warning] {type(exc).__name__}: {exc}")

            self.current_config = config
            self.last_result_snapshot = None
            self.last_bug_report_path = None
            self.last_output_dir = config.output_dir
            self._stage_order = self._build_stage_order(config)
            self._last_stage_progress.clear()
            self._stage_status.clear()
            self._stage_messages.clear()
            self._progress_log_state.clear()
            self._event_counts.clear()
            self._init_stage_table(self._stage_order)
            self.progress.setValue(0)
            self.stage_label.setText(self._t("status_starting"))
            self.result_log.clear()
            self.status_log.clear()
            self.job_meta_label.setText(self._t("job_meta_starting"))
            self.update_result_buttons()

            self.job = backend.create_backend_job(config, autostart=True)
            self._log_event("\n[job] Backend job started.")
            self._select_main_page(self._t("nav_progress"))
            self.start_button.setEnabled(False)
            self.cancel_button.setEnabled(True)
            self.preflight_button.setEnabled(False)
            self.selftest_button.setEnabled(False)
            self.timer.start()

        def cancel_job(self) -> None:
            if self.job is None:
                return
            snapshot = self.job.request_cancel("Cancel requested from PySide6 UI.")
            self.stage_label.setText(self._t("status_cancel_requested", stage=self._human_stage_label(snapshot.current_stage)))
            self._log_event("[job] Soft cancel requested. Hard cancellation is not supported in this build.")

        def poll_job(self) -> None:
            if self.job is None:
                self.timer.stop()
                return
            try:
                events = self.job.drain_events()
                for event in events:
                    self._show_event(event)
                snapshot = self.job.snapshot()
                self._update_progress_from_snapshot(snapshot)
                if snapshot.state in {"done", "error"}:
                    self.timer.stop()
                    self.start_button.setEnabled(True)
                    self.cancel_button.setEnabled(False)
                    self.preflight_button.setEnabled(True)
                    self.selftest_button.setEnabled(True)
                    self.last_result_snapshot = snapshot
                    self.last_output_dir = snapshot.output_dir or self.last_output_dir
                    self.last_bug_report_path = snapshot.bug_report_path or self.last_bug_report_path
                    final_status = backend.status_from_job_snapshot(snapshot, events)
                    self._log_status_report(final_status)
                    self._render_result(snapshot)
                    self._remember_recent_project(snapshot)
                    self.refresh_reports_review(initial=True)
                    self.update_result_buttons()
                    self._update_form_readiness()
                    if snapshot.state == "done":
                        self.progress.setRange(0, 100)
                        self.progress.setFormat(f"100% — {self._human_stage_label('done')}")
                        self.progress.setValue(100)
                        for item in self._stage_order:
                            if self._stage_status.get(item) not in {"error", "warning"}:
                                self._stage_table_set(item, "done", progress=1.0)
                        self._log_event(f"[job] Done. status={snapshot.result_status}, output={snapshot.output_dir}")
                        if bool(getattr(self.polish_settings, "auto_open_reports_after_run", False)):
                            if str(getattr(self.current_config, "mode", "") or "") == "apply-names":
                                # The dedicated apply-names action produces final/final_review.
                                # Open final first, not reports, so the button matches the
                                # user's immediate task after naming clusters.
                                self.open_final_dir()
                            else:
                                self.open_reports_dir()
                    else:
                        self._log_event(f"[job] ERROR: {snapshot.error}")
            except Exception as exc:
                self._log_status_report(backend.ui_status_report((backend.issue_from_exception(exc, source="job"),), summary="UI polling failed"))

        # ------------------------------------------------------------------
        # Progress/results
        # ------------------------------------------------------------------
        def _build_stage_order(self, config: Any) -> List[str]:
            order = ["validate", "environment"]
            try:
                stages = list(backend.mode_stages(config.mode))
            except Exception:
                stages = []
            if stages != ["bug-report"]:
                order.append("database")
            order.extend(_stage_key(stage) for stage in stages)
            if bool(getattr(config, "make_bug_report", False)) and "bug_report" not in order:
                order.append("bug_report")
            order.append("done")
            compact: List[str] = []
            for stage in order:
                if stage not in compact:
                    compact.append(stage)
            return compact

        def _update_progress_from_snapshot(self, snapshot: Any) -> None:
            state = str(snapshot.state or "pending")
            stage = _stage_key(snapshot.current_stage or "")
            if stage:
                self._last_stage_progress[stage] = float(snapshot.progress_ratio) if snapshot.progress_ratio is not None else self._last_stage_progress.get(stage, 0.0)
            message = str(snapshot.last_message or "")
            display_state = "cancel requested" if bool(getattr(snapshot, "cancel_requested", False)) and state not in {"done", "error"} else state
            label = self._t("status_line", state=display_state, stage=self._human_stage_label(stage))
            if message:
                label += f": {message}"
            self.stage_label.setText(label)
            self._update_job_meta(snapshot)
            self._update_stage_table_from_snapshot(snapshot)

            if state == "done":
                self.progress.setRange(0, 100)
                self.progress.setFormat(f"100% — {self._human_stage_label('done')}")
                self.progress.setValue(100)
                for item in self._stage_order:
                    if self._stage_status.get(item) not in {"error", "warning"}:
                        self._stage_table_set(item, "done", progress=1.0)
                return
            if state == "error":
                self.progress.setFormat("error — see Status / errors")
                return
            if not self._stage_order or not stage:
                return
            if stage not in self._stage_order:
                self._stage_order.insert(max(0, len(self._stage_order) - 1), stage)
                self._init_stage_table(self._stage_order)
            denominator = max(1, len(self._stage_order) - 1)
            index = self._stage_order.index(stage)
            local = self._last_stage_progress.get(stage, 0.0)
            overall = max(0.0, min(1.0, (index + local) / denominator))
            self.progress.setFormat(f"{int(overall * 100)}% — {self._human_stage_label(stage)}")
            self.progress.setValue(int(overall * 100))

        def _show_event(self, event: Any) -> None:
            kind = str(getattr(event, "kind", "event") or "event")
            stage = _stage_key(str(getattr(event, "stage", "") or ""))
            message = str(getattr(event, "message", "") or "")
            done = getattr(event, "done", None)
            total = getattr(event, "total", None)
            self._event_counts[kind] = self._event_counts.get(kind, 0) + 1

            if kind == "stage":
                self._mark_prior_stages_done(stage)
                self._stage_table_set(stage, "running", progress=None, message=message)
                self._log_event(f"[stage] {self._human_stage_label(stage)}" + (f": {message}" if message else ""))
                return

            if kind == "progress":
                ratio: Optional[float] = None
                if total:
                    ratio = max(0.0, min(1.0, float(done or 0) / float(total)))
                    self._last_stage_progress[stage] = ratio
                self._stage_table_set(stage, "running", progress=ratio, message=message or self._stage_messages.get(stage, ""))
                self._log_progress_event_throttled(stage, done, total, ratio)
                return

            if kind in {"warning", "error", "callback_error", "job_error"}:
                severity = "warning" if kind == "warning" else "error"
                self._stage_table_set(stage or "job", "warning" if severity == "warning" else "error", message=message)
                issue = backend.ui_issue(f"backend_{kind}", severity, "job", f"Backend {kind}", message, stage=stage, details=dict(getattr(event, "data", {}) or {}))
                self._log_status_report(backend.ui_status_report((issue,), summary=f"Backend {kind}"))
            elif kind == "job_done":
                for item in self._stage_order:
                    if item != "done" and self._stage_status.get(item) not in {"error", "warning"}:
                        self._stage_table_set(item, "done", progress=1.0)
                self._stage_table_set("done", "done", progress=1.0, message=message or "Backend job finished.")
            elif kind == "cancel_requested":
                self._stage_table_set(stage or "job", "cancel requested", message=message)

            prefix = f"[{kind}:{self._human_stage_label(stage)}]"
            self._log_event(f"{prefix} {message}" if message else prefix)

        def _init_stage_table(self, stages: Iterable[str]) -> None:
            self.stage_table.setRowCount(0)
            self._stage_rows.clear()
            for stage in stages:
                key = _stage_key(stage)
                if key in self._stage_rows:
                    continue
                row = self.stage_table.rowCount()
                self.stage_table.insertRow(row)
                self._stage_rows[key] = row
                self.stage_table.setItem(row, 0, QtWidgets.QTableWidgetItem(self._human_stage_label(key)))
                self.stage_table.setItem(row, 1, QtWidgets.QTableWidgetItem("pending"))
                self.stage_table.setItem(row, 2, QtWidgets.QTableWidgetItem("—"))
                self.stage_table.setItem(row, 3, QtWidgets.QTableWidgetItem(""))
                self._stage_status[key] = "pending"
            self.stage_table.resizeColumnsToContents()

        def _ensure_stage_row(self, stage: str) -> int:
            key = _stage_key(stage or "job")
            if key not in self._stage_rows:
                row = self.stage_table.rowCount()
                self.stage_table.insertRow(row)
                self._stage_rows[key] = row
                self.stage_table.setItem(row, 0, QtWidgets.QTableWidgetItem(self._human_stage_label(key)))
                self.stage_table.setItem(row, 1, QtWidgets.QTableWidgetItem("pending"))
                self.stage_table.setItem(row, 2, QtWidgets.QTableWidgetItem("—"))
                self.stage_table.setItem(row, 3, QtWidgets.QTableWidgetItem(""))
                self._stage_status[key] = "pending"
            return self._stage_rows[key]

        def _stage_table_set(self, stage: str, state: Optional[str] = None, *, progress: Optional[float] = None, message: str = "") -> None:
            key = _stage_key(stage or "job")
            row = self._ensure_stage_row(key)
            if state:
                self._stage_status[key] = state
                self.stage_table.item(row, 1).setText(state)
            if progress is not None:
                progress = max(0.0, min(1.0, float(progress)))
                self.stage_table.item(row, 2).setText(f"{int(progress * 100)}%")
            elif state == "done":
                self.stage_table.item(row, 2).setText("100%")
            if message:
                self._stage_messages[key] = str(message)
                self.stage_table.item(row, 3).setText(str(message))
            self.stage_table.resizeColumnsToContents()

        def _mark_prior_stages_done(self, current_stage: str) -> None:
            current_stage = _stage_key(current_stage)
            if current_stage not in self._stage_order:
                return
            current_index = self._stage_order.index(current_stage)
            for stage in self._stage_order[:current_index]:
                if stage == "done":
                    continue
                if self._stage_status.get(stage) in {"pending", "running", "cancel requested", None}:
                    self._stage_table_set(stage, "done", progress=1.0)

        def _update_stage_table_from_snapshot(self, snapshot: Any) -> None:
            state = str(snapshot.state or "pending")
            stage = _stage_key(snapshot.current_stage or "")
            if not stage:
                return
            if state == "error":
                self._stage_table_set(stage, "error", message=str(snapshot.error or snapshot.last_message or ""))
                return
            if state == "done":
                self._stage_table_set(stage, "done", progress=1.0, message=str(snapshot.last_message or ""))
                return
            if bool(getattr(snapshot, "cancel_requested", False)):
                self._stage_table_set(stage, "cancel requested", progress=snapshot.progress_ratio, message=str(snapshot.last_message or ""))
                return
            self._stage_table_set(stage, "running", progress=snapshot.progress_ratio, message=str(snapshot.last_message or ""))

        def _log_progress_event_throttled(self, stage: str, done: Any, total: Any, ratio: Optional[float]) -> None:
            import time as _time
            if self.verbose_progress_check.isChecked():
                if total:
                    self._log_event(f"[{self._human_stage_label(stage)}] progress {done}/{total}")
                else:
                    self._log_event(f"[{self._human_stage_label(stage)}] progress {done}")
                return
            now = _time.monotonic()
            previous = self._progress_log_state.get(stage)
            current_ratio = float(ratio if ratio is not None else -1.0)
            current_done = int(done or 0) if str(done or "").isdigit() else 0
            should_log = previous is None
            if previous is not None:
                last_time, last_ratio, last_done, last_total = previous
                if total and done == total:
                    should_log = True
                elif current_ratio >= 0 and last_ratio >= 0 and abs(current_ratio - last_ratio) >= 0.05:
                    should_log = True
                elif now - last_time >= 2.0 and current_done != last_done:
                    should_log = True
                elif total != last_total:
                    should_log = True
            if should_log:
                self._progress_log_state[stage] = (now, current_ratio, current_done, total)
                if total and ratio is not None:
                    self._log_event(f"[{self._human_stage_label(stage)}] progress {done}/{total} ({int(ratio * 100)}%)")
                else:
                    self._log_event(f"[{self._human_stage_label(stage)}] progress {done}")

        def _update_job_meta(self, snapshot: Any) -> None:
            warnings = int(getattr(snapshot, "warnings_count", 0) or self._event_counts.get("warning", 0))
            errors = int(getattr(snapshot, "errors_count", 0) or sum(self._event_counts.get(kind, 0) for kind in ("error", "callback_error", "job_error")))
            events_total = int(getattr(snapshot, "events_total", 0) or sum(self._event_counts.values()))
            duration = getattr(snapshot, "duration_ms", None)
            duration_text = "—" if duration is None else f"{duration / 1000:.1f}s"
            pending = getattr(snapshot, "events_pending", 0)
            job_id = getattr(snapshot, "job_id", "—")
            last_kind = getattr(snapshot, "last_event_kind", "") or "—"
            self.job_meta_label.setText(
                f"Job: {job_id} | state: {getattr(snapshot, 'state', '—')} | events: {events_total} "
                f"(+{pending} pending) | warnings: {warnings} | errors: {errors} | last: {last_kind} | duration: {duration_text}"
            )

        def _count_csv_rows(self, path: Path) -> int:
            if not path.exists():
                return 0
            try:
                with path.open("r", encoding="utf-8-sig", newline="") as f:
                    return max(0, sum(1 for _row in csv.reader(f)) - 1)
            except Exception:
                return 0

        def _folder_file_count(self, path: Path) -> int:
            if not path.exists():
                return 0
            try:
                return sum(1 for item in path.rglob("*") if item.is_file())
            except Exception:
                return 0

        def _folder_child_dir_count(self, path: Path) -> int:
            if not path.exists():
                return 0
            try:
                return sum(1 for item in path.iterdir() if item.is_dir())
            except Exception:
                return 0

        def _report_counts(self, output_dir: Path) -> Dict[str, int]:
            reports = output_dir / "reports"
            review = output_dir / "review"
            return {
                "summary_rows": self._count_csv_rows(reports / "summary.csv"),
                "assignment_rows": self._count_csv_rows(reports / "assignments.csv"),
                "review_cluster_rows": self._count_csv_rows(reports / "review_clusters.csv"),
                "duplicate_rows": self._count_csv_rows(reports / "duplicates.csv"),
                "problem_rows": self._count_csv_rows(reports / "problem_files.csv"),
                "person_folders": self._folder_child_dir_count(output_dir / "people"),
                "review_files": self._folder_file_count(review),
                "review_no_faces_files": self._folder_file_count(review / "no_faces"),
                "review_unknown_faces_files": self._folder_file_count(review / "unknown_faces"),
            }

        def _problem_files_count(self, output_dir: Path) -> int:
            return self._count_csv_rows(output_dir / "reports" / "problem_files.csv")

        def _render_result(self, snapshot: Any) -> None:
            self.result_log.clear()
            lines: List[str] = []
            output_dir = Path(snapshot.output_dir) if snapshot.output_dir else None
            reports_dir = output_dir / "reports" if output_dir else None
            summary = backend.inspect_project(output_dir) if output_dir else None
            problem_count = self._problem_files_count(output_dir) if output_dir else 0
            problem_summary = backend.load_problem_files_summary(reports_dir / "problem_files.csv") if reports_dir else None
            counts = self._report_counts(output_dir) if output_dir else {}
            status_text = snapshot.result_status or snapshot.state

            lines.append(f"Tuned Image Sorter {backend.SCRIPT_VERSION} — {self._t('run_result_title')}")
            lines.append("=" * 44)
            lines.append(f"status: {status_text}")
            lines.append(f"state: {snapshot.state}")
            lines.append(f"output_dir: {snapshot.output_dir or ''}")
            lines.append(f"reports_dir: {reports_dir or ''}")
            lines.append(f"diagnostics_dir: {self.diagnostics_path_from_ui_or_result() or ''}")
            lines.append(f"db_path: {snapshot.db_path or ''}")
            lines.append(f"bug_report_path: {snapshot.bug_report_path or self.last_bug_report_path or ''}")
            lines.append("")
            lines.append(self._t("run_user_summary"))
            lines.append("----------------------")
            if summary is not None:
                photos_processed = summary.files_scanned or summary.files_total or counts.get("assignment_rows", 0)
                clusters_found = counts.get("summary_rows", 0)
                lines.append(self._t("photos_processed", count=photos_processed))
                lines.append(self._t("summary_rows", count=clusters_found))
                lines.append(self._t("person_folders", count=counts.get("person_folders", 0)))
                lines.append(self._t("review_files_total", count=counts.get("review_files", 0)))
                lines.append(f"review/no_faces: {counts.get('review_no_faces_files', 0)}")
                lines.append(f"review/unknown_faces: {counts.get('review_unknown_faces_files', 0)}")
                lines.append(self._t("assignments_rows", count=counts.get("assignment_rows", 0)))
                lines.append(self._t("review_clusters_rows", count=counts.get("review_cluster_rows", 0)))
                lines.append(self._t("duplicates_rows", count=counts.get("duplicate_rows", 0)))
                lines.append(self._t("problem_files_rows", count=problem_count))
                lines.append(f"problem_files status: {self._problem_summary_status_line(problem_summary)}")
            else:
                lines.append(self._t("project_json_not_read"))
                lines.append(self._t("problem_files_rows", count=problem_count))
                lines.append(f"problem_files status: {self._problem_summary_status_line(problem_summary)}")
            lines.append("")
            lines.append(self._tx("Что можно открыть сейчас", "What you can open now"))
            lines.append("----------------------")
            lines.extend(self._result_action_lines(output_dir))
            lines.append("")
            lines.append(self._t("problem_files_section"))
            lines.append("----------------")
            lines.extend(self._problem_summary_lines(problem_summary))
            lines.append("")
            lines.append(self._t("explanations_section"))
            lines.append("---------")
            lines.append(self._t("explain_no_faces"))
            lines.append(self._t("explain_unknown_faces"))
            lines.append(self._t("explain_problem_files_missing"))
            lines.append(self._t("explain_open_reports"))
            lines.append("")
            lines.append(self._t("technical_summary_section"))
            lines.append("------------------")
            lines.append(f"stages_completed: {', '.join(snapshot.stages_completed or ())}")
            if summary is not None:
                lines.append(f"project_status: {summary.status}")
                lines.append(f"project_stage: {summary.stage}")
                lines.append(f"last_successful_stage: {summary.last_successful_stage}")
                lines.append(f"files_total: {summary.files_total if summary.files_total is not None else ''}")
                lines.append(f"files_scanned: {summary.files_scanned}")
                lines.append(f"copy_total: {summary.copy_total if summary.copy_total is not None else ''}")
                lines.append(f"files_copied: {summary.files_copied}")
            if snapshot.error:
                lines.append("")
                lines.append("error:")
                lines.append(str(snapshot.error))
                if snapshot.traceback:
                    lines.append("")
                    lines.append("traceback: captured by BackendJob; use bug-report/diagnostics for full details.")
            self.result_log.setPlainText("\n".join(lines))
            self._update_post_run_actions_label()

        def _remember_recent_project(self, snapshot: Any) -> None:
            output_dir = snapshot.output_dir or self.last_output_dir
            if not output_dir:
                return
            try:
                summary = backend.inspect_project(output_dir)
                self.session = backend.remember_recent_project(
                    self.session,
                    output_dir,
                    input_dir=summary.input_dir,
                    output_dir=summary.output_dir,
                    status=summary.status or snapshot.result_status,
                    last_successful_stage=summary.last_successful_stage,
                    updated_at=summary.updated_at or snapshot.finished_at,
                    display_text=summary.display_text,
                )
                backend.save_ui_session_state(self.session, self.session_path)
                self.refresh_resume_projects(initial=True)
            except Exception as exc:
                self._log_event(f"[session warning] recent project not saved: {type(exc).__name__}: {exc}")

        # ------------------------------------------------------------------
        # Bug report and open buttons
        # ------------------------------------------------------------------
        def _open_path(self, path: Optional[Path]) -> None:
            if not path:
                self._warn(self._t("warn_path_unknown"))
                return
            path = Path(path)
            if not path.exists():
                self._warn(self._t("warn_path_not_found", path=path))
                return
            if self._open_path_windows_no_console(path):
                return
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))

        def _open_path_windows_no_console(self, path: Path) -> bool:
            """Open a file/folder on Windows without spawning cmd.exe.

            QDesktopServices is usually fine, but on some Windows builds/Qt
            combinations folder/file opening may route through a shell helper
            that briefly flashes a console.  ShellExecuteW opens Explorer or the
            registered file handler directly and keeps GUI launcher behavior
            no-console for both CPU and GPU builds.
            """
            if os.name != "nt":
                return False
            try:
                import ctypes

                rc = ctypes.windll.shell32.ShellExecuteW(
                    None,
                    "open",
                    str(path),
                    None,
                    None,
                    1,
                )
                return int(rc) > 32
            except Exception:
                return False

        def output_path_from_ui_or_result(self) -> Optional[Path]:
            try:
                text = str(self._read_widget_value("output_dir") or "").strip()
                if text:
                    return Path(text)
            except Exception:
                pass
            if self.last_output_dir:
                return Path(self.last_output_dir)
            return None

        def open_output_dir(self) -> None:
            self._open_path(self.output_path_from_ui_or_result())

        def open_people_dir(self) -> None:
            output = self.output_path_from_ui_or_result()
            self._open_path((output / "people") if output else None)

        def open_review_dir(self) -> None:
            output = self.output_path_from_ui_or_result()
            self._open_path((output / "review") if output else None)

        def open_reports_dir(self) -> None:
            output = self.output_path_from_ui_or_result()
            self._open_path((output / "reports") if output else None)

        def diagnostics_path_from_ui_or_result(self) -> Optional[Path]:
            return self._diagnostics_candidate_for_output(self.output_path_from_ui_or_result())

        def open_diagnostics_dir(self) -> None:
            self._open_path(self.diagnostics_path_from_ui_or_result())

        def bug_reports_path_from_ui_or_result(self) -> Optional[Path]:
            output = self.output_path_from_ui_or_result()
            if output:
                return Path(output) / "bug_reports"
            if self.last_bug_report_path:
                return Path(self.last_bug_report_path).parent
            return None

        def open_bug_reports_dir(self) -> None:
            self._open_path(self.bug_reports_path_from_ui_or_result())

        def open_bug_report(self) -> None:
            self._open_path(self.last_bug_report_path)

        def _attach_ui_bug_report_context(self, args: Any) -> Any:
            try:
                args.ui_session_path = str(self.session_path)
                args.ui_session_state = self.session.to_dict() if hasattr(self.session, "to_dict") else {}
            except Exception:
                pass
            try:
                snapshot = self.job.snapshot() if self.job is not None else self.last_result_snapshot
                args.ui_job_snapshot = snapshot.to_dict() if hasattr(snapshot, "to_dict") else {}
            except Exception as exc:
                args.ui_job_snapshot = {"error": f"{type(exc).__name__}: {exc}"}
            args.ui_last_events = list(self._ui_log_tail[-300:])
            try:
                args.ui_status_log = self.status_log.toPlainText()[-20000:]
                args.ui_result_log = self.result_log.toPlainText()[-20000:]
                args.ui_reports_details = self.reports_details.toPlainText()[-12000:] if hasattr(self, "reports_details") else ""
                args.ui_diagnostics_text = self._current_diagnostics_text()[-40000:]
            except Exception:
                pass
            return args

        def create_bug_report_from_ui(self) -> None:
            try:
                config = self.current_config
                if config is None:
                    config = self.build_config()
                args = self._attach_ui_bug_report_context(config.to_namespace())
                path = backend.create_bug_report(args)
                if path:
                    self.last_bug_report_path = Path(path)
                    self._log_event(f"[bug-report] Created: {path}")
                    self.update_result_buttons()
                    if hasattr(self, "support_summary_text"):
                        self._render_support_panel_summary()
                    if self.last_result_snapshot is not None:
                        self._render_result(self.last_result_snapshot)
                else:
                    self._warn(self._tx("Bug-report не был создан. Подробности должны быть в PowerShell/log output.", "Bug-report was not created. Details should be in PowerShell/log output."))
            except Exception as exc:
                # Fallback for a partially filled form: still let the existing
                # bug-report API capture output/project diagnostics when possible.
                try:
                    output = self.output_path_from_ui_or_result()
                    input_dir = str(self._read_widget_value("input_dir") or "") if "input_dir" in self._field_widgets else ""
                    if output:
                        args = self._attach_ui_bug_report_context(SimpleNamespace(input=input_dir, output=str(output)))
                        path = backend.create_bug_report(args, error=exc)
                        if path:
                            self.last_bug_report_path = Path(path)
                            self._log_event(f"[bug-report] Created with fallback args: {path}")
                            self.update_result_buttons()
                            if hasattr(self, "support_summary_text"):
                                self._render_support_panel_summary()
                            return
                except Exception:
                    pass
                self._log_status_report(backend.ui_status_report((backend.issue_from_exception(exc, source="job", code="bug_report_create_failed"),), summary="Bug-report creation failed"))

        def update_result_buttons(self) -> None:
            output = self.output_path_from_ui_or_result()
            self.open_output_button.setEnabled(bool(output and output.exists()))
            reports = output / "reports" if output else None
            self.open_reports_button.setEnabled(bool(reports and reports.exists()))
            if hasattr(self, "open_reports_from_result_button"):
                self.open_reports_from_result_button.setEnabled(bool(reports and reports.exists()))
            people = output / "people" if output else None
            review = output / "review" if output else None
            bug_reports = output / "bug_reports" if output else None
            final = output / "final" if output else None
            final_review = output / "final_review" if output else None
            if hasattr(self, "open_people_button"):
                self.open_people_button.setEnabled(bool(people and people.exists()))
            if hasattr(self, "open_review_button"):
                self.open_review_button.setEnabled(bool(review and review.exists()))
            if hasattr(self, "open_bug_reports_from_result_button"):
                self.open_bug_reports_from_result_button.setEnabled(bool(bug_reports and bug_reports.exists()))
            if hasattr(self, "open_latest_zip_from_result_button"):
                self.open_latest_zip_from_result_button.setEnabled(bool(self.last_bug_report_path and self.last_bug_report_path.exists()))
            if hasattr(self, "open_final_from_result_button"):
                self.open_final_from_result_button.setEnabled(bool(final and final.exists()))
            if hasattr(self, "open_final_review_from_result_button"):
                self.open_final_review_from_result_button.setEnabled(bool(final_review and final_review.exists()))
            diagnostics = self.diagnostics_path_from_ui_or_result()
            if hasattr(self, "open_diagnostics_button"):
                self.open_diagnostics_button.setEnabled(bool(diagnostics and diagnostics.exists()))
            if hasattr(self, "open_diagnostics_from_result_button"):
                self.open_diagnostics_from_result_button.setEnabled(bool(diagnostics and diagnostics.exists()))
            self.open_bug_button.setEnabled(bool(self.last_bug_report_path and self.last_bug_report_path.exists()))
            self.create_bug_button.setEnabled(True)
            if hasattr(self, "copy_summary_button"):
                self.copy_summary_button.setEnabled(True)
            if hasattr(self, "copy_paths_button"):
                self.copy_paths_button.setEnabled(True)
            self._update_post_run_actions_label()
            if hasattr(self, "support_path_label"):
                reports = output / "reports" if output else None
                diagnostics = self.diagnostics_path_from_ui_or_result()
                bug_reports = self.bug_reports_path_from_ui_or_result()
                if hasattr(self, "support_result_health_button"):
                    self.support_result_health_button.setEnabled(bool(output and output.exists()))
                if hasattr(self, "support_bundle_button"):
                    running = bool(self.job is not None and self.job.is_alive())
                    self.support_bundle_button.setEnabled(not running)
                if hasattr(self, "support_open_reports_button"):
                    self.support_open_reports_button.setEnabled(bool(reports and reports.exists()))
                if hasattr(self, "support_open_bug_reports_button"):
                    self.support_open_bug_reports_button.setEnabled(bool(bug_reports and bug_reports.exists()))
                if hasattr(self, "support_open_diagnostics_button"):
                    self.support_open_diagnostics_button.setEnabled(bool(diagnostics and diagnostics.exists()))
                if hasattr(self, "support_open_last_bundle_button"):
                    self.support_open_last_bundle_button.setEnabled(bool(self.last_bug_report_path and self.last_bug_report_path.exists()))

        # ------------------------------------------------------------------
        # Logging/status helpers
        # ------------------------------------------------------------------
        def _append_log(self, widget: Any, message: str) -> None:
            widget.append(str(message))
            if self.auto_scroll_check.isChecked():
                cursor = widget.textCursor()
                cursor.movePosition(QtGui.QTextCursor.End)
                widget.setTextCursor(cursor)

        def _log_event(self, message: str) -> None:
            text = str(message)
            self._ui_log_tail.append(text)
            if len(self._ui_log_tail) > 500:
                self._ui_log_tail = self._ui_log_tail[-500:]
            self._append_log(self.events_log, text)

        def _log_status_report(self, report: Any) -> None:
            try:
                report = backend.humanize_status_report(report, language=self._ui_language())
            except Exception:
                pass
            self._last_status_report = report
            summary = backend.summarize_status_report(report)
            self._append_log(self.status_log, f"\n[status] {report.summary} | errors={summary.errors}, warnings={summary.warnings}, infos={summary.infos}")
            if not report.issues:
                self._append_log(self.status_log, "  OK")
                return
            for issue in report.issues:
                marker = "ERROR" if issue.severity == "error" else ("WARN" if issue.severity == "warning" else "INFO")
                title = f"  [{marker}] {issue.source}:{issue.code}"
                if issue.stage:
                    title += f" @{self._human_stage_label(issue.stage)}"
                self._append_log(self.status_log, title)
                if issue.title:
                    self._append_log(self.status_log, f"    {issue.title}")
                if issue.message:
                    self._append_log(self.status_log, f"    {issue.message}")
                details = dict(getattr(issue, "details", {}) or {})
                user_meaning = str(details.pop("user_meaning", "") or "")
                recommended_action = str(details.pop("recommended_action", "") or "")
                user_category = str(details.pop("user_category", "") or "")
                if user_meaning:
                    label = self._tx("Что это значит", "Meaning")
                    self._append_log(self.status_log, f"    {label}: {user_meaning}")
                if issue.action:
                    label = self._tx("Что сделать", "Action")
                    self._append_log(self.status_log, f"    {label}: {issue.action}")
                elif recommended_action:
                    label = self._tx("Что сделать", "Action")
                    self._append_log(self.status_log, f"    {label}: {recommended_action}")
                if user_category:
                    details.setdefault("user_category", user_category)
                if details:
                    compact = {k: ("<traceback captured; copy diagnostics or create bug-report for full details>" if k == "traceback" else v) for k, v in details.items() if k != "traceback" or v}
                    if compact:
                        self._append_log(self.status_log, f"    Details: {compact}")

        def clear_logs(self) -> None:
            self.events_log.clear()
            self.status_log.clear()
            self.result_log.clear()
            self.status_log.setPlaceholderText(self._t("status_placeholder"))
            self.result_log.setPlaceholderText(self._t("result_placeholder"))
            self._event_counts.clear()
            self._progress_log_state.clear()
            self.job_meta_label.setText(self._t("job_meta_empty"))

        def _current_diagnostics_text(self) -> str:
            parts = [
                "Tuned Image Sorter UI diagnostics",
                f"version: {backend.backend_capabilities().get('version')}",
                f"refactor_stage: {backend.backend_capabilities().get('refactor_stage')}",
                f"release_check: {backend.backend_capabilities().get('release_check')}",
                "",
                "Current job snapshot:",
            ]
            if self.job is not None:
                try:
                    parts.append(str(self.job.snapshot().to_dict()))
                except Exception as exc:
                    parts.append(f"<snapshot failed: {type(exc).__name__}: {exc}>")
            elif self.last_result_snapshot is not None:
                parts.append(str(self.last_result_snapshot.to_dict()))
            else:
                parts.append("<no job snapshot>")
            if self.last_preflight_summary:
                parts.extend([
                    "",
                    "Last runtime preflight summary:",
                    str(self.last_preflight_summary),
                ])
            parts.extend([
                "",
                "Events / logs:",
                self.events_log.toPlainText(),
                "",
                "Status / errors:",
                self.status_log.toPlainText(),
                "",
                "RunResult:",
                self.result_log.toPlainText(),
                "",
                "Reports / review:",
                self.reports_details.toPlainText() if hasattr(self, "reports_details") else "",
                "",
                "Diagnostics / support:",
                self.support_summary_text.toPlainText() if hasattr(self, "support_summary_text") else "",
            ])
            return "\n".join(parts)

        def copy_diagnostics(self) -> None:
            QtWidgets.QApplication.clipboard().setText(self._current_diagnostics_text())
            self._log_event("[ui] Diagnostics copied to clipboard.")

        def _warn(self, message: str) -> None:
            QtWidgets.QMessageBox.warning(self, "Tuned Image Sorter", message)
            self._log_event(f"[warning] {message}")

        def closeEvent(self, event: Any) -> None:  # noqa: N802 - Qt API name
            if self.job is not None and self.job.is_alive():
                answer = QtWidgets.QMessageBox.question(
                    self,
                    "Tuned Image Sorter",
                    self._t("close_running_job"),
                )
                if answer != QtWidgets.QMessageBox.Yes:
                    event.ignore()
                    return
            self.save_session_from_form()
            super().closeEvent(event)

    return MainWindow()


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------
def launch_ui(argv: Optional[list[str]] = None) -> int:
    """Launch the optional PySide6 UI and return the Qt exit code."""
    QtCore, QtGui, QtWidgets = _load_qt()
    app = QtWidgets.QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QtWidgets.QApplication(argv or sys.argv)
    else:
        try:
            if bool(app.property("face_sorter_temp_gpu_lite_app")):
                owns_app = True
                app.setProperty("face_sorter_temp_gpu_lite_app", False)
        except Exception:
            pass
    window = create_main_window()
    window.show()
    if owns_app:
        return int(app.exec())
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    """Command-line entry point for ``python -m face_sorter_mvp.ui``."""
    try:
        return launch_ui(argv)
    except Exception as exc:
        print(f"Tuned Image Sorter UI failed to start: {exc}", file=sys.stderr)
        if os.environ.get("FACE_SORTER_UI_DEBUG"):
            traceback.print_exc()
        return 2
