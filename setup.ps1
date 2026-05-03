# Bundlbite Windows Setup Script (PowerShell)
# Run: .\setup.ps1

Write-Host "=== Bundlbite Setup ==="  -ForegroundColor Cyan

# 1. Create virtual environment
Write-Host "`n[1/5] Creating virtual environment..." -ForegroundColor Yellow
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Install dependencies
Write-Host "`n[2/5] Installing Python dependencies..." -ForegroundColor Yellow
pip install -r backend/requirements.txt

# 3. Install Playwright Chromium
Write-Host "`n[3/5] Installing Playwright Chromium..." -ForegroundColor Yellow
playwright install chromium

# 4. Copy .env if not exists
Write-Host "`n[4/5] Setting up .env..." -ForegroundColor Yellow
if (-Not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ".env created from .env.example" -ForegroundColor Green
    Write-Host ">> Open .env and fill in NVIDIA_API_KEY" -ForegroundColor Red
} else {
    Write-Host ".env already exists, skipping." -ForegroundColor Green
}

Write-Host "`n[5/5] Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Edit .env and add your NVIDIA_API_KEY"
Write-Host "     Get free key: https://build.nvidia.com"
Write-Host "  2. Start Redis (Docker): docker run -p 6379:6379 redis:7-alpine"
Write-Host "  3. Start scraper:  .\run-scraper.ps1"
Write-Host "  4. Start backend:  .\run-backend.ps1"
