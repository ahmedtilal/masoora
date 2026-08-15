"""Dependency graph resolution for pipeline steps.

Steps are nodes; catalog keys are edges: a step depends on the step that
produces each of its input keys. Keys not produced by any step are seeds
(pre-populated catalog entries) and create no edges.
"""

from __future__ import annotations

import heapq
from typing import TYPE_CHECKING, TypeVar

from masoora.errors import PipelineCycleError, PipelineValidationError

if TYPE_CHECKING:
    from masoora.context import PipelineContext
    from masoora.steps import Step

ContextT = TypeVar("ContextT", bound="PipelineContext")


def _dependencies(steps: list[Step[ContextT]]) -> list[set[int]]:
    """deps[i] = indices of steps that must run before steps[i]."""
    producer: dict[str, int] = {}
    for idx, step in enumerate(steps):
        for key in step.outputs:
            producer[key] = idx
    deps: list[set[int]] = [set() for _ in steps]
    for idx, step in enumerate(steps):
        for key in step.inputs:
            if key in producer:
                deps[idx].add(producer[key])
    return deps


def topo_sort(steps: list[Step[ContextT]]) -> list[Step[ContextT]]:
    """Kahn's algorithm; declaration order breaks ties (deterministic)."""
    steps = list(steps)
    deps = _dependencies(steps)
    dependents: list[list[int]] = [[] for _ in steps]
    indegree = [0] * len(steps)
    for idx, dep_set in enumerate(deps):
        indegree[idx] = len(dep_set)
        for dep in dep_set:
            dependents[dep].append(idx)

    heap = [idx for idx in range(len(steps)) if indegree[idx] == 0]
    heapq.heapify(heap)
    order: list[Step[ContextT]] = []
    while heap:
        idx = heapq.heappop(heap)
        order.append(steps[idx])
        for dependent in dependents[idx]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                heapq.heappush(heap, dependent)

    if len(order) != len(steps):
        raise PipelineCycleError(_find_cycle(steps, deps))
    return order


def _find_cycle(steps: list[Step[ContextT]], deps: list[set[int]]) -> list[str]:
    """Extract one cycle (as step names) from the unresolved subgraph."""
    unresolved = {idx for idx, dep_set in enumerate(deps) if dep_set}
    # Follow unresolved predecessors until we revisit a node.
    path: list[int] = []
    current = next(iter(unresolved))
    seen: dict[int, int] = {}
    while current not in seen:
        seen[current] = len(path)
        path.append(current)
        current = next(idx for idx in deps[current] if idx in unresolved)
    cycle = path[seen[current] :]
    names = [steps[idx].name for idx in cycle]
    return [*names, steps[current].name]


def ancestors_of_target(steps: list[Step[ContextT]], target: str) -> list[Step[ContextT]]:
    """Return the topo-ordered subset of steps needed to produce `target`.

    `steps` must already be topo-sorted. Raises if no step produces `target`.
    """
    steps = list(steps)
    deps = _dependencies(steps)
    producer: dict[str, int] = {}
    for idx, step in enumerate(steps):
        for key in step.outputs:
            producer[key] = idx
    if target not in producer:
        available = sorted(producer)
        raise PipelineValidationError(
            f"Target {target!r} is not produced by any step. Available: {available}"
        )

    needed: set[int] = set()
    stack = [producer[target]]
    while stack:
        idx = stack.pop()
        if idx in needed:
            continue
        needed.add(idx)
        stack.extend(deps[idx])
    return [step for idx, step in enumerate(steps) if idx in needed]
