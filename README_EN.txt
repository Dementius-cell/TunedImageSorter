Tuned Image Sorter v69.6 / Stage 055
=================================

Friend-ready stable portable package for Windows.

Normal launch:
  TunedImageSorter.exe

Start here as a regular user:
  START_HERE_EN.txt
  QUICK_START_EN.txt
  FIRST_RUN_EN.txt

If something goes wrong:
  ERRORS_EN.txt
  TROUBLESHOOTING_EN.txt

Before sharing the build with another person:
  RC_CHECKLIST_EN.txt
  RELEASE_GATE_EN.txt
  RELEASE_FREEZE_EN.txt

For developers / documentation checks:
  DOCS_I18N_HYGIENE_EN.txt
  DUAL_GPU_PACKAGING_EN.txt

Diagnostics:
  TunedImageSorter_CLI.exe --diagnostics-help
  TunedImageSorter_CLI.exe --runtime-preflight
  TunedImageSorter_CLI.exe --runtime-preflight --gpu
  TunedImageSorter_CLI.exe --release-check
  TunedImageSorter_CLI.exe --self-test
  TunedImageSorter_CLI.exe --scan-probe <input_dir> [--gpu]
  TunedImageSorter_CLI.exe --result-health --output <result_dir>
  TunedImageSorter_CLI.exe --support-bundle --output <result_dir>

CPU package:
  Does not require Python, pip, Visual Studio, CUDA Toolkit, cuDNN installer, onnxruntime or insightface on the target machine.
  CUDAExecutionProvider is not needed and must be absent.

GPU package:
  Does not require Python, pip, Visual Studio, CUDA Toolkit, cuDNN installer, onnxruntime or insightface on the target machine.
  Requires Windows x64, an NVIDIA GPU and a current NVIDIA driver.
  The large _internal\nvidia folder is normal for the full portable CUDA GPU build.
  First launch must not download NVIDIA runtime files from the internet.

What changed in v69.6:
  The three official profiles CPU / GPU_FULL / GPU_LITE are now fixed explicitly.
  Added DOCS_I18N_HYGIENE_RU.txt / DOCS_I18N_HYGIENE_EN.txt.
  Developer notes and architecture notes were cleaned of stale early-stage references as the current baseline.
  Package/source/ZIP verification now checks DOCS_I18N_HYGIENE files.
  Release-check now has the docs_i18n_hygiene_polish guard.
  Expected ZIP files: TunedImageSorter_CPU_portable_v69_6.zip, TunedImageSorter_GPU_FULL_portable_v69_6.zip, TunedImageSorter_GPU_LITE_portable_v69_6.zip.
  The v66.6 regression guard is preserved: ordinary Start must not run apply-names.

v69.6 boundaries:
  ML, face recognition, clustering, ordinary Start, pipeline stages, SQLite schema, project.json, resume, report CSV formats, Review clusters/apply-names backend, result-health/support-bundle backend, CPU/GPU packaging split and pinned GPU runtime were not changed.

Support-bundle:
  TunedImageSorter_CLI.exe --support-bundle --output <result_dir>

Support-bundle automatically includes output\reports\result_health_check.json and result_health_check.txt if the output/result folder is known.

Official portable ZIP files for v69.6:
  TunedImageSorter_CPU_portable_v69_6.zip
  TunedImageSorter_GPU_FULL_portable_v69_6.zip
  TunedImageSorter_GPU_LITE_portable_v69_6.zip

GPU Lite experimental package:
  GPU_LITE_EN.txt
  TunedImageSorter_GPU_LITE_portable_v69_6.zip
  TunedImageSorter_CLI.exe --gpu-lite-runtime-status
  TunedImageSorter_CLI.exe --gpu-lite-runtime-setup --yes
  experimental_slim_gpu_package


Product rename:
  Details: PRODUCT_RENAME_EN.txt

Additional v69.6 files for public handoff:
  PROFILE_GUIDE_EN.txt — choosing CPU / GPU_FULL / GPU_LITE.
  PRIVACY_LOCAL_PROCESSING_EN.txt — privacy and local processing.
  KNOWN_LIMITATIONS_EN.txt — known limitations, including reports auto-open.
  PUBLIC_RELEASE_NOTES_EN.txt — short note for sharing the package.


Final v69.6 release bundle:
  RELEASE_BUNDLE_EN.txt — how to create the final TunedImageSorter_v69_6_release folder.
  WHICH_VERSION_TO_DOWNLOAD_EN.txt — which version to download: CPU / GPU_FULL / GPU_LITE.
  tools\windows_packaging\make_release_bundle.py — copies the three ZIP files into the release folder and writes SHA256SUMS.txt + RELEASE_BUNDLE_MANIFEST.json.
