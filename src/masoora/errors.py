"""Errors raised by masoora."""

from __future__ import annotations


class PipelineError(Exception):
    """Base class for all masoora errors."""


class PipelineValidationError(PipelineError):
    """Raised at build time when the pipeline definition is invalid."""


class PipelineCycleError(PipelineValidationError):
    """Raised at build time when steps form a dependency cycle."""

    def __init__(self, cycle: list[str]) -> None:
        self.cycle = cycle
        super().__init__(f"Pipeline contains a dependency cycle: {' -> '.join(cycle)}")


class DataValidationError(PipelineError):
    """Raised when a catalog value fails the validator declared for its key."""

    def __init__(self, key: str, phase: str, original: Exception) -> None:
        self.key = key
        self.phase = phase
        self.original = original
        super().__init__(
            f"Data for catalog key {key!r} failed validation on {phase}: "
            f"{type(original).__name__}: {original}"
        )


class StepExecutionError(PipelineError):
    """Raised when a step fails during run()."""

    def __init__(self, step_index: int, step_name: str, original: Exception) -> None:
        self.step_index = step_index
        self.step_name = step_name
        self.original = original
        super().__init__(
            f"Step {step_index} ({step_name!r}) failed: {type(original).__name__}: {original}"
        )
