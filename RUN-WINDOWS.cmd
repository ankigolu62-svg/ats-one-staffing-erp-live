@echo off
setlocal
cd /d "%~dp0"
where pwsh.exe >nul 2>nul
if %errorlevel%==0 (
  pwsh.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RUN-WINDOWS.ps1"
) else (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RUN-WINDOWS.ps1"
)
if errorlevel 1 (
  echo.
  echo ATS One failed to start. Review the error above.
  pause
  exit /b 1
)
