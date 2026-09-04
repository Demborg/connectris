"""A scripted stand-in for the model, and the boards it hands back.

Deliberately not a simulator. What this replaced was a 227-line second puzzle designer
with its own word bank, difficulty model and revision behaviour — and its fidelity was
never the point, because what it did *not* model is what mattered: its tests passed an
empty corpus, which is how a bug that deduped every candidate against itself reached a
real run.

So this returns canned objects and nothing else. Anything that has to be true of a real
batch has to be found by running a real batch.
"""

from __future__ import annotations

import random

from connectris_pipeline.config import Config, ModelSpec
from connectris_pipeline.llm import Call, Ledger
from connectris_pipeline.schema import (
    Grade,
    ProposedGroup,
    ProposedPuzzle,
    RedTeamReport,
    SolveAttempt,
    SolvedGroup,
)

CONFIG = Config(solver=ModelSpec("fake-solver", thinking_level="low"), concurrency=4)

#: Five categories each, all distinct across boards, so a batch can be deduped for real.
BOARDS: list[list[tuple[str, list[str]]]] = [
    [
        ("Hand tools", ["HAMMER", "CHISEL", "PLANE", "WRENCH"]),
        ("Bad weather", ["FROST", "GALE", "HAZE", "SLEET"]),
        ("Rocks", ["SHALE", "BASALT", "CHALK", "SLATE"]),
        ("Fish", ["PERCH", "SOLE", "BASS", "SKATE"]),
        ("Trees", ["BIRCH", "ALDER", "ROWAN", "ASPEN"]),
    ],
    [
        ("Sailing boats", ["KETCH", "SLOOP", "BARGE", "CANOE"]),
        ("Currencies", ["PESO", "RAND", "YEN", "DINAR"]),
        ("Body parts", ["SPINE", "PALM", "TEMPLE", "IRIS"]),
        ("Flowers", ["ASTER", "PEONY", "LILAC", "TULIP"]),
        ("Music notation", ["TEMPO", "CHORD", "SCALE", "CLEF"]),
    ],
    [
        ("Sewing kit", ["THIMBLE", "BOBBIN", "HEM", "SEAM"]),
        ("___ STONE", ["LIME", "KEY", "MILE", "BRIM"]),
        ("Typography", ["SERIF", "KERNING", "GUTTER", "LIGATURE"]),
        ("Aircraft", ["JET", "GLIDER", "ROCKET", "BLIMP"]),
        ("Big top", ["TRAPEZE", "CLOWN", "JUGGLER", "UNICYCLE"]),
    ],
]

CLEAN = RedTeamReport(ambiguous_words=[], alternatives=[], verdict="clean")
PASSES = Grade(verdict="accept", fairness=5, elegance=4, reasons="scripted", revised_groups=[])


class ScriptedLLM:
    """Hands back whatever it was told to, in order. `recovers` drives the solver."""

    backend = "scripted"

    def __init__(
        self,
        *,
        boards: list[list[tuple[str, list[str]]]] | None = None,
        red: RedTeamReport = CLEAN,
        grade: Grade = PASSES,
        recovers: int = 3,
    ) -> None:
        self.ledger = Ledger()
        self._boards = list(BOARDS if boards is None else boards)
        self._red = red
        self._grade = grade
        self._recovers = recovers
        self._proposed = 0
        #: Word set -> answer key, so the solver can score whichever board it is shown.
        self._keys: dict[frozenset[str], list[tuple[str, list[str]]]] = {}

    async def generate(self, *, stage, model, system, prompt, schema, seed=None):
        self.ledger.add(Call(stage=stage, model=model.key, input_tokens=len(prompt) // 4))
        if schema is ProposedPuzzle:
            return self._propose()
        if schema is SolveAttempt:
            return self._solve(prompt)
        if schema is RedTeamReport:
            return self._red
        if schema is Grade:
            return self._grade
        raise NotImplementedError(schema)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return []

    def _propose(self) -> ProposedPuzzle:
        rows = self._boards[self._proposed % len(self._boards)]
        self._proposed += 1
        self._keys[frozenset(w for _, ws in rows for w in ws)] = rows
        return ProposedPuzzle(
            name=f"Board {self._proposed}",
            groups=[
                ProposedGroup(label=label, words=list(ws), trap=f"{ws[0]} baits another row")
                for label, ws in rows
            ],
            hardest_group=rows[-1][0],
        )

    def _solve(self, prompt: str) -> SolveAttempt:
        shown = {w for w in prompt.split() if w.isupper()}
        rows = next((r for k, r in self._keys.items() if k <= shown), None)
        if rows is None:
            return SolveAttempt(groups=[])
        found = [
            SolvedGroup(category=label, words=list(ws)) for label, ws in rows[: self._recovers]
        ]
        loose = [w for _, ws in rows[self._recovers :] for w in ws]
        # Shuffled, or the leftovers fall back into their own rows in order and the
        # scripted solver accidentally solves every board.
        random.Random(len(loose)).shuffle(loose)
        found += [
            SolvedGroup(category="not sure", words=loose[i : i + 4])
            for i in range(0, len(loose), 4)
        ]
        return SolveAttempt(groups=found)
