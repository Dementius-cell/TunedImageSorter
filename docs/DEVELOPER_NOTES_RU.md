# Tuned Image Sorter v69.6 — заметки для разработчика

`v69.6 / Этап 055` — first public polish / release identity pass поверх подтверждённой `v69.3.1 / Этап 052` rebrand-базы.

## Назначение этапа

Короткий идентификатор этапа: `first public polish / release identity pass`.

Цель этапа — привести developer-facing и friend-ready документацию к согласованному состоянию перед передачей проекта другому разработчику или пользователю.

Изменения ограничены текстами, проверками наличия документов и проверками токенов. Поведение приложения не меняется.

## Что изменено в v69.6

- Добавлены `DOCS_I18N_HYGIENE_RU.txt` и `DOCS_I18N_HYGIENE_EN.txt`.
- Уточнены `docs/DEVELOPER_NOTES_RU.md` и `docs/DEVELOPER_NOTES_EN.md`.
- Уточнены `face_sorter_mvp/ARCHITECTURE_FOR_AGENTS.md` и package README.
- Удалены устаревшие ссылки на ранние этапы как на текущую базу.
- RU-документация приведена к русскому тексту, кроме технических имён команд, файлов, провайдеров и CLI-флагов.
- EN-документация приведена к единообразному `Stage 055`, кроме совместимых технических строк.
- Добавлен release-check guard `docs_i18n_hygiene_polish`.

## Разрешённый scope

В рамках этого этапа разрешены только:

- исправления README, HELP, USER_GUIDE, DEVELOPER_NOTES, ARCHITECTURE_FOR_AGENTS;
- уточнение friend-ready top-level документов;
- обновление VERSION/CHANGELOG;
- обновление статических проверок документации и токенов;
- переименование версии и ZIP-артефактов с `v69.0` на `v69.6`.

## Запрещено менять без отдельного решения

- ML и распознавание лиц;
- clustering;
- обычный `Start` / `mode=all`;
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

CPU и GPU остаются двумя профилями одной source-базы:

```text
TunedImageSorter_CPU: onnxruntime==1.27.0, CUDAExecutionProvider отсутствует
TunedImageSorter_GPU_FULL: onnxruntime-gpu==1.26.0, CUDAExecutionProvider виден, CUDA runtime bundled
```

GPU full portable остаётся самодостаточным: `_internal\nvidia` входит в ZIP, первый запуск пользователя не должен скачивать NVIDIA runtime.

## Технические строки, которые намеренно не переводятся

Не переводить:

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

Эти строки являются частью стабильного технического контракта, логов или CLI.

## Проверка

Минимальная source-проверка:

```powershell
tools\windows_packaging\build_windows_gui.ps1 -Profile cpu -InstallRequirements
tools\windows_packaging\build_windows_gui.ps1 -Profile gpu -InstallRequirements
```

Минимальный PASS:

```text
release-check OK
package_identity_check: OK
friend_ready_package: OK
zip_integrity: OK
```


## v69.6 / Этап 055 — GPU Lite experimental package

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
