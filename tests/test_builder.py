from conftest import Ctx

from masoora import PipelineBuilder, PipelineValidationError


def test_duplicate_output_rejected() -> None:
    builder = (
        PipelineBuilder[Ctx]()
        .with_read_step(lambda ctx: 1, output="a")
        .with_read_step(lambda ctx: 2, output="a")
    )
    try:
        builder.build()
    except PipelineValidationError as exc:
        assert "Duplicate output key 'a'" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected PipelineValidationError")


def test_unknown_input_rejected() -> None:
    builder = PipelineBuilder[Ctx]().with_transform_step(
        lambda ctx, missing: missing, inputs=["missing"], output="b"
    )
    try:
        builder.build()
    except PipelineValidationError as exc:
        assert "'missing'" in str(exc)
        assert ".with_seed" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected PipelineValidationError")


def test_write_step_without_inputs_rejected() -> None:
    builder = PipelineBuilder[Ctx]().with_write_step(lambda ctx: None, inputs=[])
    try:
        builder.build()
    except PipelineValidationError as exc:
        assert "no inputs" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected PipelineValidationError")


def test_seeded_input_accepted() -> None:
    pipeline = (
        PipelineBuilder[Ctx]()
        .with_seed("cfg")
        .with_transform_step(lambda ctx, cfg: cfg, inputs=["cfg"], output="out")
        .build()
    )
    assert len(pipeline.steps) == 1
