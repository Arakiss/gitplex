"""Common UI utilities shared across modules."""

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.theme import Theme

# Create a custom theme for consistent styling
theme = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "red",
        "success": "green",
        "title": "bold cyan",
        "subtitle": "italic cyan",
        "highlight": "bold yellow",
        "path": "blue",
        "command": "green",
    }
)

console = Console(theme=theme)


def print_error(message: str) -> None:
    """Print error message."""
    console.print(f"[error]Error:[/error] {message}")


def print_warning(message: str) -> None:
    """Print warning message."""
    console.print(f"[warning]Warning:[/warning] {message}")


def print_info(message: str) -> None:
    """Print info message."""
    console.print(f"[info]Info:[/info] {message}")


def print_success(message: str) -> None:
    """Print success message."""
    console.print(f"[success]Success:[/success] {message}")


def confirm_action(prompt: str, default: bool = True) -> bool:
    """Confirm an action with the user."""
    try:
        return Confirm.ask(prompt, default=default)
    except KeyboardInterrupt:
        from .exceptions import GitplexError
        raise GitplexError("Operation cancelled by user") from None
