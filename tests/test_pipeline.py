from conftest import Ctx

from masoora import (
    DataCatalog,
    PipelineBuilder,
    PipelineContext,
    PipelineCycleError,
    PipelineValidationError,
    StepExecutionError,
)


def test_linear_chain_runs_in_order() -> None:
    pipeline = (
        PipelineBuilder[Ctx]()
        .with_read_step(lambda ctx: ctx.n, output="raw")
        .with_transform_step(lambda ctx, raw: raw * 2, inputs=["raw"], output="doubled")
        .with_transform_step(
            lambda ctx, raw, doubled: raw + doubled, inputs=["raw", "doubled"], output="total"
        )
        .build()
    )
    catalog = pipeline.run(Ctx(n=3))
    assert catalog.snapshot() == {"raw": 3, "doubled": 6, "total": 9}


def test_out_of_order_declaration_is_topo_sorted() -> None:
    pipeline = (
        PipelineBuilder[Ctx]()
        .with_transform_step(lambda ctx, raw: raw * 2, inputs=["raw"], output="doubled")
        .with_read_step(lambda ctx: ctx.n, output="raw")
        .build()
    )
    catalog = pipeline.run(Ctx(n=4))
    assert catalog["doubled"] == 8


def test_write_step_receives_inputs() -> None:
    received: list[tuple[int, int]] = []

    def writer(ctx: Ctx, a: int, b: int) -> None:
        received.append((a, b))

    pipeline = (
        PipelineBuilder[Ctx]()
        .with_read_step(lambda ctx: 1, output="a")
        .with_read_step(lambda ctx: 2, output="b")
        .with_write_step(writer, inputs=["a", "b"])
        .build()
    )
    pipeline.run(Ctx(n=0))
    assert received == [(1, 2)]


def test_target_prunes_unrelated_steps() -> None:
    calls: list[str] = []

    def read_a(ctx: Ctx) -> int:
        calls.append("read_a")
        return 1

    def read_b(ctx: Ctx) -> int:
        calls.append("read_b")
        return 2

    written: list[int] = []
    pipeline = (
        PipelineBuilder[Ctx]()
        .with_read_step(read_a, output="a")
        .with_read_step(read_b, output="b")
        .with_transform_step(lambda ctx, a: a * 10, inputs=["a"], output="a10")
        .with_write_step(lambda ctx, b: written.append(b), inputs=["b"])
        .build()
    )
    catalog = pipeline.run(Ctx(n=0), target="a10")
    assert catalog["a10"] == 10
    assert calls == ["read_a"]
    assert written == []


def test_target_unknown_key_raises() -> None:
    pipeline = PipelineBuilder[Ctx]().with_read_step(lambda ctx: 1, output="a").build()
    try:
        pipeline.run(Ctx(n=0), target="nope")
    except PipelineValidationError as exc:
        assert "nope" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected PipelineValidationError")


def test_step_failure_is_wrapped_with_step_info() -> None:
    def boom(ctx: Ctx, a: int) -> int:
        raise ValueError("bad data")

    pipeline = (
        PipelineBuilder[Ctx]()
        .with_read_step(lambda ctx: 1, output="a")
        .with_transform_step(boom, inputs=["a"], output="b")
        .build()
    )
    try:
        pipeline.run(Ctx(n=0))
    except StepExecutionError as exc:
        assert exc.step_index == 1
        assert exc.step_name == "boom"
        assert isinstance(exc.original, ValueError)
    else:  # pragma: no cover
        raise AssertionError("expected StepExecutionError")


def test_catalog_can_be_preseeded() -> None:
    pipeline = (
        PipelineBuilder[Ctx]()
        .with_seed("external")
        .with_transform_step(lambda ctx, ext: ext + 1, inputs=["external"], output="next")
        .build()
    )
    catalog = pipeline.run(Ctx(n=0), catalog=DataCatalog({"external": 41}))
    assert catalog["next"] == 42


def test_diamond_dependencies() -> None:
    pipeline = (
        PipelineBuilder[Ctx]()
        .with_transform_step(lambda ctx, x: x + 1, inputs=["x"], output="left")
        .with_read_step(lambda ctx: 1, output="x")
        .with_transform_step(
            lambda ctx, left, right: left * right, inputs=["left", "right"], output="join"
        )
        .with_transform_step(lambda ctx, x: x * 10, inputs=["x"], output="right")
        .build()
    )
    catalog = pipeline.run(Ctx(n=0))
    assert catalog["join"] == 20


def test_cycle_detected_at_build() -> None:
    builder = (
        PipelineBuilder[Ctx]()
        .with_transform_step(lambda ctx, b: b, inputs=["b"], output="a")
        .with_transform_step(lambda ctx, a: a, inputs=["a"], output="b")
    )
    try:
        builder.build()
    except PipelineCycleError as exc:
        assert "->" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected PipelineCycleError")


def test_context_is_pydantic_validated() -> None:
    class Strict(PipelineContext):
        count: int

    try:
        Strict(count="not-an-int")  # type: ignore[arg-type]
    except Exception:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected validation error")
