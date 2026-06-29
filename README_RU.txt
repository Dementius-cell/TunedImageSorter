Tuned Image Sorter v69.6 / Этап 055
================================

Friend-ready stable portable package для Windows.

Обычный запуск:
  TunedImageSorter.exe

Сначала читать обычному пользователю:
  START_HERE_RU.txt
  QUICK_START_RU.txt
  FIRST_RUN_RU.txt

Если возникла проблема:
  ERRORS_RU.txt
  TROUBLESHOOTING_RU.txt

Перед передачей сборки другому человеку:
  RC_CHECKLIST_RU.txt
  RELEASE_GATE_RU.txt
  RELEASE_FREEZE_RU.txt

Для разработчика / проверки документации:
  DOCS_I18N_HYGIENE_RU.txt
  DUAL_GPU_PACKAGING_RU.txt

Диагностика:
  TunedImageSorter_CLI.exe --diagnostics-help
  TunedImageSorter_CLI.exe --runtime-preflight
  TunedImageSorter_CLI.exe --runtime-preflight --gpu
  TunedImageSorter_CLI.exe --release-check
  TunedImageSorter_CLI.exe --self-test
  TunedImageSorter_CLI.exe --scan-probe <input_dir> [--gpu]
  TunedImageSorter_CLI.exe --result-health --output <result_dir>
  TunedImageSorter_CLI.exe --support-bundle --output <result_dir>

CPU package:
  Не требует Python, pip, Visual Studio, CUDA Toolkit, cuDNN installer, onnxruntime или insightface на машине запуска.
  CUDAExecutionProvider не нужен и должен отсутствовать.

GPU package:
  Не требует Python, pip, Visual Studio, CUDA Toolkit, cuDNN installer, onnxruntime или insightface на машине запуска.
  На ПК нужен Windows x64, NVIDIA GPU и актуальный NVIDIA driver.
  Большая папка _internal\nvidia является нормальной для full portable CUDA GPU build.
  Первый запуск пользователя не должен скачивать NVIDIA runtime из интернета.

Что нового в v69.6:
  Закреплены три официальных профиля CPU / GPU_FULL / GPU_LITE.
  Добавлены DOCS_I18N_HYGIENE_RU.txt / DOCS_I18N_HYGIENE_EN.txt.
  Developer notes и architecture notes очищены от устаревших ссылок на ранние этапы как на текущую базу.
  Package/source/ZIP verification теперь проверяет DOCS_I18N_HYGIENE файлы.
  Release-check получил guard docs_i18n_hygiene_polish.
  Ожидаемые ZIP: TunedImageSorter_CPU_portable_v69_6.zip, TunedImageSorter_GPU_FULL_portable_v69_6.zip, TunedImageSorter_GPU_LITE_portable_v69_6.zip.
  Guard против регрессии v66.6 сохранён: обычный «Старт» не запускает apply-names.

Границы v69.6:
  ML, распознавание лиц, clustering, ordinary Start, pipeline stages, SQLite schema, project.json, resume, report CSV formats, Review clusters/apply-names backend, result-health/support-bundle backend, CPU/GPU packaging split и pinned GPU runtime не менялись.

Support-bundle:
  TunedImageSorter_CLI.exe --support-bundle --output <result_dir>

Support-bundle автоматически включает output\reports\result_health_check.json и result_health_check.txt, если output/result папка известна.

Официальные portable ZIP v69.6:
  TunedImageSorter_CPU_portable_v69_6.zip
  TunedImageSorter_GPU_FULL_portable_v69_6.zip
  TunedImageSorter_GPU_LITE_portable_v69_6.zip

GPU Lite experimental package:
  GPU_LITE_RU.txt
  TunedImageSorter_GPU_LITE_portable_v69_6.zip
  TunedImageSorter_CLI.exe --gpu-lite-runtime-status
  TunedImageSorter_CLI.exe --gpu-lite-runtime-setup --yes
  experimental_slim_gpu_package


Переименование продукта:
  Подробности: PRODUCT_RENAME_RU.txt

Дополнительные файлы v69.6 для публичной передачи:
  PROFILE_GUIDE_RU.txt — какой профиль выбрать: CPU / GPU_FULL / GPU_LITE.
  PRIVACY_LOCAL_PROCESSING_RU.txt — privacy и локальная обработка.
  KNOWN_LIMITATIONS_RU.txt — известные ограничения, включая reports auto-open.
  PUBLIC_RELEASE_NOTES_RU.txt — короткая памятка для передачи сборки.


Финальный release bundle v69.6:
  RELEASE_BUNDLE_RU.txt — как собрать итоговую папку TunedImageSorter_v69_6_release.
  WHICH_VERSION_TO_DOWNLOAD_RU.txt — какую версию скачать: CPU / GPU_FULL / GPU_LITE.
  tools\windows_packaging\make_release_bundle.py — копирует три ZIP в release-папку и создаёт SHA256SUMS.txt + RELEASE_BUNDLE_MANIFEST.json.
