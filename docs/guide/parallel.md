# Parallel execution

Pipelines run sequentially by default. Pass `parallel` to run independent
steps concurrently:

```python
pipeline.run(ctx, parallel=True)  # thread pool, os.cpu_count() workers
pipeline.run(ctx, parallel=4)  # explicit worker count
pipeline.run(ctx, executor=pool)  # your own Executor
```

An executor you supply is **not** shut down by masoora — its lifetime stays
yours.

## Dependency-driven scheduling

Steps run in a `ThreadPoolExecutor`, and each step starts the instant its own
dependencies finish.

There is no level barrier. That distinction matters more than it sounds: a
level-synchronised scheduler runs the DAG in waves and every step in wave *N+1*
waits for the slowest step in wave *N*, so one slow branch stalls unrelated
work. masoora tracks dependencies per step, so a ready branch never waits on an
unrelated slow one.

## Failure behaviour

Execution is fail-fast. The first step to raise:

1. cancels work that is queued but not yet started,
2. raises [`StepExecutionError`][masoora.StepExecutionError] immediately.

Steps already running are **not** interrupted — Python cannot safely kill a
running thread — so they finish in the background. Keep this in mind if your
steps have side effects: a write that was already in flight when a sibling
failed will still complete.

## The contract

Parallel results are identical to sequential results **provided each step**:

- reads only the input keys it declared,
- writes only its own output key,
- treats the context as read-only.

!!! warning "These rules are not enforced"

    masoora cannot see inside your step functions. A step that reaches into an
    undeclared catalog key, or mutates the context, may work sequentially and
    then fail intermittently under `parallel=True`. If a pipeline behaves
    differently with and without `parallel`, a violated contract is the first
    thing to check.

## Threads, not processes

The executor is a thread pool, so this parallelism helps when steps are
**I/O-bound** — reading from object storage, querying a warehouse, calling an
API. CPU-bound pure-Python transforms contend on the GIL and will not speed up.

In practice this fits ETL well: the slow parts are usually the network, and
libraries like polars, pandas, and pyarrow release the GIL during their heavy
work anyway.
