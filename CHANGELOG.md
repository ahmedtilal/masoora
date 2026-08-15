# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.4] - 2026-08-15

Documentation release. There are no changes to library behaviour or the public
API; upgrading from 0.1.3 is a no-op at runtime.

### Added

- A documentation site at <https://ahmedtilal.github.io/masoora/>, with guides
  for building pipelines, parallel execution, and testing, plus a generated
  API reference for every public symbol.
- `Documentation` in the project URLs, so the site is reachable from the PyPI
  sidebar.

### Changed

- The `Homepage` project URL now points at the documentation site rather than
  the repository. `Repository` still points at GitHub.

## [0.1.3] - 2026-08-15

Documentation release. There are no changes to library behaviour or the public
API; upgrading from 0.1.2 is a no-op at runtime.

### Fixed

- The changelog and license links on the PyPI project page. They were written
  as repository-relative paths, which GitHub resolves but PyPI does not — on
  pypi.org they resolved against the project page and 404'd. All README links
  are now absolute.

### Added

- A `Changelog` entry in the project URLs, so it appears in the PyPI sidebar
  rather than only inside the rendered README.

## [0.1.2] - 2026-08-15

Documentation release. There are no changes to library behaviour or the public
API; upgrading from 0.1.1 is a no-op at runtime.

### Added

- Installation instructions in the README, including the `masoora[pytest]`
  extra required by `make_pipeline_fixture`. This is the point of the release:
  the PyPI page embeds the README from the published artifact, so the
  instructions only reach pypi.org by shipping a new version.
- Continuous integration on pushes and pull requests: the test suite across
  Python 3.10–3.14, plus Ruff lint, Ruff format, and strict Mypy.

## [0.1.1] - 2026-08-15

Packaging-only release. There are no changes to library behaviour or the public
API; upgrading from 0.1.0 is a no-op at runtime.

### Added

- This changelog, which is now shipped inside the source distribution.

## [0.1.0] - 2026-08-15

Initial release.

### Added

- `PipelineBuilder` — fluent construction via `.with_read_step()`,
  `.with_transform_step()`, and `.with_write_step()`.
- `PipelineContext` — Pydantic-typed configuration passed to every step.
- `DataCatalog` — in-memory key → dataset store, agnostic to the dataframe
  library in use (polars, pandas, spark, plain dicts).
- DAG resolution — steps may be declared in any order; cycles and missing
  inputs are rejected at `build()` rather than at run time.
- Parallel execution with dependency-driven scheduling: independent steps run
  concurrently once their inputs are satisfied.
- `TestablePipeline` and `make_pipeline_fixture()` — mock reads and writes and
  assert against the resulting catalog from a pytest fixture.
- Typed error hierarchy: `PipelineError`, `PipelineValidationError`,
  `PipelineCycleError`, `StepExecutionError`.
- `py.typed` marker — the package ships inline type information.

[Unreleased]: https://github.com/ahmedtilal/masoora/compare/v0.1.4...HEAD
[0.1.4]: https://github.com/ahmedtilal/masoora/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/ahmedtilal/masoora/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/ahmedtilal/masoora/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/ahmedtilal/masoora/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/ahmedtilal/masoora/releases/tag/v0.1.0
