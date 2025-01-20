"""UI module for GitPlex."""

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import git
from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from .ascii_art import BANNER
from .exceptions import GitplexError
from .ssh import SSHKey
from .ui_common import (
    console,
    print_error,
    print_info,
    print_success,
    print_warning,
    confirm_action,
)
from .version import __version__

def print_welcome() -> None:
    """Print welcome message and banner."""
    # Clear screen for better presentation
    console.clear()
    
    # Print banner with version
    console.print(f"\n[bold cyan]{BANNER}[/bold cyan]")
    console.print(f"\n[dim]Version {__version__}[/dim]")
    
    # Welcome message
    welcome_text = """
    Welcome to GitPlex! 🚀
    
    GitPlex helps you manage multiple Git identities and workspaces.
    Let's get you set up with a new Git profile.
    """
    welcome_panel = Panel(
        Markdown(welcome_text),
        title="[bold]Welcome[/bold]",
        border_style="cyan",
    )
    console.print(welcome_panel)
    
    # System info - minimal but useful
    console.print("[dim]System:[/dim] " + get_system_info())
    console.print("[dim]Git:[/dim] " + get_git_version())
    console.print("\n")
    
    # Start process
    console.print("[bold cyan]Ready to start? Let's set up your first Git profile![/bold cyan]")
    console.print("\n[dim]Choose a profile name (e.g., personal, work, opensource)[/dim]")
    console.print()

def print_setup_steps() -> None:
    """Print setup steps overview."""
    console.print("\n[bold]Setup Steps:[/bold]")
    console.print("\n")
    steps = [
        ("1. Profile", "Git identity"),
        ("2. SSH", "Authentication"),
        ("3. Workspace", "Project directories"),
        ("4. Verify", "Test configuration")
    ]
    
    for step, desc in steps:
        console.print(f"[blue]{step}[/blue] - {desc}")
    console.print()

def print_system_info() -> None:
    """Print minimal system information."""
    sys_info = Table.grid(padding=1)
    sys_info.add_column(style="blue")
    sys_info.add_column()
    
    sys_info.add_row("System", get_system_info())
    sys_info.add_row("Git", get_git_version())
    
    console.print(sys_info)

def get_system_info() -> str:
    """Get system information."""
    import platform
    return platform.platform()

def get_git_version() -> str:
    """Get Git version."""
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitplexError("Failed to get Git version") from e

def prompt_name() -> str:
    """Prompt for profile name."""
    while True:
        name = Prompt.ask(
            "[cyan]Profile name[/cyan]",
            default="personal"
        ).strip().lower()
        
        if not name:
            print_error("Profile name cannot be empty")
            continue
        
        if not name.isalnum() and not name.replace("_", "").isalnum():
            print_error("Profile name must be alphanumeric (underscores allowed)")
            continue
        
        return name

def prompt_email() -> str:
    """Prompt for Git email."""
    while True:
        email = Prompt.ask("[cyan]Git email[/cyan]").strip()
        
        if not email:
            print_error("Email cannot be empty")
            continue
        
        if "@" not in email:
            print_error("Invalid email format")
            continue
        
        return email

def prompt_username() -> str:
    """Prompt for Git username."""
    while True:
        username = Prompt.ask("[cyan]Git username[/cyan]").strip()
        
        if not username:
            print_error("Username cannot be empty")
            continue
        
        return username

def prompt_directory(default: str | None = None) -> Path:
    """Prompt for workspace directory."""
    if default is None:
        default = str(Path.home() / "Projects")
    
    print_info(f"Default workspace directory: {default}")
    
    while True:
        directory = Prompt.ask(
            "[cyan]Workspace directory[/cyan]",
            default=default
        )
        
        try:
            path = Path(directory).expanduser().resolve()
            
            # Create directory if it doesn't exist
            if not path.exists():
                if Confirm.ask(f"Directory {path} does not exist. Create it?"):
                    path.mkdir(parents=True)
                else:
                    continue
            
            # Check if directory is writable
            if not os.access(path, os.W_OK):
                print_error(f"Directory {path} is not writable")
                continue
            
            return path
            
        except Exception as e:
            print_error(f"Invalid directory: {e}")

def prompt_providers() -> list[str]:
    """Prompt for Git providers."""
    providers = ["github", "gitlab", "bitbucket", "azure", "other"]
    
    # Show available providers
    console.print("\n[cyan]Available providers:[/cyan]")
    for i, provider in enumerate(providers, 1):
        console.print(f"  {i}. {provider}")
    
    while True:
        choice = Prompt.ask(
            "[cyan]Choose provider (1-5)[/cyan]",
            default="1"
        )
        
        try:
            index = int(choice) - 1
            if 0 <= index < len(providers):
                return [providers[index]]
            else:
                print_error("Invalid choice")
        except ValueError:
            print_error("Please enter a number")

def print_profile_table(profiles: list[dict[str, Any]]) -> None:
    """Print profiles in a table format."""
    table = Table(
        title="Git Profiles",
        box=box.ROUNDED,
        header_style="bold cyan",
        border_style="blue"
    )
    
    table.add_column("Name", style="cyan")
    table.add_column("Email", style="green")
    table.add_column("Username", style="blue")
    table.add_column("Directory", style="magenta")
    table.add_column("Provider", style="yellow")
    table.add_column("Active", justify="center", style="bold green")
    
    for profile in profiles:
        table.add_row(
            profile["name"],
            profile["email"],
            profile["username"],
            str(profile["directories"][0]),  # Show primary directory
            profile["providers"][0],  # Show primary provider
            "✓" if profile["active"] else ""
        )
    
    console.print(table)
    console.print()

def print_git_config_info() -> None:
    """Print Git configuration information."""
    console.print("Git Configuration:", style="bold")
    console.print("• Global: ~/.gitconfig")
    console.print("• Local: .git/config")
    console.print("• System: /usr/local/etc/gitconfig")
    console.print()
    
    console.print("To verify your configuration, run:", style="bold")
    console.print("  git config --list --show-origin")
    console.print()

def print_ssh_key_info(key: SSHKey) -> None:
    """Print SSH key information."""
    panel = Panel(
        Text.assemble(
            Text("SSH Key Generated", style="bold green"),
            "\n\n",
            Text("Public Key: ", style="dim"),
            Text(str(key.public_key), style="cyan"),
            "\n",
            Text("Private Key: ", style="dim"),
            Text(str(key.private_key), style="blue"),
        ),
        title="[bold]SSH Key Info[/bold]",
        border_style="green",
    )
    console.print(panel)
    console.print()

def print_backup_info(backup_path: Path, config_type: str) -> None:
    """Print backup information."""
    console.print(f"\n[bold green]✓ {config_type} Backup Created[/bold green]")
    console.print("\n")
    console.print(f"[dim]Location:[/dim] [cyan]{backup_path}[/cyan]")
    console.print(f"[dim]Time:[/dim] [blue]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/blue]")
    console.print("\n")
