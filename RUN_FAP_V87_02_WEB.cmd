@echo off
setlocal
cd /d "%~dp0"

if not defined FAP_PORT set "FAP_PORT=11439"
if not defined FAP_HOST set "FAP_HOST=127.0.0.1"
if not defined FAP_MODEL set "FAP_MODEL=gemma4:e2b"

set "PYRUN="
where py >nul 2>&1
if not errorlevel 1 set "PYRUN=py -3"
if not defined PYRUN (
  where python >nul 2>&1
  if not errorlevel 1 set "PYRUN=python"
)

if not defined PYRUN (
  echo [ERROR] Python 3 was not found.
  pause
  exit /b 1
)

echo [FAP] Starting V87.02 Core on http://127.0.0.1:%FAP_PORT%/
start "FAP V87.02 Core" /min cmd /c "%PYRUN% "%~dp0fap_v87_02_gateway.py""

where adb >nul 2>&1
if not errorlevel 1 (
  adb start-server >nul 2>&1
  adb reverse tcp:%FAP_PORT% tcp:%FAP_PORT% >nul 2>&1
  if not errorlevel 1 (
    echo [FAP] Android loopback bridge ready: tcp:%FAP_PORT%
  ) else (
    echo [FAP] ADB reverse was not established. Connect/authorize one Android device and retry.
  )
)

timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:%FAP_PORT%/"

echo.
echo FAP V87.02 is running.
echo PC:      http://127.0.0.1:%FAP_PORT%/
echo Android: http://127.0.0.1:%FAP_PORT%/  ^(with adb reverse^)
echo Downloaded FAP_Chat.html can also use this loopback endpoint.
echo.
pause
