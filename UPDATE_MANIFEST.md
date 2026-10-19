# Research Factory 1.1.0 — manifest aktualizacji in-place

## Pliki dodane

- `alembic/versions/0002_google_research_input.py`
- `src/research_factory/google_scraper_adapter.py`
- `src/research_factory/synthesis_contract.py`
- `tests/test_research_extensions.py`
- `scripts/verify_update_contract.py`
- `docs/V02_CORRECTION.md`
- `docs/OUTPUT_CONTRACT.md`
- `docs/UPDATE_1.1.0.md`

## Główne pliki rozszerzone

- `.env.example`, `settings.py` — Reddit i adapter Google;
- `templates/index.html`, `api/app.py` — rozszerzenie tego samego GUI;
- `schemas.py`, `models.py` — opcjonalne wejście Google i dwa nowe zakresy;
- `orchestrator.py`, `worker.py`, `research.py` — dwa nowe typy zadań w tej samej kolejce;
- `reporting.py` — nowe artefakty w istniejącym raporcie;
- `selfcheck.py`, `test_pipeline.py` — pełna regresja istniejącego grafu.

## Pliki gwarantowane jako niezmienione funkcjonalnie

- `config/question_templates.yaml` — 12 pytań, identyczny plik;
- `queue.py` — dotychczasowe statusy, lease, retry i resume;
- `model_gateway.py` — kontrakty OpenAI/Gemini/DeepSeek;
- `comparison.py` — dotychczasowe porównanie modeli;
- `templates/project.html`, `static/status.js`, `static/app.css` — istniejący ekran statusu i wygląd;
- `artifacts.py` — atomowy zapis i ochrona ścieżek.

Aktualizacja nie zawiera osobnego GUI, drugiego projektu, Excela jako źródła pytań ani nowej biblioteki promptów.
