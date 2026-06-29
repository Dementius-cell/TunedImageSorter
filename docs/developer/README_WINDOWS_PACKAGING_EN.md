# Windows packaging — Tuned Image Sorter v69.6

`v69.6 / Stage 055` preserves the confirmed CPU/GPU portable packaging baseline and adds first public polish / release identity pass. ML/pipeline/schema are unchanged.

## CPU build

```powershell
tools\windows_packaging\build_windows_gui.ps1 -Profile cpu -InstallRequirements
```

Expected result:

```text
dist\windows\TunedImageSorter_CPU
dist\windows\TunedImageSorter_CPU_portable_v69_6.zip
```

CPU runtime must be clean:

```text
onnxruntime==1.27.0
CUDAExecutionProvider absent
onnxruntime-gpu not installed
```

## GPU build

```powershell
tools\windows_packaging\build_windows_gui.ps1 -Profile gpu -InstallRequirements
```

Expected result:

```text
dist\windows\TunedImageSorter_GPU_FULL
dist\windows\TunedImageSorter_GPU_FULL_portable_v69_6.zip
```

GPU runtime must be pinned:

```text
onnxruntime-gpu==1.26.0
CUDAExecutionProvider visible
CUDA session smoke-test OK
bundled CUDA/cuDNN/cuBLAS runtime present
```

## Full GPU portable

The GPU ZIP remains full portable. The `_internal\nvidia` folder is included in the package, so the user's first launch should not download NVIDIA runtime files.

## Checks

The build script runs:

```text
compileall
file_ops self-test
smoke_test_packaging
friend-ready source verification
release-check
source CPU/GPU provider sanity
PyInstaller one-folder build
portable_manifest
package_identity_check
friend_ready_package
zip_integrity
```

## Docs/i18n hygiene

v69.6 additionally verifies:

```text
DOCS_I18N_HYGIENE_RU.txt
DOCS_I18N_HYGIENE_EN.txt
docs/DEVELOPER_NOTES_RU.md
docs/DEVELOPER_NOTES_EN.md
face_sorter_mvp/ARCHITECTURE_FOR_AGENTS.md
```

Guard:

```text
docs_i18n_hygiene_polish
```

## Boundaries

Do not change in this stage: ML, face recognition, clustering, ordinary Start, apply-names, pipeline stages, SQLite schema, project.json, CSV schemas, Review clusters backend, result-health backend, support-bundle backend, CPU/GPU packaging split, pinned GPU runtime and bundled CUDA runtime.


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

## v69.6 / Stage 055 — public release handoff docs

The following user-facing files are additionally verified:

```text
PROFILE_GUIDE_EN.txt
PRIVACY_LOCAL_PROCESSING_EN.txt
KNOWN_LIMITATIONS_EN.txt
PUBLIC_RELEASE_NOTES_EN.txt
```

This stage does not change ML/pipeline/schema/runtime split.


## v69.6 / Stage 055 — release bundle / checksums

After all three ZIP files have been built, create the single release folder:

```powershell
py tools\windows_packaging\make_release_bundle.py
```

Expected output:

```text
dist\windows\TunedImageSorter_v69_6_release\
  TunedImageSorter_CPU_portable_v69_6.zip
  TunedImageSorter_GPU_FULL_portable_v69_6.zip
  TunedImageSorter_GPU_LITE_portable_v69_6.zip
  SHA256SUMS.txt
  RELEASE_BUNDLE_MANIFEST.json
  WHICH_VERSION_TO_DOWNLOAD_RU.txt
  WHICH_VERSION_TO_DOWNLOAD_EN.txt
```

This step does not run ML, does not scan photos and does not change result folders.
