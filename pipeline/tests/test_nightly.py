"""The gate, and the night around it.

Everything here is about money. The generator is the only expensive thing in this repo
and `plan` is the function that decides whether it runs, so these are the tests that say
what a forgotten project costs: nothing.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from conftest import BOARDS, CONFIG, MemoryCategorySource, ScriptedLLM

from connectris_pipeline import nightly
from connectris_pipeline.categories import DEVICES, Category, draw
from connectris_pipeline.day import shift
from connectris_pipeline.schema import Grade
from connectris_pipeline.spec import Group, Puzzle
from connectris_pipeline.store import MemoryStore, Published, corpus_of

NOW = datetime(2026, 9, 6, 22, 0, tzinfo=UTC)
TODAY = "2026-09-06"
TOMORROW = "2026-09-07"


def board(
    name: str, rows: list[tuple[str, list[str]]] | None = None, language: str = "en"
) -> Puzzle:
    rows = rows if rows is not None else BOARDS[0]
    return Puzzle(
        id=name,
        name=name,
        language=language,
        groups=[Group(id=label.lower(), label=label, words=list(ws)) for label, ws in rows],
    )


def ms(at: datetime) -> int:
    return int(at.timestamp() * 1000)


def store(*, live_on: str = TODAY, played: list[datetime] | None = None) -> MemoryStore:
    """A game with one board up, and whoever finished it when."""
    return MemoryStore(
        boards=[Published(puzzle=board("today"), live_on=live_on)],
        runs=[("today", ms(at)) for at in (played or [])],
    )


# --- the gate -------------------------------------------------------------------------


def test_a_finished_run_today_pays_for_tomorrows_board():
    decided = nightly.plan(store(played=[NOW - timedelta(hours=3)]), now=NOW)
    assert decided.verdict == "generate"
    assert decided.live_on == TOMORROW
    assert decided.measured_on == "today"


def test_a_game_nobody_played_costs_nothing():
    """The whole reason this exists. A project left running with no players must stop
    spending on its own, without anyone remembering to turn it off."""
    decided = nightly.plan(store(), now=NOW)
    assert decided.verdict == "idle"
    assert "nobody finished today" in decided.reason


def test_play_from_last_week_does_not_pay_for_tonight():
    """The failure this window is here to prevent.

    Gated on "has this board ever been played", a generator whose board stops changing —
    because it is broken, or because it has been idle a while — sees the same old run
    every night and bills for a new board every night forever. Demand has to be recent to
    be demand.
    """
    decided = nightly.plan(store(played=[NOW - timedelta(days=7)]), now=NOW)
    assert decided.verdict == "idle"


def test_a_run_just_inside_the_window_still_counts():
    inside = nightly.plan(store(played=[NOW - timedelta(hours=35)]), now=NOW)
    outside = nightly.plan(store(played=[NOW - timedelta(hours=37)]), now=NOW)
    assert (inside.verdict, outside.verdict) == ("generate", "idle")


def test_an_unfinished_board_is_not_a_finished_run():
    """`finished_runs` counts wins and losses. A player who opened the board and wandered
    off has told us nothing about whether the game is worth another board."""
    idle = MemoryStore(boards=[Published(puzzle=board("today"), live_on=TODAY)], runs=[])
    assert nightly.plan(idle, now=NOW).verdict == "idle"


def test_demand_is_read_from_the_board_that_is_up():
    """Not from yesterday's, and not from the archive. Someone replaying a board from
    last month is welcome, but it is not evidence that today's board found an audience."""
    played_elsewhere = MemoryStore(
        boards=[
            Published(puzzle=board("old"), live_on=shift(TODAY, -10)),
            Published(puzzle=board("today"), live_on=TODAY),
        ],
        runs=[("old", ms(NOW - timedelta(hours=1)))],
    )
    assert nightly.plan(played_elsewhere, now=NOW).verdict == "idle"


def test_the_first_board_never_waits_for_a_player():
    """An empty game has nothing for anyone to have played, so a gate that asked would
    close permanently on its first night."""
    decided = nightly.plan(MemoryStore(), now=NOW)
    assert decided.verdict == "generate"
    assert decided.measured_on == ""


def test_a_night_that_already_wrote_tomorrows_board_does_nothing_twice():
    """Idempotence by date, which is what makes the job safe to retry and safe to run by
    hand at any hour without wondering whether it already went."""
    done = store(played=[NOW - timedelta(hours=1)])
    done.boards.append(Published(puzzle=board("tomorrow"), live_on=TOMORROW))
    decided = nightly.plan(done, now=NOW)
    assert decided.verdict == "scheduled"
    assert "tomorrow is already written for 2026-09-07" in decided.reason


def test_force_spends_without_asking():
    decided = nightly.plan(store(), now=NOW, force=True)
    assert decided.verdict == "generate"
    assert "--force" in decided.reason


def test_a_board_scheduled_for_next_week_does_not_block_tomorrow():
    """Only tomorrow can collide, because tomorrow is the only day this job writes.

    Read as "is anything dated ahead", one board hand-scheduled a week out would stop the
    generator for a week and leave every day in between on the same board.
    """
    later = store(played=[NOW - timedelta(hours=1)])
    later.boards.append(Published(puzzle=board("next-week"), live_on=shift(TODAY, 7)))
    decided = nightly.plan(later, now=NOW)
    assert decided.verdict == "generate"
    assert decided.live_on == TOMORROW


def test_force_still_will_not_write_a_second_board_for_one_day():
    """`--force` overrides the demand gate, not the calendar. Two boards on one date is
    a bug the game has no way to resolve."""
    done = store()
    done.boards.append(Published(puzzle=board("tomorrow"), live_on=TOMORROW))
    assert nightly.plan(done, now=NOW, force=True).verdict == "scheduled"


# --- the night ------------------------------------------------------------------------


async def tonight(store_: MemoryStore, llm: ScriptedLLM | None = None, **kwargs) -> nightly.Night:
    return await nightly.tonight(
        llm or ScriptedLLM(),
        CONFIG,
        store_,
        count=3,
        seed=7,
        now=NOW,
        source=MemoryCategorySource(["Stone fruit", "Chess tactics", "Bed linen"]),
        **kwargs,
    )


async def test_a_gated_night_calls_no_model_at_all():
    """Not a cheap night — a free one. The gate has to come before the first token, not
    before the last."""
    llm = ScriptedLLM()
    night = await tonight(store(), llm=llm)
    assert night.plan.verdict == "idle"
    assert llm.ledger.calls == []
    assert night.published is None


async def test_an_accepted_board_goes_up_for_tomorrow():
    game = store(played=[NOW - timedelta(hours=2)])
    night = await tonight(game)

    assert night.published is not None
    assert night.published.live_on == TOMORROW
    assert [b.live_on for b in game.schedule()] == [TODAY, TOMORROW]
    assert game.schedule()[-1].puzzle.id == night.published.puzzle.id


async def test_the_board_that_goes_up_has_its_rows_explained():
    """The gloss stage runs after the accept and before the publish, so a board reaches a
    player with the notes already on it — there is no second pass, and nothing to fetch
    while somebody is playing."""
    game = store(played=[NOW - timedelta(hours=2)])
    night = await tonight(game)

    assert night.published is not None
    published = game.schedule()[-1].puzzle
    for g in published.groups:
        assert g.notes is not None, f"{g.id} went up with nothing under it"
        assert [w.word for w in g.notes.words] == g.words


async def test_a_board_whose_notes_fail_still_goes_up():
    """A day with a puzzle and no notes beats a day with no puzzle. The board is already
    paid for and already judged; the prose is the one part of it that is optional."""

    class NoNotes(ScriptedLLM):
        async def generate(self, **kwargs):
            if kwargs["stage"] == "gloss":
                raise RuntimeError("no")
            return await super().generate(**kwargs)

    game = store(played=[NOW - timedelta(hours=2)])
    night = await tonight(game, llm=NoNotes())

    assert night.published is not None
    assert all(g.notes is None for g in game.schedule()[-1].puzzle.groups)


async def test_a_night_that_accepts_nothing_publishes_nothing():
    """The board that is up stays up. A day repeated is a smaller failure than a day
    missing, and a retry would only spend the same money on the same bad idea."""
    rejects = Grade(verdict="reject", fairness=2, elegance=1, reasons="scripted")
    game = store(played=[NOW - timedelta(hours=2)])
    night = await tonight(game, llm=ScriptedLLM(grade=rejects))

    assert night.run is not None
    assert night.published is None
    assert [b.live_on for b in game.schedule()] == [TODAY]


async def test_a_dry_run_generates_and_publishes_nothing():
    game = store(played=[NOW - timedelta(hours=2)])
    night = await tonight(game, dry_run=True)
    assert night.run is not None and night.run.by_verdict("accept")
    assert night.published is None
    assert len(game.schedule()) == 1


async def test_tonights_board_is_deduped_against_every_board_ever_published():
    """Including the archive, and including one dated ahead.

    The corpus is the database rather than a window of it, because a board a player met
    last spring is still a board they have met, and a repeat is most obvious when the two
    are closest together.
    """
    game = MemoryStore(
        boards=[
            Published(puzzle=board("ancient", BOARDS[0]), live_on=shift(TODAY, -300)),
            Published(puzzle=board("today", BOARDS[1]), live_on=TODAY),
        ],
        runs=[("today", ms(NOW - timedelta(hours=1)))],
    )
    corpus = corpus_of(game.schedule())
    assert "HAMMER" in corpus.words, "a board from 300 days ago left the corpus"
    assert "KETCH" in corpus.words

    # The scripted proposer hands back BOARDS[0] first, which the archive already holds.
    night = await tonight(game)
    first = night.run.candidates[0] if night.run else None
    assert first is not None
    assert "stale-words" in [p.code for p in first.problems], first.warnings


# --- variety --------------------------------------------------------------------------


def test_a_week_of_nights_gets_a_week_of_shapes():
    """Boards stopped coming twenty at a time, so the device list stopped being walked.

    A batch of twenty took the whole shuffled list. A night that proposes one or two takes
    only its front, and a fresh shuffle each night landed on about four distinct shapes a
    week — sometimes one, when the seed did not move. Walking the cycle from the date's
    ordinal gives all seven, in some order, every week.
    """
    pool = [Category(label=x) for x in ("Stone fruit", "Chess tactics", "Bed linen")]
    week = [
        draw(pool, 1, rng=random.Random(0), cooldown=60, day=shift(TODAY, i))[0][0].device
        for i in range(7)
    ]
    assert len(set(week)) == len(DEVICES)


def test_two_boards_in_one_night_are_not_the_same_shape_either():
    slots, _ = draw(
        [Category(label="Stone fruit")], 2, rng=random.Random(0), cooldown=60, day=TODAY
    )
    assert slots[0].device != slots[1].device


def test_a_night_re_run_reproduces_itself():
    """Seeded on the day the board is for, so retrying tonight is tonight again."""
    assert nightly.seed_for(TOMORROW) == nightly.seed_for(TOMORROW)
    assert nightly.seed_for(TOMORROW) != nightly.seed_for(shift(TOMORROW, 1))


# --- two languages, one schedule --------------------------------------------------------


def test_one_language_does_not_cover_the_other_s_tomorrow():
    """The bug this would have been.

    Both languages publish on the same days, so a gate reading the whole schedule sees a
    Swedish board written for tomorrow and calls tomorrow covered — and English never
    generates again. Neither language is ever mentioned in the other's reason.
    """
    both = store(played=[NOW - timedelta(hours=1)])
    both.boards.append(Published(puzzle=board("i-morgon", language="sv"), live_on=TOMORROW))

    assert nightly.plan(both, language="sv", now=NOW).verdict == "scheduled"
    assert nightly.plan(both, language="en", now=NOW).verdict == "generate"


def test_demand_is_measured_on_the_board_of_the_language_being_written():
    """Nobody playing the Swedish board is not evidence that nobody is playing."""
    mixed = MemoryStore(
        boards=[
            Published(puzzle=board("today"), live_on=TODAY),
            Published(puzzle=board("idag", language="sv"), live_on=TODAY),
        ],
        runs=[("today", ms(NOW - timedelta(hours=1)))],
    )

    assert nightly.plan(mixed, language="en", now=NOW).verdict == "generate"
    idle = nightly.plan(mixed, language="sv", now=NOW)
    assert idle.verdict == "idle"
    assert "idag" in idle.reason


def test_a_language_with_nothing_published_is_always_allowed_to_start():
    """English is live and Swedish has never shipped. The Swedish gate has no board to
    measure demand on, so refusing would mean it could never open."""
    only_english = MemoryStore(boards=[Published(puzzle=board("today"), live_on=TODAY)], runs=[])
    decided = nightly.plan(only_english, language="sv", now=NOW)
    assert decided.verdict == "generate"
    assert "nothing to wait for" in decided.reason
