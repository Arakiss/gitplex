"""Terminal UI components and utilities."""

from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.theme import Theme
from rich.syntax import Syntax

from .exceptions import SystemConfigError

# Create a custom theme for consistent styling
theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red",
    "success": "green",
    "title": "bold cyan",
    "subtitle": "italic cyan",
    "highlight": "bold yellow",
    "path": "blue",
    "command": "green",
})

console = Console(theme=theme)

BANNER = """
 ██████╗ ██╗████████╗██████╗ ██╗     ███████╗██╗  ██╗
██╔════╝ ██║╚══██╔══╝██╔══██╗██║     ██╔════╝╚██╗██╔╝
██║  ███╗██║   ██║   ██████╔╝██║     █████╗   ╚███╔╝ 
██║   ██║██║   ██║   ██╔═══╝ ██║     ██╔══╝   ██╔██╗ 
╚██████╔╝██║   ██║   ██║     ███████╗███████╗██╔╝ ██╗
 ╚═════╝ ╚═╝   ╚═╝   ╚═╝     ╚══════╝╚══════╝╚═╝  ╚═╝
"""

def print_welcome() -> None:
    """Print welcome message and guide."""
    console.print(Panel(BANNER, style="cyan", border_style="blue"))
    
    welcome_panel = Panel.fit(
        "[title]Welcome to GitPlex![/]\n\n"
        "🔄 The smart Git profile manager that helps you maintain multiple Git identities.\n\n"
        "[subtitle]Features:[/]\n"
        "• 🔐 Secure profile management\n"
        "• 🔄 Easy profile switching\n"
        "• 🌐 Multi-provider support (GitHub, GitLab, BitBucket)\n"
        "• 📂 Workspace organization\n"
        "• 🔑 Automatic SSH key management\n\n"
        "[subtitle]What GitPlex will do:[/]\n"
        "• Create and manage Git configurations for each profile\n"
        "• Generate and configure SSH keys automatically\n"
        "• Organize your workspaces by profile\n"
        "• Backup existing configurations for safety\n\n"
        "[warning]Note: This will modify your Git and SSH configurations.[/]\n"
        "Make sure you understand the changes being made.",
        title="GitPlex",
        border_style="blue",
    )
    console.print(welcome_panel)


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


def print_info(message: str) -> None:
    """Print an informational message."""
    panel = Panel.fit(
        f"ℹ️  {message}",
        style="info",
        border_style="blue",
    )
    console.print(panel)


def confirm_action(message: str, default: bool = True) -> bool:
    """Ask for user confirmation."""
    return Confirm.ask(f"[highlight]{message}[/] [y/n]", default=default)


def get_user_input(prompt: str, default: str | None = None) -> str:
    """Get user input with optional default value."""
    styled_prompt = f"[highlight]{prompt}[/]"
    if default:
        # Escape any square brackets in the default value
        escaped_default = str(default).replace("[", "\\[").replace("]", "\\]")
        return Prompt.ask(f"{styled_prompt} ({escaped_default})") or default
    return Prompt.ask(styled_prompt)


def print_profile_table(profiles: list[dict[str, Any]]) -> None:
    """Print a table of profiles."""
    table = Table(
        title="[title]Git Profiles[/]",
        show_header=True,
        header_style="bold cyan",
        border_style="blue",
    )

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

    console.print("\n")
    console.print(table)
    console.print("\n")


def print_backup_info(backup_path: Path, config_type: str) -> None:
    """Print information about backup creation."""
    # Escape path for display
    escaped_path = str(backup_path).replace("[", "\\[").replace("]", "\\]")
    print_success(f"{config_type} backup created successfully")
    print_info(
        f"[path]Backup location:[/] {escaped_path}\n\n"
        "You can restore this backup later using:\n"
        f"[command]gitplex restore {escaped_path} --type "
        f"{config_type.split()[0].lower()}[/]"
    )


def suggest_workspace_directory(profile_name: str) -> str:
    """Suggest a workspace directory based on profile name."""
    home = Path.home()
    suggestions = [
        home / "Projects" / profile_name,
        home / "Code" / profile_name,
        home / "Workspace" / profile_name,
        home / profile_name,
    ]

    # Try to find or create a suitable directory
    for path in suggestions:
        if path.exists() and path.is_dir():
            return str(path)
        elif not path.exists() and path.parent.exists():
            return str(path)

    # Default to home directory with profile name
    return str(home / profile_name)


def prompt_directory(profile_name: str = "") -> str:
    """Prompt for a directory path and ensure it exists."""
    suggested_dir = suggest_workspace_directory(profile_name)

    while True:
        dir_path = get_user_input(
            "Enter workspace directory",
            default=suggested_dir,
        )
        try:
            path = Path(dir_path).resolve()
            if not path.exists():
                # Escape path for display
                escaped_path = str(path).replace("[", "\\[").replace("]", "\\]")
                if confirm_action(f"Directory {escaped_path} does not exist. Create it?"):
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    continue
            return str(path)
        except Exception as e:
            # Escape error message
            error_msg = str(e).replace("[", "\\[").replace("]", "\\]")
            print_error("Invalid directory path", error_msg)
            if not confirm_action("Try again?"):
                raise SystemConfigError("Directory setup failed") from e


def prompt_name() -> str:
    """Prompt for profile name."""
    print_info(
        "Choose a name for your Git profile\n"
        "Examples: personal, work, opensource"
    )
    return get_user_input("Enter profile name")


def prompt_email() -> str:
    """Prompt for Git email."""
    print_info(
        "Enter the email address for this Git profile\n"
        "This will be used in your commits"
    )
    return get_user_input("Enter Git email")


def prompt_username() -> str:
    """Prompt for Git username."""
    print_info(
        "Enter your Git username for this profile\n"
        "This will be used in your commits"
    )
    return get_user_input("Enter Git username")


def prompt_providers(default: str = "github") -> list[str]:
    """Prompt for Git providers."""
    providers = ["github", "gitlab", "bitbucket"]
    print_info(
        "Choose your Git provider(s)\n"
        "Available providers: " + ", ".join(f"[highlight]{p}[/]" for p in providers)
    )
    provider = get_user_input(
        "Enter Git provider",
        default=default,
    )
    if provider not in providers:
        print_warning(f"Invalid provider '{provider}', using default: {default}")
        provider = default
    return [provider]


def confirm_backup() -> bool:
    """Confirm backup creation."""
    return confirm_action(
        "Existing Git configurations found. Would you like to back them up?",
    )


def print_ssh_key(public_key: str, provider: str) -> None:
    """Print SSH public key in a formatted panel with copy instructions."""
    # Format the key with syntax highlighting
    key_syntax = Syntax(public_key, "ssh-key", theme="monokai", word_wrap=True)
    
    # Create a panel with the key and instructions
    key_panel = Panel.fit(
        f"[bold]Your SSH Public Key for {provider.title()}[/]\n\n"
        f"{key_syntax}\n\n"
        "[subtitle]Instructions:[/]\n"
        "1. Copy the entire key above (including ssh-ed25519/ssh-rsa prefix)\n"
        "2. Go to your Git provider's SSH key settings\n"
        "3. Add a new SSH key and paste the copied content\n"
        "4. Give it a memorable name (e.g., 'GitPlex Key')\n\n"
        "[info]Tip: The key has been formatted for easy copying[/]",
        title="🔑 SSH Key",
        border_style="green",
    )
    
    console.print("\n")
    console.print(key_panel)
    console.print("\n")
