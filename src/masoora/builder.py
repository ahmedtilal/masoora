"""Fluent builder for pipelines."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from masoora.errors import PipelineValidationError
from masoora.graph import topo_sort
from masoora.pipeline import Pipeline
from masoora.steps import ReadStep, Step, TransformStep, WriteStep
from masoora.validation import SupportsValidate, Validator

if TYPE_CHECKING:
    from typing_extensions import Self

    from masoora.context import PipelineContext

ContextT = TypeVar("ContextT", bound="PipelineContext")


class PipelineBuilder(Generic[ContextT]):
    """Chain read/transform/write steps, then build() a validated Pipeline.

    Steps may be declared in any order; build() resolves dependencies
    (DAG topo-sort) and fails fast on unknown inputs, duplicate outputs,
    or cycles.
    """

    def __init__(self) -> None:
        self._steps: list[Step[ContextT]] = []
        self._seeds: set[str] = set()
        self._validators: dict[str, Validator] = {}

    def with_read_step(
        self, fn: Callable[[ContextT], Any], *, output: str, validate: Validator | None = None
    ) -> Self:
        """fn(context) -> dataset, stored at catalog[output]."""
        self._steps.append(ReadStep(fn=fn, output=output))
        self._register_validator(output, validate)
        return self

    def with_transform_step(
        self,
        fn: Callable[..., Any],
        *,
        inputs: Sequence[str],
        output: str,
        validate: Validator | None = None,
    ) -> Self:
        """fn(context, *inputs) -> dataset, stored at catalog[output]."""
        self._steps.append(TransformStep(fn=fn, inputs=inputs, output=output))
        self._register_validator(output, validate)
        return self

    def with_write_step(self, fn: Callable[..., None], *, inputs: Sequence[str]) -> Self:
        """fn(context, *inputs) -> None; terminal step."""
        self._steps.append(WriteStep(fn=fn, inputs=inputs))
        return self

    def with_seed(self, key: str, *, validate: Validator | None = None) -> Self:
        """Declare a catalog key that will be pre-populated before run()."""
        self._seeds.add(key)
        self._register_validator(key, validate)
        return self

    def _register_validator(self, key: str, validate: Validator | None) -> None:
        if validate is None:
            return
        if key in self._validators:
            raise PipelineValidationError(f"Duplicate validator for catalog key {key!r}")
        # An unusable validator is a wiring bug, not bad data. Whether it is
        # usable is knowable now, so it fails now rather than mid-run.
        if not isinstance(validate, SupportsValidate) and not callable(validate):
            raise PipelineValidationError(
                f"Validator for catalog key {key!r} must expose .validate(data) or be "
                f"callable, got {type(validate).__name__}"
            )
        self._validators[key] = validate

    def build(self) -> Pipeline[ContextT]:
        """Validate and topo-sort the steps into an executable Pipeline."""
        self._validate()
        return Pipeline(steps=topo_sort(self._steps), validators=self._validators)

    def _validate(self) -> None:
        produced: dict[str, str] = {}
        for step in self._steps:
            for key in step.outputs:
                if key in produced:
                    raise PipelineValidationError(
                        f"Duplicate output key {key!r}: produced by both "
                        f"{produced[key]!r} and {step.name!r}"
                    )
                produced[key] = step.name

        unknown: dict[str, list[str]] = {}
        for step in self._steps:
            for key in step.inputs:
                if key not in produced and key not in self._seeds:
                    unknown.setdefault(key, []).append(step.name)
        if unknown:
            details = "; ".join(
                f"{key!r} (needed by {', '.join(names)})" for key, names in unknown.items()
            )
            raise PipelineValidationError(
                f"Input keys not produced by any step and not seeded: {details}. "
                "Add a producing step or declare .with_seed(key)."
            )

        for step in self._steps:
            if isinstance(step, WriteStep) and not step.inputs:
                raise PipelineValidationError(f"Write step {step.name!r} has no inputs")
