@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%"
python -m unittest discover -s tests -v
