@echo off
chcp 65001 >nul
rem Start HerbMind Agent service (:8091) using conda env "herbmind".
rem Double-click this file, or: run-agent.bat  (Ctrl+C to stop)
rem NOTE: keep this file ASCII-only (chcp 65001 + Chinese chars breaks cmd parsing).
setlocal

set "PORT=8091"

set "PY="
if exist "D:\software\anaconda\anaconda_1\envs\herbmind\python.exe" set "PY=D:\software\anaconda\anaconda_1\envs\herbmind\python.exe"
if not defined PY if exist "%USERPROFILE%\anaconda3\envs\herbmind\python.exe" set "PY=%USERPROFILE%\anaconda3\envs\herbmind\python.exe"
if not defined PY if exist "%USERPROFILE%\miniconda3\envs\herbmind\python.exe" set "PY=%USERPROFILE%\miniconda3\envs\herbmind\python.exe"

if not defined PY (
  echo conda env "herbmind" python.exe not found.
  echo Expected: D:\software\anaconda\anaconda_1\envs\herbmind\python.exe
  echo Create it first:  conda create -n herbmind python=3.11 -y
  echo Then install deps: python -m pip install -r requirements.txt
  pause
  exit /b 1
)

rem --- Guard: port already in use --------------------------------------
rem When the port is taken, Windows reports WSAEACCES (WinError 10013) or
rem WSAEADDRINUSE (10048). Both look like a permission problem but are not,
rem so find the listening PID and name it before uvicorn gets a chance to
rem fail with a message nobody can act on.
set "BUSY="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:"TCP.*:%PORT%.*LISTENING"') do set "BUSY=%%P"

if defined BUSY (
  echo [ERROR] Port %PORT% is already in use by PID %BUSY%:
  echo.
  tasklist /fi "PID eq %BUSY%" /fo table /nh
  echo.
  echo It is usually a leftover uvicorn from a previous run.
  echo Stop it first:   taskkill /PID %BUSY% /F
  echo Then start this script again.
  echo.
  echo If the PID above is not a python.exe, inspect the port yourself:
  echo   netstat -ano ^| findstr :%PORT%
  pause
  exit /b 1
)

rem .env is loaded relative to cwd, so always run from this directory
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

echo Using python: %PY%
echo Starting on http://127.0.0.1:%PORT%  (health: /api/agent/health)
echo Press Ctrl+C to stop.
echo.
"%PY%" -m uvicorn app.main:app --host 0.0.0.0 --port %PORT%

echo.
echo Agent service stopped.
pause
endlocal
