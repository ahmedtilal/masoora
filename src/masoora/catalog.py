"""In-memory data catalog: keys mapped to datasets of any type."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, MutableMapping
from typing import Any


class DataCatalog(MutableMapping[str, Any]):
    """Holds datasets produced and consumed by pipeline steps.

    Values are unconstrained: polars/pandas/spark dataframes, dicts, models, etc.
    """

    def __init__(self, initial: Mapping[str, Any] | None = None) -> None:
        self._data: dict[str, Any] = dict(initial) if initial else {}

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __delitem__(self, key: str) -> None:
        del self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"DataCatalog(keys={list(self._data)})"

    def snapshot(self) -> dict[str, Any]:
        """Return a shallow copy of the catalog contents."""
        return dict(self._data)
