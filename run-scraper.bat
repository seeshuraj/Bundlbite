@echo off
call venv\Scripts\activate.bat
uvicorn scraper.main:app --host 0.0.0.0 --port 8001 --reload
