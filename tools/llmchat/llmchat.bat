@echo off
rem ============================================================
rem  llmchat.bat - Windows launcher for halo-ubuntu llama-server
rem  Double-click to start chatting. First run asks for the API key once.
rem
rem  Usage:  llmchat.bat                 interactive chat
rem          llmchat.bat -Fast "question" one-shot, no thinking
rem          llmchat.bat update          re-download the latest client
rem          llmchat.bat resetkey        enter the API key again
rem
rem  NOTE: keep this file ASCII-only. Korean text in .bat breaks (CP949).
rem ============================================================
setlocal
set "DIR=%~dp0"
set "PS1=%DIR%llmchat.ps1"
set "SRC=https://raw.githubusercontent.com/genishs/llmmodelforreact/main/tools/llmchat/llmchat.ps1"
if not defined LLM_URL set "LLM_URL=http://192.168.234.209:8080"

if /i "%~1"=="update" (
  del "%PS1%" 2>nul
  shift
)
if /i "%~1"=="resetkey" (
  set "LLM_KEY="
  shift
)

if exist "%PS1%" goto haveclient
echo Downloading client ...
powershell -NoProfile -Command "try { Invoke-WebRequest '%SRC%' -OutFile '%PS1%' -UseBasicParsing } catch { exit 1 }"
if errorlevel 1 (
  echo [ERROR] Download failed. Check internet access.
  pause
  exit /b 1
)
:haveclient

if defined LLM_KEY goto havekey
echo.
set /p "LLM_KEY=Enter API key (saved for next time): "
if not defined LLM_KEY (
  echo [ERROR] No key entered.
  pause
  exit /b 1
)
setx LLM_KEY "%LLM_KEY%" >nul
:havekey

echo Checking server %LLM_URL% ...
powershell -NoProfile -Command "try { $r = Invoke-WebRequest '%LLM_URL%/health' -UseBasicParsing -TimeoutSec 5; exit 0 } catch { exit 1 }"
if errorlevel 1 (
  echo [ERROR] Cannot reach %LLM_URL%
  echo         - Is the server on?  ^(on halo-ubuntu: ~/llm.sh start cn lan^)
  echo         - Same network?      ^(192.168.234.x^)
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -Url "%LLM_URL%" -Key "%LLM_KEY%" %1 %2 %3 %4 %5 %6
if "%~1"=="" pause
endlocal
