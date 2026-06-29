# Tuned Image Sorter v69.6 — Help

`v69.6 / Stage 055` is a first public polish / release identity pass on top of the confirmed `v69.3.1 / Stage 052` rebrand base.

## Quick start

1. Run `TunedImageSorter.exe`.
2. Select the `input` folder with source photos.
3. Select a separate `output` folder for results.
4. Click `Environment check`.
5. For the first run, use a small test folder.
6. After verification, click `Start`.

## Diagnostics

Main commands run through `TunedImageSorter_CLI.exe`:

```powershell
TunedImageSorter_CLI.exe --diagnostics-help
TunedImageSorter_CLI.exe --runtime-preflight
TunedImageSorter_CLI.exe --runtime-preflight --gpu
TunedImageSorter_CLI.exe --release-check
TunedImageSorter_CLI.exe --result-health --output <result_dir>
TunedImageSorter_CLI.exe --support-bundle --output <result_dir>
```

## Documentation map

- `START_HERE_EN.txt` — where to start.
- `QUICK_START_EN.txt` — quick launch.
- `FIRST_RUN_EN.txt` — safe first run.
- `ERRORS_EN.txt` — human-readable errors.
- `TROUBLESHOOTING_EN.txt` — common problems.
- `RC_CHECKLIST_EN.txt` — checklist before sharing the ZIP.
- `RELEASE_GATE_EN.txt` — PASS/FAIL gate.
- `RELEASE_FREEZE_EN.txt` — stable release freeze.
- `DOCS_I18N_HYGIENE_EN.txt` — documentation and translation hygiene check.

## What is unchanged

`v69.6` does not change ML, face recognition, pipeline, clustering, SQLite schema, `project.json`, CSV schemas, Review clusters, apply-names, result-health, support-bundle, CPU/GPU split or GPU runtime packaging.
