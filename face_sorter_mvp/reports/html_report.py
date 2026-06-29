# -*- coding: utf-8 -*-
"""Summary/HTML report implementation extracted during v44 / Этап 003."""
from __future__ import annotations

from typing import Any


def _legacy_core() -> Any:
    try:
        from .. import face_sorter_mvp as legacy
    except ImportError:
        import face_sorter_mvp as legacy  # type: ignore
    return legacy


def _ensure_legacy_globals() -> Any:
    """Bind legacy helper functions/constants lazily without overriding local implementations."""
    legacy = _legacy_core()
    for name, value in legacy.__dict__.items():
        if name.startswith("__"):
            continue
        globals().setdefault(name, value)
    return legacy

def generate_summary_csv(args: argparse.Namespace, conn: sqlite3.Connection) -> Path:
    """Write a compact run summary for reports and bug reports."""
    _ensure_legacy_globals()
    output_dir = Path(args.output).resolve()
    report_dir = output_dir / "reports"
    ensure_dir(report_dir)
    path = report_dir / "summary.csv"
    rows = conn.execute(
        """
        SELECT cluster_key, COUNT(*) AS faces, COUNT(DISTINCT image_id) AS files, AVG(det_score) AS avg_det
        FROM faces
        WHERE cluster_key IS NOT NULL
        GROUP BY cluster_key
        ORDER BY cluster_key
        """
    ).fetchall()
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["cluster_key", "faces", "files", "avg_det_score"])
        for row in rows:
            writer.writerow([row[0], row[1], row[2], f"{float(row[3] or 0):.4f}"])
    return path


def generate_html_report(args: argparse.Namespace, conn: sqlite3.Connection) -> Path:
    """Generate the HTML cluster preview report."""
    _ensure_legacy_globals()
    output_dir = Path(args.output).resolve()
    report_dir = output_dir / "reports"
    ensure_dir(report_dir)
    path = report_dir / "clusters.html"
    limit = int(args.report_faces_per_cluster)
    rows = conn.execute(
        """
        SELECT cluster_key, COUNT(*) AS faces, COUNT(DISTINCT image_id) AS files, AVG(det_score) AS avg_det
        FROM faces
        WHERE cluster_key IS NOT NULL
        GROUP BY cluster_key
        ORDER BY cluster_key
        """
    ).fetchall()

    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        "<title>Face clusters</title>",
        "<style>body{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#111;color:#eee;} .cluster{margin:0 0 32px;padding:16px;background:#1b1b1b;border-radius:12px;} .grid{display:flex;flex-wrap:wrap;gap:8px;} img{width:96px;height:96px;object-fit:cover;border-radius:8px;border:1px solid #333;} .muted{color:#aaa}</style>",
        "</head><body>",
        f"<h1>Face clusters</h1><p class='muted'>Generated: {html.escape(now_iso())}</p>",
        "<p>Проверьте кластеры в names.csv: можно задать name, action=keep/merge/review/ignore и merge_into, затем запустить --mode apply-names.</p>",
    ]
    for key, faces_count, files_count, avg_det in rows:
        parts.append("<div class='cluster'>")
        parts.append(f"<h2>{html.escape(str(key))}</h2>")
        parts.append(f"<p class='muted'>faces={faces_count}; files={files_count}; avg_det={float(avg_det or 0):.4f}</p>")
        crops = conn.execute(
            "SELECT crop_relpath FROM faces WHERE cluster_key=? AND crop_relpath IS NOT NULL ORDER BY det_score DESC LIMIT ?",
            (key, limit),
        ).fetchall()
        parts.append("<div class='grid'>")
        for (rel,) in crops:
            rel_url = Path(rel).as_posix()
            parts.append(f"<img src='../{html.escape(rel_url)}' loading='lazy'>")
        parts.append("</div></div>")
    parts.append("</body></html>")
    path.write_text("\n".join(parts), encoding="utf-8")
    print(lang_text("HTML-отчёт:", "HTML report:"), path)
    return path


def generate_names_csv(*args: Any, **kwargs: Any) -> Any:
    from .review_clusters import generate_names_csv as _impl
    return _impl(*args, **kwargs)


__all__ = ["generate_summary_csv", "generate_html_report", "generate_names_csv"]
