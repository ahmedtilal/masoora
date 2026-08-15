# Data validation

Attach a schema to a catalog key and masoora checks the data against it.

```python
import pandera.pandas as pa

events_schema = pa.DataFrameSchema(
    {
        "event_id": pa.Column(str),
        "score": pa.Column(float, pa.Check.in_range(0, 1)),
    }
)

pipeline = (
    PipelineBuilder[MyContext]()
    .with_read_step(read_events, output="events", validate=events_schema)
    .with_transform_step(score, inputs=["events"], output="scored")
    .build()
)
```

If `read_events` returns something that does not match, the run stops with
[`DataValidationError`][masoora.DataValidationError] naming the key.

## Any validator works

masoora never imports pandera. A validator is either:

- an object with a `.validate(data)` method — pandera schemas and
  `DataFrameModel` classes both have one, or
- any callable that raises on bad data.

```python
def non_empty(data):
    if len(data) == 0:
        raise ValueError("no rows")


.with_read_step(read_events, output="events", validate=non_empty)
```

So this works with polars, pandas, Spark, plain dicts, Pydantic models, or a
three-line function. Install pandera yourself, or use the extra:

```bash
pip install "masoora[pandera]"
```

## Checked on write and on read

A value is checked when it is written to a key, and when it is read from a key
that has not been checked yet. Each value is checked once — a read after a
validated write does not repeat the work.

The read check exists because some data never passes through a step:

- **seeded keys** — data handed to the pipeline by the caller
- **test fixtures** — the `reads={...}` values from
  [`to_testable()`][masoora.Pipeline.to_testable]

That second one matters. Fake data drifting away from the real schema is the
main way a well-tested pipeline still breaks in production. Validating fixtures
means your tests fail when the fake data stops resembling reality.

```python
# fails: the fixture does not match the schema the real read step produces
pipeline.to_testable(reads={"events": [{"wrong": "shape"}]}).run(ctx)
```

## Validating seeded keys

Seeds take a validator too:

```python
pipeline = (
    PipelineBuilder[MyContext]()
    .with_seed("events", validate=events_schema)
    .with_transform_step(score, inputs=["events"], output="scored")
    .build()
)

pipeline.run(ctx, catalog=DataCatalog({"events": incoming}))
```

This is worth doing at the edges of your pipeline, where data arrives from
somewhere you do not control.

## Errors

A failure raises [`DataValidationError`][masoora.DataValidationError], carrying
the `key`, the `phase` (`"read"` or `"write"`), and the `original` exception
from your validator. Like any step failure it is wrapped in
[`StepExecutionError`][masoora.StepExecutionError], so you also get the step
that was running:

```python
try:
    pipeline.run(ctx)
except StepExecutionError as exc:
    if isinstance(exc.original, DataValidationError):
        print(exc.original.key, exc.original.phase)
        print(exc.original.original)  # the pandera error, with its report
```

A validator that is neither callable nor has `.validate()` is a wiring
mistake, so it fails at build time with
[`PipelineValidationError`][masoora.PipelineValidationError] rather than
mid-run.

## What this does not do

Validation is opt-in per key. Keys without a validator are never inspected, and
masoora still has no opinion about what a dataset is.

Nor does it replace the checks at your boundaries. Validating on read from your
warehouse tells you the data arrived as expected; validating a transform output
tells you your code did what you meant. Both are useful, for different reasons.
