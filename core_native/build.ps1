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

# --- Path resolution --------------------------------------------------
Write-Stage "Resolve paths"

$root      = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$nativeDir = Join-Path $root 'core_native'

if (-not $OutDir -or [string]::IsNullOrWhiteSpace($OutDir)) {
    $OutDir = Join-Path $root 'build/protected'
} else {
    $OutDir = [System.IO.Path]::GetFullPath($OutDir)
}

$targetDir  = Join-Path $nativeDir 'target'
$releaseDir = Join-Path $targetDir 'release'
$exePath    = Join-Path $releaseDir 'core_native.exe'
$hashTool   = Join-Path $releaseDir 'selfhash.exe'
$embedTool  = Join-Path $releaseDir 'embedhash.exe'
$protectExe = Join-Path $releaseDir 'protect.exe'
$protectedDir = Join-Path $nativeDir 'protected'

Write-Info "root:        $root"
Write-Info "nativeDir:   $nativeDir"
Write-Info "outDir:      $OutDir"

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

Run-Quiet -Command $protectExe -Args @('--out', "$OutDir")

# --- Done --------------------------------------------------------------
Write-Success "Protected payloads ready at $OutDir"
