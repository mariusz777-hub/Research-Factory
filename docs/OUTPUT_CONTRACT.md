# Kontrakt wyjścia badanego projektu

Artefakty w `data/projects/<slug>/<run-id>/reports/` opisują **badany projekt**, nie aplikację Research Factory.

| Plik | Zawartość |
|---|---|
| `architecture.md` | architektura logiczna i wdrożeniowa badanego projektu |
| `backlog.md` | epiki, przyrosty pionowe, zależności i DoD |
| `user_stories.md` | user stories z kryteriami akceptacji |
| `specification.feature` | kompletna specyfikacja Gherkin zachowania projektu |
| `project_structure.md` | docelowe katalogi, pliki, moduły i kierunek zależności |
| `coding_prompt.md` | końcowy prompt do implementacji badanego projektu |
| `executive_summary.md` | synteza wykonawcza |
| `synthesis.json` | ustrukturyzowane źródło powyższych plików |
| `report.md` | łączny raport z odpowiedziami, researchiem i wyjściami |

Prompt syntezy zabrania kopiowania architektury Factory do architektury badanego rozwiązania. Wnioski powstają z jednego opisu pomysłu, niezmienionych 12 pytań, odpowiedzi wybranych modeli, porównań i źródeł GitHub/Reddit/Google/WWW.

Research Factory zachowuje własną dokumentację techniczną wyłącznie w `docs/ARCHITECTURE.md`; nie jest ona materiałem wyjściowym badanego projektu.
