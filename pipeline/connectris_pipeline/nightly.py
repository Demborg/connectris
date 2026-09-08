"""One night's work: decide whether to spend anything, and if so publish one board.

The pipeline is the expensive part and this is the part that decides whether it runs at
all. Two gates, in this order, and both of them exist to stop money leaving:

**Is tomorrow already covered?** The job is idempotent by date. Running it twice in a
night, or retrying a task that already got as far as publishing, does nothing the second
time — which is what lets the Cloud Run Job be configured with retries at all.

**Has anyone played?** A night of generation costs about $0.33 and the game may have nobody
playing it. The signal is a finished run — the client posts one from `finish()` and from
nowhere else, so a record is a player who saw a board through to a win or a loss — against
the board that is up now, within a window. The window is what makes this safe to leave
running: "has this board ever been played" is true forever once it is true once, so a
generator gated on it would keep billing a project whose last player left in March.

The board demand is read from is the one already live, not the one about to be written.
Running late in the evening and publishing for tomorrow is what makes that fair: today's
board has had most of a day in front of whoever was going to play it, and the board this
produces does not go up for another couple of hours.

What is deliberately *not* here: a retry on a night that generates nothing. A ceiling of
five proposals that all failed is a night the pipeline had a bad idea about, and paying
twice for it is the shape of spending this whole module exists to prevent. The board that
is up stays up, which is a game that repeats a day rather than a game with a hole in it.
"""

from __future__ import annotations

import json
import logging
import zlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from .categories import CategorySource
from .config import Config
from .corpus import load as load_shipped
from .day import shift
from .language import get as get_language
from .llm import LLM
from .pipeline import Run
from .pipeline import run as run_pipeline
from .record import Candidate
from .spec import Puzzle
from .stages import gloss as gloss_board
from .store import GameStore, Published, corpus_of

log = logging.getLogger(__name__)

#: How far back a finished run still counts as somebody playing. A day and a half: long
#: enough that anyone who played yesterday keeps tonight's board coming, short enough that
#: a game nobody has touched since the day before last stops costing anything.
DEMAND_WINDOW_HOURS = 36

Verdict = Literal["generate", "scheduled", "idle"]


@dataclass(frozen=True)
class Plan:
    """Whether tonight spends money, and the sentence explaining why."""

    verdict: Verdict
    reason: str
    #: The day a board written tonight would be due.
    live_on: str
    #: The board demand was read from. Empty when there was none to read.
    measured_on: str = ""


def plan(
    store: GameStore,
    *,
    language: str = "en",
    now: datetime | None = None,
    window_hours: int = DEMAND_WINDOW_HOURS,
    force: bool = False,
) -> Plan:
    """Read the schedule and the play log, and decide. No model, no cost, no writes.

    Everything here is per language, and it has to be. Two languages publish on the same
    days, so a shared schedule would read Swedish's board as covering English's tomorrow
    and one of the two would never generate again; and demand is per language by its
    nature — nobody playing the Swedish board is not evidence that nobody is playing.
    """
    at = now or datetime.now(UTC)
    day = at.date().isoformat()
    tomorrow = shift(day, 1)
    schedule = [b for b in store.schedule() if b.puzzle.language == language]

    # Tomorrow specifically, not "anything dated ahead". The job only ever writes tomorrow,
    # so tomorrow is the only day it can collide on — and a board hand-scheduled for next
    # Friday must not be read as the schedule being covered, or every day between now and
    # then goes ungenerated.
    if covered := [b for b in schedule if b.live_on == tomorrow]:
        return Plan(
            "scheduled",
            f"{covered[0].puzzle.id} is already written for {tomorrow}",
            live_on=tomorrow,
        )

    live = [b for b in schedule if b.live_on <= day]
    if not live:
        # Nothing has ever been published, so there is no demand to measure and no board
        # for a player to have finished. Refusing here would mean the gate could never
        # open, so the first board is always allowed.
        return Plan("generate", "no board is live yet; nothing to wait for", live_on=tomorrow)

    current = max(live, key=lambda b: b.live_on)
    if force:
        return Plan(
            "generate",
            "--force, so demand was not consulted",
            live_on=tomorrow,
            measured_on=current.puzzle.id,
        )

    since = at - timedelta(hours=window_hours)
    played = store.finished_runs(current.puzzle.id, since_ms=int(since.timestamp() * 1000))
    detail = f"{current.puzzle.id} (live since {current.live_on}) in the last {window_hours}h"
    if played == 0:
        return Plan("idle", f"nobody finished {detail}", tomorrow, current.puzzle.id)
    return Plan(
        "generate",
        f"{played} finished run(s) on {detail}",
        live_on=tomorrow,
        measured_on=current.puzzle.id,
    )


@dataclass
class Night:
    """What happened. `run` and `published` are set only as far as the night got."""

    plan: Plan
    run: Run | None = None
    published: Published | None = None

    def summary(self) -> str:
        lines = [f"{self.plan.verdict}: {self.plan.reason}"]
        if self.run is not None:
            lines.append("")
            lines.append(self.run.summary())
        lines.append("")
        if self.published is not None:
            lines.append(f"published {self.published.puzzle.id} for {self.published.live_on}")
        elif self.run is not None:
            lines.append(
                f"nothing accepted; the board that is up stays up until {self.plan.live_on} "
                "at the earliest"
            )
        return "\n".join(lines)


def seed_for(day: str) -> int:
    """A run seed fixed for a given night and different from the night before.

    A constant default seed looked like the reproducible choice and is the wrong kind of
    reproducible for a job that runs every night: everything downstream that draws from
    the run's rng would draw the same thing every night forever. The wordplay device is no
    longer one of those — `draw` walks that cycle from the date's own ordinal, because
    that was too important to leave to a seed — but the theme choice still is, as soon as
    the pool grows past its cooldown and there is more than one candidate to shuffle.

    Keyed on the date the board is *for*, so re-running a night reproduces that night, and
    `crc32` because `hash` is salted per process.
    """
    return zlib.crc32(day.encode()) & 0x7FFFFFFF


async def tonight(
    llm: LLM,
    cfg: Config,
    store: GameStore,
    *,
    count: int,
    seed: int | None = None,
    out_dir: Path | None = None,
    source: CategorySource | None = None,
    now: datetime | None = None,
    window_hours: int = DEMAND_WINDOW_HOURS,
    force: bool = False,
    dry_run: bool = False,
) -> Night:
    """Gate, generate, publish. The whole of what the scheduled job does.

    One language per call. The scheduler runs it once per language, which keeps a night
    that fails for Swedish from taking English's board down with it, and keeps the two
    bills separable.
    """
    lang = get_language(cfg.language)
    decided = plan(store, language=lang.code, now=now, window_hours=window_hours, force=force)
    log.info("%s: %s", decided.verdict, decided.reason)
    if decided.verdict != "generate":
        return Night(plan=decided)

    schedule = store.schedule()

    # Two different corpora, deliberately. What a board must be *new* against is
    # everything the game holds, which is the database. What it is shown as an *example*
    # of a good board is the hand-written pair in puzzles.json — those were written to be
    # the quality target, and feeding the generator its own recent output instead is how a
    # house style drifts into a rut with nothing to measure it against.
    # Narrowed to the language being written. The examples carry the construction standard
    # and an English board is a poor example of a Swedish one — and once Swedish boards
    # have shipped, they are the standard for the next Swedish board.
    examples, _ = load_shipped(language=lang.code)
    if not examples:
        examples, _ = load_shipped()

    result = await run_pipeline(
        llm,
        cfg,
        count=count,
        seed=seed_for(decided.live_on) if seed is None else seed,
        out_dir=out_dir,
        corpus=corpus_of(schedule, lang.code),
        # Three, not two. It was two because two were hand-written; a seed set is however
        # many somebody wrote, and truncating it silently threw a third of one away.
        examples=examples[:3],
        source=source,
    )

    # The review queue, such as it is. A board that reached `review` cost the same as one
    # that was accepted and is being walked away from, so it goes into the log where it can
    # be read later and put in by hand — the run directory it is also in does not outlive
    # the task. Rejects are not logged: those are boards the machinery is sure about.
    for c in result.by_verdict("review"):
        log.info(
            "reviewable %s: %s | %s",
            c.id,
            "; ".join(c.decision.reasons if c.decision else []),
            json.dumps(c.puzzle.to_game_json(), ensure_ascii=False),
        )

    accepted = result.by_verdict("accept")
    if not accepted:
        return Night(plan=decided, run=result)

    # One board a day. `run` stops at the first accept, so there is normally exactly one
    # here; `--all` can produce more, and the rest are left in the run directory for a
    # human rather than stacked onto future dates by a job that cannot see whether they
    # are any good.
    board = _publishable(accepted[0], decided.live_on)

    # The notes a player reads under a solved row, written now that there is a board worth
    # explaining. Last, and after the accept, because 45% of candidates are thrown away
    # and glossing those would be paying to explain puzzles nobody will see.
    #
    # Not fatal. A board with no notes is the board this game shipped for its first weeks
    # and its rows simply do not open; a board withheld because one stage of prose failed
    # is a day with no puzzle on it.
    try:
        board = Published(puzzle=await gloss_board(llm, cfg, board.puzzle), live_on=board.live_on)
    except Exception:
        log.exception("could not write notes for %s; publishing it without them", board.puzzle.id)

    # Logged before the write, not after. The run directory lives in the container and dies
    # with the task, so if `publish` throws — a permission, a bad date, an outage — this log
    # line is the only surviving copy of a board that has already been paid for, and it can
    # be put in by hand from here.
    log.info(
        "accepted %s for %s: %s",
        board.puzzle.id,
        board.live_on,
        json.dumps(board.puzzle.to_game_json(), ensure_ascii=False),
    )

    if dry_run:
        log.info("--dry-run, not publishing %s", board.puzzle.id)
        return Night(plan=decided, run=result)

    store.publish(
        board.puzzle,
        live_on=board.live_on,
        source=f"pipeline/{result.directory.name}" if result.directory else "pipeline",
    )
    return Night(plan=decided, run=result, published=board)


def _publishable(candidate: Candidate, live_on: str) -> Published:
    """The board as the game will hold it, under the date it is due.

    The candidate id doubles as the puzzle id, and it carries the run stamp — so a board's
    provenance is legible from its URL, and two nights can never collide on one.
    """
    return Published(
        puzzle=Puzzle(
            id=candidate.puzzle.id,
            name=candidate.puzzle.name,
            groups=candidate.puzzle.groups,
            language=candidate.puzzle.language,
        ),
        live_on=live_on,
    )


__all__ = ["DEMAND_WINDOW_HOURS", "Night", "Plan", "plan", "seed_for", "tonight"]
