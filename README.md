# Tuned Image Sorter

Tuned Image Sorter is a Windows application for local photo sorting by detected face clusters. It is designed for large personal archives, event folders, family collections and professional image sets where photos should stay on the user's computer.

Русское описание: Tuned Image Sorter - Windows-приложение для локальной сортировки больших папок с фотографиями по распознанным лицам. Доступны профили CPU, GPU_FULL и GPU_LITE.

## Status

- Version: `v69.6`
- Stage: `055`
- Internal Python package: `face_sorter_mvp`
- Main Windows launchers in portable builds: `TunedImageSorter.exe` and `TunedImageSorter_CLI.exe`
- Processing model: local-first, no cloud service required by the app workflow

The public product name is **Tuned Image Sorter**. The internal package name remains `face_sorter_mvp` for compatibility with the existing code and build scripts.

## Downloads

Portable Windows ZIP files should be published through GitHub Releases, not committed to the source repository.

| Asset | Recommended for |
| --- | --- |
| `TunedImageSorter_CPU_portable_v69_6.zip` | Most Windows PCs. Safest first download. |
| `TunedImageSorter_GPU_FULL_portable_v69_6.zip` | NVIDIA GPU PCs. Larger package with bundled CUDA runtime files. |
| `TunedImageSorter_GPU_LITE_portable_v69_6.zip` | Experimental smaller GPU profile with runtime setup/fallback behavior. |

Use `WHICH_VERSION_TO_DOWNLOAD_RU.txt` or `WHICH_VERSION_TO_DOWNLOAD_EN.txt` for user-facing download guidance. SHA256 checksums should be published next to release assets.

## Quick Start From Source

Source-tree runs are mainly for development and packaging. Regular users should prefer a portable release ZIP.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r tools\windows_packaging\requirements-windows-cpu.txt
.\.venv\Scripts\python.exe -m face_sorter_mvp --help
.\.venv\Scripts\python.exe -m face_sorter_mvp.ui
```

For NVIDIA GPU packaging, read `tools/windows_packaging/README_WINDOWS_PACKAGING_EN.md` and use the controlled GPU build flow instead of mixing CPU and GPU ONNX Runtime packages manually.

## Repository Structure

| Path | Purpose |
| --- | --- |
| `face_sorter_mvp/` | Application package, CLI, backend pipeline, optional PySide6 UI and resources. |
| `face_sorter_mvp/core/` | Pipeline contracts, release checks, runtime preflight, project state and packaging guards. |
| `face_sorter_mvp/reports/` | HTML/report and support-bundle helpers. |
| `docs/` | User guides, help files, developer notes and GitHub Pages entry page. |
| `docs/release/v69.6/public_handoff/` | Release announcement drafts, checklist, support templates and publication notes. |
| `tools/release_check.py` | Lightweight source/release-candidate verification entry point. |
| `tools/windows_packaging/` | Windows PyInstaller build profiles and CPU/GPU dependency sets. |

Several RU/EN `.txt` files intentionally remain at the repository root because the release checks and friend-ready portable package layout expect them there.

## Documentation Map

| Need | Files |
| --- | --- |
| First user read | `START_HERE_RU.txt`, `START_HERE_EN.txt` |
| Short setup | `QUICK_START_RU.txt`, `QUICK_START_EN.txt`, `FIRST_RUN_RU.txt`, `FIRST_RUN_EN.txt` |
| Errors and recovery | `ERRORS_RU.txt`, `ERRORS_EN.txt`, `TROUBLESHOOTING_RU.txt`, `TROUBLESHOOTING_EN.txt` |
| Version choice | `WHICH_VERSION_TO_DOWNLOAD_RU.txt`, `WHICH_VERSION_TO_DOWNLOAD_EN.txt` |
| Privacy | `PRIVACY_LOCAL_PROCESSING_RU.txt`, `PRIVACY_LOCAL_PROCESSING_EN.txt` |
| Known limits | `KNOWN_LIMITATIONS_RU.txt`, `KNOWN_LIMITATIONS_EN.txt` |
| Developer notes | `docs/DEVELOPER_NOTES_RU.md`, `docs/DEVELOPER_NOTES_EN.md` |
| Windows packaging | `tools/windows_packaging/README_WINDOWS_PACKAGING_RU.md`, `tools/windows_packaging/README_WINDOWS_PACKAGING_EN.md` |

## Verification

Run source-level checks before publishing:

```powershell
py tools\release_check.py --no-self-test
py tools\release_check.py --no-self-test --json
```

For portable ZIP publication, verify the release bundle contents and checksums as described in `docs/release/v69.6/public_handoff/SHA256_VERIFY_EN.txt` and `docs/release/v69.6/public_handoff/SHA256_VERIFY_RU.txt`.

## GitHub Pages

This repository includes a static project page in `docs/index.html`. In GitHub, enable Pages with:

- Source: `Deploy from a branch`
- Branch: `main`
- Folder: `/docs`

## License

This project is published under the MIT License. See `LICENSE`.
