"""Command-line interface."""

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
from .exceptions import GitplexError, ProfileError, SystemConfigError
from .profile import Profile, ProfileManager
from .system import check_system_compatibility
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
)

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
@click.option("--name", help="Profile name")
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
    help="Git provider (e.g., github, gitlab, bitbucket)",
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
    directory: Path | None = None,
    provider: str | None = None,
    non_interactive: bool = False,
    no_backup: bool = False,
) -> None:
    """Set up a new Git profile with Git and SSH configurations."""
    try:
        # Print welcome message
        if not non_interactive:
            print_welcome()

        # Check system compatibility
        check_system_compatibility()

        # Collect all profile information first
        if not name:
            name = prompt_name()

        # Check if profile exists
        try:
            existing_profile = profile_manager.get_profile(name)
            if not force:
                if not confirm_action(
                    f"Profile '{name}' already exists. Do you want to overwrite it?"
                ):
                    print_info("Operation cancelled")
                    return
                print_warning(f"Overwriting existing profile '{name}'")
        except ProfileError:
            # Profile doesn't exist, continue with setup
            pass

        if not no_backup:
            # Check for existing configurations
            existing_configs = check_existing_configs()
            if existing_configs and not force:
                if not confirm_action(
                    "Existing Git/SSH configurations found. Would you like to back them up?"
                ):
                    print_info("Operation cancelled")
                    return

                # Backup existing configurations
                backup_path = backup_configs()
                if backup_path:
                    print_success(f"Configurations backed up to: {backup_path}")
                    print_info(
                        "You can restore them later with: gitplex restore "
                        "--backup-path <path>"
                    )

        if not email:
            email = prompt_email()

        if not username:
            username = prompt_username()

        if not directory:
            directory = prompt_directory()

        if not provider:
            provider = prompt_providers()[0]  # Take first provider if multiple

        # Create new profile
        profile = profile_manager.create_profile(
            name=name,
            email=email,
            username=username,
            provider=provider,
            base_dir=directory,
            force=force,
        )

        if not non_interactive:
            print_setup_steps()

        print_success(f"Profile '{name}' created successfully")
        print_info(
            f"Profile '{name}' is now active. Your Git and SSH configurations "
            "have been updated."
        )

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
@handle_errors
def update(name: str, email: str | None = None, username: str | None = None) -> None:
    """Update a Git profile."""
    if not email and not username:
        print_error("Please provide at least one of --email or --username")
        return

    profile = profile_manager.get_profile(name)
    
    if email:
        profile.email = email
    if username:
        profile.username = username
    
    profile_manager._save_profiles()  # Save changes
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
