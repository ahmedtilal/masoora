"""Pipeline: an ordered, executable sequence of steps."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from masoora.catalog import DataCatalog
from masoora.errors import StepExecutionError
from masoora.graph import ancestors_of_target
from masoora.steps import ReadStep, Step, WriteStep
from masoora.testing import TestRunResult

if TYPE_CHECKING:
    from masoora.context import PipelineContext

ContextT = TypeVar("ContextT", bound="PipelineContext")


def _execute_steps(
    steps: Sequence[Step[ContextT]], context: ContextT, catalog: DataCatalog
) -> None:
    for index, step in enumerate(steps):
        try:
            step.execute(context, catalog)
        except Exception as exc:
            raise StepExecutionError(index, step.name, exc) from exc


class Pipeline(Generic[ContextT]):
    """A topo-sorted sequence of steps. Built via PipelineBuilder."""

    def __init__(self, steps: Sequence[Step[ContextT]]) -> None:
        self._steps: tuple[Step[ContextT], ...] = tuple(steps)

    @property
    def steps(self) -> tuple[Step[ContextT], ...]:
        return self._steps

    def run(
        self,
        context: ContextT,
        catalog: DataCatalog | None = None,
        target: str | None = None,
    ) -> DataCatalog:
        """Execute all steps (or only those needed for `target`) in topo order."""
        steps = self._select(target)
        cat = catalog if catalog is not None else DataCatalog()
        _execute_steps(steps, context, cat)
        return cat

    def to_testable(
        self,
        reads: Mapping[str, Any] | None = None,
        *,
        mock_writes: bool = True,
        target: str | None = None,
    ) -> TestablePipeline[ContextT]:
        """Return a copy with read steps replaced by fixture data and,
        optionally, write steps captured instead of executed."""
        read_fixtures = dict(reads) if reads else {}
        mocked: list[Step[ContextT]] = []
        for step in self._select(target):
            if isinstance(step, ReadStep) and step.output in read_fixtures:
                value = read_fixtures[step.output]

                def constant_read(_ctx: ContextT, v: Any = value) -> Any:
                    return v

                mocked.append(ReadStep(fn=constant_read, output=step.output))
            elif isinstance(step, WriteStep) and mock_writes:
                mocked.append(step)  # capture happens in TestablePipeline.run
            else:
                mocked.append(step)
        return TestablePipeline(steps=mocked, mock_writes=mock_writes)

    def _select(self, target: str | None) -> list[Step[ContextT]]:
        if target is None:
            return list(self._steps)
        return ancestors_of_target(list(self._steps), target)


class TestablePipeline(Generic[ContextT]):
    """A pipeline with mocked reads/writes; run() returns a TestRunResult."""

    def __init__(self, steps: Sequence[Step[ContextT]], *, mock_writes: bool) -> None:
        self._steps: tuple[Step[ContextT], ...] = tuple(steps)
        self._mock_writes = mock_writes

    def run(self, context: ContextT, catalog: DataCatalog | None = None) -> TestRunResult[ContextT]:
        cat = catalog if catalog is not None else DataCatalog()
        written: dict[str, Any] = {}
        steps: list[Step[ContextT]] = []
        for step in self._steps:
            if isinstance(step, WriteStep) and self._mock_writes:
                keys = step.inputs

                def capture(_ctx: ContextT, *datasets: Any, keys: tuple[str, ...] = keys) -> None:
                    written.update(dict(zip(keys, datasets, strict=True)))

                steps.append(WriteStep(fn=capture, inputs=step.inputs))
            else:
                steps.append(step)
        _execute_steps(steps, context, cat)
        return TestRunResult(catalog=cat, written=written)
