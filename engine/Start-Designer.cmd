@echo off
setlocal EnableExtensions
title Krypton designer
cd /d "%~dp0"

echo Starting Krypton on this PC...
echo If a red error appears, take a photo of this window.
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-Designer.ps1"
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" (
  echo.
  echo Designer stopped with an error.
  pause
)
exit /b %EXITCODE%
