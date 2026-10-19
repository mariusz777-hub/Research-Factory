$ErrorActionPreference = 'Stop'
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path .venv)) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Write-Host "Uruchom PostgreSQL: docker compose up -d postgres"
Write-Host "Migracje: .\.venv\Scripts\alembic.exe upgrade head"
Write-Host "API:      .\.venv\Scripts\research-factory-api.exe"
Write-Host "Worker:   .\.venv\Scripts\research-factory-worker.exe"
