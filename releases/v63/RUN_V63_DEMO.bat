@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%"
python examples\run_v63_activation_rollback_demo.py
