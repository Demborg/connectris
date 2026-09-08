"""Command line.

    connectris-pipeline nightly
    connectris-pipeline run --count 8
    connectris-pipeline regrade runs/20260903-101500 --config strict.toml
    connectris-pipeline export runs/20260903-101500
    connectris-pipeline gloss --published
    connectris-pipeline check

`nightly` is the scheduled job and the only one that writes to the game: it checks whether
anyone has played, generates until a board is accepted, and publishes that board for
tomorrow. Everything it decides is in `nightly.py`; this file only turns flags into
arguments and an outcome into an exit code.

`gloss` is the one-off backfill: boards written before the gloss stage existed have no
notes under their rows, and this buys them. It is the only command besides `nightly` that
writes to the game.

`run` is the same generator with no database attached — it writes a run directory and
stops, which is what an experiment wants. `regrade` re-decides a finished run under
different thresholds without spending anything, which is how the numbers in config.py get
tuned. `export` appends accepted boards into the game's puzzles.json, which is where they
go when there is no database to publish to.

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

from . import backfill as backfill_module
from . import config as config_module
from . import corpus as corpus_module
from . import nightly as nightly_module
from . import pipeline
from .llm import GeminiLLM, Ledger
from .spec import Puzzle, validate
from .store import FirestoreCategories, FirestoreStore, connect

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


Count = Annotated[
    int,
    typer.Option(
        help="Ceiling on boards proposed. Generation stops at the first one accepted.",
        min=1,
    ),
]
Seed = Annotated[int, typer.Option(help="Makes a run reproducible.")]
NightlySeed = Annotated[
    int | None,
    typer.Option(help="Makes a night reproducible. Default: derived from the date."),
]


def _llm(cfg: config_module.Config) -> GeminiLLM:
    llm = GeminiLLM(ledger=Ledger(), max_retries=cfg.max_retries, concurrency=cfg.concurrency)
    typer.secho(f"provider: {llm.backend}", err=True, fg=typer.colors.BRIGHT_BLACK)
    return llm


@app.command()
def nightly(
    count: Count = 5,
    config: ConfigFile = None,
    out: Annotated[Path, typer.Option(help="Where to write the run directory.")] = DEFAULT_RUNS,
    seed: NightlySeed = None,
    project: Annotated[
        str | None,
        typer.Option(
            envvar="GOOGLE_CLOUD_PROJECT",
            help="The game's Firestore project. Read from the environment on Cloud Run.",
        ),
    ] = None,
    window_hours: Annotated[
        int,
        typer.Option(help="How far back a finished run still counts as somebody playing.", min=1),
    ] = nightly_module.DEMAND_WINDOW_HOURS,
    force: Annotated[
        bool, typer.Option("--force", help="Generate even if nobody has played. Costs money.")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Generate, write the run directory, publish nothing.")
    ] = False,
) -> None:
    """The scheduled job: publish tomorrow's board, if anyone is still playing today's.

    Exits 0 for every outcome it planned for, including the two that publish nothing — a
    night with no players and a night where no board was good enough are both the system
    working. Only a genuine failure exits non-zero, so that a Cloud Run Job's retry means
    "something broke" rather than "try spending that again".
    """
    if not project:
        typer.secho("GOOGLE_CLOUD_PROJECT is not set", err=True, fg=typer.colors.RED)
        raise typer.Exit(2)

    cfg = config_module.load(config)
    # One client, two adapters on it: the game's boards and runs, and the generator's own
    # category pool. The pool lives in the database rather than beside the code because a
    # Cloud Run task's disk does not survive it, and a pool re-invented nightly is not a
    # pool.
    db = connect(project)
    night = asyncio.run(
        nightly_module.tonight(
            _llm(cfg),
            cfg,
            FirestoreStore(db),
            source=FirestoreCategories(db),
            count=count,
            seed=seed,
            out_dir=out,
            window_hours=window_hours,
            force=force,
            dry_run=dry_run,
        )
    )
    typer.echo(night.summary())
    if night.run is not None:
        # The run directory lives in the container's filesystem and dies with the task, so
        # the ledger goes to stdout as well. Cloud Logging keeps it for a month for
        # nothing, and it is the only record of what a night cost.
        typer.echo("\nledger: " + json.dumps(night.run.ledger.to_json()["summary"]))
        if night.run.directory:
            typer.echo(f"written to {night.run.directory}")


@app.command()
def run(
    count: Count = 4,
    config: ConfigFile = None,
    out: Annotated[Path, typer.Option(help="Where to write the run directory.")] = DEFAULT_RUNS,
    seed: Seed = 0,
    all_of_them: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Propose all `count` boards instead of stopping at the first accepted one.",
        ),
    ] = False,
) -> None:
    """Generate, solve, red-team and grade, into a run directory. Publishes nothing.

    `--all` is for experiments: comparing two configurations wants a sample of a known
    size, and a run that stops early gives a sample whose size is the result.
    """
    cfg = config_module.load(config)
    result = asyncio.run(
        pipeline.run(
            _llm(cfg),
            cfg,
            count=count,
            seed=seed,
            out_dir=out,
            stop_on_accept=not all_of_them,
        )
    )
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
def gloss(
    config: ConfigFile = None,
    published: Annotated[
        bool,
        typer.Option(
            "--published",
            help="Annotate the boards in the game's database instead of puzzles.json.",
        ),
    ] = False,
    project: Annotated[
        str | None,
        typer.Option(envvar="GOOGLE_CLOUD_PROJECT", help="Needed with --published."),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Rewrite notes on boards that already have them.")
    ] = False,
    limit: Annotated[
        int | None,
        typer.Option(help="Stop after this many boards, so a first run can be a cheap one.", min=1),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Explain the boards, print them, write nothing.")
    ] = False,
) -> None:
    """Write the notes a player reads under a solved row, onto boards that have none.

    A one-off, not a schedule: every board written from now on is glossed on the night it
    is generated, and this is for the ones that came before. It is cheap — one short call
    per board, an order of magnitude under what proposing one costs — but it is a call per
    board, so `--limit` is there to buy a few and look at them first.
    """
    cfg = config_module.load(config)

    # Rewritten one board at a time, so a backfill that is killed keeps what it paid for.
    # Prettier reformats the file afterwards, exactly as it does after `export`.
    def to_file(puzzle: Puzzle) -> None:
        corpus_module.rewrite([puzzle])

    written: list[Puzzle] = []
    if published:
        if not project:
            typer.secho("--published needs GOOGLE_CLOUD_PROJECT", err=True, fg=typer.colors.RED)
            raise typer.Exit(2)
        store = FirestoreStore(connect(project))
        boards = [entry.puzzle for entry in store.schedule()]
        write = written.append if dry_run else store.annotate
    else:
        boards, _ = corpus_module.load()
        write = written.append if dry_run else to_file

    done = asyncio.run(
        backfill_module.backfill(_llm(cfg), cfg, boards, write, force=force, limit=limit)
    )
    typer.echo(done.summary())

    if dry_run:
        typer.echo(json.dumps([p.to_game_json() for p in written], indent="\t", ensure_ascii=False))
    elif done.glossed and not published:
        typer.secho("now run `pnpm format && pnpm test` in the repo root", err=True)

    # Nothing explained and something tried is a failure worth an exit code; a run with
    # nothing left to do is not.
    raise typer.Exit(1 if done.failed and not done.glossed else 0)


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
