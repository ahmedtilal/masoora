"""In-memory data catalog: keys mapped to datasets of any type."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, MutableMapping
from typing import Any

from masoora.errors import DataValidationError
from masoora.validation import Validator, run_validator


class DataCatalog(MutableMapping[str, Any]):
    """Holds datasets produced and consumed by pipeline steps.

    Values are unconstrained: polars/pandas/spark dataframes, dicts, models, etc.

    A key may carry a validator. Values are checked when written and when read,
    so data that never passed through a step -- seeded keys, fixtures supplied
    by to_testable() -- is checked too. Each value is checked once: a read after
    a validated write does not repeat the work.
    """

    def __init__(
        self,
        initial: Mapping[str, Any] | None = None,
        validators: Mapping[str, Validator] | None = None,
    ) -> None:
        self._data: dict[str, Any] = dict(initial) if initial else {}
        self._validators: dict[str, Validator] = dict(validators) if validators else {}
        self._validated: set[str] = set()

    def attach_validators(self, validators: Mapping[str, Validator]) -> None:
        """Register validators for keys that do not already have one."""
        for key, validator in validators.items():
            self._validators.setdefault(key, validator)

    def _check(self, key: str, value: Any, phase: str) -> None:
        validator = self._validators.get(key)
        if validator is None:
            return
        try:
            run_validator(validator, value)
        except Exception as exc:
            raise DataValidationError(key, phase, exc) from exc
        self._validated.add(key)

    def __getitem__(self, key: str) -> Any:
        value = self._data[key]
        if key not in self._validated:
            self._check(key, value, "read")
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        self._validated.discard(key)
        self._check(key, value, "write")
        self._data[key] = value

    def __delitem__(self, key: str) -> None:
        del self._data[key]
        self._validated.discard(key)

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"DataCatalog(keys={list(self._data)})"

    def snapshot(self) -> dict[str, Any]:
        """Return a shallow copy of the catalog contents, skipping validation."""
        return dict(self._data)
