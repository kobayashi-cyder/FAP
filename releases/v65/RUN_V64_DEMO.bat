@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%"
python examples\run_v64_demo.py
