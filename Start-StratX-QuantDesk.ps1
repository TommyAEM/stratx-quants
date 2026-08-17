# ==============================================================================
# StratX Institutional Quantitative Research Desk - Master PowerShell Launcher
# Directory: C:\Trading\DE40-Research
# ==============================================================================
$ErrorActionPreference = 'Stop'

$PythonExe = "C:\Users\Tommy\AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\python.exe"
$ResearchDir = "C:\Trading\DE40-Research"
$LiveConsole = "$ResearchDir\orchestrator\stratx_live_console.py"

Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host " [STRATX] AUTONOMOUS QUANTITATIVE RESEARCH DESK" -ForegroundColor Yellow
Write-Host "==============================================================================" -ForegroundColor Cyan

# 1. Release terminal locks
Write-Host "[1/2] Checking environment & releasing terminal locks..." -ForegroundColor Gray
Get-Process terminal64 -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 300

# 2. Verify Python Interpreter
if (-not (Test-Path $PythonExe)) {
    Write-Error "Python executable not found at: $PythonExe"
    exit 1
}

Write-Host "[2/2] Launching Deep Self-Healing Mission in current console..." -ForegroundColor Green
Write-Host "==============================================================================" -ForegroundColor DarkGray

# Run directly in the active PowerShell window
& $PythonExe $LiveConsole
