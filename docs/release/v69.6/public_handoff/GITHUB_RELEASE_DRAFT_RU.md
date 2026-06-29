# Tuned Image Sorter v69.6 — первый public portable release

**Tuned Image Sorter** — Windows-приложение для локальной сортировки больших папок с фотографиями по распознанным лицам. Приложение ориентировано на семейные архивы, любительские фотоподборки и профессиональные наборы изображений.

## Что внутри релиза

- Три portable ZIP-профиля: CPU, GPU_FULL, GPU_LITE.
- Локальная обработка без обязательного облачного сервиса.
- Result reports, diagnostics, result-health и support-bundle.
- Документы RU/EN: быстрый старт, выбор версии, privacy note, known limitations.
- SHA256 checksums для проверки целостности ZIP-файлов.

## Какую версию скачать

| Файл | Кому подходит |
|---|---|
| `TunedImageSorter_CPU_portable_v69_6.zip` | Самый совместимый вариант. Работает без NVIDIA GPU. Медленнее, но проще. |
| `TunedImageSorter_GPU_FULL_portable_v69_6.zip` | Для ПК с NVIDIA GPU. Самый тяжёлый архив, включает CUDA runtime. |
| `TunedImageSorter_GPU_LITE_portable_v69_6.zip` | Экспериментальный облегчённый GPU-вариант. Может использовать GPU runtime cache или fallback. |

Если не уверены — начните с CPU.

## Проверка SHA256

После скачивания можно проверить ZIP в PowerShell:

```powershell
Get-FileHash .\TunedImageSorter_CPU_portable_v69_6.zip -Algorithm SHA256
Get-FileHash .\TunedImageSorter_GPU_FULL_portable_v69_6.zip -Algorithm SHA256
Get-FileHash .\TunedImageSorter_GPU_LITE_portable_v69_6.zip -Algorithm SHA256
```

Сравните результат с `SHA256SUMS.txt`.

## Известные ограничения

- Распознавание лиц не идеально: сложные ракурсы, плохой свет, закрытые лица и маленькие лица могут давать ошибки.
- На маленьких наборах фото кластеризация может быть менее полезной.
- Папка `reports` может не открываться автоматически после обычного запуска через кнопку «Старт». Используйте кнопки открытия результата/отчётов в интерфейсе.
- GPU_FULL занимает много места, потому что включает CUDA/cuDNN/cuBLAS runtime.
- GPU_LITE остаётся дополнительным/экспериментальным профилем, а не заменой CPU/GPU_FULL.

## Privacy / local processing

Приложение рассчитано на локальную обработку фото на компьютере пользователя. При передаче support-bundle другому человеку учитывайте, что diagnostics могут содержать технические сведения, пути к папкам, логи и отчёты.
