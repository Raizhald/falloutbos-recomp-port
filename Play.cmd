@echo off
rem Start the recompiled game in a window. An XInput pad is player 1; mouse
rem and keyboard work too (keys in mkb.ini; Controls=Keyboard in settings.ini
rem gives the old keyboard-only layout: WASD, Z/X/C/V = A/B/X/Y, Enter = Start).
rem F11 or Alt+Enter toggles full screen.
rem Options come from settings.ini -- change them with Settings.cmd.
setlocal
cd /d "%~dp0"
if not exist settings.ini call :defaults
for /f "usebackq eol=; tokens=1,* delims==" %%a in ("settings.ini") do set "CFG_%%a=%%b"
if defined FBOS_FORCE_GPU set "CFG_Renderer=GPU"
set RECOMP_PB_EXEC=1
set RECOMP_FB_WINDOW=1
if not defined CFG_Controls set "CFG_Controls=MouseKeyboard"
set "RECOMP_KEYBOARD="
set "RECOMP_MKB="
if /i "%CFG_Controls%"=="Keyboard" (set "RECOMP_KEYBOARD=1") else (set "RECOMP_MKB=1" & set "RECOMP_MKB_INI=%CD%\mkb.ini")
if /i "%CFG_Renderer%"=="GPU" (set "RECOMP_GPU_BACKEND=0") else (set "RECOMP_GPU_BACKEND=")
if defined CFG_ResolutionScale set "RECOMP_GPU_SCALE=%CFG_ResolutionScale%"
if defined CFG_TextureFilter set "RECOMP_GPU_TEXFILTER=%CFG_TextureFilter%"
rem Silhouette=1: the player shows through walls as a coloured outline.
set "RECOMP_SILHOUETTE="
if not defined CFG_Silhouette set "CFG_Silhouette=1"
if "%CFG_Silhouette%"=="1" set "RECOMP_SILHOUETTE=1"
rem AspectRatio 16:9 / 16:10 / 21:9 shows more of the world at the sides
rem (graphics card renderer only); 4:3 is the original picture.
set "RECOMP_WIDESCREEN="
if not defined CFG_AspectRatio set "CFG_AspectRatio=4:3"
if /i "%CFG_Renderer%"=="GPU" if not "%CFG_AspectRatio%"=="4:3" set "RECOMP_WIDESCREEN=%CFG_AspectRatio%"
rem Players=2 plugs a second controller into the console's port 2 for the
rem game's own two-player mode (Start New Game > Two Player): Xbox
rem controller 1 is player 1, controller 2 is player 2.
set "RECOMP_USB_PADS="
if "%CFG_Players%"=="2" set "RECOMP_USB_PADS=2"
if defined CFG_VSync set "RECOMP_VSYNC=%CFG_VSync%"
if defined CFG_Fullscreen set "RECOMP_FULLSCREEN=%CFG_Fullscreen%"
if defined CFG_WindowScale set "RECOMP_WINDOW_SCALE=%CFG_WindowScale%"
if "%CFG_FPSLimit%"=="0" (set "RECOMP_FPS_LIMIT=") else if defined CFG_FPSLimit set "RECOMP_FPS_LIMIT=%CFG_FPSLimit%"
if "%CFG_Mute%"=="1" set "RECOMP_AUDIO_MUTE=1"
rem Every run writes its output to logs\last-run.log (the run before is kept as
rem previous-run.log) -- send that file along when the game misbehaves.
if not exist logs mkdir logs
if exist logs\last-run.log move /y logs\last-run.log logs\previous-run.log >nul
bin\fbos.exe %* > logs\last-run.log 2>&1
exit /b %errorlevel%

:defaults
> settings.ini (
  echo ; Fallout: Brotherhood of Steel - game settings. Change them with Settings.cmd.
  echo [Video]
  echo Renderer=GPU
  echo ResolutionScale=2
  echo TextureFilter=2
  echo AspectRatio=4:3
  echo Silhouette=1
  echo VSync=1
  echo Fullscreen=0
  echo WindowScale=2
  echo FPSLimit=60
  echo [Input]
  echo Controls=MouseKeyboard
  echo Players=1
  echo [Audio]
  echo Mute=0
)
exit /b 0
