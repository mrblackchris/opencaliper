@echo off
setlocal
where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%~dp0scripts\launch.py" %*
    if errorlevel 1 goto failed
    exit /b 0
)
where python >nul 2>nul
if not errorlevel 1 (
    python "%~dp0scripts\launch.py" %*
    if errorlevel 1 goto failed
    exit /b 0
)
echo Python 3.10 or newer is required. Install Python with the Python launcher or add it to PATH.
:failed
echo.
echo OpenCaliper could not start. See the message above.
pause
exit /b 1
