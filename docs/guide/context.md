# Context and dependency injection

Every step receives a context as its first argument. Steps also need things
that are not configuration: an HTTP client, a database connection, a storage
backend. This page covers where each belongs.

The short version:

- **Configuration** — dates, thresholds, URLs, paths — goes in the context.
- **Clients and stores** — anything you want to swap in tests — are passed to a
  factory function that builds the pipeline, and the steps close over them.

## What the context is

[`PipelineContext`][masoora.PipelineContext] is a Pydantic `BaseModel`
configured with `arbitrary_types_allowed=True`. That setting means a field may
be annotated with any class, not only types Pydantic knows how to validate.
For such a field Pydantic does an `isinstance` check and nothing else.

So both of these work.

## Pattern A: put the client in the context

```python
from masoora import PipelineBuilder, PipelineContext


class Client:
    def fetch(self) -> list[int]:
        return [1, 2, 3]


class ClientContext(PipelineContext):
    client: Client  # accepted because arbitrary_types_allowed=True
    threshold: int = 1


def read_numbers(ctx: ClientContext) -> list[int]:
    return ctx.client.fetch()


pipeline = PipelineBuilder[ClientContext]().with_read_step(read_numbers, output="numbers").build()
catalog = pipeline.run(ClientContext(client=Client()))
assert catalog["numbers"] == [1, 2, 3]
```

This is the least ceremony, and it is fine for a script with one backend.
Its costs show up later:

- The context stops being plain data. You cannot print it, serialise it, or
  build it from an orchestrator's parameters without also constructing the
  client.
- Every step that takes the context can reach every client, so a step's real
  dependencies are no longer visible from its signature.
- Swapping the client for a fake means constructing a different context for
  every test.

## Pattern B: inject through a factory (recommended)

Keep the context to validated configuration, and pass clients to a function
that returns the pipeline. The step functions are defined inside it, so they
close over what they need:

```python
from masoora import Pipeline, PipelineBuilder, PipelineContext


class Client:
    def fetch(self) -> list[int]:
        return [1, 2, 3]


class Config(PipelineContext):
    threshold: int = 1


def build_pipeline(client: Client) -> Pipeline[Config]:
    def read_numbers(ctx: Config) -> list[int]:
        return client.fetch()

    def keep_large(ctx: Config, numbers: list[int]) -> list[int]:
        return [n for n in numbers if n > ctx.threshold]

    return (
        PipelineBuilder[Config]()
        .with_read_step(read_numbers, output="numbers")
        .with_transform_step(keep_large, inputs=["numbers"], output="large")
        .build()
    )


catalog = build_pipeline(Client()).run(Config(threshold=1))
assert catalog["large"] == [2, 3]
```

In a test, hand the factory a fake:

```python
class FakeClient(Client):
    def fetch(self) -> list[int]:
        return [10, 20]


catalog = build_pipeline(FakeClient()).run(Config(threshold=15))
assert catalog["large"] == [20]
```

**Use Pattern B for anything you want to swap**, which in practice means every
piece of IO. The reasons:

- **The context stays data.** It validates at the boundary, prints cleanly,
  and is exactly what an orchestrator or CLI hands over. See
  [Orchestrators](orchestrators.md).
- **Swapping is one argument.** Production passes the real store, tests pass a
  fake, and the pipeline definition is identical in both.
- **Dependencies are explicit.** What the pipeline touches is the factory's
  signature, not whatever happens to be on the context.
- **Step names stay clean.** Closures defined with `def` keep their
  `__name__`, which is what shows up in errors and diagrams — see
  [Step names](pipelines.md#step-names).

!!! tip "Pattern B still works with `reads=`"

    [`to_testable(reads=...)`][masoora.Pipeline.to_testable] replaces read
    steps whatever they close over, so you can combine both: use a fake store
    where you want real transform and write code to run, and `reads=` where you
    only want to feed data in. See [Testing](testing.md).

For a complete, runnable version with a `Protocol`, a local implementation, and
a fake, see [Example: a pipeline with swappable storage](../examples/swappable-storage.md).

## What belongs in the context

Put a value in the context when it is **configuration**: plain, validated,
and something a caller could reasonably pass on a command line or in a job
parameter.

```python
from pydantic import Field

from masoora import PipelineContext


class DailyContext(PipelineContext):
    run_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    min_amount: float = Field(default=1.0, ge=0)
```

Everything Pydantic offers works here — constraints, defaults, validators —
and a bad value fails at construction, before any step runs.

Put a value in a factory argument when it is a **collaborator**: something with
behaviour that talks to the outside world.

## Treat the context as read-only

Steps must not assign to the context or mutate objects reachable from it. The
rule matters in two ways:

- **Parallel runs.** Steps running on different threads share one context
  instance. A step that changes it can change what a concurrently running step
  sees. See [Parallel execution](parallel.md).
- **Readability.** Data flows between steps through the catalog. If a step
  also communicates through the context, the diagram no longer shows the
  pipeline's real dependencies.

masoora does not enforce this. If you want it enforced, make the context
immutable:

```python
from pydantic import ConfigDict

from masoora import PipelineContext


class FrozenContext(PipelineContext):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    run_date: str
```

Subclasses of `PipelineContext` inherit its `model_config` and merge their own
into it, so `arbitrary_types_allowed=True` is kept even if you only set
`frozen`; repeating it above is harmless and makes the intent obvious.

Frozen stops attribute assignment. It cannot stop a step mutating a list or
dict stored in a field, so keep mutable values out of the context.
