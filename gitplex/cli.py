"""Command-line interface."""

import logging
import subprocess
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar, cast

import click
from rich import box
from rich.prompt import Confirm, Prompt
from rich.table import Table

from .backup import (
    backup_configs,
    check_existing_configs,
    restore_git_config,
    restore_ssh_config,
    get_git_config,
)
from .exceptions import GitplexError, ProfileError, SystemConfigError, BackupError
from .profile import Profile, ProfileManager
from .ssh import copy_to_clipboard, test_ssh_connection
from .ssh_manager import SSHManager
from .system import check_system_compatibility, clean_existing_configs
from .ui import (
    confirm_action,
    print_error,
    print_git_config_info,
    print_info,
    print_profile_table,
    print_setup_steps,
    print_ssh_key_info,
    print_success,
    print_warning,
    print_welcome,
    prompt_directory,
    prompt_email,
    prompt_name,
    prompt_providers,
    prompt_username,
)
from .ui_common import console

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

F = TypeVar('F', bound=Callable[..., Any])

# Initialize profile manager
profile_manager = ProfileManager()

def handle_errors(f: F) -> F:
    """Decorator to handle errors in CLI commands."""
    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return f(*args, **kwargs)
        except ProfileError as e:
            # Handle profile-specific errors
            if "already exists" in str(e):
                console.print("\n[bold red]Error:[/bold red] " + str(e))
                
                if hasattr(e, 'current_config') and e.current_config:
                    console.print("\n[bold cyan]Current configuration:[/bold cyan]")
                    for key, value in e.current_config.items():
                        console.print(f"• {key}: {value}")
                
                console.print("\n[bold cyan]Options:[/bold cyan]")
                console.print("1. Use a different name for your new profile")
                if hasattr(e, 'profile_name'):
                    console.print(f"2. Delete the existing profile: [yellow]gitplex delete {e.profile_name}[/yellow]")
                    console.print(f"3. Use --force to overwrite: [yellow]gitplex setup {e.profile_name} --force[/yellow]")
            else:
                console.print(f"\n[bold red]Error:[/bold red] {str(e)}")
            
            raise click.Abort()
            
        except (GitplexError, SystemConfigError) as e:
            console.print(f"\n[bold red]Error:[/bold red] {str(e)}")
            if hasattr(e, 'details') and e.details:
                console.print(f"[dim]{e.details}[/dim]")
            raise click.Abort()
            
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            console.print(f"\n[bold red]Unexpected error:[/bold red] {str(e)}")
            raise click.Abort()
    return cast(F, wrapper)


def ensure_directory(path: str) -> str:
    """Ensure directory exists and return absolute path."""
    try:
        dir_path = Path(path).resolve()
        dir_path.mkdir(parents=True, exist_ok=True)
        return str(dir_path)
    except Exception as e:
        msg = f"Failed to create directory {path}: {str(e)}"
        raise SystemConfigError(msg) from e


@click.group()
@click.option('--debug', is_flag=True, help='Enable debug logging')
def cli(debug: bool) -> None:
    """Git profile manager."""
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")
    
    logger.debug("Starting GitPlex CLI")


@cli.command()
@click.argument("name", required=False)
@click.option("--force", is_flag=True, help="Force overwrite existing profile")
@click.option("--email", help="Git email address")
@click.option("--username", help="Git username")
@click.option(
    "--directory",
    type=click.Path(path_type=Path),
    help="Workspace directory",
)
@click.option(
    "--provider",
    help="Git provider name (e.g., github, gitlab, custom-provider)",
)
@click.option(
    "--non-interactive",
    is_flag=True,
    help="Run in non-interactive mode",
)
@click.option(
    "--no-backup",
    is_flag=True,
    help="Skip backing up existing configurations",
)
@click.option(
    "--reuse-credentials",
    is_flag=True,
    help="Reuse existing credentials if they match",
    default=True,
)
@click.option(
    "--clean-setup",
    is_flag=True,
    help="⚠️  Start fresh by removing ALL existing Git and SSH configurations",
)
@handle_errors
def setup(
    name: str | None = None,
    force: bool = False,
    email: str | None = None,
    username: str | None = None,
    directory: Path | None = None,
    provider: str | None = None,
    non_interactive: bool = False,
    no_backup: bool = False,
    reuse_credentials: bool = True,
    clean_setup: bool = False,
) -> None:
    """Set up a new Git profile with Git and SSH configurations."""
    try:
        # Print welcome message
        if not non_interactive:
            print_welcome()

        # Check system compatibility first
        check_system_compatibility()

        # Scan for existing configurations
        if not clean_setup:
            print_info("\n🔍 Scanning for existing configurations...")
            existing_configs = check_existing_configs()
            
            if existing_configs["git"]["exists"]:
                console.print("\n[bold cyan]🔍 Existing Git Configuration[/bold cyan]")
                git_info = Table(box=box.ROUNDED, show_header=False, border_style="blue")
                git_info.add_column("Setting", style="dim")
                git_info.add_column("Value", style="green")
                
                git_config = get_git_config()
                if "user.email" in git_config:
                    git_info.add_row("Email", git_config["user.email"])
                if "user.name" in git_config:
                    git_info.add_row("Username", git_config["user.name"])
                if "github.user" in git_config:
                    git_info.add_row("GitHub", git_config["github.user"])
                
                console.print(git_info)
                
                # Pre-fill values if not provided
                if not email and "user.email" in git_config:
                    email = git_config["user.email"]
                    print_info("[dim]Using existing Git email[/dim]")
                if not username and "user.name" in git_config:
                    username = git_config["user.name"]
                    print_info("[dim]Using existing Git username[/dim]")
            
            if existing_configs["ssh"]["exists"]:
                console.print("\n[bold cyan]🔑 Existing SSH Configuration[/bold cyan]")
                ssh_info = Table(box=box.ROUNDED, show_header=False, border_style="blue")
                ssh_info.add_column("Type", style="dim")
                ssh_info.add_column("Details", style="green")
                
                # Add SSH keys info
                key_count = len(existing_configs["ssh"]["keys"])
                ssh_info.add_row(
                    "SSH Keys",
                    f"{key_count} key{'s' if key_count != 1 else ''} found"
                )
                
                # Add key details in a nested table
                if existing_configs["ssh"]["keys"]:
                    key_table = Table(
                        box=None,
                        show_header=False,
                        show_edge=False,
                        pad_edge=False
                    )
                    for key in existing_configs["ssh"]["keys"]:
                        key_table.add_row(
                            f"[dim]•[/dim] [blue]{key.name}[/blue] ([yellow]{key.key_type}[/yellow])"
                        )
                    ssh_info.add_row("", key_table)
                
                # Add provider info
                if existing_configs["ssh"]["providers"]:
                    providers_str = "\n".join(
                        f"[dim]•[/dim] [blue]{p}[/blue]"
                        for p in existing_configs["ssh"]["providers"]
                    )
                    ssh_info.add_row("Providers", providers_str)
                
                console.print(ssh_info)
                
                # Pre-fill provider if not provided and only one exists
                if not provider and len(existing_configs["ssh"]["providers"]) == 1:
                    provider = existing_configs["ssh"]["providers"][0]
                    print_info(f"[dim]Using existing provider: {provider}[/dim]")
            
            # If we found existing configurations, ask what to do
            if (existing_configs["git"]["exists"] or existing_configs["ssh"]["exists"]) and not non_interactive:
                console.print("\n[bold cyan]📝 Setup Options[/bold cyan]")
                options_table = Table(box=box.ROUNDED, show_header=False, border_style="cyan")
                options_table.add_column("Option", style="bold yellow")
                options_table.add_column("Description", style="white")
                
                options_table.add_row(
                    "1. View/Manage Keys",
                    "Inspect and manage existing SSH keys\n[dim]View key details, copy public keys, or test connections[/dim]"
                )
                options_table.add_row(
                    "2. Reuse",
                    "Keep existing configurations and add new profile\n[dim]Best for adding a new profile without affecting existing setup[/dim]"
                )
                options_table.add_row(
                    "3. Backup",
                    "Backup existing configs and start fresh\n[dim]Recommended if you want to start clean but keep a backup[/dim]"
                )
                options_table.add_row(
                    "4. Clean",
                    "Remove existing configs without backup\n[dim]⚠️ Use with caution - this will remove all existing configurations[/dim]"
                )
                
                console.print(options_table)
                console.print()
                
                choice = Prompt.ask(
                    "[cyan]What would you like to do?[/cyan]",
                    choices=["1", "2", "3", "4"],
                    default="2"
                )
                
                # Map numeric choices to actions
                choice_map = {
                    "1": "view",
                    "2": "reuse",
                    "3": "backup",
                    "4": "clean"
                }
                
                choice = choice_map[choice]
                
                if choice == "view":
                    # Show detailed key management menu
                    key_table = Table(box=box.ROUNDED, show_header=True, border_style="blue")
                    key_table.add_column("#", style="dim")
                    key_table.add_column("Name", style="cyan")
                    key_table.add_column("Type", style="yellow")
                    key_table.add_column("Provider", style="green")
                    
                    for idx, key in enumerate(existing_configs["ssh"]["keys"], 1):
                        provider = key.provider if hasattr(key, 'provider') else 'Unknown'
                        key_table.add_row(
                            str(idx),
                            key.name,
                            key.key_type,
                            provider
                        )
                    
                    console.print("\n[bold cyan]🔑 SSH Key Management[/bold cyan]")
                    console.print(key_table)
                    
                    key_choice = Prompt.ask(
                        "\n[cyan]Select a key to manage (or 'c' to continue setup)[/cyan]",
                        choices=[str(i) for i in range(1, len(existing_configs["ssh"]["keys"]) + 1)] + ['c'],
                        default='c'
                    )
                    
                    if key_choice != 'c':
                        selected_key = existing_configs["ssh"]["keys"][int(key_choice) - 1]
                        console.print(f"\n[bold cyan]Selected Key: {selected_key.name}[/bold cyan]")
                        
                        key_action = Prompt.ask(
                            "What would you like to do?",
                            choices=["1", "2", "3", "4"],
                            default="1"
                        )
                        
                        # Map key actions
                        key_action_map = {
                            "1": "view",
                            "2": "copy",
                            "3": "test",
                            "4": "back"
                        }
                        
                        key_action = key_action_map[key_action]
                        should_continue_key_management = True
                        
                        while should_continue_key_management and key_action != "back":
                            if key_action == "view":
                                console.print("\n[bold]Public Key Content:[/bold]")
                                console.print(selected_key.get_public_key())
                            elif key_action == "copy":
                                copy_to_clipboard(selected_key.get_public_key())
                                print_success("Public key copied to clipboard!")
                            elif key_action == "test":
                                test_ssh_connection(selected_key.provider if hasattr(selected_key, 'provider') else 'github')
                            
                            # Ask if they want to do something else with this key
                            continue_key_management = Prompt.ask(
                                "\nWould you like to do something else with this key?",
                                choices=["yes", "no"],
                                default="no"
                            )
                            
                            if continue_key_management == "yes":
                                key_action = key_action_map[Prompt.ask(
                                    "What would you like to do?",
                                    choices=["1", "2", "3", "4"],
                                    default="1"
                                )]
                            else:
                                should_continue_key_management = False
                    
                    # After key management, show setup options again
                    console.print("\n[bold cyan]📝 Setup Options[/bold cyan]")
                    options_table = Table(box=box.ROUNDED, show_header=False, border_style="cyan")
                    options_table.add_column("Option", style="bold yellow")
                    options_table.add_column("Description", style="white")
                    
                    options_table.add_row(
                        "2. Reuse",
                        "Keep existing configurations and add new profile\n[dim]Best for adding a new profile without affecting existing setup[/dim]"
                    )
                    options_table.add_row(
                        "3. Backup",
                        "Backup existing configs and start fresh\n[dim]Recommended if you want to start clean but keep a backup[/dim]"
                    )
                    options_table.add_row(
                        "4. Clean",
                        "Remove existing configs without backup\n[dim]⚠️ Use with caution - this will remove all existing configurations[/dim]"
                    )
                    
                    console.print(options_table)
                    console.print()
                    
                    next_choice = Prompt.ask(
                        "\n[cyan]How would you like to proceed with setup?[/cyan]",
                        choices=["2", "3", "4"],
                        default="2"
                    )
                    choice = choice_map[next_choice]
                
                if choice == "backup":
                    if not no_backup:
                        backup_path = backup_configs()
                        print_success(f"Configurations backed up to: {backup_path}")
                    clean_existing_configs()
                elif choice == "clean":
                    if Confirm.ask(
                        "\n⚠️  This will remove ALL existing configurations. Are you sure?",
                        default=False
                    ):
                        clean_existing_configs()
                    else:
                        print_info("Operation cancelled")
                        return
                elif choice == "reuse":
                    # Set reuse_credentials and force to True explicitly
                    reuse_credentials = True
                    force = True
                    # Ensure we reuse existing SSH keys
                    if existing_configs["ssh"]["keys"]:
                        # Find the GitHub key if it exists
                        github_key = next(
                            (key for key in existing_configs["ssh"]["keys"] 
                             if key.name.endswith("_ed25519") or key.name.endswith("_rsa")),
                            None
                        )
                        if github_key:
                            print_info(f"\n[dim]Using existing SSH key: {github_key.name}[/dim]")
                            
                            # Use SSH manager to handle key setup
                            ssh_manager = SSHManager()
                            actions = ssh_manager.troubleshoot_key(github_key.private_key)
                            
                            # Show actions taken
                            if actions:
                                console.print("\n[bold cyan]🔧 SSH Key Setup[/bold cyan]")
                                for action in actions:
                                    if "Fixed" in action or "Added" in action:
                                        print_success(action)
                                    elif "issue" in action.lower():
                                        print_error(action)
                                    else:
                                        print_info(action)
                            
                            # Verify final setup
                            if ssh_manager.verify_key_setup(github_key.private_key):
                                print_success("SSH key setup verified successfully")
                            else:
                                print_warning("SSH key setup could not be fully verified")
                                print_info("You may need to:")
                                print_info("1. Check key permissions (should be 600 for private, 644 for public)")
                                print_info(f"2. Add the key manually: ssh-add {github_key.private_key}")
                                print_info("3. Test the connection: ssh -T git@github.com")
                    
                    print_info("\n[dim]Using existing configurations as base...[/dim]")
        
        # Handle clean setup if requested
        if clean_setup:
            if non_interactive:
                raise GitplexError(
                    "Clean setup cannot be used in non-interactive mode",
                    details="This is a destructive operation that requires explicit confirmation"
                )
            
            # Get paths that will be affected
            home = Path.home()
            git_config = home / ".gitconfig"
            ssh_dir = home / ".ssh"
            ssh_config = ssh_dir / "config"
            gitplex_dir = home / ".gitplex"
            
            # Show warning and get confirmation
            console.print("\n[bold red]⚠️  WARNING: Complete System Cleanup Selected[/bold red]")
            console.print("\n[bold]The following configurations will be completely removed:[/bold]")
            
            console.print(f"\n[yellow]Git Configuration:[/yellow]")
            console.print(f"• [bold]ALL[/bold] Git global settings: [cyan]{git_config}[/cyan]")
            
            console.print(f"\n[yellow]SSH Configuration:[/yellow]")
            console.print(f"• [bold]ALL[/bold] SSH configurations: [cyan]{ssh_config}[/cyan]")
            console.print(f"• [bold]ALL[/bold] SSH keys in: [cyan]{ssh_dir}[/cyan]")
            console.print("  [dim](This includes all your existing SSH keys, not just GitPlex ones!)[/dim]")
            
            console.print(f"\n[yellow]GPG Configuration:[/yellow]")
            console.print("• GitPlex GPG keys (if GPG is installed)")
            console.print("  [dim](Only keys containing 'gitplex' in their description)[/dim]")
            
            console.print(f"\n[yellow]GitPlex Data:[/yellow]")
            console.print(f"• GitPlex profiles and settings: [cyan]{gitplex_dir}[/cyan]")
            
            console.print("\n[bold red]⚠️  WARNING:[/bold red]")
            console.print("• This will remove [bold]ALL[/bold] your SSH keys and Git configurations")
            console.print("• You will need to reconfigure any existing Git/SSH setups after this")
            console.print("• This operation [bold red]CANNOT[/bold red] be undone!")
            
            if not no_backup:
                console.print("\n[green]A backup will be created before proceeding.[/green]")
                console.print("[dim]Use --no-backup to skip backup creation (not recommended)[/dim]")
            else:
                console.print("\n[bold red]⚠️  No backup will be created (--no-backup flag is set)![/bold red]")
                console.print("[bold red]All existing configurations will be permanently lost![/bold red]")
            
            if not click.confirm("\nAre you absolutely sure you want to proceed with the complete cleanup?", default=False):
                console.print("[yellow]Operation cancelled.[/yellow]")
                return
            
            try:
                # Create backup first if requested
                if not no_backup:
                    backup_path = backup_configs()
                    print_success(f"All configurations backed up to: {backup_path}")
                    print_info(f"You can restore this backup later with: gitplex restore {backup_path} --type git")
                    print_info(f"Or restore SSH config with: gitplex restore {backup_path} --type ssh")
                
                # Proceed with clean setup
                clean_existing_configs()
                print_success("Complete system cleanup finished")
                print_info("\nYou can now create a new profile with: gitplex setup")
                return  # Return here to prevent automatic profile creation
                
            except BackupError as e:
                print_error(f"Failed to create backup: {e}")
                if not click.confirm("Continue without backup?", default=False):
                    console.print("[yellow]Operation cancelled.[/yellow]")
                    return
                clean_existing_configs()
                print_success("Complete system cleanup finished (without backup)")
                print_info("\nYou can now create a new profile with: gitplex setup")
                return  # Return here as well

        # Before asking for workspace directory, show workspace explanation
        console.print("\n[bold cyan]📂 Workspace Organization[/bold cyan]")
        workspace_info = Table(box=box.ROUNDED, show_header=False, border_style="cyan")
        workspace_info.add_column("Topic", style="bold yellow")
        workspace_info.add_column("Description", style="white")
        
        workspace_info.add_row(
            "What is a workspace?",
            "A workspace is a dedicated directory where all your Git projects for a specific profile will live.\n" +
            "[dim]For example, personal projects, work projects, open source contributions, etc.[/dim]"
        )
        workspace_info.add_row(
            "Recommended Structure",
            "~/Projects/\n" +
            "  ├── personal/    [dim]# Your personal projects[/dim]\n" +
            "  ├── work/        [dim]# Work-related projects[/dim]\n" +
            "  └── opensource/  [dim]# Open source contributions[/dim]"
        )
        workspace_info.add_row(
            "Benefits",
            "• Each profile has its own isolated space\n" +
            "• Automatic Git config switching based on directory\n" +
            "• Better organization of projects by purpose\n" +
            "• Easier to maintain different Git identities"
        )
        
        console.print(workspace_info)
        console.print()

        # Collect profile information first
        if not name:
            name = prompt_name()
        
        if not email:
            email = prompt_email()
        
        if not username:
            username = prompt_username()

        # Set up workspace directory
        if not directory:
            directory = Path.home() / "Projects" / name
            try:
                directory.mkdir(parents=True, exist_ok=True)
                print_success(f"Created workspace directory: {directory}")
            except Exception as e:
                print_warning(f"Could not create workspace directory: {e}")
                directory = prompt_directory()
        
        if not provider:
            provider = prompt_providers()[0]
        
        # Create new profile
        try:
            profile = profile_manager.create_profile(
                name=name,
                email=email,
                username=username,
                provider=provider,
                base_dir=directory.parent,  # Pass the parent directory as base_dir
                force=force,
                reuse_credentials=reuse_credentials,
            )
            
            if not non_interactive:
                print_setup_steps()
                print_git_config_info(profile.workspace_dir)
            
            print_success(f"Profile '{name}' created successfully")
            print_info(
                f"Profile '{name}' is now active. Your Git and SSH configurations "
                "have been updated."
            )
        except FileNotFoundError as e:
            if "gpg" in str(e):
                print_warning("GPG is not installed, skipping GPG key generation")
                profile = profile_manager.create_profile(
                    name=name,
                    email=email,
                    username=username,
                    provider=provider,
                    base_dir=directory,
                    force=force,
                    reuse_credentials=reuse_credentials,
                    skip_gpg=True,
                )
                if not non_interactive:
                    print_setup_steps()
                    print_git_config_info(profile.workspace_dir)
                print_success(f"Profile '{name}' created successfully (without GPG)")
                print_info(
                    f"Profile '{name}' is now active. Your Git and SSH configurations "
                    "have been updated."
                )
            else:
                raise
    
    except (ProfileError, SystemConfigError) as e:
        raise GitplexError(str(e))


@cli.command()
@click.argument("name")
@handle_errors
def switch(name: str) -> None:
    """Switch to a different Git profile."""
    profile_manager.activate_profile(name)
    print_success(f"Switched to profile '{name}'")
    print_info(
        "\nYour Git configuration has been updated. You can verify it with:\n"
        "git config --global --list"
    )


@cli.command()
@handle_errors
def list() -> None:
    """List all Git profiles."""
    profiles = profile_manager.list_profiles()

    if not profiles:
        print_info("No profiles found. Create one with: gitplex setup")
        return

    profiles_data = [
        {
            "name": p.name,
            "email": p.email,
            "username": p.username,
            "directories": [str(p.workspace_dir)],
            "providers": [p.provider],
            "active": p.is_active,
        }
        for p in profiles
    ]
    print_profile_table(profiles_data)


@cli.command()
@click.argument("name")
@click.option("--force", is_flag=True, help="Force delete without confirmation")
@handle_errors
def delete(name: str, force: bool = False) -> None:
    """Delete a Git profile."""
    if not force and not confirm_action(
        f"Are you sure you want to delete profile '{name}'?"
    ):
        print_info("Operation cancelled")
        return

    profile_manager.delete_profile(name, keep_files=False)
    print_success(f"Profile '{name}' deleted successfully")


@cli.command()
@click.argument("name")
@click.option("--email", help="New Git email")
@click.option("--username", help="New Git username")
@click.option("--provider", help="Add new provider", multiple=True)
@click.option("--remove-provider", help="Remove provider", multiple=True)
@handle_errors
def update(
    name: str,
    email: str | None = None,
    username: str | None = None,
    provider: tuple[str, ...] | None = None,
    remove_provider: tuple[str, ...] | None = None,
) -> None:
    """Update a Git profile."""
    if not any([email, username, provider, remove_provider]):
        print_error("Please provide at least one of --email, --username, --provider, or --remove-provider")
        return

    profile = profile_manager.get_profile(name)
    
    if email or username:
        # Update credentials
        new_email = email or profile.credentials.email
        new_username = username or profile.credentials.username
        
        # Check if we can reuse existing credentials
        existing_creds = profile_manager.find_matching_credentials(new_email, new_username)
        if existing_creds:
            profile.credentials = existing_creds
            print_success("Updated profile with existing credentials")
        else:
            # Create new credentials
            profile.credentials.email = new_email
            profile.credentials.username = new_username
    
    if provider:
        # Add new providers
        for p in provider:
            if p not in profile.providers:
                profile.providers.append(p)
                print_success(f"Added provider: {p}")
    
    if remove_provider:
        # Remove providers
        for p in remove_provider:
            if p in profile.providers:
                profile.providers.remove(p)
                print_success(f"Removed provider: {p}")
    
    profile_manager._save_profiles()
    print_success(f"Profile '{name}' updated successfully")


@cli.command()
@click.argument("backup_path", type=click.Path(exists=True))
@click.option("--type", type=click.Choice(["git", "ssh"]), required=True)
@handle_errors
def restore(backup_path: str, type: str) -> None:
    """Restore Git or SSH configuration from backup."""
    backup = Path(backup_path)

    print_info(f"Restoring {type.upper()} configuration from {backup}...")
    if type == "git":
        restore_git_config(backup)
    else:
        restore_ssh_config(backup)

    print_success(f"{type.upper()} configuration restored successfully")


@cli.group()
def keys() -> None:
    """Manage SSH keys."""
    pass

@keys.command()
@handle_errors
def list() -> None:
    """List all SSH keys."""
    # Get existing configs
    existing_configs = check_existing_configs()
    
    if not existing_configs["ssh"]["exists"]:
        print_info("No SSH keys found")
        return
    
    # Create table for keys
    key_table = Table(box=box.ROUNDED, show_header=True, border_style="blue")
    key_table.add_column("Name", style="cyan")
    key_table.add_column("Type", style="yellow")
    key_table.add_column("Provider", style="green")
    key_table.add_column("Profile", style="magenta")
    
    for key in existing_configs["ssh"]["keys"]:
        key_table.add_row(
            key.name,
            key.key_type,
            key.provider,
            key.profile_name,
        )
    
    console.print("\n[bold cyan]🔑 SSH Keys[/bold cyan]")
    console.print(key_table)
    console.print()

@keys.command()
@click.argument("provider")
@handle_errors
def test(provider: str) -> None:
    """Test SSH connection to a provider."""
    test_ssh_connection(provider)

@keys.command()
@click.argument("provider")
@handle_errors
def copy(provider: str) -> None:
    """Copy SSH public key for a provider to clipboard."""
    # Get existing configs
    existing_configs = check_existing_configs()
    
    if not existing_configs["ssh"]["exists"]:
        print_error("No SSH keys found")
        return
    
    # Find key for provider
    provider_key = None
    for key in existing_configs["ssh"]["keys"]:
        if key.provider.lower() == provider.lower():
            provider_key = key
            break
    
    if not provider_key:
        print_error(f"No SSH key found for provider: {provider}")
        return
    
    # Copy key to clipboard
    public_key = provider_key.get_public_key()
    copy_to_clipboard(public_key)
    
    # Show key info
    print_ssh_key_info(provider_key)

@keys.command()
@click.argument("provider")
@click.option("--fix", is_flag=True, help="Automatically fix issues found")
@click.option("--profile", help="Configure Git settings for a specific profile")
@handle_errors
def diagnose(provider: str, fix: bool, profile: str | None) -> None:
    """Diagnose and optionally fix SSH and Git configuration issues."""
    # Get existing configs
    existing_configs = check_existing_configs()
    
    if not existing_configs["ssh"]["exists"]:
        print_error("No SSH keys found")
        return
    
    # Find key for provider
    provider_key = None
    for key in existing_configs["ssh"]["keys"]:
        if key.provider.lower() == provider.lower():
            provider_key = key
            break
    
    if not provider_key:
        print_error(f"No SSH key found for provider: {provider}")
        return
    
    console.print("\n[bold cyan]🔍 SSH Diagnostic Report[/bold cyan]")
    
    # Track issues for fixing
    issues = []
    
    # Check key files and build issues list
    key_table = Table(box=box.ROUNDED, show_header=True, border_style="blue")
    key_table.add_column("Check", style="cyan")
    key_table.add_column("Status", style="green")
    key_table.add_column("Details", style="white")
    
    # Check private key
    if provider_key.private_key.exists():
        perms = oct(provider_key.private_key.stat().st_mode)[-3:]
        if perms == "600":
            key_table.add_row(
                "Private Key",
                "[green]✓[/green]",
                f"Found at {provider_key.private_key} with correct permissions (600)"
            )
        else:
            key_table.add_row(
                "Private Key",
                "[yellow]![/yellow]",
                f"Found but has wrong permissions: {perms} (should be 600)"
            )
            issues.append(("chmod", "600", provider_key.private_key))
    else:
        key_table.add_row(
            "Private Key",
            "[red]✗[/red]",
            f"Not found at {provider_key.private_key}"
        )
        issues.append(("regenerate_keys", None, None))
    
    # Check public key
    if provider_key.public_key.exists():
        perms = oct(provider_key.public_key.stat().st_mode)[-3:]
        if perms == "644":
            key_table.add_row(
                "Public Key",
                "[green]✓[/green]",
                f"Found at {provider_key.public_key} with correct permissions (644)"
            )
        else:
            key_table.add_row(
                "Public Key",
                "[yellow]![/yellow]",
                f"Found but has wrong permissions: {perms} (should be 644)"
            )
            issues.append(("chmod", "644", provider_key.public_key))
    else:
        key_table.add_row(
            "Public Key",
            "[red]✗[/red]",
            f"Not found at {provider_key.public_key}"
        )
        issues.append(("regenerate_keys", None, None))
    
    # Check SSH config
    ssh_config = Path.home() / ".ssh" / "config"
    if ssh_config.exists():
        config_content = ssh_config.read_text()
        if str(provider_key.private_key) in config_content:
            key_table.add_row(
                "SSH Config",
                "[green]✓[/green]",
                "Key is properly configured in SSH config"
            )
        else:
            key_table.add_row(
                "SSH Config",
                "[yellow]![/yellow]",
                "Key not found in SSH config"
            )
            issues.append(("update_ssh_config", None, None))
    else:
        key_table.add_row(
            "SSH Config",
            "[red]✗[/red]",
            "SSH config file not found"
        )
        issues.append(("create_ssh_config", None, None))
    
    # Check SSH agent
    try:
        result = subprocess.run(
            ["ssh-add", "-l"],
            capture_output=True,
            text=True
        )
        if str(provider_key.private_key) in result.stdout:
            key_table.add_row(
                "SSH Agent",
                "[green]✓[/green]",
                "Key is loaded in SSH agent"
            )
        else:
            key_table.add_row(
                "SSH Agent",
                "[yellow]![/yellow]",
                "Key not loaded in SSH agent"
            )
            issues.append(("add_to_agent", None, provider_key.private_key))
    except subprocess.CalledProcessError:
        key_table.add_row(
            "SSH Agent",
            "[red]✗[/red]",
            "SSH agent not running"
        )
        issues.append(("start_agent", None, None))
    
    # Test connection
    try:
        result = subprocess.run(
            ["ssh", "-T", f"git@{get_provider_hostname(provider)}"],
            capture_output=True,
            text=True
        )
        if "successfully authenticated" in result.stderr.lower():
            key_table.add_row(
                "Connection Test",
                "[green]✓[/green]",
                "Successfully authenticated with provider"
            )
        else:
            key_table.add_row(
                "Connection Test",
                "[red]✗[/red]",
                f"Authentication failed: {result.stderr.strip()}"
            )
    except subprocess.CalledProcessError as e:
        if "successfully authenticated" in e.stderr.lower():
            key_table.add_row(
                "Connection Test",
                "[green]✓[/green]",
                "Successfully authenticated with provider"
            )
        else:
            key_table.add_row(
                "Connection Test",
                "[red]✗[/red]",
                f"Connection failed: {e.stderr.strip()}"
            )
    
    console.print(key_table)
    
    # Check Git configuration
    console.print("\n[bold cyan]🔧 Git Configuration Report[/bold cyan]")
    git_table = Table(box=box.ROUNDED, show_header=True, border_style="blue")
    git_table.add_column("Check", style="cyan")
    git_table.add_column("Status", style="green")
    git_table.add_column("Details", style="white")
    
    # Get Git configs
    global_git_config = get_git_config()
    profile_git_config = get_git_config(profile) if profile else {}
    
    # Check user.name
    if profile and "user.name" in profile_git_config:
        git_table.add_row(
            f"user.name ({profile})",
            "[green]✓[/green]",
            f"Set to: {profile_git_config['user.name']}"
        )
    elif "user.name" in global_git_config:
        git_table.add_row(
            "user.name (global)",
            "[green]✓[/green]",
            f"Set to: {global_git_config['user.name']}"
        )
    else:
        git_table.add_row(
            "user.name",
            "[red]✗[/red]",
            "Not configured"
        )
        issues.append(("set_git_config", "user.name", profile))
    
    # Check user.email
    if profile and "user.email" in profile_git_config:
        git_table.add_row(
            f"user.email ({profile})",
            "[green]✓[/green]",
            f"Set to: {profile_git_config['user.email']}"
        )
    elif "user.email" in global_git_config:
        git_table.add_row(
            "user.email (global)",
            "[green]✓[/green]",
            f"Set to: {global_git_config['user.email']}"
        )
    else:
        git_table.add_row(
            "user.email",
            "[red]✗[/red]",
            "Not configured"
        )
        issues.append(("set_git_config", "user.email", profile))
    
    console.print(git_table)
    
    if issues:
        console.print("\n[bold cyan]📋 Issues Found:[/bold cyan]")
        
        # Group all issues by type for batch processing
        fixes_needed = {
            "chmod": [],
            "regenerate_keys": False,
            "update_ssh_config": False,
            "add_to_agent": None,
            "start_agent": False,
            "git_config": {"user.name": None, "user.email": None}
        }
        
        # Collect all issues first
        for issue_type, param, path in issues:
            if issue_type == "chmod":
                fixes_needed["chmod"].append((param, path))
            elif issue_type == "regenerate_keys":
                fixes_needed["regenerate_keys"] = True
            elif issue_type == "update_ssh_config":
                fixes_needed["update_ssh_config"] = True
            elif issue_type == "add_to_agent":
                fixes_needed["add_to_agent"] = path
            elif issue_type == "start_agent":
                fixes_needed["start_agent"] = True
            elif issue_type == "set_git_config":
                fixes_needed["git_config"][param] = profile
        
        # Now apply all fixes if --fix is specified
        if fix:
            print_info("\n🔧 Applying fixes...")
            
            # Fix permissions first
            for perm, path in fixes_needed["chmod"]:
                try:
                    path.chmod(int(perm, 8))
                    print_success(f"✓ Changed permissions of {path} to {perm}")
                except Exception as e:
                    print_error(f"✗ Failed to change permissions of {path}: {e}")
            
            # Start SSH agent if needed
            if fixes_needed["start_agent"]:
                try:
                    subprocess.run(["eval", "`ssh-agent -s`"], shell=True, check=True)
                    print_success("✓ Started SSH agent")
                except subprocess.CalledProcessError as e:
                    print_error(f"✗ Failed to start SSH agent: {e}")
            
            # Add key to agent
            if fixes_needed["add_to_agent"]:
                try:
                    subprocess.run(["ssh-add", fixes_needed["add_to_agent"]], check=True)
                    print_success("✓ Added key to SSH agent")
                except subprocess.CalledProcessError as e:
                    print_error(f"✗ Failed to add key to agent: {e}")
            
            # Configure Git settings
            git_config = fixes_needed["git_config"]
            if git_config["user.name"] is not None or git_config["user.email"] is not None:
                print_info("\nConfiguring Git settings...")
                
                if git_config["user.name"] is not None:
                    name = prompt_name()
                    try:
                        set_git_config("user.name", name, profile=git_config["user.name"])
                        print_success(f"✓ Set user.name to: {name}")
                    except Exception as e:
                        print_error(f"✗ Failed to set user.name: {e}")
                
                if git_config["user.email"] is not None:
                    email = prompt_email()
                    try:
                        set_git_config("user.email", email, profile=git_config["user.email"])
                        print_success(f"✓ Set user.email to: {email}")
                    except Exception as e:
                        print_error(f"✗ Failed to set user.email: {e}")
            
            # Regenerate keys if needed (should be last as it's most disruptive)
            if fixes_needed["regenerate_keys"]:
                print_info("\nRegenerating SSH keys...")
                setup(clean_setup=True)
            elif fixes_needed["update_ssh_config"]:
                print_info("\nUpdating SSH config...")
                setup(force=True)
            
            # Run final diagnostic to verify fixes
            print_info("\nVerifying fixes...")
            diagnose(provider, fix=False, profile=profile)
        else:
            print_info("\nTo automatically fix these issues, run:")
            print_info(f"  gitplex keys diagnose {provider} --fix" + (f" --profile {profile}" if profile else ""))
    else:
        print_success("\n✓ No issues found!")
        print_info("If you're still having problems:")
        print_info("1. Verify the key is added to your GitHub account")
        print_info("2. Try running: ssh -vT git@github.com for verbose output")
        print_info("3. Check GitHub's SSH troubleshooting guide: https://docs.github.com/en/authentication/troubleshooting-ssh")

def get_provider_hostname(provider: str) -> str:
    """Get the SSH hostname for a Git provider."""
    provider = provider.lower()
    hostnames = {
        "github": "github.com",
        "gitlab": "gitlab.com",
        "bitbucket": "bitbucket.org",
        "azure": "ssh.dev.azure.com",
    }
    if provider not in hostnames:
        raise GitplexError(f"Unknown provider: {provider}")
    return hostnames[provider]

def prompt_git_config(param: str) -> str:
    """Prompt user for Git configuration value."""
    if param == "user.name":
        return prompt_name()
    elif param == "user.email":
        return prompt_email()
    else:
        return Prompt.ask(f"Enter value for {param}")

def set_git_config(param: str, value: str, profile: str | None = None) -> None:
    """Set Git configuration value."""
    if profile:
        # Set for specific profile directory
        profile_dir = Path.home() / ".gitplex" / "profiles" / profile
        if not profile_dir.exists():
            raise ProfileError(f"Profile directory not found: {profile}")
        subprocess.run(
            ["git", "config", "--file", str(profile_dir / ".gitconfig"), param, value],
            check=True
        )
    else:
        # Set globally
        subprocess.run(["git", "config", "--global", param, value], check=True)
