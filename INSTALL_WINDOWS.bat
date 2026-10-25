@echo off
setlocal
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto error
echo.
echo Ready. Run RUN_WINDOWS.bat to open RetroRip.
echo FFmpeg must be installed and available on PATH for MP3 and video merging.
pause
exit /b 0
:error
echo Installation failed. Install Python 3.10 or newer, then try again.
pause
exit /b 1
