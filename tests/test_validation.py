"""Per-key data validation: on write, on read, and through to_testable()."""

from __future__ import annotations

from typing import Any

import pytest

from masoora import (
    DataCatalog,
    DataValidationError,
    PipelineBuilder,
    PipelineContext,
    StepExecutionError,
)


class Ctx(PipelineContext):
    pass


def positive(data: Any) -> None:
    """Callable validator: rejects any non-positive number."""
    if any(n <= 0 for n in data):
        raise ValueError("values must be positive")


class SchemaLike:
    """Stands in for a pandera schema: validates via .validate() and is callable."""

    def __init__(self) -> None:
        self.calls = 0

    def validate(self, data: Any) -> Any:
        self.calls += 1
        if not isinstance(data, list):
            raise TypeError(f"expected list, got {type(data).__name__}")
        return data

    def __call__(self, data: Any) -> Any:  # pragma: no cover - must not be preferred
        raise AssertionError(".validate() should be preferred over __call__")


def test_validates_on_write() -> None:
    pipeline = (
        PipelineBuilder[Ctx]()
        .with_read_step(lambda _c: [1, -2], output="nums", validate=positive)
        .build()
    )
    with pytest.raises(StepExecutionError) as exc:
        pipeline.run(Ctx())
    assert isinstance(exc.value.original, DataValidationError)
    assert exc.value.original.key == "nums"
    assert exc.value.original.phase == "write"


def test_valid_data_passes() -> None:
    pipeline = (
        PipelineBuilder[Ctx]()
        .with_read_step(lambda _c: [1, 2], output="nums", validate=positive)
        .with_transform_step(lambda _c, n: [x * 2 for x in n], inputs=["nums"], output="doubled")
        .build()
    )
    assert pipeline.run(Ctx())["doubled"] == [2, 4]


def test_validates_seeded_key_on_read() -> None:
    """A seed never passes through a write, so the read path must check it."""
    pipeline = (
        PipelineBuilder[Ctx]()
        .with_seed("nums", validate=positive)
        .with_transform_step(lambda _c, n: sum(n), inputs=["nums"], output="total")
        .build()
    )
    with pytest.raises(StepExecutionError) as exc:
        pipeline.run(Ctx(), catalog=DataCatalog({"nums": [1, -2]}))
    assert isinstance(exc.value.original, DataValidationError)
    assert exc.value.original.phase == "read"


def test_validates_mocked_read_fixture() -> None:
    """Fake data that has drifted from the real schema must still fail."""
    pipeline = (
        PipelineBuilder[Ctx]()
        .with_read_step(lambda _c: [1, 2], output="nums", validate=positive)
        .with_transform_step(lambda _c, n: sum(n), inputs=["nums"], output="total")
        .build()
    )
    with pytest.raises(StepExecutionError) as exc:
        pipeline.to_testable(reads={"nums": [-1]}).run(Ctx())
    assert isinstance(exc.value.original, DataValidationError)


def test_validate_method_preferred_over_call() -> None:
    schema = SchemaLike()
    pipeline = (
        PipelineBuilder[Ctx]()
        .with_read_step(lambda _c: [1, 2], output="nums", validate=schema)
        .build()
    )
    pipeline.run(Ctx())
    assert schema.calls == 1


def test_each_value_validated_once() -> None:
    """A write already checked the value; later reads must not redo the work."""
    schema = SchemaLike()
    pipeline = (
        PipelineBuilder[Ctx]()
        .with_read_step(lambda _c: [1, 2], output="nums", validate=schema)
        .with_transform_step(lambda _c, n: sum(n), inputs=["nums"], output="a")
        .with_transform_step(lambda _c, n: len(n), inputs=["nums"], output="b")
        .build()
    )
    pipeline.run(Ctx())
    assert schema.calls == 1  # one write, two reads


def test_rewrite_revalidates() -> None:
    catalog = DataCatalog(validators={"nums": positive})
    catalog["nums"] = [1]
    with pytest.raises(DataValidationError):
        catalog["nums"] = [-1]
    assert catalog["nums"] == [1]  # failed write left the old value in place


def test_keys_without_validators_are_untouched() -> None:
    pipeline = (
        PipelineBuilder[Ctx]().with_read_step(lambda _c: "anything at all", output="raw").build()
    )
    assert pipeline.run(Ctx())["raw"] == "anything at all"


def test_duplicate_validator_rejected_at_build() -> None:
    from masoora import PipelineValidationError

    builder = PipelineBuilder[Ctx]()
    builder.with_seed("nums", validate=positive)
    with pytest.raises(PipelineValidationError, match="Duplicate validator"):
        builder.with_read_step(lambda _c: [1], output="nums", validate=positive)


def test_bad_validator_rejected_at_build_time() -> None:
    """An unusable validator is a wiring bug: it fails before anything runs."""
    from masoora import PipelineValidationError

    with pytest.raises(PipelineValidationError, match="must expose .validate"):
        PipelineBuilder[Ctx]().with_read_step(
            lambda _c: [1],
            output="nums",
            validate="not a validator",  # type: ignore[arg-type]
        )


def test_validation_survives_parallel_execution() -> None:
    pipeline = (
        PipelineBuilder[Ctx]()
        .with_read_step(lambda _c: [1, 2], output="a", validate=positive)
        .with_read_step(lambda _c: [3, -4], output="b", validate=positive)
        .with_transform_step(lambda _c, x, y: x + y, inputs=["a", "b"], output="both")
        .build()
    )
    with pytest.raises(StepExecutionError) as exc:
        pipeline.run(Ctx(), parallel=True)
    assert isinstance(exc.value.original, DataValidationError)
    assert exc.value.original.key == "b"
