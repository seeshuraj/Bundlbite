# Start Bundlbite Backend (PowerShell)
# Run from project root: .\run-backend.ps1

Write-Host "Starting Bundlbite Backend on http://localhost:8000" -ForegroundColor Cyan

# Activate venv if exists
if (Test-Path ".\venv\Scripts\Activate.ps1") {
    .\venv\Scripts\Activate.ps1
}

# Load .env manually (uvicorn reads it via python-dotenv)
$envFile = ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^([^#=]+)=(.*)$") {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
    Write-Host ".env loaded" -ForegroundColor Green
}

uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
