@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Create .venv and install requirements.txt first, or download a FULL/LITE release.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -X utf8 "app.py"
