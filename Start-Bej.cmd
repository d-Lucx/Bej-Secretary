@echo off
setlocal
if not exist "%~dp0.bej-local\venv\Scripts\python.exe" (
  echo Bej's local Python environment is missing. See README.md for setup.
  pause
  exit /b 1
)
if not exist "%~dp0dist-bej\bej.html" (
  echo Build the workspace first: npm run build:bej
  pause
  exit /b 1
)
"%~dp0.bej-local\venv\Scripts\python.exe" "%~dp0bej-companion\server.py"
