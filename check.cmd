@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
 ".venv\Scripts\python.exe" -B check.py
) else (
 py -3 -B check.py
)
set "APP_EXIT=%errorlevel%"
if not "%APP_EXIT%"=="0" pause
exit /b %APP_EXIT%
