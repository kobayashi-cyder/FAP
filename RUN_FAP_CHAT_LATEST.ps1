param(
    [int]$PreferredPort = 11439
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$LatestVersion = '87.54-unified-chat'
$Gateway = Join-Path $Root 'fap_v87_54_research_cycle_gateway.py'
$Runtime = Join-Path $Root 'runtime'
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null
$StdoutLog = Join-Path $Runtime 'fap_chat_latest.stdout.log'
$StderrLog = Join-Path $Runtime 'fap_chat_latest.stderr.log'

function Get-PythonCommand {
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        try {
            $real = (& $py.Source -3 -c "import sys; print(sys.executable)" 2>$null | Select-Object -First 1).Trim()
            if ($LASTEXITCODE -eq 0 -and $real -and (Test-Path $real)) {
                return [pscustomobject]@{ Exe = $real; Prefix = @() }
            }
        } catch {
        }
        return [pscustomobject]@{ Exe = $py.Source; Prefix = @('-3') }
    }
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        return [pscustomobject]@{ Exe = $python.Source; Prefix = @() }
    }
    throw 'Python 3 not found. Install Python 3 and ensure py.exe or python.exe is on PATH.'
}

function Get-FapVersion([int]$Port, [bool]$AllowLegacyStatus = $true) {
    try {
        $s = Invoke-RestMethod -TimeoutSec 2 -Uri ("http://127.0.0.1:{0}/api/v1/ready" -f $Port)
        if ($s.version) {
            return [string]$s.version
        }
    } catch {
    }

    if ($AllowLegacyStatus) {
        try {
            $s = Invoke-RestMethod -TimeoutSec 2 -Uri ("http://127.0.0.1:{0}/api/v1/status" -f $Port)
            return [string]$s.version
        } catch {
        }
    }
    return ''
}

function Get-Listener([int]$Port) {
    try {
        return Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop |
            Select-Object -First 1
    } catch {
        return $null
    }
}

function Wait-PortFree([int]$Port, [int]$Milliseconds = 3500) {
    $deadline = (Get-Date).AddMilliseconds($Milliseconds)
    do {
        if (-not (Get-Listener $Port)) { return $true }
        Start-Sleep -Milliseconds 100
    } while ((Get-Date) -lt $deadline)
    return $false
}

function Show-StartupLogs {
    if (Test-Path $StderrLog) {
        $err = Get-Content -Path $StderrLog -Tail 80 -ErrorAction SilentlyContinue
        if ($err) {
            Write-Host ''
            Write-Host '[STARTUP STDERR]'
            $err | ForEach-Object { Write-Host $_ }
        }
    }
    if (Test-Path $StdoutLog) {
        $out = Get-Content -Path $StdoutLog -Tail 40 -ErrorAction SilentlyContinue
        if ($out) {
            Write-Host ''
            Write-Host '[STARTUP STDOUT]'
            $out | ForEach-Object { Write-Host $_ }
        }
    }
}

if (-not (Test-Path $Gateway)) {
    Write-Host "[ERROR] Missing latest gateway: $Gateway"
    Write-Host '[INFO] Run: git pull --ff-only'
    exit 1
}

$Python = Get-PythonCommand
$Prefix = @($Python.Prefix)
Write-Host ("[INFO] Python: {0} {1}" -f $Python.Exe, ($Prefix -join ' '))

$Candidates = @($PreferredPort, 11441, 11443, 11445, 11447) | Select-Object -Unique
$Port = $null

foreach ($candidate in $Candidates) {
    $version = Get-FapVersion $candidate
    if ($version -eq $LatestVersion) {
        $url = "http://127.0.0.1:$candidate/"
        Write-Host "[OK] Latest FAP CHAT is already running: $LatestVersion"
        Write-Host "[OK] $url"
        Start-Process $url
        exit 0
    }

    $listener = Get-Listener $candidate
    if (-not $listener) {
        $Port = $candidate
        break
    }

    $pidValue = [int]$listener.OwningProcess
    $procInfo = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $pidValue) -ErrorAction SilentlyContinue
    $cmd = if ($procInfo) { [string]$procInfo.CommandLine } else { '' }

    if ($cmd -match '(?i)fap_.*gateway\.py') {
        Write-Host "[INFO] Stale/hung FAP owns port $candidate (PID $pidValue). Replacing it."
        try {
            Stop-Process -Id $pidValue -Force -ErrorAction Stop
        } catch {
            Write-Host "[WARN] Could not stop PID $pidValue. Trying another port."
            continue
        }
        if (Wait-PortFree $candidate) {
            $Port = $candidate
            break
        }
        Write-Host "[WARN] Port $candidate did not become free. Trying another port."
        continue
    }

    if ($version) {
        Write-Host "[INFO] Port $candidate is serving FAP $version but its process could not be safely replaced."
    } else {
        Write-Host "[INFO] Port $candidate is occupied by another process (PID $pidValue)."
    }
}

if ($null -eq $Port) {
    $tcp = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $tcp.Start()
    $Port = ([System.Net.IPEndPoint]$tcp.LocalEndpoint).Port
    $tcp.Stop()
    Write-Host "[INFO] Using dynamically selected port $Port."
}

$Build38 = Join-Path $Root 'releases\v87_38\native_raster\build_native.py'
$Build39 = Join-Path $Root 'releases\v87_39\native_geometry\build_native.py'
foreach ($build in @($Build38, $Build39)) {
    if (Test-Path $build) {
        & $Python.Exe @Prefix $build '--quiet'
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[WARN] Native build unavailable for $build; preserved Python fallback will be used."
        }
    }
}

$oldPort = $env:FAP_PORT
$env:FAP_PORT = [string]$Port
try {
    Write-Host "[INFO] Preflight: validating latest chat stack..."
    & $Python.Exe @Prefix '-c' "import fap_v87_54_research_cycle_gateway as g; s=g.CORE.chat_status(); print('[OK] preflight version=' + str(s.get('version',''))); raise SystemExit(0 if s.get('version') == '87.54-unified-chat' else 4)"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Latest FAP CHAT preflight failed with exit code $LASTEXITCODE."
        exit $LASTEXITCODE
    }

    Remove-Item $StdoutLog, $StderrLog -Force -ErrorAction SilentlyContinue

    $Arguments = @()
    $Arguments += $Prefix
    $Arguments += $Gateway

    Write-Host "[INFO] Starting FAP CHAT $LatestVersion on port $Port ..."
    $startParams = @{
        FilePath = $Python.Exe
        ArgumentList = $Arguments
        WorkingDirectory = $Root
        WindowStyle = 'Minimized'
        PassThru = $true
        RedirectStandardOutput = $StdoutLog
        RedirectStandardError = $StderrLog
    }
    $proc = Start-Process @startParams

    $deadline = (Get-Date).AddSeconds(30)
    do {
        Start-Sleep -Milliseconds 100

        $version = Get-FapVersion $Port $false
        if ($version -eq $LatestVersion) {
            $url = "http://127.0.0.1:$Port/"
            Write-Host "[OK] FAP CHAT is now $LatestVersion on port $Port."
            Write-Host "[OK] PID=$($proc.Id)"
            Write-Host "[OK] $url"
            Start-Process $url
            exit 0
        }

        if ($proc.HasExited) {
            Write-Host "[ERROR] FAP CHAT exited during startup with code $($proc.ExitCode)."
            Show-StartupLogs
            if ($proc.ExitCode -ne 0) { exit $proc.ExitCode }
            exit 1
        }
    } while ((Get-Date) -lt $deadline)

    Write-Host "[ERROR] Latest FAP did not report $LatestVersion within 30 seconds."
    Write-Host "[INFO] PID=$($proc.Id)"
    Show-StartupLogs
    exit 1
}
finally {
    if ($null -eq $oldPort) {
        Remove-Item Env:FAP_PORT -ErrorAction SilentlyContinue
    } else {
        $env:FAP_PORT = $oldPort
    }
}
