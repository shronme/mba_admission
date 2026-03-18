.PHONY: up down logs test

up:
	docker compose up --build -d

down:
	docker compose down -v

logs:
	docker compose logs -f --tail=200

test:
	cd backend && PYTHONPATH=. python -m pytest -q
