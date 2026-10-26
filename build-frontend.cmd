@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0frontend"
call npm ci
if errorlevel 1 exit /b 1
call npm run build
exit /b %errorlevel%
