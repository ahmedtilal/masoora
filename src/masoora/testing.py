"""Testing helpers: run pipelines with mocked reads/writes under pytest."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeVar

if TYPE_CHECKING:
    from pytest import Config

    from masoora.catalog import DataCatalog
    from masoora.context import PipelineContext
    from masoora.pipeline import Pipeline

ContextT = TypeVar("ContextT", bound="PipelineContext")
_FixtureScope = Literal["function", "class", "module", "package", "session"]


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
    scope: _FixtureScope | Callable[[str, Config], _FixtureScope] = "function",
) -> Callable[[], TestRunResult[ContextT]]:
    """Create a pytest fixture that runs the pipeline with mocked IO.

    Pytest controls the fixture lifetime through ``scope``, which defaults to
    ``"function"``. A scope callable receives ``fixture_name`` and ``config`` as
    keyword arguments. A context factory is called once per fixture instance.
    Tests sharing a result must treat its datasets as read-only.

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

    @pytest.fixture(scope=scope)
    def _fixture() -> TestRunResult[ContextT]:
        ctx = context() if callable(context) else context
        return pipeline.to_testable(reads=reads, mock_writes=mock_writes, target=target).run(ctx)

    return _fixture
