"""Mermaid rendering of a pipeline."""

from __future__ import annotations

from typing import Any

import pytest

from masoora import PipelineBuilder, PipelineContext


class Ctx(PipelineContext):
    pass


def read_events(_c: Ctx) -> list[int]:
    return [1, 2]


def score(_c: Ctx, events: list[int]) -> list[int]:
    return events


def write_db(_c: Ctx, scored: list[int]) -> None:
    pass


def _pipeline() -> Any:
    return (
        PipelineBuilder[Ctx]()
        .with_read_step(read_events, output="events")
        .with_transform_step(score, inputs=["events"], output="scored")
        .with_write_step(write_db, inputs=["scored"])
        .build()
    )


def test_renders_steps_and_edges() -> None:
    diagram = _pipeline().to_mermaid()
    assert diagram.startswith("flowchart TD")
    assert '["read_events"]:::read' in diagram
    assert '["score"]:::transform' in diagram
    assert '["write_db"]:::write' in diagram
    assert '-->|"events"|' in diagram
    assert '-->|"scored"|' in diagram


def test_seeds_get_their_own_node() -> None:
    diagram = (
        PipelineBuilder[Ctx]()
        .with_seed("raw")
        .with_transform_step(score, inputs=["raw"], output="scored")
        .build()
        .to_mermaid()
    )
    assert '(["raw"]):::data' in diagram
    assert "seed0 --> n0" in diagram


def test_unconsumed_output_gets_its_own_node() -> None:
    """The pipeline's result is worth showing, not just its steps."""
    diagram = (
        PipelineBuilder[Ctx]()
        .with_read_step(read_events, output="events")
        .with_transform_step(score, inputs=["events"], output="scored")
        .build()
        .to_mermaid()
    )
    assert '(["scored"]):::data' in diagram
    assert "n1 --> out0" in diagram


def test_intermediate_keys_stay_edge_labels() -> None:
    """'events' is consumed, so it labels an edge rather than adding a node."""
    diagram = _pipeline().to_mermaid()
    assert '(["events"]):::data' not in diagram


def test_target_narrows_the_diagram() -> None:
    diagram = _pipeline().to_mermaid(target="scored")
    assert "read_events" in diagram
    assert "write_db" not in diagram


def test_direction_is_configurable() -> None:
    assert _pipeline().to_mermaid(direction="LR").startswith("flowchart LR")


def test_invalid_direction_rejected() -> None:
    with pytest.raises(ValueError, match="direction must be one of"):
        _pipeline().to_mermaid(direction="sideways")


def test_lambda_names_are_escaped() -> None:
    """Step names come from __name__, so '<lambda>' is routine."""
    diagram = (
        PipelineBuilder[Ctx]().with_read_step(lambda _c: [1], output="events").build().to_mermaid()
    )
    assert "<lambda>" not in diagram
    assert "#lt;lambda#gt;" in diagram


def test_duplicate_step_names_stay_distinct() -> None:
    """Two lambdas share a name; index-based ids keep the nodes separate."""
    diagram = (
        PipelineBuilder[Ctx]()
        .with_read_step(lambda _c: [1], output="a")
        .with_read_step(lambda _c: [2], output="b")
        .with_transform_step(lambda _c, x, y: x + y, inputs=["a", "b"], output="c")
        .build()
        .to_mermaid()
    )
    assert "n0[" in diagram
    assert "n1[" in diagram
    assert "n2[" in diagram


def test_output_is_deterministic() -> None:
    """Docs commit these diagrams, so the same pipeline must render identically."""
    assert _pipeline().to_mermaid() == _pipeline().to_mermaid()
