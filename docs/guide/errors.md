# Errors and retries

When a step raises during [`run()`][masoora.Pipeline.run], masoora wraps the
exception in a [`StepExecutionError`][masoora.StepExecutionError] and stops.
This page covers what you get back, how to turn it into a clean failure, and
what a failed run leaves behind.

## What `StepExecutionError` carries

| Attribute | Meaning |
|---|---|
| `step_index` | Position of the failing step in the execution order |
| `step_name` | The step's name — see [Step names](pipelines.md#step-names) |
| `original` | The exception the step raised |

The original is also chained as `__cause__`, so an unhandled
`StepExecutionError` prints the original traceback beneath it.

```python
from masoora import PipelineBuilder, PipelineContext, StepExecutionError


class Config(PipelineContext):
    pass


def read_rows(ctx: Config) -> list[int]:
    return [1, 2, 3]


def write_warehouse(ctx: Config, rows: list[int]) -> None:
    raise ConnectionError("warehouse unreachable")


pipeline = (
    PipelineBuilder[Config]()
    .with_read_step(read_rows, output="rows")
    .with_write_step(write_warehouse, inputs=["rows"])
    .build()
)

try:
    pipeline.run(Config())
except StepExecutionError as exc:
    print(exc.step_index, exc.step_name, repr(exc.original))
    print(exc)
```

```text
1 write_warehouse ConnectionError('warehouse unreachable')
Step 1 ('write_warehouse') failed: ConnectionError: warehouse unreachable
```

`step_index` is the step's position in the list being executed. With
`target=`, that is the pruned list, not the full pipeline.

### Only `Exception` is wrapped

Steps are wrapped when they raise a subclass of `Exception`. `KeyboardInterrupt`,
`SystemExit` and other `BaseException`s propagate unchanged, in both sequential
and parallel mode. That is what you want from Ctrl-C and from a worker being
told to exit: they are not step failures.

Also wrapped, because they happen inside the step:

- A [`DataValidationError`][masoora.DataValidationError] from a catalog key's
  validator. Its `original` is the `DataValidationError`, which in turn has the
  validator's exception as *its* `original` and the `key` and `phase`. See
  [Data validation](validation.md).

Build-time errors — `PipelineValidationError`, `PipelineCycleError` — are
raised by `build()` and `run(target=...)` and are not wrapped.

### In parallel mode

Only the *first* failure is reported; if two steps fail at once, the other is
dropped. Queued steps are cancelled but steps already running are not
interrupted, so they may finish — and perform their side effects — after the
error is raised. See [Parallel execution](parallel.md#failure-behaviour).

## Turning it into a non-zero exit

For a command-line entry point or a container job, unwrap the error, log what
failed, and exit non-zero. Here with [Typer](https://typer.tiangolo.com/),
which masoora does not depend on:

```python
import typer

from masoora import PipelineBuilder, PipelineContext, StepExecutionError


class Ctx(PipelineContext):
    run_date: str


def load(ctx: Ctx) -> list[int]:
    if ctx.run_date == "bad":
        raise ConnectionError("warehouse unreachable")
    return [1, 2, 3]


pipeline = PipelineBuilder[Ctx]().with_read_step(load, output="rows").build()


def main(run_date: str) -> None:
    try:
        catalog = pipeline.run(Ctx(run_date=run_date))
    except StepExecutionError as exc:
        typer.echo(f"{exc.step_name} failed: {exc.original!r}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"rows={len(catalog['rows'])}")


if __name__ == "__main__":
    typer.run(main)
```

Run as `python cli.py 2026-01-01` it prints `rows=3` and exits 0. Run as
`python cli.py bad` it prints `load failed: ConnectionError('warehouse unreachable')`
to stderr and exits 1.

The same shape works without Typer: catch `StepExecutionError`, write to
stderr, `sys.exit(1)`. Orchestrators and schedulers treat a non-zero exit as
failure and apply their own retry policy — which is the right place for it.
masoora does not retry.

If you let a `StepExecutionError` escape instead, Python exits with status 1
and prints the traceback, which also works; catching it just gives you control
over the message.

## What is not rolled back

masoora runs steps one after another and has **no transaction around the run**.
When step *N* fails:

- Steps before *N* have already run. **Write steps among them have already
  written.** Nothing undoes that.
- In sequential mode, steps after *N* do not run. In parallel mode, steps that
  depend on *N* do not run, but unrelated steps already in flight may still
  finish.
- The catalog is not cleared. If you passed your own
  [`DataCatalog`][masoora.DataCatalog] to `run(catalog=...)`, it still holds
  every value produced before the failure, which is useful for debugging.
  `run()` raises instead of returning, so without your own catalog there is
  nothing to inspect.

Concretely:

```python
from masoora import DataCatalog, PipelineBuilder, PipelineContext, StepExecutionError


class Config(PipelineContext):
    pass


log: list[str] = []


def read_rows(ctx: Config) -> list[int]:
    return [1, 2, 3]


def write_first(ctx: Config, rows: list[int]) -> None:
    log.append("write_first")


def write_second(ctx: Config, rows: list[int]) -> None:
    raise ConnectionError("warehouse unreachable")


pipeline = (
    PipelineBuilder[Config]()
    .with_read_step(read_rows, output="rows")
    .with_write_step(write_first, inputs=["rows"])
    .with_write_step(write_second, inputs=["rows"])
    .build()
)

partial = DataCatalog()
try:
    pipeline.run(Config(), catalog=partial)
except StepExecutionError:
    pass

print(log, list(partial))
```

```text
['write_first'] ['rows']
```

`write_first` happened and stays happened.

## Designing writes for failure

Since a failed run can leave earlier writes in place, and an orchestrator may
re-run the whole thing, design writes so that re-running is safe.

### Make writes idempotent

A write is idempotent when running it twice leaves the same state as running
it once. Prefer:

- **Overwrite a partition keyed by the run** — `orders/run_date=2026-01-31/` —
  rather than appending to a shared table. A re-run replaces the partition.
- **Upsert on a key** (`MERGE`, `INSERT ... ON CONFLICT DO UPDATE`) rather than
  a bare insert.
- **Delete-then-insert inside one transaction**, scoped to the run's key, when
  the store has transactions.
- **Write to a temporary name, then rename.** A reader never sees a
  half-written file; a crash leaves only a stray temp file.

Avoid blind appends, and anything that derives a name from the current time.
Take the date from the [context](context.md) — `ctx.run_date` — so a re-run
targets the same place.

### Write the completion marker last

Downstream consumers need to know a run's output is complete. A file existing
does not tell them: it may be the first of three. Write an explicit *completion
marker* — a `_SUCCESS` file, a row in a `runs` table, a manifest — as the very
last thing the pipeline does, so that **the marker's presence means every
earlier write finished**. Consumers wait for the marker, not the data.

Write steps have no output, so no other step can depend on one: masoora cannot
order a *separate* marker step after the data writes. There are two reliable
ways to get "last":

1. Write the marker at the end of the **same write step**, after the other
   writes, so the order is plain code:

    ```python
    def write_results(ctx: Config, accepted: Rows, rejected: Rows) -> None:
        store.write(f"accepted_{ctx.run_date}", accepted)
        store.write(f"rejected_{ctx.run_date}", rejected)
        store.write(f"_done_{ctx.run_date}", [])  # last: its presence means "complete"
    ```

2. Write the marker **after `run()` returns**. `run()` only returns normally if
   every step succeeded, so reaching the next line is the proof:

    ```python
    pipeline.run(ctx)
    store.write(f"_done_{ctx.run_date}", [])
    ```

Two write steps that share no dependency may run in either order in parallel
mode, and in sequential mode their order is an implementation detail (see
[Step order](pipelines.md#step-order)). Do not rely on it.

Combine this with idempotent writes: a failed run leaves no marker, so
consumers ignore it, and the re-run overwrites the partial output and then
writes the marker.

## Retries

masoora has no retry mechanism. Retry at the level that can do it safely:

- **The whole run**, by the orchestrator or job runner, which is why writes
  must be idempotent.
- **Inside a single step**, around one flaky call — a library such as
  [tenacity](https://tenacity.readthedocs.io/), or a plain loop — when the call
  is safe to repeat. An exception only becomes a `StepExecutionError` once
  your step has given up.
