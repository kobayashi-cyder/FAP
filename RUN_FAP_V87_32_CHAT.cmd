@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 fap_v87_32_unified_chat_gateway.py
) else (
  python fap_v87_32_unified_chat_gateway.py
)
endlocal
