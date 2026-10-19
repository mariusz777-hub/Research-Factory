from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from itertools import combinations


_WORD = re.compile(r"[\wąćęłńóśźż-]+", re.IGNORECASE)
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
_NUMBER = re.compile(r"(?<!\w)\d+(?:[.,]\d+)?%?")
NEGATIONS = {"nie", "brak", "bez", "nigdy", "none", "no", "not", "cannot", "can't"}
STOP = {
    "oraz", "który", "która", "które", "jest", "są", "dla", "jako", "przez", "tego",
    "this", "that", "with", "from", "into", "have", "has", "the", "and", "or", "a", "an",
}


@dataclass(frozen=True)
class ComparisonResult:
    agreements: list[dict]
    conflicts: list[dict]
    gaps: list[str]
    summary: str

    def to_dict(self) -> dict:
        return asdict(self)


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in _WORD.findall(text) if len(token) > 2 and token.lower() not in STOP}


def _sentences(text: str) -> list[str]:
    result = []
    for part in _SENTENCE.split(text):
        clean = re.sub(r"^[-*#\d.()\s]+", "", part).strip()
        if len(clean) >= 15:
            result.append(clean[:900])
    return result[:120]


def _similarity(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _polarity(text: str) -> bool:
    return bool(_tokens(text) & NEGATIONS)


def compare_responses(responses: dict[str, str], expected_models: list[str]) -> ComparisonResult:
    gaps = [f"Brak odpowiedzi modelu {model}." for model in expected_models if not responses.get(model)]
    statements = {model: _sentences(text) for model, text in responses.items() if text.strip()}
    agreement_rows: list[dict] = []
    conflict_rows: list[dict] = []
    seen_agreements: set[tuple] = set()
    seen_conflicts: set[tuple] = set()

    for left_model, right_model in combinations(statements, 2):
        for left in statements[left_model]:
            best_right = ""
            best_score = 0.0
            for right in statements[right_model]:
                score = _similarity(left, right)
                if score > best_score:
                    best_score, best_right = score, right
            if not best_right:
                continue
            left_numbers = set(_NUMBER.findall(left))
            right_numbers = set(_NUMBER.findall(best_right))
            polarity_conflict = _polarity(left) != _polarity(best_right) and best_score >= 0.28
            number_conflict = bool(left_numbers and right_numbers and left_numbers != right_numbers and best_score >= 0.25)
            if polarity_conflict or number_conflict:
                key = (left_model, right_model, left[:120], best_right[:120])
                if key not in seen_conflicts:
                    seen_conflicts.add(key)
                    conflict_rows.append(
                        {
                            "models": [left_model, right_model],
                            "left": left,
                            "right": best_right,
                            "reason": "sprzeczna polaryzacja" if polarity_conflict else "różne wartości liczbowe",
                            "classification": "conflicting",
                            "similarity": round(best_score, 3),
                        }
                    )
            elif best_score >= 0.42:
                key = tuple(sorted((left_model, right_model))) + (left[:160],)
                if key not in seen_agreements:
                    seen_agreements.add(key)
                    agreement_rows.append(
                        {
                            "claim": left,
                            "models": [left_model, right_model],
                            "support": best_right,
                            "classification": "consensus_unverified",
                            "similarity": round(best_score, 3),
                        }
                    )

    if len(responses) < 2:
        gaps.append("Porównanie wymaga co najmniej dwóch odpowiedzi; wynik ma ograniczoną wiarygodność.")
    if not agreement_rows:
        gaps.append("Nie wykryto wystarczająco podobnych twierdzeń między modelami.")
    cited = {model: bool(re.search(r"https?://|źródł|source|github", text, re.I)) for model, text in responses.items()}
    missing_citations = [model for model, has_citations in cited.items() if not has_citations]
    if missing_citations:
        gaps.append("Brak jawnych odwołań do źródeł: " + ", ".join(sorted(missing_citations)) + ".")

    agreement_rows = sorted(agreement_rows, key=lambda item: item["similarity"], reverse=True)[:30]
    conflict_rows = sorted(conflict_rows, key=lambda item: item["similarity"], reverse=True)[:30]
    summary = (
        f"Modele z odpowiedzią: {len(responses)}/{len(expected_models)}; "
        f"zgodności: {len(agreement_rows)}; sprzeczności: {len(conflict_rows)}; braki: {len(gaps)}."
    )
    return ComparisonResult(agreement_rows, conflict_rows, gaps, summary)
