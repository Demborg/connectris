"""A provider that never leaves the machine.

Not a stub: it plays every role well enough that the whole pipeline — proposal through
decision, artifacts, exporter — runs end to end with no credentials, which is what makes
the orchestration testable and lets you tune thresholds against a known answer key before
spending a token. Its solvers get groups right with a seeded probability that falls with
category difficulty and rises with temperature, so recovery rates come out varied and
reproducible rather than degenerate.

It is a fixture, not a puzzle designer. Nothing it invents should ever ship.
"""

from __future__ import annotations

import random
import re
import zlib
from dataclasses import dataclass

from .config import ModelSpec
from .llm import Call, Ledger
from .schema import (
    AmbiguousWord,
    Grade,
    ProposedGroup,
    ProposedPuzzle,
    RedTeamReport,
    SolveAttempt,
    SolvedGroup,
)

#: (label, four words, how hard it is for a weak solver, 0 easy .. 1 nearly invisible)
BANK: list[tuple[str, list[str], float]] = [
    ("Hand tools", ["HAMMER", "CHISEL", "PLANE", "WRENCH"], 0.2),
    ("Aircraft", ["JET", "GLIDER", "ROCKET", "BLIMP"], 0.15),
    ("Bad weather", ["FROST", "GALE", "HAZE", "SLEET"], 0.3),
    ("Rocks", ["SHALE", "BASALT", "CHALK", "SLATE"], 0.35),
    ("Sewing kit", ["THIMBLE", "BOBBIN", "HEM", "SEAM"], 0.4),
    ("___ STONE", ["LIME", "KEY", "MILE", "BRIM"], 0.8),
    ("Fish", ["PERCH", "SOLE", "BASS", "SKATE"], 0.55),
    ("Music notation", ["TEMPO", "CHORD", "SCALE", "CLEF"], 0.3),
    ("Trees", ["BIRCH", "ALDER", "ROWAN", "ASPEN"], 0.25),
    ("Sailing boats", ["KETCH", "SLOOP", "BARGE", "CANOE"], 0.4),
    ("Currencies", ["PESO", "RAND", "YEN", "DINAR"], 0.2),
    ("Body parts", ["SPINE", "PALM", "TEMPLE", "IRIS"], 0.5),
    ("Flowers", ["ASTER", "PEONY", "LILAC", "TULIP"], 0.2),
    ("Under the big top", ["TRAPEZE", "CLOWN", "JUGGLER", "UNICYCLE"], 0.45),
    ("Typography", ["SERIF", "KERNING", "GUTTER", "LIGATURE"], 0.6),
]


@dataclass
class _Key:
    words: frozenset[str]
    groups: list[tuple[str, list[str], float]]


def _effort(model: ModelSpec) -> float:
    """How hard this solver is trying, 0..1, from whichever thinking knob it uses."""
    if model.thinking_level is not None:
        return {"low": 0.0, "medium": 0.5, "high": 1.0}[model.thinking_level]
    if model.thinking_budget is not None:
        return 0.0 if model.thinking_budget == 0 else 1.0
    return 0.5


def _stable_hash(words: frozenset[str]) -> int:
    """crc32, because `hash` is salted per process and runs must be reproducible."""
    return zlib.crc32(" ".join(sorted(words)).encode())


class MockLLM:
    """Deterministic given its seed. Same seed, same run, byte for byte."""

    backend = "mock"

    def __init__(
        self, *, ledger: Ledger | None = None, seed: int = 0, ambiguity_rate: float = 0.3
    ) -> None:
        self._rng = random.Random(seed)
        self.ledger = ledger or Ledger()
        self._keys: list[_Key] = []
        #: Share of *boards* given a planted ambiguity, so a dry run exercises the review
        #: and revision paths too. Keyed off the words, so it survives re-runs.
        self._ambiguity_rate = ambiguity_rate
        self._proposed = 0

    # -- the seam ---------------------------------------------------------------

    async def generate(
        self, *, stage, model: ModelSpec, system: str, prompt: str, schema, seed: int | None = None
    ):
        self.ledger.add(
            Call(
                stage=stage,
                model=f"mock:{model.key}",
                input_tokens=len(prompt) // 4,
                output_tokens=64,
                seconds=0.0,
            )
        )
        if schema is ProposedPuzzle:
            return self._propose()
        if schema is SolveAttempt:
            return self._solve(prompt, model, seed)
        if schema is RedTeamReport:
            return self._red_team(prompt)
        if schema is Grade:
            return self._grade(prompt)
        raise NotImplementedError(f"mock has no answer for {schema}")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return []  # forces the lexical similarity path, which is what a bare run gets

    # -- roles ------------------------------------------------------------------

    def _propose(self) -> ProposedPuzzle:
        while True:
            picked = self._rng.sample(BANK, 5)
            words = [w for _, ws, _ in picked for w in ws]
            if len(set(words)) == len(words):
                break
        self._proposed += 1
        self._keys.append(_Key(frozenset(words), picked))
        return ProposedPuzzle(
            name=f"Mock board {self._proposed}",
            groups=[
                ProposedGroup(label=label, words=list(ws), trap=f"{ws[0]} baits another row")
                for label, ws, _ in picked
            ],
            hardest_group=picked[-1][0],
        )

    def _solve(self, prompt: str, model: ModelSpec, seed: int | None) -> SolveAttempt:
        key = self._lookup(prompt)
        if key is None:
            return SolveAttempt(groups=[])

        # Honour the seed the way the real API does: same seed, same attempt.
        rng = random.Random(seed) if seed is not None else self._rng
        effort = _effort(model)

        found: list[SolvedGroup] = []
        loose: list[str] = []
        for label, words, difficulty in key.groups:
            p = max(0.02, min(0.95, (1.0 - difficulty) * (0.6 + 0.35 * effort)))
            if rng.random() < p:
                found.append(SolvedGroup(category=self._name(label, rng), words=list(words)))
            else:
                loose.extend(words)

        rng.shuffle(loose)
        for i in range(0, len(loose), 4):
            found.append(SolvedGroup(category="not sure", words=loose[i : i + 4]))
        return SolveAttempt(groups=found)

    def _name(self, label: str, rng: random.Random) -> str:
        """Sometimes the exact label, sometimes a paraphrase — legibility needs both."""
        if rng.random() < 0.35:
            return rng.choice(
                [f"kinds of {label.lower()}", f"{label} (I think)", "words that go together"]
            )
        return label

    def _red_team(self, prompt: str) -> RedTeamReport:
        key = self._lookup(prompt)
        if key is None or _stable_hash(key.words) % 100 >= self._ambiguity_rate * 100:
            return RedTeamReport(ambiguous_words=[], alternatives=[], verdict="clean")
        label, words, _ = key.groups[0]
        other = key.groups[1][0]
        return RedTeamReport(
            ambiguous_words=[
                AmbiguousWord(
                    word=words[0],
                    intended_label=label,
                    also_fits=other,
                    why="mock ambiguity, planted to exercise the review queue",
                )
            ],
            alternatives=[],
            verdict="soft",
        )

    def _grade(self, prompt: str) -> Grade:
        clean = "nothing found" in prompt
        if clean:
            return Grade(
                verdict="accept", fairness=5, elegance=4, reasons="mock grade", revised_groups=[]
            )

        # Exercise the revision loop for real: swap the flagged word for a spare, and
        # register the new board so the solvers can still find its answer key.
        key = self._lookup(prompt)
        if key is None:
            return Grade(
                verdict="reject",
                fairness=2,
                elegance=2,
                reasons="mock grade: could not repair",
                revised_groups=[],
            )

        spare = next(w for _, ws, _ in BANK for w in ws if w not in key.words)
        groups = [(label, list(ws), d) for label, ws, d in key.groups]
        groups[0][1][0] = spare
        self._keys.append(_Key(frozenset(w for _, ws, _ in groups for w in ws), groups))
        return Grade(
            verdict="revise",
            fairness=3,
            elegance=3,
            reasons="mock grade: red team flagged a word, swapped it",
            revised_groups=[
                ProposedGroup(label=label, words=list(ws), trap=f"{ws[0]} baits another row")
                for label, ws, _ in groups
            ],
        )

    # -- plumbing ---------------------------------------------------------------

    def _lookup(self, prompt: str) -> _Key | None:
        """Find which board a prompt is about, whatever shape the prompt is."""
        seen = set(re.findall(r"[A-Z][A-Z'\- ]{1,11}", prompt))
        seen = {s.strip() for s in seen}
        for key in self._keys:
            if key.words <= seen:
                return key
        return None
