# Research Factory

Odrębny system badawczo-analityczny z istniejącym webowym GUI, trwałą kolejką i wspólnym Model Gateway dla **OpenAI, Gemini i DeepSeek**. Przyjmuje jeden pomysł, wstawia go do niezmienionej biblioteki 12 pytań `config/question_templates.yaml`, wykonuje każde pytanie niezależnie, prowadzi research GitHub/Reddit/Google/WWW, porównuje odpowiedzi i zapisuje pełny audyt na dysku.

Nie ma integracji z Microsoft Copilot ani automatyzacji przeglądarki. Załączony wcześniej runner ewaluacyjny nie jest częścią rozwiązania.

## Zakres działającego MVP

- GUI: nazwa projektu, opis pomysłu, modele, zakres GitHub/WWW/Reddit/Google, wejściowy research Google, etapy i statusy;
- wersjonowalna biblioteka pytań YAML z Jinja2 `{{ idea }}` i `{{ project_name }}`;
- adaptery OpenAI/DeepSeek (Chat Completions) i Gemini (`generateContent`);
- wspólny Model Gateway, timeouty, usage tokenów, budżet runu i odstępy per dostawca;
- kolejka PostgreSQL: status, priorytet, `next_attempt_at`, retry/backoff, lease, odzyskanie po restarcie;
- research GitHub API, Reddit API, Google przez adapter istniejącego scrapera użytkownika oraz WWW przez Tavily lub fallback DuckDuckGo HTML;
- porównanie: zgodności, możliwe sprzeczności i braki;
- synteza badanego projektu przez wybrany model prowadzący: architektura, backlog, user stories, kompletna specyfikacja Gherkin, struktura katalogów/plików i `coding_prompt.md`;
- raport Markdown i pełny zapis artefaktów;
- testy jednostkowe, integracyjny pipeline bez zewnętrznych API i self-check.

## Szybki start — Docker (zalecany)

Wymagane: Docker Desktop / Docker Engine z Compose.

```bash
cp .env.example .env
# Uzupełnij OPENAI_API_KEY, GEMINI_API_KEY i DEEPSEEK_API_KEY.
# Opcjonalnie: GITHUB_TOKEN, REDDIT_TOKEN, GOOGLE_SCRAPER_TARGET i TAVILY_API_KEY.
docker compose up --build
```

GUI: <http://localhost:8000>  
Healthcheck: <http://localhost:8000/health>

PostgreSQL i artefakty mają osobne trwałe wolumeny. API wykonuje migrację Alembic przy starcie, worker odzyskuje przeterminowane dzierżawy i aktywne runy.

## Uruchomienie developerskie

Python 3.11+ i PostgreSQL 16+.

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e '.[dev]'
docker compose up -d postgres
alembic upgrade head
research-factory-api
```

W drugim terminalu:

```bash
source .venv/bin/activate
research-factory-worker
```

Na Windows można zacząć od `scripts\run_local.ps1`.

## Konfiguracja modeli

| Dostawca | Zmienne minimalne | Domyślny model |
|---|---|---|
| OpenAI | `OPENAI_API_KEY` | `gpt-4.1-mini` |
| Gemini | `GEMINI_API_KEY` | `gemini-2.5-flash` |
| DeepSeek | `DEEPSEEK_API_KEY` | `deepseek-chat` |

Nazwy modeli i bazowe URL-e można zmienić w `.env` bez zmian kodu. Brak klucza jest błędem nieretryowalnym danego zadania; pipeline nadal dochodzi do raportu `PARTIAL` z jawnym brakiem.

## Konfiguracja researchu GitHub, Reddit i Google

```dotenv
GITHUB_TOKEN=
REDDIT_TOKEN=
REDDIT_USER_AGENT=ResearchFactory/1.1

# Istniejący scraper użytkownika; nie jest kopiowany ani zastępowany.
GOOGLE_SCRAPER_TARGET=C:/projekty/moj_google_scraper.py:search

GITHUB_RESULT_LIMIT=10
REDDIT_RESULT_LIMIT=10
GOOGLE_RESULT_LIMIT=10
```

`GOOGLE_SCRAPER_TARGET` przyjmuje `module:function` albo `C:/pełna/ścieżka.py:function`.
Funkcja może być synchroniczna lub asynchroniczna i przyjmować `query`, opcjonalnie
`limit`. Wynik może być listą słowników/obiektów z polami `title`, `url`/`link` oraz
`snippet`/`description`. Adapter jedynie normalizuje wynik do istniejącego modelu
`ResearchSource` i istniejącej kolejki.

Pole **Wejściowy research Google** w istniejącym formularzu przyjmuje JSON albo tekst/Markdown
z adresami URL. Jeżeli podano zarówno research wejściowy, jak i scraper, oba zbiory są łączone
i deduplikowane. Tokeny pozostają wyłącznie w `.env`; nie są zapisywane w projekcie ani artefaktach.

## Biblioteka pytań

Plik `config/question_templates.yaml` jest ładowany przy tworzeniu projektu. Każde aktywne pytanie wymaga unikalnego `id`, kategorii i `template`. Przykład:

```yaml
- id: system_architecture
  category: architecture
  enabled: true
  template: |
    Projekt: {{ project_name }}
    Pomysł: {{ idea }}
    Zaproponuj architekturę, API, przepływy danych i mechanizm wznowienia.
```

Zmiana YAML wpływa na nowe projekty. Run zapisuje wersję biblioteki, wyrenderowane prompty i ich SHA-256.

## Kolejka i wznowienie

1. Worker atomowo claimuje gotowe zadanie przez `FOR UPDATE SKIP LOCKED`.
2. Ustawia `RUNNING`, `leased_until`, `worker_id` i zwiększa `attempts`.
3. Sukces zapisuje wynik przed statusem `SUCCESS`.
4. Błąd retryowalny ustawia `RETRY` i przyszłe `next_attempt_at` z wykładniczym backoffem oraz jitterem.
5. Błąd nieretryowalny lub wyczerpanie limitu ustawia `FAILED`.
6. Przed płatnym wywołaniem worker atomowo rezerwuje budżet wywołania; po odpowiedzi zapisuje usage tokenów lub konserwatywną estymację.
7. Przy starcie worker odzyskuje zadania z wygasłą dzierżawą i rozwija aktywne grafy.

Pętla używa krótkiego `asyncio.wait_for` tylko wtedy, gdy nie ma pracy. Retry nie blokuje procesu i nie jest realizowany długim `time.sleep`.

## Artefakty

```text
data/projects/<slug>/<run-id>/
├── manifest.json
├── prompts/
│   ├── system.md
│   ├── <question-id>/{prompt.md,openai.md,gemini.md,deepseek.md}
│   ├── research_github.txt
│   ├── research_reddit.txt
│   ├── research_google.txt
│   ├── research_web.txt
│   └── synthesis.md
├── responses/<question-id>/{model}.md + {model}.json
├── sources/{github.json,reddit.json,google.json,web.json}
├── comparisons/<question-id>.json
├── reports/
│   ├── executive_summary.md
│   ├── architecture.md             # architektura badanego projektu
│   ├── backlog.md
│   ├── user_stories.md
│   ├── specification.feature       # kompletna specyfikacja Gherkin
│   ├── project_structure.md        # katalogi i pliki badanego projektu
│   ├── coding_prompt.md
│   ├── synthesis.json
│   └── report.md
├── logs/events.jsonl
└── artifact_manifest.json      # rozmiary i SHA-256; log append-only jest wyłączony
```

PostgreSQL pozostaje źródłem statusu operacyjnego; dysk przechowuje audytowalne wejścia i wyniki.

## Testy i self-check

```bash
./scripts/verify.sh
# Windows PowerShell: .\scripts\verify.ps1
```

Skrypt wykonuje kompilację, lint, pełne `pytest` i `research-factory-selfcheck`.

Self-check tworzy tymczasową bazę, używa deterministycznych fake adapterów i przechodzi pełny graf: pytania → modele → research → porównania → synteza → raport. Nie wymaga kluczy API.

## Weryfikacja live

Po testach automatycznych uruchom projekt z prawdziwymi kluczami i krótką biblioteką 1–2 pytań. Sprawdź odpowiedzi, limity i nazwy modeli dostępne na Twoich kontach. Zewnętrzne API, limity i dostępność modeli nie mogą być wiarygodnie testowane offline.

## Struktura

- `src/research_factory/api/` — GUI i status API;
- `orchestrator.py` — graf i kompletność;
- `queue.py` — claim, retry, `next_attempt_at`, lease;
- `worker.py` — wykonawca zadań;
- `model_gateway.py` — adaptery modeli;
- `research.py` — GitHub/Reddit/Google/WWW;
- `google_scraper_adapter.py` — adapter do istniejącego scrapera Google użytkownika;
- `comparison.py` — zgodności/sprzeczności/braki;
- `reporting.py` — końcowy raport;
- `models.py` — model PostgreSQL;
- `alembic/` — migracje;
- `tests/` — regresja i pełny pipeline.

Szczegóły: `docs/ARCHITECTURE.md`. Etap drugi: `docs/STAGE2.md`. Zakres wykonanej weryfikacji: `docs/BUILD_VERIFICATION.md`.

## Świadomie poza MVP

Klonowanie repozytoriów, statyczna analiza kodu, bezpieczne uruchamianie w kontenerach, Neo4j, wyszukiwanie semantyczne, diagramy i eksport Word/PDF. Nie ma atrap tych funkcji w GUI ani w kolejce.
