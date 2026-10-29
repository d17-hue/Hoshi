@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Hoshi has not been installed. Please run install_windows.bat first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" companion.py
if errorlevel 1 (
    echo Hoshi exited with an error. Copy the message above for troubleshooting.
    pause
)
