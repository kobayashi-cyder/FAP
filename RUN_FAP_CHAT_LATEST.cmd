@echo off
setlocal
cd /d "%~dp0"

set "PORT=11439"
set "EXISTING="
for /f "usebackq delims=" %%V in (`powershell.exe -NoProfile -Command "try { (Invoke-RestMethod -TimeoutSec 1 http://127.0.0.1:11439/api/v1/status).version } catch { ''}"`) do set "EXISTING=%%V"

if /I "%EXISTING%"=="87.37-unified-chat" (
  start "" "http://127.0.0.1:11439/"
  exit /b 0
)

if not "%EXISTING%"=="" (
  echo Existing FAP Core detected on port 11439: %EXISTING%
  echo Starting latest FAP on port 11441 instead.
  set "PORT=11441"
)

set "FAP_PORT=%PORT%"
where py >nul 2>nul
if %errorlevel%==0 (
  start "FAP V87.37 Sparse" /min py -3 "%~dp0fap_v87_37_sparse_unified_chat_gateway.py"
) else (
  start "FAP V87.37 Sparse" /min python "%~dp0fap_v87_37_sparse_unified_chat_gateway.py"
)

powershell.exe -NoProfile -Command ^
  "$u='http://127.0.0.1:%PORT%/api/v1/status'; $d=(Get-Date).AddSeconds(12); while((Get-Date) -lt $d){ try { $s=Invoke-RestMethod -TimeoutSec 1 $u; if($s.version -eq '87.37-unified-chat'){ exit 0 } } catch {}; Start-Sleep -Milliseconds 75 }; exit 1"

if errorlevel 1 (
  echo [WARN] FAP did not report ready within 12 seconds.
) else (
  start "" "http://127.0.0.1:%PORT%/"
)
exit /b 0
