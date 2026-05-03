# Bundlbite — Dev Commands

.PHONY: install dev scraper backend redis logs clean

install:
	pip install -r backend/requirements.txt
	playwright install chromium

dev:
	docker-compose up --build

scraper:
	uvicorn scraper.main:app --host 0.0.0.0 --port 8001 --reload

backend:
	uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

redis:
	docker run -p 6379:6379 redis:7-alpine

logs:
	docker-compose logs -f

clean:
	docker-compose down -v
