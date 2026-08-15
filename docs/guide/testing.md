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
: A mapping of catalog key → value. Any read step whose `output` appears here
  is not called; the value is placed in the catalog directly. Read steps you
  do not name still run — so you can fake one source and let another run for
  real.

`mock_writes`
: `True` by default. Write steps do not execute; their inputs are captured into
  [`TestRunResult.written`][masoora.TestRunResult] instead, keyed by input key.
  Set `False` to let writes actually run.

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
