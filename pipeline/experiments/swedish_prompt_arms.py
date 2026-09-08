"""The 2x2: does prompting *in* Swedish beat prompting in English about Swedish?

Two factors, crossed:

  seeds   — the few-shot boards the proposer copies its standard from. Either the three
            shipped English boards, or three hand-written Swedish ones (`seeds.sv.json`).
  prompt  — the language the *authoring* instructions are written in. `sv` is today's
            production behaviour: English instructions, "your output is Swedish".
            `sv-native` is `prompts_sv`, the same instructions written in Swedish.

Held constant across all four arms, on purpose and at some cost:

- **One category pool, shared.** Inventing per arm would have let theme sampling — three
  themes drawn from twelve — swamp an effect measured on three boards. So the pool is
  invented once, copied to each arm, and every arm draws the same three (device, theme)
  slots. (Themes are drawn from one rng seed; devices are walked from the date's ordinal,
  so arms run on the same day agree on those too.) The inventor is a prompt too, and the
  question of whether
  *it* should be Swedish is answered separately and far more cheaply, by running it both
  ways and reading the two pools side by side (`invent_only`).
- **Three examples per arm, not two.** Production shows `[:2]`; the Swedish seeds are
  three. Handing one arm two examples and the other three would confound example count
  with example language.
- **English solve, red-team and grade in every arm.** They are the measuring instruments.

Arms run concurrently, each with its own ledger, so per-arm cost is attributable.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
from dataclasses import replace
from pathlib import Path

from connectris_pipeline import corpus as corpus_module
from connectris_pipeline import pipeline
from connectris_pipeline.categories import JsonCategorySource
from connectris_pipeline.config import Config
from connectris_pipeline.language import get as get_language
from connectris_pipeline.llm import GeminiLLM, Ledger
from connectris_pipeline.spec import Puzzle
from connectris_pipeline.stages import invent as invent_stage

HERE = Path(__file__).resolve().parent
SEEDS_SV = HERE.parent / "seeds.sv.json"
OUT = HERE.parent / "runs" / "arms"

ARMS = {
    "en-seed_en-prompt": ("en", "sv"),
    "sv-seed_en-prompt": ("sv", "sv"),
    "en-seed_sv-prompt": ("en", "sv-native"),
    "sv-seed_sv-prompt": ("sv", "sv-native"),
    # The follow-up, run after the 2x2 and against the *other* pool. The 2x2 held the pool
    # fixed at the English-prompted one, which came back full of Nordic themes and pushed
    # every arm toward folklore and capital cities. This arm is the winning configuration
    # drawing from the Swedish-prompted pool instead, whose themes are ordinary categories
    # that happen to be in Swedish. Whether that is better is a judgement about register,
    # not a number the pipeline can produce.
    "sv-seed_sv-prompt_neutral-pool": ("sv", "sv-native"),
}


def swedish_seeds() -> list[Puzzle]:
    return [Puzzle.from_game_json(p) for p in json.loads(SEEDS_SV.read_text())]


def english_seeds() -> list[Puzzle]:
    return corpus_module.load()[0][:3]


async def build_pool(llm: GeminiLLM, language: str, path: Path, count: int) -> Path:
    """Invent one pool, for one prompt language, and leave it on disk to be copied."""
    if await asyncio.to_thread(path.exists):
        return path
    cfg = replace(Config(), language=language, invent_batch=count)
    source = JsonCategorySource(path, devices=list(get_language(language).devices))
    shipped = corpus_module.load()[1]
    banked = await invent_stage(llm, cfg, source, count=count, taken=set(shipped.concepts))
    print(f"  pool {path.name}: banked {banked}")
    return path


async def one_arm(name: str, seeds: str, language: str, pool: Path, count: int) -> dict:
    arm_dir = OUT / name
    arm_dir.mkdir(parents=True, exist_ok=True)

    # Each arm gets its own copy of the identical pool, so `allocate` marking a theme used
    # in one arm cannot change what the next arm is handed.
    arm_pool = arm_dir / "categories.json"
    shutil.copy(pool, arm_pool)
    lang = get_language(language)
    source = JsonCategorySource(arm_pool, devices=list(lang.devices))

    cfg = replace(Config(), language=language, concurrency=4)
    llm = GeminiLLM(ledger=Ledger(), max_retries=cfg.max_retries, concurrency=cfg.concurrency)

    result = await pipeline.run(
        llm,
        cfg,
        count=count,
        seed=0,
        # `count` is a ceiling in production and a sample size here. An arm that stopped at
        # its first accepted board would report a sample whose size is itself a result.
        stop_on_accept=False,
        out_dir=arm_dir,
        # Words narrowed to Swedish (so: none shipped); concepts pooled across languages.
        corpus=corpus_module.load(language="sv")[1],
        examples=swedish_seeds() if seeds == "sv" else english_seeds(),
        source=source,
    )
    print(f"\n=== {name} ===\n{result.summary()}")
    return {
        "arm": name,
        "seeds": seeds,
        "language": language,
        "directory": str(result.directory),
        "ledger": llm.ledger.summary(),
    }


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--invent-batch", type=int, default=12)
    ap.add_argument("--only", default="", help="Comma-separated arm names.")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    pooler = GeminiLLM(ledger=Ledger(), max_retries=3, concurrency=2)
    print("inventing pools")
    pools = {
        lang: await build_pool(pooler, lang, OUT / f"pool.{lang}.json", args.invent_batch)
        for lang in ("sv", "sv-native")
    }

    wanted = set(args.only.split(",")) if args.only else set(ARMS)
    results = await asyncio.gather(
        *(
            # Every arm draws from the *same* pool — the English-prompted one, which is
            # today's production behaviour. Giving each prompt language its own pool was
            # tried and rejected: the two pools come back with different themes, and at
            # three boards an arm's subject matter would have swamped its prompt.
            one_arm(
                name,
                seeds,
                lang,
                pools["sv-native" if name.endswith("neutral-pool") else "sv"],
                args.count,
            )
            for name, (seeds, lang) in ARMS.items()
            if name in wanted
        )
    )
    (OUT / "arms.json").write_text(
        json.dumps(
            {"pool_ledger": pooler.ledger.summary(), "arms": list(results)},
            indent=2,
            ensure_ascii=False,
        )
    )
    total = pooler.ledger.summary()["output_tokens"] + pooler.ledger.summary()["thinking_tokens"]
    for r in results:
        total += r["ledger"]["output_tokens"] + r["ledger"]["thinking_tokens"]
    print(f"\ntotal billed output+thinking: {total:,} tokens  (~${total * 4.15 / 1_146_408:.2f})")


if __name__ == "__main__":
    asyncio.run(main())
