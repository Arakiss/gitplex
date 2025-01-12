"""Command-line interface."""

import sys
from pathlib import Path
from typing import List, Optional

import click
from rich.console import Console
from rich.table import Table

from .exceptions import ProfileError, SystemConfigError
from .profile import ProfileManager
from .system import check_system_compatibility, get_home_dir
from .ui import (
    confirm_backup,
    prompt_directory,
    prompt_email,
    prompt_name,
    prompt_providers,
    prompt_username,
)

console = Console()


def handle_error(error: Exception) -> None:
    """Handle error and exit."""
    console.print(f"\n❌ Failed: {str(error)}\n", style="red")
    sys.exit(1)


@click.group()
def cli() -> None:
    """Git profile manager."""
    try:
        home_dir = get_home_dir()
        console.print(f"\nℹ️  Using home directory: {home_dir}\n")
        check_system_compatibility()
    except SystemConfigError as e:
        handle_error(e)


@cli.command()
@click.option("--name", help="Profile name")
@click.option("--email", help="Git email")
@click.option("--username", help="Git username")
@click.option("--directory", help="Working directory", multiple=True)
@click.option("--provider", help="Git provider", multiple=True)
def setup(
    name: Optional[str],
    email: Optional[str],
    username: Optional[str],
    directory: Optional[List[str]],
    provider: Optional[List[str]],
) -> None:
    """Set up a new Git profile."""
    try:
        # Get profile information
        if not name:
            name = prompt_name()
        if not email:
            email = prompt_email()
        if not username:
            username = prompt_username()
        if not directory:
            directory = [prompt_directory()]
        if not provider:
            provider = prompt_providers()

        # Create profile
        profile_manager = ProfileManager()
        profile = profile_manager.setup_profile(
            name=name,
            email=email,
            username=username,
            directories=list(directory),
            providers=list(provider),
        )

        console.print(f"\n✅ Profile '{profile.name}' created successfully\n")

    except (ProfileError, SystemConfigError) as e:
        handle_error(e)


@cli.command()
@click.argument("name")
def switch(name: str) -> None:
    """Switch to a different Git profile."""
    try:
        profile_manager = ProfileManager()
        profile = profile_manager.switch_profile(name)
        console.print(f"\n✅ Switched to profile '{profile.name}'\n")
    except ProfileError as e:
        handle_error(e)


@cli.command()
def list() -> None:
    """List all Git profiles."""
    try:
        profile_manager = ProfileManager()
        profiles = profile_manager.list_profiles()

        if not profiles:
            console.print("\nℹ️  No profiles found\n")
            return

        table = Table(title="Git Profiles")
        table.add_column("Name")
        table.add_column("Email")
        table.add_column("Username")
        table.add_column("Directories")
        table.add_column("Providers")
        table.add_column("Active")

        for profile in profiles:
            table.add_row(
                profile.name,
                profile.email,
                profile.username,
                "\n".join(str(d) for d in profile.directories),
                "\n".join(str(p) for p in profile.providers),
                "✓" if profile.active else "",
            )

        console.print("\n")
        console.print(table)
        console.print("\n")

    except ProfileError as e:
        handle_error(e)


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
