"""Render a pipeline as a Mermaid flowchart.

Steps are nodes and catalog keys are edge labels. Keys at the pipeline's
boundaries get their own nodes: seeds, which nothing produces, and outputs,
which nothing consumes. That keeps the middle compact while still showing what
goes in and what comes out.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, TypeVar

from masoora.steps import ReadStep, TransformStep, WriteStep

if TYPE_CHECKING:
    from masoora.context import PipelineContext
    from masoora.steps import Step

ContextT = TypeVar("ContextT", bound="PipelineContext")

DIRECTIONS = frozenset({"TB", "TD", "BT", "LR", "RL"})

_STYLES = (
    "    classDef read fill:#dbeafe,stroke:#2563eb,color:#0b2a5b;",
    "    classDef transform fill:#e5e7eb,stroke:#4b5563,color:#111827;",
    "    classDef write fill:#dcfce7,stroke:#16a34a,color:#052e16;",
    "    classDef data fill:#fef3c7,stroke:#d97706,color:#451a03;",
)


def _escape(text: str) -> str:
    """Neutralise characters Mermaid treats as markup.

    Step names are function names, so `<lambda>` turns up routinely.
    """
    return text.replace('"', "#quot;").replace("<", "#lt;").replace(">", "#gt;")


def _kind(step: Step[ContextT]) -> str:
    if isinstance(step, ReadStep):
        return "read"
    if isinstance(step, WriteStep):
        return "write"
    if isinstance(step, TransformStep):
        return "transform"
    return "transform"  # pragma: no cover - Step is a closed union


def to_mermaid(steps: Sequence[Step[ContextT]], *, direction: str = "TD") -> str:
    """Return a Mermaid `flowchart` definition for `steps`."""
    if direction not in DIRECTIONS:
        raise ValueError(f"direction must be one of {sorted(DIRECTIONS)}, got {direction!r}")

    steps = list(steps)
    producer: dict[str, int] = {}
    for idx, step in enumerate(steps):
        for key in step.outputs:
            producer[key] = idx
    consumed = {key for step in steps for key in step.inputs}

    lines = [f"flowchart {direction}"]
    for idx, step in enumerate(steps):
        lines.append(f'    n{idx}["{_escape(step.name)}"]:::{_kind(step)}')

    seeds = sorted({key for step in steps for key in step.inputs if key not in producer})
    seed_ids = {key: f"seed{i}" for i, key in enumerate(seeds)}
    for key, node in seed_ids.items():
        lines.append(f'    {node}(["{_escape(key)}"]):::data')

    outputs = sorted({key for step in steps for key in step.outputs if key not in consumed})
    output_ids = {key: f"out{i}" for i, key in enumerate(outputs)}
    for key, node in output_ids.items():
        lines.append(f'    {node}(["{_escape(key)}"]):::data')

    for idx, step in enumerate(steps):
        for key in step.inputs:
            if key in producer:
                lines.append(f'    n{producer[key]} -->|"{_escape(key)}"| n{idx}')
            else:
                lines.append(f"    {seed_ids[key]} --> n{idx}")
        for key in step.outputs:
            if key in output_ids:
                lines.append(f"    n{idx} --> {output_ids[key]}")

    lines.extend(_STYLES)
    return "\n".join(lines)
