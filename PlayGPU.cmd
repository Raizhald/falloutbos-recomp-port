@echo off
rem Like Play.cmd, but drawn on the GPU (Direct3D 11) and paced to 60 FPS.
set RECOMP_GPU_BACKEND=0
set RECOMP_FPS_LIMIT=60
call "%~dp0Play.cmd" %*
