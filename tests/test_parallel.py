import threading
import time
from concurrent.futures import ThreadPoolExecutor

from conftest import Ctx

from masoora import PipelineBuilder, StepExecutionError


def _diamond() -> PipelineBuilder[Ctx]:
    return (
        PipelineBuilder[Ctx]()
        .with_transform_step(lambda ctx, x: x + 1, inputs=["x"], output="left")
        .with_read_step(lambda ctx: 1, output="x")
        .with_transform_step(
            lambda ctx, left, right: left * right, inputs=["left", "right"], output="join"
        )
        .with_transform_step(lambda ctx, x: x * 10, inputs=["x"], output="right")
    )


def test_parallel_true_matches_sequential() -> None:
    pipeline = _diamond().build()
    seq = pipeline.run(Ctx(n=0))
    par = pipeline.run(Ctx(n=0), parallel=True)
    assert par.snapshot() == seq.snapshot()


def test_parallel_int_workers() -> None:
    pipeline = _diamond().build()
    catalog = pipeline.run(Ctx(n=0), parallel=2)
    assert catalog["join"] == 20


def test_independent_steps_actually_run_concurrently() -> None:
    barrier = threading.Barrier(2)

    def slow(ctx: Ctx) -> int:
        barrier.wait(timeout=5)  # only passes if both run at the same time
        return 1

    pipeline = (
        PipelineBuilder[Ctx]()
        .with_read_step(slow, output="a")
        .with_read_step(slow, output="b")
        .build()
    )
    catalog = pipeline.run(Ctx(n=0), parallel=True)
    assert catalog.snapshot() == {"a": 1, "b": 1}


def test_parallel_failure_fails_fast_with_topo_index() -> None:
    def boom(ctx: Ctx) -> int:
        raise ValueError("nope")

    pipeline = (
        PipelineBuilder[Ctx]()
        .with_read_step(boom, output="bad")
        .with_read_step(lambda ctx: time.sleep(2), output="slow")
        .build()
    )
    start = time.monotonic()
    try:
        pipeline.run(Ctx(n=0), parallel=True)
    except StepExecutionError as exc:
        assert exc.step_name == "boom"
        assert exc.step_index == 0  # index in topo order, not completion order
        assert isinstance(exc.original, ValueError)
        assert time.monotonic() - start < 1.5  # fail-fast: didn't wait for slow sibling
    else:  # pragma: no cover
        raise AssertionError("expected StepExecutionError")


def test_external_executor_wins_and_is_not_shut_down() -> None:
    pipeline = _diamond().build()
    with ThreadPoolExecutor(max_workers=2) as pool:
        catalog = pipeline.run(Ctx(n=0), executor=pool)
        assert catalog["join"] == 20
        # pool still usable afterwards
        assert pool.submit(lambda: 42).result() == 42


def test_parallel_with_target_pruning() -> None:
    calls: list[str] = []
    lock = threading.Lock()

    def read_a(ctx: Ctx) -> int:
        with lock:
            calls.append("read_a")
        return 1

    def read_b(ctx: Ctx) -> int:
        with lock:
            calls.append("read_b")
        return 2

    pipeline = (
        PipelineBuilder[Ctx]()
        .with_read_step(read_a, output="a")
        .with_read_step(read_b, output="b")
        .with_transform_step(lambda ctx, a: a * 10, inputs=["a"], output="a10")
        .build()
    )
    catalog = pipeline.run(Ctx(n=0), target="a10", parallel=True)
    assert catalog["a10"] == 10
    assert calls == ["read_a"]


def test_downstream_of_fast_branch_runs_before_slow_branch_finishes() -> None:
    """Dependency-driven: no level barrier between unrelated branches."""
    events: list[str] = []
    lock = threading.Lock()

    def record(name: str) -> None:
        with lock:
            events.append(name)

    def read_fast(ctx: Ctx) -> int:
        record("read_fast")
        return 1

    def read_slow(ctx: Ctx) -> int:
        time.sleep(0.3)
        record("read_slow")
        return 2

    def tf(ctx: Ctx, fast: int) -> int:
        record("tf")
        return fast * 10

    pipeline = (
        PipelineBuilder[Ctx]()
        .with_read_step(read_fast, output="fast")
        .with_read_step(read_slow, output="slow")
        .with_transform_step(tf, inputs=["fast"], output="fast10")
        .build()
    )
    catalog = pipeline.run(Ctx(n=0), parallel=True)
    assert catalog["fast10"] == 10
    assert events.index("tf") < events.index("read_slow")


def test_failure_does_not_wait_for_unrelated_inflight_branch() -> None:
    """A failure downstream of a fast step aborts while a slow unrelated
    step is still running (impossible under barrier scheduling)."""

    def boom(ctx: Ctx, fast: int) -> int:
        raise ValueError("nope")

    pipeline = (
        PipelineBuilder[Ctx]()
        .with_read_step(lambda ctx: 1, output="fast")
        .with_read_step(lambda ctx: time.sleep(2), output="slow")
        .with_transform_step(boom, inputs=["fast"], output="bad")
        .build()
    )
    start = time.monotonic()
    try:
        pipeline.run(Ctx(n=0), parallel=True)
    except StepExecutionError as exc:
        assert exc.step_name == "boom"
        assert exc.step_index == 2
        assert time.monotonic() - start < 1.5
    else:  # pragma: no cover
        raise AssertionError("expected StepExecutionError")


def test_testable_parallel_mocks_reads_and_writes() -> None:
    written: list[int] = []
    pipeline = (
        PipelineBuilder[Ctx]()
        .with_read_step(lambda ctx: 1, output="a")
        .with_read_step(lambda ctx: 2, output="b")
        .with_write_step(lambda ctx, a: written.append(a), inputs=["a"])
        .with_write_step(lambda ctx, b: written.append(b), inputs=["b"])
        .build()
    )
    result = pipeline.to_testable(reads={"a": 100}).run(Ctx(n=0), parallel=True)
    assert result.catalog["a"] == 100
    assert result.catalog["b"] == 2
    assert result.written == {"a": 100, "b": 2}
    assert written == []  # real writers never called
