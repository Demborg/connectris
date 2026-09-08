"""Print every board an arm produced, with its slot, verdict and stated traps."""

from __future__ import annotations

import sys

from analyse_arms import ARMS, latest

from connectris_pipeline.pipeline import reload


def main() -> None:
    wanted = sys.argv[1:] or ARMS
    for arm in wanted:
        print("=" * 78)
        print(arm)
        print("=" * 78)
        for c in reload(latest(arm)):
            verdict = c.decision.verdict if c.decision else "?"
            recovery = f"{c.stats.mean_recovery:.0%}" if c.stats else "-"
            print(f"\n{c.id}  [{verdict}]  recovery {recovery}  — {c.puzzle.name}")
            print(f"  slot: {c.slot.get('theme', '')!r} / {c.slot.get('device', '')[:60]}")
            for g in c.puzzle.groups:
                print(f"    {g.label[:38]:40} {' '.join(g.words)}")
                print(f"      concept: {g.concept}")
                print(f"      trap:    {c.traps.get(g.id, '')[:150]}")
            for p in c.problems:
                print(f"    ! {p}")
            if c.grade:
                g = c.grade
                print(f"    grade: fair {g.fairness} eleg {g.elegance} — {g.reasons}")
        print()


if __name__ == "__main__":
    main()
