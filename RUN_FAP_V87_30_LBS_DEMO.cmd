@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (
  py -3 "%~dp0fap_v87_30_lbs_demo.py"
  goto :done
)
python "%~dp0fap_v87_30_lbs_demo.py"
:done
pause
