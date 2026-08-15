# masoora

Fluent builder for testable ETL pipelines in Python.

- **Fluent chaining**: `.with_read_step()` / `.with_transform_step()` / `.with_write_step()`
- **Pydantic context**: typed configuration passed to every step
- **Data catalog**: in-memory key → dataset store (polars/pandas/spark/dicts — anything)
- **DAG resolution**: declare steps in any order; cycles and missing inputs fail at `build()`
- **Testable**: mock reads/writes and assert on the catalog with a pytest fixture

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

## Testing

```python
from masoora import TestRunResult, make_pipeline_fixture

run_pipeline = make_pipeline_fixture(
    pipeline,
    MyContext(source_url="test"),
    reads={"events": fake_events},   # read step is replaced, real source untouched
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
