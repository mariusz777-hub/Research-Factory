# Weryfikacja aktualizacji in-place 1.1.0

## Baza i porównanie

- bazą była paczka `research-factory-1.0.0.zip`, zgodna ze zrzutami aplikacji webowej;
- porównano ją z błędną `Research_Factory_v0.2.0.zip`;
- nie przeniesiono Tkintera, Excela, runnerów Copilot ani osobnej kolejki z v0.2;
- żaden plik bazowy nie został usunięty;
- `config/question_templates.yaml` jest identyczny bajt w bajt z bazą;
- SHA-256 biblioteki 12 pytań: `5ee022bd6ffae27a0ff850c01b8315c271a6d59ec6d038b81ee34f943a6082ac`.

## Wykonane sprawdzenia w środowisku budowania

- parsowanie AST i `compileall` wszystkich 31 plików Python — OK;
- `scripts/verify_update_contract.py` — OK;
- 12 niezależnych testów pytest niewymagających ORM — 12/12 OK;
- 4 oryginalne testy asynchroniczne Model Gateway — 4/4 OK;
- adapter istniejącego pliku scrapera Google — OK;
- połączenie researchu wejściowego i wyniku scrapera — OK;
- Reddit OAuth: token wyłącznie w nagłówku, brak tokenu w URL — OK;
- walidator kompletności user stories/Gherkin/architektury/struktury/coding prompt — OK;
- statyczny skan GUI: brak identyfikatorów i treści 12 szablonów — OK;
- brak osobnego pliku frontend/GUI — OK;
- render istniejącego GUI przez Jinja2 + CSS do PDF/PNG — OK; zachowano nazwę, opis, modele, GitHub/WWW i historię, dodano tylko wejście Google oraz zakresy Reddit/Google;
- skan sekretów i ścieżek środowiska budowania — wykonywany przed spakowaniem;
- test integralności ZIP i `SOURCE_SHA256SUMS.txt` — wykonywany po spakowaniu.

## Testy zawarte w paczce

Paczka zawiera 19 testów regresyjnych. Trzy testy zależne od SQLAlchemy — kolejka (2) i pełny pipeline (1) — nie mogły zostać wykonane w kontenerze budowania, ponieważ jego rejestr pakietów nie udostępniał `SQLAlchemy` ani `Alembic`. Nie oznaczono ich fałszywie jako wykonanych.

Na docelowym środowisku projektu komplet uruchamia:

```powershell
.\scripts\verify.ps1
```

Skrypt instaluje zależności z `pyproject.toml`, wykonuje lint, wszystkie 19 testów, kontrolę niezmienionej biblioteki 12 pytań i pełny self-check SQLite: modele → cztery rodzaje researchu → porównania → rozszerzona synteza → raport. Dotychczasowa ścieżka PostgreSQL/Alembic pozostaje wspierana.
