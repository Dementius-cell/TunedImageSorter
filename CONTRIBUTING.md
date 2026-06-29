# Contributing

Thanks for helping improve Tuned Image Sorter.

## Development Scope

For `v69.6`, keep changes conservative unless there is a separate decision to change behavior. The public handoff explicitly protects:

- ML and face recognition behavior.
- Clustering logic and thresholds.
- Ordinary Start pipeline behavior.
- SQLite, `project.json` and CSV schemas.
- Result-health and support-bundle formats.
- CPU / GPU_FULL / GPU_LITE packaging split.
- Pinned GPU runtime behavior.
- Internal Python package name `face_sorter_mvp`.

## Local Checks

```powershell
py tools\release_check.py --no-self-test
py -m compileall face_sorter_mvp tools
```

Use `tools/windows_packaging/README_WINDOWS_PACKAGING_EN.md` or `tools/windows_packaging/README_WINDOWS_PACKAGING_RU.md` before changing packaging scripts.

## Pull Requests

Include:

- A short summary of the change.
- Which user flow or packaging profile is affected.
- The checks you ran.
- Any release asset or documentation impact.
