@echo off
setlocal
cd /d "%~dp0"

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
start "FAP V87.20 Media Lab" /min py -3 "%~dp0fap_v87_20_media_lab.py"
goto :open

:run_python
start "FAP V87.20 Media Lab" /min python "%~dp0fap_v87_20_media_lab.py"

:open
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:%FAP_MEDIA_LAB_PORT%/"

echo.
echo FAP V87.20 Media Lab is running.
echo UI: http://127.0.0.1:%FAP_MEDIA_LAB_PORT%/
echo.
echo Real generation requires compatible engine descriptors in FAP_MEDIA_ENGINES_JSON
echo and the referenced token environment variables.
echo Qwen is not used.
echo.
pause
