# Tuned Image Sorter v69.6 — справка

`v69.6 / Этап 055` — first public polish / release identity pass поверх подтверждённой `v69.3.1 / Этап 052` rebrand-базы.

## Быстрый старт

1. Запустите `TunedImageSorter.exe`.
2. Выберите папку `input` с исходными фотографиями.
3. Выберите отдельную папку `output` для результата.
4. Нажмите `Проверка окружения`.
5. Для первого запуска используйте маленькую тестовую папку.
6. После проверки нажмите `Старт`.

## Диагностика

Основные команды выполняются через `TunedImageSorter_CLI.exe`:

```powershell
TunedImageSorter_CLI.exe --diagnostics-help
TunedImageSorter_CLI.exe --runtime-preflight
TunedImageSorter_CLI.exe --runtime-preflight --gpu
TunedImageSorter_CLI.exe --release-check
TunedImageSorter_CLI.exe --result-health --output <result_dir>
TunedImageSorter_CLI.exe --support-bundle --output <result_dir>
```

## Где читать документацию

- `START_HERE_RU.txt` — с чего начать.
- `QUICK_START_RU.txt` — быстрый запуск.
- `FIRST_RUN_RU.txt` — безопасный первый прогон.
- `ERRORS_RU.txt` — понятные ошибки.
- `TROUBLESHOOTING_RU.txt` — типовые проблемы.
- `RC_CHECKLIST_RU.txt` — checklist перед передачей ZIP.
- `RELEASE_GATE_RU.txt` — PASS/FAIL gate.
- `RELEASE_FREEZE_RU.txt` — stable release freeze.
- `DOCS_I18N_HYGIENE_RU.txt` — проверка документации и перевода.

## Что не изменено

`v69.6` не меняет ML, распознавание лиц, pipeline, clustering, SQLite schema, `project.json`, CSV schemas, Review clusters, apply-names, result-health, support-bundle, CPU/GPU split и GPU runtime packaging.
