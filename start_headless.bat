@echo off
setlocal

set "PYTHON_EXE=C:\Users\Tommy\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\python.exe"
set "PROJECT_DIR=C:\Trading\DE40-Research"
set "LOG_FILE=%PROJECT_DIR%\stratx_live.log"

echo ============================================================
echo   STRATX QUANT DESK — LAUNCHING HEADLESS BACKGROUND DAEMON
echo ============================================================
echo.

:: Launch python detached in background with stdout/stderr piped to log file
powershell -Command "Start-Process -FilePath '%PYTHON_EXE%' -ArgumentList 'orchestrator/stratx_live_console.py' -WorkingDirectory '%PROJECT_DIR%' -RedirectStandardOutput '%LOG_FILE%' -RedirectStandardError '%LOG_FILE%' -WindowStyle Hidden"

echo [OK] StratX engine is now running in the background.
echo [OK] Output is logging to: %LOG_FILE%
echo.
echo To view live stream anytime, run:
echo   Get-Content C:\Trading\DE40-Research\stratx_live.log -Wait -Tail 40
echo.
echo To stop the background daemon, run:
echo   .\stop_headless.bat
echo ============================================================

endlocal
