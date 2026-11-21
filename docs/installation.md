# Installation

The current release is **0.3.0**. masoora supports **Python 3.10 to 3.14**;
CI runs the test suite on every minor version in that range. Its only runtime
dependency is Pydantic.

=== "pip"

    ```bash
    pip install masoora
    ```

=== "uv"

    ```bash
    uv add masoora
    ```

To check which version is installed:

```python
from importlib.metadata import version

print(version("masoora"))
```

## Stability

masoora is **alpha** software (`Development Status :: 3 - Alpha` on PyPI) and
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html), including
its rule for `0.x` versions:

- **Patch releases** (`0.3.0` → `0.3.1`) fix bugs or change documentation only.
- **Minor releases** (`0.3.x` → `0.4.0`) may change the public API. Every
  change is recorded in the [changelog](https://github.com/ahmedtilal/masoora/blob/master/CHANGELOG.md).
- `1.0.0` is when backwards-compatibility guarantees start.

**What counts as public API:** the names exported from the top-level `masoora`
package (`masoora.__all__`), their documented signatures and behaviour, and the
attributes documented on the error classes (`StepExecutionError.step_name`
and friends). Everything on the [API reference](reference/api.md) page is
public.

**What does not:** the submodules (`masoora.builder`, `masoora.graph`,
`masoora.diagram`, …) and anything whose name starts with an underscore.
Import from `masoora`, not from its submodules. The wording of exception
messages and the exact text of [`to_mermaid()`][masoora.Pipeline.to_mermaid]
output are not promised either; assert on exception attributes, not on message
text.

**Pin an exact version.** Until 1.0, a range such as `masoora>=0.3` can pick
up a breaking change on the next install:

=== "pip"

    ```bash
    pip install "masoora==0.3.0"
    ```

=== "uv"

    ```bash
    uv add "masoora==0.3.0"
    ```

Upgrade deliberately: read the changelog, bump the pin, run your tests.

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

## The pandera extra

masoora never imports pandera — a validator is anything with `.validate(data)`,
or any callable. This extra is a convenience for installing pandera alongside
it. See [Data validation](guide/validation.md).

=== "pip"

    ```bash
    pip install "masoora[pandera]"
    ```

=== "uv"

    ```bash
    uv add "masoora[pandera]"
    ```

## Typing

The package ships a `py.typed` marker and is checked under strict Mypy, so
type information is available to your type checker with no stub package.

## Verifying the install

```python
import masoora

print(masoora.__all__)
```
