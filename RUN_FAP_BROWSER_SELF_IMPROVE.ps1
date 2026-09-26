param(
    [string]$Goal = "",

    [string]$Branch = "",

    [string]$TargetRepo = "",

    [string[]]$PreferredPath = @(),

    [ValidateRange(1024, 65535)]
    [int]$Port = 9222,

    [string]$Profile = "$env:LOCALAPPDATA\FAP\browser-profile",

    [string]$RuntimeDir = "$env:LOCALAPPDATA\FAP\browser-runtime",

    [ValidateRange(0, 60)]
    [int]$WaitForLoginMinutes = 15,

    [ValidateRange(0, 3)]
    [int]$AutoRecoverCount = 1,

    [ValidateSet("google", "duckduckgo")]
    [string]$SearchEngine = "google",

    [switch]$NoWebSearch,

    [switch]$LoginOnly
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not $TargetRepo) {
    $TargetRepo = $PSScriptRoot
}
$TargetRepo = [System.IO.Path]::GetFullPath($TargetRepo)

function Find-Chrome {
    $candidates = @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }
    $cmd = Get-Command chrome.exe -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }
    throw "Google Chrome was not found."
}

function Test-CdpEndpoint([string]$Endpoint) {
    try {
        $info = Invoke-RestMethod "$Endpoint/json/version" -TimeoutSec 2
        return [bool]$info.webSocketDebuggerUrl
    } catch {
        return $false
    }
}

function Start-FapChrome(
    [string]$Chrome,
    [string]$ProfilePath,
    [int]$DebugPort,
    [string]$Endpoint
) {
    if (Test-CdpEndpoint $Endpoint) {
        return
    }

    $chromeArgs = @(
        "--remote-debugging-port=$DebugPort",
        "--user-data-dir=$ProfilePath",
        "--no-first-run",
        "--no-default-browser-check",
        "https://chatgpt.com/"
    )
    Start-Process -FilePath $Chrome -ArgumentList $chromeArgs | Out-Null

    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 500
        if (Test-CdpEndpoint $Endpoint) {
            return
        }
    }
    throw "Chrome DevTools endpoint did not become ready at $Endpoint."
}

function Invoke-BrowserPreflight(
    [string]$Endpoint,
    [int]$WaitSeconds,
    [string]$Engine
) {
    $preflightArgs = @(
        "fap_browser_preflight.py",
        "--cdp-url", $Endpoint,
        "--wait-sec", "$WaitSeconds",
        "--search-engine", $Engine
    )
    & python @preflightArgs
    return $LASTEXITCODE
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python was not found in PATH."
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git was not found in PATH."
}
if (-not $LoginOnly -and -not $Goal.Trim()) {
    throw "-Goal is required unless -LoginOnly is used."
}

if (-not $LoginOnly) {
    if (-not (Test-Path -LiteralPath (Join-Path $TargetRepo ".git"))) {
        throw "Target repository is not a Git checkout: $TargetRepo"
    }
    if (-not $Branch) {
        $Branch = (& git -C $TargetRepo branch --show-current).Trim()
    }
    if (-not $Branch) {
        throw "Could not determine the target Git branch. Pass -Branch explicitly."
    }
    if ($Branch -in @("main", "master")) {
        throw "FAP browser self-improvement must run on a side branch, not $Branch."
    }
}

& python -c "import playwright" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Playwright is required. Run: python -m pip install playwright"
}

$chrome = Find-Chrome
New-Item -ItemType Directory -Force -Path $Profile | Out-Null
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

$markerPath = Join-Path $Profile "FAP_BROWSER_PROFILE.json"
$marker = [ordered]@{
    version = "fap.browser.profile.1"
    port = $Port
    profile = $Profile
}
$marker | ConvertTo-Json | Set-Content -LiteralPath $markerPath -Encoding UTF8

$endpoint = "http://127.0.0.1:$Port"
Start-FapChrome $chrome $Profile $Port $endpoint

$waitSeconds = [int]($WaitForLoginMinutes * 60)

Write-Host "FAP browser backend: $endpoint"
Write-Host "Browser profile: $Profile"
Write-Host "Runtime state: $RuntimeDir"
if (-not $LoginOnly) {
    Write-Host "Target repository: $TargetRepo"
    Write-Host "Branch: $Branch"
}
Write-Host "Auto-recovery attempts: $AutoRecoverCount"
Write-Host ""
Write-Host "Checking ChatGPT Web readiness..."
Write-Host "If login is required, complete it in the visible FAP Chrome window."
Write-Host "The same command continues automatically after the composer appears."
Write-Host ""

$preflightCode = Invoke-BrowserPreflight $endpoint $waitSeconds $SearchEngine
if ($preflightCode -ne 0) {
    if ($preflightCode -eq 3) {
        Write-Error "ChatGPT login did not become ready before the login wait timeout."
    } else {
        Write-Error "Browser preflight failed with exit code $preflightCode."
    }
    exit $preflightCode
}

if ($LoginOnly) {
    Write-Host "FAP browser profile is ready for later autonomous runs."
    exit 0
}

$argsList = @(
    "fap_self_improvement_controller.py",
    "--backend", "browser",
    "--cdp-url", $endpoint,
    "--search-engine", $SearchEngine,
    "--runtime-dir", $RuntimeDir,
    "--wait-for-login-sec", "15",
    "--repo", $TargetRepo,
    "--goal", $Goal,
    "--branch", $Branch
)

if ($NoWebSearch) {
    $argsList += "--no-web-search"
}
foreach ($path in $PreferredPath) {
    if ($path) {
        $argsList += @("--preferred-path", $path)
    }
}

$recoveryAttempt = 0
while ($true) {
    Write-Host ""
    Write-Host "Starting browser-driven FAP self-improvement..."
    if ($recoveryAttempt -gt 0) {
        Write-Host "Recovery attempt: $recoveryAttempt / $AutoRecoverCount"
    }
    Write-Host ""

    & python @argsList
    $code = $LASTEXITCODE

    if ($code -ne 5 -or $recoveryAttempt -ge $AutoRecoverCount) {
        break
    }

    $recoveryAttempt += 1
    Write-Warning "Browser runtime failed. Re-establishing Chrome/CDP before one bounded retry."

    Start-FapChrome $chrome $Profile $Port $endpoint
    $preflightCode = Invoke-BrowserPreflight $endpoint $waitSeconds $SearchEngine
    if ($preflightCode -ne 0) {
        $code = $preflightCode
        break
    }
}

$statePath = Join-Path $RuntimeDir "state.json"
if (Test-Path -LiteralPath $statePath) {
    Write-Host ""
    Write-Host "Last runtime state:"
    Get-Content -LiteralPath $statePath
}

exit $code
