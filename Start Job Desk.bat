@echo off
rem Double-click to open Job Desk. It runs without a console window and stops when you close the app.
cd /d "%~dp0"
where pythonw >nul 2>nul
if errorlevel 1 (
  echo Python is not installed on this computer.
  echo Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH" in the installer.
  pause
  exit /b 1
)
start "" pythonw app.py
