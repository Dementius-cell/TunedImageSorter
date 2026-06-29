param(
    [ValidateSet("cpu", "gpu", "gpu-full", "gpu-cu12", "gpu-lite")]
    [string]$Profile = "cpu",
    [switch]$Gpu,
    [switch]$Windowed,
    [switch]$Console,
    [switch]$InstallRequirements,
    [switch]$SkipChecks,
    [switch]$ZipOutput,
    [switch]$NoZipOutput
)

$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Label,
        [Parameter(Mandatory=$true)]
        [scriptblock]$Command
    )
    Write-Host ""
    Write-Host "==> $Label"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

function Test-AnyFile {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Root,
        [Parameter(Mandatory=$true)]
        [string]$Pattern
    )
    if (-not (Test-Path $Root)) { return $false }
    $hit = Get-ChildItem -Path $Root -Recurse -File -Filter $Pattern -ErrorAction SilentlyContinue | Select-Object -First 1
    return $null -ne $hit
}

function Assert-AnyFile {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Root,
        [Parameter(Mandatory=$true)]
        [string]$Pattern,
        [Parameter(Mandatory=$true)]
        [string]$Message
    )
    if (-not (Test-AnyFile -Root $Root -Pattern $Pattern)) {
        throw "$Message Pattern: $Pattern Root: $Root"
    }
    Write-Host "Runtime file OK: $Pattern"
}


function Copy-FriendReadyDocs {
    param(
        [Parameter(Mandatory=$true)]
        [string]$ProjectRoot,
        [Parameter(Mandatory=$true)]
        [string]$OutputDir
    )
    $Docs = @(
        "START_HERE_RU.txt",
        "START_HERE_EN.txt",
        "QUICK_START_RU.txt",
        "QUICK_START_EN.txt",
        "FIRST_RUN_RU.txt",
        "FIRST_RUN_EN.txt",
        "ERRORS_RU.txt",
        "ERRORS_EN.txt",
        "TROUBLESHOOTING_RU.txt",
        "TROUBLESHOOTING_EN.txt",
        "RC_CHECKLIST_RU.txt",
        "RC_CHECKLIST_EN.txt",
        "RELEASE_GATE_RU.txt",
        "RELEASE_GATE_EN.txt",
        "RELEASE_FREEZE_RU.txt",
        "RELEASE_FREEZE_EN.txt",
        "DOCS_I18N_HYGIENE_RU.txt",
        "DOCS_I18N_HYGIENE_EN.txt",
        "GPU_LITE_RU.txt",
        "GPU_LITE_EN.txt",
        "DUAL_GPU_PACKAGING_RU.txt",
        "DUAL_GPU_PACKAGING_EN.txt",
        "PRODUCT_RENAME_RU.txt",
        "PRODUCT_RENAME_EN.txt",
        "PRE_RELEASE_POLISH_RU.txt",
        "PRE_RELEASE_POLISH_EN.txt",
        "PROFILE_GUIDE_RU.txt",
        "PROFILE_GUIDE_EN.txt",
        "PRIVACY_LOCAL_PROCESSING_RU.txt",
        "PRIVACY_LOCAL_PROCESSING_EN.txt",
        "KNOWN_LIMITATIONS_RU.txt",
        "KNOWN_LIMITATIONS_EN.txt",
        "PUBLIC_RELEASE_NOTES_RU.txt",
        "PUBLIC_RELEASE_NOTES_EN.txt",
        "RELEASE_BUNDLE_RU.txt",
        "RELEASE_BUNDLE_EN.txt",
        "WHICH_VERSION_TO_DOWNLOAD_RU.txt",
        "WHICH_VERSION_TO_DOWNLOAD_EN.txt",
        "README_RU.txt",
        "README_EN.txt",
        "VERSION.txt",
        "SUPPORT_BUNDLE_RU.txt",
        "SUPPORT_BUNDLE_EN.txt"
    )
    foreach ($Doc in $Docs) {
        $Source = Join-Path $ProjectRoot $Doc
        $Target = Join-Path $OutputDir $Doc
        if (-not (Test-Path $Source)) { throw "Friend-ready doc is missing from source tree: $Source" }
        Copy-Item -LiteralPath $Source -Destination $Target -Force
        Write-Host "Friend-ready doc OK: $Target"
    }
}


function Write-PortableManifest {
    param(
        [Parameter(Mandatory=$true)]
        [string]$OutputDir,
        [Parameter(Mandatory=$true)]
        [ValidateSet("cpu", "gpu", "gpu-lite")]
        [string]$Profile
    )

    $ManifestPath = Join-Path $OutputDir "portable_manifest.json"
    $RuntimeExpectations = if ($Profile -eq "gpu") {
        [ordered]@{
            onnxruntime_distribution = "onnxruntime-gpu==1.26.0"
            requires_cuda_execution_provider = $true
            requires_bundled_cuda12_runtime = $true
            expected_provider = "CUDAExecutionProvider"
            bundled_runtime_families = @("CUDA", "cuDNN", "cuBLAS", "NVRTC", "cuFFT", "cuRAND", "nvJitLink")
        }
    } elseif ($Profile -eq "gpu-lite") {
        [ordered]@{
            onnxruntime_distribution = "onnxruntime-gpu==1.26.0"
            requires_cuda_execution_provider = $true
            requires_bundled_cuda12_runtime = $false
            expected_provider = "CUDAExecutionProvider"
            first_run_runtime_setup = $true
            local_runtime_cache = "%LOCALAPPDATA%\TunedImageSorter\gpu_lite_runtime\cuda12_ort126_v69_3_1"
            runtime_setup_command = "TunedImageSorter_CLI.exe --gpu-lite-runtime-setup --yes"
            runtime_status_command = "TunedImageSorter_CLI.exe --gpu-lite-runtime-status"
            removed_bundled_runtime_families = @("CUDA", "cuDNN", "cuBLAS", "NVRTC", "cuFFT", "cuRAND", "nvJitLink")
        }
    } else {
        [ordered]@{
            onnxruntime_distribution = "onnxruntime==1.27.0"
            requires_cuda_execution_provider = $false
            requires_bundled_cuda12_runtime = $false
            expected_provider = "CPUExecutionProvider"
            forbidden_provider = "CUDAExecutionProvider"
        }
    }

    $RuntimePreflightCommand = if ($Profile -eq "gpu" -or $Profile -eq "gpu-lite") { "TunedImageSorter_CLI.exe --runtime-preflight --gpu" } else { "TunedImageSorter_CLI.exe --runtime-preflight" }

    # Keep this construction ASCII-only so Windows PowerShell 5.1 cannot
    # mojibake the Cyrillic stage label when the script is read on systems
    # that do not preserve UTF-8 source encoding.
    $RefactorStage = (-join ([char[]](0x042D, 0x0442, 0x0430, 0x043F))) + " 055"

    $Manifest = [ordered]@{
        schema_version = 1
        app = "Tuned Image Sorter"
        package_kind = "friend-ready-portable"
        version = "v69.6"
        refactor_stage = $RefactorStage
        ui_api_version = 21
        profile = $Profile
        created_at_utc = ((Get-Date).ToUniversalTime().ToString("s") + "Z")
        launchers = [ordered]@{
            gui = "TunedImageSorter.exe"
            cli = "TunedImageSorter_CLI.exe"
        }
        diagnostics = [ordered]@{
            release_check = "TunedImageSorter_CLI.exe --release-check"
            runtime_preflight = $RuntimePreflightCommand
            result_health = "TunedImageSorter_CLI.exe --result-health --output <result_dir>"
            support_bundle = "TunedImageSorter_CLI.exe --support-bundle --output <result_dir>"
            diagnostics_help = "TunedImageSorter_CLI.exe --diagnostics-help"
        }
        runtime_expectations = $RuntimeExpectations
        unchanged_contracts = @(
            "ML/recognition unchanged",
            "clustering unchanged",
            "pipeline stages unchanged",
            "SQLite schema unchanged",
            "project.json unchanged",
            "CSV report schemas unchanged",
            "ordinary Start must run mode=all, not apply-names"
        )
    }

    $Manifest | ConvertTo-Json -Depth 8 | Out-File -FilePath $ManifestPath -Encoding utf8
    Write-Host "Portable manifest OK: $ManifestPath"
}



function Invoke-CpuRequirementsInstall {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Python,
        [Parameter(Mandatory=$true)]
        [string]$RequirementsPath
    )
    Write-Host "Installing CPU build requirements with clean CPU ONNX Runtime."

    & $Python -m pip install -r $RequirementsPath
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    # CPU and GPU ONNX Runtime wheels share the top-level `onnxruntime` package.
    # When a reused Python install was previously used for GPU packaging, simply
    # installing CPU `onnxruntime` can leave GPU provider DLLs and
    # `onnxruntime-gpu` metadata behind.  v69.6 makes the CPU profile symmetric
    # with the GPU profile: remove both ORT distributions and force-reinstall the
    # CPU wheel so the CPU portable build cannot accidentally collect CUDA/TensorRT
    # provider DLLs from a prior GPU build.
    & $Python -m pip uninstall -y onnxruntime-gpu onnxruntime
    $global:LASTEXITCODE = 0

    & $Python -m pip install --upgrade --force-reinstall --no-deps "onnxruntime"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

function Invoke-SourceCpuProviderCheck {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Python
    )
    & $Python tools\windows_packaging\check_onnxruntime_provider.py --require-no-cuda --require-no-gpu-distribution
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

function Assert-FrozenCpuProvider {
    param(
        [Parameter(Mandatory=$true)]
        [string]$ExePath,
        [Parameter(Mandatory=$true)]
        [string]$OutputDir,
        [Parameter(Mandatory=$true)]
        [string]$InternalDir,
        [Parameter(Mandatory=$true)]
        [string]$Python,
        [Parameter(Mandatory=$true)]
        [string]$ProjectRoot
    )
    $CheckPath = Join-Path $OutputDir "runtime_preflight_cpu_build_check.json"
    $RawCheckPath = Join-Path $OutputDir "runtime_preflight_cpu_build_check.raw.txt"
    $Extractor = Join-Path $ProjectRoot "tools\windows_packaging\extract_json_from_mixed_output.py"
    if (Test-Path $CheckPath) { Remove-Item $CheckPath -Force }
    if (Test-Path $RawCheckPath) { Remove-Item $RawCheckPath -Force }

    & $ExePath --runtime-preflight 2>&1 | Out-File -FilePath $RawCheckPath -Encoding utf8
    if ($LASTEXITCODE -ne 0) {
        throw "Frozen CPU runtime preflight failed with exit code $LASTEXITCODE. See $RawCheckPath"
    }
    & $Python $Extractor $RawCheckPath $CheckPath --require cuda_provider_available=false
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "Frozen CPU runtime preflight raw output:"
        Get-Content -Path $RawCheckPath | Write-Host
        throw "Could not extract/validate frozen CPU runtime preflight JSON: $RawCheckPath"
    }

    if (Test-AnyFile -Root $InternalDir -Pattern "onnxruntime_providers_cuda.dll") {
        throw "CPU build must not bundle onnxruntime_providers_cuda.dll. Rebuild after CPU ORT cleanup."
    }
    if (Test-AnyFile -Root $InternalDir -Pattern "onnxruntime_providers_tensorrt.dll") {
        throw "CPU build must not bundle onnxruntime_providers_tensorrt.dll. Rebuild after CPU ORT cleanup."
    }
    Write-Host "Frozen CPU provider OK: CUDAExecutionProvider is absent and GPU provider DLLs are not bundled."
    Write-Host "Frozen CPU preflight JSON: $CheckPath"
}

function Invoke-GpuRequirementsInstall {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Python,
        [Parameter(Mandatory=$true)]
        [string]$RequirementsPath
    )
    Write-Host "Installing deterministic GPU build requirements without activating CPU onnxruntime/latest GPU wheels."

    # Do not install requirements-windows-common.txt as-is for GPU builds: the
    # upstream insightface dependency asks pip for CPU-only `onnxruntime`, which
    # caused v67.8/v67.8.1 to temporarily download onnxruntime latest and then
    # remove it.  Install the same runtime dependencies in a controlled order and
    # install insightface without dependencies, then pin the CUDA 12 ORT stack.
    & $Python -m pip install `
        "PySide6" `
        "pyinstaller" `
        "numpy" `
        "Pillow" `
        "opencv-python" `
        "scikit-learn" `
        "hdbscan" `
        "tqdm" `
        "pillow-heif" `
        "psutil" `
        "onnx" `
        "requests" `
        "scikit-image"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $Python -m pip install --no-deps "insightface"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    # Clean up ORT packages in reused Python installs. CPU ``onnxruntime`` and
    # GPU ``onnxruntime-gpu`` share the top-level ``onnxruntime`` package.  If
    # both were present, uninstalling only the CPU wheel can leave a broken
    # half-removed module where metadata says onnxruntime-gpu is installed but
    # ``onnxruntime.get_available_providers`` is missing.  v69.6 therefore
    # removes both distributions and force-reinstalls the pinned GPU wheel.
    & $Python -m pip uninstall -y onnxruntime onnxruntime-gpu
    $global:LASTEXITCODE = 0

    & $Python -m pip install --upgrade --force-reinstall --no-deps `
        "onnxruntime-gpu==1.26.0" `
        "nvidia-cuda-runtime-cu12==12.9.79" `
        "nvidia-cudnn-cu12==9.23.1.3" `
        "nvidia-cublas-cu12==12.9.2.10" `
        "nvidia-cuda-nvrtc-cu12==12.9.86" `
        "nvidia-cufft-cu12==11.4.1.4" `
        "nvidia-curand-cu12==10.3.10.19" `
        "nvidia-nvjitlink-cu12==12.9.86"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Invoke-GpuPipCheck -Python $Python
    if ($LASTEXITCODE -ne 0) {
        $global:LASTEXITCODE = 0
    }
}

function Invoke-GpuPipCheck {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Python
    )

    $PipCheckOutput = & $Python -m pip check 2>&1
    $PipCheckExitCode = $LASTEXITCODE
    if ($PipCheckExitCode -eq 0) {
        Write-Host "pip check: OK"
        return
    }

    $Unexpected = @()
    foreach ($LineObject in $PipCheckOutput) {
        $Line = ("$LineObject").Trim()
        if ($Line.Length -eq 0) { continue }
        if ($Line -match '^insightface\s+1\.0\.1\s+requires\s+onnxruntime,\s+which\s+is\s+not\s+installed\.$') {
            Write-Host "pip check: allowed GPU metadata mismatch: $Line"
            continue
        }
        $Unexpected += $Line
    }

    if ($Unexpected.Count -gt 0) {
        foreach ($Line in $Unexpected) { Write-Error $Line }
        exit $PipCheckExitCode
    }

    Write-Host "pip check: OK (allowed insightface metadata requirement; onnxruntime-gpu provides the runtime module)"

    # PowerShell keeps the previous native command exit code in $LASTEXITCODE even
    # after a successful function return.  Because pip check intentionally exits 1
    # for this allowed metadata-only mismatch, reset the native exit code so the
    # outer Invoke-Checked wrapper does not treat the already-accepted state as a
    # failed GPU requirements install.
    $global:LASTEXITCODE = 0
}

function Invoke-SourceGpuProviderCheck {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Python
    )
    & $Python tools\windows_packaging\check_onnxruntime_provider.py --require-cuda --require-pinned-gpu-runtime --require-cuda-session
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

function Assert-FrozenGpuProvider {
    param(
        [Parameter(Mandatory=$true)]
        [string]$ExePath,
        [Parameter(Mandatory=$true)]
        [string]$OutputDir,
        [Parameter(Mandatory=$true)]
        [string]$Python,
        [Parameter(Mandatory=$true)]
        [string]$ProjectRoot
    )
    $CheckPath = Join-Path $OutputDir "runtime_preflight_gpu_build_check.json"
    $RawCheckPath = Join-Path $OutputDir "runtime_preflight_gpu_build_check.raw.txt"
    $Extractor = Join-Path $ProjectRoot "tools\windows_packaging\extract_json_from_mixed_output.py"
    if (Test-Path $CheckPath) { Remove-Item $CheckPath -Force }
    if (Test-Path $RawCheckPath) { Remove-Item $RawCheckPath -Force }

    # Capture stdout+stderr first.  Native redirection in Windows PowerShell 5.x
    # writes UTF-16LE by default, which is valid text but awkward for machine
    # tooling.  v65.4 writes the raw capture as UTF-8 and the extractor also
    # understands UTF-16 for logs produced manually with `>` redirection.
    & $ExePath --runtime-preflight --gpu 2>&1 | Out-File -FilePath $RawCheckPath -Encoding utf8
    if ($LASTEXITCODE -ne 0) {
        throw "Frozen GPU runtime preflight failed with exit code $LASTEXITCODE. See $RawCheckPath"
    }
    & $Python $Extractor $RawCheckPath $CheckPath --require gpu.cuda_provider_available=true
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "Frozen GPU runtime preflight raw output:"
        Get-Content -Path $RawCheckPath | Write-Host
        throw "Could not extract/validate frozen GPU runtime preflight JSON: $RawCheckPath"
    }
    # Use Python to parse the normalized JSON. Windows PowerShell 5.x may read
    # UTF-8 without BOM as the legacy ANSI code page; ConvertFrom-Json can then
    # fail even when the extractor produced valid JSON. The extractor already
    # validated gpu.cuda_provider_available=true; this second parse gives a
    # stable, code-page-independent guard and clearer output.
    $VerifierCode = @"
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
data = json.loads(p.read_text(encoding='utf-8-sig'))
if not data.get('gpu', {}).get('cuda_provider_available'):
    raise SystemExit('CUDAExecutionProvider is absent in frozen runtime preflight JSON')
print('Frozen GPU provider OK: CUDAExecutionProvider is visible.')
"@
    & $Python -c $VerifierCode $CheckPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "Frozen GPU runtime preflight did not expose CUDAExecutionProvider. Diagnostic JSON:"
        Get-Content -Path $CheckPath | Write-Host
        throw "GPU build is not valid as a GPU portable build: CUDAExecutionProvider is absent after packaging."
    }
    Write-Host "Frozen GPU preflight JSON: $CheckPath"
}


function Remove-GpuLiteBundledRuntime {
    param(
        [Parameter(Mandatory=$true)]
        [string]$InternalDir
    )
    $NvidiaDir = Join-Path $InternalDir "nvidia"
    if (Test-Path $NvidiaDir) {
        Remove-Item -LiteralPath $NvidiaDir -Recurse -Force
        Write-Host "GPU Lite runtime strip OK: removed $NvidiaDir"
    }

    # v69.6 GPU Lite hotfix: PyInstaller can also copy CUDA runtime DLLs
    # directly under _internal (or another subfolder), not only under
    # _internal\nvidia. Strip those DLLs too; keep onnxruntime_providers_cuda.dll
    # because ORT needs the provider DLL and the missing CUDA runtime is supplied
    # by the first-run GPU Lite bootstrap after user consent.
    $RuntimeDllPatterns = @(
        "cudart64_12.dll",
        "cublas64_12.dll",
        "cublasLt64_12.dll",
        "cudnn64_9.dll",
        "nvrtc64_*.dll",
        "cufft64_*.dll",
        "curand64_*.dll",
        "nvJitLink*.dll"
    )
    $RemovedCount = 0
    foreach ($Pattern in $RuntimeDllPatterns) {
        $Matches = Get-ChildItem -LiteralPath $InternalDir -Filter $Pattern -File -Recurse -ErrorAction SilentlyContinue
        foreach ($Item in $Matches) {
            Remove-Item -LiteralPath $Item.FullName -Force
            $RemovedCount += 1
            Write-Host "GPU Lite runtime strip OK: removed bundled NVIDIA runtime DLL $($Item.FullName)"
        }
    }
    if ($RemovedCount -eq 0) {
        Write-Host "GPU Lite runtime strip OK: no bundled NVIDIA runtime DLLs found outside nvidia folder"
    }
}

function Assert-GpuLitePackage {
    param(
        [Parameter(Mandatory=$true)]
        [string]$InternalDir,
        [Parameter(Mandatory=$true)]
        [string]$CliExePath,
        [Parameter(Mandatory=$true)]
        [string]$OutputDir,
        [Parameter(Mandatory=$true)]
        [string]$Python,
        [Parameter(Mandatory=$true)]
        [string]$ProjectRoot
    )
    Assert-AnyFile -Root $InternalDir -Pattern "onnxruntime_providers_cuda.dll" -Message "GPU Lite build must keep ONNX Runtime CUDA provider DLL."
    foreach ($Pattern in @("cudart64_12.dll", "cublas64_12.dll", "cublasLt64_12.dll", "cudnn64_9.dll")) {
        if (Test-AnyFile -Root $InternalDir -Pattern $Pattern) {
            throw "GPU Lite package must not bundle NVIDIA runtime DLL $Pattern under _internal."
        }
    }
    $StatusPath = Join-Path $OutputDir "gpu_lite_runtime_status_build_check.json"
    & $CliExePath --gpu-lite-runtime-status 2>&1 | Out-File -FilePath $StatusPath -Encoding utf8
    if ($LASTEXITCODE -ne 0) {
        throw "GPU Lite runtime status command failed. See $StatusPath"
    }
    Write-Host "GPU Lite package OK: CUDA provider DLL kept, bundled NVIDIA runtime stripped, first-run runtime setup enabled."
    Write-Host "GPU Lite runtime status JSON: $StatusPath"
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..")
Set-Location $ProjectRoot

if ($Gpu) { $Profile = "gpu" }
$CanonicalProfile = if ($Profile -eq "gpu-cu12" -or $Profile -eq "gpu-full") { "gpu" } else { $Profile }
$GpuFamily = ($CanonicalProfile -eq "gpu" -or $CanonicalProfile -eq "gpu-lite")

if (-not (Test-Path "face_sorter_mvp\__init__.py")) {
    throw "Project root is invalid. Run this from the unpacked face_sorter_mvp_v69_6 folder, not from inside face_sorter_mvp."
}

$Python = "py"
$Spec = if ($GpuFamily) {
    Join-Path $ScriptDir "face_sorter_mvp_gui_gpu_cuda12.spec"
} else {
    Join-Path $ScriptDir "face_sorter_mvp_gui_cpu.spec"
}
$Req = if ($GpuFamily) {
    Join-Path $ScriptDir "requirements-windows-gpu-cu12.txt"
} else {
    Join-Path $ScriptDir "requirements-windows-cpu.txt"
}
$OutputName = if ($CanonicalProfile -eq "gpu-lite") { "TunedImageSorter_GPU_LITE" } elseif ($CanonicalProfile -eq "gpu") { "TunedImageSorter_GPU_FULL" } else { "TunedImageSorter_CPU" }
$OutputDir = Join-Path $ProjectRoot "dist\windows\$OutputName"
$InternalDir = Join-Path $OutputDir "_internal"

Write-Host "Tuned Image Sorter v69.6 Windows one-folder packaging"
Write-Host "Project root: $ProjectRoot"
Write-Host "Profile: $CanonicalProfile"
if ($Profile -eq "gpu-cu12") { Write-Host "Profile alias: gpu-cu12 -> gpu" }
if ($Profile -eq "gpu-full") { Write-Host "Profile alias: gpu-full -> gpu" }
Write-Host "Spec: $Spec"
Write-Host "Requirements: $Req"
Write-Host "Output: $OutputDir"

if ($InstallRequirements) {
    Invoke-Checked "Upgrade pip/setuptools/wheel" { & $Python -m pip install --upgrade pip setuptools wheel }
    if ($GpuFamily) {
        Invoke-Checked "Install gpu requirements with forced GPU ONNX Runtime" { Invoke-GpuRequirementsInstall -Python $Python -RequirementsPath $Req }
        Invoke-Checked "Pinned source GPU provider sanity" { Invoke-SourceGpuProviderCheck -Python $Python }
    } else {
        Invoke-Checked "Install cpu requirements with clean CPU ONNX Runtime" { Invoke-CpuRequirementsInstall -Python $Python -RequirementsPath $Req }
        Invoke-Checked "Source CPU provider sanity" { Invoke-SourceCpuProviderCheck -Python $Python }
    }
}

if (-not $SkipChecks) {
    Invoke-Checked "compileall" { & $Python -m compileall -q face_sorter_mvp tools }
    Invoke-Checked "file_ops self-test" { & $Python face_sorter_mvp\file_ops.py --self-test }
    Invoke-Checked "packaging smoke-test" { & $Python tools\windows_packaging\smoke_test_packaging.py }
    Invoke-Checked "friend-ready source verification" { & $Python tools\windows_packaging\verify_friend_ready_package.py --source-root $ProjectRoot }
    Invoke-Checked "release check" { & $Python tools\release_check.py }
    if ($GpuFamily) {
        Invoke-Checked "Pinned source GPU provider sanity" { Invoke-SourceGpuProviderCheck -Python $Python }
    } else {
        Invoke-Checked "Source CPU provider sanity" { Invoke-SourceCpuProviderCheck -Python $Python }
    }
}

$PreviousPyInstallerAppName = $env:FACE_SORTER_PYINSTALLER_APP_NAME
try {
    $env:FACE_SORTER_PYINSTALLER_APP_NAME = $OutputName
    Invoke-Checked "PyInstaller one-folder build" { & $Python -m PyInstaller --noconfirm --clean --distpath dist\windows --workpath build\pyinstaller $Spec }
} finally {
    if ($null -eq $PreviousPyInstallerAppName) {
        Remove-Item Env:\FACE_SORTER_PYINSTALLER_APP_NAME -ErrorAction SilentlyContinue
    } else {
        $env:FACE_SORTER_PYINSTALLER_APP_NAME = $PreviousPyInstallerAppName
    }
}

$MeanShapePath = Join-Path $InternalDir "objects\meanshape_68.pkl"
if (-not (Test-Path $MeanShapePath)) {
    throw "PyInstaller output is missing InsightFace runtime object: $MeanShapePath. The frozen EXE will crash in landmark_3d_68 without it."
}
Write-Host "InsightFace runtime object OK: $MeanShapePath"

$GuiExePath = Join-Path $OutputDir "TunedImageSorter.exe"
$CliExePath = Join-Path $OutputDir "TunedImageSorter_CLI.exe"
if (-not (Test-Path $GuiExePath)) { throw "PyInstaller output is missing GUI launcher: $GuiExePath" }
if (-not (Test-Path $CliExePath)) { throw "PyInstaller output is missing CLI diagnostics launcher: $CliExePath" }
Write-Host "GUI launcher OK: $GuiExePath"
Write-Host "CLI diagnostics launcher OK: $CliExePath"

Copy-FriendReadyDocs -ProjectRoot $ProjectRoot -OutputDir $OutputDir
if ($CanonicalProfile -eq "gpu-lite") {
    Remove-GpuLiteBundledRuntime -InternalDir $InternalDir
}
Write-PortableManifest -OutputDir $OutputDir -Profile $CanonicalProfile

if ($CanonicalProfile -eq "gpu") {
    Assert-AnyFile -Root $InternalDir -Pattern "onnxruntime_providers_cuda.dll" -Message "GPU build is missing ONNX Runtime CUDA provider DLL."
    Assert-AnyFile -Root $InternalDir -Pattern "cudart64_12.dll" -Message "GPU build is missing CUDA runtime DLL from nvidia-cuda-runtime-cu12."
    Assert-AnyFile -Root $InternalDir -Pattern "cublas64_12.dll" -Message "GPU build is missing cuBLAS DLL from nvidia-cublas-cu12."
    Assert-AnyFile -Root $InternalDir -Pattern "cublasLt64_12.dll" -Message "GPU build is missing cuBLASLt DLL from nvidia-cublas-cu12."
    if ((-not (Test-AnyFile -Root $InternalDir -Pattern "cudnn64_9.dll")) -and (-not (Test-AnyFile -Root $InternalDir -Pattern "cudnn64_8.dll"))) {
        throw "GPU build is missing cuDNN runtime DLLs. Expected cudnn64_9.dll or cudnn64_8.dll under $InternalDir."
    }
    Write-Host "Runtime file OK: cuDNN runtime DLL"
    Assert-FrozenGpuProvider -ExePath (Join-Path $OutputDir "TunedImageSorter_CLI.exe") -OutputDir $OutputDir -Python $Python -ProjectRoot $ProjectRoot
} elseif ($CanonicalProfile -eq "gpu-lite") {
    Assert-GpuLitePackage -InternalDir $InternalDir -CliExePath (Join-Path $OutputDir "TunedImageSorter_CLI.exe") -OutputDir $OutputDir -Python $Python -ProjectRoot $ProjectRoot
} else {
    Assert-FrozenCpuProvider -ExePath (Join-Path $OutputDir "TunedImageSorter_CLI.exe") -OutputDir $OutputDir -InternalDir $InternalDir -Python $Python -ProjectRoot $ProjectRoot
}

$IdentityJsonPath = Join-Path $OutputDir "package_identity_check.json"
$IdentityTextPath = Join-Path $OutputDir "package_identity_check.txt"
Invoke-Checked "package identity report" {
    & $Python tools\windows_packaging\package_identity_report.py --package-dir $OutputDir --profile $CanonicalProfile --write-json $IdentityJsonPath --write-txt $IdentityTextPath
}

$FriendReadyVerifyArgs = @("tools\windows_packaging\verify_friend_ready_package.py", "--package-dir", $OutputDir, "--profile", $CanonicalProfile)
if ($CanonicalProfile -eq "gpu") { $FriendReadyVerifyArgs += "--after-gpu-verification" }
Invoke-Checked "friend-ready package verification" { & $Python @FriendReadyVerifyArgs }

Write-Host ""
Write-Host "Build complete. Output folder:"
Write-Host "  $OutputDir"
Write-Host ""
Write-Host "Run GUI:"
Write-Host "  $OutputDir\TunedImageSorter.exe"
Write-Host ""
if ($GpuFamily) {
    Write-Host "Recommended diagnostics:"
    Write-Host "  $OutputDir\TunedImageSorter_CLI.exe --runtime-preflight --gpu"
    if ($CanonicalProfile -eq "gpu-lite") {
        Write-Host "  $OutputDir\TunedImageSorter_CLI.exe --gpu-lite-runtime-status"
        Write-Host "  $OutputDir\TunedImageSorter_CLI.exe --gpu-lite-runtime-setup --yes"
    }
    Write-Host "  $OutputDir\TunedImageSorter_CLI.exe --release-check"
    Write-Host "  $OutputDir\TunedImageSorter_CLI.exe --scan-probe `"D:\orig light`" --gpu"
    Write-Host "  $OutputDir\TunedImageSorter_CLI.exe --support-bundle --output `"D:\result 12-30 15.06.2026`""
    Write-Host "  $OutputDir\TunedImageSorter_CLI.exe --result-health --output `"D:\result 12-30 15.06.2026`""
} else {
    Write-Host "Recommended diagnostics:"
    Write-Host "  $OutputDir\TunedImageSorter_CLI.exe --runtime-preflight"
    Write-Host "  $OutputDir\TunedImageSorter_CLI.exe --release-check"
    Write-Host "  $OutputDir\TunedImageSorter_CLI.exe --scan-probe `"D:\orig light`""
    Write-Host "  $OutputDir\TunedImageSorter_CLI.exe --support-bundle --output `"D:\result 12-30 15.06.2026`""
    Write-Host "  $OutputDir\TunedImageSorter_CLI.exe --result-health --output `"D:\result 12-30 15.06.2026`""
}

$ShouldCreateZip = $ZipOutput -or (-not $NoZipOutput)
if ($ShouldCreateZip) {
    $ZipPath = Join-Path $ProjectRoot "dist\windows\${OutputName}_portable_v69_6.zip"
    if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
    Write-Host ""
    Write-Host "Creating portable zip:"
    Write-Host "  $ZipPath"
    Compress-Archive -Path $OutputDir -DestinationPath $ZipPath
    Invoke-Checked "friend-ready zip integrity" { & $Python tools\windows_packaging\verify_friend_ready_package.py --zip $ZipPath }
    Write-Host "Portable zip: $ZipPath"
} else {
    Write-Host ""
    Write-Host "Portable zip skipped because -NoZipOutput was set."
}
