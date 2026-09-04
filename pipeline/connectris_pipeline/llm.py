"""The provider seam.

One method, `generate`, which takes a schema and returns an instance of it.

The `LLM` protocol is narrow on purpose: `GeminiLLM` and the scripted double in
`tests/conftest.py` are its only implementations, and Vertex serving Claude as well as
Gemini is the reason it stays an interface rather than a class. It is worth having only
because it is *checked* — `tests/test_request_shape.py` asserts both implementations
satisfy it, so a signature that drifts fails the type check instead of failing at 3am.

Token counts are recorded per call rather than money. Prices move; tokens don't.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import time
from dataclasses import asdict, dataclass, field
from typing import Protocol, TypeVar

from pydantic import BaseModel

from .config import ModelSpec

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class ModelError(RuntimeError):
    """A call that failed every retry."""


@dataclass
class Call:
    stage: str
    #: `ModelSpec.key`, so the ledger separates two configurations of the same model.
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    #: Billed as output, invisible in the response, and the reason a "cheap" stage isn't.
    thinking_tokens: int = 0
    seconds: float = 0.0
    attempts: int = 1
    ok: bool = True


@dataclass
class Ledger:
    """What the run cost, in the only unit that stays true."""

    calls: list[Call] = field(default_factory=list)

    def add(self, call: Call) -> None:
        self.calls.append(call)

    def summary(self) -> dict:
        by_model: dict[str, dict[str, int]] = {}
        for c in self.calls:
            row = by_model.setdefault(
                c.model,
                {
                    "calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "thinking_tokens": 0,
                    "failed": 0,
                },
            )
            row["calls"] += 1
            row["input_tokens"] += c.input_tokens
            row["output_tokens"] += c.output_tokens
            row["thinking_tokens"] += c.thinking_tokens
            row["failed"] += 0 if c.ok else 1
        return {
            "calls": len(self.calls),
            "input_tokens": sum(c.input_tokens for c in self.calls),
            "output_tokens": sum(c.output_tokens for c in self.calls),
            "thinking_tokens": sum(c.thinking_tokens for c in self.calls),
            "seconds": round(sum(c.seconds for c in self.calls), 1),
            "by_model": by_model,
        }

    def to_json(self) -> dict:
        return {"summary": self.summary(), "calls": [asdict(c) for c in self.calls]}


class LLM(Protocol):
    #: Every implementation records what it spent here.
    ledger: Ledger
    #: Named in the run header, so an operator can see which project a batch hit.
    backend: str

    async def generate(
        self,
        *,
        stage: str,
        model: ModelSpec,
        system: str,
        prompt: str,
        schema: type[T],
        seed: int | None = None,
    ) -> T: ...


class GeminiLLM:
    """google-genai on Vertex AI.

    One backend and one transport, deliberately. Vertex is where this job lives — a Cloud
    Run Job in the same project, authenticating with ADC, no key to leak — and supporting
    AI Studio alongside it bought a second code path for a second set of failure modes.

    Vertex serves generation through `models.generate_content`; its Interactions endpoint
    rejects every Gemini model with `Unsupported model interaction`, so the newer surface
    is simply not available here yet. Structured output is a Pydantic class handed to
    `response_schema`, and the SDK parses the reply back into it.
    """

    def __init__(self, *, ledger: Ledger, max_retries: int = 3, concurrency: int = 8) -> None:
        from google import genai  # imported here so the package works without the SDK

        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not project:
            raise ModelError(
                "No project. Set GOOGLE_CLOUD_PROJECT, and authenticate with "
                "`gcloud auth application-default login`."
            )
        location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")

        self._client = genai.Client(vertexai=True, project=project, location=location)
        self.backend = f"vertex:{project}/{location}"
        self.ledger = ledger
        self._max_retries = max_retries
        self._gate = asyncio.Semaphore(concurrency)

    @staticmethod
    def config(model: ModelSpec, system: str, schema: type[BaseModel], seed: int | None):
        """The whole request, minus the prompt. Every stage goes through here.

        Only the knobs that are actually set are sent — an unset knob is not a default.
        Temperature in particular is normally absent: Gemini 3 wants it left at 1.0, and
        sending 1.0 explicitly is a claim about sampling we do not want to make.
        """
        from google.genai import types

        if model.thinking_level is not None:
            thinking = types.ThinkingConfig(thinking_level=model.thinking_level)
        elif model.thinking_budget is not None:
            thinking = types.ThinkingConfig(thinking_budget=model.thinking_budget)
        else:
            thinking = None

        return types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
            thinking_config=thinking,
            temperature=model.temperature,
            seed=seed,
            # No tools anywhere in this pipeline; saying so keeps the SDK from warning
            # about automatic function calling on every call.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

    async def generate(
        self,
        *,
        stage: str,
        model: ModelSpec,
        system: str,
        prompt: str,
        schema: type[T],
        seed: int | None = None,
    ) -> T:
        started = time.monotonic()
        config = self.config(model, system, schema, seed)
        last: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                async with self._gate:
                    resp = await self._client.aio.models.generate_content(
                        model=model.name, contents=prompt, config=config
                    )
                # Structured output can still come back as text when the model hits a stop
                # reason mid-object; try the text before giving up to a retry.
                parsed = resp.parsed or schema.model_validate_json(resp.text or "")
                usage = resp.usage_metadata
                self.ledger.add(
                    Call(
                        stage=stage,
                        model=model.key,
                        input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
                        output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
                        thinking_tokens=getattr(usage, "thoughts_token_count", 0) or 0,
                        seconds=time.monotonic() - started,
                        attempts=attempt,
                    )
                )
                return parsed
            except Exception as exc:
                # Covers the SDK's own error tree and a ValidationError from output that
                # came back as well-formed JSON but the wrong shape.
                last = exc
                log.warning("%s call to %s failed (attempt %d): %s", stage, model.key, attempt, exc)
                if attempt < self._max_retries:
                    await asyncio.sleep(min(2**attempt, 20) * (0.5 + random.random()))

        self.ledger.add(
            Call(
                stage=stage,
                model=model.key,
                seconds=time.monotonic() - started,
                attempts=self._max_retries,
                ok=False,
            )
        )
        raise ModelError(f"{stage}: {model.key} failed {self._max_retries} times: {last}") from last


def dumps(obj) -> str:
    """Compact JSON for embedding structured data inside a prompt."""
    if isinstance(obj, BaseModel):
        obj = obj.model_dump()
    return json.dumps(obj, ensure_ascii=False, indent=2)
