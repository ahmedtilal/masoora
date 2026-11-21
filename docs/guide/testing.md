# Testing

This is the part of masoora that justifies the rest of it.

A pipeline's read and write steps are the only places it touches the outside
world. Replace those, and everything in between — the transforms, the DAG, the
scheduling — runs exactly as it does in production, against data you control.

```python
from masoora import TestRunResult, make_pipeline_fixture

run_pipeline = make_pipeline_fixture(
    pipeline,
    MyContext(source_url="test"),
    reads={"events": fake_events},  # read step replaced, real source untouched
)


def test_top_events(run_pipeline: TestRunResult[MyContext]) -> None:
    assert run_pipeline.catalog["top"] == expected
    assert run_pipeline.written["top"] == expected  # write captured, not executed
```

`make_pipeline_fixture` returns a **pytest fixture**, so assign it at module
level and request it by name in your tests.

## What gets replaced

`reads`
: A mapping of catalog key → value. Any **read step** whose `output` appears
  here is not called; the value is placed in the catalog directly. Read steps
  you do not name still run — so you can fake one source and let another run
  for real. Only read steps are replaced: a key that is a transform's output,
  or a [seed](pipelines.md#seeding-the-catalog), is silently ignored in
  `reads`, with no error. A seeded key is fed through the catalog instead
  (see [Seeding a catalog](#seeding-a-catalog)); a transform's output is
  computed, so to control it, control its inputs.

`mock_writes`
: `True` by default. Write steps do not execute; their inputs are captured into
  [`TestRunResult.written`][masoora.TestRunResult] instead, keyed by the write
  step's **input keys**. Set `False` to let writes actually run — see
  [Testing a write step for real](#testing-a-write-step-for-real).

`target`
: Run only the steps needed to produce one key, exactly as
  [`Pipeline.run`][masoora.Pipeline.run] does. Useful for testing one branch
  of a larger DAG in isolation.

## Asserting on the result

[`TestRunResult`][masoora.TestRunResult] gives you two views:

```python
def test_pipeline(run_pipeline: TestRunResult[MyContext]) -> None:
    # every intermediate value, not just the final one
    assert len(run_pipeline.catalog["scored"]) == 100
    assert run_pipeline.catalog["top"] == expected

    # what would have been written, had writes been real
    assert run_pipeline.written["top"] == expected
```

Asserting on intermediates is the point. When a pipeline produces the wrong
output, the useful question is *which step* went wrong, and the catalog answers
it directly.

### How `written` is keyed

A mocked write step captures one entry per input key, whatever the step is
called. A step with `inputs=["accepted", "rejected"]` produces two entries:

```python
result = pipeline.to_testable().run(ctx)
assert result.written["accepted"] == expected_accepted
assert result.written["rejected"] == expected_rejected
```

Consequences worth knowing:

- Two write steps that consume the same key share one entry, and `written`
  records *what* would have been written, not *which step* wrote it. To check
  that a particular write ran, test it for real.
- A key that no write step consumes never appears in `written`, even though it is
  in `catalog`.
- Writes are mocked only when `mock_writes=True`. With `False`, `written` is
  empty.

The mocked write step is also replaced wholesale, so the real write function
is **not** called. Anything it would have done, including validating its
arguments, does not happen. That is what the next section is for.

## A fresh context per test

Pass a **callable** instead of an instance when the context must not be shared
between tests:

```python
run_pipeline = make_pipeline_fixture(
    pipeline,
    lambda: MyContext(source_url="test"),  # constructed per test
    reads={"events": fake_events},
)
```

With a plain instance, every test that requests the fixture sees the same
object. That is fine for a frozen config and a problem for anything mutable.

## Without pytest

The fixture is a thin wrapper. The underlying API needs no test framework at
all:

```python
result = pipeline.to_testable(reads={"events": fake_events}).run(ctx)
assert result.catalog["top"] == expected
```

[`to_testable()`][masoora.Pipeline.to_testable] returns a
[`TestablePipeline`][masoora.TestablePipeline] and takes the same `reads`,
`mock_writes`, and `target` arguments. Use it from unittest, from a script, or
from a notebook.

!!! tip

    Because `to_testable()` has no pytest dependency, you can install plain
    `masoora` rather than `masoora[pytest]` if this is the style you use.

Everything on this page that mentions the fixture works the same through
`to_testable()`. It is also the more flexible of the two: only `to_testable()`
can take a catalog, which the fixture does not expose.

## Seeding a catalog

When a pipeline declares a [seed](pipelines.md#seeding-the-catalog), the data
arrives through the catalog, so pass one to `run()`:

```python
from masoora import DataCatalog, PipelineBuilder, PipelineContext


class Config(PipelineContext):
    pass


def add_one(ctx: Config, raw: list[int]) -> list[int]:
    return [r + 1 for r in raw]


pipeline = (
    PipelineBuilder[Config]()
    .with_seed("raw")
    .with_transform_step(add_one, inputs=["raw"], output="out")
    .build()
)

result = pipeline.to_testable().run(Config(), catalog=DataCatalog({"raw": [1, 2]}))
assert result.catalog["out"] == [2, 3]
```

`result.catalog` is the same object you passed in, now holding the outputs
as well. Seeded values are validated on first read if the key has a
[validator](validation.md).

## Testing a write step for real

Mocked writes prove a pipeline *would* write the right data. They do not
exercise the write function itself: its SQL, its file layout, its atomic
rename. Test that by running it with `mock_writes=False` against a real but
disposable target — pytest's `tmp_path` for files:

```python
from pathlib import Path

from masoora import PipelineBuilder, PipelineContext


class Ctx(PipelineContext):
    out_dir: Path


def read_rows(ctx: Ctx) -> list[int]:
    raise RuntimeError("real source; replaced in tests")


def write_rows(ctx: Ctx, rows: list[int]) -> None:
    (ctx.out_dir / "rows.txt").write_text("\n".join(map(str, rows)))


pipeline = (
    PipelineBuilder[Ctx]()
    .with_read_step(read_rows, output="rows")
    .with_write_step(write_rows, inputs=["rows"])
    .build()
)


def test_write_rows_for_real(tmp_path: Path) -> None:
    result = pipeline.to_testable(reads={"rows": [1, 2, 3]}, mock_writes=False).run(
        Ctx(out_dir=tmp_path)
    )

    assert (tmp_path / "rows.txt").read_text() == "1\n2\n3"
    assert result.written == {}  # nothing is captured when writes are real
```

The read is still faked, the write is real, and `tmp_path` is deleted by
pytest. The same approach works for any target you can create and discard: a
SQLite file, a local DuckDB database, a temporary schema.

If the write goes through an injected store, you do not need `mock_writes=False`
at all — hand the factory a fake or a store pointed at `tmp_path`. See
[Context and dependency injection](context.md) and the
[end-to-end example](../examples/swappable-storage.md).

## A note on step names in tests

`to_testable()` replaces each faked read step with a function named
`constant_read`. If a fixture value fails the key's
[validator](validation.md), the resulting `StepExecutionError` reports
`step_name == "constant_read"` rather than your read function's name. Tests that
assert on `step_name` should expect that for replaced reads.
