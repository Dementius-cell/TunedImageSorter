# Tuned Image Sorter v69.6 — first public portable release

**Tuned Image Sorter** is a Windows app for locally sorting large photo folders by detected faces. It is designed for family archives, casual photo collections and professional image sets.

## What's included

- Three portable ZIP profiles: CPU, GPU_FULL and GPU_LITE.
- Local processing without requiring a cloud service.
- Result reports, diagnostics, result-health and support-bundle tools.
- RU/EN documents: quick start, version selection, privacy note and known limitations.
- SHA256 checksums for ZIP integrity verification.

## Which version should I download?

| File | Recommended for |
|---|---|
| `TunedImageSorter_CPU_portable_v69_6.zip` | Most compatible option. Works without an NVIDIA GPU. Slower, but simpler. |
| `TunedImageSorter_GPU_FULL_portable_v69_6.zip` | PCs with an NVIDIA GPU. Largest package; includes CUDA runtime files. |
| `TunedImageSorter_GPU_LITE_portable_v69_6.zip` | Experimental lighter GPU profile. Can use a GPU runtime cache or fallback. |

Start with CPU if unsure.

## SHA256 verification

After downloading, verify the ZIP files in PowerShell:

```powershell
Get-FileHash .\TunedImageSorter_CPU_portable_v69_6.zip -Algorithm SHA256
Get-FileHash .\TunedImageSorter_GPU_FULL_portable_v69_6.zip -Algorithm SHA256
Get-FileHash .\TunedImageSorter_GPU_LITE_portable_v69_6.zip -Algorithm SHA256
```

Compare the output with `SHA256SUMS.txt`.

## Known limitations

- Face recognition is not perfect: difficult angles, low light, occlusions and tiny faces may produce mistakes.
- Very small photo sets may not cluster well.
- The `reports` folder may not auto-open after an ordinary Start run finishes. Use the result/report open buttons in the UI.
- GPU_FULL is large because it bundles CUDA/cuDNN/cuBLAS runtime files.
- GPU_LITE remains a supplementary/experimental profile, not a replacement for CPU/GPU_FULL.

## Privacy / local processing

The application is designed for local photo processing on the user's computer. If you share a support bundle with someone else, remember that diagnostics may contain technical information, folder paths, logs and reports.
