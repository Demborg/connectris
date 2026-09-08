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
    concept_key,
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


# --- Swedish ---------------------------------------------------------------
#
# These pin the two defects that made the old rules hostile to Swedish, and they are
# separate tests because the two failed differently: the charset regex rejected Å Ä Ö
# loudly, and `normalise_word` destroyed them quietly, on both sides of the comparison at
# once, so nothing downstream could see it had happened.


def swedish(words: list[str]) -> Puzzle:
    """A Swedish board, differing from `board()` only in language and vocabulary."""
    return Puzzle(
        id="sv",
        name="Prov",
        language="sv",
        groups=[
            Group("djur", "Husdjur", words),
            Group("vader", "Dåligt väder", ["REGN", "SNÖ", "DIMMA", "HAGEL"]),
            Group("berg", "Bergarter", ["GRANIT", "SKIFFER", "KALKSTEN", "GNEJS"]),
            Group("fisk", "Fiskar", ["ABBORRE", "GÄDDA", "LAX", "SIK"]),
            Group("trad", "Träd", ["BJÖRK", "ASP", "ALM", "EK"]),
        ],
    )


def test_swedish_letters_are_letters_not_accents():
    """RÅTTA and RATTA are different words; folding one into the other is a spelling bug."""
    assert normalise_word("råtta") == "RÅTTA"
    assert normalise_word("Ögon") == "ÖGON"
    # An acute on a letter that is already there stays decoration, and still folds.
    assert normalise_word("Café") == "CAFE"


def test_swedish_board_passes_its_own_charset():
    assert not is_fatal(validate(swedish(["HUND", "KATT", "HÄST", "MARSVIN"])))


def test_swedish_letters_are_rejected_on_an_english_board():
    """The charset gate is per-language, so 'not English' is an error, not a silent repair."""
    p = swedish(["HUND", "KATT", "HÄST", "MARSVIN"])
    p.language = "en"
    assert "charset" in codes(p)


def test_the_cap_counts_swedish_letters_as_one_character_each():
    """A precomposed Å is one char. It would be two if anything here left the string NFD."""
    assert not is_fatal(validate(swedish(["HUND", "KATT", "HÄST", "SOMMARSTUGA"])))
    assert "too-long" in codes(swedish(["HUND", "KATT", "HÄST", "KAFFEBRYGGARE"]))


def test_label_key_keeps_swedish_labels_apart():
    """Stripping Å Ä Ö left a consonant skeleton behind, and skeletons collide."""
    assert label_key("Stjärnor") != label_key("Stjärnorna")
    assert label_key("Stenfrukt") == label_key("stenfrukt!")


def test_corpus_is_scoped_by_language():
    """BAND and KORT are ordinary words in both languages and must not block each other."""
    raw = [
        {"id": "a", "language": "en", "groups": [{"label": "Bands", "words": ["BAND"]}]},
        {"id": "b", "language": "sv", "groups": [{"label": "Kort", "words": ["KORT"]}]},
    ]
    assert Corpus.from_game_json(raw, "en").words == {"BAND"}
    assert Corpus.from_game_json(raw, "sv").words == {"KORT"}
    assert Corpus.from_game_json(raw).words == {"BAND", "KORT"}


def test_a_whole_duplicated_row_is_flagged():
    """The gate was `> 4` and a row is exactly four words, so one copied row slid through.

    It did, in a real run: two boards shipped FÄNRIK, LÖJTNANT, KAPTEN, MAJOR identically
    and nothing said a word about it.
    """
    shipped = Corpus(words={"HAMMER", "CHISEL", "PLANE", "WRENCH"})
    assert "stale-words" in codes(board(), shipped)
    # Three shared words is still a coincidence rather than a copy.
    assert "stale-words" not in codes(board(), Corpus(words={"HAMMER", "CHISEL", "PLANE"}))


def test_concepts_compare_across_languages_where_labels_cannot():
    """The one thing `label_key` structurally cannot do.

    'Bleckblåsinstrument' and 'Orchestral brass instruments' share not one character, so
    the lexical index rates them maximally different. They are the same board.
    """
    shipped = Corpus(concepts={concept_key("brass instruments")})
    assert label_key("Bleckblåsinstrument") not in shipped.labels
    assert shipped.matches_concept("brass instruments")
    # Containment either way: one extra word of precision is the same category.
    assert shipped.matches_concept("orchestral brass instruments")
    assert not shipped.matches_concept("woodwind instruments")


def test_the_concept_index_is_not_scoped_by_language():
    """The opposite call from `words`, and deliberately so: a word being taken in English
    says nothing about Swedish, but an *idea* being taken says everything."""
    raw = [
        {
            "id": "a",
            "language": "en",
            "groups": [{"label": "Stone fruit", "words": ["PLUM"], "concept": "stone fruit"}],
        }
    ]
    assert Corpus.from_game_json(raw, "sv").words == set()
    assert Corpus.from_game_json(raw, "sv").matches_concept("stone fruit")


def test_a_translated_category_is_warned_about_and_a_native_one_is_not():
    p = board(
        [
            Group(
                "a",
                "Bleckblåsinstrument",
                ["TRUMPET", "TROMBON", "TUBA", "KORNETT"],
                concept="brass instruments",
            ),
            Group("b", "Schackpjäser", ["BONDE", "DAM", "KUNG", "TORN"], concept="chess pieces"),
        ]
    )
    p.language = "sv"
    problems = validate(p, Corpus(concepts={concept_key("brass instruments")}))
    stale = [x.message for x in problems if x.code == "stale-concept"]
    assert len(stale) == 1
    assert "Bleckblåsinstrument" in stale[0]
