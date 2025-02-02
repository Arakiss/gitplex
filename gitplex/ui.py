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
from .gpg import GPGKey
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
    
    # Welcome message with improved styling
    welcome_panel = Panel(
        Text.assemble(
            Text("Welcome to GitPlex! 🚀\n\n", style="bold cyan"),
            Text("GitPlex helps you manage multiple Git identities and workspaces.\n", style="white"),
            Text("Let's get you set up with a new Git profile.", style="white"),
        ),
        title="[bold cyan]Welcome[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(welcome_panel)
    
    # System info in a nice table
    sys_info = Table(box=box.ROUNDED, show_header=False, border_style="blue")
    sys_info.add_column("Component", style="dim")
    sys_info.add_column("Details", style="green")
    sys_info.add_row("System", get_system_info())
    sys_info.add_row("Git", get_git_version())
    console.print(sys_info)
    
    # Status checks with icons
    console.print("\n[bold cyan]🔍 System Check[/bold cyan]")
    status_table = Table(box=box.ROUNDED, show_header=False, border_style="green", padding=(0, 1))
    status_table.add_column("Check", style="dim")
    status_table.add_column("Status", style="green")
    
    status_table.add_row("Git Installation", "[green]✓[/green] Git is installed")
    status_table.add_row("SSH Installation", "[green]✓[/green] SSH is installed")
    status_table.add_row("SSH Agent", "[green]✓[/green] SSH agent is running")
    status_table.add_row("System Compatibility", "[green]✓[/green] System compatibility check passed")
    
    console.print(status_table)
    console.print()
    
    # Start process with clear next steps
    console.print("\n[bold cyan]🚀 Let's Get Started![/bold cyan]")
    console.print("[dim]Choose a profile name (e.g., personal, work, opensource)[/dim]")
    console.print()

def print_setup_steps() -> None:
    """Print setup completion steps with improved formatting."""
    # Header
    console.print("\n[bold green]🎉 Setup Complete![/bold green]")
    
    # Configuration Summary Panel
    config_panel = Panel(
        Text.assemble(
            Text("✅ Git Profile Created\n", style="green"),
            Text("✅ SSH Key Generated\n", style="green"),
            Text("✅ GPG Key Generated\n", style="green"),
            Text("✅ Git Config Updated\n", style="green"),
            Text("✅ SSH Config Updated\n", style="green"),
            Text("✅ SSH Agent Configured\n", style="green"),
            Text("✅ Commit Signing Enabled", style="green"),
        ),
        title="[bold]Configuration Status[/bold]",
        border_style="green",
    )
    console.print(config_panel)
    
    # Next Steps Panel
    next_steps = Panel(
        Text.assemble(
            Text("1. ", style="yellow"),
            Text("Add your SSH key to your Git provider\n", style="white"),
            Text("   • ", style="dim"),
            Text("The key has been copied to your clipboard\n", style="white"),
            Text("   • ", style="dim"),
            Text("Follow the instructions above to add it\n", style="white"),
            "\n",
            Text("2. ", style="yellow"),
            Text("Add your GPG key to GitHub\n", style="white"),
            Text("   • ", style="dim"),
            Text("Go to GitHub Settings > SSH and GPG keys\n", style="white"),
            Text("   • ", style="dim"),
            Text("Add both your SSH and GPG keys\n", style="white"),
            "\n",
            Text("3. ", style="yellow"),
            Text("Test your setup\n", style="white"),
            Text("   • ", style="dim"),
            Text("SSH: ", style="white"),
            Text("ssh -T git@github.com\n", style="cyan"),
            Text("   • ", style="dim"),
            Text("GPG: ", style="white"),
            Text("git commit --allow-empty -m \"test signed commit\"\n", style="cyan"),
            "\n",
            Text("4. ", style="yellow"),
            Text("Start using your new profile\n", style="white"),
            Text("   • ", style="dim"),
            Text("Your workspace is ready for Git operations\n", style="white"),
            Text("   • ", style="dim"),
            Text("All commits will be automatically signed\n", style="white"),
        ),
        title="[bold]🚀 Next Steps[/bold]",
        border_style="cyan",
    )
    console.print(next_steps)
    
    # Quick Reference Panel
    quick_ref = Panel(
        Text.assemble(
            Text("Common Commands:", style="bold yellow"),
            "\n\n",
            Text("• ", style="dim"),
            Text("Switch profiles: ", style="white"),
            Text("gitplex switch <profile>\n", style="cyan"),
            Text("• ", style="dim"),
            Text("List profiles: ", style="white"),
            Text("gitplex list\n", style="cyan"),
            Text("• ", style="dim"),
            Text("Show current profile: ", style="white"),
            Text("gitplex current\n", style="cyan"),
            Text("• ", style="dim"),
            Text("Update profile: ", style="white"),
            Text("gitplex update <profile>\n", style="cyan"),
            Text("• ", style="dim"),
            Text("Verify commit signing: ", style="white"),
            Text("git log --show-signature", style="cyan"),
        ),
        title="[bold]📝 Quick Reference[/bold]",
        border_style="yellow",
    )
    console.print(quick_ref)
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
    """Prompt for profile name with helpful hints."""
    console.print("\n[cyan]📝 Profile Name[/cyan]")
    console.print(
        "[dim]Choose a name for your Git profile (e.g., personal, work, opensource)\n"
        "This will be used to organize your Git configurations and SSH keys.[/dim]"
    )
    
    while True:
        name = Prompt.ask("[cyan]Profile name[/cyan]").strip()
        if name and name.isalnum():
            return name
        print_error("Profile name must be alphanumeric")

def prompt_email() -> str:
    """Prompt for Git email with helpful hints."""
    console.print("\n[cyan]📧 Git Email[/cyan]")
    console.print(
        "[dim]Enter the email address associated with your Git account\n"
        "This will be used for your Git commits and SSH keys.[/dim]"
    )
    
    while True:
        email = Prompt.ask("[cyan]Git email[/cyan]").strip()
        if "@" in email and "." in email:
            return email
        print_error("Please enter a valid email address")

def prompt_username() -> str:
    """Prompt for Git username with helpful hints."""
    console.print("\n[cyan]👤 Git Username[/cyan]")
    console.print(
        "[dim]Enter your Git username\n"
        "This is the username you use to login to your Git provider.[/dim]"
    )
    
    while True:
        username = Prompt.ask("[cyan]Git username[/cyan]").strip()
        if username:
            return username
        print_error("Please enter a valid username")

def prompt_directory(default: str | None = None) -> Path:
    """Prompt for workspace directory with helpful hints."""
    if default is None:
        default = str(Path.home() / "Projects")
    
    console.print("\n[cyan]📁 Workspace Directory[/cyan]")
    console.print(
        "[dim]Choose where to store your Git repositories\n"
        f"Default location: {default}[/dim]"
    )
    
    while True:
        directory = Prompt.ask(
            "[cyan]Workspace directory[/cyan]",
            default=default
        )
        
        try:
            path = Path(directory).expanduser().resolve()
            
            # Create directory if it doesn't exist
            if not path.exists():
                if Confirm.ask(f"Directory {path} does not exist. Create it? 📁"):
                    path.mkdir(parents=True)
                else:
                    continue
            
            # Check if directory is writable
            if not os.access(path, os.W_OK):
                print_error(f"Directory {path} is not writable 🚫")
                continue
            
            return path
            
        except Exception as e:
            print_error(f"Invalid directory: {e}")

def prompt_providers() -> str:
    """Prompt for Git provider name with helpful hints."""
    console.print("\n[cyan]🌐 Git Provider[/cyan]")
    console.print(
        "[dim]Available providers:[/dim]"
    )
    
    # Show available providers
    providers_table = Table(box=box.ROUNDED, show_header=False, border_style="blue")
    providers_table.add_column("Provider", style="cyan")
    providers_table.add_column("Description", style="white")
    
    providers_table.add_row(
        "github",
        "GitHub - github.com"
    )
    providers_table.add_row(
        "gitlab",
        "GitLab - gitlab.com"
    )
    providers_table.add_row(
        "bitbucket",
        "Bitbucket - bitbucket.org"
    )
    providers_table.add_row(
        "azure",
        "Azure DevOps - dev.azure.com"
    )
    
    console.print(providers_table)
    
    valid_providers = ["github", "gitlab", "bitbucket", "azure"]
    
    while True:
        provider = Prompt.ask(
            "[cyan]Provider name[/cyan]",
            default="github"
        ).strip().lower()
        
        if provider in valid_providers:
            return provider
        
        print_error(
            f"Invalid provider: {provider}\n"
            "Please choose from: github, gitlab, bitbucket, azure"
        )

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

def print_git_config_info(workspace_dir: Path) -> None:
    """Print Git configuration information with detailed explanations."""
    # Header
    console.print("\n[bold cyan]🔧 Git Configuration Overview[/bold cyan]")
    
    # Configuration Files Panel
    config_files = Panel(
        Text.assemble(
            Text("Git uses a layered configuration system:\n\n", style="white"),
            Text("1. ", style="yellow"),
            Text("System Config ", style="white"),
            Text("(/usr/local/etc/gitconfig)\n", style="dim"),
            Text("   • ", style="dim"),
            Text("Applied to all users on the system\n", style="white"),
            "\n",
            Text("2. ", style="yellow"),
            Text("Global Config ", style="white"),
            Text("(~/.gitconfig)\n", style="dim"),
            Text("   • ", style="dim"),
            Text("Your user-level settings\n", style="white"),
            Text("   • ", style="dim"),
            Text("Managed by GitPlex\n", style="white"),
            "\n",
            Text("3. ", style="yellow"),
            Text("Profile Config ", style="white"),
            Text(f"({workspace_dir}/.gitconfig)\n", style="dim"),
            Text("   • ", style="dim"),
            Text("Profile-specific settings\n", style="white"),
            Text("   • ", style="dim"),
            Text("Automatically included based on directory\n", style="white"),
        ),
        title="[bold]📁 Configuration Files[/bold]",
        border_style="blue",
    )
    console.print(config_files)
    
    # Verification Commands Panel
    verify_panel = Panel(
        Text.assemble(
            Text("Useful commands to verify your setup:\n\n", style="white"),
            Text("• ", style="dim"),
            Text("Show all settings: \n", style="white"),
            Text("  git config --list --show-origin\n", style="cyan"),
            "\n",
            Text("• ", style="dim"),
            Text("Show current user email: \n", style="white"),
            Text("  git config user.email\n", style="cyan"),
            "\n",
            Text("• ", style="dim"),
            Text("Show current username: \n", style="white"),
            Text("  git config user.name\n", style="cyan"),
            "\n",
            Text("• ", style="dim"),
            Text("Show SSH command: \n", style="white"),
            Text("  git config core.sshCommand", style="cyan"),
        ),
        title="[bold]🔍 Verify Configuration[/bold]",
        border_style="yellow",
    )
    console.print(verify_panel)
    
    # Tips Panel
    tips_panel = Panel(
        Text.assemble(
            Text("💡 Tips:\n\n", style="bold yellow"),
            Text("• ", style="dim"),
            Text("Git uses the most specific config that applies\n", style="white"),
            Text("• ", style="dim"),
            Text("Profile settings override global settings\n", style="white"),
            Text("• ", style="dim"),
            Text("Repository settings (in .git/config) override all\n", style="white"),
            Text("• ", style="dim"),
            Text("Use ", style="white"),
            Text("gitplex current", style="cyan"),
            Text(" to see active profile", style="white"),
        ),
        title="[bold]💭 Good to Know[/bold]",
        border_style="green",
    )
    console.print(tips_panel)
    console.print()

def print_ssh_key_info(key: SSHKey) -> None:
    """Print SSH key information with clear instructions for both personal and organizational use."""
    # Header
    console.print("\n[bold green]🔑 SSH Key Generated Successfully![/bold green]")
    
    # Public Key Panel - Made More Prominent
    public_key = key.get_public_key()
    public_key_panel = Panel(
        Text.assemble(
            Text("Your SSH Public Key:\n", style="bold yellow"),
            Text("─" * 50 + "\n", style="dim"),
            Text(public_key, style="bold green"),
            Text("\n" + "─" * 50, style="dim"),
            Text("\n💡 This key has been copied to your clipboard", style="cyan"),
            Text("\n💡 Save this key somewhere safe - you'll need it to set up your Git provider", style="cyan"),
        ),
        title="[bold]📋 SSH Public Key[/bold]",
        border_style="yellow",
        padding=(1, 2),
    )
    console.print(public_key_panel)
    
    # GitHub-specific Instructions
    github_steps = Panel(
        Text.assemble(
            Text("Setting up SSH access for GitHub:\n\n", style="bold white"),
            Text("1. Personal Account Setup:\n", style="bold cyan"),
            Text("   • Go to ", style="white"),
            Text("https://github.com/settings/keys\n", style="blue underline"),
            Text("   • Click 'New SSH Key'\n", style="white"),
            Text("   • Title: ", style="white"),
            Text(f"GitPlex {key.profile_name} - {key.provider}\n", style="green"),
            Text("   • Key type: Authentication Key\n", style="white"),
            Text("   • Paste the key shown above and save\n\n", style="white"),
            Text("2. Organization Access (if needed):\n", style="bold cyan"),
            Text("   • Go to your organization settings\n", style="white"),
            Text("   • Navigate to ", style="white"),
            Text("Settings > Security > SSH Keys\n", style="blue"),
            Text("   • Add the same SSH key\n", style="white"),
            Text("   • Title: ", style="white"),
            Text(f"GitPlex {key.profile_name} - Organization\n", style="green"),
            "\n",
            Text("💡 Tips:\n", style="bold yellow"),
            Text("• One SSH key can be used for both personal and org access\n", style="white"),
            Text("• Make sure you have the right organization permissions\n", style="white"),
            Text("• Test access with: ", style="white"),
            Text("ssh -T git@github.com", style="cyan"),
        ),
        title="[bold]🚀 GitHub SSH Setup Guide[/bold]",
        border_style="green",
        padding=(1, 2),
    )
    console.print(github_steps)
    
    # Key Details Panel
    key_info = Panel(
        Text.assemble(
            Text("Type: ", style="dim"),
            Text(key.key_type.upper(), style="blue"),
            Text(" | ", style="dim"),
            Text("Profile: ", style="dim"),
            Text(key.profile_name, style="blue"),
            Text(" | ", style="dim"),
            Text("Location: ", style="dim"),
            Text(str(key.private_key.parent), style="blue"),
        ),
        title="[bold]ℹ️ Key Details[/bold]",
        border_style="blue",
        padding=(1, 2),
    )
    console.print(key_info)
    console.print()

def print_gpg_key_info(key: "GPGKey") -> None:
    """Print GPG key information with clear instructions."""
    # Header
    console.print("\n[bold green]🔒 GPG Key Generated Successfully![/bold green]")
    
    # Key Details Panel
    key_info = Panel(
        Text.assemble(
            Text("Key ID: ", style="dim"),
            Text(key.key_id, style="blue"),
            Text(" | ", style="dim"),
            Text("Name: ", style="dim"),
            Text(key.name, style="blue"),
            Text(" | ", style="dim"),
            Text("Email: ", style="dim"),
            Text(key.email, style="blue"),
        ),
        title="[bold]🔑 Key Details[/bold]",
        border_style="blue",
    )
    console.print(key_info)
    
    # GitHub Instructions Panel
    github_steps = Panel(
        Text.assemble(
            Text("Setting up GPG signing for GitHub:\n\n", style="bold white"),
            Text("1. Add GPG Key to GitHub:\n", style="bold cyan"),
            Text("   • Go to ", style="white"),
            Text("https://github.com/settings/keys\n", style="blue underline"),
            Text("   • Click 'New GPG Key'\n", style="white"),
            Text("   • Paste your GPG public key (already copied to clipboard)\n\n", style="white"),
            Text("2. Verify Setup:\n", style="bold cyan"),
            Text("   • Make a test commit: ", style="white"),
            Text("git commit -m \"test signed commit\"\n", style="cyan"),
            Text("   • Check signature: ", style="white"),
            Text("git log --show-signature\n", style="cyan"),
            "\n",
            Text("💡 Tips:\n", style="bold yellow"),
            Text("• Your commits will be automatically signed\n", style="white"),
            Text("• Look for the 'Verified' badge on GitHub\n", style="white"),
            Text("• Use ", style="white"),
            Text("-S", style="cyan"),
            Text(" flag to force signing: ", style="white"),
            Text("git commit -S -m \"message\"", style="cyan"),
        ),
        title="[bold]🚀 GPG Setup Guide[/bold]",
        border_style="green",
    )
    console.print(github_steps)
    console.print()

def print_backup_info(backup_path: Path, config_type: str) -> None:
    """Print backup information."""
    console.print(f"\n[bold green]✓ {config_type} Backup Created[/bold green]")
    console.print("\n")
    console.print(f"[dim]Location:[/dim] [cyan]{backup_path}[/cyan]")
    console.print(f"[dim]Time:[/dim] [blue]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/blue]")
    console.print("\n")
