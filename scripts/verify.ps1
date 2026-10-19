$ErrorActionPreference = 'Stop'
if (-not (Test-Path .venv)) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
& .\.venv\Scripts\python.exe -m compileall -q src tests alembic scripts
& .\.venv\Scripts\ruff.exe check src tests scripts
& .\.venv\Scripts\pytest.exe
& .\.venv\Scripts\python.exe scripts\verify_update_contract.py
& .\.venv\Scripts\research-factory-selfcheck.exe
Write-Host "WERYFIKACJA: OK"
