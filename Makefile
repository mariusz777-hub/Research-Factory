.PHONY: install test lint selfcheck up down
install:
	python -m pip install -e '.[dev]'
test:
	pytest
lint:
	ruff check src tests
selfcheck:
	research-factory-selfcheck
up:
	docker compose up --build
down:
	docker compose down
