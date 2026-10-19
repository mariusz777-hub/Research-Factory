from pathlib import Path

import pytest

from research_factory.artifacts import ArtifactStore


def test_atomic_text_json_and_path_guard(tmp_path: Path):
    store = ArtifactStore(tmp_path)
    text_path = store.write_text(Path("a") / "file.md", "treść")
    json_path = store.write_json(Path("a") / "file.json", {"x": 1})
    assert store.resolve_public(text_path).read_text(encoding="utf-8") == "treść"
    assert '"x": 1' in store.resolve_public(json_path).read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        store.resolve_public("../escape.txt")
