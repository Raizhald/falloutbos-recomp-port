@echo off
rem Like Play.cmd, but always drawn on the graphics card (Direct3D 11),
rem whatever settings.ini says about the renderer. The other options
rem (resolution, v-sync, full screen, FPS limit) still come from settings.ini.
rem F11 or Alt+Enter toggles full screen.
setlocal
set FBOS_FORCE_GPU=1
call "%~dp0Play.cmd" %*
