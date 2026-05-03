# Start Bundlbite Scraper (PowerShell)
# Windows fix: force SelectorEventLoop for Playwright subprocess support

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
    Write-Host ".env loaded" -ForegroundColor Green
}

# WindowsSelectorEventLoopPolicy is set inside scraper/main.py
# uvicorn must import the app module BEFORE starting the loop
uvicorn scraper.main:app --host 0.0.0.0 --port 8001 --reload --loop asyncio
