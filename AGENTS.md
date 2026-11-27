## Agent skills

### Issue tracker

Use GitHub Issues for Masoora. Read `docs/agents/issue-tracker.md` before fetching, filing, or updating tickets.

### Triage labels

Use the five default triage labels. Read `docs/agents/triage-labels.md` before applying a triage role.

### Domain docs

Masoora uses a single-context layout. Read `docs/agents/domain.md` before exploring the domain or proposing changes.

## Release checklist

- Record user-visible changes in `CHANGELOG.md`. Use `[Unreleased]` when preparing the change without a version bump.
- Bump the minor version for public API additions or changes. Use a patch bump for bug-fix and docs-only releases.
- When bumping, run `uv version <version>` to update `pyproject.toml` and `uv.lock` together. Put the release notes under `## [<version>]` with at least one bullet, then run `uv lock --check`.
