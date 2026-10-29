@echo off
setlocal
cd /d "%~dp0"
where ollama >nul 2>nul
if errorlevel 1 (
    echo Ollama was not found. Install it from https://ollama.com/download/windows
    pause
    exit /b 1
)
echo Downloading the local image-capable model. This is several gigabytes.
ollama pull gemma3:4b
if errorlevel 1 (
    echo Model download failed. Make sure Ollama is running and try again.
    pause
    exit /b 1
)
echo Model is ready. Next, run install_windows.bat
pause
