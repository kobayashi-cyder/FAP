@echo off
setlocal
cd /d "%~dp0"

if not defined FAP_MEDIA_LAB_PORT set "FAP_MEDIA_LAB_PORT=11440"
if not defined FAP_MEDIA_LAB_HOST set "FAP_MEDIA_LAB_HOST=127.0.0.1"

echo [FAP] Looking for an existing AUTOMATIC1111 / Forge API...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$urls=@('http://127.0.0.1:7860/sdapi/v1/sd-models','http://127.0.0.1:7861/sdapi/v1/sd-models');" ^
  "$ok=$false; foreach($u in $urls){try{$r=Invoke-RestMethod -Uri $u -TimeoutSec 2; if($null -ne $r){Write-Host '[FAP] Local image engine detected:' $u; $ok=$true; break}}catch{}};" ^
  "if(-not $ok){Write-Host '[FAP] Local API not detected yet. Media Lab will still start and keep auto-detect enabled.'}"

where py >nul 2>&1
if not errorlevel 1 goto :run_py
where python >nul 2>&1
if not errorlevel 1 goto :run_python

echo [ERROR] Python 3 was not found.
pause
exit /b 1

:run_py
start "FAP V87.21 Media Lab" /min py -3 "%~dp0fap_v87_21_media_lab.py"
goto :open

:run_python
start "FAP V87.21 Media Lab" /min python "%~dp0fap_v87_21_media_lab.py"

:open
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:%FAP_MEDIA_LAB_PORT%/"

echo.
echo FAP V87.21 Media Lab started.
echo UI: http://127.0.0.1:%FAP_MEDIA_LAB_PORT%/
echo.
echo If AUTOMATIC1111 or Forge is already running with API enabled on port 7860/7861,
echo FAP will discover it automatically and generate real PNG images.
echo.
pause
