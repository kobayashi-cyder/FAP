@echo off
setlocal
cd /d "%~dp0"

set "HF_HUB_OFFLINE=1"
set "TRANSFORMERS_OFFLINE=1"
set "HF_HUB_DISABLE_TELEMETRY=1"
set "DO_NOT_TRACK=1"

if not defined FAP_MEDIA_LAB_PORT set "FAP_MEDIA_LAB_PORT=11440"
if not defined FAP_MEDIA_LAB_HOST set "FAP_MEDIA_LAB_HOST=127.0.0.1"

where py >nul 2>&1
if not errorlevel 1 goto :run_py
where python >nul 2>&1
if not errorlevel 1 goto :run_python

echo [ERROR] Python 3 was not found.
pause
exit /b 1

:run_py
start "FAP V87.23 Compact Offline Media Lab" /min py -3 "%~dp0fap_v87_23_compact_offline_media_lab.py"
goto :open

:run_python
start "FAP V87.23 Compact Offline Media Lab" /min python "%~dp0fap_v87_23_compact_offline_media_lab.py"

:open
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:%FAP_MEDIA_LAB_PORT%/"

echo.
echo FAP V87.23 Compact Offline Media Lab started.
echo UI: http://127.0.0.1:%FAP_MEDIA_LAB_PORT%/
echo Network fallback: disabled.
echo It auto-detects sidecar-approved checkpoints in common A1111/Forge model folders.
echo Qwen is not used.
echo.
pause
