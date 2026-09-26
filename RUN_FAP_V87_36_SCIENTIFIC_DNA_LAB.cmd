@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (
  start "FAP V87.36 DNA" /min py -3 "%~dp0fap_v87_36_scientific_dna_lab.py"
  goto :open
)
start "FAP V87.36 DNA" /min python "%~dp0fap_v87_36_scientific_dna_lab.py"
:open
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:11440/"
pause
