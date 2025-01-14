"""Command-line interface."""

import sys
import logging
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar, cast

import click

from .backup import (
    backup_configs,
    check_existing_configs,
    restore_git_config,
    restore_ssh_config,
)
from .exceptions import ProfileError, SystemConfigError
from .profile import ProfileManager
from .ssh import KeyType, SSHKeyManager, SSHConfig
from .system import check_system_compatibility, get_home_dir
from .ui import (
    confirm_action,
    confirm_git_setup,
    get_user_input,
    print_error,
    print_git_config_preview,
    print_git_setup_summary,
    print_info,
    print_profile_info,
    print_profile_table,
    print_setup_steps,
    print_ssh_key,
    print_success,
    print_warning,
    print_welcome,
    prompt_directory,
    prompt_email,
    prompt_name,
    prompt_providers,
    prompt_username,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

F = TypeVar('F', bound=Callable[..., Any])


class GitplexError(click.ClickException):
    """Base exception for Gitplex CLI errors."""
    def show(self, file: Any = None) -> None:
        """Show error message."""
        # Escape error message for display
        escaped_message = str(self.message).replace("[", "\\[").replace("]", "\\]")
        print_error(escaped_message)


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
@click.option("--name", help="Profile name")
@click.option("--force", is_flag=True, help="Force overwrite if profile exists")
@click.option("--email", help="Git email")
@click.option("--username", help="Git username")
@click.option(
    "--directory",
    help="Workspace directories",
    multiple=True,
    type=click.Path(exists=False, file_okay=False, path_type=Path),
)
@click.option(
    "--provider",
    help="Git providers",
    multiple=True,
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
@handle_errors
def setup(
    name: str | None = None,
    force: bool = False,
    email: str | None = None,
    username: str | None = None,
    directory: tuple[Path, ...] | None = None,
    provider: tuple[str, ...] | None = None,
    non_interactive: bool = False,
    no_backup: bool = False,
) -> None:
    """Set up a new Git profile with Git and SSH configurations."""
    try:
        logger.debug("Starting setup command")
        print_welcome()
        
        # Show important warning
        print_warning(
            "⚠️  IMPORTANT: This tool modifies your Git and SSH configurations. "
            "While it creates backups by default, you should use it at your own risk. "
            "Make sure you understand the changes it will make to your system."
        )
        if not confirm_action("Do you understand and wish to continue?", default=False):
            print_info("Setup cancelled.")
            return
            
        # Show setup steps
        print_setup_steps()
        
        # System compatibility check
        logger.debug("Running system compatibility check")
        check_system_compatibility()
        
        # Check and backup existing configurations
        if not no_backup:
            configs = check_existing_configs()
            if configs["git_config_exists"] or configs["ssh_config_exists"]:
                print_info("Found existing Git/SSH configurations.")
                if confirm_action("Would you like to back them up before proceeding?", default=True):
                    backup_path = backup_configs()
                    print_success(f"Configurations backed up to: {backup_path}")
                    print_info("You can restore them later with: gitplex restore --backup-path <path>")
        
        # Initialize managers
        profile_manager = ProfileManager()
        
        # Collect all profile information first
        if not name:
            name = prompt_name()
        
        if not email:
            email = prompt_email()
        
        if not username:
            username = prompt_username()
        
        if not provider:
            provider = tuple(prompt_providers())
        
        if not directory:
            default_dir = Path.home() / name.lower()
            workspace_dir = prompt_directory(default_dir)
            directory = (Path(workspace_dir),)
        
        # Now check for conflicts
        has_conflict, conflicting_profile = profile_manager.has_provider_conflict(list(provider), email)
        if has_conflict:
            print_warning(
                f"Profile '{conflicting_profile}' already exists with different email "
                f"for providers: {', '.join(provider)}."
            )
            if not confirm_action("Would you like to continue and create a new profile anyway?", default=False):
                print_info("Setup cancelled.")
                return
            force = True
        elif profile_manager.profile_exists(name):
            print_warning(f"Profile '{name}' already exists.")
            if not confirm_action("Would you like to overwrite it?", default=False):
                print_info("Setup cancelled. Please try again with a different profile name.")
                return
            force = True
        
        # Create profile
        profile_manager.create_profile(
            name=name,
            email=email,
            username=username,
            providers=list(provider),
            directories=[str(d) for d in directory],
            force=force
        )
        
        print_success(f"Profile '{name}' created successfully!")
        print("\n[dim]Need help? Run [cyan]gitplex --help[/cyan] for more information[/dim]")
        return
        
    except Exception as e:
        logger.error(f"Setup failed: {e}", exc_info=True)
        print_error(f"Setup failed: {e}")
        raise


@cli.command()
@click.argument("name")
@handle_errors
def switch(name: str) -> None:
    """Switch to a different Git profile."""
    profile_manager = ProfileManager()
    profile = profile_manager.switch_profile(name)
    print_success(f"Switched to profile '{profile.name}'")
    print_info(
        "\nYour Git configuration has been updated. You can verify it with:\n"
        "git config --global --list"
    )


@cli.command()
@handle_errors
def list() -> None:
    """List all Git profiles."""
    profile_manager = ProfileManager()
    profiles = profile_manager.list_profiles()

    if not profiles:
        print_info("No profiles found. Create one with: gitplex setup")
        return

    profiles_data = [
        {
            "name": p.name,
            "email": p.email,
            "username": p.username,
            "directories": p.directories,
            "providers": p.providers,
            "active": p.active,
        }
        for p in profiles
    ]
    print_profile_table(profiles_data)


@cli.command()
@click.argument("name")
@click.option("--force", is_flag=True, help="Force deletion without confirmation")
@handle_errors
def delete(name: str, force: bool) -> None:
    """Delete a Git profile."""
    if not force and not confirm_action(
        f"Are you sure you want to delete profile '{name}'? This cannot be undone."
    ):
        print_info("Operation cancelled")
        return

    profile_manager = ProfileManager()
    profile_manager.delete_profile(name)
    print_success(f"Profile '{name}' deleted successfully")


@cli.command()
@click.argument("name")
@click.argument("directory", type=click.Path(resolve_path=True))
@handle_errors
def add_directory(name: str, directory: str) -> None:
    """Add a directory to a profile."""
    dir_path = ensure_directory(directory)
    profile_manager = ProfileManager()
    profile = profile_manager.add_directory(name, dir_path)
    print_success(f"Added directory '{dir_path}' to profile '{profile.name}'")
    print_info(
        "\nGit configuration will be automatically used when working in this directory"
    )


@cli.command()
@click.argument("name")
@click.argument("directory", type=click.Path(resolve_path=True))
@handle_errors
def remove_directory(name: str, directory: str) -> None:
    """Remove a directory from a profile."""
    profile_manager = ProfileManager()
    profile = profile_manager.remove_directory(name, directory)
    print_success(f"Removed directory '{directory}' from profile '{profile.name}'")


@cli.command()
@click.argument("name")
@click.option("--email", help="New Git email")
@click.option("--username", help="New Git username")
@handle_errors
def update(name: str, email: str | None, username: str | None) -> None:
    """Update a Git profile."""
    if not email and not username:
        print_error("No changes specified. Use --email or --username")
        return

    profile_manager = ProfileManager()
    profile = profile_manager.get_profile(name)

    if email:
        profile.email = email
    if username:
        profile.username = username

    profile_manager.save_profile(profile)
    print_success(f"Profile '{name}' updated successfully")
    print_info(
        "\nChanges will take effect next time you switch to this profile:\n"
        f"gitplex switch {name}"
    )


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
