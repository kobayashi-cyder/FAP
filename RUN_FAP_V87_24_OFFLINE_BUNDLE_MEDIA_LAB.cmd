@echo off
setlocal
cd /d "%~dp0"

set "HF_HUB_OFFLINE=1"
set "TRANSFORMERS_OFFLINE=1"
set "HF_HUB_DISABLE_TELEMETRY=1"
set "DO_NOT_TRACK=1"
set "FAP_OFFLINE_SINGLE_FILES=%~dp0models\fap\ssd1b\SSD-1B-A1111.safetensors"

if not exist "%FAP_OFFLINE_SINGLE_FILES%" (
  echo [ERROR] Offline SSD-1B bundle not found.
  echo Run PREPARE_FAP_V87_24_OFFLINE_SSD1B.cmd once while connected.
  pause
  exit /b 1
)

where py >nul 2>&1
if not errorlevel 1 (
  py -3 "%~dp0prepare_fap_v87_24_offline_bundle.py" --verify-only
  if errorlevel 1 goto :bad
  start "FAP V87.24 Offline Bundle Media Lab" /min py -3 "%~dp0fap_v87_23_compact_offline_media_lab.py"
  goto :open
)

where python >nul 2>&1
if not errorlevel 1 (
  python "%~dp0prepare_fap_v87_24_offline_bundle.py" --verify-only
  if errorlevel 1 goto :bad
  start "FAP V87.24 Offline Bundle Media Lab" /min python "%~dp0fap_v87_23_compact_offline_media_lab.py"
  goto :open
)

echo [ERROR] Python 3 not found.
pause
exit /b 1

:open
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:11440/"
echo.
echo FAP offline bundle verified. Media Lab is running with network fallback disabled.
echo UI: http://127.0.0.1:11440/
echo.
pause
exit /b 0

:bad
echo [ERROR] Offline bundle integrity verification failed. Inference was not started.
pause
exit /b 1
