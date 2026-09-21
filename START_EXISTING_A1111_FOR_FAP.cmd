@echo off
setlocal
cd /d "%~dp0"

echo [FAP] Searching common folders for an existing Stable Diffusion WebUI / Forge installation...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$roots=@($env:USERPROFILE+'\stable-diffusion-webui',$env:USERPROFILE+'\stable-diffusion-webui-forge',$env:USERPROFILE+'\Downloads\stable-diffusion-webui',$env:USERPROFILE+'\Downloads\stable-diffusion-webui-forge',$env:USERPROFILE+'\Desktop\stable-diffusion-webui',$env:USERPROFILE+'\Desktop\stable-diffusion-webui-forge');" ^
  "$found=$null; foreach($r in $roots){$p=Join-Path $r 'webui-user.bat'; if(Test-Path $p){$found=$p; break}};" ^
  "if($found){Write-Host '[FAP] Found:' $found; $dir=Split-Path $found; Start-Process cmd.exe -WorkingDirectory $dir -ArgumentList '/k','set COMMANDLINE_ARGS=--api && call webui-user.bat'} else {Write-Host '[FAP] No existing A1111/Forge webui-user.bat was found in common folders.'; exit 2}"

if errorlevel 2 (
  echo.
  echo No existing local diffusion installation was found.
  echo Install or place AUTOMATIC1111 / Forge locally, then rerun this launcher.
  echo FAP itself does not silently download multi-GB model weights.
)

pause
