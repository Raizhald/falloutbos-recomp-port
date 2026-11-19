@echo off
rem Like Play.cmd, but drawn on the GPU (Direct3D 11) and paced to 60 FPS.
rem The picture goes straight from the GPU to the window, with vsync.
rem F11 or Alt+Enter = full screen. RECOMP_FULLSCREEN=1 starts full screen.
set RECOMP_GPU_BACKEND=0
set RECOMP_FPS_LIMIT=60
call "%~dp0Play.cmd" %*
