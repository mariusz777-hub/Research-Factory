# Architektura Research Factory

## Granice komponentów

1. **FastAPI GUI/API** przyjmuje jeden pomysł, wybór modeli i zakres researchu. API nie wykonuje długich operacji.
2. **Orchestrator** tworzy deterministyczny graf pracy i idempotentnie dodaje kolejne etapy.
3. **PostgreSQL queue** przechowuje status, `attempts`, `next_attempt_at`, dzierżawę, błąd i ścieżkę wyniku. Claim używa `FOR UPDATE SKIP LOCKED`.
4. **Worker** pobiera pojedyncze zadanie, zapisuje wynik i rozwija graf. Retry jest odroczony w bazie; pętla nie używa długiego `time.sleep`.
5. **Model Gateway** wystawia wspólny kontrakt dla OpenAI, DeepSeek i Gemini; istniejące 12 pytań YAML pozostaje jedynym wejściem analitycznym modeli.
6. **Research services** realizują GitHub API, Reddit API, Google przez adapter istniejącego scrapera użytkownika oraz WWW (Tavily albo awaryjnie DuckDuckGo HTML).
7. **Comparator** zachowuje zgodności, możliwe sprzeczności polaryzacji/liczb i jawne braki.
8. **Artifact store** zapisuje atomowo manifest, wszystkie prompty, odpowiedzi, źródła, porównania, architekturę, backlog, raport i JSONL zdarzeń.

## Graf MVP

`MODEL_ANSWER × 12 pytań × modele` + wybrane `GITHUB_RESEARCH` / `REDDIT_RESEARCH` / `GOOGLE_RESEARCH` / `WEB_RESEARCH`
→ `COMPARE × pytania`
→ `SYNTHESIS`
→ `REPORT`

Etap uruchamia się, gdy wszystkie jego zależności są terminalne. Błąd po wyczerpaniu prób nie blokuje raportu: run kończy się jako `PARTIAL`, a brak jest widoczny w raporcie.

## Odporność

- Deduplikacja przez `(run_id, dedupe_key)`.
- Odpowiedzi przez `(question_id, model_name)`.
- Dzierżawa zadania umożliwia odzyskanie po śmierci workera.
- `next_attempt_at` i backoff rozdzielają ponowienia od wykonania.
- Budżet wywołań jest rezerwowany pod blokadą wiersza; usage tokenów jest normalizowany lub estymowany.
- Aktywne runy są rozwijane przy starcie workera.
- Pliki są zapisywane przez plik tymczasowy + `os.replace`.
- Końcowy `artifact_manifest.json` zawiera rozmiar i SHA-256 każdego stabilnego artefaktu; append-only log ma jawny wyjątek.

## Model bezpieczeństwa MVP

Sekrety tylko w `.env`; brak kluczy w logach i artefaktach. Pobieranie artefaktów ma ochronę przed path traversal. Wejście formularza jest walidowane, a GUI ucieka dynamiczny HTML. Produkcyjnie należy dodać reverse proxy, TLS, logowanie użytkowników, RBAC i menedżer sekretów.

## Granica badanego projektu

Pliki `reports/architecture.md`, `user_stories.md`, `specification.feature`, `project_structure.md` i `coding_prompt.md` opisują wyłącznie badany projekt. Architektura Research Factory z tego dokumentu nie jest kopiowana do tych artefaktów. Rozdzielenie jest wymuszone kontraktem promptu syntezy i testami regresyjnymi.
