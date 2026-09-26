param(
    [Parameter(Mandatory = $true)]
    [string]$Goal,

    [string]$Branch = "",

    [string[]]$PreferredPath = @(),

    [int]$Port = 9222,

    [string]$Profile = "$env:LOCALAPPDATA\FAP\browser-profile",

    [ValidateSet("google", "duckduckgo")]
    [string]$SearchEngine = "google"
)

$ErrorActionPreference = "Stop"

function Find-Chrome {
    $candidates = @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return $candidate
        }
    }
    $cmd = Get-Command chrome.exe -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }
    throw "Google Chrome was not found."
}

if (-not $Branch) {
    $Branch = (& git branch --show-current).Trim()
}
if (-not $Branch) {
    throw "Could not determine the current Git branch. Pass -Branch explicitly."
}
if ($Branch -in @("main", "master")) {
    throw "FAP browser self-improvement must run on a side branch, not $Branch."
}

& python -c "import playwright" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Playwright is required. Run: python -m pip install playwright"
}

$chrome = Find-Chrome
New-Item -ItemType Directory -Force -Path $Profile | Out-Null

$endpoint = "http://127.0.0.1:$Port"
$ready = $false
try {
    Invoke-RestMethod "$endpoint/json/version" -TimeoutSec 2 | Out-Null
    $ready = $true
} catch {
    $ready = $false
}

if (-not $ready) {
    $chromeArgs = @(
        "--remote-debugging-port=$Port",
        "--user-data-dir=$Profile",
        "--no-first-run",
        "--no-default-browser-check",
        "https://chatgpt.com/"
    )
    Start-Process -FilePath $chrome -ArgumentList $chromeArgs | Out-Null

    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 500
        try {
            Invoke-RestMethod "$endpoint/json/version" -TimeoutSec 2 | Out-Null
            $ready = $true
            break
        } catch {
            $ready = $false
        }
    }
}

if (-not $ready) {
    throw "Chrome DevTools endpoint did not become ready at $endpoint."
}

$argsList = @(
    "fap_self_improvement_controller.py",
    "--backend", "browser",
    "--cdp-url", $endpoint,
    "--search-engine", $SearchEngine,
    "--goal", $Goal,
    "--branch", $Branch
)

foreach ($path in $PreferredPath) {
    if ($path) {
        $argsList += @("--preferred-path", $path)
    }
}

Write-Host "FAP browser backend: $endpoint"
Write-Host "Browser profile: $Profile"
Write-Host "Branch: $Branch"
Write-Host ""
Write-Host "If ChatGPT is not signed in, sign in manually in the opened FAP Chrome window once."
Write-Host ""

& python @argsList
exit $LASTEXITCODE
