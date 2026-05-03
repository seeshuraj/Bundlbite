# Start Bundlbite Backend (PowerShell — Windows safe)
Write-Host "Starting Bundlbite Backend on http://localhost:8000" -ForegroundColor Cyan

if (Test-Path ".\venv\Scripts\Activate.ps1") {
    .\venv\Scripts\Activate.ps1
}

if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match "^([^#=]+)=(.*)$") {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
    Write-Host ".env loaded" -ForegroundColor Green
}

python run_backend.py
