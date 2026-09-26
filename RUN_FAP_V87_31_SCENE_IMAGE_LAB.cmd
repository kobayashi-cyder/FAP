@echo off
setlocal
cd /d "%~dp0"

set "HF_HUB_OFFLINE=1"
set "TRANSFORMERS_OFFLINE=1"
set "HF_HUB_DISABLE_TELEMETRY=1"
set "DO_NOT_TRACK=1"

where py >nul 2>&1
if not errorlevel 1 (
  start "FAP V87.31 Scene Image Lab" /min py -3 "%~dp0fap_v87_31_scene_image_lab.py"
  goto :open
)
where python >nul 2>&1
if not errorlevel 1 (
  start "FAP V87.31 Scene Image Lab" /min python "%~dp0fap_v87_31_scene_image_lab.py"
  goto :open
)

echo [ERROR] Python 3 not found.
pause
exit /b 1

:open
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:11440/"
echo FAP V87.31 Scene Image Lab is running.
pause
