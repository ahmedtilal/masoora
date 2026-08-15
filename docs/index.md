# masoora

Fluent builder for testable ETL pipelines in Python.

masoora is a **library, not a platform** — no scheduler, no server, no
deployment. You define a pipeline in Python, run it in-process, and test it
with a pytest fixture that swaps out every read and write.

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

## Why

Most orchestration tools ask you to adopt a platform before you can run a
pipeline: a scheduler, a database, a web UI, a deployment story. That is the
right trade when you are running hundreds of jobs on a schedule. It is a poor
trade when you want to express a handful of transformation steps and, above
all, *test them*.

masoora takes the opposite position. A pipeline is an ordinary Python object.
You build it, you run it, and in tests you replace its edges with fakes.

## What you get

- **Fluent chaining** — `.with_read_step()` / `.with_transform_step()` /
  `.with_write_step()` return the builder, so pipelines read top to bottom.
- **Pydantic context** — one typed configuration object, validated once,
  passed to every step.
- **Data catalog** — an in-memory key → dataset store. masoora never inspects
  your data, so polars, pandas, Spark DataFrames and plain dicts all work.
- **DAG resolution** — declare steps in any order. Cycles and missing inputs
  are rejected at [`build()`][masoora.PipelineBuilder.build], not halfway
  through a run.
- **Parallel execution** — dependency-driven scheduling with no level
  barriers. See [Parallel execution](guide/parallel.md).
- **Testable** — mock reads and writes, then assert against the resulting
  catalog. See [Testing](guide/testing.md).

## Where to go next

<div class="grid cards" markdown>

- **[Installation](installation.md)** — install from PyPI, plus the pytest extra.
- **[Building pipelines](guide/pipelines.md)** — steps, the catalog, and DAG rules.
- **[Parallel execution](guide/parallel.md)** — the concurrency contract.
- **[Testing](guide/testing.md)** — fixtures, fakes, and captured writes.
- **[API reference](reference/api.md)** — every public symbol.

</div>
