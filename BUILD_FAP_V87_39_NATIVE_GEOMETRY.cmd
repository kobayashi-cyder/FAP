@echo off
setlocal
cd /d "%~dp0"
set "PY="
where py >nul 2>nul
if %errorlevel%==0 set "PY=py -3"
if not defined PY (
  where python >nul 2>nul
  if %errorlevel%==0 set "PY=python"
)
if not defined PY (
  echo [ERROR] Python 3 not found.
  pause
  exit /b 1
)
%PY% "%~dp0releases\v87_39\native_geometry\build_native.py" --force
if errorlevel 1 (
  echo [WARN] Native geometry build failed. Fallback remains available.
  pause
  exit /b 1
)
echo [PASS] FAP V87.39 native geometry built.
pause
