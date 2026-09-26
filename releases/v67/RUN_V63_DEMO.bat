@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"
python examples\run_v63_demo.py
exit /b %ERRORLEVEL%
