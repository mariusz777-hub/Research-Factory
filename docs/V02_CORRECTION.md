# Korekta błędnej paczki v0.2

## Wniosek z porównania

Błędna paczka `Research_Factory_v0.2.0.zip` nie była aktualizacją lokalnego projektu. Zawierała inny produkt: desktopowy runner Tkinter uruchamiający `run.py`/`run_parallel.py`, pliki pytań Excel, modele `TestQuestion`/`TestResult` oraz osobny moduł `research_factory/`. Nie zawierała bazowego FastAPI GUI, modeli projekt/run/job, kolejki z lease, historii projektów ani `config/question_templates.yaml`.

Poprawiona wersja 1.1.0 została zbudowana bezpośrednio na bazie `research-factory-1.0.0.zip`, odpowiadającej katalogowi `C:\projekty\robotanalitykprojektow` ze zrzutów.

## Elementy zachowane bez zastępowania

- jedno istniejące GUI FastAPI i jego układ;
- nazwa projektu oraz jeden opis pomysłu;
- wybór OpenAI, Gemini i DeepSeek;
- istniejące zakresy GitHub i WWW;
- historia ostatnich projektów;
- modele SQLAlchemy `Project`, `Run`, `Question`, `Job`, `ModelResponse`, `ResearchSource`, `Comparison`, `Event`;
- statusy, retry, backoff, lease, resume i deduplikacja zadań;
- istniejące raporty i manifesty artefaktów;
- `config/question_templates.yaml` — dokładnie 12 pytań, SHA-256:
  `5ee022bd6ffae27a0ff850c01b8315c271a6d59ec6d038b81ee34f943a6082ac`;
- SQLite używany w testach/lokalnie oraz PostgreSQL wspierany przez obecną konfigurację;
- dotychczasowy kontrakt Model Gateway.

## Zmiany dodane in-place

1. Dwa nowe zakresy istniejącego formularza: Reddit i Google.
2. Opcjonalne pole tekstowe „Wejściowy research Google”.
3. `REDDIT_TOKEN` i `REDDIT_USER_AGENT` w istniejącym `Settings`/`.env`.
4. Zachowana obsługa `GITHUB_TOKEN`, rozszerzona regresją bezpieczeństwa.
5. `GoogleScraperAdapter` wskazujący istniejącą funkcję scrapera przez `GOOGLE_SCRAPER_TARGET`.
6. Zadania `REDDIT_RESEARCH` i `GOOGLE_RESEARCH` w tej samej kolejce `Job`.
7. Normalizacja źródeł do istniejącego `ResearchSource`.
8. Dodatkowe wyjścia syntezy badanego projektu:
   - `user_stories.md`,
   - `specification.feature`,
   - `project_structure.md`,
   - `architecture.md`,
   - `coding_prompt.md`.
9. Migracja Alembic dodająca wyłącznie opcjonalne wejście Google do istniejącego projektu.

## Świadomie nie przeniesiono z błędnej v0.2

- osobnego GUI Tkinter;
- plików Excel jako biblioteki pytań;
- osobnego CLI i workspace nowego projektu;
- modeli i statusów runnera Copilot;
- drugiej, równoległej kolejki SQLite;
- przykładowego generatora specyfikacji niezależnego od 12 analiz.
