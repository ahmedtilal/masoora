"""Base class for pipeline contexts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PipelineContext(BaseModel):
    """Holds all variables/configuration a pipeline needs.

    Users subclass this and declare their own fields:

        class MyContext(PipelineContext):
            source_url: str
            batch_size: int = 100
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
