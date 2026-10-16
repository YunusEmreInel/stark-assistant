# Stark'ı başlatır (şimdilik konsol sürümü). Kullanım: powershell -ExecutionPolicy Bypass -File scripts\run_windows.ps1
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = "utf-8"
$env:HF_HUB_DISABLE_PROGRESS_BARS = "1"
$env:HF_HUB_DISABLE_TELEMETRY = "1"
& "$root\.venv\Scripts\python.exe" -m stark

