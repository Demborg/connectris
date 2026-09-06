# The nightly generator, as a Cloud Run Job.
#
# Built from the repository root, not from `pipeline/`, because the pipeline reads two
# things out of the repo and the simplest way to keep those paths true is to keep the
# layout: the package resolves `puzzles.json` relative to its own file, so the image is
# laid out the way a checkout is and no code has to learn it is in a container.
#
# Nothing here is optimised for start-up. This is a job that thinks for ten minutes and
# runs once a day; the only thing worth buying is a dependency layer that a source-only
# change does not invalidate.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/pipeline/.venv

# Dependencies from the lock, before any source, so editing a prompt does not reinstall
# grpc. `--no-dev` keeps pytest, ruff and the type checker out of the runtime image.
COPY pipeline/pyproject.toml pipeline/uv.lock ./pipeline/
RUN cd pipeline && uv sync --locked --no-dev --no-install-project

COPY pipeline/connectris_pipeline ./pipeline/connectris_pipeline

# The hand-written boards. Few-shot examples for the proposer and nothing else — what a
# new board must be *new* against is read from Firestore, not from here.
COPY src/lib/data/puzzles.json ./src/lib/data/puzzles.json

# `categories.json` is deliberately absent. It is the file-backed category pool, which is
# git-ignored local state and would not exist in a clean checkout anyway; in here the pool
# lives in Firestore, because a Cloud Run task's disk does not outlive the task. An empty
# pool is a valid starting point — the first night finds it short and banks a batch.

RUN cd pipeline && uv sync --locked --no-dev

ENV PATH="/app/pipeline/.venv/bin:$PATH"

# Never root. The category pool and the run directory are written under /app/pipeline, so
# that has to be writable by the user that runs.
RUN useradd --create-home --uid 1001 generator && chown -R generator:generator /app
USER generator

ENTRYPOINT ["connectris-pipeline", "--verbose"]
CMD ["nightly"]
