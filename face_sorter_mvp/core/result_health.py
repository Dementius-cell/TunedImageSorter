# -*- coding: utf-8 -*-
"""Import-safe result/output health-check helpers.

v69.6 / Этап 055 adds a diagnostics-only check for an existing result/output
folder.  It does not scan photos, does not run ML, does not copy files and does
not change report CSV schemas.  The optional JSON/TXT outputs are additional
files under reports/ for support purposes only.  Frozen CLI console output is
English/ASCII by default to avoid Windows code-page mojibake; UTF-8 report files
remain unchanged.

 v69.6 / Этап 055 corrects result-health paths for root-level names.csv
 and writes self-referential written_files into the generated JSON/TXT.
"""
from __future__ import annotations

import datetime as dt
import json
import zipfile
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .constants import SCRIPT_VERSION

RESULT_HEALTH_SCHEMA_VERSION = 1
RESULT_HEALTH_STAGE = "Этап 055"


@dataclass(frozen=True)
class ResultHealthItem:
    """One checked file/folder in a result/output project."""

    key: str
    path: str
    exists: bool
    kind: str = "file"  # file | dir | optional-file | optional-dir
    severity: str = "info"  # info | warning | error
    message_ru: str = ""
    message_en: str = ""
    size_bytes: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResultHealthSummary:
    """Serializable result/output health-check summary."""

    ok: bool
    version: str
    refactor_stage: str
    schema_version: int
    output_dir: str
    created_at: str
    files_checked: int
    errors: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    infos: Tuple[str, ...] = ()
    items: Tuple[ResultHealthItem, ...] = field(default_factory=tuple)
    written_files: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["items"] = [item.to_dict() for item in self.items]
        return data


def _size(path: Path) -> Optional[int]:
    try:
        if path.is_file():
            return int(path.stat().st_size)
    except Exception:
        pass
    return None


def _rel(base: Path, path: Path) -> str:
    try:
        return str(path.relative_to(base))
    except Exception:
        return str(path)


def _item(base: Path, rel_path: str, *, kind: str, required: bool, message_ru: str, message_en: str) -> ResultHealthItem:
    path = base / rel_path
    exists = path.is_dir() if kind.endswith("dir") else path.is_file()
    severity = "info" if exists else ("error" if required else "warning")
    if not exists:
        label_ru = "папка" if kind.endswith("dir") else "файл"
        label_en = "folder" if kind.endswith("dir") else "file"
        required_word_ru = "Обязательная" if kind.endswith("dir") else "Обязательный"
        optional_word_ru = "Необязательная" if kind.endswith("dir") else "Необязательный"
        if required:
            message_ru = f"{required_word_ru} {label_ru} отсутствует: {rel_path}."
            message_en = f"Required {label_en} is missing: {rel_path}."
        else:
            message_ru = f"{optional_word_ru} {label_ru} отсутствует: {rel_path}; это может быть нормально для такого запуска."
            message_en = f"Optional {label_en} is missing: {rel_path}; this can be normal for this run."
            kind = "optional-dir" if kind.endswith("dir") else "optional-file"
    return ResultHealthItem(
        key=rel_path.replace("\\", "/"),
        path=_rel(base, path),
        exists=exists,
        kind=kind,
        severity=severity,
        message_ru=message_ru,
        message_en=message_en,
        size_bytes=_size(path),
    )




def _item_candidates(
    base: Path,
    primary_rel_path: str,
    candidate_rel_paths: Iterable[str],
    *,
    kind: str,
    required: bool,
    message_ru: str,
    message_en: str,
) -> ResultHealthItem:
    """Check an item that may have legacy/current locations.

    The first candidate that exists wins.  If none exists, the primary path is
    reported.  This keeps the item count stable while avoiding misleading
    warnings such as reporting ``reports/names.csv`` missing when the canonical
    ``names.csv`` exists in the output root.
    """
    candidates = list(candidate_rel_paths)
    for rel_path in candidates:
        path = base / rel_path
        exists = path.is_dir() if kind.endswith("dir") else path.is_file()
        if exists:
            return ResultHealthItem(
                key=primary_rel_path.replace("\\", "/"),
                path=_rel(base, path),
                exists=True,
                kind=kind,
                severity="info",
                message_ru=message_ru,
                message_en=message_en,
                size_bytes=_size(path),
            )
    return _item(base, primary_rel_path, kind=kind, required=required, message_ru=message_ru, message_en=message_en)

def _latest_zip(folder: Path) -> Optional[Path]:
    try:
        zips = [p for p in folder.glob("*.zip") if p.is_file()]
        if not zips:
            return None
        return max(zips, key=lambda p: p.stat().st_mtime)
    except Exception:
        return None


def _zip_ok(path: Path) -> Tuple[bool, str]:
    try:
        with zipfile.ZipFile(path) as zf:
            bad = zf.testzip()
        if bad:
            return False, f"bad member: {bad}"
        return True, "zip ok"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def build_result_health_summary(output_dir: str | Path, *, write_reports: bool = False) -> ResultHealthSummary:
    """Inspect an existing output/result folder and optionally write a summary.

    The function is intentionally shallow.  It checks file presence and ZIP
    integrity only; it does not parse embeddings, does not open user images and
    does not change existing CSV/report formats.
    """
    output = Path(output_dir).expanduser().resolve()
    created_at = dt.datetime.now().isoformat(timespec="seconds")
    items: List[ResultHealthItem] = []
    written: List[str] = []

    if not output.exists() or not output.is_dir():
        msg_ru = f"Не найдена output/result папка: {output}"
        msg_en = f"Output/result folder was not found: {output}"
        return ResultHealthSummary(
            ok=False,
            version=SCRIPT_VERSION,
            refactor_stage=RESULT_HEALTH_STAGE,
            schema_version=RESULT_HEALTH_SCHEMA_VERSION,
            output_dir=str(output),
            created_at=created_at,
            files_checked=0,
            errors=(msg_ru,),
            items=(ResultHealthItem("output", str(output), False, "dir", "error", msg_ru, msg_en),),
        )

    required = [
        ("project.json", "file", "Главный project.json найден.", "Main project.json is present."),
        ("reports", "dir", "Папка reports найдена.", "reports folder is present."),
        ("reports/summary.csv", "file", "summary.csv найден.", "summary.csv is present."),
        ("reports/assignments.csv", "file", "assignments.csv найден.", "assignments.csv is present."),
        ("reports/review_clusters.csv", "file", "review_clusters.csv найден.", "review_clusters.csv is present."),
    ]
    optional = [
        ("names.csv", ("names.csv", "reports/names.csv"), "file", "names.csv найден или может быть создан через Review clusters.", "names.csv is present or can be created by Review clusters."),
        ("reports/review_decisions.csv", ("reports/review_decisions.csv",), "file", "review_decisions.csv найден или появится после сохранения решений review.", "review_decisions.csv is present or appears after saving review decisions."),
        ("reports/problem_files.csv", ("reports/problem_files.csv",), "file", "problem_files.csv найден; отсутствие нормально, если проблемных файлов не было.", "problem_files.csv is present; absence is normal if no problematic files were found."),
        ("reports/diagnostics", ("reports/diagnostics",), "dir", "diagnostics найдены; отсутствие нормально для старых/простых запусков.", "diagnostics are present; absence can be normal for older/simple runs."),
        ("database/faces.sqlite", ("database/faces.sqlite",), "file", "SQLite database найдена.", "SQLite database is present."),
        ("people", ("people",), "dir", "people найдена после обычной сортировки.", "people folder is present after regular sorting."),
        ("review", ("review",), "dir", "review найдена после обычной сортировки.", "review folder is present after regular sorting."),
        ("final", ("final",), "dir", "final найдена после apply-names.", "final folder is present after apply-names."),
        ("final_review", ("final_review",), "dir", "final_review найдена после apply-names.", "final_review folder is present after apply-names."),
        ("bug_reports", ("bug_reports",), "dir", "bug_reports найдена после создания support-bundle.", "bug_reports folder is present after creating a support-bundle."),
    ]

    for rel_path, kind, ru, en in required:
        items.append(_item(output, rel_path, kind=kind, required=True, message_ru=ru, message_en=en))
    for rel_path, candidates, kind, ru, en in optional:
        items.append(_item_candidates(output, rel_path, candidates, kind=kind, required=False, message_ru=ru, message_en=en))

    bug_dir = output / "bug_reports"
    latest = _latest_zip(bug_dir) if bug_dir.exists() else None
    if latest is not None:
        ok, message = _zip_ok(latest)
        items.append(ResultHealthItem(
            key="bug_reports/latest_zip",
            path=_rel(output, latest),
            exists=True,
            kind="file",
            severity="info" if ok else "error",
            message_ru=f"Последний support-bundle ZIP: {message}",
            message_en=f"Latest support-bundle ZIP: {message}",
            size_bytes=_size(latest),
        ))

    errors = tuple(item.message_ru for item in items if item.severity == "error")
    warnings = tuple(item.message_ru for item in items if item.severity == "warning")
    infos = tuple(item.message_ru for item in items if item.severity == "info")

    summary = ResultHealthSummary(
        ok=not errors,
        version=SCRIPT_VERSION,
        refactor_stage=RESULT_HEALTH_STAGE,
        schema_version=RESULT_HEALTH_SCHEMA_VERSION,
        output_dir=str(output),
        created_at=created_at,
        files_checked=len(items),
        errors=errors,
        warnings=warnings,
        infos=infos,
        items=tuple(items),
        written_files=(),
    )

    if write_reports:
        reports = output / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        json_path = reports / "result_health_check.json"
        txt_path = reports / "result_health_check.txt"
        written = [str(json_path), str(txt_path)]
        summary = replace(summary, written_files=tuple(written))
        json_path.write_text(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        txt_path.write_text(format_result_health_text(summary, language="ru"), encoding="utf-8")

    return summary


def _ascii_safe_line(line: str) -> str:
    """Make console-friendly English diagnostics immune to Windows code pages."""
    return line.encode("ascii", "backslashreplace").decode("ascii")


def _stage_en(stage: str) -> str:
    text = str(stage)
    if text.startswith("Этап"):
        return "Stage" + text[len("Этап"):]
    return text


def format_result_health_text(summary: ResultHealthSummary, *, language: str = "ru") -> str:
    """Render a compact human-readable result health summary."""
    is_en = str(language).lower().startswith("en")
    lines: List[str] = []
    if is_en:
        lines.append(f"Tuned Image Sorter result health-check - {summary.version} / {_stage_en(summary.refactor_stage)}")
        lines.append(f"Output: {summary.output_dir}")
        lines.append(f"Status: {'OK' if summary.ok else 'PROBLEM'}")
        lines.append(f"Checked: {summary.files_checked}")
        if summary.warnings:
            lines.append("Note: WARN for optional files/folders is not a failure. review_decisions.csv, problem_files.csv, final and final_review can be absent in normal workflows.")
        lines.append("")
        for item in summary.items:
            mark = "OK" if item.exists and item.severity != "error" else ("WARN" if item.severity == "warning" else "ERROR")
            lines.append(f"[{mark}] {item.path} - {item.message_en}")
        if summary.written_files:
            lines.append("")
            lines.append("Written files:")
            lines.extend(f"  {p}" for p in summary.written_files)
    else:
        lines.append(f"Tuned Image Sorter health-check результата - {summary.version} / {summary.refactor_stage}")
        lines.append(f"Output: {summary.output_dir}")
        lines.append(f"Статус: {'OK' if summary.ok else 'ПРОБЛЕМА'}")
        lines.append(f"Проверено: {summary.files_checked}")
        if summary.warnings:
            lines.append("Примечание: WARN по необязательным файлам/папкам не означает ошибку. review_decisions.csv, problem_files.csv, final и final_review могут отсутствовать в нормальных workflow.")
        lines.append("")
        for item in summary.items:
            mark = "OK" if item.exists and item.severity != "error" else ("WARN" if item.severity == "warning" else "ERROR")
            lines.append(f"[{mark}] {item.path} - {item.message_ru}")
        if summary.written_files:
            lines.append("")
            lines.append("Созданы файлы:")
            lines.extend(f"  {p}" for p in summary.written_files)
    if is_en:
        lines = [_ascii_safe_line(line) for line in lines]
    return "\n".join(lines) + "\n"


__all__ = [
    "RESULT_HEALTH_SCHEMA_VERSION",
    "RESULT_HEALTH_STAGE",
    "ResultHealthItem",
    "ResultHealthSummary",
    "build_result_health_summary",
    "format_result_health_text",
]
