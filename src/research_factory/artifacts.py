from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def safe_name(value: str, fallback: str = "item") -> str:
    result = _SAFE.sub("-", value.strip()).strip("-.")
    return (result or fallback)[:180]


class ArtifactStore:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def run_root(self, project_slug: str, run_id: str) -> Path:
        path = self.root / "projects" / safe_name(project_slug) / safe_name(run_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _atomic_write(self, path: Path, content: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        except Exception:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise
        return path

    def write_text(self, relative: Path, content: str) -> str:
        destination = (self.root / relative).resolve()
        destination.relative_to(self.root)
        self._atomic_write(destination, content)
        return destination.relative_to(self.root).as_posix()

    def write_json(self, relative: Path, data: Any) -> str:
        return self.write_text(relative, json.dumps(data, ensure_ascii=False, indent=2, default=str))

    def append_event(self, project_slug: str, run_id: str, event: dict) -> str:
        path = self.run_root(project_slug, run_id) / "logs" / "events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False, separators=(",", ":"), default=str) + "\n"
        fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o640)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
        return path.relative_to(self.root).as_posix()

    def resolve_public(self, relative: str) -> Path:
        target = (self.root / relative).resolve()
        target.relative_to(self.root)
        return target
