@echo off
chcp 65001 >nul
rem Double-click to start HerbMind v2 middleware (calls Git Bash -> start-infra.sh).
rem Command line usage:  start-infra.bat --status
rem NOTE: keep this file ASCII-only. Chinese chars before/after chcp can shift
rem cmd.exe parsing offsets and break later lines.
setlocal

set "BASH="
if exist "C:\Program Files\Git\bin\bash.exe" set "BASH=C:\Program Files\Git\bin\bash.exe"
if not defined BASH if exist "C:\Program Files (x86)\Git\bin\bash.exe" set "BASH=C:\Program Files (x86)\Git\bin\bash.exe"
if not defined BASH if exist "%LOCALAPPDATA%\Programs\Git\bin\bash.exe" set "BASH=%LOCALAPPDATA%\Programs\Git\bin\bash.exe"

if not defined BASH (
  echo.
  echo Git Bash ^(bash.exe^) not found.
  echo Please install Git for Windows: https://git-scm.com/download/win
  echo Then double-click this file again.
  echo.
  pause
  exit /b 1
)

"%BASH%" "%~dp0start-infra.sh" %*

rem Keep window open when double-clicked; stay quiet when called with args
if "%~1"=="" pause
endlocal
