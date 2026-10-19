@echo off
setlocal
rem Prefer PATH Python so an existing activated environment is respected.
where python >nul 2>nul
if not errorlevel 1 (
    python -m opencaliper gui %*
    if errorlevel 1 goto failed
    exit /b 0
)
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -m opencaliper gui %*
    if errorlevel 1 goto failed
    exit /b 0
)
echo Python 3.10 or newer is required.
:failed
echo.
echo OpenCaliper could not start. Install it in this Python environment as described in the README.
pause
exit /b 1
