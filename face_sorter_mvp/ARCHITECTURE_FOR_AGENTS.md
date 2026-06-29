# Tuned Image Sorter v69.6 — Architecture Notes for AI Agents

Treat **v69.6 / Этап 055** as the current source baseline.

This is a first public polish / release identity pass on top of the user-confirmed **v69.3.1 / Этап 052 rebrand/package identity** base. It does not change runtime behavior.

```text
one source base v69.6
  ├─ TunedImageSorter_CPU
  └─ TunedImageSorter_GPU_FULL
```

## Current release contract

```text
version = v69.6
refactor_stage = Этап 055
ui_api_version = 21
```

The current stable release contains:

- no-console GUI launcher: `TunedImageSorter.exe`;
- console diagnostics launcher: `TunedImageSorter_CLI.exe`;
- CPU portable profile: `onnxruntime==1.27.0`, no `CUDAExecutionProvider`;
- GPU full portable profile: `onnxruntime-gpu==1.26.0`, `CUDAExecutionProvider` visible, bundled CUDA 12 runtime;
- friend-ready RU/EN documents;
- RC checklist, release gate, release freeze and docs/i18n hygiene documents;
- release/package verification through `release-check`, `package_identity_check`, `friend_ready_package` and `zip_integrity`.

## v69.6 scope

Allowed changes:

- documentation text cleanup;
- RU/EN consistency cleanup;
- developer notes cleanup;
- architecture notes cleanup;
- verification token updates for documentation files;
- version and ZIP artifact naming updates.

## Do not change without a separate decision

- ML algorithms;
- face recognition behavior;
- clustering;
- ordinary Start / `mode=all`;
- apply-names workflow;
- pipeline stage logic;
- CLI wizard behavior;
- `project.json`;
- resume/session formats except UI-only compatibility additions;
- report CSV schemas;
- bug-report/support-bundle backend;
- result-health backend;
- SQLite schema;
- output/result structure;
- Review clusters backend;
- CPU/GPU packaging split;
- pinned GPU runtime;
- bundled CUDA runtime.

## GPU packaging note

The current GPU package is a **Full GPU portable** build. It intentionally includes `_internal\nvidia` in the ZIP.

First launch should not download NVIDIA runtime files. Slim-GPU packaging, where runtime files are downloaded or installed separately, must be treated as a separate experimental stage and not mixed into this stable release line.

## Verification commands

Source checks:

```bash
python tools/windows_packaging/verify_friend_ready_package.py --source-root .
python tools/windows_packaging/smoke_test_packaging.py
python tools/release_check.py
```

Windows build checks:

```powershell
tools\windows_packaging\build_windows_gui.ps1 -Profile cpu -InstallRequirements
tools\windows_packaging\build_windows_gui.ps1 -Profile gpu -InstallRequirements
```

Expected Windows ZIP artifacts:

```text
dist\windows\TunedImageSorter_CPU_portable_v69_6.zip
dist\windows\TunedImageSorter_GPU_FULL_portable_v69_6.zip
```

Minimum PASS:

```text
release-check OK
package_identity_check: OK
friend_ready_package: OK
zip_integrity: OK
```


## v69.6 / Этап 055 — GPU Lite UI completion and small-set fallback polish

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
