# -*- coding: utf-8 -*-
"""Review-clusters and names implementation extracted during v44 / Этап 003."""
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

def compute_cluster_review_rows(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Return per-cluster stats used by names.csv and future review UI."""
    _ensure_legacy_globals()
    rows = conn.execute(
        """
        SELECT
            cluster_key,
            COUNT(*) AS faces,
            COUNT(DISTINCT image_id) AS files,
            AVG(det_score) AS avg_det,
            MIN(det_score) AS min_det,
            MAX(det_score) AS max_det
        FROM faces
        WHERE cluster_key IS NOT NULL
        GROUP BY cluster_key
        ORDER BY cluster_key
        """
    ).fetchall()
    result: List[Dict[str, Any]] = []
    for key, faces_count, files_count, avg_det, min_det, max_det in rows:
        avg = float(avg_det or 0.0)
        # This is a review confidence hint, not identity certainty. It helps sort
        # clusters in UI and names.csv, but the user still confirms names/actions.
        confidence = max(0.0, min(1.0, avg))
        result.append({
            "cluster_key": str(key),
            "faces": int(faces_count or 0),
            "files": int(files_count or 0),
            "avg_det_score": avg,
            "min_det_score": float(min_det or 0.0),
            "max_det_score": float(max_det or 0.0),
            "confidence": confidence,
        })
    return result


def generate_names_csv(args: argparse.Namespace, conn: sqlite3.Connection) -> Path:
    """Create names.csv with review-model columns while preserving existing decisions."""
    _ensure_legacy_globals()
    output_dir = Path(args.output).resolve()
    path = output_dir / "names.csv"
    if path.exists() and not args.overwrite_names:
        print(lang_text("names.csv уже существует:", "names.csv already exists:"), path)
        return path

    rows = compute_cluster_review_rows(conn)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["cluster_key", "name", "action", "merge_into", "confidence", "notes"])
        for row in rows:
            writer.writerow([
                row["cluster_key"],
                "",
                "keep",
                "",
                f"{row['confidence']:.4f}",
                f"faces={row['faces']}; files={row['files']}; avg_det={row['avg_det_score']:.4f}",
            ])
    print(lang_text("Создан файл имён:", "Names file created:"), path)
    return path


def generate_review_clusters_csv(args: argparse.Namespace, conn: sqlite3.Connection) -> Path:
    """Write a machine-friendly review model snapshot for GUI/import tools."""
    _ensure_legacy_globals()
    output_dir = Path(args.output).resolve()
    report_dir = output_dir / "reports"
    ensure_dir(report_dir)
    path = report_dir / "review_clusters.csv"
    rows = compute_cluster_review_rows(conn)
    fields = ["cluster_key", "faces", "files", "confidence", "avg_det_score", "min_det_score", "max_det_score"]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "cluster_key": row["cluster_key"],
                "faces": row["faces"],
                "files": row["files"],
                "confidence": f"{row['confidence']:.4f}",
                "avg_det_score": f"{row['avg_det_score']:.4f}",
                "min_det_score": f"{row['min_det_score']:.4f}",
                "max_det_score": f"{row['max_det_score']:.4f}",
            })
    return path


def parse_review_confidence(value: str) -> Optional[float]:
    """Parse review confidence values from names/review CSV rows."""
    _ensure_legacy_globals()
    value = (value or "").strip().replace(",", ".")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def normalize_review_action(action: str) -> str:
    """Normalize keep/merge/review/ignore actions from names.csv."""
    _ensure_legacy_globals()
    action = (action or "keep").strip().lower()
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


def load_review_decisions(names_path: Path) -> Dict[str, ReviewDecision]:
    """Load names.csv in both legacy and v29 review-model formats."""
    _ensure_legacy_globals()
    decisions: Dict[str, ReviewDecision] = {}
    with names_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row.get("cluster_key") or row.get("cluster") or "").strip()
            if not key:
                continue
            action = normalize_review_action(row.get("action") or "keep")
            decisions[key] = ReviewDecision(
                cluster_key=key,
                name=(row.get("name") or "").strip(),
                action=action,
                merge_into=(row.get("merge_into") or row.get("merge") or "").strip(),
                confidence=parse_review_confidence(row.get("confidence") or ""),
                notes=(row.get("notes") or "").strip(),
            )
    return decisions


def resolve_review_decision(cluster_key: str, decisions: Dict[str, ReviewDecision]) -> Tuple[str, ReviewDecision, List[str], Optional[str]]:
    """Resolve merge chains and return (effective_key, decision, chain, error)."""
    _ensure_legacy_globals()
    current = cluster_key
    chain: List[str] = []
    seen = set()
    while True:
        if current in seen:
            fallback = ReviewDecision(cluster_key=cluster_key, action="review", notes="merge cycle detected")
            return cluster_key, fallback, chain, "merge_cycle"
        seen.add(current)
        chain.append(current)
        decision = decisions.get(current, ReviewDecision(cluster_key=current, action="review"))
        action = decision.normalized_action()
        if action == "merge":
            target = (decision.merge_into or "").strip()
            if not target:
                fallback = ReviewDecision(cluster_key=current, action="review", notes="merge without target")
                return current, fallback, chain, "merge_without_target"
            if target not in decisions:
                # Still allow merging into a raw cluster id, but it has no name/action.
                fallback = ReviewDecision(cluster_key=target, action="review", notes=f"merge target missing for {cluster_key}")
                return target, fallback, chain + [target], "merge_target_missing"
            current = target
            continue
        return current, decision, chain, None


def write_review_decisions_report(args: argparse.Namespace, decisions: Dict[str, ReviewDecision]) -> Optional[Path]:
    """Write resolved review decisions and any merge problems."""
    _ensure_legacy_globals()
    try:
        output_dir = Path(args.output).resolve()
        report_dir = output_dir / "reports"
        ensure_dir(report_dir)
        path = report_dir / "review_decisions.csv"
        fields = ["cluster_key", "effective_cluster_key", "name", "action", "merge_into", "confidence", "notes", "merge_chain", "error"]
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for key in sorted(decisions):
                effective_key, decision, chain, error = resolve_review_decision(key, decisions)
                writer.writerow({
                    "cluster_key": key,
                    "effective_cluster_key": effective_key,
                    "name": decision.name,
                    "action": decision.normalized_action(),
                    "merge_into": decisions[key].merge_into,
                    "confidence": "" if decision.confidence is None else f"{decision.confidence:.4f}",
                    "notes": decision.notes,
                    "merge_chain": ";".join(chain),
                    "error": error or "",
                })
        return path
    except Exception:
        return None


def ensure_review_decisions_for_rows(rows: List[Dict[str, Any]], decisions: Dict[str, ReviewDecision]) -> Dict[str, ReviewDecision]:
    """Return decisions for all known clusters without forcing rename/merge defaults.

    Console review assistant is intentionally conservative: missing rows become
    action=keep with an empty name, which means "no rename and no merge". During
    apply-names an empty keep name is still sent to final_review, so the user never
    accidentally creates a wrong person folder just by opening the assistant.
    """
    _ensure_legacy_globals()
    merged = dict(decisions)
    for row in rows:
        key = str(row.get("cluster_key", "")).strip()
        if key and key not in merged:
            merged[key] = ReviewDecision(
                cluster_key=key,
                name="",
                action="keep",
                merge_into="",
                confidence=parse_review_confidence(str(row.get("confidence", ""))),
                notes=f"faces={row.get('faces', '')}; files={row.get('files', '')}",
            )
    return merged


def write_names_csv_from_decisions(names_path: Path, rows: List[Dict[str, Any]], decisions: Dict[str, ReviewDecision]) -> Path:
    """Write v29/v30 review-model names.csv in a stable cluster order."""
    _ensure_legacy_globals()
    row_by_key = {str(row.get("cluster_key", "")).strip(): row for row in rows}
    keys = sorted(set(row_by_key) | set(decisions), key=cluster_sort_key)
    ensure_dir(names_path.parent)
    with names_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["cluster_key", "name", "action", "merge_into", "confidence", "notes"])
        for key in keys:
            row = row_by_key.get(key, {})
            d = decisions.get(key, ReviewDecision(cluster_key=key, action="keep"))
            confidence = d.confidence
            if confidence is None:
                confidence = parse_review_confidence(str(row.get("confidence", "")))
            notes = d.notes
            if not notes and row:
                notes = f"faces={row.get('faces', '')}; files={row.get('files', '')}; avg_det={row.get('avg_det_score', '')}"
            writer.writerow([
                key,
                d.name,
                d.normalized_action(),
                d.merge_into,
                "" if confidence is None else f"{confidence:.4f}",
                notes,
            ])
    return names_path


def print_review_cluster_help(names_path: Path, html_path: Path) -> None:
    """Print short instructions for console review-clusters mode."""
    _ensure_legacy_globals()
    print("\n" + lang_text("Консольная проверка кластеров", "Console cluster review"))
    print_wrapped(lang_text(
        "По умолчанию Enter ничего не объединяет и не переименовывает. Вы явно выбираете действие только для тех кластеров, которые хотите исправить.",
        "By default Enter does not merge or rename anything. Choose an action only for clusters you want to change.",
    ))
    print_wrapped(lang_text(
        f"Рекомендуется держать открытым HTML-отчёт с превью: {html_path}",
        f"Recommended: keep the HTML preview report open: {html_path}",
    ))
    print_wrapped(lang_text(
        f"Решения сохраняются в: {names_path}",
        f"Decisions are saved to: {names_path}",
    ))


def ask_review_action(current: ReviewDecision) -> str:
    """Ask one conservative console review action."""
    _ensure_legacy_globals()
    return choose_from_options(
        lang_text("Что сделать с этим кластером?", "What to do with this cluster?"),
        [
            {"label": lang_text("ничего не менять", "no changes"), "value": "skip", "help": lang_text("По умолчанию. Не объединять, не переименовывать.", "Default. Do not merge or rename.")},
            {"label": lang_text("задать имя / keep", "set name / keep"), "value": "keep", "help": lang_text("Указать имя человека для этого кластера.", "Set the person name for this cluster.")},
            {"label": lang_text("объединить с другим кластером / merge", "merge into another cluster"), "value": "merge", "help": lang_text("Например: person_017 объединить в person_001.", "For example: merge person_017 into person_001.")},
            {"label": lang_text("отправить в review", "send to review"), "value": "review", "help": lang_text("Кластер сомнительный или смешанный.", "Cluster is uncertain or mixed.")},
            {"label": lang_text("игнорировать / ignore", "ignore"), "value": "ignore", "help": lang_text("Ложные лица или мусорный кластер.", "False faces or junk cluster.")},
            {"label": lang_text("сохранить и выйти", "save and exit"), "value": "stop", "help": lang_text("Остановить проверку сейчас.", "Stop reviewing now.")},
        ],
        "skip",
    )


def review_clusters_console(args: argparse.Namespace, conn: sqlite3.Connection) -> Path:
    """Interactive console assistant for v29/v30 review data model.

    This is intentionally conservative for console users: the default action is
    always "skip/no changes", so opening the assistant never merges or renames
    clusters unless the user explicitly asks for it.
    """
    _ensure_legacy_globals()
    output_dir = Path(args.output).resolve()
    report_dir = output_dir / "reports"
    ensure_dir(report_dir)
    names_path = Path(args.names).resolve() if getattr(args, "names", None) else output_dir / "names.csv"
    html_path = report_dir / "clusters.html"

    rows = compute_cluster_review_rows(conn)
    if not rows:
        raise SystemExit(lang_text(
            "Нет кластеров для проверки. Сначала выполните scan + cluster или mode=all.",
            "No clusters to review. Run scan + cluster or mode=all first.",
        ))

    generate_review_clusters_csv(args, conn)
    if not names_path.exists():
        generate_names_csv(args, conn)

    decisions = load_review_decisions(names_path) if names_path.exists() else {}
    decisions = ensure_review_decisions_for_rows(rows, decisions)
    write_names_csv_from_decisions(names_path, rows, decisions)

    print_review_cluster_help(names_path, html_path)
    print_wrapped(lang_text(
        "Подсказка: если не уверены — нажимайте Enter. Это оставит текущую строку без изменений.",
        "Tip: if unsure, press Enter. This leaves the current row unchanged.",
    ))

    sorted_rows = sorted(rows, key=lambda r: cluster_sort_key(str(r.get("cluster_key", ""))))
    changed = 0
    for idx, row in enumerate(sorted_rows, start=1):
        key = str(row.get("cluster_key", "")).strip()
        if not key:
            continue
        current = decisions.get(key, ReviewDecision(cluster_key=key, action="keep"))
        print("\n" + "=" * 72)
        print(lang_text(f"Кластер {idx}/{len(sorted_rows)}: {key}", f"Cluster {idx}/{len(sorted_rows)}: {key}"))
        print(lang_text(
            f"Лиц: {row.get('faces')} | файлов: {row.get('files')} | confidence: {float(row.get('confidence') or 0.0):.4f}",
            f"Faces: {row.get('faces')} | files: {row.get('files')} | confidence: {float(row.get('confidence') or 0.0):.4f}",
        ))
        print(lang_text(
            f"Текущее решение: action={current.normalized_action()} name='{current.name}' merge_into='{current.merge_into}' notes='{current.notes}'",
            f"Current decision: action={current.normalized_action()} name='{current.name}' merge_into='{current.merge_into}' notes='{current.notes}'",
        ))

        action = ask_review_action(current)
        if action == "skip":
            continue
        if action == "stop":
            break
        if action == "keep":
            name = ask_text(lang_text("Введите имя человека", "Enter person name"), current.name).strip()
            if not name:
                print_wrapped(lang_text("Имя пустое — решение не изменено.", "Empty name — decision unchanged."))
                continue
            notes = ask_text(lang_text("Заметка", "Note"), current.notes).strip()
            decisions[key] = ReviewDecision(cluster_key=key, name=name, action="keep", merge_into="", confidence=parse_review_confidence(str(row.get("confidence", ""))), notes=notes)
            changed += 1
        elif action == "merge":
            target = ask_text(lang_text("В какой cluster_key объединить? Например person_001", "Merge into which cluster_key? Example: person_001"), current.merge_into).strip()
            if not target:
                print_wrapped(lang_text("Целевой кластер пустой — решение не изменено.", "Empty target cluster — decision unchanged."))
                continue
            if target == key:
                print_wrapped(lang_text("Нельзя объединить кластер сам в себя — решение не изменено.", "Cannot merge a cluster into itself — decision unchanged."))
                continue
            notes = ask_text(lang_text("Заметка", "Note"), current.notes).strip()
            # Keep the typed name as a human hint only. apply-names resolves the target decision.
            decisions[key] = ReviewDecision(cluster_key=key, name=current.name, action="merge", merge_into=target, confidence=parse_review_confidence(str(row.get("confidence", ""))), notes=notes)
            changed += 1
        elif action in {"review", "ignore"}:
            notes = ask_text(lang_text("Заметка", "Note"), current.notes).strip()
            decisions[key] = ReviewDecision(cluster_key=key, name=current.name if action == "ignore" else "", action=action, merge_into="", confidence=parse_review_confidence(str(row.get("confidence", ""))), notes=notes)
            changed += 1

        write_names_csv_from_decisions(names_path, sorted_rows, decisions)
        print_wrapped(lang_text("Решение сохранено.", "Decision saved."))

    write_names_csv_from_decisions(names_path, sorted_rows, decisions)
    report_path = write_review_decisions_report(args, decisions)
    print("\n" + lang_text("Консольная проверка завершена.", "Console review finished."))
    print(lang_text(f"Изменений: {changed}", f"Changes: {changed}"))
    print(lang_text(f"names.csv: {names_path}", f"names.csv: {names_path}"))
    if report_path:
        print(lang_text(f"review_decisions.csv: {report_path}", f"review_decisions.csv: {report_path}"))
    return names_path


def apply_names(args: argparse.Namespace, conn: sqlite3.Connection) -> None:
    """Apply names.csv review decisions and copy final named folders."""
    _ensure_legacy_globals()
    output_dir = Path(args.output).resolve()
    names_path = Path(args.names).resolve() if args.names else output_dir / "names.csv"
    assignments_path = output_dir / "reports" / "assignments.csv"
    if not names_path.exists():
        raise SystemExit(f"Не найден names.csv: {names_path}")
    if not assignments_path.exists():
        raise SystemExit(f"Не найден assignments.csv: {assignments_path}. Сначала запустите --mode all или --mode copy.")

    decisions = load_review_decisions(names_path)
    review_decisions_path = write_review_decisions_report(args, decisions)

    final_dir = output_dir / "final"
    review_dir = output_dir / "final_review"
    if args.clean_final:
        reset_dir(final_dir)
        reset_dir(review_dir)
    else:
        ensure_dir(final_dir)
        ensure_dir(review_dir)

    copied_final = 0
    copied_review = 0
    skipped = 0
    merged = 0
    review_forced = 0
    merge_errors = 0
    with assignments_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            src = Path(row.get("image_path", ""))
            if not src.exists():
                skipped += 1
                continue
            selected = (row.get("selected_cluster") or "").strip()
            if not selected:
                bucket = row.get("review_bucket") or "unknown"
                copy_file(src, review_dir / sanitize_folder_name(bucket), args.dry_run)
                copied_review += 1
                continue

            copied_dest_keys = set()
            for cluster_key in [c for c in selected.split(";") if c]:
                effective_key, decision, chain, error = resolve_review_decision(cluster_key, decisions)
                action = decision.normalized_action()
                if error:
                    merge_errors += 1
                    action = "review"
                if action == "ignore":
                    skipped += 1
                    continue
                if action == "merge":
                    # resolve_review_decision normally resolves until a non-merge action.
                    action = "review"
                if len(chain) > 1 and action != "review":
                    merged += 1
                if action == "review" or not decision.name:
                    review_forced += 1
                    bucket = effective_key if not error else f"{cluster_key}_{error}"
                    dest_key = f"review:{bucket}"
                    if dest_key in copied_dest_keys:
                        continue
                    copy_file(src, review_dir / sanitize_folder_name(bucket), args.dry_run)
                    copied_review += 1
                    copied_dest_keys.add(dest_key)
                else:
                    dest_name = sanitize_folder_name(decision.name)
                    dest_key = f"final:{dest_name}"
                    if dest_key in copied_dest_keys:
                        continue
                    copy_file(src, final_dir / dest_name, args.dry_run)
                    copied_final += 1
                    copied_dest_keys.add(dest_key)

    print(lang_text("apply-names завершён.", "apply-names finished."))
    print(lang_text("Скопировано в final:", "Copied to final:"), copied_final)
    print(lang_text("Скопировано в final_review:", "Copied to final_review:"), copied_review)
    print(lang_text("Пропущено:", "Skipped:"), skipped)
    if merged:
        print(lang_text("Файлов/назначений обработано через merge:", "Files/assignments processed through merge:"), merged)
    if review_forced:
        print(lang_text("Отправлено в review по names.csv или из-за пустого имени:", "Sent to review by names.csv or empty name:"), review_forced)
    if merge_errors:
        print(lang_text("Проблем merge-правил:", "Merge-rule problems:"), merge_errors, lang_text("— проверьте reports/review_decisions.csv", "— check reports/review_decisions.csv"))
    if review_decisions_path:
        print(lang_text("Отчёт review-решений:", "Review decisions report:"), review_decisions_path)


__all__ = [
    "compute_cluster_review_rows",
    "generate_names_csv",
    "generate_review_clusters_csv",
    "parse_review_confidence",
    "normalize_review_action",
    "load_review_decisions",
    "resolve_review_decision",
    "write_review_decisions_report",
    "ensure_review_decisions_for_rows",
    "write_names_csv_from_decisions",
    "print_review_cluster_help",
    "ask_review_action",
    "review_clusters_console",
    "apply_names",
]
