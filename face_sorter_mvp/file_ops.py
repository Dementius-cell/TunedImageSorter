#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""File/path hardening helpers for face_sorter_mvp v38.

This module is intentionally independent from the recognition pipeline. It can be
reused by CLI, future GUI and packaged .exe builds.
"""
from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# Supported image extensions. Header validation still happens separately, because
# some files have image-like extensions but invalid content.
IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff", ".heic", ".heif"
}
WINDOWS_FORBIDDEN_CHARS = r'<>:"/\\|?*'
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
DEFAULT_MAX_PATH_LEN = 240
_SAFE_COPY_COUNTER = 0


@dataclass
class DestinationPlan:
    """Describes the planned safe target path before copying a file."""
    source_path: Path
    target_path: Path
    original_name: str
    safe_name: str
    reason: str
    path_hash: str
    flags: Dict[str, object] = field(default_factory=dict)


@dataclass
class CopyResult:
    """Structured result for one copy attempt, suitable for logs/UI/reports."""
    source_path: Path
    target_path: Optional[Path]
    status: str
    reason: str
    error: Optional[str] = None
    plan: Optional[DestinationPlan] = None
    flags: Dict[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status in {"copied", "dry_run"}


def _next_counter() -> int:
    """Return a monotonically increasing counter for generated safe names."""
    global _SAFE_COPY_COUNTER
    _SAFE_COPY_COUNTER += 1
    return _SAFE_COPY_COUNTER


def _timestamp() -> str:
    """Return a Windows-safe timestamp used in generated file names."""
    return dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def short_hash(text: str, n: int = 10) -> str:
    """Return a short deterministic hash for paths and generated file names."""
    return hashlib.sha1(str(text).encode("utf-8", errors="ignore")).hexdigest()[:n]


def normalize_path(value: object, *, base: Optional[Path] = None, must_exist: bool = False) -> Path:
    """Normalize a path typed/pasted by a user.

    - trims surrounding whitespace and quotes;
    - expands ~ and environment variables;
    - optionally resolves relative paths against base;
    - uses resolve(strict=False), so missing output directories are OK.
    """
    raw = str(value or "").strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}:
        raw = raw[1:-1].strip()
    raw = os.path.expandvars(os.path.expanduser(raw))
    path = Path(raw)
    if base is not None and not path.is_absolute():
        path = base / path
    try:
        path = path.resolve(strict=must_exist)
    except Exception:
        path = path.absolute()
    return path


def windows_long_path(path: Path) -> str:
    """Return a Windows long-path string for low-level file operations when useful.

    The normal Path is preserved in reports; this helper is only for open/copy/stat
    calls. On non-Windows it returns str(path).
    """
    s = str(path)
    if os.name != "nt":
        return s
    if s.startswith("\\\\?\\"):
        return s
    # UNC: \\server\share -> \\?\UNC\server\share
    if s.startswith("\\\\"):
        return "\\\\?\\UNC\\" + s.lstrip("\\")
    return "\\\\?\\" + s


def safe_folder_name(name: str, fallback: str = "unnamed") -> str:
    """Sanitize a user/person folder name for Windows-compatible output."""
    cleaned, _ = _sanitize_component(str(name or ""), fallback=fallback, allow_dot_ext=False)
    return cleaned


def safe_file_stem(name: str, fallback: str = "photo") -> Tuple[str, List[str]]:
    """Sanitize a filename stem and return reasons for any changes."""
    return _sanitize_component(str(name or ""), fallback=fallback, allow_dot_ext=False)


def safe_filename(name: str, fallback_stem: str = "photo", fallback_ext: str = ".bin") -> Tuple[str, List[str]]:
    """Sanitize a full filename while preserving a safe extension when possible."""
    p = Path(str(name or ""))
    stem, reasons = safe_file_stem(p.stem, fallback=fallback_stem)
    ext = safe_extension(p.suffix, fallback=fallback_ext)
    if ext != p.suffix.lower():
        reasons.append("unsafe_or_missing_extension")
    return stem + ext, _unique_reasons(reasons)


def safe_extension(ext: str, fallback: str = ".bin") -> str:
    """Return a safe lowercase file extension or a fallback extension."""
    ext = str(ext or "").strip().lower()
    if not ext.startswith(".") or len(ext) > 16 or not re.match(r"^\.[a-z0-9_+-]+$", ext):
        return fallback
    return ext


def _sanitize_component(value: str, fallback: str, allow_dot_ext: bool = False) -> Tuple[str, List[str]]:
    """Sanitize one path component without touching parent directories."""
    reasons: List[str] = []
    original = value
    cleaned = str(value or "").strip()
    if cleaned != original:
        reasons.append("trim_or_spaces")
    for ch in WINDOWS_FORBIDDEN_CHARS:
        if ch in cleaned:
            cleaned = cleaned.replace(ch, "_")
            reasons.append("invalid_chars")
    # Windows also dislikes control chars.
    if any(ord(ch) < 32 for ch in cleaned):
        cleaned = "".join("_" if ord(ch) < 32 else ch for ch in cleaned)
        reasons.append("control_chars")
    cleaned2 = re.sub(r"\s+", " ", cleaned).strip(" .")
    if cleaned2 != cleaned:
        reasons.append("trim_or_spaces")
    cleaned = cleaned2
    if not cleaned:
        cleaned = fallback
        reasons.append("empty_filename")
    if cleaned.upper() in WINDOWS_RESERVED_NAMES:
        cleaned = cleaned + "_"
        reasons.append("windows_reserved_name")
    return cleaned, _unique_reasons(reasons)


def _unique_reasons(reasons: Sequence[str]) -> List[str]:
    """Return reasons in stable order without duplicates."""
    return list(dict.fromkeys([r for r in reasons if r]))


def path_diagnostics(path: Path) -> Dict[str, object]:
    """Return path flags used by problem_files.csv and filename_map.csv."""
    s = str(path)
    flags: Dict[str, object] = {
        "path_len": len(s),
        "is_unc": s.startswith("\\\\"),
        "has_forbidden_chars_in_name": any(ch in path.name for ch in WINDOWS_FORBIDDEN_CHARS),
        "has_unicode": any(ord(ch) > 127 for ch in s),
        "has_control_chars": any(ord(ch) < 32 for ch in s),
        "suffix": path.suffix.lower(),
        "is_network_path": is_network_path(path),
        "is_cloud_placeholder": is_cloud_placeholder(path),
    }
    if len(s) >= 260:
        flags["source_path_too_long"] = True
    return flags


def is_network_path(path: Path) -> bool:
    """Best-effort detection of UNC or mapped network-drive paths."""
    s = str(path)
    if s.startswith("\\\\"):
        return True
    if os.name != "nt":
        return False
    try:
        root = Path(path).anchor
        if not root:
            return False
        DRIVE_REMOTE = 4
        GetDriveTypeW = ctypes.windll.kernel32.GetDriveTypeW
        GetDriveTypeW.argtypes = [ctypes.c_wchar_p]
        GetDriveTypeW.restype = ctypes.c_uint
        return int(GetDriveTypeW(root)) == DRIVE_REMOTE
    except Exception:
        return False


def is_cloud_placeholder(path: Path) -> bool:
    """Best-effort Windows cloud placeholder detection.

    OneDrive/Dropbox placeholders may expose OFFLINE/RECALL attributes. If this returns
    true, reading may block or trigger download; callers can log this reason.
    """
    if os.name != "nt":
        return False
    try:
        GetFileAttributesW = ctypes.windll.kernel32.GetFileAttributesW
        GetFileAttributesW.argtypes = [ctypes.c_wchar_p]
        GetFileAttributesW.restype = ctypes.c_uint32
        attrs = int(GetFileAttributesW(str(path)))
        if attrs == 0xFFFFFFFF:
            return False
        FILE_ATTRIBUTE_OFFLINE = 0x00001000
        FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x00040000
        FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x00400000
        return bool(attrs & (FILE_ATTRIBUTE_OFFLINE | FILE_ATTRIBUTE_RECALL_ON_OPEN | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS))
    except Exception:
        return False


def is_supported_image(path: Path, *, allow_header_only: bool = False) -> bool:
    """Return True when a path extension is one of the supported image types."""
    ext = path.suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        return True
    if allow_header_only:
        ok, _, _ = image_magic_status(path, allow_header_only=True)
        return ok
    return False


def iter_supported_images(root: Path, *, allow_header_only: bool = False) -> Iterable[Path]:
    """Yield supported image files from a folder tree with basic path diagnostics."""
    root = normalize_path(root, must_exist=True)
    for path in root.rglob("*"):
        try:
            if path.is_file() and is_supported_image(path, allow_header_only=allow_header_only):
                yield path
        except OSError:
            # A problematic path will be logged later if explicitly selected/read.
            continue


def image_magic_status(path: Path, *, allow_header_only: bool = False, strict_extension: bool = False) -> Tuple[bool, str, str]:
    """Check whether file extension and magic bytes look like a supported image.

    By default v37 accepts files whose extension is wrong but whose header is a
    recognized supported image format. This avoids skipping valid photos such as
    PNG files saved with .jpg names. Pass strict_extension=True to preserve the
    old v36 behavior and reject extension/header mismatches.
    """
    ext = path.suffix.lower()
    if ext not in IMAGE_EXTENSIONS and not allow_header_only:
        return False, "unsupported_extension", f"unsupported extension: {ext or '<none>'}"
    try:
        if not path.exists():
            return False, "missing_source", "file does not exist"
        flags = path_diagnostics(path)
        if flags.get("is_cloud_placeholder"):
            # Not a hard failure; return a clear reason only if opening fails later.
            pass
        if path.stat().st_size <= 0:
            return False, "empty_file", "file size is zero"
        with open(windows_long_path(path), "rb") as f:
            head = f.read(64)
    except PermissionError as exc:
        return False, "locked_or_permission_denied", str(exc)
    except OSError as exc:
        msg = str(exc)
        reason = "read_error"
        if "path" in msg.lower() and "too long" in msg.lower():
            reason = "source_path_too_long"
        return False, reason, msg
    except Exception as exc:
        return False, "read_error", str(exc)
    if not head:
        return False, "empty_file", "empty header"

    detected = _detect_image_type_from_header(head)
    if ext in IMAGE_EXTENSIONS:
        if _extension_matches_detected_type(ext, detected):
            return True, "ok", ""
        if detected:
            message = f"extension {ext} but header looks like {detected}"
            if strict_extension:
                return False, "extension_mismatch", message
            return True, "extension_mismatch_allowed", message
        return False, "not_an_image", f"extension {ext} but header is not recognized as an image"
    if allow_header_only and detected:
        return True, "header_only_image", detected
    return False, "not_an_image", "header is not recognized as an image"


def _detect_image_type_from_header(head: bytes) -> str:
    """Infer image type from magic bytes without fully decoding the file."""
    if head.startswith(b"\xff\xd8"):
        return "jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
        return "gif"
    if head.startswith(b"RIFF") and b"WEBP" in head[:16]:
        return "webp"
    if head.startswith(b"BM"):
        return "bmp"
    if head.startswith(b"II*\x00") or head.startswith(b"MM\x00*"):
        return "tiff"
    if b"ftyp" in head[:32] and any(x in head[:64] for x in [b"heic", b"heix", b"hevc", b"heif", b"mif1", b"msf1"]):
        return "heif"
    return ""


def _extension_matches_detected_type(ext: str, detected: str) -> bool:
    """Return True when the file extension is compatible with detected header type."""
    if not detected:
        return False
    groups = {
        "jpeg": {".jpg", ".jpeg"},
        "png": {".png"},
        "gif": {".gif"},
        "webp": {".webp"},
        "bmp": {".bmp"},
        "tiff": {".tif", ".tiff"},
        "heif": {".heic", ".heif"},
    }
    return ext in groups.get(detected, set())


def plan_safe_destination(src: Path, dst_dir: Path, *, max_path_len: int = DEFAULT_MAX_PATH_LEN) -> DestinationPlan:
    """Plan a collision-safe destination path and explain any renaming."""
    dst_dir = normalize_path(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    src = Path(src)
    path_hash = short_hash(str(src.resolve() if src.exists() else src), 8)
    suffix = safe_extension(src.suffix, fallback=".bin")
    stem, reasons = safe_file_stem(src.stem, fallback="photo")
    flags = path_diagnostics(src)

    def candidate(stem_value: str) -> Path:
        return dst_dir / f"{stem_value}{suffix}"

    target = candidate(stem)
    if target.exists():
        reasons.append("copy_collision")
        target = candidate(f"{stem}__{path_hash}")

    if len(str(target)) >= max_path_len:
        reasons.append("target_path_too_long")
        room = max(8, max_path_len - len(str(dst_dir)) - len(suffix) - len(path_hash) - 8)
        target = candidate(f"{stem[:room]}__{path_hash}")

    if target.exists():
        reasons.append("copy_collision_after_hash")
        seq = _next_counter()
        target = candidate(f"{stem[:80]}__{seq:06d}_{path_hash}")

    if len(str(target)) >= max_path_len or target.exists():
        reasons.append("safe_copy_fallback")
        seq = _next_counter()
        target = dst_dir / f"safe_copy_{_timestamp()}_{seq:06d}_{path_hash}{suffix}"

    safe_name = target.name
    reason = ";".join(_unique_reasons(reasons)) or "unchanged"
    return DestinationPlan(
        source_path=src,
        target_path=target,
        original_name=src.name,
        safe_name=safe_name,
        reason=reason,
        path_hash=path_hash,
        flags=flags,
    )


def copy_with_collision_handling(src: Path, dst_dir: Path, *, dry_run: bool = False, max_path_len: int = DEFAULT_MAX_PATH_LEN) -> CopyResult:
    """Copy a file using safe names, collision handling and optional dry-run."""
    plan = plan_safe_destination(src, dst_dir, max_path_len=max_path_len)
    if dry_run:
        return CopyResult(src, plan.target_path, "dry_run", plan.reason, plan=plan, flags=plan.flags)
    try:
        plan.target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(windows_long_path(plan.source_path), windows_long_path(plan.target_path))
        return CopyResult(src, plan.target_path, "copied", plan.reason, plan=plan, flags=plan.flags)
    except PermissionError as exc:
        return CopyResult(src, plan.target_path, "error", "permission_denied", str(exc), plan=plan, flags=plan.flags)
    except OSError as exc:
        msg = str(exc)
        reason = "copy_error"
        if "path" in msg.lower() and "too long" in msg.lower():
            reason = "target_path_too_long"
        return CopyResult(src, plan.target_path, "error", reason, msg, plan=plan, flags=plan.flags)
    except Exception as exc:
        return CopyResult(src, plan.target_path, "error", type(exc).__name__, str(exc), plan=plan, flags=plan.flags)

# ---------------------------------------------------------------------------
# Developer diagnostics CLI
# ---------------------------------------------------------------------------
# file_ops.py is not intended to be the main user-facing application entry
# point. The CLI below exists for maintainers, AI agents and bug triage: it can
# validate path-safety helpers without running the recognition pipeline.


def _assert_self_test(condition: bool, message: str) -> None:
    """Raise AssertionError with a readable message when a self-test fails."""
    if not condition:
        raise AssertionError(message)


def run_self_test() -> int:
    """Run a lightweight self-test for path hardening helpers.

    The test intentionally avoids image recognition and third-party ML packages.
    It verifies Windows-safe naming, collision handling, extension checks, magic
    byte detection, Unicode preservation, reserved-name handling and dry-run copy
    planning. It returns a process-style status code: 0 for success, 1 for fail.
    """
    print("file_ops self-test: starting")
    checks: List[str] = []

    def ok(name: str) -> None:
        checks.append(name)
        print(f"  OK  {name}")

    try:
        folder = safe_folder_name('bad<folder>:name?')
        _assert_self_test('<' not in folder and ':' not in folder and '?' not in folder, "forbidden chars were not removed from folder name")
        ok("safe_folder_name removes forbidden Windows characters")

        reserved = safe_folder_name('CON')
        _assert_self_test(reserved.upper() != 'CON', "reserved Windows folder name was not changed")
        ok("safe_folder_name handles Windows reserved names")

        fname, reasons = safe_filename('party:masha?.JPG')
        _assert_self_test(fname.endswith('.jpg'), "safe_filename did not normalize extension")
        _assert_self_test(':' not in fname and '?' not in fname, "safe_filename left forbidden chars")
        _assert_self_test('invalid_chars' in reasons, "safe_filename did not report invalid_chars")
        ok("safe_filename sanitizes names and preserves extension")

        unicode_name, _ = safe_filename('фото_😀.jpg')
        _assert_self_test('фото' in unicode_name and unicode_name.endswith('.jpg'), "unicode filename was not preserved")
        ok("safe_filename preserves Unicode when it is Windows-safe")

        ext = safe_extension('.JPEG')
        _assert_self_test(ext == '.jpeg', "safe_extension did not normalize extension")
        ok("safe_extension normalizes safe extensions")

        with tempfile.TemporaryDirectory(prefix='face_sorter_file_ops_') as td:
            root = Path(td)
            # Use a real Windows-safe file name for physical I/O. Invalid-name
            # behavior is tested above through safe_filename(); creating
            # source?.jpg on Windows raises OSError before the helper can run.
            src = root / 'source.jpg'
            src.write_bytes(b'\xff\xd8\xff\xe0' + b'0' * 128)
            ok_status, reason, _ = image_magic_status(src)
            _assert_self_test(ok_status and reason == 'ok', "JPEG magic bytes were not detected")
            ok("image_magic_status detects valid JPEG header")

            fake = root / 'fake.jpg'
            fake.write_text('not an image', encoding='utf-8')
            ok_status, reason, _ = image_magic_status(fake)
            _assert_self_test(not ok_status and reason == 'not_an_image', "fake JPG was not rejected")
            ok("image_magic_status rejects unrecognized image headers")

            png_named_jpg = root / "wrong_ext.jpg"
            png_named_jpg.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
            ok_status, reason, _ = image_magic_status(png_named_jpg)
            _assert_self_test(ok_status and reason == 'extension_mismatch_allowed', "extension mismatch was not allowed by default")
            ok_status, reason, _ = image_magic_status(png_named_jpg, strict_extension=True)
            _assert_self_test(not ok_status and reason == 'extension_mismatch', "strict extension mismatch was not rejected")
            ok("image_magic_status handles extension/header mismatch policy")

            dst = root / 'out'
            result1 = copy_with_collision_handling(src, dst)
            _assert_self_test(result1.ok and result1.target_path and result1.target_path.exists(), "first copy failed")
            result2 = copy_with_collision_handling(src, dst)
            _assert_self_test(result2.ok and result2.target_path and result2.target_path.exists(), "second copy failed")
            _assert_self_test(result1.target_path != result2.target_path, "collision handling reused the same target path")
            ok("copy_with_collision_handling creates unique targets")

            dry = copy_with_collision_handling(src, dst, dry_run=True)
            _assert_self_test(dry.status == 'dry_run' and dry.target_path is not None, "dry-run did not produce a planned target")
            ok("copy_with_collision_handling supports dry-run")

            diag = path_diagnostics(src)
            _assert_self_test('path_len' in diag and 'has_unicode' in diag, "path_diagnostics missing expected keys")
            ok("path_diagnostics returns stable report flags")

        print(f"file_ops self-test: passed ({len(checks)} checks)")
        return 0
    except Exception as exc:
        print(f"file_ops self-test: FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


def diagnose_path(path_value: str, *, as_json: bool = False) -> int:
    """Print diagnostics for one path without modifying files.

    This is useful when a bug report mentions long paths, Unicode names, cloud
    placeholders, network paths, invalid characters or extension/header mismatch.
    """
    try:
        path = normalize_path(path_value, must_exist=False)
        safe_name, safe_reasons = safe_filename(path.name or 'unnamed')
        magic_ok, magic_reason, magic_detail = image_magic_status(path) if path.exists() and path.is_file() else (False, 'not_checked', 'path does not exist or is not a file')
        data = {
            'original': path_value,
            'normalized': str(path),
            'exists': path.exists(),
            'is_file': path.is_file() if path.exists() else False,
            'parent_exists': path.parent.exists(),
            'suffix': path.suffix.lower(),
            'is_supported_image_by_extension': path.suffix.lower() in IMAGE_EXTENSIONS,
            'magic_ok': magic_ok,
            'magic_reason': magic_reason,
            'magic_detail': magic_detail,
            'safe_filename': safe_name,
            'safe_filename_reasons': safe_reasons,
            'safe_folder_name_for_parent_name': safe_folder_name(path.parent.name or 'folder'),
            'diagnostics': path_diagnostics(path),
            'windows_long_path': windows_long_path(path),
        }
        if path.exists() and path.is_file():
            try:
                data['size_bytes'] = path.stat().st_size
            except OSError as exc:
                data['size_error'] = str(exc)
        if as_json:
            print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
        else:
            print("file_ops path diagnostics")
            print(f"  original:      {data['original']}")
            print(f"  normalized:    {data['normalized']}")
            print(f"  exists:        {data['exists']}")
            print(f"  is_file:       {data['is_file']}")
            print(f"  suffix:        {data['suffix'] or '<none>'}")
            print(f"  supported ext: {data['is_supported_image_by_extension']}")
            print(f"  magic status:  {data['magic_reason']} ({data['magic_detail']})")
            print(f"  safe filename: {data['safe_filename']}")
            print(f"  safe reasons:  {', '.join(data['safe_filename_reasons']) or 'unchanged'}")
            print("  flags:")
            for key, value in data['diagnostics'].items():
                print(f"    {key}: {value}")
        return 0
    except Exception as exc:
        print(f"file_ops diagnose-path: FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


def build_file_ops_arg_parser() -> argparse.ArgumentParser:
    """Build the developer-only CLI parser for this helper module."""
    parser = argparse.ArgumentParser(
        description="Developer diagnostics for face_sorter_mvp file/path helpers.",
        epilog=(
            "Examples: python file_ops.py --self-test | "
            "python file_ops.py --diagnose-path \"D:\\Photos\\bad:name?.jpg\" --json"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('--self-test', action='store_true', help='Run a lightweight self-test for safe filename/path/copy helpers.')
    parser.add_argument('--diagnose-path', metavar='PATH', help='Print diagnostics for one path without modifying files.')
    parser.add_argument('--json', action='store_true', help='Print --diagnose-path output as JSON.')
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Developer CLI entry point for file_ops.py."""
    parser = build_file_ops_arg_parser()
    args = parser.parse_args(argv)
    if args.self_test:
        return run_self_test()
    if args.diagnose_path:
        return diagnose_path(args.diagnose_path, as_json=bool(args.json))
    parser.print_help()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

