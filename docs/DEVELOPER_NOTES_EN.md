# Tuned Image Sorter v69.6 — developer notes

`v69.6 / Stage 055` is a first public polish / release identity pass on top of the confirmed `v69.3.1 / Stage 052` rebrand base.

## Purpose

Short stage identifier: `first public polish / release identity pass`.

The goal is to align developer-facing and friend-ready documentation before handing the project to another developer or user.

The patch is limited to text, documentation presence checks and token checks. Application behavior is unchanged.

## Changed in v69.6

- Added `DOCS_I18N_HYGIENE_RU.txt` and `DOCS_I18N_HYGIENE_EN.txt`.
- Cleaned up `docs/DEVELOPER_NOTES_RU.md` and `docs/DEVELOPER_NOTES_EN.md`.
- Cleaned up `face_sorter_mvp/ARCHITECTURE_FOR_AGENTS.md` and package README files.
- Removed stale references to earlier stages as the current baseline.
- Kept Russian documentation in Russian except for technical command, file, provider and CLI flag names.
- Kept English documentation consistent with `Stage 055` except for compatibility strings.
- Added the release-check guard `docs_i18n_hygiene_polish`.

## Allowed scope

This stage may only change:

- README, HELP, USER_GUIDE, DEVELOPER_NOTES and ARCHITECTURE_FOR_AGENTS text;
- friend-ready top-level documents;
- VERSION and CHANGELOG text;
- static documentation/token checks;
- version and ZIP artifact names from `v69.0` to `v69.6`.

## Do not change without a separate decision

- ML and face recognition;
- clustering;
- ordinary `Start` / `mode=all`;
- apply-names workflow;
- pipeline stages;
- SQLite schema;
- `project.json`;
- CSV schemas;
- Review clusters backend;
- result-health backend;
- support-bundle backend;
- CPU/GPU packaging split;
- pinned GPU runtime;
- bundled CUDA runtime.

## CPU/GPU packaging contract

CPU and GPU remain two profiles of one source base:

```text
TunedImageSorter_CPU: onnxruntime==1.27.0, CUDAExecutionProvider absent
TunedImageSorter_GPU_FULL: onnxruntime-gpu==1.26.0, CUDAExecutionProvider visible, CUDA runtime bundled
```

The full GPU portable package remains self-contained: `_internal\nvidia` is included in the ZIP, and the user's first launch should not download NVIDIA runtime files.

## Technical strings intentionally not translated

Do not translate:

- `TunedImageSorter.exe`
- `TunedImageSorter_CLI.exe`
- `CUDAExecutionProvider`
- `CPUExecutionProvider`
- `onnxruntime`
- `onnxruntime-gpu`
- `package_identity_check`
- `friend_ready_package`
- `zip_integrity`
- `support-bundle`
- `result-health`
- `problem_files.csv`
- `review_decisions.csv`
- `project.json`

These strings are part of the stable technical contract, logs or CLI.

## Verification

Minimum Windows verification:

```powershell
tools\windows_packaging\build_windows_gui.ps1 -Profile cpu -InstallRequirements
tools\windows_packaging\build_windows_gui.ps1 -Profile gpu -InstallRequirements
```

Minimum PASS:

```text
release-check OK
package_identity_check: OK
friend_ready_package: OK
zip_integrity: OK
```


## v69.6 / Stage 055 — GPU Lite experimental package

Short stage identifier: `experimental_slim_gpu_package`.

In addition to the stable CPU/full GPU packages, v69.6 adds a separate `gpu-lite` profile:

```powershell
tools\windows_packaging\build_windows_gui.ps1 -Profile gpu-lite -InstallRequirements
```

Expected ZIP:

```text
TunedImageSorter_GPU_LITE_portable_v69_6.zip
```

GPU Lite does not replace the full GPU portable package. The full GPU portable package still bundles `_internal\nvidia` and remains the most reliable handoff option.

On first run, GPU Lite checks the NVIDIA driver and local CUDA 12 runtime DLLs. If runtime files are missing, the user is asked for consent. After consent, the runtime is downloaded and installed into a local user folder without changing system Python, drivers or global packages:

```text
%LOCALAPPDATA%\TunedImageSorter\gpu_lite_runtime\cuda12_ort126_v69_3_1
```

GPU Lite diagnostics:

```powershell
TunedImageSorter_CLI.exe --gpu-lite-runtime-status
TunedImageSorter_CLI.exe --gpu-lite-runtime-setup --yes
TunedImageSorter_CLI.exe --runtime-preflight --gpu
```

Do not change ML, recognition, clustering, ordinary Start, apply-names, SQLite schema, project.json, CSV schemas, result-health, support-bundle or the full GPU packaging contract as part of the GPU Lite experiment.
