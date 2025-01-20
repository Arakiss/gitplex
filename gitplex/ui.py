"""UI module for GitPlex."""

import os
import subprocess
from collections.abc import Callable
from pathlib import Path

import git
from rich.box import box
from rich.columns import Columns
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from .ascii_art import BANNER
from .exceptions import GitplexError
from .ssh import SSHKey
from .version import __version__

console = Console()

def print_welcome() -> None:
    """Print welcome message with comprehensive setup guide."""
    # Header with banner
    console.print(BANNER, style="cyan")
    console.print()
    
    # Welcome message
    welcome_panel = Panel(
        "[bold cyan]Welcome to GitPlex[/bold cyan]\n"
        "Multiple Git Profile Manager\n\n"
        "[dim]Version: " + __version__ + "[/dim]",
        border_style="cyan",
        padding=(1, 2)
    )
    console.print(welcome_panel)
    console.print()
    
    # Main description
    description = (
        "GitPlex helps you maintain multiple Git identities with ease. Perfect for developers\n"
        "who work on different projects (work, personal, open-source) and need to keep their\n"
        "Git configurations separate and organized."
    )
    console.print(Panel(description, style="cyan", border_style="blue"))
    console.print()
    
    # Features in columns
    features = [
        Panel(
            "[bold]Profile Management[/bold]\n"
            "Create and switch between\n"
            "Git profiles easily",
            style="cyan"
        ),
        Panel(
            "[bold]SSH Keys[/bold]\n"
            "Automatic key generation\n"
            "and provider setup",
            style="cyan"
        ),
        Panel(
            "[bold]Workspaces[/bold]\n"
            "Isolate projects and\n"
            "their configurations",
            style="cyan"
        ),
        Panel(
            "[bold]Multi-Provider[/bold]\n"
            "Support for GitHub,\n"
            "GitLab, and more",
            style="cyan"
        )
    ]
    console.print(Columns(features))
    console.print()
    
    # System information
    print_system_info()
    
    # Setup steps
    print_setup_steps()
    
    # Next steps and help
    help_text = """
[bold cyan]Getting Started:[/bold cyan]
1. Choose a profile name (e.g., 'personal', 'work', 'opensource')
2. Follow the interactive setup process
3. Start using GitPlex with [cyan]gitplex use <profile>[/cyan]

[dim]Need help? Use [cyan]gitplex --help[/cyan] for more information[/dim]
    """
    console.print(Markdown(help_text))
    
    # Important notice
    console.print(Panel(
        "[yellow]⚠️  IMPORTANT:[/yellow] This tool modifies your Git and SSH configurations.\n"
        "While it creates backups by default, please review each step carefully.",
        border_style="yellow"
    ))
    
    # Prompt for profile name
    console.print("\n[bold cyan]Let's get started![/bold cyan]")
    console.print("[cyan]Choose a name for your Git profile[/cyan]")
    console.print("[dim cyan]Examples: personal, work, opensource[/dim cyan]")


def print_setup_steps() -> None:
    """Print setup steps overview."""
    table = Table(
        title="[bold]Setup Process[/bold]",
        box=box.ROUNDED,
        title_style="cyan",
        border_style="blue",
        padding=(0, 1)
    )
    
    table.add_column("Step", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Status", style="green", justify="center")
    
    steps = [
        ("Create profile", "Set up your Git identity", "Pending"),
        ("SSH keys", "Configure SSH authentication", "Pending"),
        ("Workspaces", "Set up project directories", "Pending"),
        ("Providers", "Connect Git providers", "Pending"),
        ("Verify", "Test configuration", "Pending")
    ]
    
    for step, desc, status in steps:
        table.add_row(step, desc, status)
    
    console.print()
    console.print(Panel(table, border_style="blue"))
    console.print()


def print_system_info() -> None:
    """Print system information in a clean format."""
    sys_info = Table.grid(padding=1)
    sys_info.add_column(style="cyan")
    sys_info.add_column(style="white")
    
    sys_info.add_row("System:", get_system_info())
    sys_info.add_row("Git Version:", get_git_version())
    
    console.print(Panel(
        sys_info,
        title="[bold]System Information[/bold]",
        border_style="blue"
    ))
    console.print()


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


def suggest_profile_name(email: str, provider: str) -> str:
    """Suggest a profile name based on email and provider."""
    # Extract username from email
    username = email.split("@")[0]
    domain = email.split("@")[1].split(".")[0]
    
    suggestions = []
    if domain in ["gmail", "hotmail", "outlook", "yahoo"]:
        suggestions.append(f"personal-{provider}")
    elif domain in ["edu", "ac"]:
        suggestions.append(f"academic-{provider}")
    else:
        suggestions.append(f"{domain}-{provider}")
    
    suggestions.append(f"{username}-{provider}")
    return suggestions[0]


def prompt_name(email: str | None = None, provider: str | None = None) -> str:
    """Smart profile name prompt with suggestions."""
    # Create examples panel
    examples = [
        ("personal-github", "For personal projects"),
        ("work-gitlab", "For work repositories"),
        ("opensource-github", "For open source contributions"),
        ("{company}-gitlab", "For company-specific work"),
        ("{project}-bitbucket", "For project-specific repos"),
    ]
    
    # Create a table with examples
    table = Table(box=box.ROUNDED, show_header=False, padding=(0, 2))
    for name, desc in examples:
        table.add_row(f"• {name}", Text(desc, style="dim"))
    
    # Get suggested name if possible
    suggested_name = ""
    if email and provider:
        suggested_name = suggest_profile_name(email, provider)
    
    # Create the main panel content
    content = [
        Text("Choose a descriptive name for your Git profile", style="bold cyan"),
        Text("\nThis will help you organize your different Git identities.", style="dim"),
        Text("\nExamples:", style="cyan"),
    ]
    
    # Add examples as text lines
    for name, desc in examples:
        content.append(Text(f"\n• {name}", style="green"))
        content.append(Text(f" - {desc}", style="dim"))
    
    # Add suggestion if available
    if suggested_name:
        content.append(Text(f"\n\nSuggested: {suggested_name}", style="blue"))
    
    # Create and show the panel
    panel = Panel(
        "\n".join(str(line) for line in content),
        title="Profile Name",
        border_style="cyan"
    )
    console.print(panel)
    console.print()
    
    # Get user input
    while True:
        name = get_user_input(
            "Enter profile name",
            default=suggested_name if suggested_name else None,
            required=True
        )
        
        # Validate name
        if "/" in name or "\\" in name:
            print_error("Profile name cannot contain '/' or '\\'")
            continue
            
        return name


def detect_git_providers() -> list[str]:
    """Detect potential Git providers from existing remotes."""
    try:
        repo = git.Repo(os.getcwd())
        remotes = repo.remotes
        providers = set()
        
        for remote in remotes:
            url = remote.url
            if "github.com" in url:
                providers.add("github")
            elif "gitlab.com" in url:
                providers.add("gitlab")
            elif "bitbucket.org" in url:
                providers.add("bitbucket")
            elif "dev.azure.com" in url:
                providers.add("azure")
        
        return sorted(list(providers))
    except (git.exc.InvalidGitRepositoryError, git.exc.NoSuchPathError) as e:
        raise GitplexError("Not a valid Git repository") from e


def prompt_providers() -> list[str]:
    """Prompt for Git providers.
    
    Returns:
        List of selected providers
    """
    valid_providers = {
        "github": "GitHub - For open source and personal projects",
        "gitlab": "GitLab - For enterprise and self-hosted repos",
        "bitbucket": "Bitbucket - For team collaboration",
        "azure": "Azure DevOps - For Microsoft ecosystem"
    }
    
    # Create provider panels
    provider_panels = []
    for provider, description in valid_providers.items():
        provider_panels.append(
            Panel(
                f"[bold]{provider.title()}[/]\n{description}",
                style="cyan",
                border_style="blue"
            )
        )
    
    # Show provider options
    console.print("\n[bold cyan]Available Git Providers:[/]")
    console.print(Columns(provider_panels))
    
    providers = []
    while True:
        provider = Prompt.ask(
            "\nEnter Git provider",
            default="github",
            show_default=True
        ).strip().lower()
        
        if provider not in valid_providers:
            print_warning(f"Invalid provider. Valid providers are: {', '.join(valid_providers.keys())}")
            continue
        
        providers.append(provider)
        if not confirm_action("Add another provider?", default=False):
            break
    
    return providers


def get_user_input(
    prompt: str,
    default: str | None = None,
    required: bool = False,
) -> str:
    """Get user input with validation."""
    while True:
        try:
            value = Prompt.ask(prompt, default=default or "")
            if required and not value:
                console.print("  ⚠️  This field is required", style="red")
                continue
            return value
        except KeyboardInterrupt:
            raise GitplexError("Operation cancelled by user") from None


def confirm_action(prompt: str, default: bool = True) -> bool:
    """Confirm an action with the user."""
    try:
        return Confirm.ask(prompt, default=default)
    except KeyboardInterrupt:
        raise GitplexError("Operation cancelled by user") from None


def prompt_directory(
    message: str = "Enter directory path",
    default: str | None = None,
    create: bool = False,
) -> Path:
    """Prompt user for a directory path."""
    while True:
        path_str = get_user_input(message, default=default)
        path = Path(path_str).expanduser().resolve()

        if path.exists() and path.is_dir():
            return path
        elif create:
            try:
                path.mkdir(parents=True, exist_ok=True)
                return path
            except OSError as e:
                console.print(f"[red]Error creating directory: {e}[/red]")
        else:
            console.print("[red]Directory does not exist.[/red]")


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


def print_git_config_preview(
    profile_name: str,
    email: str,
    username: str,
    workspace_dirs: list[Path],
) -> None:
    """Print Git configuration preview."""
    panel = Panel(
        Text.assemble(
            Text("Git Configuration Preview", style="bold"),
            "\n\n",
            Text("Profile: ", style="dim"),
            Text(profile_name, style="cyan"),
            "\n",
            Text("Email: ", style="dim"),
            Text(email, style="cyan"),
            "\n",
            Text("Username: ", style="dim"),
            Text(username, style="cyan"),
            "\n",
            Text("Workspace Directories:", style="dim"),
            *[Text(f"\n  • {d}", style="blue") for d in workspace_dirs],
        ),
        title="[bold]Git Config[/bold]",
        border_style="blue",
    )
    console.print(panel)
    console.print()


def print_git_setup_summary(profile_name: str, workspace_dirs: list[Path]) -> None:
    """Print a summary of Git setup."""
    panel = Panel(
        Text.assemble(
            Text("Git Setup Complete", style="bold green"),
            "\n\n",
            Text("Profile: ", style="dim"),
            Text(profile_name, style="cyan"),
            "\n",
            Text("Workspace Directories:", style="dim"),
            *[Text(f"\n  • {d}", style="blue") for d in workspace_dirs],
        ),
        title="[bold]Setup Summary[/bold]",
        border_style="green",
    )
    console.print(panel)
    console.print()


def print_banner() -> None:
    """Print the application banner."""
    console.print(
        Panel(
            Text(BANNER, style="bold blue"),
            subtitle=f"[dim]v{__version__}[/dim]",
            border_style="blue",
        )
    )
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


def confirm_git_setup() -> bool:
    """Confirm Git setup with the user."""
    panel = Panel(
        Text.assemble(
            Text("This will:", style="bold"),
            "\n",
            Text("• Configure Git for the selected directories", style="green"),
            "\n",
            Text("• Generate SSH keys if needed", style="green"),
            "\n",
            Text("• Set up Git provider access", style="green"),
        ),
        title="[bold]Git Setup[/bold]",
        border_style="blue",
    )
    console.print(panel)
    return confirm_action("Proceed with Git setup?")


def prompt_email() -> str:
    """Prompt for Git email."""
    return get_user_input("Enter Git email", required=True)


def prompt_username() -> str:
    """Prompt for Git username."""
    return get_user_input("Enter Git username", required=True)


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"ℹ️  {message}", style="blue")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"⚠️  {message}", style="yellow")


def print_error(message: str, details: str | None = None) -> None:
    """Print an error message with optional details."""
    if details:
        console.print(
            Panel(
                f"{message}\n\n{details}",
                title="[red]Error[/red]",
                border_style="red",
            )
        )
    else:
        console.print(f"❌ {message}", style="red")


def print_profile_info(profile: dict[str, str]) -> None:
    """Print profile information."""
    table = Table(
        title="Profile Information",
        show_header=True,
        header_style="bold magenta",
        box=box.ROUNDED,
    )
    
    table.add_column("Setting", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")
    
    for key, value in profile.items():
        if key != "name":  # Name is shown in the title
            table.add_row(key.replace("_", " ").title(), str(value))
    
    console.print(table)
    console.print()

    # Show Git config locations
    console.print("\n🔧 Git Configurations:", style="bold")
    for workspace in profile["directories"]:
        console.print(f"  • {workspace}/.gitconfig")


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
