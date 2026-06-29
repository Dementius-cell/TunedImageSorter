# Tuned Image Sorter v69.6

## v69.6 / Stage 055 — first public polish / release identity pass

`v69.6` is a first public polish / release identity pass on top of the confirmed `v69.3.1 / Stage 052` rebrand base.

The architecture remains one source base for two Windows portable profiles:

```text
one source base v69.6
├─ CPU portable: onnxruntime==1.27.0, no CUDAExecutionProvider
└─ GPU full portable: pinned onnxruntime-gpu==1.26.0 + bundled CUDA 12 runtime
```

## Changed

- Added `DOCS_I18N_HYGIENE_RU.txt` and `DOCS_I18N_HYGIENE_EN.txt`.
- Cleaned up developer notes and architecture notes.
- Removed stale references to earlier stages as the current baseline.
- Aligned RU/EN documentation more consistently.
- Added the release-check guard `docs_i18n_hygiene_polish`.

## Stage boundaries

`v69.6` does not change ML, face recognition, pipeline, clustering, ordinary Start, apply-names, SQLite schema, `project.json`, CSV schemas, Review clusters backend, result-health backend, support-bundle backend, CPU/GPU packaging split, pinned GPU runtime or bundled CUDA runtime.

## Full GPU portable

The GPU version remains self-contained. The `_internal\nvidia` folder is included in the ZIP, so the user's first launch should not download NVIDIA runtime files.

## Verification

```powershell
tools\windows_packaging\build_windows_gui.ps1 -Profile cpu -InstallRequirements
tools\windows_packaging\build_windows_gui.ps1 -Profile gpu -InstallRequirements
```

Expected ZIP files:

```text
dist\windows\TunedImageSorter_CPU_portable_v69_6.zip
dist\windows\TunedImageSorter_GPU_FULL_portable_v69_6.zip
```


## v69.6 / Stage 055 — GPU Lite UI completion and small-set fallback polish

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

See also: `GPU_LITE_EN.txt`.
