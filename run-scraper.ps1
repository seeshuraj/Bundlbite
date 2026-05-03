# Start Bundlbite Scraper Microservice (PowerShell)
# Run from project root: .\run-scraper.ps1

Write-Host "Starting Bundlbite Scraper on http://localhost:8001" -ForegroundColor Cyan

if (Test-Path ".\venv\Scripts\Activate.ps1") {
    .\venv\Scripts\Activate.ps1
}

$envFile = ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^([^#=]+)=(.*)$") {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

uvicorn scraper.main:app --host 0.0.0.0 --port 8001 --reload
