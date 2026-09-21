@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "LATEST_VERSION=87.39-unified-chat"
set "PORT=11439"
set "EXISTING="

for /f "usebackq delims=" %%V in (`powershell.exe -NoProfile -Command "try { (Invoke-RestMethod -TimeoutSec 1 http://127.0.0.1:11439/api/v1/status).version } catch { '' }"`) do set "EXISTING=%%V"

if /I "%EXISTING%"=="%LATEST_VERSION%" (
  echo [OK] Latest FAP already running on port 11439: %EXISTING%
  start "" "http://127.0.0.1:11439/"
  exit /b 0
)

if not "%EXISTING%"=="" (
  echo [INFO] Stale FAP detected on port 11439: %EXISTING%
  echo [INFO] Replacing it with %LATEST_VERSION%...

  powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
    "$c=Get-NetTCPConnection -LocalPort 11439 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; if(-not $c){ exit 0 }; $p=Get-CimInstance Win32_Process -Filter ('ProcessId=' + $c.OwningProcess) -ErrorAction SilentlyContinue; $cmd=[string]$p.CommandLine; if($cmd -match '(?i)fap_.*gateway\.py'){ Stop-Process -Id $c.OwningProcess -Force -ErrorAction Stop; $deadline=(Get-Date).AddSeconds(3); while((Get-Date) -lt $deadline){ if(-not (Get-NetTCPConnection -LocalPort 11439 -State Listen -ErrorAction SilentlyContinue)){ exit 0 }; Start-Sleep -Milliseconds 100 }; exit 2 }; Write-Host ('[WARN] Port 11439 is not owned by a recognized FAP gateway: ' + $cmd); exit 3"

  if errorlevel 1 (
    echo [WARN] Could not safely replace the process on port 11439.
    echo [INFO] Latest FAP will use port 11441 instead.
    set "PORT=11441"
  ) else (
    set "EXISTING="
  )
)

set "PY="
where py >nul 2>nul
if %errorlevel%==0 set "PY=py -3"
if not defined PY (
  where python >nul 2>nul
  if %errorlevel%==0 set "PY=python"
)
if not defined PY (
  echo [ERROR] Python 3 not found.
  pause
  exit /b 1
)

if not exist "%~dp0releases\v87_38\native_raster\bin\fap_native_raster.dll" (
  %PY% "%~dp0releases\v87_38\native_raster\build_native.py" --quiet >nul 2>nul
)
if not exist "%~dp0releases\v87_39\native_geometry\bin\fap_native_geometry.dll" (
  %PY% "%~dp0releases\v87_39\native_geometry\build_native.py" --quiet >nul 2>nul
)

set "FAP_PORT=%PORT%"
start "FAP V87.39 Native Geometry" /min %PY% "%~dp0fap_v87_39_native_geometry_gateway.py"

powershell.exe -NoProfile -Command ^
  "$u='http://127.0.0.1:%PORT%/api/v1/status'; $d=(Get-Date).AddSeconds(15); while((Get-Date) -lt $d){ try { $s=Invoke-RestMethod -TimeoutSec 1 $u; if($s.version -eq '%LATEST_VERSION%'){ exit 0 } } catch {}; Start-Sleep -Milliseconds 75 }; exit 1"

if errorlevel 1 (
  echo [ERROR] Latest FAP did not report %LATEST_VERSION% within 15 seconds.
  echo [INFO] Check the minimized FAP process window for the startup error.
  pause
  exit /b 1
)

echo [OK] FAP CHAT is now %LATEST_VERSION% on port %PORT%.
start "" "http://127.0.0.1:%PORT%/"
exit /b 0
