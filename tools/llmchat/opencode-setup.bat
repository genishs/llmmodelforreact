@echo off
rem ============================================================
rem  opencode-setup.bat - install opencode and connect it to halo-ubuntu
rem  Double-click. Safe to run again (re-installs, backs up config).
rem  NOTE: ASCII-only on purpose (Korean in .bat breaks under CP949).
rem ============================================================
setlocal
set "PS1=%TEMP%\opencode-setup.ps1"
set "SRC=https://raw.githubusercontent.com/genishs/llmmodelforreact/main/tools/llmchat/opencode-setup.ps1"
echo Downloading installer ...
powershell -NoProfile -Command "try { [Net.ServicePointManager]::SecurityProtocol='Tls12'; Invoke-WebRequest '%SRC%' -OutFile '%PS1%' -UseBasicParsing } catch { exit 1 }"
if errorlevel 1 (
  echo [ERROR] Could not download the installer. Check internet access.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" %*
pause
endlocal
