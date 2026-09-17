@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%"
python -m unittest discover -s ..\v62\tests -v
if errorlevel 1 exit /b %errorlevel%
python -m unittest discover -s tests -v
exit /b %errorlevel%
