@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Please run INSTALL_WINDOWS.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" src\main.py %*
if errorlevel 1 pause
