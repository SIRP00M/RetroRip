@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Please run INSTALL_WINDOWS.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install pyinstaller
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --onedir --name RetroRip --paths src --add-data "src/assets;assets" --collect-all yt_dlp --collect-all yt_dlp_ejs src/main.py
if errorlevel 1 goto error
echo.
echo Created dist\RetroRip\RetroRip.exe. Share the entire RetroRip folder.
echo FFmpeg must still be installed on the target PC and available on PATH.
pause
exit /b 0
:error
echo Build failed. Read the error above.
pause
exit /b 1
