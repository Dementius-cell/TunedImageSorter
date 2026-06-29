# Tuned Image Sorter v69.6 — краткая инструкция GUI

`v69.6 / Этап 055` — first public polish / release identity pass. GUI по-прежнему запускается через `TunedImageSorter.exe`; диагностика — через `TunedImageSorter_CLI.exe`.

## Основной сценарий

1. Откройте `TunedImageSorter.exe`.
2. Выберите `input` и `output`.
3. Убедитесь, что `output` не находится внутри `input`.
4. Выполните `Проверка окружения`.
5. Для первого запуска используйте небольшую папку.
6. Нажмите `Старт`.
7. После завершения проверьте `final`, `reports` и `diagnostics`.

## После запуска

- `Открыть результат` открывает корневую папку результата.
- `Открыть отчёты` открывает `reports`.
- `Открыть diagnostics` открывает diagnostics/reports diagnostics.
- `result-health` проверяет уже созданную result-папку без пересканирования фотографий.
- `support-bundle` создаёт ZIP для диагностики проблемы.

## Review / apply-names

Обычный `Старт` должен запускать основной pipeline (`mode=all`) и не должен уходить в apply-names. Apply-names запускается только отдельным действием для применения `names.csv`.

## Границы версии

`v69.6` не меняет ML/pipeline/reports/schema/output formats.
