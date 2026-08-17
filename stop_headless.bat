@echo off
setlocal

echo Stopping StratX background engine processes...
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*stratx_live_console.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"

echo [OK] StratX background engine stopped cleanly.
endlocal
