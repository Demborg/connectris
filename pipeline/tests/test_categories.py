"""The category pool: novelty decided before generation rather than filtered after it."""

from __future__ import annotations

import random

from conftest import MemoryCategorySource

from connectris_pipeline.categories import Category, CategorySource, JsonCategorySource

#: Distinct as `label_key` sees them, which folds case, punctuation and digits — so
#: "Theme 1" and "Theme 2" are the *same* key, and a fixture has to mean it.
THEMES = [
    "Stone fruit",
    "Chess tactics",
    "Bed linen",
    "Circus performers",
    "Court filings",
    "Knots",
    "Birds that cannot fly",
    "Espresso drinks",
    "Sailing boats",
    "Typography",
]


def test_both_adapters_satisfy_the_port() -> None:
    """A port with one adapter is a class wearing a hat; this is what makes it a port."""
    memory: CategorySource = MemoryCategorySource()
    assert memory.known() == []

    def _json_is_a_source(source: JsonCategorySource) -> CategorySource:
        return source


def test_banking_skips_what_the_pool_already_has(tmp_path):
    source = JsonCategorySource(tmp_path / "pool.json")
    assert source.bank([Category("Stone fruit"), Category("Chess tactics")]) == 2
    assert source.bank([Category("Chess tactics"), Category("Bed linen")]) == 1
    assert sorted(c.label for c in source.known()) == ["Bed linen", "Chess tactics", "Stone fruit"]


def test_banking_folds_labels_the_way_dedupe_does(tmp_path):
    """'___ BOARD' and 'board ___' are the same idea, and label_key already knows it."""
    source = JsonCategorySource(tmp_path / "pool.json")
    assert source.bank([Category("___ BOARD")]) == 1
    assert source.bank([Category("board ___")]) == 0


def test_a_pool_survives_a_round_trip_to_disk(tmp_path):
    path = tmp_path / "pool.json"
    JsonCategorySource(path).bank([Category("Stone fruit", reads_as="reads as fruit")])
    (again,) = JsonCategorySource(path).known()
    assert again.label == "Stone fruit"
    assert again.reads_as == "reads as fruit"


def test_every_board_in_a_batch_gets_a_different_theme(tmp_path):
    """The waste this replaced: two boards inventing the same category independently."""
    source = JsonCategorySource(tmp_path / "pool.json")
    source.bank([Category(x) for x in THEMES])

    slots = source.allocate(6, rng=random.Random(1))
    themes = [s.theme for s in slots]
    assert len(set(themes)) == len(themes)


def test_devices_cycle_rather_than_being_sampled(tmp_path):
    """Sampling with replacement is what gave one batch the same domain three times."""
    source = JsonCategorySource(tmp_path / "pool.json")
    source.bank([Category(x) for x in THEMES])

    devices = [s.device for s in source.allocate(7, rng=random.Random(2))]
    assert len(set(devices)) == 7


def test_allocation_records_use_so_a_theme_is_not_offered_twice_running(tmp_path):
    path = tmp_path / "pool.json"
    source = JsonCategorySource(path)
    source.bank([Category(x) for x in THEMES[:4]])

    first = {s.theme for s in source.allocate(2, rng=random.Random(3))}
    used = {c.label for c in JsonCategorySource(path).known() if c.used}
    assert used == first


def test_an_empty_pool_still_allocates_a_device(tmp_path):
    """A board with only a device assigned is less constrained, not invalid."""
    slots = JsonCategorySource(tmp_path / "pool.json").allocate(3, rng=random.Random(4))
    assert len(slots) == 3
    assert all(s.device for s in slots)
    assert all(s.theme == "" for s in slots)


def test_labels_differing_only_in_digits_are_the_same_idea(tmp_path):
    """`label_key` folds digits, so 'Top 10 films' and 'Top 40 films' collide.

    Surprising enough to pin: it is the behaviour that makes the pool refuse near-misses
    rather than only exact repeats, and it caught a lazy fixture in this very file.
    """
    source = JsonCategorySource(tmp_path / "pool.json")
    assert source.bank([Category("Top 10 films")]) == 1
    assert source.bank([Category("Top 40 films")]) == 0
