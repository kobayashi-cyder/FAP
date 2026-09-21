@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 fap_v87_28_physics_solver_gateway.py
) else (
  python fap_v87_28_physics_solver_gateway.py
)
endlocal
