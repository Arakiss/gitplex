"""Command line interface for GitPlex."""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.prompt import Prompt

from gitplex.exceptions import GitPlexError
from gitplex.profile import ProfileManager
from gitplex.system import (
    check_system_compatibility,
    create_backup,
    get_existing_configs,
    restore_backup,
)
from gitplex.ui import (
    confirm_action,
    console,
    get_user_input,
    print_backup_info,
    print_error,
    print_info,
    print_profile_table,
    print_success,
    print_warning,
    print_welcome,
)
from gitplex.version import __version__


def handle_first_run() -> None:
    """Handle first run setup and checks."""
    print_welcome()
    
    try:
        # Check system compatibility
        warnings = check_system_compatibility()
        for warning in warnings:
            print_warning(warning)
        
        # Check for existing configs and create backup
        configs = get_existing_configs()
        if configs:
            if confirm_action(
                "Would you like to backup your existing Git and SSH configurations?",
                default=True,
            ):
                backup_path = create_backup(configs)
                print_backup_info(backup_path)
    
    except GitPlexError as e:
        print_error(e)
        sys.exit(1)


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """GitPlex - Seamlessly manage multiple Git identities and workspaces."""
    # Check if this is the first run
    config_dir = Path.home() / ".gitplex"
    if not config_dir.exists():
        handle_first_run()


@main.command()
@click.argument("name")
@click.option("--email", help="Git email address")
@click.option("--username", help="Git username")
@click.option(
    "--directory",
    "-d",
    multiple=True,
    help="Workspace directory (can be specified multiple times)",
)
@click.option(
    "--provider",
    "-p",
    multiple=True,
    help="Git provider (github, gitlab, azure-devops)",
)
def setup(
    name: str,
    email: Optional[str] = None,
    username: Optional[str] = None,
    directory: tuple[str, ...] = (),
    provider: tuple[str, ...] = (),
) -> None:
    """Set up a new Git profile."""
    try:
        # Get required information interactively if not provided
        email = email or get_user_input("Git email address: ")
        username = username or get_user_input("Git username: ")
        
        # Get directories if none provided
        directories = list(directory)
        if not directories:
            while True:
                dir_path = get_user_input(
                    "Workspace directory (empty to finish): ",
                    default="",
                )
                if not dir_path:
                    break
                directories.append(dir_path)
        
        # Get providers if none provided
        providers = list(provider)
        if not providers:
            while True:
                provider_name = get_user_input(
                    "Git provider (github/gitlab/azure-devops, empty to finish): ",
                    default="",
                )
                if not provider_name:
                    break
                providers.append(provider_name)
        
        # Confirm setup
        print_info("\nProfile Configuration:")
        print(f"  Name: {name}")
        print(f"  Email: {email}")
        print(f"  Username: {username}")
        print(f"  Directories: {', '.join(directories)}")
        print(f"  Providers: {', '.join(providers)}")
        
        if not confirm_action("\nProceed with this configuration?", default=True):
            return
        
        # Create profile
        manager = ProfileManager()
        profile = manager.setup_profile(
            name=name,
            email=email,
            username=username,
            directories=directories,
            providers=providers,
        )
        
        print_success(f"Profile {profile.name} created successfully!")
        
        # Show next steps
        if profile.providers:
            print_info(
                "Next Steps:\n"
                "1. Add your public SSH keys to your Git providers:\n" +
                "\n".join(
                    f"   - {p}: ~/.ssh/{profile.name}_{p}.pub"
                    for p in profile.providers
                )
            )
    
    except GitPlexError as e:
        print_error(e)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(0)


@main.command()
def list() -> None:
    """List all configured profiles."""
    try:
        manager = ProfileManager()
        profiles = manager.list_profiles()

        if not profiles:
            print_info("No profiles configured yet.")
            print_info("Use 'gitplex setup <name>' to create your first profile.")
            return

        print_profile_table([p.model_dump() for p in profiles])
    
    except GitPlexError as e:
        print_error(e)
        sys.exit(1)


@main.command()
@click.argument("name")
def switch(name: str) -> None:
    """Switch to a different Git profile."""
    try:
        if not confirm_action(
            f"Switch to profile '{name}'? This will update your Git configuration.",
            default=True,
        ):
            return
        
        manager = ProfileManager()
        profile = manager.switch_profile(name)
        print_success(f"Switched to profile {profile.name}")
    
    except GitPlexError as e:
        print_error(e)
        sys.exit(1)


@main.command()
@click.argument("backup-path", type=click.Path(exists=True, path_type=Path))
def restore(backup_path: Path) -> None:
    """Restore a previous backup."""
    try:
        if not confirm_action(
            "This will overwrite your current Git and SSH configurations. Continue?",
            default=False,
        ):
            return
        
        restore_backup(backup_path)
        print_success("Backup restored successfully!")
    
    except GitPlexError as e:
        print_error(e)
        sys.exit(1)


if __name__ == "__main__":
    main() 