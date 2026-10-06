@echo off
setlocal
where pwsh.exe >nul 2>nul
if %errorlevel%==0 (
  pwsh.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0DEPLOY-FREE-LIVE.ps1"
) else (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0DEPLOY-FREE-LIVE.ps1"
)
set EC=%errorlevel%
if not "%EC%"=="0" (
  echo.
  echo ATS One live deploy failed. Review the exact gate above.
  pause
  exit /b %EC%
)
pause
