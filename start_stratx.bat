@echo off
setlocal

set "PYTHON_EXE=C:\Users\Tommy\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\python.exe"
set "WT_EXE=C:\Users\Tommy\AppData\Local\Microsoft\WindowsApps\wt.exe"

:: 1. Check if Windows Terminal exists
if exist "%WT_EXE%" (
    "%WT_EXE%" -w 0 -d "C:\Trading\DE40-Research" cmd /k ""%PYTHON_EXE%" orchestrator/stratx_live_console.py" ; split-pane -V -s 0.28 -d "C:\Trading\DE40-Research" cmd /k ""%PYTHON_EXE%" orchestrator/chat_console.py"
    goto :eof
)

:: 2. Fallback: Launch Side-by-Side CMD Windows
start "StratX Quant Desk - Cognitive Research Stream" /d "C:\Trading\DE40-Research" "%PYTHON_EXE%" orchestrator/stratx_live_console.py
start "StratX Quant Desk - Interactive Chat & Steering" /d "C:\Trading\DE40-Research" "%PYTHON_EXE%" orchestrator/chat_console.py

endlocal
