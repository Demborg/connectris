"""Offline puzzle generation for Connectris. See DESIGN.md, phase 2, and pipeline/README.md."""

from .config import Config, ModelSpec, Thresholds
from .pipeline import Run, run
from .spec import COLS, MAX_ENTRY_LEN, MAX_TOKEN_LEN, ROWS, Group, Puzzle, validate

__all__ = [
    "COLS",
    "MAX_ENTRY_LEN",
    "MAX_TOKEN_LEN",
    "ROWS",
    "Config",
    "Group",
    "ModelSpec",
    "Puzzle",
    "Run",
    "Thresholds",
    "run",
    "validate",
]
