#!/usr/bin/env python3
# Copyright (c) 2025. All rights reserved.
"""Prepare a new release by bumping version numbers."""

import re
import sys
from enum import StrEnum
from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt

console = Console()


class BumpType(StrEnum):
    """Enum for version bump types."""

    PATCH = "patch"
    MINOR = "minor"
    MAJOR = "major"


def get_current_version(pyproject_path: Path) -> str:
    """Extract current version from pyproject.toml.

    Returns:
        Current version string.

    """
    content = pyproject_path.read_text(encoding="utf-8")
    match = re.search(r'version = "(\d+\.\d+\.\d+)"', content)
    if not match:
        console.print("[red]Could not find version in pyproject.toml[/red]")
        sys.exit(1)
    return match.group(1)


def bump_version(current_version: str, bump_type: BumpType) -> str:
    """Calculate new version based on bump type.

    Returns:
        New version string.

    """
    major, minor, patch = map(int, current_version.split("."))
    if bump_type == BumpType.MAJOR:
        major += 1
        minor = 0
        patch = 0
    elif bump_type == BumpType.MINOR:
        minor += 1
        patch = 0
    elif bump_type == BumpType.PATCH:
        patch += 1
    return f"{major}.{minor}.{patch}"


def update_file(path: Path, pattern: str, replacement: str) -> None:
    """Update file content using regex pattern."""
    content = path.read_text(encoding="utf-8")
    if not re.search(pattern, content):
        console.print(f"[yellow]Warning: Pattern not found in {path.name}[/yellow]")
        return
    new_content = re.sub(pattern, replacement, content)
    path.write_text(new_content, encoding="utf-8")


def main() -> None:
    """Execute the release preparation process."""
    root_dir = Path(__file__).parent.parent
    pyproject_path = root_dir / "pyproject.toml"
    cli_path = root_dir / "src" / "cli.py"
    test_cli_path = root_dir / "tests" / "integration" / "test_cli.py"

    if not pyproject_path.exists() or not cli_path.exists():
        console.print("[red]Could not find project files.[/red]")
        sys.exit(1)

    current_version = get_current_version(pyproject_path)
    console.print(f"Current version: [bold cyan]{current_version}[/bold cyan]")

    bump_type = Prompt.ask(
        "Select bump type",
        choices=[t.value for t in BumpType],
        default=BumpType.PATCH.value,
    )

    new_version = bump_version(current_version, BumpType(bump_type))
    console.print(f"Bumping to: [bold green]{new_version}[/bold green]")

    # Update pyproject.toml
    update_file(
        pyproject_path,
        r'version = "\d+\.\d+\.\d+"',
        f'version = "{new_version}"',
    )
    console.print(f"[green]✓[/green] Updated {pyproject_path.name}")

    # Update src/cli.py
    update_file(
        cli_path,
        r'version="\d+\.\d+\.\d+"',
        f'version="{new_version}"',
    )
    console.print(f"[green]✓[/green] Updated {cli_path.name}")

    # Update tests/integration/test_cli.py
    if test_cli_path.exists():
        update_file(
            test_cli_path,
            r'assert "\d+\.\d+\.\d+" in result\.output',
            f'assert "{new_version}" in result.output',
        )
        console.print(f"[green]✓[/green] Updated {test_cli_path.name}")


if __name__ == "__main__":
    main()
