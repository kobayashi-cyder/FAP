@echo off
setlocal EnableExtensions
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RUN_FAP_CHAT_LATEST.ps1"
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
  echo.
  echo [ERROR] RUN_FAP_CHAT_LATEST failed with exit code %RC%.
  echo [INFO] The PowerShell launcher prints the actual Python startup error above.
  pause
)

exit /b %RC%
