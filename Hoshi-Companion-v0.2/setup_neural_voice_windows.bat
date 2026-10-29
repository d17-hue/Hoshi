@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run install_windows.bat first to set up Hoshi.
    pause
    exit /b 1
)
echo Installing the OFFLINE Kokoro voice engine...
".venv\Scripts\python.exe" -m pip install "kokoro-onnx==0.6.1"
if errorlevel 1 goto failed
if not exist "voice_models" mkdir "voice_models"
if errorlevel 1 goto failed

if not exist "voice_models\kokoro-v1.0.fp16.onnx" (
    echo Downloading local voice model, about 164 MB...
    curl.exe --fail --location --retry 2 --output "voice_models\kokoro-v1.0.fp16.onnx" "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.fp16.onnx"
    if errorlevel 1 (
        del /q "voice_models\kokoro-v1.0.fp16.onnx" 2>nul
        goto failed
    )
)
if not exist "voice_models\voices-v1.0.bin" (
    echo Downloading voice styles, about 28 MB...
    curl.exe --fail --location --retry 2 --output "voice_models\voices-v1.0.bin" "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin"
    if errorlevel 1 (
        del /q "voice_models\voices-v1.0.bin" 2>nul
        goto failed
    )
)
".venv\Scripts\python.exe" -c "from neural_voice import models_ready; raise SystemExit(0 if models_ready() else 1)"
if errorlevel 1 goto failed
echo Local Kokoro voices are ready. Run run_windows.bat and click Preview!
pause
exit /b 0
:failed
echo Neural voice setup did not finish. Check the error above and run this file again.
pause
exit /b 1
