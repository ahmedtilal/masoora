from collections.abc import Callable
from typing import Literal

import pytest
from conftest import Ctx

from masoora import Pipeline, PipelineBuilder, TestRunResult, make_pipeline_fixture


def read_source(ctx: Ctx) -> list[int]:
    raise RuntimeError("must be mocked in tests")


def double_all(ctx: Ctx, rows: list[int]) -> list[int]:
    return [r * 2 for r in rows]


def keep_big(ctx: Ctx, rows: list[int]) -> list[int]:
    return [r for r in rows if r > ctx.n]


def write_sink(ctx: Ctx, rows: list[int]) -> None:
    raise RuntimeError("must be mocked in tests")


pipeline = (
    PipelineBuilder[Ctx]()
    .with_read_step(read_source, output="raw")
    .with_transform_step(double_all, inputs=["raw"], output="doubled")
    .with_transform_step(keep_big, inputs=["doubled"], output="filtered")
    .with_write_step(write_sink, inputs=["filtered"])
    .build()
)

run_pipeline = make_pipeline_fixture(
    pipeline,
    Ctx(n=3),
    reads={"raw": [1, 2, 3]},
)


def test_fixture_mocks_reads_and_writes(run_pipeline: TestRunResult[Ctx]) -> None:
    assert run_pipeline.catalog["raw"] == [1, 2, 3]
    assert run_pipeline.catalog["doubled"] == [2, 4, 6]
    assert run_pipeline.catalog["filtered"] == [4, 6]
    assert run_pipeline.written["filtered"] == [4, 6]


def scope_probe() -> tuple[Pipeline[Ctx], Callable[[], Ctx], list[str]]:
    calls: list[str] = []

    def context_factory() -> Ctx:
        calls.append("context")
        return Ctx(n=3)

    def read(ctx: Ctx) -> int:
        calls.append("read")
        return ctx.n

    pipeline = PipelineBuilder[Ctx]().with_read_step(read, output="raw").build()
    return pipeline, context_factory, calls


def module_scope(fixture_name: str, config: pytest.Config) -> Literal["module"]:
    return "module"


default_pipeline, default_context, default_calls = scope_probe()
module_pipeline, module_context, module_calls = scope_probe()
dynamic_pipeline, dynamic_context, dynamic_calls = scope_probe()

default_run = make_pipeline_fixture(default_pipeline, default_context)
module_run = make_pipeline_fixture(module_pipeline, module_context, scope="module")
dynamic_run = make_pipeline_fixture(dynamic_pipeline, dynamic_context, scope=module_scope)


@pytest.mark.parametrize("fixture_name", ["default_run", "module_run", "dynamic_run"])
@pytest.mark.parametrize("_case", [1, 2])
def test_pipeline_fixture_scope(
    fixture_name: str, _case: int, request: pytest.FixtureRequest
) -> None:
    default_calls_before = len(default_calls)
    result = request.getfixturevalue(fixture_name)

    assert result.catalog["raw"] == 3
    if fixture_name == "default_run":
        assert default_calls[default_calls_before:] == ["context", "read"]
    elif fixture_name == "module_run":
        assert module_calls == ["context", "read"]
    else:
        assert dynamic_calls == ["context", "read"]


def test_to_testable_directly() -> None:
    result = pipeline.to_testable(reads={"raw": [10]}).run(Ctx(n=100))
    assert result.catalog["doubled"] == [20]
    assert result.catalog["filtered"] == []
    assert result.written["filtered"] == []


def test_mock_writes_false_calls_real_writer() -> None:
    calls: list[list[int]] = []
    p = (
        PipelineBuilder[Ctx]()
        .with_read_step(lambda ctx: [5], output="raw")
        .with_write_step(lambda ctx, rows: calls.append(rows), inputs=["raw"])
        .build()
    )
    result = p.to_testable(mock_writes=False).run(Ctx(n=1))
    assert calls == [[5]]
    assert result.written == {}


def test_target_with_testable() -> None:
    result = pipeline.to_testable(reads={"raw": [10, 20]}, target="doubled").run(Ctx(n=1))
    assert result.catalog["doubled"] == [20, 40]
    assert "filtered" not in result.catalog
    assert result.written == {}
