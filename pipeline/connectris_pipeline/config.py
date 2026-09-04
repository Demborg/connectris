"""Every knob in one place, and every knob overridable from a TOML file.

The numbers here are the part of the pipeline most likely to be wrong. They are reasoned
from the design, not measured — see the honest caveat in DESIGN.md: until there is human
play data this is a filter for *broken* puzzles, not a difficulty oracle. So they live in
config, the run stores the config it used, and `regrade` can re-decide an old run under
new numbers without spending a token.
"""

from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass, field, fields, replace
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

    Three numbers, down from seven. The first real run measured how often each of the
    original seven fired across 20 candidates: `min_legibility` never, `max_mean_recovery`
    once, `min_mean_recovery` once, `max_full_solve_rate` twice — and **none of the four
    ever changed a verdict**, because the grader had already rejected those boards for
    reasons of its own. Only the grader's two scores were load-bearing.

    So the evidence stages stayed and their gates went. Solver recovery, legibility and
    the red-team report all still reach the grader as prose in the digest, and the grader
    reasons from them out loud — it has quoted "0% solver completion rate" and "an
    abysmal naming match (0.09)" back in its rejections. They are better as testimony
    than as tripwires.

    What survives is one gate the grader structurally cannot supply. A board can read as
    elegant and still be trivial, and the grader never sees it played.
    """

    #: Mean over categories of "did the weak solver recover this exact four". A cheap
    #: model reconstructing most of the board is the one failure a good grade can hide.
    max_mean_recovery: float = 0.80
    #: Grader's 1-5 scores.
    min_fairness: int = 4
    min_elegance: int = 3


@dataclass(frozen=True)
class Config:
    #: One puzzle per call — see README on why not batches. Thinking all the way up:
    #: this is the stage where a night's quality is decided and it runs twenty times.
    proposer: ModelSpec = ModelSpec("gemini-3.8-flash", thinking_level="high")
    #: One weak model, one attempt. The original ensemble was three models at three
    #: attempts each, on the theory that mixing families stops quality overfitting to one
    #: model's blind spots. The first real run falsified it: the three correlated 0.71 to
    #: 0.85 — a capability ladder measuring one latent variable, not independent blind
    #: spots — and three attempts reproduced nine on 20 verdicts out of 20, mean recovery
    #: differing by 0.044. Nine calls a board bought nothing a single call did not.
    #:
    #: 3.1-flash-lite is kept for having the highest mean and the widest spread. If a
    #: second family ever joins, it should be a genuinely different one, and it should be
    #: added because a run showed the single solver missing something.
    solver: ModelSpec = ModelSpec("gemini-3.1-flash-lite", thinking_level="low")
    #: The critical stage. Strong model, and not the same call as solving.
    red_team: ModelSpec = ModelSpec("gemini-3.8-flash", thinking_level="high")
    grader: ModelSpec = ModelSpec("gemini-3.8-flash", thinking_level="high")
    thresholds: Thresholds = field(default_factory=Thresholds)

    #: In-flight model calls across the whole run.
    concurrency: int = 8
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

    known = {f.name for f in fields(Config)}
    if unknown := raw.keys() - known:
        # A typo used to be silently ignored: `concurency = 99` fell through the filter
        # below and the run used the default, with no warning. Someone tuning thresholds
        # overnight got the defaults and no signal.
        raise ValueError(f"{path}: unknown config keys: {', '.join(sorted(unknown))}")

    def model(key: str, current: ModelSpec) -> ModelSpec:
        return replace(current, **raw[key]) if key in raw else current

    thresholds = Thresholds(**raw["thresholds"]) if "thresholds" in raw else cfg.thresholds
    top = {k: v for k, v in raw.items() if k in {"concurrency", "max_retries"}}

    return replace(
        cfg,
        proposer=model("proposer", cfg.proposer),
        red_team=model("red_team", cfg.red_team),
        grader=model("grader", cfg.grader),
        solver=model("solver", cfg.solver),
        thresholds=thresholds,
        **top,
    )
