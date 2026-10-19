from research_factory.comparison import compare_responses


def test_comparison_detects_agreement_conflict_and_missing_model():
    responses = {
        "openai": "System powinien szyfrować dane w bazie. Limit wynosi 100 żądań na minutę.",
        "gemini": "System powinien szyfrować dane w bazie. Limit wynosi 200 żądań na minutę.",
    }
    result = compare_responses(responses, ["openai", "gemini", "deepseek"])
    assert result.agreements
    assert any(item["reason"] == "różne wartości liczbowe" for item in result.conflicts)
    assert any("deepseek" in gap for gap in result.gaps)
    assert "2/3" in result.summary
