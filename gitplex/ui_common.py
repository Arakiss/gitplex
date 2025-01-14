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


def print_error(message: str, details: str | None = None) -> None:
    """Print an error message."""
    # Create plain text without any markup
    error_text = f"❌ {message}"
    if details:
        error_text += f"\n\n{details}"

    # Create panel with raw text
    panel = Panel.fit(
        error_text,
        style="error",
        border_style="red",
    )
    # Print without interpreting markup
    console.print(panel, markup=False)


def print_warning(message: str) -> None:
    """Print a warning message."""
    panel = Panel.fit(
        f"⚠️  {message}",
        style="warning",
        border_style="yellow",
    )
    console.print(panel)


def print_success(message: str) -> None:
    """Print a success message."""
    panel = Panel.fit(
        f"✅ {message}",
        style="success",
        border_style="green",
    )
    console.print(panel)


def print_info(message: str, no_panel: bool = False) -> None:
    """Print an informational message.
    
    Args:
        message: The message to print
        no_panel: If True, prints the message without a panel (useful for SSH keys)
    """
    if no_panel:
        console.print(message)
    else:
        panel = Panel.fit(
            f"ℹ️  {message}",
            style="info",
            border_style="blue",
        )
        console.print(panel)


def confirm_action(message: str, default: bool = True) -> bool:
    """Ask for user confirmation."""
    try:
        return Confirm.ask(
            f"[highlight]{message}[/]",
            default=default,
            show_default=True,
        )
    except KeyboardInterrupt:
        return False
