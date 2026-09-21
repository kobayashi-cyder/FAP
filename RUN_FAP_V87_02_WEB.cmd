@echo off
setlocal
cd /d "%~dp0"

if not defined FAP_PORT set "FAP_PORT=11439"
if not defined FAP_HOST set "FAP_HOST=127.0.0.1"
if not defined FAP_MODEL set "FAP_MODEL=gemma4:e2b"

where py >nul 2>&1
if not errorlevel 1 (
  start "" "http://%FAP_HOST%:%FAP_PORT%/"
  py -3 "%~dp0fap_v87_02_gateway.py"
  exit /b %errorlevel%
)

where python >nul 2>&1
if not errorlevel 1 (
  start "" "http://%FAP_HOST%:%FAP_PORT%/"
  python "%~dp0fap_v87_02_gateway.py"
  exit /b %errorlevel%
)

echo [ERROR] Python 3 was not found.
pause
exit /b 1
