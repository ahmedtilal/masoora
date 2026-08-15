import sys

sys.dont_write_bytecode = True

from masoora import PipelineContext  # noqa: E402  (flag must be set before imports)


class Ctx(PipelineContext):
    n: int
