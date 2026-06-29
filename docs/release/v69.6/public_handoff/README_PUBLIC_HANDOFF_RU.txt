Tuned Image Sorter v69.6 / Этап 055
Public handoff materials

Назначение папки
----------------
Эта папка содержит тексты и чеклисты для публикации первого публичного portable-релиза Tuned Image Sorter.
Это НЕ новая runtime-сборка и НЕ новый этап изменения приложения. Материалы опираются на подтверждённую базу:

  Tuned Image Sorter v69.6 / Этап 055
  release bundle / checksums / final public handoff

Что публиковать
----------------
Публиковать нужно содержимое release bundle, созданного командой:

  py tools\windows_packaging\make_release_bundle.py

Ожидаемая папка:

  dist\windows\TunedImageSorter_v69_6_release

Ожидаемые файлы:
  - TunedImageSorter_CPU_portable_v69_6.zip
  - TunedImageSorter_GPU_FULL_portable_v69_6.zip
  - TunedImageSorter_GPU_LITE_portable_v69_6.zip
  - SHA256SUMS.txt
  - RELEASE_BUNDLE_MANIFEST.json
  - WHICH_VERSION_TO_DOWNLOAD_RU.txt
  - WHICH_VERSION_TO_DOWNLOAD_EN.txt
  - PUBLIC_RELEASE_NOTES_RU.txt
  - PUBLIC_RELEASE_NOTES_EN.txt


Рекомендуемый порядок
---------------------
1. Открыть папку dist\windows\TunedImageSorter_v69_6_release.
2. Проверить наличие трёх ZIP-файлов: CPU, GPU_FULL, GPU_LITE.
3. Проверить наличие SHA256SUMS.txt и RELEASE_BUNDLE_MANIFEST.json.
4. Сверить SHA256 локально перед публикацией.
5. Скопировать текст из GITHUB_RELEASE_DRAFT_EN.md или GITHUB_RELEASE_DRAFT_RU.md.
6. Прикрепить ZIP-файлы и SHA256SUMS.txt к GitHub Release / странице публикации.
7. После публикации скачать хотя бы один ZIP с опубликованной страницы и проверить SHA256 повторно.

Не менять перед публикацией
--------------------------
Без отдельного решения не менять:
- ML / распознавание лиц;
- clustering logic;
- ordinary Start pipeline;
- apply-names;
- SQLite schema;
- project.json schema;
- CSV schemas;
- result-health;
- support-bundle;
- CPU / GPU_FULL / GPU_LITE split;
- GPU Lite runtime setup logic;
- внутренний Python package face_sorter_mvp.

Known issue
-----------
Папка reports может не открываться автоматически после завершения обычного запуска через кнопку «Старт». Это известное неблокирующее UX-ограничение.
