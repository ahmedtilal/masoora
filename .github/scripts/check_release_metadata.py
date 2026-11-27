"""Check that a changed package version has a changelog entry."""

import re
import subprocess
import sys
from pathlib import Path

import tomllib


def main(base_sha: str) -> None:
    base_manifest = subprocess.check_output(
        ["git", "show", f"{base_sha}:pyproject.toml"], text=True
    )
    base_version = tomllib.loads(base_manifest)["project"]["version"]
    manifest = Path("pyproject.toml").read_text(encoding="utf-8")
    version = tomllib.loads(manifest)["project"]["version"]
    if version == base_version:
        return

    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    sections = re.split(r"^##[ \t]+", changelog, flags=re.MULTILINE)
    heading = re.compile(rf"\[{re.escape(version)}\](?:[ \t]+-.*)?[ \t]*")
    for section in sections[1:]:
        title, _, notes = section.partition("\n")
        if heading.fullmatch(title) and re.search(r"^[-*+][ \t]+\S", notes, re.MULTILINE):
            return

    sys.exit(f"Version {version} requires a matching section with an entry in CHANGELOG.md.")


if __name__ == "__main__":
    main(sys.argv[1])
