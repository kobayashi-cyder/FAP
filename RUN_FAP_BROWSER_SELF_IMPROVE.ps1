param(
    [string]$Goal = "",

    [string]$Branch = "",

    [string[]]$PreferredPath = @(),

    [ValidateRange(1024, 65535)]
    [int]$Port = 9222,

    [string]$Profile = "$env:LOCALAPPDATA\FAP\browser-profile",

    [string]$RuntimeDir = "$env:LOCALAPPDATA\FAP\browser-runtime",

    [ValidateRange(0, 60)]
    [int]$WaitForLoginMinutes = 15,

    [ValidateSet("google", "duckduckgo")]
    [string]$SearchEngine = "google",

    [switch]$NoWebSearch,

    [switch]$LoginOnly
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

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
        if (-not $info.webSocketDebuggerUrl) {
            return $false
        }
        return $true
    } catch {
        return $false
    }
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python was not found in PATH."
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git was not found in PATH."
}
if (-not (Test-Path -LiteralPath ".git")) {
    throw "Run this launcher from the FAP Git repository."
}
if (-not $LoginOnly -and -not $Goal.Trim()) {
    throw "-Goal is required unless -LoginOnly is used."
}

if (-not $Branch) {
    $Branch = (& git branch --show-current).Trim()
}
if (-not $Branch) {
    throw "Could not determine the current Git branch. Pass -Branch explicitly."
}
if (-not $LoginOnly -and $Branch -in @("main", "master")) {
    throw "FAP browser self-improvement must run on a side branch, not $Branch."
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
$ready = Test-CdpEndpoint $endpoint

if (-not $ready) {
    $chromeArgs = @(
        "--remote-debugging-port=$Port",
        "--user-data-dir=$Profile",
        "--no-first-run",
        "--no-default-browser-check",
        "https://chatgpt.com/"
    )
    Start-Process -FilePath $chrome -ArgumentList $chromeArgs | Out-Null

    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 500
        if (Test-CdpEndpoint $endpoint) {
            $ready = $true
            break
        }
    }
}

if (-not $ready) {
    throw "Chrome DevTools endpoint did not become ready at $endpoint."
}

$waitSeconds = [int]($WaitForLoginMinutes * 60)

Write-Host "FAP browser backend: $endpoint"
Write-Host "Browser profile: $Profile"
Write-Host "Runtime state: $RuntimeDir"
Write-Host "Branch: $Branch"
Write-Host ""
Write-Host "Checking ChatGPT Web readiness..."
Write-Host "If login is required, complete it in the visible FAP Chrome window."
Write-Host "The same command continues automatically after the composer appears."
Write-Host ""

$preflightArgs = @(
    "fap_browser_preflight.py",
    "--cdp-url", $endpoint,
    "--wait-sec", "$waitSeconds",
    "--search-engine", $SearchEngine
)
& python @preflightArgs
$preflightCode = $LASTEXITCODE

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

Write-Host ""
Write-Host "Starting browser-driven FAP self-improvement..."
Write-Host ""

& python @argsList
$code = $LASTEXITCODE

$statePath = Join-Path $RuntimeDir "state.json"
if (Test-Path -LiteralPath $statePath) {
    Write-Host ""
    Write-Host "Last runtime state:"
    Get-Content -LiteralPath $statePath
}

exit $code
