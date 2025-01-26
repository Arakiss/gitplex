"""Command-line interface."""

import logging
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar, cast

import click
from rich.prompt import Prompt

from .backup import (
    backup_configs,
    check_existing_configs,
    restore_git_config,
    restore_ssh_config,
)
from .exceptions import GitplexError, ProfileError, SystemConfigError
from .profile import Profile, ProfileManager
from .system import check_system_compatibility, clean_existing_configs
from .ui import (
    confirm_action,
    print_error,
    print_info,
    print_profile_table,
    print_setup_steps,
    print_success,
    print_warning,
    print_welcome,
    prompt_directory,
    prompt_email,
    prompt_name,
    prompt_providers,
    prompt_username,
    print_git_config_info,
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

class GitplexError(click.ClickException):
    """Base exception for Gitplex CLI errors."""
    def show(self, file: Any = None) -> None:
        """Show error message."""
        print_error(self.message)

def handle_errors(f: F) -> F:
    """Decorator to handle errors in CLI commands."""
    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            logger.debug(f"Executing command {f.__name__} with args: {args}, kwargs: {kwargs}")
            return f(*args, **kwargs)
        except (ProfileError, SystemConfigError) as e:
            # Escape error message before raising
            escaped_message = str(e).replace("[", "\\[").replace("]", "\\]")
            logger.error(f"Command failed with error: {escaped_message}")
            raise GitplexError(escaped_message) from e
        except Exception as e:
            # Escape error message for display
            escaped_message = str(e).replace("[", "\\[").replace("]", "\\]")
            logger.error(f"Unexpected error: {escaped_message}", exc_info=True)
            print_error(f"Unexpected error:\n{escaped_message}")
            raise click.Abort() from e
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
    """Set up a new Git profile with Git and SSH configurations.
    
    WARNING: Using --clean-setup will remove ALL existing Git and SSH configurations!
    This includes all SSH keys, not just GitPlex-related ones.
    Make sure to backup any important configurations before proceeding.
    """
    try:
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

        # Print welcome message and continue with setup
        if not non_interactive:
            print_welcome()

        # Check system compatibility
        check_system_compatibility()

        # Collect all profile information first
        if not name:
            name = prompt_name()

        if not email:
            email = prompt_email()

        if not username:
            username = prompt_username()

        if not directory:
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
                base_dir=directory,
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
                # Continue with profile creation without GPG
                profile = profile_manager.create_profile(
                    name=name,
                    email=email,
                    username=username,
                    provider=provider,
                    base_dir=directory,
                    force=force,
                    reuse_credentials=reuse_credentials,
                    skip_gpg=True,  # Add this parameter to ProfileManager
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
