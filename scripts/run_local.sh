#!/usr/bin/env sh
set -eu
[ -f .env ] || cp .env.example .env
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
printf '%s\n' 'Uruchom PostgreSQL: docker compose up -d postgres'
printf '%s\n' 'Migracje: .venv/bin/alembic upgrade head'
printf '%s\n' 'API:      .venv/bin/research-factory-api'
printf '%s\n' 'Worker:   .venv/bin/research-factory-worker'
