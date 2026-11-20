@echo off
rem Fetch the latest version of the port and rebuild it. Keeps your game
rem files, settings and saves. See tools\update.ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\update.ps1"
