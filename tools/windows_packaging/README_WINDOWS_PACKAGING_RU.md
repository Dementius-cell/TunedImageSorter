# Windows packaging — Tuned Image Sorter v69.6

`v69.6 / Этап 055` сохраняет подтверждённую CPU/GPU portable packaging baseline и добавляет first public polish / release identity pass. ML/pipeline/schema не меняются.

## Сборка CPU

```powershell
tools\windows_packaging\build_windows_gui.ps1 -Profile cpu -InstallRequirements
```

Ожидаемый результат:

```text
dist\windows\TunedImageSorter_CPU
dist\windows\TunedImageSorter_CPU_portable_v69_6.zip
```

CPU runtime должен быть чистым:

```text
onnxruntime==1.27.0
CUDAExecutionProvider отсутствует
onnxruntime-gpu не установлен
```

## Сборка GPU

```powershell
tools\windows_packaging\build_windows_gui.ps1 -Profile gpu -InstallRequirements
```

Ожидаемый результат:

```text
dist\windows\TunedImageSorter_GPU_FULL
dist\windows\TunedImageSorter_GPU_FULL_portable_v69_6.zip
```

GPU runtime должен быть pinned:

```text
onnxruntime-gpu==1.26.0
CUDAExecutionProvider виден
CUDA session smoke-test OK
bundled CUDA/cuDNN/cuBLAS runtime присутствует
```

## Full GPU portable

GPU ZIP остаётся full portable. Папка `_internal\nvidia` входит в пакет, поэтому первый запуск пользователя не должен скачивать NVIDIA runtime.

## Проверки

Сборочный скрипт выполняет:

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

В v69.6 дополнительно проверяются:

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

## Границы

Не менять в этом этапе: ML, распознавание лиц, clustering, ordinary Start, apply-names, pipeline stages, SQLite schema, project.json, CSV schemas, Review clusters backend, result-health backend, support-bundle backend, CPU/GPU packaging split, pinned GPU runtime и bundled CUDA runtime.


## v69.6 / Этап 055 — GPU Lite UI completion and small-set fallback polish

Короткий идентификатор этапа: `experimental_slim_gpu_package`.

Дополнительно к стабильным CPU/full GPU пакетам добавлен отдельный профиль `gpu-lite`:

```powershell
tools\windows_packaging\build_windows_gui.ps1 -Profile gpu-lite -InstallRequirements
```

Ожидаемый ZIP:

```text
TunedImageSorter_GPU_LITE_portable_v69_6.zip
```

GPU Lite не заменяет full GPU portable. Full GPU portable по-прежнему содержит `_internal\nvidia` и остаётся самым надёжным вариантом передачи пользователю.

GPU Lite при первом запуске проверяет NVIDIA driver и локальные CUDA 12 runtime DLLs. Если runtime отсутствует, пользователь получает запрос согласия. После согласия runtime скачивается и устанавливается в локальную папку пользователя, без изменения системного Python, драйверов и глобальных пакетов:

```text
%LOCALAPPDATA%\TunedImageSorter\gpu_lite_runtime\cuda12_ort126_v69_3_1
```

Диагностика GPU Lite:

```powershell
TunedImageSorter_CLI.exe --gpu-lite-runtime-status
TunedImageSorter_CLI.exe --gpu-lite-runtime-setup --yes
TunedImageSorter_CLI.exe --runtime-preflight --gpu
```

Запрещено менять ML, recognition, clustering, ordinary Start, apply-names, SQLite schema, project.json, CSV schemas, result-health, support-bundle и full GPU packaging contract в рамках GPU Lite эксперимента.

## v69.6 / Этап 055 — public release handoff docs

Дополнительно проверяются пользовательские файлы:

```text
PROFILE_GUIDE_RU.txt
PRIVACY_LOCAL_PROCESSING_RU.txt
KNOWN_LIMITATIONS_RU.txt
PUBLIC_RELEASE_NOTES_RU.txt
```

Этап не меняет ML/pipeline/schema/runtime split.


## v69.6 / Этап 055 — release bundle / checksums

После успешной сборки трёх ZIP можно создать единую папку релиза:

```powershell
py tools\windows_packaging\make_release_bundle.py
```

Ожидаемый результат:

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

Этот шаг не запускает ML, не сканирует фото и не меняет result-папки.
