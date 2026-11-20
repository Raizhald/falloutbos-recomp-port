@echo off
rem Start the recompiled game in a window. An XInput pad is player 1; the
rem keyboard also works (WASD, Z/X/C/V = A/B/X/Y, Enter = Start).
rem F11 or Alt+Enter toggles full screen.
rem Options come from settings.ini -- change them with Settings.cmd.
setlocal
cd /d "%~dp0"
if not exist settings.ini call :defaults
for /f "usebackq eol=; tokens=1,* delims==" %%a in ("settings.ini") do set "CFG_%%a=%%b"
if defined FBOS_FORCE_GPU set "CFG_Renderer=GPU"
set RECOMP_PB_EXEC=1
set RECOMP_FB_WINDOW=1
set RECOMP_KEYBOARD=1
if /i "%CFG_Renderer%"=="GPU" (set "RECOMP_GPU_BACKEND=0") else (set "RECOMP_GPU_BACKEND=")
if defined CFG_ResolutionScale set "RECOMP_GPU_SCALE=%CFG_ResolutionScale%"
if defined CFG_TextureFilter set "RECOMP_GPU_TEXFILTER=%CFG_TextureFilter%"
if defined CFG_VSync set "RECOMP_VSYNC=%CFG_VSync%"
if defined CFG_Fullscreen set "RECOMP_FULLSCREEN=%CFG_Fullscreen%"
if defined CFG_WindowScale set "RECOMP_WINDOW_SCALE=%CFG_WindowScale%"
if "%CFG_FPSLimit%"=="0" (set "RECOMP_FPS_LIMIT=") else if defined CFG_FPSLimit set "RECOMP_FPS_LIMIT=%CFG_FPSLimit%"
if "%CFG_Mute%"=="1" set "RECOMP_AUDIO_MUTE=1"
bin\fbos.exe %*
exit /b %errorlevel%

:defaults
> settings.ini (
  echo ; Fallout: Brotherhood of Steel - game settings. Change them with Settings.cmd.
  echo [Video]
  echo Renderer=GPU
  echo ResolutionScale=2
  echo TextureFilter=2
  echo VSync=1
  echo Fullscreen=0
  echo WindowScale=2
  echo FPSLimit=60
  echo [Audio]
  echo Mute=0
)
exit /b 0
