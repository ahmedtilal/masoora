# Installation

masoora requires **Python 3.10 or newer**. Its only runtime dependency is
Pydantic.

=== "pip"

    ```bash
    pip install masoora
    ```

=== "uv"

    ```bash
    uv add masoora
    ```

## The pytest extra

[`make_pipeline_fixture`][masoora.make_pipeline_fixture] imports pytest, so if
you use the testing helpers you need pytest installed. It ships as an extra:

=== "pip"

    ```bash
    pip install "masoora[pytest]"
    ```

=== "uv"

    ```bash
    uv add "masoora[pytest]"
    ```

!!! note

    The extra only matters for [`make_pipeline_fixture`][masoora.make_pipeline_fixture].
    The core builder, pipeline, and catalog have no test-time dependencies, and
    `pipeline.to_testable()` works without pytest — see [Testing](guide/testing.md).

## Typing

The package ships a `py.typed` marker and is checked under strict Mypy, so
type information is available to your type checker with no stub package.

## Verifying the install

```python
import masoora

print(masoora.__all__)
```
