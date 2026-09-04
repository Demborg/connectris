"""Offline puzzle generation for Connectris. See DESIGN.md, phase 2, and pipeline/README.md."""

from .config import Config, ModelSpec, Thresholds
from .pipeline import Run, run
from .spec import COLS, MAX_WORD_LEN, ROWS, Group, Puzzle, validate

__all__ = [
    "COLS",
    "ROWS",
    "MAX_WORD_LEN",
    "Config",
    "Group",
    "ModelSpec",
    "Puzzle",
    "Run",
    "Thresholds",
    "run",
    "validate",
]
