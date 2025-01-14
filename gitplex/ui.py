"""Terminal UI components and utilities."""

import subprocess
from pathlib import Path
from typing import Any, Optional, Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.markdown import Markdown
from rich.columns import Columns
from rich.prompt import Prompt
from rich.align import Align
from rich.text import Text
from rich.style import Style

from .ascii_art import BANNER
from .version import __version__
from .exceptions import SystemConfigError
from .ssh import SSHKey

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
            check=True
        )
        return result.stdout.strip()
    except:
        return "Git not found"


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


def prompt_name(email: Optional[str] = None, provider: Optional[str] = None) -> str:
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


def detect_git_providers() -> List[str]:
    """Detect potential Git providers from existing remotes."""
    try:
        import git
        providers = set()
        for repo in git.Repo(".").remotes:
            url = repo.url
            if "github" in url:
                providers.add("github")
            elif "gitlab" in url:
                providers.add("gitlab")
            elif "bitbucket" in url:
                providers.add("bitbucket")
            elif "dev.azure.com" in url:
                providers.add("azure")
        return list(providers)
    except:
        return []


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
    default: Optional[str] = None,
    required: bool = False,
    completer: Optional[callable] = None,
) -> str:
    """Enhanced user input with auto-completion and validation."""
    prompt_style = "bold cyan"
    default_style = "italic yellow"
    
    prompt_text = Text()
    prompt_text.append(f"❯ {prompt}", style=prompt_style)
    
    if default:
        prompt_text.append(f" (default: {default})", style=default_style)
    
    console.print(prompt_text)
    
    # Show completion hints if available
    if completer:
        completions = completer()
        if completions:
            console.print(
                Text("💡 Tab to cycle through: ", style="dim") + 
                Text(", ".join(completions), style="blue dim")
            )
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        while True:
            progress.add_task("", description="")
            value = input("  ").strip()
            
            if not value:
                if default:
                    return default
                elif required:
                    console.print("  ⚠️  This field is required", style="red")
                    continue
                else:
                    return ""
            
            return value


def confirm_action(message: str, default: bool = True) -> bool:
    """Enhanced action confirmation with visual feedback."""
    style = "bold cyan"
    prompt = Text()
    prompt.append(f"❯ {message} ", style=style)
    prompt.append("[y/n]", style="italic yellow")
    if default:
        prompt.append(" (y)", style="dim")
    else:
        prompt.append(" (n)", style="dim")
    
    console.print(prompt)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        while True:
            progress.add_task("", description="")
            choice = input("  ").lower().strip()
            if not choice:
                return default
            if choice in ["y", "yes"]:
                return True
            if choice in ["n", "no"]:
                return False
            console.print("  ⚠️  Please answer 'y' or 'n'", style="red")


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


def print_backup_info(backup_path: Path, config_type: str = "configuration") -> None:
    """Print information about backup creation."""
    # Create a clean panel for backup information
    backup_info = [
        "[green]✓[/green] Backup created successfully",
        "",
        "[bold]Location:[/bold]",
        f"  {backup_path}",
        "",
        "[bold]Restore command:[/bold]",
        f"  gitplex restore {backup_path} --type {config_type.split()[0].lower()}"
    ]
    
    console.print(Panel(
        "\n".join(backup_info),
        title=f"[bold]{config_type} Backup[/bold]",
        border_style="green"
    ))
    console.print()  # Add spacing


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


def prompt_directory(default_path: str | Path | None = None) -> str:
    """Smart directory prompt with path validation."""
    if not default_path:
        default_path = Path.home() / "workspace"
    elif isinstance(default_path, str):
        default_path = Path(default_path)
    
    panel = Panel(
        Align.center(
            Text.assemble(
                Text("Choose a workspace directory for this profile", style="bold cyan"),
                "\n\n",
                Text("This directory will:", style="dim"),
                "\n",
                Text("• Store your Git repositories", style="green"),
                "\n",
                Text("• Use profile-specific Git config", style="green"),
                "\n",
                Text("• Help organize your work", style="green"),
                "\n\n",
                Text(f"Default: {default_path}", style="blue"),
            )
        ),
        title="Workspace Directory",
        box=box.ROUNDED,
    )
    console.print(panel)
    
    while True:
        dir_str = get_user_input(
            "Enter workspace directory",
            default=str(default_path),
            required=True
        )
        
        try:
            path = Path(dir_str).expanduser().resolve()
            # Create directory if it doesn't exist
            if not path.exists():
                if confirm_action(f"Directory {path} doesn't exist. Create it?", default=True):
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    continue
            return str(path)
        except Exception as e:
            console.print(f"  ⚠️  Invalid path: {e}", style="red")


def print_git_config_preview(profile_name: str, email: str, username: str, workspace_dir: Path) -> None:
    """Print preview of Git configuration that will be created."""
    config_preview = f"""
[user]
    email = {email}
    name = {username}

[core]
    sshCommand = "ssh -i ~/.ssh/id_{profile_name}_ed25519"

[init]
    defaultBranch = main
"""
    
    panel = Panel(
        f"Git Configuration Preview for {workspace_dir}:\n{config_preview}",
        title="📝 Git Config",
        border_style="blue"
    )
    console.print(panel)


def print_git_setup_summary(profile_name: str, workspace_dirs: List[Path]) -> None:
    """Print summary of Git configuration setup."""
    console.print("\n=== Git Configuration Summary ===\n", style="bold blue")
    
    # Show global config changes
    console.print("🔧 Global Git Configuration:", style="bold")
    console.print(f"Location: ~/.gitconfig")
    console.print("Added workspace-specific configurations:")
    
    for workspace in workspace_dirs:
        console.print(f"  • {workspace}: Uses profile '{profile_name}' settings")
    
    console.print("\n🔍 To verify your configuration, run:", style="bold")
    console.print("  git config --list --show-origin")


def confirm_git_setup() -> bool:
    """Confirm Git configuration setup with user."""
    return confirm_action(
        "Would you like to proceed with Git configuration setup?",
        default=True
    )


def print_profile_info(profile: dict[str, Any]) -> None:
    """Print detailed profile information."""
    table = Table(title=f"Profile: {profile['name']}")
    
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Email", profile["email"])
    table.add_row("Username", profile["username"])
    table.add_row("Workspaces", "\n".join(str(d) for d in profile["directories"]))
    table.add_row("Providers", "\n".join(profile["providers"]))
    table.add_row("SSH Key", profile["ssh_key"] or "None")
    table.add_row("Status", "Active" if profile["active"] else "Inactive")
    
    console.print(table)
    
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


def confirm_backup() -> bool:
    """Confirm backup creation."""
    return confirm_action(
        "Existing Git configurations found. Would you like to back them up?",
    )


def prompt_email() -> str:
    """Smart email prompt with validation."""
    panel = Panel(
        Align.center(
            Text.assemble(
                Text("Enter the email address for this Git profile", style="bold cyan"),
                "\n\n",
                Text("This will be used in your Git commits and:", style="dim"),
                "\n",
                Text("• Signing your commits", style="green"),
                "\n",
                Text("• Identifying you to Git providers", style="green"),
                "\n",
                Text("• Suggesting profile names", style="green"),
            )
        ),
        title="Git Email",
        box=box.ROUNDED,
    )
    console.print(panel)
    
    while True:
        email = get_user_input("Enter Git email", required=True)
        if "@" not in email or "." not in email:
            console.print("  ⚠️  Please enter a valid email address", style="red")
            continue
        return email


def prompt_username() -> str:
    """Smart username prompt with suggestions."""
    panel = Panel(
        Align.center(
            Text.assemble(
                Text("Enter your Git username for this profile", style="bold cyan"),
                "\n\n",
                Text("This will be used to:", style="dim"),
                "\n",
                Text("• Sign your commits", style="green"),
                "\n",
                Text("• Display your contributions", style="green"),
                "\n",
                Text("• Identify you in repositories", style="green"),
            )
        ),
        title="Git Username",
        box=box.ROUNDED,
    )
    console.print(panel)
    
    return get_user_input("Enter Git username", required=True)


def prompt_directory(default_path: str | Path | None = None) -> Path:
    """Smart directory prompt with path validation."""
    if not default_path:
        default_path = Path.home() / "workspace"
    elif isinstance(default_path, str):
        default_path = Path(default_path)
    
    panel = Panel(
        Align.center(
            Text.assemble(
                Text("Choose a workspace directory for this profile", style="bold cyan"),
                "\n\n",
                Text("This directory will:", style="dim"),
                "\n",
                Text("• Store your Git repositories", style="green"),
                "\n",
                Text("• Use profile-specific Git config", style="green"),
                "\n",
                Text("• Help organize your work", style="green"),
                "\n\n",
                Text(f"Default: {default_path}", style="blue"),
            )
        ),
        title="Workspace Directory",
        box=box.ROUNDED,
    )
    console.print(panel)
    
    while True:
        dir_str = get_user_input(
            "Enter workspace directory",
            default=str(default_path),
            required=True
        )
        
        try:
            path = Path(dir_str).expanduser().resolve()
            # Create directory if it doesn't exist
            if not path.exists():
                if confirm_action(f"Directory {path} doesn't exist. Create it?", default=True):
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    continue
            return path
        except Exception as e:
            console.print(f"  ⚠️  Invalid path: {e}", style="red")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"ℹ️  {message}", style="blue")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"✅ {message}", style="green")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"⚠️  {message}", style="yellow")


def print_error(message: str) -> None:
    """Print an error message with details if provided."""
    if "\n" in message:
        # If message contains newlines, format it as a panel
        console.print(Panel(
            message,
            title="[red]Error[/red]",
            border_style="red"
        ))
    else:
        console.print(f"❌ {message}", style="red")


def confirm_action(message: str, default: bool = False) -> bool:
    """Confirm an action with the user."""
    return Prompt.ask(
        f"[yellow]{message}[/]",
        choices=["y", "n"],
        default="y" if default else "n"
    ).lower() == "y"


def get_user_input(
    prompt: str,
    default: Optional[str] = None,
    required: bool = False,
    completer: Optional[callable] = None,
) -> str:
    """Get user input with optional default value and completion."""
    while True:
        value = Prompt.ask(
            f"[cyan]{prompt}[/]",
            default=default or "",
        ).strip()
        
        if not value and required:
            print_error("This field is required")
            continue
            
        return value
