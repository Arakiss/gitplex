"""Terminal UI components and utilities."""

from pathlib import Path
from typing import Any, List

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.theme import Theme
import click

# Create a custom theme for consistent styling
theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red",
    "success": "green",
})

console = Console(theme=theme)


def print_error(message: str, details: str | None = None) -> None:
    """Print an error message."""
    if details:
        console.print(f"\n❌ {message}: {details}\n", style="error")
    else:
        console.print(f"\n❌ {message}\n", style="error")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"\n⚠️  {message}\n", style="warning")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"\n✅ {message}\n", style="success")


def print_info(message: str) -> None:
    """Print an informational message."""
    console.print(f"\nℹ️  {message}\n", style="info")


def confirm_action(message: str, default: bool = True) -> bool:
    """Ask for user confirmation."""
    return Confirm.ask(f"{message} [y/n]", default=default)


def get_user_input(prompt: str, default: str | None = None) -> str:
    """Get user input with optional default value."""
    if default:
        return Prompt.ask(f"{prompt} [{default}]") or default
    return Prompt.ask(f"{prompt}")


def print_profile_table(profiles: list[dict[str, Any]]) -> None:
    """Print a table of profiles."""
    table = Table(title="Git Profiles")

    # Add columns
    table.add_column("Name", style="cyan")
    table.add_column("Email", style="green")
    table.add_column("Username", style="yellow")
    table.add_column("Directories", style="blue")
    table.add_column("Providers", style="magenta")
    table.add_column("Active", style="red")

    # Add rows
    for profile in profiles:
        table.add_row(
            profile["name"],
            profile["email"],
            profile["username"],
            "\n".join(profile["directories"]),
            "\n".join(profile["providers"]),
            "✓" if profile["active"] else "",
        )

    console.print(table)


def print_welcome() -> None:
    """Print welcome message and disclaimer."""
    welcome_panel = Panel.fit(
        "[bold cyan]Welcome to GitPlex![/]\n\n"
        "This tool will help you manage multiple Git identities and workspaces.\n"
        "[yellow]Note: This will modify your Git and SSH configurations.[/]\n"
        "Make sure you understand the changes being made.",
        title="GitPlex",
        border_style="blue",
    )
    console.print(welcome_panel)


def print_backup_info(backup_path: Path) -> None:
    """Print information about backup creation."""
    print_success("Backup created successfully")
    print_info(f"Backup location: {backup_path}")
    print_info(
        "You can restore this backup later using:\n"
        f"gitplex restore {backup_path}"
    )


def prompt_name() -> str:
    """Prompt for profile name."""
    return click.prompt("Enter profile name")


def prompt_email() -> str:
    """Prompt for Git email."""
    return click.prompt("Enter Git email")


def prompt_username() -> str:
    """Prompt for Git username."""
    return click.prompt("Enter Git username")


def prompt_directory() -> str:
    """Prompt for workspace directory."""
    directory = click.prompt("Enter workspace directory")
    return str(Path(directory).resolve())


def prompt_providers() -> List[str]:
    """Prompt for Git providers."""
    return [
        click.prompt(
            "Enter Git provider",
            type=click.Choice(["github", "gitlab", "bitbucket"]),
            default="github",
        )
    ]


def confirm_backup() -> bool:
    """Confirm backup creation."""
    return click.confirm(
        "Existing Git configurations found. Would you like to back them up?",
    )
