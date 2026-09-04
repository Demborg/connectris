"""Reading and writing the game's own puzzle file.

The pipeline's only coupling to the app is this file, and it goes both ways: shipped
puzzles are the few-shot examples and the dedupe index, and accepted candidates are
appended back into it in exactly the shape `engine.spec.ts` expects.
"""

from __future__ import annotations

import json
from pathlib import Path

from .spec import Corpus, Group, Puzzle

#: pipeline/connectris_pipeline/corpus.py -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
PUZZLES_JSON = REPO_ROOT / "src" / "lib" / "data" / "puzzles.json"


def load(path: Path = PUZZLES_JSON) -> tuple[list[Puzzle], Corpus]:
    if not path.exists():
        return [], Corpus()
    raw = json.loads(path.read_text())
    puzzles = [
        Puzzle(
            id=p["id"],
            name=p["name"],
            language=p.get("language", "en"),
            groups=[
                Group(id=g["id"], label=g["label"], words=list(g["words"])) for g in p["groups"]
            ],
        )
        for p in raw
    ]
    return puzzles, Corpus.from_game_json(raw)


def append(puzzles: list[Puzzle], path: Path = PUZZLES_JSON) -> int:
    """Append accepted puzzles, skipping ids already present. Returns how many landed.

    Written with tabs to match prettier's `useTabs`, but run `pnpm format` after: prettier
    collapses short objects onto one line and this does not try to imitate that.
    """
    existing = json.loads(path.read_text()) if path.exists() else []
    have = {p["id"] for p in existing}
    fresh = [p.to_game_json() for p in puzzles if p.id not in have]
    if not fresh:
        return 0
    path.write_text(json.dumps(existing + fresh, indent="\t", ensure_ascii=False) + "\n")
    return len(fresh)
