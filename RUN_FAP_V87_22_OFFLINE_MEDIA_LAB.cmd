@echo off
setlocal
cd /d "%~dp0"

set "HF_HUB_OFFLINE=1"
set "TRANSFORMERS_OFFLINE=1"
set "HF_HUB_DISABLE_TELEMETRY=1"
set "DO_NOT_TRACK=1"

if not defined FAP_MEDIA_LAB_PORT set "FAP_MEDIA_LAB_PORT=11440"
if not defined FAP_MEDIA_LAB_HOST set "FAP_MEDIA_LAB_HOST=127.0.0.1"

if not defined FAP_OFFLINE_MODEL_DIRS (
  echo [FAP] FAP_OFFLINE_MODEL_DIRS is not set.
  echo [FAP] Point it to one or more already-downloaded local Diffusers model folders.
  echo [FAP] Each folder must contain model_index.json and fap_model_manifest.json.
  echo.
)

where py >nul 2>&1
if not errorlevel 1 goto :run_py
where python >nul 2>&1
if not errorlevel 1 goto :run_python

echo [ERROR] Python 3 was not found.
pause
exit /b 1

:run_py
start "FAP V87.22 Offline Media Lab" /min py -3 "%~dp0fap_v87_22_offline_media_lab.py"
goto :open

:run_python
start "FAP V87.22 Offline Media Lab" /min python "%~dp0fap_v87_22_offline_media_lab.py"

:open
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:%FAP_MEDIA_LAB_PORT%/"

echo.
echo FAP V87.22 Offline Media Lab started.
echo UI: http://127.0.0.1:%FAP_MEDIA_LAB_PORT%/
echo Network fallback: disabled.
echo Qwen: not used.
echo.
pause
