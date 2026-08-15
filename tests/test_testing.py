from conftest import Ctx

from masoora import PipelineBuilder, TestRunResult, make_pipeline_fixture


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
