@echo off
rem Opens the settings window (writes settings.ini, used by Play.cmd).
start "" powershell -NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File "%~dp0tools\settings_gui.ps1"
