# -*- coding: utf-8 -*-
"""Import-safe report/review helpers for the optional PySide6 UI.

v69.6 / Этап 055 keeps this lightweight layer so the GUI can inspect generated
reports, display review-cluster rows and save ``names.csv`` decisions without
running ML, changing report formats, or reusing the interactive console wizard.
"""
from __future__ import annotations

import csv
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .contracts import REVIEW_ACTIONS
from .project_state import default_project_db_path

REVIEW_UI_SCHEMA_VERSION = 1
REVIEW_UI_ACTIONS: Tuple[str, ...] = ("keep", "merge", "review", "ignore")


@dataclass(frozen=True)
class ReviewUiReportFile:
    """One report/review file exposed to the UI."""

    key: str
    path: Path
    exists: bool
    size_bytes: Optional[int] = None
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["path"] = str(self.path)
        return data


@dataclass(frozen=True)
class ReviewUiProblemRow:
    """One read-only row from reports/problem_files.csv interpreted for the UI.

    This is an in-memory/UI interpretation only. It deliberately does not add,
    remove or rename columns in the generated ``problem_files.csv`` report.
    """

    index: int
    category: str
    stage: str
    path: Path
    name: str = ""
    suffix: str = ""
    error: str = ""
    time: str = ""
    size_bytes: Optional[int] = None
    raw: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["path"] = str(self.path)
        data["raw"] = dict(self.raw)
        return data


@dataclass(frozen=True)
class ReviewUiProblemSummary:
    """Read-only summary for reports/problem_files.csv shown in Reports/review."""

    path: Path
    exists: bool
    total_rows: int = 0
    category_counts: Dict[str, int] = field(default_factory=dict)
    stage_counts: Dict[str, int] = field(default_factory=dict)
    rows: Tuple[ReviewUiProblemRow, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["path"] = str(self.path)
        data["rows"] = [row.to_dict() for row in self.rows]
        return data


@dataclass(frozen=True)
class ReviewUiClusterRow:
    """One editable cluster decision row for the UI review table."""

    cluster_key: str
    faces: int = 0
    files: int = 0
    confidence: Optional[float] = None
    avg_det_score: Optional[float] = None
    min_det_score: Optional[float] = None
    max_det_score: Optional[float] = None
    name: str = ""
    action: str = "keep"
    merge_into: str = ""
    notes: str = ""
    thumbnails: Tuple[Path, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["thumbnails"] = [str(path) for path in self.thumbnails]
        return data


@dataclass(frozen=True)
class ReviewUiSnapshot:
    """Serializable snapshot of report/review files in one result folder."""

    output_dir: Path
    reports_dir: Path
    names_path: Path
    review_clusters_path: Path
    review_decisions_path: Path
    clusters_html_path: Path
    assignments_path: Path
    summary_path: Path
    problem_files_path: Path
    duplicates_path: Path
    diagnostics_dir: Path
    db_path: Path
    rows: Tuple[ReviewUiClusterRow, ...] = ()
    report_files: Tuple[ReviewUiReportFile, ...] = ()
    problem_summary: ReviewUiProblemSummary = field(default_factory=lambda: ReviewUiProblemSummary(path=Path("problem_files.csv"), exists=False))
    warnings: Tuple[str, ...] = ()
    can_apply_names: bool = False

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        for key in (
            "output_dir",
            "reports_dir",
            "names_path",
            "review_clusters_path",
            "review_decisions_path",
            "clusters_html_path",
            "assignments_path",
            "summary_path",
            "problem_files_path",
            "duplicates_path",
            "diagnostics_dir",
            "db_path",
        ):
            data[key] = str(data[key])
        data["rows"] = [row.to_dict() for row in self.rows]
        data["report_files"] = [item.to_dict() for item in self.report_files]
        data["problem_summary"] = self.problem_summary.to_dict()
        return data


@dataclass(frozen=True)
class ReviewUiSaveResult:
    """Result of saving edited review decisions from the UI."""

    output_dir: Path
    names_path: Path
    review_decisions_path: Path
    rows_saved: int
    warnings: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["output_dir"] = str(self.output_dir)
        data["names_path"] = str(self.names_path)
        data["review_decisions_path"] = str(self.review_decisions_path)
        return data


def _cluster_sort_key(value: str) -> Tuple[str, int, str]:
    text = str(value or "")
    match = re.search(r"(.*?)(\d+)$", text)
    if match:
        return (match.group(1), int(match.group(2)), text)
    return (text, -1, text)


def _parse_float(value: Any) -> Optional[float]:
    text = str(value or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_int(value: Any) -> int:
    try:
        return int(float(str(value or "0").strip().replace(",", ".")))
    except ValueError:
        return 0


def _normalize_action(value: Any) -> str:
    action = str(value or "keep").strip().lower()
    aliases = {
        "skip": "ignore",
        "ignored": "ignore",
        "delete": "ignore",
        "remove": "ignore",
        "manual": "review",
        "check": "review",
        "merge_into": "merge",
    }
    action = aliases.get(action, action)
    return action if action in REVIEW_ACTIONS else "review"


def _read_csv_dicts(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _parse_optional_int(value: Any) -> Optional[int]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(float(text.replace(",", ".")))
    except ValueError:
        return None


def _problem_category_from_row(row: Dict[str, str]) -> str:
    """Classify a problem_files.csv row for UI grouping only.

    The generated CSV historically uses the ``stage`` column for both stage-like
    and reason-like values. Keep the classifier broad and additive so older
    reports still receive useful labels without requiring a schema migration.
    """
    stage = str(row.get("stage") or row.get("reason") or row.get("status") or "").strip().lower()
    error = str(row.get("error") or row.get("message") or "").strip().lower()
    text = f"{stage} {error}"

    if "timeout" in text:
        return "timeout"
    if any(token in text for token in (
        "unsupported_extension", "unsupported format", "unsupported extension",
        "extension_mismatch", "not_an_image", "not an image", "header is not recognized",
    )):
        return "unsupported_format"
    if any(token in text for token in (
        "decode", "cannot identify image", "unidentifiedimageerror", "truncated",
        "corrupt", "corrupted", "bad image", "invalid image", "image file is truncated",
    )):
        return "decode_error"
    if any(token in text for token in (
        "missing_source", "stat_error", "read_error", "locked_or_permission_denied",
        "permission", "access denied", "no such file", "file does not exist",
        "source_path_too_long", "open", "i/o", "errno",
    )):
        return "read_open_error"
    if any(token in text for token in (
        "scan_worker", "copy_worker", "worker", "brokenprocesspool", "processpool",
        "pool", "internal", "traceback",
    )):
        return "internal_worker_error"
    return "other"


def load_problem_files_summary(problem_files_path: str | Path, *, max_rows: int = 500) -> ReviewUiProblemSummary:
    """Load and classify reports/problem_files.csv for UI display only.

    This helper is intentionally read-only. It never creates problem_files.csv and
    never changes its columns; it only groups existing rows into stable categories
    so the GUI can explain them to the user.
    """
    path = Path(problem_files_path)
    try:
        exists = path.exists()
    except OSError:
        exists = False
    if not exists:
        return ReviewUiProblemSummary(path=path, exists=False)

    rows: List[ReviewUiProblemRow] = []
    category_counts: Dict[str, int] = {}
    stage_counts: Dict[str, int] = {}
    csv_rows = _read_csv_dicts(path)
    for index, csv_row in enumerate(csv_rows, start=1):
        normalized = {str(k): str(v or "") for k, v in dict(csv_row).items()}
        stage = normalized.get("stage", "")
        category = _problem_category_from_row(normalized)
        category_counts[category] = category_counts.get(category, 0) + 1
        stage_counts[stage or "<empty>"] = stage_counts.get(stage or "<empty>", 0) + 1
        if len(rows) >= max_rows:
            continue
        row_path_text = normalized.get("path", "")
        row_path = Path(row_path_text) if row_path_text else Path("")
        rows.append(ReviewUiProblemRow(
            index=index,
            category=category,
            stage=stage,
            path=row_path,
            name=normalized.get("name", "") or row_path.name,
            suffix=normalized.get("suffix", "") or row_path.suffix.lower(),
            error=normalized.get("error", ""),
            time=normalized.get("time", ""),
            size_bytes=_parse_optional_int(normalized.get("size_bytes")),
            raw=normalized,
        ))

    return ReviewUiProblemSummary(
        path=path,
        exists=True,
        total_rows=len(csv_rows),
        category_counts=category_counts,
        stage_counts=stage_counts,
        rows=tuple(rows),
    )


def _default_paths(output_dir: Path) -> Dict[str, Path]:
    output_dir = Path(output_dir).expanduser().resolve()
    reports_dir = output_dir / "reports"
    return {
        "output_dir": output_dir,
        "reports_dir": reports_dir,
        "names_path": output_dir / "names.csv",
        "review_clusters_path": reports_dir / "review_clusters.csv",
        "review_decisions_path": reports_dir / "review_decisions.csv",
        "clusters_html_path": reports_dir / "clusters.html",
        "assignments_path": reports_dir / "assignments.csv",
        "summary_path": reports_dir / "summary.csv",
        "problem_files_path": reports_dir / "problem_files.csv",
        "duplicates_path": reports_dir / "duplicates.csv",
        "diagnostics_dir": reports_dir / "diagnostics",
        "db_path": default_project_db_path(output_dir),
    }


def _report_file(key: str, path: Path, description: str) -> ReviewUiReportFile:
    try:
        exists = path.exists()
        size = path.stat().st_size if exists else None
    except OSError:
        exists = False
        size = None
    return ReviewUiReportFile(key=key, path=path, exists=exists, size_bytes=size, description=description)


def _cluster_rows_from_review_csv(path: Path) -> Dict[str, Dict[str, Any]]:
    rows: Dict[str, Dict[str, Any]] = {}
    for row in _read_csv_dicts(path):
        key = str(row.get("cluster_key") or row.get("cluster") or "").strip()
        if not key:
            continue
        rows[key] = {
            "cluster_key": key,
            "faces": _parse_int(row.get("faces")),
            "files": _parse_int(row.get("files")),
            "confidence": _parse_float(row.get("confidence")),
            "avg_det_score": _parse_float(row.get("avg_det_score")),
            "min_det_score": _parse_float(row.get("min_det_score")),
            "max_det_score": _parse_float(row.get("max_det_score")),
        }
    return rows


def _cluster_rows_from_db(db_path: Path) -> Dict[str, Dict[str, Any]]:
    if not db_path.exists():
        return {}
    rows: Dict[str, Dict[str, Any]] = {}
    with sqlite3.connect(str(db_path)) as conn:
        for key, faces, files, avg_det, min_det, max_det in conn.execute(
            """
            SELECT cluster_key, COUNT(*) AS faces, COUNT(DISTINCT image_id) AS files,
                   AVG(det_score) AS avg_det, MIN(det_score) AS min_det, MAX(det_score) AS max_det
            FROM faces
            WHERE cluster_key IS NOT NULL
            GROUP BY cluster_key
            ORDER BY cluster_key
            """
        ):
            avg = float(avg_det or 0.0)
            rows[str(key)] = {
                "cluster_key": str(key),
                "faces": int(faces or 0),
                "files": int(files or 0),
                "confidence": max(0.0, min(1.0, avg)),
                "avg_det_score": avg,
                "min_det_score": float(min_det or 0.0),
                "max_det_score": float(max_det or 0.0),
            }
    return rows


def _thumbnail_map_from_db(output_dir: Path, db_path: Path, *, max_per_cluster: int) -> Dict[str, Tuple[Path, ...]]:
    if max_per_cluster <= 0 or not db_path.exists():
        return {}
    result: Dict[str, List[Path]] = {}
    with sqlite3.connect(str(db_path)) as conn:
        for key, rel in conn.execute(
            """
            SELECT cluster_key, crop_relpath
            FROM faces
            WHERE cluster_key IS NOT NULL AND crop_relpath IS NOT NULL
            ORDER BY cluster_key, det_score DESC
            """
        ):
            cluster_key = str(key)
            bucket = result.setdefault(cluster_key, [])
            if len(bucket) >= max_per_cluster:
                continue
            path = output_dir / str(rel)
            if path.exists():
                bucket.append(path)
    return {key: tuple(paths) for key, paths in result.items()}


def _decisions_from_names(names_path: Path) -> Dict[str, Dict[str, Any]]:
    decisions: Dict[str, Dict[str, Any]] = {}
    for row in _read_csv_dicts(names_path):
        key = str(row.get("cluster_key") or row.get("cluster") or "").strip()
        if not key:
            continue
        decisions[key] = {
            "name": str(row.get("name") or "").strip(),
            "action": _normalize_action(row.get("action") or "keep"),
            "merge_into": str(row.get("merge_into") or row.get("merge") or "").strip(),
            "confidence": _parse_float(row.get("confidence")),
            "notes": str(row.get("notes") or "").strip(),
        }
    return decisions


def load_review_ui_snapshot(output_dir: str | Path, *, max_thumbnails_per_cluster: int = 12) -> ReviewUiSnapshot:
    """Load report/review files for the UI without running pipeline stages.

    The function reads existing ``reports/review_clusters.csv`` and ``names.csv``.
    If the review snapshot CSV is missing but the SQLite DB exists, it derives the
    same cluster statistics directly from the DB. It never writes user files.
    """
    paths = _default_paths(Path(output_dir))
    output = paths["output_dir"]
    reports = paths["reports_dir"]
    warnings: List[str] = []

    base_rows = _cluster_rows_from_review_csv(paths["review_clusters_path"])
    if not base_rows:
        try:
            base_rows = _cluster_rows_from_db(paths["db_path"])
            if base_rows and not paths["review_clusters_path"].exists():
                warnings.append("reports/review_clusters.csv is missing; cluster stats were read from SQLite for display only.")
        except Exception as exc:
            warnings.append(f"Could not read cluster rows from SQLite: {type(exc).__name__}: {exc}")
            base_rows = {}

    decisions = _decisions_from_names(paths["names_path"])
    thumb_map: Dict[str, Tuple[Path, ...]] = {}
    try:
        thumb_map = _thumbnail_map_from_db(output, paths["db_path"], max_per_cluster=max_thumbnails_per_cluster)
    except Exception as exc:
        warnings.append(f"Could not read preview thumbnails from SQLite: {type(exc).__name__}: {exc}")

    keys = sorted(set(base_rows) | set(decisions), key=_cluster_sort_key)
    rows: List[ReviewUiClusterRow] = []
    for key in keys:
        stats = base_rows.get(key, {"cluster_key": key})
        decision = decisions.get(key, {})
        confidence = decision.get("confidence")
        if confidence is None:
            confidence = stats.get("confidence")
        rows.append(ReviewUiClusterRow(
            cluster_key=key,
            faces=_parse_int(stats.get("faces")),
            files=_parse_int(stats.get("files")),
            confidence=confidence,
            avg_det_score=_parse_float(stats.get("avg_det_score")),
            min_det_score=_parse_float(stats.get("min_det_score")),
            max_det_score=_parse_float(stats.get("max_det_score")),
            name=str(decision.get("name") or ""),
            action=_normalize_action(decision.get("action") or "keep"),
            merge_into=str(decision.get("merge_into") or ""),
            notes=str(decision.get("notes") or (f"faces={stats.get('faces', '')}; files={stats.get('files', '')}" if stats else "")),
            thumbnails=thumb_map.get(key, ()),
        ))

    problem_summary = load_problem_files_summary(paths["problem_files_path"])

    report_files = (
        _report_file("summary_csv", paths["summary_path"], "Cluster summary CSV"),
        _report_file("assignments_csv", paths["assignments_path"], "Photo assignment CSV used by apply-names"),
        _report_file("clusters_html", paths["clusters_html_path"], "HTML face-cluster preview"),
        _report_file("duplicates_csv", paths["duplicates_path"], "Exact duplicate report"),
        _report_file("review_clusters_csv", paths["review_clusters_path"], "Machine-friendly cluster review snapshot"),
        _report_file("problem_files_csv", paths["problem_files_path"], "Problem files report with files skipped because of read/decode/timeout/worker issues"),
        _report_file("names_csv", paths["names_path"], "Editable review decisions; optional until Review clusters decisions are saved"),
        _report_file("review_decisions_csv", paths["review_decisions_path"], "Resolved review decision report; optional after a normal run and created after saving/applying Review clusters decisions"),
        _report_file("diagnostics_dir", paths["diagnostics_dir"], "Diagnostics folder"),
        _report_file("runtime_diagnostics_json", paths["diagnostics_dir"] / "runtime_diagnostics.json", "Runtime diagnostics included in bug reports"),
    )

    if not output.exists():
        warnings.append(f"Output folder does not exist: {output}")
    if not paths["names_path"].exists():
        warnings.append("names.csv does not exist yet; saving review decisions will create it with the existing v29/v30 columns.")
    if not paths["assignments_path"].exists():
        warnings.append("reports/assignments.csv is missing; apply-names needs it and will ask you to run mode=all or mode=copy first.")

    return ReviewUiSnapshot(
        output_dir=output,
        reports_dir=reports,
        names_path=paths["names_path"],
        review_clusters_path=paths["review_clusters_path"],
        review_decisions_path=paths["review_decisions_path"],
        clusters_html_path=paths["clusters_html_path"],
        assignments_path=paths["assignments_path"],
        summary_path=paths["summary_path"],
        problem_files_path=paths["problem_files_path"],
        duplicates_path=paths["duplicates_path"],
        diagnostics_dir=paths["diagnostics_dir"],
        db_path=paths["db_path"],
        rows=tuple(rows),
        report_files=report_files,
        problem_summary=problem_summary,
        warnings=tuple(warnings),
        can_apply_names=paths["names_path"].exists() and paths["assignments_path"].exists(),
    )


def _row_from_any(row: ReviewUiClusterRow | Dict[str, Any]) -> ReviewUiClusterRow:
    if isinstance(row, ReviewUiClusterRow):
        return row
    return ReviewUiClusterRow(
        cluster_key=str(row.get("cluster_key") or "").strip(),
        faces=_parse_int(row.get("faces")),
        files=_parse_int(row.get("files")),
        confidence=_parse_float(row.get("confidence")),
        avg_det_score=_parse_float(row.get("avg_det_score")),
        min_det_score=_parse_float(row.get("min_det_score")),
        max_det_score=_parse_float(row.get("max_det_score")),
        name=str(row.get("name") or "").strip(),
        action=_normalize_action(row.get("action") or "keep"),
        merge_into=str(row.get("merge_into") or "").strip(),
        notes=str(row.get("notes") or "").strip(),
        thumbnails=tuple(Path(path) for path in row.get("thumbnails", ()) if str(path)),
    )


def _resolve_decision(key: str, decisions: Dict[str, ReviewUiClusterRow]) -> Tuple[str, ReviewUiClusterRow, List[str], str]:
    current = key
    chain: List[str] = []
    seen = set()
    while True:
        if current in seen:
            return key, decisions[key], chain, "merge_cycle"
        seen.add(current)
        chain.append(current)
        decision = decisions.get(current)
        if decision is None:
            return current, decisions[key], chain, "merge_target_missing"
        action = _normalize_action(decision.action)
        if action == "merge":
            target = str(decision.merge_into or "").strip()
            if not target:
                return current, decision, chain, "merge_without_target"
            if target not in decisions:
                return target, decision, chain + [target], "merge_target_missing"
            current = target
            continue
        return current, decision, chain, ""


def save_review_ui_decisions(output_dir: str | Path, rows: Sequence[ReviewUiClusterRow | Dict[str, Any]]) -> ReviewUiSaveResult:
    """Save edited UI review decisions to existing ``names.csv`` format.

    This writes only ``names.csv`` and ``reports/review_decisions.csv``. It does
    not copy photos and does not alter ``project.json``; final folders are still
    produced by the existing backend ``apply-names`` stage.
    """
    paths = _default_paths(Path(output_dir))
    paths["reports_dir"].mkdir(parents=True, exist_ok=True)
    paths["output_dir"].mkdir(parents=True, exist_ok=True)

    normalized = [_row_from_any(row) for row in rows]
    normalized = [row for row in normalized if row.cluster_key]
    normalized.sort(key=lambda row: _cluster_sort_key(row.cluster_key))
    decisions = {row.cluster_key: row for row in normalized}
    warnings: List[str] = []

    with paths["names_path"].open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["cluster_key", "name", "action", "merge_into", "confidence", "notes"])
        for row in normalized:
            action = _normalize_action(row.action)
            if action == "merge" and not row.merge_into:
                warnings.append(f"{row.cluster_key}: action=merge without merge_into; apply-names will send it to review.")
            writer.writerow([
                row.cluster_key,
                row.name,
                action,
                row.merge_into,
                "" if row.confidence is None else f"{float(row.confidence):.4f}",
                row.notes,
            ])

    with paths["review_decisions_path"].open("w", encoding="utf-8-sig", newline="") as f:
        fields = ["cluster_key", "effective_cluster_key", "name", "action", "merge_into", "confidence", "notes", "merge_chain", "error"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in normalized:
            effective_key, effective_decision, chain, error = _resolve_decision(row.cluster_key, decisions)
            if error:
                warnings.append(f"{row.cluster_key}: {error}")
            writer.writerow({
                "cluster_key": row.cluster_key,
                "effective_cluster_key": effective_key,
                "name": effective_decision.name,
                "action": _normalize_action(effective_decision.action),
                "merge_into": row.merge_into,
                "confidence": "" if row.confidence is None else f"{float(row.confidence):.4f}",
                "notes": row.notes,
                "merge_chain": ";".join(chain),
                "error": error,
            })

    return ReviewUiSaveResult(
        output_dir=paths["output_dir"],
        names_path=paths["names_path"],
        review_decisions_path=paths["review_decisions_path"],
        rows_saved=len(normalized),
        warnings=tuple(warnings),
    )


__all__ = [
    "REVIEW_UI_SCHEMA_VERSION",
    "REVIEW_UI_ACTIONS",
    "ReviewUiReportFile",
    "ReviewUiProblemRow",
    "ReviewUiProblemSummary",
    "ReviewUiClusterRow",
    "ReviewUiSnapshot",
    "ReviewUiSaveResult",
    "load_problem_files_summary",
    "load_review_ui_snapshot",
    "save_review_ui_decisions",
]
