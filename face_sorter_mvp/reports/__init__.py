# -*- coding: utf-8 -*-
"""Report modules extracted for Tuned Image Sorter v62 / Этап 021."""
from __future__ import annotations

from .bug_report import collect_ui_bug_report_diagnostics, create_bug_report, diagnostics_dir_for_output, summarize_diagnostics
from .html_report import generate_html_report, generate_names_csv, generate_summary_csv
from .review_clusters import (
    apply_names,
    ask_review_action,
    compute_cluster_review_rows,
    ensure_review_decisions_for_rows,
    generate_review_clusters_csv,
    load_review_decisions,
    normalize_review_action,
    parse_review_confidence,
    print_review_cluster_help,
    resolve_review_decision,
    review_clusters_console,
    write_names_csv_from_decisions,
    write_review_decisions_report,
)

__all__ = [
    "create_bug_report",
    "collect_ui_bug_report_diagnostics",
    "summarize_diagnostics",
    "diagnostics_dir_for_output",
    "generate_summary_csv",
    "generate_html_report",
    "generate_names_csv",
    "generate_review_clusters_csv",
    "compute_cluster_review_rows",
    "parse_review_confidence",
    "normalize_review_action",
    "load_review_decisions",
    "resolve_review_decision",
    "write_review_decisions_report",
    "ensure_review_decisions_for_rows",
    "write_names_csv_from_decisions",
    "print_review_cluster_help",
    "ask_review_action",
    "apply_names",
    "review_clusters_console",
]
