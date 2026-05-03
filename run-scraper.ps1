# Start Bundlbite Scraper (PowerShell — Windows safe)
Write-Host "Starting Bundlbite Scraper on http://localhost:8001" -ForegroundColor Cyan

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

# Use Python entrypoint so SelectorEventLoop is set before uvicorn
python run_scraper.py
