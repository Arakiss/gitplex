"""Terminal UI components and utilities."""

import subprocess
from pathlib import Path
from typing import Any, Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from .exceptions import SystemConfigError
from .ssh import SSHKey
from .ui_common import (
    confirm_action,
    console,
    print_error,
    print_info,
    print_success,
    print_warning,
)
from .providers import ProviderManager

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


def get_user_input(prompt: str, default: str | None = None, required: bool = False) -> str:
    """Get user input with optional default value.
    
    Args:
        prompt: The prompt to show to the user
        default: Optional default value
        required: Whether the input is required (can't be empty)
    """
    styled_prompt = f"[highlight]{prompt}[/]"
    while True:
        if default:
            # Escape any square brackets in the default value
            escaped_default = str(default).replace("[", "\\[").replace("]", "\\]")
            value = Prompt.ask(f"{styled_prompt} ({escaped_default})") or default
        else:
            value = Prompt.ask(styled_prompt)
        
        if required and not value:
            print_warning("This field is required. Please enter a value.")
            continue
        return value


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
        "Choose a name for your Git profile\nExamples: personal, work, opensource"
    )
    return get_user_input("Enter profile name", required=True)


def prompt_email() -> str:
    """Prompt for Git email."""
    print_info(
        "Enter the email address for this Git profile\n"
        "This will be used in your commits"
    )
    return get_user_input("Enter Git email", required=True)


def prompt_username() -> str:
    """Prompt for Git username."""
    print_info(
        "Enter your Git username for this profile\n"
        "This will be used in your commits"
    )
    return get_user_input("Enter Git username", required=True)


def prompt_providers() -> list[str]:
    """Prompt for Git providers.
    
    Returns:
        List of selected providers
    """
    valid_providers = ["github", "gitlab", "bitbucket", "azure"]
    providers = []
    
    while True:
        provider = Prompt.ask(
            "Enter Git provider",
            default="github",
            show_default=True,
        ).strip().lower()
        
        if provider not in valid_providers:
            print_warning(f"Invalid provider. Valid providers are: {', '.join(valid_providers)}")
            continue
            
        providers.append(provider)
        if not confirm_action("Add another provider?", default=False):
            break
    
    return providers


def print_ssh_key(key: SSHKey, provider: str | None = None) -> None:
    """Print SSH key information."""
    console.print(key.public_key_content + "\n", style="bold")
    
    # Get key fingerprint
    result = subprocess.run(
        ["ssh-keygen", "-l", "-f", str(key.public_key)],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        console.print(f"Key fingerprint: {result.stdout.strip()}", style="info")


def confirm_backup() -> bool:
    """Confirm backup creation."""
    return confirm_action(
        "Existing Git configurations found. Would you like to back them up?",
    )
