# Changelog

## v69.6 / Этап 055 — release bundle / checksums / final public handoff

Packaging-only public handoff layer on top of confirmed `v69.5 / Этап 054`.

- Added `RELEASE_BUNDLE_RU.txt` and `RELEASE_BUNDLE_EN.txt` with final release-folder instructions.
- Added `WHICH_VERSION_TO_DOWNLOAD_RU.txt` and `WHICH_VERSION_TO_DOWNLOAD_EN.txt` for CPU / GPU_FULL / GPU_LITE selection.
- Added `tools/windows_packaging/make_release_bundle.py`, which copies the three already-built portable ZIP files into `dist/windows/TunedImageSorter_v69_6_release`, writes `SHA256SUMS.txt` and writes `RELEASE_BUNDLE_MANIFEST.json`.
- Aligned package identity, friend-ready verification and release-check guards with `v69.6 / Этап 055` and ZIP names `TunedImageSorter_*_portable_v69_6.zip`.
- Kept the internal Python package name `face_sorter_mvp` unchanged.
- Kept ML/recognition, clustering, ordinary Start pipeline, apply-names, SQLite/project.json/CSV schemas, result-health, support-bundle, CPU/GPU_FULL/GPU_LITE split and GPU Lite runtime setup logic unchanged.
- Known non-blocking issue remains documented: `reports` may not auto-open after an ordinary Start run.

## v69.5 / Этап 054 — packaging hotfix

- Fixed Windows portable packaging copy list: `PROFILE_GUIDE_RU/EN.txt`, `PRIVACY_LOCAL_PROCESSING_RU/EN.txt`, `KNOWN_LIMITATIONS_RU/EN.txt` and `PUBLIC_RELEASE_NOTES_RU/EN.txt` are now copied into built `TunedImageSorter_*` portable folders before friend-ready package verification.
- Aligned `package_identity_report.py` required-doc list with the v69.5 public release handoff docs.
- Runtime behavior is unchanged: ML, clustering, ordinary Start, apply-names, schemas, result-health, support-bundle and CPU/GPU_FULL/GPU_LITE split were not changed.

## v69.5 / Этап 054 — public release handoff / profile guide / privacy / known limitations polish

Safe documentation and release-handoff polish on top of confirmed `v69.4 / Этап 053`.

- Added `PROFILE_GUIDE_RU.txt` and `PROFILE_GUIDE_EN.txt` to explain CPU / GPU_FULL / GPU_LITE selection.
- Added `PRIVACY_LOCAL_PROCESSING_RU.txt` and `PRIVACY_LOCAL_PROCESSING_EN.txt` for local-processing and support-bundle privacy expectations.
- Added `KNOWN_LIMITATIONS_RU.txt` and `KNOWN_LIMITATIONS_EN.txt`, including the known non-blocking issue where `reports` may not auto-open after the ordinary Start button run.
- Added `PUBLIC_RELEASE_NOTES_RU.txt` and `PUBLIC_RELEASE_NOTES_EN.txt` as a short handoff note for the first public portable package.
- Aligned version/stage/package identity expectations to `v69.5 / Этап 054` and ZIP names to `TunedImageSorter_*_portable_v69_5.zip`.
- Kept the internal Python package name `face_sorter_mvp` unchanged.
- Kept ML/recognition, clustering, ordinary Start pipeline, apply-names, SQLite/project.json/CSV schemas, result-health, support-bundle, CPU/GPU_FULL/GPU_LITE split and GPU Lite runtime setup logic unchanged.
- GPU Lite runtime cache remains `%LOCALAPPDATA%\TunedImageSorter\gpu_lite_runtime\cuda12_ort126_v69_3_1` because the pinned runtime stack did not change.

## v69.4 / Этап 053 — first public polish / release identity pass

Confirmed on Windows as a pre-release polish base. Known non-blocking UX issue: after a run started with the Start button, the `reports` folder may not auto-open; the UI buttons can still open result/reports manually.

- Bumped source/package identity to `v69.4 / Этап 053`.
- Aligned friend-ready docs, release gate, RC checklist, package identity report and portable manifest expectations with the new version.
- Added `PRE_RELEASE_POLISH_RU.txt` and `PRE_RELEASE_POLISH_EN.txt` as a short final human QA checklist before sharing the portable packages.
- Kept the internal Python package name `face_sorter_mvp` unchanged.
- Kept ML/recognition, clustering, ordinary Start pipeline, apply-names, SQLite/project.json/CSV schemas, result-health, support-bundle, CPU/GPU_FULL/GPU_LITE split and GPU Lite runtime setup logic unchanged.

## v69.3.1 / Этап 052 — product rename / package identity rebrand


- Public product name changed to **Tuned Image Sorter**.
- User-facing launchers renamed to `TunedImageSorter.exe` and `TunedImageSorter_CLI.exe`.
- Portable folders/ZIPs now use `TunedImageSorter_CPU`, `TunedImageSorter_GPU_FULL` and `TunedImageSorter_GPU_LITE`.
- Added `PRODUCT_RENAME_RU.txt` and `PRODUCT_RENAME_EN.txt`.
- Internal Python package remains `face_sorter_mvp` to reduce regression risk.
- GPU Lite uses `%LOCALAPPDATA%\TunedImageSorter\gpu_lite_runtime\cuda12_ort126_v69_3_1` as the primary cache path and keeps a compatibility fallback for pre-rename `FaceSorterMVP` caches.
- Added release-check guard `product_rename_package_identity`.
- Закреплены три официальных portable-профиля: CPU, GPU_FULL и GPU_LITE.
- Full GPU artifact теперь явно называется `TunedImageSorter_GPU_FULL_portable_v69_3_1.zip`; старый профиль `-Profile gpu` сохранён как совместимый способ собрать full GPU, добавлен alias `-Profile gpu-full`.
- GPU Lite artifact остаётся отдельным: `TunedImageSorter_GPU_LITE_portable_v69_3_1.zip`; он не заменяет full GPU portable.
- Добавлены `DUAL_GPU_PACKAGING_RU.txt` и `DUAL_GPU_PACKAGING_EN.txt` с матрицей выбора CPU/GPU_FULL/GPU_LITE и release verification matrix.
- `portable_manifest.json`, `package_identity_check`, friend-ready verification и ZIP integrity теперь проверяют новые docs и финальные имена ZIP.
- Добавлен release-check guard `dual_gpu_packaging_release_docs`.
- ML, recognition, clustering, ordinary Start, apply-names, SQLite schema, project.json, CSV schemas, result-health/support-bundle backend и GPU Lite runtime setup behavior не менялись.

## v69.1 / Этап 050 — experimental slim GPU package

- Added a separate experimental packaging profile `gpu-lite`; it does not replace stable CPU portable or stable full GPU portable.
- New expected ZIP: `TunedImageSorter_GPU_LITE_portable_v69_1.zip`.
- Full GPU portable can still be built separately and contains `_internal\nvidia`; GPU Lite removes bundled NVIDIA runtime from `_internal\nvidia`.
- Added first-run bootstrap `face_sorter_mvp/core/gpu_lite_runtime.py`: NVIDIA driver / `nvidia-smi` check, CUDA 12 runtime DLL check, explicit user consent and local runtime setup under `%LOCALAPPDATA%\TunedImageSorter\gpu_lite_runtime\cuda12_ort126_v69_1`.
- Added CLI diagnostics: `--gpu-lite-runtime-status` and `--gpu-lite-runtime-setup --yes`.
- Added `GPU_LITE_RU.txt` and `GPU_LITE_EN.txt` next to the portable EXE.
- Superseded by v69.3.1 for Windows GPU Lite packaging because v69.1 used the shared GPU collect folder name.

## v69.0.1 / Этап 049 — first public polish / release identity pass

- Added `DOCS_I18N_HYGIENE_RU.txt` and `DOCS_I18N_HYGIENE_EN.txt` next to the portable EXE.
- Cleaned developer-facing notes and RU/EN documentation consistency.
- Added release-check guard `docs_i18n_hygiene_polish`.
- Stable CPU/full GPU release-freeze baseline remains unchanged.

## v68.6 / Этап 047 — friend-ready README / quick start / troubleshooting polish

- Добавлены `QUICK_START_RU.txt` и `QUICK_START_EN.txt` рядом с portable EXE.
- Добавлены `TROUBLESHOOTING_RU.txt` и `TROUBLESHOOTING_EN.txt` рядом с portable EXE.
- `START_HERE_RU/EN.txt` и `README_RU/EN.txt` теперь явно ведут обычного пользователя по файлам пакета.
- Package/source/ZIP verification проверяет QUICK_START и TROUBLESHOOTING docs.
- Добавлен release-check guard `friend_ready_quick_start_troubleshooting`.
- ML, recognition, clustering, ordinary Start, apply-names, pipeline stages, SQLite schema, project.json, CSV schemas, result-health/support-bundle backend, CPU/GPU split и pinned GPU runtime не менялись.


## v68.5 / Этап 046 — human-readable errors polish

- Добавлен UX-слой понятных ошибок для раздела `Статус / ошибки`: каждое UI status issue получает короткое объяснение `Что это значит` / `Meaning` и `Что сделать` / `Action`.
- Новый import-safe helper в `core/status.py`: `human_error_guidance()`, `humanize_issue()`, `humanize_status_report()` и `build_error_guidance_text()`.
- GUI теперь применяет `humanize_status_report()` перед отображением status report; полный traceback остаётся в diagnostics/bug-report, а основной UI показывает безопасное краткое объяснение.
- Добавлены friend-ready docs `ERRORS_RU.txt` и `ERRORS_EN.txt` рядом с portable EXE.
- `Copy-FriendReadyDocs`, `verify_friend_ready_package.py`, `package_identity_report.py`, `verify_friend_ready_source_layout()` и ZIP integrity теперь проверяют ERRORS файлы.
- `release-check` получил source-level guard `human_readable_errors`.
- ML, распознавание лиц, clustering, ordinary Start, pipeline stages, SQLite schema, `project.json`, resume, report CSV schemas, Review clusters/apply-names backend, result-health/support-bundle backend, CPU/GPU packaging split и pinned GPU runtime не менялись.

## v68.3 / Этап 044 — package identity report polish

- Добавлен статический отчёт идентичности portable-пакета: `package_identity_check.json` и `package_identity_check.txt` рядом с `TunedImageSorter.exe`.
- Новый helper `tools/windows_packaging/package_identity_report.py` проверяет `portable_manifest.json`, launchers, friend-ready docs, CPU/GPU profile expectations и guard `ordinary Start must run mode=all, not apply-names`.
- `build_windows_gui.ps1` создаёт package identity report до friend-ready package/zip verification.
- `verify_friend_ready_package.py` проверяет package identity report в built package и portable ZIP; JSON output больше не печатается дважды при `--json`.
- `release-check` и source packaging guards обновлены под v68.3 / Этап 044.
- ML, распознавание лиц, clustering, ordinary Start, pipeline stages, SQLite schema, `project.json`, resume, report CSV schemas, Review clusters/apply-names backend, result-health/support-bundle backend, CPU/GPU packaging split и pinned GPU runtime не менялись.

## v68.2 / Этап 043 — portable manifest / package identity polish

- Добавлен `portable_manifest.json` в каждую собранную portable-папку CPU/GPU.
- Manifest фиксирует `version`, `refactor_stage`, `ui_api_version`, `profile`, launchers, diagnostic commands и runtime expectations для CPU/GPU.
- Исправлена генерация `portable_manifest.json` в Windows PowerShell 5.1: поле `refactor_stage` больше не должно превращаться в mojibake `Р­С‚Р°Рї 043`.
- `build_windows_gui.ps1` автоматически создаёт manifest после копирования friend-ready docs и до package/zip verification.
- `verify_friend_ready_package.py` проверяет manifest в built package и внутри portable ZIP, а также проверяет, что ZIP содержит один top-level package folder с `TunedImageSorter.exe`, `TunedImageSorter_CLI.exe`, `_internal`, docs и manifest.
- `release-check` получил source/frozen guards для manifest-пути.
- ML, распознавание лиц, clustering, ordinary Start, pipeline stages, SQLite schema, `project.json`, resume и CSV schemas не менялись.

## v68.1 packaging hotfix — portable ZIP default

- `tools/windows_packaging/build_windows_gui.ps1` creates `TunedImageSorter_CPU_portable_v68_1.zip` / `TunedImageSorter_GPU_portable_v68_1.zip` by default next to the built one-folder package.
- `-ZipOutput` remains accepted for backward compatibility.
- Added `-NoZipOutput` for explicit local debug builds without archive creation.
- No ML, pipeline, CSV, SQLite, project.json, resume, result-health, support-bundle or CPU/GPU runtime changes.

## v68.1 / Этап 042 — UX polish: run history / recent results / clearer post-run actions

- Улучшен GUI-раздел `Продолжение / recent`: таблица теперь показывает профиль, CPU/GPU runtime и краткие состояния result-папки, а выбранный recent/result получил быстрые действия для `reports`, `diagnostics`, `bug_reports`, `final` и `final_review`.
- В `Итог запуска` добавлен post-run блок быстрых действий: открыть `people`, `review`, `reports`, `diagnostics`, `bug_reports`, последний support-bundle ZIP, `final` и `final_review`.
- Итог запуска теперь явно объясняет нормальные отсутствующие состояния: `final` появляется после `apply-names`, `final_review` может отсутствовать без action=review, `problem_files.csv` может отсутствовать без проблемных файлов, `review_decisions.csv` появляется после сохранения решений Review clusters.
- После `Сохранить names.csv` UI подсказывает следующий шаг — применить имена для создания `final/final_review`; обычный `Старт` по-прежнему защищён от stale `mode=apply-names`.
- Support-bundle UX уточнён через post-run actions: отображается путь к последнему ZIP и сохраняется пояснение, что support-bundle не содержит исходные фото/embeddings.
- Добавлен source-level release guard для run history / post-run actions UI.
- ML, распознавание лиц, кластеризация, pipeline stage logic, SQLite schema, `project.json`, resume, support-bundle/result-health backend, CSV schemas, CPU/GPU packaging split и pinned GPU runtime не менялись.

## v68.0 / Этап 041 — UX/diagnostics polish

- GUI `Диагностика / Support` теперь показывает diagnostic summary блоками: runtime, CPU runtime, GPU runtime, result-health, support-bundle и optional warnings.
- Для frozen GPU добавлено пояснение: package metadata `onnxruntime-gpu` может быть недоступна, если `CUDAExecutionProvider` реально виден и работает.
- CPU source sanity больше не выводит косметический `MISMATCH` по pinned GPU runtime, когда `onnxruntime-gpu` в CPU profile ожидаемо отсутствует.
- Result-health в GUI объясняет optional warnings: `review_decisions.csv`, `problem_files.csv`, `final`, `final_review`, `bug_reports` могут отсутствовать в нормальных workflow.
- TensorRT DLL warnings в GPU PyInstaller output явно отмечены как optional, если CUDAExecutionProvider работает.
- ML, recognition, clustering, pipeline stage logic, SQLite schema, `project.json`, resume и report CSV formats не менялись.

## v67.9.2 / Этап 040 — CPU build ORT cleanup hotfix

- CPU packaging now removes both `onnxruntime-gpu` and `onnxruntime` before force-reinstalling the CPU `onnxruntime` wheel.
- Added CPU source/frozen guards: CPU builds must not expose `CUDAExecutionProvider` and must not bundle `onnxruntime_providers_cuda.dll` / `onnxruntime_providers_tensorrt.dll`.
- Fixed compact preflight summary so CPU frozen builds are no longer mislabeled as `onnxruntime-gpu` only because the shared `onnxruntime` module imports successfully.
- Scope remains packaging/diagnostics-only; ML, pipeline, reports, SQLite and apply-names behavior are unchanged.

## v67.9.2 / Этап 040 — GPU build ORT reinstall hotfix

- Исправлен GPU build в повторно используемом Python окружении: `build_windows_gui.ps1 -Profile gpu -InstallRequirements` теперь удаляет `onnxruntime` и `onnxruntime-gpu`, затем принудительно переустанавливает pinned `onnxruntime-gpu==1.26.0` с CUDA 12 runtime pins.
- Добавлен более явный guard для повреждённого `onnxruntime` module state, где metadata `onnxruntime-gpu` присутствует, но `onnxruntime.get_available_providers()` отсутствует.
- ML, pipeline, clustering, reports formats, apply-names workflow и GUI diagnostics/support panel не менялись.

## v67.9.2 / Этап 040 — GUI diagnostics/support panel polish

- Добавлен отдельный GUI-раздел `Диагностика / Support` в левую навигацию.
- В разделе собраны безопасные действия: `Проверка окружения`, `Проверка результата`, `Создать support-bundle`, открыть `reports`, открыть `bug_reports`, открыть `diagnostics`, открыть последний ZIP и скопировать короткую diagnostic summary.
- `Проверка результата` вызывает существующий `core.result_health.build_result_health_summary(..., write_reports=True)` и создаёт только дополнительные `reports/result_health_check.json` / `reports/result_health_check.txt`.
- `Создать support-bundle` использует существующий bug-report/support-bundle API, не создавая параллельный механизм диагностики.
- `release_check` получил source-level guard `gui_diagnostics_support_panel`, который проверяет наличие GUI-кнопок и привязку к существующим helpers.
- Guard против регрессии `v66.6` сохранён: обычный `Старт` не запускает `apply-names`; `apply-names` остаётся отдельным действием Review clusters / Имена.
- GPU pinned runtime guard из `v67.8.4` сохранён: нельзя подтягивать latest `onnxruntime-gpu` / CUDA wheels.
- No ML, clustering, ordinary pipeline stage logic, SQLite schema, project/resume, existing report CSV schemas, Review clusters/apply-names backend workflow or output/result structure changes.

## v67.8.4 / Этап 039-hotfix — deterministic GPU install pip-check guard

- Исправлена регрессия `v67.8`: GPU build мог подтянуть свежие `onnxruntime-gpu` / NVIDIA CUDA wheel packages во время `-InstallRequirements` и собрать CUDA runtime, несовместимый с portable CUDA 12 profile.
- `requirements-windows-gpu-cu12.txt` теперь жёстко фиксирует проверенную GPU runtime связку: `onnxruntime-gpu==1.26.0`, `nvidia-cudnn-cu12==9.23.1.3` и остальные CUDA 12 wheel versions.
- `build_windows_gui.ps1 -Profile gpu -InstallRequirements` теперь переустанавливает именно pinned GPU runtime versions, а не latest packages.
- GPU install допускает только известное metadata-предупреждение `insightface requires onnxruntime`, потому что runtime-модуль предоставляет `onnxruntime-gpu`; остальные `pip check` ошибки остаются блокирующими.
- `check_onnxruntime_provider.py` получил guard `--require-pinned-gpu-runtime` и CUDA session smoke-test `--require-cuda-session`, чтобы provider list без реально загруженных CUDA DLL больше не считался достаточной проверкой.
- Подтверждённая `v67.7 / Этап 038` база и `v67.8` diagnostics command center сохранены.
- No ML, clustering, ordinary Start, pipeline stage logic, SQLite schema, project/resume, Review clusters/apply-names, CSV schema or output/result structure changes.

## v67.6 / Этап 037 — support-bundle + result-health integration polish

- Подтверждённая `v67.5.3 / Этап 036` result-health база сохранена.
- `--support-bundle --output <result>` теперь автоматически запускает lightweight result-health для указанной папки результата перед созданием ZIP.
- В support-bundle ZIP добавляются `output/reports/result_health_check.json` и `output/reports/result_health_check.txt`, если известна и доступна output/result папка.
- `system_info.json` внутри support-bundle содержит `result_health_summary`.
- `support_bundle_manifest.json` содержит флаг `includes_result_health_check`.
- Friend-ready docs и support-bundle README обновлены: пользователю достаточно отправить один ZIP, отдельный `--result-health` остаётся доступен для быстрой проверки.
- Source-level packaging verification проверяет, что support-bundle не потерял result-health интеграцию.
- ML, clustering, pipeline stage logic, CLI wizard, SQLite schema, project/resume formats, существующие report CSV formats, Review clusters/apply-names и output/result structure не менялись.

## v67.5.3 / Этап 036-hotfix2 — Windows CLI Cyrillic encoding fix

- Исправлен mojibake в `TunedImageSorter_CLI.exe --result-health` на Windows Terminal / PowerShell: frozen CLI использует ASCII-safe English console output для diagnostics-команд.
- Для console-friendly вывода `result-health` заменены длинные Unicode-разделители на обычный ASCII `-`; UTF-8 report files остаются полноценными.
- Добавлен source-level packaging guard для CLI launcher.
- ML, clustering, pipeline, reports CSV schema, Review clusters/apply-names, support-bundle и output/result structure не менялись.

## v67.5 / Этап 036 — result health-check diagnostics polish

- Подтверждённая `v67.4 / Этап 035` support-bundle база сохранена.
- Добавлена диагностика существующей папки результата без повторной сортировки:
  - `TunedImageSorter_CLI.exe --result-health --output <result>`;
  - `TunedImageSorter_CLI.exe --mode result-health --output <result>`.
- Health-check проверяет наличие ключевых файлов/папок результата: `project.json`, `reports/summary.csv`, `reports/assignments.csv`, `reports/review_clusters.csv`, optional `names.csv`, `review_decisions.csv`, `problem_files.csv`, `diagnostics`, `database/faces.sqlite`, `people`, `review`, `final`, `final_review`, `bug_reports`.
- Команда создаёт только дополнительные диагностические файлы `reports/result_health_check.json` и `reports/result_health_check.txt`.
- Release-check выполняет import-safe smoke-test result-health слоя.
- Friend-ready README/START_HERE/SUPPORT_BUNDLE инструкции обновлены командой `--result-health`.
- ML, clustering, pipeline stage logic, CLI wizard, SQLite schema, project/resume formats, существующие report CSV formats, Review clusters/apply-names и output/result structure не менялись.

## v67.3 / Этап 034 — friend-ready portable package polish

- Добавлены top-level portable-инструкции `START_HERE_RU.txt`, `START_HERE_EN.txt`, `README_RU.txt`, `README_EN.txt`, `VERSION.txt` для CPU/GPU one-folder пакетов.
- Windows build script теперь копирует friend-ready docs рядом с `TunedImageSorter.exe` и `TunedImageSorter_CLI.exe` после PyInstaller build.
- Добавлена import-safe verification-команда `tools/windows_packaging/verify_friend_ready_package.py` для проверки source layout, built package layout и portable zip integrity.
- `release_check` и packaging smoke-test теперь проверяют friend-ready source layout.
- Scope остаётся packaging/docs/verification-only: ML, clustering, pipeline, SQLite, reports, resume/project formats и Review clusters/apply-names workflow не менялись.

## v67.2.2 / Этап 033-hotfix2 — no-console polish and apply-names final open

- Убраны дополнительные источники кратковременных terminal flashes в windowed GUI: captured subprocess diagnostics теперь используют Windows `CREATE_NO_WINDOW`, а UI open-file/open-folder actions используют `ShellExecuteW` на Windows.
- После успешного `apply-names` при включённом auto-open теперь открывается `final/`, а не `reports/`.
- Не менялись ML, pipeline, clustering, reports/schema/output formats, CPU/GPU source architecture и Review clusters/apply-names backend workflow.

## v67.2.1 / Этап 033-hotfix — CPU GUI no-console stdio safeguard

- Исправлена регрессия `v67.2.2` в CPU GUI/no-console build: при запуске `TunedImageSorter.exe` без консоли `sys.stdout`/`sys.stderr` могут быть `None`, из-за чего CPU inline scan/tqdm падал с `AttributeError: 'NoneType' object has no attribute 'write'`.
- Добавлен безопасный `NullTextStream` и `ensure_non_null_stdio()` для windowed PyInstaller GUI-процесса.
- PyInstaller GUI entry теперь подставляет безопасные stdout/stderr sinks перед запуском UI, не открывая чёрное консольное окно.
- Backend pipeline вызывает stdio safeguard перед job, чтобы GUI-запуск не зависел от наличия console streams.
- Добавлен self-test `windowed_stdio_safeguard` и source-level packaging guard.
- GPU path, CLI diagnostics launcher, ML, pipeline logic, reports formats, schema, Review clusters / apply-names и output/result structure не менялись.

## v67.2 / Этап 033 — Windows GUI no-console launcher / CLI diagnostics split

- Подтверждённая `v67.1 / Этап 032` CPU/GPU база сохранена.
- `TunedImageSorter.exe` в CPU/GPU PyInstaller specs переключён на `console=False`, чтобы запуск из проводника открывал только GUI.
- В ту же one-folder папку добавлен `TunedImageSorter_CLI.exe` с `console=True` для диагностики.
- Build script теперь проверяет наличие обоих launchers после сборки.
- GPU frozen provider verification переведён на `TunedImageSorter_CLI.exe --runtime-preflight --gpu`, чтобы diagnostic output оставался видимым и пригодным для JSON extraction.
- `verify_windows_packaging()` добавил source-level guard: CPU/GPU specs должны содержать GUI no-console launcher и CLI diagnostics launcher.
- ML, clustering, pipeline stage logic, CLI wizard, SQLite schema, project/resume, reports formats, bug-report formats, Review clusters / apply-names workflow и output/result structure не менялись.
- CPU/GPU source/build profile architecture сохранена.

## v67.0 / Этап 031 — stability safeguards / problem files UX

- Подтверждённая `v66.9 / Этап 030` CPU/GPU база сохранена: обычный `Старт` остаётся обычным pipeline, apply-names запускается только отдельными кнопками Review clusters / apply-names.
- В `Отчёты / review` добавлен read-only раздел `Проблемные файлы` для `reports/problem_files.csv`.
- Отсутствие `problem_files.csv` после успешного прогона объясняется как нормальное состояние: проблемные файлы не зафиксированы.
- Существующие строки `problem_files.csv` группируются в UI без изменения CSV schema: unsupported format, read/open error, decode error / broken image, timeout, internal worker error, other.
- Добавлены кнопки открытия `problem_files.csv`, disabled/missing tooltips и problem-files summary в `Итог запуска` и clipboard-сводку отчётов.
- Worker timeout logic не переписывалась: существующая защита и запись timeout в `problem_files.csv` сохранены.
- ML, clustering, pipeline stage logic, CLI wizard, SQLite schema, project/resume, reports formats, bug-report formats и output/result structure не менялись.
- CPU/GPU PyInstaller profiles сохранены.

## v66.9 / Этап 030 — Review clusters / apply-names guidance polish

- Подтверждённая `v66.8 / Этап 030` база сохранена: `review_decisions.csv` UX работает корректно, обычный CPU/GPU прогон фото не сломан.
- В `Отчёты / review` → `Review clusters` добавлена короткая памятка по workflow:
  - `keep + Name` создаёт именованную final-папку;
  - `keep` без `Name` не создаёт именованную папку;
  - `merge` требует `Merge into` с целевым `cluster_key`;
  - `review` отправляет кластер в `final_review`;
  - `ignore` исключает кластер из применения имени.
- Добавлен live-status Review workflow: количество строк и действий `keep/merge/review/ignore`, состояние `names.csv` и `review_decisions.csv`, предупреждения про `keep` без `Name` и `merge` без `Merge into`.
- В таблице Review clusters добавлены tooltip-подсказки для `Action`, `Name`, `Merge into`, `Notes`.
- Раздел `Имена / apply-names` получил более точное объяснение: apply-names не пересканирует фото, а создаёт `final/final_review` из существующих `assignments.csv + names.csv`.
- ML, clustering, pipeline stage logic, CLI wizard, SQLite schema, project/resume, reports formats, bug-report formats и output/result structure не менялись.
- CPU/GPU PyInstaller profiles сохранены.



## v66.8 / Этап 030 — review_decisions/report files UX clarification

- Подтверждённая `v66.7 / Этап 029` hotfix-база сохранена: обычный CPU/GPU прогон сортирует фото корректно.
- В `Отчёты / review` → `Файлы отчётов` статус файлов стал яснее: `есть`, `отсутствует`, `не создан`.
- Для `review_decisions.csv` явно показано, что файл не обязан создаваться после обычной сортировки и появляется после `Сохранить names.csv` или `Применить имена из Review clusters`.
- Кнопки отсутствующих report files остаются disabled; двойной клик/открытие отсутствующей строки показывает понятную причину вместо попытки открыть путь.
- Clipboard-сводка отчётов теперь включает причину отсутствия optional report files.
- В `Review clusters` добавлена подсказка о моменте создания `reports/review_decisions.csv`.
- ML, clustering, pipeline stage logic, CLI wizard, SQLite schema, project/resume, reports formats, bug-report formats и output/result structure не менялись.
- CPU/GPU PyInstaller profiles сохранены.

## v66.6 / Этап 029 — review clusters workflow UX polish

- Подтверждённая `v66.5 / Этап 028` global left-navigation UI shell база сохранена: левая навигация работает, правый workspace переключается, CPU/GPU прогон фото не сломан.
- После нажатия `Старт` UI автоматически переключается в раздел `Ход выполнения`.
- В `Отчёты / review` → `Review clusters` добавлено пояснение к столбцу `Action`:
  - `keep` — оставить кластер как есть;
  - `merge` — объединить с кластером из `Merge into`;
  - `review` — отправить в ручную проверку/final_review;
  - `ignore` — не применять имя к кластеру.
- В разделе `Review clusters` добавлены кнопки `Сохранить names.csv` и `Применить имена из Review clusters`, чтобы применять решения не только из `Имена / apply-names`.
- Preview thumbnails в `Review clusters` переведены с одной горизонтальной линии на адаптивную сетку по ширине доступной области с сохранением прокрутки.
- ML, clustering, pipeline stage logic, CLI wizard, SQLite schema, project/resume, reports formats, bug-report formats и output/result structure не менялись.
- CPU/GPU PyInstaller profiles сохранены.

## v66.4 / Этап 027 — reports/review navigation UX polish

- Подтверждённая `v66.3 / Этап 027` reports UI база сохранена: CPU/GPU прогон фото не сломан, `Открыть diagnostics` работает корректно.
- Вкладка `Отчёты / review` переведена с плотной одноэкранной раскладки на двухпанельную схему:
  - слева — навигация по разделам;
  - справа — рабочая область выбранного раздела.
- Добавлены разделы навигации:
  - `Обзор`;
  - `Файлы отчётов`;
  - `Review clusters`;
  - `Имена / apply-names`;
  - `Папки результата`.
- Быстрые кнопки report files больше не сливаются в одну длинную строку: они находятся в разделе `Файлы отчётов`.
- Кнопка выбранного report file теперь подписана яснее: `Открыть выбранный файл/папку`.
- Кнопка clipboard-сводки в reports UI подписана как `Копировать сводку отчётов`.
- Документация и version labels обновлены под `v66.4 / Этап 027`.

Не менялось: ML, clustering, pipeline stage logic, CLI wizard, `project.json`, resume, SQLite schema, bug-report formats, reports formats и структура output/result.

## v66.3 / Этап 027 — reports/diagnostics UI viewer polish

- Подтверждённая `v66.2 / Этап 026` onboarding-база сохранена.
- Расширена вкладка `Отчёты / review` без изменения форматов reports:
  - быстрые кнопки открытия `summary.csv`, `assignments.csv`, `clusters.html`, `duplicates.csv`, `review_clusters.csv`, `names.csv`, `review_decisions.csv`;
  - кнопки `Открыть reports`, `Открыть diagnostics`, `Открыть выбранный`;
  - двойной клик по строке таблицы report files открывает выбранный файл/папку;
  - кнопка `Копировать сводку отчётов` копирует пути и счётчики reports/review.
- В summary вкладки reports добавлены счётчики строк `summary.csv`, `assignments.csv`, `review_clusters.csv`, `duplicates.csv`, `problem_files.csv`.
- `ReviewUiSnapshot` теперь показывает `duplicates.csv` и `reports/diagnostics` в существующей UI-таблице report files.

## v66.2 / Этап 026 — first-run onboarding polish

- Добавлен динамический first-run checklist на стартовом экране: input, output, проверка окружения, CPU/GPU режим и быстрый тест.
- Добавлена кнопка `Быстрый тест` с памяткой для проверки 20–50 фото в отдельной result-папке.
- Улучшено предупреждение, если output/result находится внутри input.
- CPU/GPU status и onboarding checklist обновляются после `Проверка окружения`: при доступном `CUDAExecutionProvider` UI рекомендует GPU для больших папок; при недоступном GPU объясняет CPU fallback.

## v66.1 / Этап 025 — compact UI layout polish

- Нижняя вкладочная панель стартует компактнее.
- Подробная таблица `Этап / Состояние / Прогресс / Последнее сообщение` скрыта по умолчанию.
- Верхняя рабочая область формы получает больше вертикального места.

## v66.0 / Этап 025 — post-packaging product stabilization and usability pass

- Первый безопасный UX/UI polish pass поверх стабильной `v65.4` CPU/GPU portable packaging base.
- Добавлены стартовые подсказки UI, CPU/GPU status block, improved run summary и кнопка `Открыть diagnostics`.
