# masoora

A helper library for writing data pipelines in Python.

masoora handles the wiring — working out step order, passing data between
steps, running independent steps at the same time — so your code stays focused
on the transformations.

```python
from masoora import PipelineBuilder, PipelineContext


class MyContext(PipelineContext):
    source_url: str
    min_score: float = 0.5


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

## Readable pipelines

That chain is the whole pipeline. Someone opening the file can see where the
data comes from, what happens to it, and where it ends up, without running
anything or opening a UI.

Most of a data engineer's time goes on reading pipelines rather than writing
them — during an incident, during a handover, six months later. Keeping the
shape of the pipeline visible in the source is the point.

## Works with your orchestrator

masoora does not schedule anything. It runs in the process you call it from.
Airflow, Dagster, Prefect, cron, a Lambda, or your laptop all work.

A common setup: build the pipeline, package it as a versioned wheel, and call
it from an Airflow task. Airflow passes its parameters in as the context, and
the whole pipeline runs as one task.

```python
# inside an Airflow task
from my_pipelines import build_daily_events

pipeline = build_daily_events()
pipeline.run(MyContext(**context["params"]))
```

Because the pipeline is a package, you change it and ship a new version
without deploying the orchestrator. Pin the version in the DAG and you know
exactly what ran. See [Orchestrators](guide/orchestrators.md).

## Testable

Read and write steps are the only places a pipeline touches the outside world.
Swap them for fixtures and everything in between runs exactly as it does in
production, against data you control.

```python
run_pipeline = make_pipeline_fixture(
    pipeline,
    MyContext(source_url="test"),
    reads={"events": fake_events},
)
```

See [Testing](guide/testing.md).

## What you get

- **Fluent chaining** — `.with_read_step()` / `.with_transform_step()` /
  `.with_write_step()` return the builder, so pipelines read top to bottom.
- **Pydantic context** — one typed configuration object, validated once,
  passed to every step. Also the handoff point from whatever calls you.
- **Data catalog** — an in-memory key → dataset store. masoora never inspects
  your data, so polars, pandas, Spark DataFrames and plain dicts all work.
- **DAG resolution** — declare steps in any order. Cycles and missing inputs
  are caught at [`build()`][masoora.PipelineBuilder.build], before any data
  is read.
- **Data validation** — attach a pandera schema, or any callable, to a catalog
  key. See [Data validation](guide/validation.md).
- **Parallel execution** — dependency-driven scheduling with no level
  barriers. See [Parallel execution](guide/parallel.md).

## Where to go next

<div class="grid cards" markdown>

- **[Installation](installation.md)** — install from PyPI, plus the extras.
- **[Building pipelines](guide/pipelines.md)** — steps, the catalog, and DAG rules.
- **[Data validation](guide/validation.md)** — schemas on catalog keys.
- **[Parallel execution](guide/parallel.md)** — the concurrency contract.
- **[Testing](guide/testing.md)** — fixtures, fakes, and captured writes.
- **[Orchestrators](guide/orchestrators.md)** — packaging and running under Airflow.
- **[API reference](reference/api.md)** — every public symbol.

</div>
