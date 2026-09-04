"""Every knob in one place, and every knob overridable from a TOML file.

The numbers here are the part of the pipeline most likely to be wrong. They are reasoned
from the design, not measured — see the honest caveat in DESIGN.md: until there is human
play data this is a filter for *broken* puzzles, not a difficulty oracle. So they live in
config, the run stores the config it used, and `regrade` can re-decide an old run under
new numbers without spending a token.
"""

from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Literal

#: Gemini 3 takes a thinking *level*. `minimal` is deliberately absent: 3.8 Flash rejects
#: it outright, and a solver ensemble that errors is worse than one that thinks a little.
ThinkingLevel = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class ModelSpec:
    """One model in one configuration. The solver ensemble is a list of these.

    Two generations, two thinking knobs. Gemini 3 takes `thinking_level`; 2.5 takes a
    `thinking_budget` in tokens (0 to switch thinking off). Whichever is set is sent, and
    setting both is a config error rather than a silent precedence rule.
    """

    name: str
    thinking_level: ThinkingLevel | None = None
    thinking_budget: int | None = None
    #: Left unset on purpose. Google's Gemini 3 guidance is to keep temperature at its
    #: default of 1.0 — below that the models loop and degrade on reasoning tasks — so
    #: `None` means "do not send it", and sampling diversity comes from `seed` instead
    #: (see stages/solve.py). Only set this on a 2.5-family model that wants it.
    temperature: float | None = None

    def __post_init__(self) -> None:
        if self.thinking_level is not None and self.thinking_budget is not None:
            raise ValueError(f"{self.name}: set thinking_level or thinking_budget, not both")

    @property
    def key(self) -> str:
        thinking = self.thinking_level or (
            f"budget:{self.thinking_budget}" if self.thinking_budget is not None else "default"
        )
        return f"{self.name}/{thinking}"


@dataclass(frozen=True)
class Thresholds:
    """Where auto-accept stops and the review queue starts.

    Solve rates here are over the *weak* ensemble, which is a proxy for difficulty and
    not a measurement of it. Both ends are pruned: a puzzle nothing can touch is usually
    unfair rather than hard, and one every cheap model solves is not a puzzle.
    """

    #: Mean over categories of "what fraction of solver attempts recovered this exact four".
    min_mean_recovery: float = 0.15
    max_mean_recovery: float = 0.80
    #: Fraction of attempts that got all five rows. Weak models should mostly fail this.
    max_full_solve_rate: float = 0.50
    #: Category-name similarity, over recovered groups only. Catches "found it but can't
    #: say why", which is the unfairness a solver alone will never surface.
    min_legibility: float = 0.45
    #: Any word the red team can file in two places blocks auto-accept.
    max_ambiguous_words: int = 0
    #: Grader's 1-5 scores.
    min_fairness: int = 4
    min_elegance: int = 3


@dataclass(frozen=True)
class Config:
    #: One puzzle per call — see README on why not batches. Thinking all the way up:
    #: this is the stage where a night's quality is decided and it runs twenty times.
    proposer: ModelSpec = ModelSpec("gemini-3.8-flash", thinking_level="high")
    #: Deliberately weak, deliberately mixed. Two generations and two tiers, because
    #: mixing model families is a feature: it stops puzzle quality overfitting to one
    #: model's blind spots. Add a Claude-on-Vertex entry once llm.py has that arm.
    solvers: tuple[ModelSpec, ...] = (
        ModelSpec("gemini-3.5-flash-lite", thinking_level="low"),
        ModelSpec("gemini-3.1-flash-lite", thinking_level="low"),
        ModelSpec("gemini-2.5-flash-lite", thinking_budget=0),
    )
    attempts_per_solver: int = 3
    #: The critical stage. Strong model, and not the same call as solving.
    red_team: ModelSpec = ModelSpec("gemini-3.8-flash", thinking_level="high")
    grader: ModelSpec = ModelSpec("gemini-3.8-flash", thinking_level="high")
    #: Empty string falls back to lexical similarity, which keeps the pipeline runnable
    #: without an embeddings endpoint at a cost in precision. `gemini-embedding-001` is
    #: not served on Vertex here; `-2` is.
    embedding_model: str = "gemini-embedding-2"

    thresholds: Thresholds = field(default_factory=Thresholds)

    #: In-flight model calls across the whole run.
    concurrency: int = 8
    #: How many times a 'revise' verdict may send a puzzle back around. Two is plenty;
    #: a puzzle that needs three rewrites was a bad idea, not a bad draft.
    max_revisions: int = 1
    #: Retries per model call, for transient errors and for output that will not parse.
    max_retries: int = 3

    def to_json(self) -> dict:
        return asdict(self)


def load(path: Path | None) -> Config:
    """Overlay a TOML file on the defaults. Absent keys keep their default."""
    cfg = Config()
    if path is None:
        return cfg

    raw = tomllib.loads(path.read_text())

    def model(key: str, current: ModelSpec) -> ModelSpec:
        return replace(current, **raw[key]) if key in raw else current

    if "solvers" in raw:
        solvers = tuple(ModelSpec(**s) for s in raw["solvers"])
    else:
        solvers = cfg.solvers

    thresholds = Thresholds(**raw["thresholds"]) if "thresholds" in raw else cfg.thresholds
    top = {
        k: v
        for k, v in raw.items()
        if k
        in {"attempts_per_solver", "embedding_model", "concurrency", "max_revisions", "max_retries"}
    }

    return replace(
        cfg,
        proposer=model("proposer", cfg.proposer),
        red_team=model("red_team", cfg.red_team),
        grader=model("grader", cfg.grader),
        solvers=solvers,
        thresholds=thresholds,
        **top,
    )
