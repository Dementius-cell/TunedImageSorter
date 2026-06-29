# Tuned Image Sorter v69.6

## v69.6 / Этап 055 — first public polish / release identity pass

`v69.6` — first public polish / release identity pass поверх подтверждённой `v69.3.1 / Этап 052` rebrand-базы.

Архитектура остаётся одной source-базой для двух Windows portable профилей:

```text
одна source-база v69.6
├─ CPU portable: onnxruntime==1.27.0, без CUDAExecutionProvider
└─ GPU full portable: pinned onnxruntime-gpu==1.26.0 + bundled CUDA 12 runtime
```

## Что изменено

- Добавлены `DOCS_I18N_HYGIENE_RU.txt` и `DOCS_I18N_HYGIENE_EN.txt`.
- Уточнены developer notes и architecture notes.
- Удалены устаревшие ссылки на ранние этапы как на текущую базу.
- RU/EN документация приведена к более согласованному виду.
- Добавлен release-check guard `docs_i18n_hygiene_polish`.

## Границы этапа

`v69.6` не меняет ML, распознавание лиц, pipeline, clustering, обычный Start, apply-names, SQLite schema, `project.json`, CSV schemas, Review clusters backend, result-health backend, support-bundle backend, CPU/GPU packaging split, pinned GPU runtime или bundled CUDA runtime.

## GPU full portable

GPU версия остаётся самодостаточной. Папка `_internal\nvidia` входит в ZIP, поэтому первый запуск пользователя не должен скачивать NVIDIA runtime.

## Проверка

```powershell
tools\windows_packaging\build_windows_gui.ps1 -Profile cpu -InstallRequirements
tools\windows_packaging\build_windows_gui.ps1 -Profile gpu -InstallRequirements
```

Ожидаемые ZIP:

```text
dist\windows\TunedImageSorter_CPU_portable_v69_6.zip
dist\windows\TunedImageSorter_GPU_FULL_portable_v69_6.zip
```


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

See also: `GPU_LITE_RU.txt`.
