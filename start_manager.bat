@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Local Python environment is missing.
  echo Run this command with Python installed:
  echo   python -m venv .venv
  echo   .venv\Scripts\python.exe -m pip install -r requirements-manager.txt
  pause
  exit /b 1
)

".venv\Scripts\python.exe" manager.py --open
if errorlevel 1 pause
