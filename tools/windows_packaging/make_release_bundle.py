#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create the public Tuned Image Sorter release bundle.

This script is intentionally packaging-only. It does not run TunedImageSorter.exe,
does not import Qt, does not run ML, does not scan photos and does not modify
user result folders. It copies already-built portable ZIP archives into a
single release handoff directory and writes SHA256SUMS.txt plus a JSON manifest.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from face_sorter_mvp.core.constants import SCRIPT_VERSION  # noqa: E402

RELEASE_BUNDLE_STAGE = "Этап 055"
RELEASE_BUNDLE_SCHEMA_VERSION = 1
RELEASE_BUNDLE_DIR_NAME = "TunedImageSorter_v69_6_release"
RELEASE_ZIP_FILES: Tuple[str, ...] = (
    "TunedImageSorter_CPU_portable_v69_6.zip",
    "TunedImageSorter_GPU_FULL_portable_v69_6.zip",
    "TunedImageSorter_GPU_LITE_portable_v69_6.zip",
)
HANDOFF_DOCS: Tuple[str, ...] = (
    "RELEASE_BUNDLE_RU.txt",
    "RELEASE_BUNDLE_EN.txt",
    "WHICH_VERSION_TO_DOWNLOAD_RU.txt",
    "WHICH_VERSION_TO_DOWNLOAD_EN.txt",
    "PUBLIC_RELEASE_NOTES_RU.txt",
    "PUBLIC_RELEASE_NOTES_EN.txt",
    "PROFILE_GUIDE_RU.txt",
    "PROFILE_GUIDE_EN.txt",
    "PRIVACY_LOCAL_PROCESSING_RU.txt",
    "PRIVACY_LOCAL_PROCESSING_EN.txt",
    "KNOWN_LIMITATIONS_RU.txt",
    "KNOWN_LIMITATIONS_EN.txt",
    "README_RU.txt",
    "README_EN.txt",
    "VERSION.txt",
)


@dataclass(frozen=True)
class ReleaseBundleFile:
    filename: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class ReleaseBundleManifest:
    app: str
    version: str
    refactor_stage: str
    schema_version: int
    created_at_utc: str
    bundle_dir: str
    profiles: Dict[str, str]
    files: Tuple[ReleaseBundleFile, ...]
    docs: Tuple[str, ...]
    known_non_blocking_issue: str
    unchanged_contracts: Tuple[str, ...]

    def to_dict(self) -> Dict[str, object]:
        data = asdict(self)
        data["files"] = [asdict(item) for item in self.files]
        return data


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def create_release_bundle(*, source_root: Path, dist_dir: Path, output_dir: Path, clean: bool) -> ReleaseBundleManifest:
    if SCRIPT_VERSION != "v69.6":
        raise RuntimeError(f"SCRIPT_VERSION is {SCRIPT_VERSION!r}; expected 'v69.6'")

    source_root = source_root.resolve()
    dist_dir = dist_dir.resolve()
    output_dir = output_dir.resolve()

    missing = [name for name in RELEASE_ZIP_FILES if not (dist_dir / name).exists()]
    if missing:
        raise FileNotFoundError(
            "Missing portable ZIP files in dist dir: "
            + ", ".join(missing)
            + f". Build CPU, GPU_FULL and GPU_LITE first under {dist_dir}."
        )

    if output_dir.exists() and clean:
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    files: List[ReleaseBundleFile] = []
    sha_lines: List[str] = []
    for name in RELEASE_ZIP_FILES:
        src = dist_dir / name
        dst = output_dir / name
        shutil.copy2(src, dst)
        digest = _sha256(dst)
        files.append(ReleaseBundleFile(filename=name, sha256=digest, size_bytes=dst.stat().st_size))
        sha_lines.append(f"{digest}  {name}")

    copied_docs: List[str] = []
    for name in HANDOFF_DOCS:
        src = source_root / name
        if not src.exists():
            raise FileNotFoundError(f"Missing handoff doc: {src}")
        shutil.copy2(src, output_dir / name)
        copied_docs.append(name)

    (output_dir / "SHA256SUMS.txt").write_text("\n".join(sha_lines) + "\n", encoding="utf-8")
    copied_docs.append("SHA256SUMS.txt")

    manifest = ReleaseBundleManifest(
        app="Tuned Image Sorter",
        version=SCRIPT_VERSION,
        refactor_stage=RELEASE_BUNDLE_STAGE,
        schema_version=RELEASE_BUNDLE_SCHEMA_VERSION,
        created_at_utc=dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        bundle_dir=str(output_dir),
        profiles={
            "CPU": "TunedImageSorter_CPU_portable_v69_6.zip",
            "GPU_FULL": "TunedImageSorter_GPU_FULL_portable_v69_6.zip",
            "GPU_LITE": "TunedImageSorter_GPU_LITE_portable_v69_6.zip",
        },
        files=tuple(files),
        docs=tuple(copied_docs),
        known_non_blocking_issue="reports folder may not auto-open after ordinary Start",
        unchanged_contracts=(
            "ML/recognition unchanged",
            "clustering unchanged",
            "ordinary Start pipeline unchanged",
            "apply-names unchanged",
            "SQLite schema unchanged",
            "project.json schema unchanged",
            "CSV schemas unchanged",
            "result-health unchanged",
            "support-bundle unchanged",
            "CPU/GPU_FULL/GPU_LITE split unchanged",
            "GPU Lite runtime setup logic unchanged",
            "internal Python package remains face_sorter_mvp",
        ),
    )
    (output_dir / "RELEASE_BUNDLE_MANIFEST.json").write_text(
        json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Tuned Image Sorter public release bundle with SHA256 checksums.")
    parser.add_argument("--source-root", default=str(ROOT), help="Source root containing handoff docs. Defaults to project root.")
    parser.add_argument("--dist-dir", default=str(ROOT / "dist" / "windows"), help="Folder containing portable ZIP files.")
    parser.add_argument("--output-dir", default="", help="Release bundle output directory. Defaults to dist/windows/TunedImageSorter_v69_6_release.")
    parser.add_argument("--no-clean", action="store_true", help="Do not remove an existing output directory before copying files.")
    args = parser.parse_args()

    source_root = Path(args.source_root)
    dist_dir = Path(args.dist_dir)
    output_dir = Path(args.output_dir) if args.output_dir else dist_dir / RELEASE_BUNDLE_DIR_NAME
    manifest = create_release_bundle(source_root=source_root, dist_dir=dist_dir, output_dir=output_dir, clean=not args.no_clean)
    print("release_bundle: OK")
    print(f"version={manifest.version} refactor_stage={manifest.refactor_stage}")
    print(f"bundle={manifest.bundle_dir}")
    for item in manifest.files:
        print(f"sha256 {item.sha256}  {item.filename}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
