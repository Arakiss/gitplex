"""Command-line interface."""

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
from .ssh import KeyType, SSHKeyManager
from .system import check_system_compatibility, get_home_dir
from .ui import (
    confirm_action,
    print_error,
    print_info,
    print_profile_table,
    print_ssh_key,
    print_success,
    print_welcome,
    prompt_directory,
    prompt_email,
    prompt_name,
    prompt_providers,
    prompt_username,
)

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
            return f(*args, **kwargs)
        except (ProfileError, SystemConfigError) as e:
            # Escape error message before raising
            escaped_message = str(e).replace("[", "\\[").replace("]", "\\]")
            raise GitplexError(escaped_message) from e
        except Exception as e:
            # Escape error message for display
            escaped_message = str(e).replace("[", "\\[").replace("]", "\\]")
            print_error("Unexpected error", escaped_message)
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
@handle_errors
def cli() -> None:
    """Git profile manager."""
    print_welcome()
    home_dir = get_home_dir()
    print_info(f"Using home directory: {home_dir}")
    check_system_compatibility()


@cli.command()
@click.option("--name", help="Profile name")
@click.option("--email", help="Git email")
@click.option("--username", help="Git username")
@click.option(
    "--directory",
    help="Working directory",
    multiple=True,
    type=click.Path(resolve_path=True),
)
@click.option("--provider", help="Git provider", multiple=True)
@click.option("--non-interactive", is_flag=True, help="Run in non-interactive mode")
@click.option("--no-backup", is_flag=True, help="Skip backup of existing configurations")
@click.option(
    "--key-type",
    type=click.Choice(["ed25519", "rsa"]),
    default="ed25519",
    help="SSH key type (default: ed25519)",
)
@click.option(
    "--key-bits",
    type=int,
    default=4096,
    help="Key size in bits (only for RSA, default: 4096)",
)
@click.option(
    "--passphrase",
    help="SSH key passphrase (default: none)",
    default="",
)
@handle_errors
def setup(
    name: str | None,
    email: str | None,
    username: str | None,
    directory: list[str] | None,
    provider: list[str] | None,
    non_interactive: bool,
    no_backup: bool,
    key_type: str,
    key_bits: int,
    passphrase: str,
) -> None:
    """Set up a new Git profile.
    
    This command will:
    1. Create a backup of existing configurations (optional)
    2. Generate a new SSH key pair for secure authentication
    3. Configure Git with your profile information
    4. Set up workspace directories
    5. Configure SSH for each Git provider
    """
    # Check existing configurations
    configs = check_existing_configs()
    if (configs["git_config_exists"] or configs["ssh_config_exists"]) and not no_backup:
        if confirm_action(
            "Existing Git/SSH configurations found. Would you like to back them up?"
        ):
            backup_configs()

    if non_interactive and not all([name, email, username, directory, provider]):
        raise SystemConfigError(
            "When using --non-interactive, you must provide all required options:\n"
            "--name, --email, --username, --directory, and --provider"
        )

    # Get profile information
    if not name:
        name = prompt_name()
    if not email:
        email = prompt_email()
    if not username:
        username = prompt_username()
    if not directory:
        directory = [prompt_directory(name)]
    if not provider:
        provider = prompt_providers()

    # Ensure directories exist and convert to absolute paths
    directories = [ensure_directory(d) for d in directory]

    # Generate SSH key for the profile
    print_info("Generating SSH key pair...")
    ssh_manager = SSHKeyManager()
    ssh_key = ssh_manager.generate_key(
        name=name,
        email=email,
        key_type=KeyType(key_type),
        bits=key_bits,
        passphrase=passphrase,
    )

    # Update SSH config for each provider
    for p in provider:
        print_info(f"Configuring SSH for {p}...")
        ssh_manager.update_config(ssh_key, f"{p}.com")
        print_ssh_key(ssh_key.public_key_content, p)
        print_info(ssh_manager.get_provider_instructions(ssh_key, p))

    # Create profile
    print_info("Creating Git profile...")
    profile_manager = ProfileManager()
    profile = profile_manager.setup_profile(
        name=name,
        email=email,
        username=username,
        directories=directories,
        providers=list(provider),
        ssh_key=str(ssh_key.private_key),
    )

    print_success(f"Profile '{profile.name}' created successfully!")
    print_info(
        "\nNext steps:\n"
        "1. Add your SSH key to each Git provider (see instructions above)\n"
        "2. Test your configuration with: git clone git@github.com:username/repo.git\n"
        f"3. Switch to this profile anytime with: gitplex switch {profile.name}"
    )


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


if __name__ == "__main__":
    cli()
