@echo off
REM Bundlbite Windows Setup (CMD fallback)
REM Run: setup.bat

echo === Bundlbite Setup ===

echo [1/4] Creating virtual environment...
python -m venv venv
call venv\Scripts\activate.bat

echo [2/4] Installing dependencies...
pip install -r backend\requirements.txt

echo [3/4] Installing Playwright Chromium...
playwright install chromium

echo [4/4] Copying .env...
if not exist .env copy .env.example .env

echo.
echo Setup complete!
echo Edit .env and add NVIDIA_API_KEY
echo Get free key: https://build.nvidia.com
echo.
echo To start backend:  run-backend.bat
echo To start scraper:  run-scraper.bat
