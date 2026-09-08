@echo off
setlocal EnableExtensions
title Krypton designer
cd /d "%~dp0.."

net session >nul 2>&1
if errorlevel 1 (
  echo Krypton can export a setup without administrator rights.
  echo Installing on this PC later will ask for elevation.
)

where py >nul 2>&1
if %errorlevel%==0 (
  py -3 -m krypton serve
  goto :eof
)

where python >nul 2>&1
if %errorlevel%==0 (
  python -m krypton serve
  goto :eof
)

echo Python 3 was not found. Install Python from https://www.python.org/downloads/
echo then re-run Start-Krypton.cmd to open the designer.
echo.
echo You can still run an already exported bundle with Install.cmd.
pause
