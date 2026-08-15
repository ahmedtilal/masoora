"""Optional per-key data validation.

masoora does not depend on any validation library. A validator is either an
object with a ``.validate(data)`` method (which is what pandera schemas and
models expose) or a plain callable that raises on bad data.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SupportsValidate(Protocol):
    """Anything exposing pandera's ``.validate(data)`` interface."""

    def validate(self, data: Any, /) -> Any: ...


#: A pandera schema/model, or any callable that raises on invalid data.
Validator = SupportsValidate | Callable[[Any], Any]


def run_validator(validator: Validator, data: Any) -> None:
    """Apply `validator` to `data`, letting its own exception propagate."""
    # Checked before `callable`: pandera schemas are both.
    if isinstance(validator, SupportsValidate):
        validator.validate(data)
    elif callable(validator):
        validator(data)
    else:
        raise TypeError(
            f"Validator must expose .validate(data) or be callable, got {type(validator).__name__}"
        )
