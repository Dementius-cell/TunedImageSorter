Tuned Image Sorter v69.6 / Stage 055
Public handoff materials

Purpose
-------
This folder contains publication texts and checklists for the first public portable release of Tuned Image Sorter.
This is NOT a new runtime build and NOT a new application-change stage. The materials are based on the confirmed base:

  Tuned Image Sorter v69.6 / Stage 055
  release bundle / checksums / final public handoff

What to publish
---------------
Publish the contents of the release bundle created with:

  py tools\windows_packaging\make_release_bundle.py

Expected folder:

  dist\windows\TunedImageSorter_v69_6_release

Expected files:
  - TunedImageSorter_CPU_portable_v69_6.zip
  - TunedImageSorter_GPU_FULL_portable_v69_6.zip
  - TunedImageSorter_GPU_LITE_portable_v69_6.zip
  - SHA256SUMS.txt
  - RELEASE_BUNDLE_MANIFEST.json
  - WHICH_VERSION_TO_DOWNLOAD_RU.txt
  - WHICH_VERSION_TO_DOWNLOAD_EN.txt
  - PUBLIC_RELEASE_NOTES_RU.txt
  - PUBLIC_RELEASE_NOTES_EN.txt


Recommended order
-----------------
1. Open dist\windows\TunedImageSorter_v69_6_release.
2. Confirm that the CPU, GPU_FULL and GPU_LITE ZIP files are present.
3. Confirm that SHA256SUMS.txt and RELEASE_BUNDLE_MANIFEST.json are present.
4. Verify SHA256 locally before publishing.
5. Use GITHUB_RELEASE_DRAFT_EN.md or GITHUB_RELEASE_DRAFT_RU.md as the release text.
6. Attach the ZIP files and SHA256SUMS.txt to the GitHub Release / publication page.
7. After publishing, download at least one ZIP from the public page and verify SHA256 again.

Do not change before publication
--------------------------------
Do not change without a separate decision:
- ML / face recognition;
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
- internal Python package face_sorter_mvp.

Known issue
-----------
The reports folder may not auto-open after an ordinary Start run finishes. This is a known non-blocking UX limitation.
