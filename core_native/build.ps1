<# =====================================================================
 build.ps1 — Quiet, readable Rust build wrapper for Shahin core_native
-----------------------------------------------------------------------
- Suppresses Cargo noise by default (warnings don’t break the build).
- Still fails fast on real errors (non-zero exit code).
- Segmented with clear steps and guardrails.
- Usage:
    pwsh ./build.ps1 [-OutDir <path>] [-ShowCargo]
===================================================================== #>

[CmdletBinding()]
param(
    # Where to drop the sealed/protected artifacts.
    [string] $OutDir,

    # Optional: override PyArmor output directory (default: build/pyarmor).
    [string] $PyArmorOutDir,

    # Optional hex-encoded 32-byte client key for per-client sealing.
    [string] $ClientKeyHex,

    # Path to a file that contains the client key (hex). Alternative to ClientKeyHex.
    [string] $ClientKeyFile,

    # Human-friendly client name; used to derive/store client id and key under .keys/clients/.
    [string] $ClientName,

    # Optional: show Cargo’s full stdout/stderr (for debugging).
    [switch] $ShowCargo
)

# --- Global safety ----------------------------------------------------
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# --- Logging helpers --------------------------------------------------
function Write-Info   { param([string]$Msg) Write-Host "[*] $Msg" }
function Write-Success{ param([string]$Msg) Write-Host "[+] $Msg" }
function Write-Stage  { param([string]$Msg) Write-Host "`n=== $Msg ===" }

function Normalize-ClientKeyHex {
    param([Parameter(Mandatory)][string]$Hex)
    $trimmed = $Hex.Trim()
    if ([string]::IsNullOrWhiteSpace($trimmed)) {
        throw "Client key material cannot be empty"
    }
    if ($trimmed.Length -ne 64) {
        throw "Client key material must be exactly 64 hexadecimal characters"
    }
    if ($trimmed -notmatch '^[0-9a-fA-F]+$') {
        throw "Client key material must contain only hexadecimal characters"
    }
    return $trimmed.ToLowerInvariant()
}

function Ensure-PyArmorAvailable {
    $pyarmor = Get-Command 'pyarmor' -ErrorAction SilentlyContinue
    if (-not $pyarmor) {
        throw "PyArmor not found. Install it in your build env (e.g., 'pip install pyarmor')."
    }
    return $pyarmor.Source
}

function Invoke-PyArmorObfuscation {
    param(
        [Parameter(Mandatory)][string]$Root,
        [Parameter(Mandatory)][string]$OutputDir
    )

    $pyarmorCmd = Ensure-PyArmorAvailable
    if (Test-Path -LiteralPath $OutputDir) {
        Remove-Item -LiteralPath $OutputDir -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

    $pythonInputs = @(
        'main.py',
        'tray_app.py',
        'src/common_utils/app_logger.py',
        'src/common_utils/resource_path.py',
        'src/common_utils/license_utils.py',
        'src/common_utils/native_guard.py',
        'src/detectors/plate_detector.py',
        'src/detectors/vehicle_detector.py',
        'src/preprocessor/preprocessor.py',
        'src/segmentation/segmentation.py',
        'src/selector/best_frame_selector.py',
        'src/detect_vehicle.py'
    )

    $args = @('gen', '-O', $OutputDir)
    foreach ($input in $pythonInputs) {
        $args += $input
    }

    Write-Stage "Obfuscate Python payloads (PyArmor)"
    Write-Info "pyarmor: $pyarmorCmd"
    Push-Location $Root
    try {
        & $pyarmorCmd @args
        if ($LASTEXITCODE -ne 0) {
            throw "pyarmor failed with exit code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }
}

function Generate-ClientKeyHex {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    } finally {
        $rng.Dispose()
    }
    return (-join ($bytes | ForEach-Object { $_.ToString("x2") }))
}

function Generate-ClientId {
    param([Parameter(Mandatory)][string]$SafeName)
    $suffix = ([guid]::NewGuid().ToString('N')).Substring(0,8)
    return ("{0}-{1}" -f $SafeName, $suffix)
}

# Run a native tool quietly; surface output only on failure
# - We temporarily relax $ErrorActionPreference so native stderr (warnings)
#   isn’t promoted to a terminating error by PowerShell.
# - On failure (non-zero exit), we throw with captured combined output.
function Run-Quiet {
    param(
        [Parameter(Mandatory)][string]$Command,
        [string[]]$Args,
        [switch]$PassThruOutput # for commands whose stdout is needed
    )

    # If caller requested full logs, just run and let output stream
    if ($ShowCargo) {
        & $Command @Args
        if ($LASTEXITCODE -ne 0) {
            throw "[fail] $Command $($Args -join ' ')"
        }
        return
    }

    $oldEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $all = & $Command @Args 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "[fail] $Command $($Args -join ' ')`n$($all -join [Environment]::NewLine)"
        }
        if ($PassThruOutput) {
            # Return raw combined output to caller
            return $all
        }
    } finally {
        $ErrorActionPreference = $oldEap
    }
}

# Compose a Cargo call with --quiet unless debugging
function Invoke-Cargo {
    param(
        [Parameter(Mandatory)][string[]]$Args,
        [switch]$NeedsOutput
    )
    $effectiveArgs = @()
    if (-not $ShowCargo) { $effectiveArgs += '--quiet' }
    $effectiveArgs += $Args
    if ($NeedsOutput) {
        return Run-Quiet -Command 'cargo' -Args $effectiveArgs -PassThruOutput
    } else {
        Run-Quiet -Command 'cargo' -Args $effectiveArgs
    }
}

function Get-FullPathFromRoot {
    param(
        [Parameter(Mandatory)][string]$Root,
        [Parameter(Mandatory)][string]$Relative
    )
    $normalized = $Relative -replace '/', [System.IO.Path]::DirectorySeparatorChar
    return [System.IO.Path]::GetFullPath((Join-Path $Root $normalized))
}

function Compute-FileSha256 {
    param([Parameter(Mandatory)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Expected file not found: $Path"
    }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        $hash = $sha.ComputeHash($stream)
    } finally {
        $stream.Dispose()
        $sha.Dispose()
    }
    return ([System.BitConverter]::ToString($hash)).Replace('-', '').ToLowerInvariant()
}

function Update-ProtectedExpectedHashes {
    param(
        [Parameter(Mandatory)][string]$ProtectedRsPath,
        [Parameter(Mandatory)][string]$RepoRoot
    )

    $lines = Get-Content -LiteralPath $ProtectedRsPath
    $currentPlaintext = $null
    $digestMap = @{}
    $changed = $false

    for ($i = 0; $i -lt $lines.Count; $i++) {
        $line = $lines[$i]
        if ($line -match 'plaintext_path:\s*"([^"]+)"') {
            $currentPlaintext = $matches[1]
        }
        if ($line -match 'expected_sha256:\s*"([0-9a-fA-F]{64})"') {
            if (-not $currentPlaintext) {
                throw "protected.rs: expected_sha256 appeared before plaintext_path near line $($i + 1)"
            }
            $abs = Get-FullPathFromRoot -Root $RepoRoot -Relative $currentPlaintext
            $digest = Compute-FileSha256 -Path $abs
            $digestMap[$currentPlaintext] = $digest
            $existing = $matches[1].ToLowerInvariant()
            if ($digest -ne $existing) {
                $lines[$i] = $line -replace '(?<=expected_sha256:\s*")[0-9a-fA-F]{64}(?=")', $digest
                $changed = $true
                Write-Info ("{0}: updated expected hash ({1} -> {2})" -f $currentPlaintext, $existing, $digest)
            } 
            $currentPlaintext = $null
        }
    }

    if ($changed) {
        Set-Content -LiteralPath $ProtectedRsPath -Value $lines -Encoding UTF8
        Write-Info "protected.rs hashes refreshed"
    } else {
        Write-Info "protected.rs already up to date"
    }

    return $digestMap
}

function Update-MainHashFile {
    param(
        [Parameter(Mandatory)][string]$MainPath,
        [Parameter(Mandatory)][string]$HashPath,
        [hashtable]$KnownHashes,
        [string]$KnownKey
    )

    $digest = $null
    $lookupKey = if ($KnownKey) { $KnownKey } else { 'main.py' }
    if ($KnownHashes -and $KnownHashes.ContainsKey($lookupKey)) {
        $digest = $KnownHashes[$lookupKey]
    } else {
        $digest = Compute-FileSha256 -Path $MainPath
    }

    $existing = $null
    if (Test-Path -LiteralPath $HashPath) {
        $existing = (Get-Content -LiteralPath $HashPath -Raw).Trim()
    }

    $hashDir = Split-Path -Parent $HashPath
    if ($hashDir -and -not (Test-Path -LiteralPath $hashDir)) {
        New-Item -ItemType Directory -Force -Path $hashDir | Out-Null
    }

    if (-not $existing -or $existing.ToLowerInvariant() -ne $digest) {
        Set-Content -LiteralPath $HashPath -Value ($digest + [Environment]::NewLine) -Encoding UTF8
        $prev = if ($existing) { $existing } else { "missing" }
        Write-Info ("res/main.py.sha256 updated ({0} -> {1})" -f $prev, $digest)
    } else {
        Write-Info "res/main.py.sha256 already matches main.py"
    }
}

# --- Path resolution --------------------------------------------------
Write-Stage "Resolve paths"

$root      = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$nativeDir = Join-Path $root 'core_native'

if (-not $OutDir -or [string]::IsNullOrWhiteSpace($OutDir)) {
    $OutDir = Join-Path $root 'build/protected'
}
if (-not $PyArmorOutDir -or [string]::IsNullOrWhiteSpace($PyArmorOutDir)) {
    $PyArmorOutDir = Join-Path $root 'build/pyarmor'
} else {
    $PyArmorOutDir = [System.IO.Path]::GetFullPath($PyArmorOutDir)
}
if (-not [System.IO.Path]::IsPathRooted($OutDir)) {
    $OutDir = [System.IO.Path]::GetFullPath($OutDir)
}

$targetDir  = Join-Path $nativeDir 'target'
$releaseDir = Join-Path $targetDir 'release'
$exePath    = Join-Path $releaseDir 'core_native.exe'
$hashTool   = Join-Path $releaseDir 'selfhash.exe'
$embedTool  = Join-Path $releaseDir 'embedhash.exe'
$embedKeyExe = Join-Path $releaseDir 'embedkey.exe'
$protectExe = Join-Path $releaseDir 'protect.exe'
$protectedDir = Join-Path $nativeDir 'protected'
$pyArmorMain = Join-Path $PyArmorOutDir 'main.py'
$pyArmorLabel = 'build/pyarmor/main.py'

Write-Info "root:        $root"
Write-Info "nativeDir:   $nativeDir"
Write-Info "outDir:      $OutDir"
Write-Info "pyarmorDir:  $PyArmorOutDir"

$ResolvedClientKey = $null
$ClientKeyRecordPath = $null
$ClientKeysDir = Join-Path $root '.keys/clients'
$ClientDir = $null
$safeClientName = $null
$ClientIdPath = $null
$ClientId = $null

if ($ClientKeyHex -and $ClientKeyFile) {
    throw "Specify either -ClientKeyHex or -ClientKeyFile, not both"
}
if ($ClientKeyFile) {
    if (-not (Test-Path -LiteralPath $ClientKeyFile)) {
        throw "Client key file not found at $ClientKeyFile"
    }
    $ClientKeyHex = (Get-Content -LiteralPath $ClientKeyFile -Raw).Trim()
}
if ($ClientKeyHex) {
    $ResolvedClientKey = Normalize-ClientKeyHex $ClientKeyHex
    Write-Info "Using explicitly provided client key material"
}

if (-not $ClientName) {
    throw "ClientName is required; provide -ClientName <friendly name>"
}

$ClientName = $ClientName.Trim()
if ([string]::IsNullOrWhiteSpace($ClientName)) {
    throw "ClientName cannot be empty"
}
$safeClientName = ($ClientName -replace '[^0-9A-Za-z._-]', '_').Trim()
if ([string]::IsNullOrWhiteSpace($safeClientName)) {
    throw "ClientName must contain at least one alphanumeric character"
}
if (-not (Test-Path -LiteralPath $ClientKeysDir)) {
    New-Item -ItemType Directory -Force -Path $ClientKeysDir | Out-Null
}
$ClientDir = Join-Path $ClientKeysDir $safeClientName
if (-not (Test-Path -LiteralPath $ClientDir)) {
    New-Item -ItemType Directory -Force -Path $ClientDir | Out-Null
}
$ClientKeyRecordPath = Join-Path $ClientDir 'client.key'
$ClientIdPath = Join-Path $ClientDir 'client.id'

if (-not $ClientId -and (Test-Path -LiteralPath $ClientIdPath)) {
    $ClientId = (Get-Content -LiteralPath $ClientIdPath -Raw).Trim()
}
if (-not $ClientId) {
    $ClientId = Generate-ClientId -SafeName $safeClientName
    Set-Content -LiteralPath $ClientIdPath -Value $ClientId -NoNewline
    Write-Info "Generated client id '$ClientId' for '$ClientName' at $ClientIdPath"
} else {
    Write-Info "Reusing client id '$ClientId' for '$ClientName' from $ClientIdPath"
}
if ($ResolvedClientKey) {
    if (Test-Path -LiteralPath $ClientKeyRecordPath) {
        $existing = Normalize-ClientKeyHex ((Get-Content -LiteralPath $ClientKeyRecordPath -Raw).Trim())
        if ($existing -ne $ResolvedClientKey) {
            throw "Client key file at $ClientKeyRecordPath already exists with different material"
        }
        Write-Info "Reusing existing client key for '$ClientId' from $ClientKeyRecordPath"
    } else {
        Set-Content -LiteralPath $ClientKeyRecordPath -Value $ResolvedClientKey -NoNewline
        Write-Info "Stored provided client key for '$ClientId' at $ClientKeyRecordPath"
    }
} elseif (Test-Path -LiteralPath $ClientKeyRecordPath) {
    $stored = Normalize-ClientKeyHex ((Get-Content -LiteralPath $ClientKeyRecordPath -Raw).Trim())
    $ResolvedClientKey = $stored
    Write-Info "Reusing existing client key for '$ClientId' from $ClientKeyRecordPath"
} else {
    $ResolvedClientKey = Generate-ClientKeyHex
    Set-Content -LiteralPath $ClientKeyRecordPath -Value $ResolvedClientKey -NoNewline
    Write-Info "Generated new client key for '$ClientId' at $ClientKeyRecordPath"
}

if (-not $ResolvedClientKey) {
    throw "Client key resolution failed; aborting to avoid launcher-hash fallback"
}

# --- Refresh expected hashes -----------------------------------------
Invoke-PyArmorObfuscation -Root $root -OutputDir $PyArmorOutDir

Write-Stage "Refresh expected hashes"
$protectedRsPath = Join-Path $nativeDir 'src/protected.rs'
$hashMap = Update-ProtectedExpectedHashes -ProtectedRsPath $protectedRsPath -RepoRoot $root
Update-MainHashFile -MainPath $pyArmorMain -HashPath (Join-Path $root 'res/main.py.sha256') -KnownHashes $hashMap -KnownKey $pyArmorLabel

# --- Clean previous artifacts (optional) ------------------------------
Write-Stage "Clean previous artifacts (if any)"
if (Test-Path -LiteralPath $releaseDir) {
    Write-Info "Clearing $targetDir"
    Remove-Item -LiteralPath $targetDir -Recurse -Force
} else {
    Write-Info "Nothing to clean"
}

# --- Step 1: Bootstrap build to produce tools -------------------------
Write-Stage "Build core_native for hash bootstrap"

Invoke-Cargo -Args @(
    'build',
    '--manifest-path', (Join-Path $nativeDir 'Cargo.toml'),
    '--release',
    '--bins'
)

# Validate expected tools exist
if (-not (Test-Path -LiteralPath $exePath)) {
    throw "core_native executable not found at $exePath"
}
if (-not (Test-Path -LiteralPath $hashTool)) {
    throw "selfhash helper missing at $hashTool"
}
if (-not (Test-Path -LiteralPath $embedTool)) {
    throw "embedhash helper missing at $embedTool"
}
if (-not (Test-Path -LiteralPath $embedKeyExe)) {
    throw "embedkey helper missing at $embedKeyExe"
}
if (-not (Test-Path -LiteralPath $protectExe)) {
    throw "protect executable not found at $protectExe"
}

# --- Step 2: Compute launcher hash (pre-embed) ------------------------
Write-Stage "Compute launcher hash (pre-embed)"
# We want the stdout of the tool; suppress noise unless debugging
$preOut = Run-Quiet -Command $hashTool -Args @($exePath) -PassThruOutput
$preSanitized = ($preOut -join "`n").Trim().ToLowerInvariant()
Write-Info "Sanitized hash (pre-embed): $preSanitized"

# --- Step 3: Embed hash into protected dir ----------------------------
Write-Stage "Embed self hash"
New-Item -ItemType Directory -Force -Path $protectedDir | Out-Null
Set-Content -LiteralPath (Join-Path $protectedDir 'self.sha256') -Value $preSanitized -NoNewline
Write-Info "Embedded launcher hash: $preSanitized"

# --- Step 4: Patch launchers with embedded hash -----------------------
Write-Stage "Patch launcher payloads"
$embedArgs = @($preSanitized, $exePath, $protectExe)
Run-Quiet -Command $embedTool -Args $embedArgs

# --- Step 4b: Embed client key (if provided) --------------------------
if ($ResolvedClientKey) {
    Write-Stage "Embed client key"
    Run-Quiet -Command $embedKeyExe -Args @($ResolvedClientKey, $preSanitized, $exePath)
}

# --- Step 5: Re-hash after embed for sanity ---------------------------
Write-Stage "Compute launcher hash (post-embed)"
$postOut = Run-Quiet -Command $hashTool -Args @($exePath) -PassThruOutput
$postSanitized = ($postOut -join "`n").Trim().ToLowerInvariant()
Write-Info "Sanitized hash (post-embed): $postSanitized"
if ($postSanitized -ne $preSanitized) {
    throw "post-embed hash ($postSanitized) does not match pre-embed hash ($preSanitized)"
}

# --- Step 6: Seal protected modules -----------------------------------
Write-Stage "Seal protected modules"

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$protectArgs = @('--out', "$OutDir")
if ($ResolvedClientKey) {
    $protectArgs += @('--client-key', $ResolvedClientKey)
    if ($ClientId) {
        $protectArgs += @('--client-id', $ClientId)
    }
}

Run-Quiet -Command $protectExe -Args $protectArgs

# --- Done --------------------------------------------------------------
Write-Success "Protected payloads ready at $OutDir"
