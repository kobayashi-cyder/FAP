@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 fap_v87_27_physics_knowledge_gateway.py
) else (
  python fap_v87_27_physics_knowledge_gateway.py
)
endlocal
