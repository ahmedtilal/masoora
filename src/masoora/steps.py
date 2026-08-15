"""Pipeline steps: read, transform, write."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from masoora.catalog import DataCatalog
    from masoora.context import PipelineContext

ContextT = TypeVar("ContextT", bound="PipelineContext")


@dataclass(frozen=True)
class ReadStep(Generic[ContextT]):
    """fn(context) -> dataset, stored at catalog[output]."""

    fn: Callable[[ContextT], Any]
    output: str
    inputs: tuple[str, ...] = field(default_factory=tuple, init=False)

    @property
    def name(self) -> str:
        return getattr(self.fn, "__name__", repr(self.fn))

    @property
    def outputs(self) -> tuple[str, ...]:
        return (self.output,)

    def execute(self, context: ContextT, catalog: DataCatalog) -> None:
        catalog[self.output] = self.fn(context)


@dataclass(frozen=True)
class TransformStep(Generic[ContextT]):
    """fn(context, *inputs) -> dataset, stored at catalog[output]."""

    fn: Callable[..., Any]
    inputs: tuple[str, ...]
    output: str

    def __init__(self, fn: Callable[..., Any], inputs: Sequence[str], output: str) -> None:
        object.__setattr__(self, "fn", fn)
        object.__setattr__(self, "inputs", tuple(inputs))
        object.__setattr__(self, "output", output)

    @property
    def name(self) -> str:
        return getattr(self.fn, "__name__", repr(self.fn))

    @property
    def outputs(self) -> tuple[str, ...]:
        return (self.output,)

    def execute(self, context: ContextT, catalog: DataCatalog) -> None:
        catalog[self.output] = self.fn(context, *(catalog[key] for key in self.inputs))


@dataclass(frozen=True)
class WriteStep(Generic[ContextT]):
    """fn(context, *inputs) -> None; produces no catalog output."""

    fn: Callable[..., None]
    inputs: tuple[str, ...]

    def __init__(self, fn: Callable[..., None], inputs: Sequence[str]) -> None:
        object.__setattr__(self, "fn", fn)
        object.__setattr__(self, "inputs", tuple(inputs))

    @property
    def name(self) -> str:
        return getattr(self.fn, "__name__", repr(self.fn))

    @property
    def outputs(self) -> tuple[str, ...]:
        return ()

    def execute(self, context: ContextT, catalog: DataCatalog) -> None:
        self.fn(context, *(catalog[key] for key in self.inputs))


Step = ReadStep[ContextT] | TransformStep[ContextT] | WriteStep[ContextT]
