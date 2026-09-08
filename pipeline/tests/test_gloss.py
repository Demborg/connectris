"""The notes under a solved row, and the pairing that has to be right.

A note is shipped prose stating a fact about a word, so the failure that matters here is
not a missing note — it is a note filed under the wrong word, which a player reads as
fact about that word. Everything below is about the pairing: it is done by name, it is
all-or-nothing, and a reply that does not describe the board is thrown away whole.
"""

from __future__ import annotations

import json

from conftest import CONFIG, ScriptedLLM

from connectris_pipeline import backfill as backfill_module
from connectris_pipeline.language import of as language_of
from connectris_pipeline.prompts import gloss as gloss_prompt
from connectris_pipeline.schema import GlossedCategory, GlossedWord, PuzzleGloss
from connectris_pipeline.spec import Group, Notes, Puzzle, WordNote, validate
from connectris_pipeline.stages import gloss
from connectris_pipeline.stages.gloss import GlossError, attach

ROWS = [
    ("Hound dog breeds", ["BASSET", "BEAGLE", "BLOODHOUND", "GREYHOUND"]),
    ("Living amphibians", ["FROG", "NEWT", "SALAMANDER", "TOAD"]),
    ("___ CLIP", ["ALLIGATOR", "BINDER", "BULLDOG", "PAPER"]),
    ("Adjectives meaning 'principal'", ["CHIEF", "MAIN", "MAJOR", "PRIME"]),
    ("Undergraduate class years", ["FRESHMAN", "JUNIOR", "SENIOR", "SOPHOMORE"]),
]


def board(pid: str = "gen-01") -> Puzzle:
    return Puzzle(
        id=pid,
        name="Natural Order",
        groups=[Group(id=label.lower(), label=label, words=list(ws)) for label, ws in ROWS],
    )


def reply(rows: list[tuple[str, list[str]]] | None = None) -> PuzzleGloss:
    """A well-formed reply for `board()`, or for whatever rows are handed in."""
    return PuzzleGloss(
        categories=[
            GlossedCategory(
                label=label,
                summary=f"What {label} is.",
                words=[GlossedWord(word=w, note=f"About {w}.") for w in words],
            )
            for label, words in (rows if rows is not None else ROWS)
        ]
    )


def notes_of(puzzle: Puzzle) -> dict[str, list[str]]:
    """Group id -> the words its notes are about, in order."""
    return {g.id: [w.note for w in g.notes.words] for g in puzzle.groups if g.notes is not None}


# --- pairing --------------------------------------------------------------------------


def test_every_word_gets_the_note_that_names_it():
    explained = attach(board(), reply())
    for g in explained.groups:
        assert g.notes is not None
        assert [w.word for w in g.notes.words] == g.words
        assert [w.note for w in g.notes.words] == [f"About {w}." for w in g.words]


def test_a_reply_in_another_order_still_lands_on_the_right_rows():
    """The reason the pairing is by name rather than by position.

    A model that answers the five categories in an order of its own is a formatting habit,
    not a defect — but paired positionally it would file the amphibians under the hounds,
    and the player would read that the SALAMANDER is a breed of dog.
    """
    shuffled = reply(list(reversed(ROWS)))
    explained = attach(board(), shuffled)
    assert notes_of(explained)["living amphibians"] == [
        "About FROG.",
        "About NEWT.",
        "About SALAMANDER.",
        "About TOAD.",
    ]


def test_a_word_in_another_order_still_lands_on_the_right_word():
    rows = [(label, list(reversed(ws))) for label, ws in ROWS]
    explained = attach(board(), reply(rows))
    for g in explained.groups:
        assert g.notes is not None
        assert [w.word for w in g.notes.words] == g.words


def test_a_label_echoed_back_loosely_still_matches():
    """Same fold the dedupe index uses, so punctuation and case are not a failure."""
    rows = [(label.upper().replace("'", ""), ws) for label, ws in ROWS]
    explained = attach(board(), reply(rows))
    assert len(notes_of(explained)) == len(ROWS)


def test_labels_rewritten_past_recognition_fall_back_to_the_order_they_were_given():
    rows = [(f"Category {i}", ws) for i, (_, ws) in enumerate(ROWS)]
    explained = attach(board(), reply(rows))
    assert notes_of(explained)["hound dog breeds"][0] == "About BASSET."


def test_a_reply_that_is_neither_this_board_nor_the_right_length_is_refused():
    rows = [(f"Category {i}", ws) for i, (_, ws) in enumerate(ROWS[:3])]
    try:
        attach(board(), reply(rows))
    except GlossError as exc:
        assert "not this board" in str(exc)
    else:
        raise AssertionError("a reply about three rows explained a board of five")


# --- all or nothing -------------------------------------------------------------------


def test_a_row_with_a_word_left_out_takes_the_whole_board_with_it():
    """Five bars where four open reads as one that is broken.

    And the alternative is worse than a board with no notes at all: filling the gap from
    the words it did get is how a note ends up under its neighbour.
    """
    rows = [(ROWS[0][0], ROWS[0][1][:3]), *ROWS[1:]]
    try:
        attach(board(), reply(rows))
    except GlossError as exc:
        assert "GREYHOUND" in str(exc)
    else:
        raise AssertionError("a row of four shipped three notes")


def test_a_note_about_a_word_that_is_not_on_the_row_is_refused():
    rows = [(ROWS[0][0], ["BASSET", "BEAGLE", "BLOODHOUND", "WHIPPET"]), *ROWS[1:]]
    try:
        attach(board(), reply(rows))
    except GlossError:
        pass
    else:
        raise AssertionError("a note about WHIPPET was written under a row without one")


def test_an_empty_note_is_no_note():
    """A blank line is a row that opens onto nothing, which is the same defect."""
    out = reply()
    out.categories[0].words[0].note = "   "
    try:
        attach(board(), out)
    except GlossError:
        pass
    else:
        raise AssertionError("an empty note counted as a note")


def test_an_empty_summary_is_refused_too():
    out = reply()
    out.categories[2].summary = ""
    try:
        attach(board(), out)
    except GlossError:
        pass
    else:
        raise AssertionError("a category with no summary was explained")


def test_the_board_itself_is_untouched():
    """Notes are the only thing this stage may add. Words are the game."""
    original = board()
    explained = attach(original, reply())
    assert explained.to_game_json()["name"] == original.to_game_json()["name"]
    assert [g.words for g in explained.groups] == [g.words for g in original.groups]
    assert all(g.notes is None for g in original.groups), "attach mutated its input"


# --- the stage ------------------------------------------------------------------------


async def test_the_stage_asks_once_and_comes_back_with_a_whole_board():
    llm = ScriptedLLM()
    explained = await gloss(llm, CONFIG, board())

    assert [c.stage for c in llm.ledger.calls] == ["gloss"]
    assert len(notes_of(explained)) == len(ROWS)
    assert explained.groups[0].notes is not None
    assert explained.groups[0].notes.summary == "What Hound dog breeds is."


async def test_the_shipped_shape_survives_a_round_trip():
    explained = await gloss(ScriptedLLM(), CONFIG, board())
    back = Puzzle.from_game_json(explained.to_game_json())
    assert notes_of(back) == notes_of(explained)
    assert [x.severity for x in validate(back)] == []


def test_a_board_without_notes_round_trips_without_growing_a_field():
    """`puzzles.json` predates notes, and reading it must not rewrite it."""
    raw = board().to_game_json()
    assert "notes" not in raw["groups"][0]


# --- what validate says ---------------------------------------------------------------


def explained_board() -> Puzzle:
    p = board()
    for g in p.groups:
        g.notes = Notes(
            summary=f"What {g.label} is.",
            words=[WordNote(word=w, note=f"About {w}.") for w in g.words],
        )
    return p


def test_notes_that_do_not_cover_a_row_are_a_warning_on_the_shipped_file():
    """`attach` is what refuses these; this is the guard on the file itself.

    `cli check` reads it over `puzzles.json`, which is the one place a hand edit or a
    half-finished backfill could leave a note under the wrong word.
    """
    p = explained_board()
    assert p.groups[0].notes is not None
    p.groups[0].notes.words[0].word = "WHIPPET"
    codes = {x.code: x.severity for x in validate(p)}
    assert codes.get("notes-mismatch") == "warn"


def test_a_part_explained_board_is_a_warning():
    p = explained_board()
    p.groups[3].notes = None
    codes = {x.code: x.severity for x in validate(p)}
    assert codes.get("part-explained") == "warn"


def test_a_board_with_no_notes_at_all_is_not_a_warning():
    assert "part-explained" not in {x.code for x in validate(board())}


# --- writing it back to puzzles.json --------------------------------------------------


def test_the_file_is_edited_in_place_rather_than_appended_to(tmp_path):
    """`rewrite` is `append`'s counterpart, and the distinction is the whole reason it
    exists: adding notes is an edit to a board, and an append would leave two of it."""
    from connectris_pipeline.corpus import load, rewrite

    target = tmp_path / "puzzles.json"
    boards = [board("gen-01"), board("gen-02")]
    target.write_text(json.dumps([p.to_game_json() for p in boards], indent="\t"))

    explained = attach(board("gen-02"), reply())
    assert rewrite([explained], target) == 1

    reloaded, _ = load(target)
    assert [p.id for p in reloaded] == ["gen-01", "gen-02"], "order and count are unchanged"
    assert all(g.notes is None for g in reloaded[0].groups)
    assert notes_of(reloaded[1]) == notes_of(explained)


def test_a_board_the_file_has_never_heard_of_is_not_published_by_the_back_door(tmp_path):
    from connectris_pipeline.corpus import load, rewrite

    target = tmp_path / "puzzles.json"
    target.write_text(json.dumps([board("gen-01").to_game_json()], indent="\t"))

    assert rewrite([attach(board("gen-99"), reply())], target) == 0
    reloaded, _ = load(target)
    assert [p.id for p in reloaded] == ["gen-01"]


# --- the backfill ---------------------------------------------------------------------


async def test_a_backfill_explains_the_boards_that_have_none():
    boards = [board("gen-01"), board("gen-02")]
    written: list[Puzzle] = []
    done = await backfill_module.backfill(ScriptedLLM(), CONFIG, boards, written.append)

    assert done.glossed == ["gen-01", "gen-02"]
    assert done.failed == {}
    assert [len(notes_of(p)) for p in written] == [len(ROWS), len(ROWS)]


async def test_a_backfill_does_not_pay_twice_for_a_board_it_already_explained():
    """The command is run by hand and will be run again. Re-glossing every board each
    time is a bill for prose that is already written."""
    llm = ScriptedLLM()
    written: list[Puzzle] = []
    done = await backfill_module.backfill(llm, CONFIG, [explained_board()], written.append)

    assert done.skipped == ["gen-01"]
    assert llm.ledger.calls == []
    assert written == []


async def test_force_explains_a_board_that_already_has_notes():
    llm = ScriptedLLM()
    written: list[Puzzle] = []
    done = await backfill_module.backfill(
        llm, CONFIG, [explained_board()], written.append, force=True
    )
    assert done.glossed == ["gen-01"]
    assert len(llm.ledger.calls) == 1


async def test_a_limit_stops_it_spending_more_than_it_was_asked_to():
    boards = [board(f"gen-{i:02d}") for i in range(5)]
    llm = ScriptedLLM()
    written: list[Puzzle] = []
    done = await backfill_module.backfill(llm, CONFIG, boards, written.append, limit=2)

    assert len(done.glossed) == 2
    assert len(llm.ledger.calls) == 2
    assert len(done.skipped) == 3


async def test_one_board_that_cannot_be_explained_does_not_stop_the_rest():
    """These boards are already published and playable. A failure here costs one row of
    prose, and must not cost the backfill."""

    class Broken(ScriptedLLM):
        async def generate(self, **kwargs):
            if kwargs["stage"] == "gloss" and self._proposed == 0:
                self._proposed = 1
                raise RuntimeError("no")
            return await super().generate(**kwargs)

    written: list[Puzzle] = []
    done = await backfill_module.backfill(
        Broken(), CONFIG, [board("gen-01"), board("gen-02")], written.append
    )

    assert done.glossed == ["gen-02"]
    assert "RuntimeError: no" in done.failed["gen-01"]
    assert [p.id for p in written] == ["gen-02"]


async def test_each_board_is_written_as_it_lands():
    """A backfill over a year of boards is minutes of model calls, and one that is killed
    part-way has to keep what it paid for."""
    seen: list[int] = []
    boards = [board(f"gen-{i:02d}") for i in range(3)]

    def write(_: Puzzle) -> None:
        seen.append(len(seen))

    await backfill_module.backfill(ScriptedLLM(), CONFIG, boards, write)
    assert seen == [0, 1, 2]


def test_glossing_a_board_keeps_the_fields_it_does_not_touch():
    """`attach` rebuilds every board that ships, so anything it forgets is gone for good.

    `concept` was forgotten exactly once, and the damage was quiet: boards published fine,
    and the cross-language index they were supposed to fill stayed empty for ever.
    """
    p = board()
    p.language = "sv"
    for g in p.groups:
        g.concept = f"idea of {g.id}"

    out = attach(p, reply())

    assert out.language == "sv"
    assert [g.concept for g in out.groups] == [f"idea of {g.id}" for g in p.groups]
    assert all(g.notes is not None for g in out.groups)


def test_a_swedish_board_is_glossed_in_swedish():
    """The only stage a player reads, and the only one where the language is not a detail.

    Nothing downstream reads a note, so English prose under a Swedish row would have
    shipped without a single check objecting.
    """
    sv = board()
    sv.language = "sv"
    system, _ = gloss_prompt(sv, language_of(sv.language))
    assert "write every summary and every word note in Swedish" in system

    system, _ = gloss_prompt(board(), language_of("en"))
    assert "Swedish" not in system

    # A board tagged with a language the generator has never heard of still gets glossed.
    odd = board()
    odd.language = "no"
    assert gloss_prompt(odd, language_of(odd.language))[0] == system


# --- the concept backfill ----------------------------------------------------------------


def test_a_published_board_is_given_the_concept_the_index_compares_on():
    """Free, and the thing that makes the cross-language index work at all.

    Without it the index is present and inert: boards that shipped before the field
    existed carry no concept, so a Swedish batch is told nothing has shipped and
    re-invents the English catalogue in translation. It did exactly that, banking
    *Bleckblåsinstrument* against a live board called "Orchestral brass instruments".
    """
    written: list[Puzzle] = []
    known = {"Hound dog breeds": "hound dog breeds"}
    done = backfill_module.name_concepts([board()], written.append, known)

    assert done.named == ["gen-01"]
    named = {g.label: g.concept for g in written[0].groups}
    # The hand-written concept wins where there is one; the label is the concept otherwise,
    # because an English label already is an English noun phrase.
    assert named["Hound dog breeds"] == "hound dog breeds"
    assert named["___ CLIP"] == "___ clip"
    assert named["Living amphibians"] == "living amphibians"


def test_a_board_that_already_has_concepts_is_left_alone():
    already = board()
    for g in already.groups:
        g.concept = "kept"
    written: list[Puzzle] = []
    done = backfill_module.name_concepts([already], written.append, {})
    assert done.skipped == ["gen-01"] and written == []


def test_a_swedish_board_is_skipped_rather_than_guessed_at():
    """Its label is not English and nothing here could make it so. Boards written from now
    on carry a concept from the proposer; the few that predate that want a person."""
    swedish = board()
    swedish.language = "sv"
    written: list[Puzzle] = []
    done = backfill_module.name_concepts([swedish], written.append, {})
    assert done.skipped == ["gen-01"] and written == []
