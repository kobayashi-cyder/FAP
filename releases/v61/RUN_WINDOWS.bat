@echo off
setlocal
cd /d %~dp0
python -m compileall -q fap_autonomy || exit /b 1
python -m unittest discover -s tests -v || exit /b 1
python -m fap_autonomy.cli benchmarks\dev_results.jsonl --out capability_report.json || exit /b 1
echo.
echo PASS - report: capability_report.json
endlocal
