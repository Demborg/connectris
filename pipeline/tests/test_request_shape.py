"""The parts of the Gemini request that are pure, and the parts most likely to rot.

None of this needs credentials or a network — `config` builds a request without sending
one. It exists because this shape has already moved under us: `thinking_level` replaced
`thinking_budget` for Gemini 3, and Gemini 3 wants temperature left alone, which cost a
design decision (see DESIGN.md on solver variety). When it moves again, these fail first.
"""

from __future__ import annotations

import pytest
from conftest import ScriptedLLM
from google.genai.types import GenerateContentConfig, ThinkingConfig
from pydantic import BaseModel

from connectris_pipeline import config as config_module
from connectris_pipeline import prompts
from connectris_pipeline.config import Config, ModelSpec
from connectris_pipeline.llm import LLM, GeminiLLM
from connectris_pipeline.schema import Grade, ProposedPuzzle, RedTeamReport, SolveAttempt
from connectris_pipeline.spec import Group, Puzzle
from connectris_pipeline.stages.solve import attempt_seed, board_order


def config(
    model: ModelSpec, seed: int | None = None, schema: type[BaseModel] = ProposedPuzzle
) -> GenerateContentConfig:
    return GeminiLLM.config(model, "you are a puzzle constructor", schema, seed)


def thinking(model: ModelSpec) -> ThinkingConfig:
    sent = config(model).thinking_config
    assert sent is not None, "a model with a thinking setting must send one"
    return sent


def test_gemini_3_models_send_a_thinking_level():
    """The SDK normalises our lowercase config value into its own enum."""
    sent = thinking(ModelSpec("gemini-3.8-flash", thinking_level="high"))
    assert sent.thinking_level is not None
    assert sent.thinking_level.value.lower() == "high"
    assert sent.thinking_budget is None


def test_two_five_models_still_send_a_token_budget():
    sent = thinking(ModelSpec("gemini-2.5-flash-lite", thinking_budget=0))
    assert sent.thinking_budget == 0
    assert sent.thinking_level is None


def test_the_seed_is_what_makes_two_attempts_differ():
    assert config(ModelSpec("gemini-3.5-flash-lite", thinking_level="low"), 12345).seed == 12345


def test_temperature_is_left_alone_unless_someone_asked_for_it():
    """Gemini 3 wants it at 1.0; sending 1.0 is still a claim we do not want to make."""
    assert config(ModelSpec("gemini-3.8-flash", thinking_level="low")).temperature is None
    assert config(ModelSpec("old-model", temperature=0.4)).temperature == 0.4


def test_a_model_cannot_have_both_thinking_knobs():
    with pytest.raises(ValueError, match="not both"):
        ModelSpec("gemini-3.8-flash", thinking_level="high", thinking_budget=0)


def test_model_key_separates_two_configurations_of_one_model():
    lite = ModelSpec("gemini-3.5-flash-lite", thinking_level="low")
    assert lite.key != ModelSpec("gemini-3.5-flash-lite", thinking_level="high").key
    assert "gemini-3.5-flash-lite" in lite.key


@pytest.mark.parametrize("schema", [ProposedPuzzle, SolveAttempt, Grade])
def test_every_stage_asks_for_json_against_its_own_schema(schema):
    sent = config(ModelSpec("gemini-3.8-flash", thinking_level="low"), schema=schema)
    assert sent.response_mime_type == "application/json"
    assert sent.response_schema is schema


def test_the_grade_schemas_enum_survives_into_the_json_schema():
    """Literal -> enum is what keeps the grader's verdict parseable."""
    assert set(Grade.model_json_schema()["properties"]["verdict"]["enum"]) == {
        "accept",
        "revise",
        "reject",
    }


def test_field_descriptions_reach_the_model():
    """They are the cheapest prompt surface there is, so they must not be stripped."""
    group = ProposedPuzzle.model_json_schema()["$defs"]["ProposedGroup"]["properties"]
    assert "12 characters" in group["words"]["description"]


def test_no_tools_are_offered_anywhere_in_this_pipeline():
    sent = config(ModelSpec("gemini-3.8-flash", thinking_level="low")).automatic_function_calling
    assert sent is not None and sent.disable is True


def test_the_solver_is_weak_and_the_judges_are_not():
    """The difficulty proxy only means anything if the solver is worse than the proposer."""
    cfg = Config()
    assert cfg.solver.thinking_level == "low"
    assert "lite" in cfg.solver.name
    for judge in (cfg.proposer, cfg.red_team, cfg.grader):
        assert judge.thinking_level == "high"


PUZZLE = Puzzle(
    id="t",
    name="T",
    groups=[
        Group("a", "A", ["HAMMER", "CHISEL", "PLANE", "WRENCH"]),
        Group("b", "B", ["FROST", "GALE", "HAZE", "SLEET"]),
    ],
)


def test_attempts_get_different_boards_and_the_same_board_twice():
    seeds = {attempt_seed("t", "m/low", i) for i in range(3)}
    assert len(seeds) == 3, "attempts must differ"
    assert attempt_seed("t", "m/low", 0) == attempt_seed("t", "m/low", 0), "runs must repeat"

    orders = {tuple(board_order(PUZZLE, s)) for s in seeds}
    assert len(orders) == 3
    for order in orders:
        assert sorted(order) == sorted(PUZZLE.words), "a shuffle, not a rewrite"


def test_the_board_is_never_handed_over_in_solution_order():
    assert board_order(PUZZLE, attempt_seed("t", "m/low", 0)) != PUZZLE.words


def test_both_implementations_satisfy_the_seam() -> None:
    """The Protocol is only worth having because this line is type-checked.

    `ty` resolves these assignments against `LLM`; a signature that drifts on either
    implementation fails CI rather than failing at 3am. Nothing here runs at runtime
    beyond two constructions.
    """
    scripted: LLM = ScriptedLLM()
    assert scripted.backend == "scripted"

    def _gemini_is_an_llm(client: GeminiLLM) -> LLM:
        return client


def test_a_red_team_that_never_ran_reads_as_absent_not_as_clean() -> None:
    """A stage that fell over must not be indistinguishable from one that found nothing."""
    _, absent = prompts.grade(puzzle=PUZZLE, traps={}, solver_digest="", red=None, warnings=[])
    assert "did not run" in absent

    _, clean = prompts.grade(
        puzzle=PUZZLE,
        traps={},
        solver_digest="",
        red=RedTeamReport(ambiguous_words=[], alternatives=[], verdict="clean"),
        warnings=[],
    )
    assert "did not run" not in clean


def test_a_mistyped_config_key_is_refused_rather_than_ignored(tmp_path) -> None:
    """It used to fall through the filter and the run quietly used the default."""
    good = tmp_path / "good.toml"
    good.write_text("concurrency = 99\n")
    assert config_module.load(good).concurrency == 99

    typo = tmp_path / "typo.toml"
    typo.write_text("concurency = 99\n")
    with pytest.raises(ValueError, match="concurency"):
        config_module.load(typo)
