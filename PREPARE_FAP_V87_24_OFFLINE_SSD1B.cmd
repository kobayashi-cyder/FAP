@echo off
setlocal
cd /d "%~dp0"

echo FAP V87.24 Offline Bundle Preparation
echo.
echo This is the ONE-TIME connected preparation step.
echo It downloads the pinned Apache-2.0 SSD-1B A1111 checkpoint and local config files.
echo The checkpoint is verified against the pinned SHA-256 before FAP accepts it.
echo.
echo Source: segmind/SSD-1B
echo License identifier: Apache-2.0
echo Checkpoint: SSD-1B-A1111.safetensors
echo Expected SHA-256: 1895a00bfc769a00b0c0c43a95e433e79e9db8a85402b45a33e8448785bde94d
echo.
choice /C YN /M "Have you reviewed and accepted the model license/terms"
if errorlevel 2 exit /b 1

where py >nul 2>&1
if not errorlevel 1 goto :py
where python >nul 2>&1
if not errorlevel 1 goto :python

echo [ERROR] Python 3 not found.
pause
exit /b 1

:py
py -3 -m pip install --upgrade huggingface_hub
if errorlevel 1 goto :fail
py -3 "%~dp0prepare_fap_v87_24_offline_bundle.py" --accept-license
if errorlevel 1 goto :fail
goto :done

:python
python -m pip install --upgrade huggingface_hub
if errorlevel 1 goto :fail
python "%~dp0prepare_fap_v87_24_offline_bundle.py" --accept-license
if errorlevel 1 goto :fail
goto :done

:done
echo.
echo [FAP] Offline model bundle prepared and checksum verified.
echo [FAP] You may now disconnect the network before inference.
echo.
pause
exit /b 0

:fail
echo.
echo [ERROR] Bundle preparation failed. FAP will not mark the model offline-ready.
pause
exit /b 1
