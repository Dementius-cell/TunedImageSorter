#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract the first valid JSON value from mixed command output.

Used by Windows packaging verification when a third-party native library writes
extra text before/after a diagnostic JSON payload. The extracted JSON is written
back as clean UTF-8 so PowerShell can use ConvertFrom-Json deterministically.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence


def _decode_bytes(raw: bytes) -> str:
    """Decode command output produced by Python, cmd.exe or Windows PowerShell.

    Windows PowerShell 5.x writes redirected native-process output as UTF-16LE
    with a BOM.  v65.2 failed here because the latin-1 fallback accepted those
    bytes before JSON scanning saw real braces.  v65.4 checks UTF-16 encodings
    before single-byte fallbacks so build-time GPU verification can parse both
    auto-created raw logs and manually redirected diagnostics.
    """
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "utf-16-le", "utf-16-be", "cp866", "cp1251"):
        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        # Avoid accepting UTF-16 data decoded as a single-byte code page.
        if text.count("\x00") > max(4, len(text) // 20):
            continue
        return text
    return raw.decode("utf-8", errors="replace")


def extract_first_json(text: str) -> tuple[Any, int, int]:
    """Return ``(value, start, end)`` for the first decodable JSON value.

    The scanner tries every ``{`` and ``[`` position.  This is deliberately more
    reliable than a simple first-brace/last-brace substring when logs contain
    provider lists or warnings around the JSON object.
    """
    decoder = json.JSONDecoder()
    starts = [idx for idx, char in enumerate(text) if char in "{["]
    last_error: Exception | None = None
    for start in starts:
        try:
            value, rel_end = decoder.raw_decode(text[start:])
            return value, start, start + rel_end
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise ValueError(f"No valid JSON value found in mixed output. Last parse error: {last_error}")
    raise ValueError("No JSON object/array start marker found in mixed output.")


def _get_path_value(payload: Any, dotted_path: str) -> Any:
    value = payload
    for part in dotted_path.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            raise KeyError(dotted_path)
    return value


def _parse_required_value(text: str) -> Any:
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    try:
        return json.loads(text)
    except Exception:
        return text


def _validate_requirements(payload: Any, requirements: Iterable[str]) -> list[str]:
    errors: list[str] = []
    for requirement in requirements:
        if "=" not in requirement:
            errors.append(f"Invalid requirement {requirement!r}; expected path=value")
            continue
        path, expected_raw = requirement.split("=", 1)
        expected = _parse_required_value(expected_raw)
        try:
            actual = _get_path_value(payload, path)
        except KeyError:
            errors.append(f"Missing required JSON path: {path}")
            continue
        if actual != expected:
            errors.append(f"JSON path {path} is {actual!r}, expected {expected!r}")
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract first JSON object/array from mixed command output.")
    parser.add_argument("input", help="Input text file that may contain logs plus JSON.")
    parser.add_argument("output", nargs="?", help="Clean JSON output path. Defaults to stdout if omitted.")
    parser.add_argument("--require", action="append", default=[], help="Assert dotted.path=value in extracted JSON. May be repeated.")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    raw = input_path.read_bytes()
    text = _decode_bytes(raw)
    try:
        payload, start, end = extract_first_json(text)
    except Exception as exc:
        print(f"extract_json_from_mixed_output: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    errors = _validate_requirements(payload, args.require)
    if errors:
        for error in errors:
            print(f"extract_json_from_mixed_output: {error}", file=sys.stderr)
        return 3

    clean = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(clean + "\n", encoding="utf-8")
    else:
        print(clean)

    prefix = text[:start].strip()
    suffix = text[end:].strip()
    if prefix or suffix:
        print(
            f"extract_json_from_mixed_output: ignored non-JSON text before={len(prefix)} chars after={len(suffix)} chars",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
