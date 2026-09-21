@echo off
setlocal
cd /d "%~dp0"

set "PORT=11439"
set "EXISTING="
for /f "usebackq delims=" %%V in (`powershell.exe -NoProfile -Command "try { (Invoke-RestMethod -TimeoutSec 1 http://127.0.0.1:11439/api/v1/status).version } catch { ''}"`) do set "EXISTING=%%V"

if /I "%EXISTING%"=="87.38-unified-chat" (
  start "" "http://127.0.0.1:11439/"
  exit /b 0
)
if not "%EXISTING%"=="" (
  echo Existing FAP Core detected on port 11439: %EXISTING%
  echo Starting latest FAP on port 11441 instead.
  set "PORT=11441"
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
  echo Building V87.38 native raster if a C compiler is available...
  %PY% "%~dp0releases\v87_38\native_raster\build_native.py" --quiet >nul 2>nul
)

set "FAP_PORT=%PORT%"
start "FAP V87.38 Native" /min %PY% "%~dp0fap_v87_38_native_unified_chat_gateway.py"

powershell.exe -NoProfile -Command ^
  "$u='http://127.0.0.1:%PORT%/api/v1/status'; $d=(Get-Date).AddSeconds(15); while((Get-Date) -lt $d){ try { $s=Invoke-RestMethod -TimeoutSec 1 $u; if($s.version -eq '87.38-unified-chat'){ exit 0 } } catch {}; Start-Sleep -Milliseconds 75 }; exit 1"

if errorlevel 1 (
  echo [WARN] FAP did not report ready within 15 seconds.
) else (
  start "" "http://127.0.0.1:%PORT%/"
)
exit /b 0
