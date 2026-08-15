"""Pipeline: an ordered, executable sequence of steps."""

from __future__ import annotations

import os
from collections import deque
from collections.abc import Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, Executor, Future, ThreadPoolExecutor, wait
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from masoora.catalog import DataCatalog
from masoora.errors import StepExecutionError
from masoora.graph import ancestors_of_target, dependency_edges
from masoora.steps import ReadStep, Step, WriteStep
from masoora.testing import TestRunResult
from masoora.validation import Validator

if TYPE_CHECKING:
    from masoora.context import PipelineContext

ContextT = TypeVar("ContextT", bound="PipelineContext")

#: parallel=False -> sequential; True -> os.cpu_count() workers; int -> N workers
ParallelMode = bool | int


def _execute_steps(
    steps: Sequence[Step[ContextT]], context: ContextT, catalog: DataCatalog
) -> None:
    for index, step in enumerate(steps):
        try:
            step.execute(context, catalog)
        except Exception as exc:
            raise StepExecutionError(index, step.name, exc) from exc


def _execute_parallel(
    steps: Sequence[Step[ContextT]],
    context: ContextT,
    catalog: DataCatalog,
    parallel: ParallelMode,
    executor: Executor | None,
) -> None:
    """Dependency-driven scheduling; fail-fast on the first error.

    Each step is submitted the instant its own dependencies complete (no
    level barrier). Correct under the masoora step contract: steps only read
    declared input keys and write their own output key, and treat context as
    read-only.
    """
    steps = list(steps)
    n = len(steps)
    deps, dependents = dependency_edges(steps)
    remaining = [len(dep_set) for dep_set in deps]
    ready: deque[int] = deque(idx for idx in range(n) if remaining[idx] == 0)
    futures: dict[Future[None], int] = {}
    completed = 0

    pool: Executor
    if executor is not None:
        pool = executor
        owns_pool = False
    else:
        workers = None
        if parallel is True:
            workers = os.cpu_count()
        elif isinstance(parallel, int) and parallel > 0:
            workers = parallel
        pool = ThreadPoolExecutor(max_workers=workers)
        owns_pool = True

    error: tuple[int, str, BaseException] | None = None
    try:
        while completed < n:
            while ready and error is None:
                idx = ready.popleft()
                futures[pool.submit(steps[idx].execute, context, catalog)] = idx
            if not futures:
                break
            finished, _ = wait(set(futures), return_when=FIRST_COMPLETED)
            for future in finished:
                idx = futures.pop(future)
                completed += 1
                exc = future.exception()
                if exc is not None:
                    if error is None:
                        error = (idx, steps[idx].name, exc)
                elif error is None:
                    for nxt in dependents[idx]:
                        remaining[nxt] -= 1
                        if remaining[nxt] == 0:
                            ready.append(nxt)
            if error is not None:
                for future in futures:
                    future.cancel()
                break
    finally:
        if owns_pool:
            # On failure return promptly: cancel queued work, don't wait for
            # running steps (they only touch their own catalog keys).
            pool.shutdown(wait=error is None, cancel_futures=error is not None)

    if error is not None:
        index, name, exc = error
        if isinstance(exc, Exception):
            raise StepExecutionError(index, name, exc) from exc
        raise exc  # KeyboardInterrupt & co. propagate unwrapped


def _dispatch(
    steps: Sequence[Step[ContextT]],
    context: ContextT,
    catalog: DataCatalog,
    parallel: ParallelMode,
    executor: Executor | None,
) -> None:
    if executor is None and not parallel:
        _execute_steps(steps, context, catalog)
    else:
        _execute_parallel(steps, context, catalog, parallel, executor)


class Pipeline(Generic[ContextT]):
    """A topo-sorted sequence of steps. Built via PipelineBuilder."""

    def __init__(
        self,
        steps: Sequence[Step[ContextT]],
        validators: Mapping[str, Validator] | None = None,
    ) -> None:
        self._steps: tuple[Step[ContextT], ...] = tuple(steps)
        self._validators: dict[str, Validator] = dict(validators) if validators else {}

    @property
    def steps(self) -> tuple[Step[ContextT], ...]:
        return self._steps

    @property
    def validators(self) -> Mapping[str, Validator]:
        """Catalog key -> validator, as declared on the builder."""
        return dict(self._validators)

    def run(
        self,
        context: ContextT,
        catalog: DataCatalog | None = None,
        target: str | None = None,
        parallel: ParallelMode = False,
        executor: Executor | None = None,
    ) -> DataCatalog:
        """Execute all steps (or only those needed for `target`) in topo order.

        parallel: False (default) runs sequentially; True uses a thread pool
        with os.cpu_count() workers; an int sets the worker count. Steps run
        concurrently, each starting the instant its own dependencies finish
        (dependency-driven scheduling, no level barrier).
        executor: caller-provided Executor; wins over `parallel` and is NOT
        shut down by the pipeline.
        """
        steps = self._select(target)
        cat = catalog if catalog is not None else DataCatalog()
        # A caller-supplied catalog holds the seeded keys, so it needs the
        # validators too -- that is what gets seeds checked on first read.
        cat.attach_validators(self._validators)
        _dispatch(steps, context, cat, parallel, executor)
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
        return TestablePipeline(steps=mocked, mock_writes=mock_writes, validators=self._validators)

    def _select(self, target: str | None) -> list[Step[ContextT]]:
        if target is None:
            return list(self._steps)
        return ancestors_of_target(list(self._steps), target)


class TestablePipeline(Generic[ContextT]):
    """A pipeline with mocked reads/writes; run() returns a TestRunResult."""

    def __init__(
        self,
        steps: Sequence[Step[ContextT]],
        *,
        mock_writes: bool,
        validators: Mapping[str, Validator] | None = None,
    ) -> None:
        self._steps: tuple[Step[ContextT], ...] = tuple(steps)
        self._mock_writes = mock_writes
        self._validators: dict[str, Validator] = dict(validators) if validators else {}

    def run(
        self,
        context: ContextT,
        catalog: DataCatalog | None = None,
        parallel: ParallelMode = False,
        executor: Executor | None = None,
    ) -> TestRunResult[ContextT]:
        cat = catalog if catalog is not None else DataCatalog()
        cat.attach_validators(self._validators)
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
        _dispatch(steps, context, cat, parallel, executor)
        return TestRunResult(catalog=cat, written=written)
