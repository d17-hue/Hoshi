@echo off
setlocal
cd /d "%~dp0"
py -3.11 --version >nul 2>nul
if errorlevel 1 (
    echo Python 3.11 was not found. Install 64-bit Python 3.11 with the Python Launcher.
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)
echo Creating the Hoshi Python environment...
py -3.11 -m venv .venv
if errorlevel 1 goto failed
echo Installing required packages...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Setup complete. Launching Hoshi...
".venv\Scripts\python.exe" companion.py
pause
exit /b 0
:failed
echo Setup failed. Please copy the error details if you need help.
pause
exit /b 1
