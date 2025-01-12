"""Terminal UI components and utilities."""

import sys
from pathlib import Path
from typing import Any, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.theme import Theme

from gitplex.exceptions import GitPlexError

# Custom theme for consistent styling
theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red",
    "success": "green",
    "path": "blue underline",
    "header": "bold magenta",
})

console = Console(theme=theme)


def print_error(error: GitPlexError) -> None:
    """Print an error message with optional details.
    
    Args:
        error: The error to display
    """
    console.print(f"\n[error]❌ Error: {error.message}[/]")
    if error.details:
        console.print(f"[error]Details: {error.details}[/]")


def print_warning(message: str, details: Optional[str] = None) -> None:
    """Print a warning message.
    
    Args:
        message: Warning message
        details: Optional details
    """
    console.print(f"\n[warning]⚠️  Warning: {message}[/]")
    if details:
        console.print(f"[warning]{details}[/]")


def print_success(message: str) -> None:
    """Print a success message.
    
    Args:
        message: Success message
    """
    console.print(f"\n[success]✅ {message}[/]")


def print_info(message: str) -> None:
    """Print an info message.
    
    Args:
        message: Info message
    """
    console.print(f"\n[info]ℹ️  {message}[/]")


def confirm_action(
    message: str,
    default: bool = False,
    abort: bool = True,
) -> bool:
    """Ask for user confirmation.
    
    Args:
        message: Confirmation message
        default: Default response
        abort: Whether to abort if user says no
        
    Returns:
        True if confirmed, False if not and abort is False
        
    Raises:
        SystemExit: If user says no and abort is True
    """
    try:
        if Confirm.ask(message, default=default):
            return True
        if abort:
            console.print("\n[warning]Operation aborted by user[/]")
            sys.exit(0)
        return False
    except KeyboardInterrupt:
        console.print("\n[warning]Operation aborted by user[/]")
        sys.exit(0)


def print_profile_table(
    profiles: List[dict],
    title: str = "Git Profiles",
) -> None:
    """Print a table of profiles.
    
    Args:
        profiles: List of profile data
        title: Table title
    """
    table = Table(title=title, show_header=True, header_style="header")
    
    table.add_column("Name", style="cyan")
    table.add_column("Email", style="green")
    table.add_column("Username", style="blue")
    table.add_column("Directories", style="path")
    table.add_column("Providers", style="magenta")
    
    for profile in profiles:
        table.add_row(
            profile["name"],
            profile["email"],
            profile["username"],
            "\n".join(str(d) for d in profile["directories"]),
            "\n".join(
                p["name"] if isinstance(p, dict) else p
                for p in profile["providers"]
            ),
        )
    
    console.print("\n", table, "\n")


def print_welcome() -> None:
    """Print welcome message and disclaimer."""
    welcome_panel = Panel.fit(
        "[bold cyan]Welcome to GitPlex![/]\n\n"
        "🔄 The smart way to manage multiple Git identities\n\n"
        "[yellow]⚠️  DISCLAIMER[/]\n"
        "This tool will modify your Git and SSH configurations.\n"
        "While it creates backups, you should review the changes\n"
        "and ensure they match your expectations.\n\n"
        "Use at your own risk and always keep backups of your\n"
        "important configurations.",
        title="[bold]GitPlex",
        border_style="cyan",
    )
    console.print("\n", welcome_panel, "\n")


def print_backup_info(backup_path: Path) -> None:
    """Print backup information.
    
    Args:
        backup_path: Path where backup was saved
    """
    backup_panel = Panel.fit(
        f"[green]✅ Backup created successfully at:[/]\n"
        f"[blue]{backup_path}[/]\n\n"
        "[yellow]Keep this backup safe! You can restore it manually if needed.[/]",
        title="[bold]Backup Information",
        border_style="green",
    )
    console.print("\n", backup_panel, "\n")


def get_user_input(
    prompt: str,
    default: Optional[str] = None,
    password: bool = False,
) -> str:
    """Get input from user with proper error handling.
    
    Args:
        prompt: Input prompt
        default: Default value
        password: Whether this is a password field
        
    Returns:
        User input
        
    Raises:
        SystemExit: If user interrupts
    """
    try:
        return Prompt.ask(
            prompt,
            default=default,
            password=password,
        )
    except KeyboardInterrupt:
        console.print("\n[warning]Operation aborted by user[/]")
        sys.exit(0) 