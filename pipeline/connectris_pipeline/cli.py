"""Command line.

    connectris-pipeline run --count 8
    connectris-pipeline regrade runs/20260903-101500 --config strict.toml
    connectris-pipeline export runs/20260903-101500
    connectris-pipeline check

`run` is the nightly job. `regrade` re-decides a finished run under different thresholds
without spending anything, which is how the numbers in config.py get tuned. `export`
appends accepted boards into the game's puzzles.json.

Typer rather than argparse: the options are already typed and the annotations carry the
help text, so there is no second copy of the signature to keep in sync. It is Click
underneath, so the behaviour is the boring, well-understood one.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Annotated

import typer

from . import config as config_module
from . import corpus as corpus_module
from . import pipeline
from .llm import GeminiLLM, Ledger
from .spec import validate

DEFAULT_RUNS = Path(__file__).resolve().parents[1] / "runs"

app = typer.Typer(
    help="Offline puzzle generation for Connectris.",
    no_args_is_help=True,
    add_completion=False,
)

RunDir = Annotated[Path, typer.Argument(help="A run directory under runs/.", exists=True)]
ConfigFile = Annotated[
    Path | None,
    typer.Option("--config", help="TOML overlay on the defaults.", exists=True, dir_okay=False),
]


@app.callback()
def main_options(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Log every stage.")] = False,
) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )


@app.command()
def run(
    count: Annotated[int, typer.Option(help="How many boards to propose.", min=1)] = 4,
    config: ConfigFile = None,
    out: Annotated[Path, typer.Option(help="Where to write the run directory.")] = DEFAULT_RUNS,
    seed: Annotated[int, typer.Option(help="Makes a run reproducible.")] = 0,
) -> None:
    """Generate, solve, red-team and grade a batch."""
    cfg = config_module.load(config)
    llm = GeminiLLM(
        ledger=Ledger(),
        max_retries=cfg.max_retries,
        concurrency=cfg.concurrency,
    )
    typer.secho(f"provider: {llm.backend}", err=True, fg=typer.colors.BRIGHT_BLACK)

    result = asyncio.run(pipeline.run(llm, cfg, count=count, seed=seed, out_dir=out))
    typer.echo(result.summary())
    if result.directory:
        typer.echo(f"\nwritten to {result.directory}")


@app.command()
def regrade(run: RunDir, config: ConfigFile = None) -> None:
    """Re-decide a finished run under new thresholds. Costs nothing."""
    cfg = config_module.load(config)
    result = pipeline.regrade(run, cfg)
    pipeline.write(result, cfg, run)
    typer.echo(result.summary())


@app.command()
def export(
    run: RunDir,
    include_review: Annotated[
        bool, typer.Option("--include-review", help="Also export the review queue.")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Print what would be appended, write nothing.")
    ] = False,
) -> None:
    """Append accepted puzzles to the game's puzzles.json."""
    candidates = pipeline.reload(run)
    wanted = {"accept"} | ({"review"} if include_review else set())
    chosen = [c for c in candidates if c.decision and c.decision.verdict in wanted]

    _, corpus = corpus_module.load()
    blocked = [
        (c, fatal)
        for c in chosen
        if (fatal := [p for p in validate(c.puzzle, corpus) if p.severity == "fatal"])
    ]
    if blocked:
        # Should be unreachable: nothing fatal gets past `decide`. If it fires, the
        # pipeline's rules have drifted from the game's and that is the bug to fix.
        for c, fatal in blocked:
            typer.secho(
                f"refusing {c.id}: {'; '.join(str(p) for p in fatal)}",
                err=True,
                fg=typer.colors.RED,
            )
        raise typer.Exit(1)

    if dry_run:
        typer.echo(json.dumps([c.puzzle.to_game_json() for c in chosen], indent="\t"))
        return

    added = corpus_module.append([c.puzzle for c in chosen])
    typer.echo(f"appended {added} puzzle(s) to {corpus_module.PUZZLES_JSON}")
    typer.secho("now run `pnpm format && pnpm test` in the repo root", err=True)


@app.command()
def check() -> None:
    """Run the pipeline's own rules over the shipped puzzles.

    A guard against drift: these rules exist to keep generated puzzles out of a red CI,
    which only works if they still agree with `engine.spec.ts`.
    """
    puzzles, corpus = corpus_module.load()
    bad = 0
    for p in puzzles:
        # Each shipped puzzle is in the corpus already, so dedupe would flag every one.
        problems = [x for x in validate(p) if x.severity == "fatal"]
        if problems:
            bad += 1
            typer.secho(f"{p.id}: {'; '.join(str(x) for x in problems)}", fg=typer.colors.RED)
    typer.echo(
        f"{len(puzzles)} shipped puzzles, {bad} would be rejected, "
        f"{len(corpus.words)} words and {len(corpus.labels)} categories in the dedupe index"
    )
    raise typer.Exit(1 if bad else 0)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
