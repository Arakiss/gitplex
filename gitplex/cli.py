"""Command-line interface."""

from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar, cast

import click
from rich.console import Console
from rich.table import Table

from .exceptions import ProfileError, SystemConfigError
from .profile import ProfileManager
from .system import check_system_compatibility, get_home_dir
from .ui import (
    prompt_directory,
    prompt_email,
    prompt_name,
    prompt_providers,
    prompt_username,
)

# Separate consoles for stdout and stderr
console = Console()
error_console = Console(stderr=True)

F = TypeVar('F', bound=Callable[..., Any])


class GitplexError(click.ClickException):
    """Base exception for Gitplex CLI errors."""
    def show(self, file: Any = None) -> None:
        """Show error message."""
        error_console.print(f"\n❌ Failed: {self.message}\n", style="red")


def handle_errors(f: F) -> F:
    """Decorator to handle errors in CLI commands."""
    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return f(*args, **kwargs)
        except (ProfileError, SystemConfigError) as e:
            raise GitplexError(str(e)) from e
        except Exception as e:
            error_console.print(f"\n❌ Unexpected error: {str(e)}\n", style="red")
            raise click.Abort() from e
    return cast(F, wrapper)


def ensure_directory(path: str) -> str:
    """Ensure directory exists and return absolute path."""
    try:
        dir_path = Path(path).resolve()
        dir_path.mkdir(parents=True, exist_ok=True)
        return str(dir_path)
    except Exception as e:
        raise SystemConfigError(f"Failed to create directory {path}: {str(e)}") from e


@click.group()
@handle_errors
def cli() -> None:
    """Git profile manager."""
    home_dir = get_home_dir()
    console.print(f"\nℹ️  Using home directory: {home_dir}\n")
    check_system_compatibility()


@cli.command()
@click.option("--name", help="Profile name")
@click.option("--email", help="Git email")
@click.option("--username", help="Git username")
@click.option(
    "--directory",
    help="Working directory",
    multiple=True,
    type=click.Path(resolve_path=True),
)
@click.option("--provider", help="Git provider", multiple=True)
@handle_errors
def setup(
    name: str | None,
    email: str | None,
    username: str | None,
    directory: list[str] | None,
    provider: list[str] | None,
) -> None:
    """Set up a new Git profile."""
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

    # Ensure directories exist and convert to absolute paths
    directories = [ensure_directory(d) for d in directory]

    # Create profile
    profile_manager = ProfileManager()
    profile = profile_manager.setup_profile(
        name=name,
        email=email,
        username=username,
        directories=directories,
        providers=list(provider),
    )

    console.print(f"\n✅ Profile '{profile.name}' created successfully\n")


@cli.command()
@click.argument("name")
@handle_errors
def switch(name: str) -> None:
    """Switch to a different Git profile."""
    profile_manager = ProfileManager()
    profile = profile_manager.switch_profile(name)
    console.print(f"\n✅ Switched to profile '{profile.name}'\n")


@cli.command()
@handle_errors
def list() -> None:
    """List all Git profiles."""
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
            "\n".join(p.value for p in profile.providers),
            "✓" if profile.active else "",
        )

    console.print("\n")
    console.print(table)
    console.print("\n")


if __name__ == "__main__":
    cli()
