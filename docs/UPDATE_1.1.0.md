# Aktualizacja in-place 1.1.0

## Aktualizacja istniejącego katalogu

1. Zatrzymaj API i workera.
2. Utwórz kopię katalogu oraz bazy.
3. Nadpisz pliki aplikacji zawartością paczki 1.1.0, ale zachowaj własny `.env` i katalog `data/`.
4. Dopisz do `.env` opcjonalne ustawienia:

```dotenv
REDDIT_TOKEN=
REDDIT_USER_AGENT=ResearchFactory/1.1
GOOGLE_SCRAPER_TARGET=C:/projekty/sciezka/do/scraper_google.py:search
REDDIT_RESULT_LIMIT=10
GOOGLE_RESULT_LIMIT=10
```

5. Zainstaluj aktualizację: `pip install -e ".[dev]"`.
6. Wykonaj `alembic upgrade head` — migracja dodaje jedno pole, nie usuwa danych.
7. Uruchom `scripts\verify.ps1`.
8. Uruchom ponownie API i workera dotychczasowymi skryptami.

## Kompatybilność

Nowe zakresy nie są automatycznie włączane w starych projektach. Istniejące projekty, runy, pytania, zadania, odpowiedzi, statusy i artefakty pozostają czytelne. Nowe pliki wyjściowe powstają dla nowych runów, w których wykona się rozszerzona synteza.

`question_templates.yaml` nie jest migrowany ani generowany. Aktualizacja ma test blokujący zmianę jego sumy SHA-256.
