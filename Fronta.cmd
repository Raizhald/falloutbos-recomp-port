@echo off
setlocal enabledelayedexpansion
title Fallout port - queue for Claude (closing this window stops the queue)
cd /d "%~dp0"
if not exist build\queue\done mkdir build\queue\done
echo Queue running. Runs the .cmd scripts Claude puts into build\queue.
echo Each job runs in its own process (no leftover variables) with a time limit
echo (1 hour, or "rem timeout=<seconds>" inside the job).
:loop
echo %date% %time% > build\queue\alive.txt
for %%f in (build\queue\*.cmd) do (
  set "JOB=%%~nxf"
  echo [!date! !time!] start !JOB! >> build\queue\queue.log
  echo [!date! !time!] start !JOB!
  move /y "%%f" "build\queue\done\!JOB!" >nul
  powershell -NoProfile -ExecutionPolicy Bypass -File tools\queue_run.ps1 "build\queue\done\!JOB!" >> build\queue\queue.log 2>&1
  echo [!date! !time!] end !JOB! exit !errorlevel! >> build\queue\queue.log
  cd /d "%~dp0"
)
timeout /t 15 /nobreak >nul
goto loop
