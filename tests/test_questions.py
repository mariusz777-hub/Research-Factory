from pathlib import Path

import pytest

from research_factory.question_library import load_question_library


def test_library_renders_every_enabled_question(library):
    questions = library.render(project_name="Projekt X", idea="Pomysł o wystarczająco długim opisie")
    assert len(questions) == 12
    assert len({item.template_id for item in questions}) == len(questions)
    assert all("Projekt X" in item.prompt for item in questions)
    assert all("{{" not in item.prompt for item in questions)
    assert all(len(item.checksum) == 64 for item in questions)


def test_duplicate_template_id_is_rejected(tmp_path: Path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        "system_prompt: test\nquestions:\n"
        "  - {id: x, template: 'A {{ idea }}'}\n"
        "  - {id: x, template: 'B {{ idea }}'}\n",
        encoding="utf-8",
    )
    library = load_question_library(path)
    with pytest.raises(ValueError, match="Powtórzone"):
        library.render(project_name="P", idea="I")
