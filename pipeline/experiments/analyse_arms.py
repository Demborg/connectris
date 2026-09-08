"""Read the four arms back and put the numbers that decide the question side by side.

Everything here is computed from the artifacts, not from a model. The one measure that
matters most — whether a category is an English one in translation — is checked two ways:
mechanically, against the shipped concept index, and by listing every concept so a human
can see the ones the machine cannot.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from connectris_pipeline import corpus as corpus_module
from connectris_pipeline.pipeline import reload
from connectris_pipeline.spec import normalise_word

ARMS = ["en-seed_en-prompt", "sv-seed_en-prompt", "en-seed_sv-prompt", "sv-seed_sv-prompt"]
OUT = Path(__file__).resolve().parent.parent / "runs" / "arms"


def latest(arm: str) -> Path:
    dirs = sorted(
        d for d in (OUT / arm).iterdir() if d.is_dir() and (d / "candidates.jsonl").exists()
    )
    return dirs[-1]


def load(arm: str) -> list:
    return reload(latest(arm))


def stats(arm: str) -> dict:
    cands = load(arm)
    shipped = corpus_module.load()[1]
    words = [normalise_word(w) for c in cands for w in c.puzzle.words]
    groups = [g for c in cands for g in c.puzzle.groups]
    lens = [len(w) for w in words]

    graded = [c for c in cands if c.grade]
    solved = [c for c in cands if c.stats]
    legib = [c.stats.mean_legibility for c in solved if c.stats.mean_legibility is not None]

    codes: dict[str, int] = {}
    for c in cands:
        for p in c.problems:
            codes[p.code] = codes.get(p.code, 0) + 1

    return {
        "arm": arm,
        "boards": len(cands),
        "errors": sum(1 for c in cands if c.error),
        "verdicts": {
            v: sum(1 for c in cands if c.decision and c.decision.verdict == v)
            for v in ("accept", "review", "reject")
        },
        "words": len(words),
        "mean_len": round(statistics.mean(lens), 2) if lens else 0,
        "max_len": max(lens) if lens else 0,
        "pct_over_8": round(100 * sum(1 for x in lens if x > 8) / len(lens), 1) if lens else 0,
        "pct_diacritic": round(100 * sum(1 for w in words if set(w) & set("ÅÄÖ")) / len(words), 1)
        if words
        else 0,
        # The headline measure. A category whose *concept* is already shipped in English
        # is the same board idea in a Swedish costume.
        "calqued": [g.label for g in groups if shipped.matches_concept(g.concept)],
        "open_compound_labels": [g.label for g in groups if "___ " in g.label or " ___" in g.label],
        "mean_recovery": round(statistics.mean([c.stats.mean_recovery for c in solved]), 3)
        if solved
        else None,
        "mean_legibility": round(statistics.mean(legib), 3) if legib else None,
        "fairness": round(statistics.mean([c.grade.fairness for c in graded]), 2)
        if graded
        else None,
        "elegance": round(statistics.mean([c.grade.elegance for c in graded]), 2)
        if graded
        else None,
        "problems": codes,
    }


def main() -> None:
    rows = [stats(a) for a in ARMS if (OUT / a).exists()]
    cols = ("arm", "a/r/r", "len", ">8", "ÅÄÖ", "recov", "legib", "fair", "eleg", "calq")
    widths = (20, 9, 6, 6, 6, 7, 7, 6, 6, 6)
    header = "".join(
        c.ljust(w) if i == 0 else c.rjust(w)
        for i, (c, w) in enumerate(zip(cols, widths, strict=True))
    )
    print(header)
    print("-" * len(header))
    for r in rows:
        v = r["verdicts"]
        cells = (
            r["arm"],
            f"{v['accept']}/{v['review']}/{v['reject']}",
            r["mean_len"],
            r["pct_over_8"],
            r["pct_diacritic"],
            r["mean_recovery"],
            r["mean_legibility"],
            r["fairness"],
            r["elegance"],
            len(r["calqued"]),
        )
        print(
            "".join(
                str(c).ljust(w) if i == 0 else str(c).rjust(w)
                for i, (c, w) in enumerate(zip(cells, widths, strict=True))
            )
        )
    print()
    for r in rows:
        print(f"--- {r['arm']}  problems={r['problems']}")
        if r["calqued"]:
            print(f"    calqued: {r['calqued']}")
        if r["open_compound_labels"]:
            print(f"    open-compound labels: {r['open_compound_labels']}")
    (OUT / "analysis.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
