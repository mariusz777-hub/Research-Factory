#!/usr/bin/env sh
set -eu
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
python -m compileall -q src tests alembic scripts
ruff check src tests scripts
pytest
python scripts/verify_update_contract.py
research-factory-selfcheck
printf '%s\n' 'WERYFIKACJA: OK'
