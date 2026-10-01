@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  python main.py
) else (
  py -3 main.py
)
if errorlevel 1 pause
