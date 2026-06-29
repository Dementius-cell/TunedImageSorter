# Tuned Image Sorter v69.6 — quick GUI guide

`v69.6 / Stage 055` is a first public polish / release identity pass patch. The GUI still starts through `TunedImageSorter.exe`; diagnostics use `TunedImageSorter_CLI.exe`.

## Main workflow

1. Open `TunedImageSorter.exe`.
2. Select `input` and `output`.
3. Make sure `output` is not inside `input`.
4. Run `Environment check`.
5. For the first run, use a small folder.
6. Click `Start`.
7. After completion, check `final`, `reports` and `diagnostics`.

## After a run

- `Open result` opens the result root folder.
- `Open reports` opens `reports`.
- `Open diagnostics` opens diagnostics/reports diagnostics.
- `result-health` checks an existing result folder without rescanning photos.
- `support-bundle` creates a diagnostic ZIP for troubleshooting.

## Review / apply-names

Ordinary `Start` must run the main pipeline (`mode=all`) and must not switch into apply-names. Apply-names runs only through the dedicated action for applying `names.csv`.

## Version boundaries

`v69.6` does not change ML/pipeline/reports/schema/output formats.
