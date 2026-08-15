# masoora

[![CI](https://github.com/ahmedtilal/masoora/actions/workflows/ci.yml/badge.svg)](https://github.com/ahmedtilal/masoora/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/masoora.svg)](https://pypi.org/project/masoora/)
[![Python versions](https://img.shields.io/pypi/pyversions/masoora.svg)](https://pypi.org/project/masoora/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/ahmedtilal/masoora/blob/master/LICENSE)
[![Typed](https://img.shields.io/badge/typing-strict-blue.svg)](https://peps.python.org/pep-0561/)

Fluent builder for testable ETL pipelines in Python.

masoora is a **library, not a platform** — no scheduler, no server, no
deployment. You define a pipeline in Python, run it in-process, and test it
with a pytest fixture that swaps out every read and write.

- **Fluent chaining**: `.with_read_step()` / `.with_transform_step()` / `.with_write_step()`
- **Pydantic context**: typed configuration passed to every step
- **Data catalog**: in-memory key → dataset store (polars/pandas/spark/dicts — anything)
- **DAG resolution**: declare steps in any order; cycles and missing inputs fail at `build()`
- **Parallel**: dependency-driven scheduling, no level barriers
- **Testable**: mock reads/writes and assert on the catalog with a pytest fixture

## Installation

```bash
pip install masoora
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add masoora
```

Requires Python 3.10+. The only runtime dependency is Pydantic.

The pytest helpers (`make_pipeline_fixture`) need pytest, available as an extra:

```bash
pip install "masoora[pytest]"
```

## Usage

```python
from masoora import PipelineBuilder, PipelineContext


class MyContext(PipelineContext):
    source_url: str
    min_score: float = 0.5


def read_events(ctx: MyContext): ...
def score(ctx: MyContext, events): ...
def filter_top(ctx: MyContext, scored): ...
def write_db(ctx: MyContext, top): ...


pipeline = (
    PipelineBuilder[MyContext]()
    .with_read_step(read_events, output="events")
    .with_transform_step(score, inputs=["events"], output="scored")
    .with_transform_step(filter_top, inputs=["scored"], output="top")
    .with_write_step(write_db, inputs=["top"])
    .build()
)

catalog = pipeline.run(MyContext(source_url="https://..."))
```

Step signatures:

| Step kind | Signature | Effect |
|---|---|---|
| read | `fn(ctx) -> dataset` | `catalog[output] = result` |
| transform | `fn(ctx, *inputs) -> dataset` | `catalog[output] = result` |
| write | `fn(ctx, *inputs) -> None` | terminal |

Steps may be declared in any order — `build()` topo-sorts them. Run only what's
needed for one output with `pipeline.run(ctx, target="top")`. Pre-populated
catalog keys are declared with `.with_seed(key)`.

## Parallel execution

```python
pipeline.run(ctx, parallel=True)  # thread pool, os.cpu_count() workers
pipeline.run(ctx, parallel=4)  # explicit worker count
pipeline.run(ctx, executor=pool)  # your Executor (not shut down by masoora)
```

Steps run concurrently in a `ThreadPoolExecutor` with dependency-driven
scheduling: each step starts the instant its own dependencies finish — there
is no level barrier, so unrelated slow steps never delay a ready branch.
Fail-fast: the first step error cancels queued work and raises
`StepExecutionError` immediately; already-running siblings finish in the
background.

Contract: steps must only read their declared input keys, write their own
output key, and treat the context as read-only. Under this contract parallel
results are identical to sequential.

## Testing

```python
from masoora import TestRunResult, make_pipeline_fixture

run_pipeline = make_pipeline_fixture(
    pipeline,
    MyContext(source_url="test"),
    reads={"events": fake_events},  # read step is replaced, real source untouched
)


def test_top_events(run_pipeline: TestRunResult[MyContext]) -> None:
    assert run_pipeline.catalog["top"] == expected
    assert run_pipeline.written["top"] == expected  # write step captured, not executed
```

Or without pytest: `pipeline.to_testable(reads={...}).run(ctx)` → `TestRunResult`.

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
uv run mypy src tests
```

Issues and pull requests are welcome. The API is still young — if something
feels awkward to use, that is worth an issue.

## Links

- [Documentation](https://ahmedtilal.github.io/masoora/)
- [Changelog](https://github.com/ahmedtilal/masoora/blob/master/CHANGELOG.md)
- [PyPI](https://pypi.org/project/masoora/)
- [Issues](https://github.com/ahmedtilal/masoora/issues)

## License

MIT — see [LICENSE](https://github.com/ahmedtilal/masoora/blob/master/LICENSE).
