"""Testing helpers: run pipelines with mocked reads/writes under pytest."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from masoora.catalog import DataCatalog
    from masoora.context import PipelineContext
    from masoora.pipeline import Pipeline

ContextT = TypeVar("ContextT", bound="PipelineContext")


@dataclass
class TestRunResult(Generic[ContextT]):
    """Result of running a TestablePipeline.

    catalog: full data catalog after the run (assert on any key).
    written: input key -> dataset for every mocked write step.
    """

    catalog: DataCatalog
    written: dict[str, Any] = field(default_factory=dict)

    __test__ = False  # not a pytest test class


def make_pipeline_fixture(
    pipeline: Pipeline[ContextT],
    context: ContextT | Callable[[], ContextT],
    reads: Mapping[str, Any] | None = None,
    *,
    mock_writes: bool = True,
    target: str | None = None,
) -> Callable[[], TestRunResult[ContextT]]:
    """Create a pytest fixture that runs the pipeline with mocked IO.

    Usage:
        run_pipeline = make_pipeline_fixture(
            my_pipeline, MyContext(url="test"), reads={"raw": fake_df}
        )

        def test_output(run_pipeline: TestRunResult[MyContext]) -> None:
            assert "clean" in run_pipeline.catalog
    """
    try:
        import pytest
    except ImportError as exc:  # pragma: no cover
        raise ImportError("make_pipeline_fixture requires pytest; install masoora[pytest]") from exc

    @pytest.fixture
    def _fixture() -> TestRunResult[ContextT]:
        ctx = context() if callable(context) else context
        return pipeline.to_testable(reads=reads, mock_writes=mock_writes, target=target).run(ctx)

    return _fixture
