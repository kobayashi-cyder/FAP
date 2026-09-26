@echo off
setlocal
if "%~1"=="" (
  echo Usage: RUN_V61_FROM_V59_LOG.bat path\to\v59_verified_log.jsonl
  exit /b 2
)
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"
python -m fap_autonomy.v59_operational_cli "%~1" --state fap_v61_operational.sqlite3 --out reports\v61_capability_decision.json --request-queue skill_factory_inbox
endlocal
