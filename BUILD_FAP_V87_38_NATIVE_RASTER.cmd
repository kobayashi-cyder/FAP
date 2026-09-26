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

%PY% "%~dp0releases\v87_38\native_raster\build_native.py" --force
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo [WARN] Native build failed. V87.37 Python fallback remains available.
  pause
  exit /b %RC%
)

echo.
echo [PASS] FAP V87.38 native raster built.
pause
exit /b 0
