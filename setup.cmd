@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
py -3.12 --version >nul 2>nul
if not errorlevel 1 (
  set "TOOL_CENTER_PY=-3.12"
  goto create_venv
)
py -3.11 --version >nul 2>nul
if not errorlevel 1 (
  set "TOOL_CENTER_PY=-3.11"
  goto create_venv
)
echo Please install Python 3.12 or 3.11 with Tk and the Python Launcher, then run setup.cmd again.
pause
exit /b 1
:create_venv
py %TOOL_CENTER_PY% -m venv .venv
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install -r requirements.txt
exit /b %errorlevel%
