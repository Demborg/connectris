"""The deterministic rules, and that they still agree with the game's own tests."""

from __future__ import annotations

import pytest

from connectris_pipeline.corpus import load
from connectris_pipeline.spec import (
    COLS,
    ROWS,
    Corpus,
    Group,
    Puzzle,
    is_fatal,
    label_key,
    normalise_word,
    slugify,
    validate,
)


def board(groups: list[Group] | None = None) -> Puzzle:
    default = [
        Group("tools", "Hand tools", ["HAMMER", "CHISEL", "PLANE", "WRENCH"]),
        Group("weather", "Bad weather", ["FROST", "GALE", "HAZE", "SLEET"]),
        Group("rocks", "Rocks", ["SHALE", "BASALT", "CHALK", "SLATE"]),
        Group("fish", "Fish", ["PERCH", "SOLE", "BASS", "SKATE"]),
        Group("trees", "Trees", ["BIRCH", "ALDER", "ROWAN", "ASPEN"]),
    ]
    return Puzzle(id="t", name="Test", groups=default if groups is None else groups)


def codes(puzzle: Puzzle, corpus: Corpus | None = None) -> set[str]:
    return {p.code for p in validate(puzzle, corpus)}


def test_a_clean_board_has_nothing_to_say():
    assert validate(board()) == []


def test_shipped_puzzles_pass_the_pipeline_rules():
    """If this fails, the pipeline would emit puzzles the vitest suite rejects."""
    puzzles, _ = load()
    assert puzzles, "no shipped puzzles found"
    for p in puzzles:
        fatal = [x for x in validate(p) if x.severity == "fatal"]
        assert fatal == [], f"{p.id}: {fatal}"


def test_repeated_word_is_fatal():
    p = board()
    p.groups[1].words[0] = "HAMMER"
    assert "duplicate-word" in codes(p)
    assert is_fatal(validate(p))


def test_word_over_twelve_characters_is_fatal():
    p = board()
    p.groups[0].words[0] = "SLEDGEHAMMERS"
    assert "too-long" in codes(p)


def test_wrong_shape_is_fatal():
    p = board()
    p.groups[0].words.append("SPANNER")
    assert "col-count" in codes(p)
    p = board(groups=board().groups[:4])
    assert "row-count" in codes(p)
    assert len(board().groups) == ROWS
    assert len(board().groups[0].words) == COLS


def test_a_word_written_into_a_label_is_a_warning_not_a_kill():
    p = board()
    p.groups[2].label = "Rocks and slate"
    problems = validate(p)
    assert [x.code for x in problems] == ["label-gives-it-away"]
    assert not is_fatal(problems)


def test_a_word_in_a_different_rows_label_is_flagged_too():
    p = board()
    p.groups[0].label = "Things on a plane"
    assert "label-gives-it-away" in codes(p)


def test_dedupe_flags_shipped_words_and_categories():
    p = board()
    corpus = Corpus(words={"HAMMER", "CHISEL", "PLANE", "WRENCH", "FROST"}, labels={"fish"})
    found = codes(p, corpus)
    assert "stale-words" in found
    assert "stale-category" in found


def test_label_keys_ignore_ordering_and_punctuation():
    p = board()
    p.groups[0].label = "board ___"
    assert "stale-category" in codes(p, Corpus(labels={label_key("___ BOARD")}))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("  latte ", "LATTE"), ("Café", "CAFE"), ("big  top", "BIG TOP")],
)
def test_normalise_word(raw, expected):
    assert normalise_word(raw) == expected


def test_slugify():
    assert slugify("___ STONE") == "stone"
    assert slugify("Under the big top") == "under-the-big-top"
