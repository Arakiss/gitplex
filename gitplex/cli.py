"""Command-line interface."""

import logging
import subprocess
import os
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar, cast, Tuple, List, Optional

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
from .system import (
    check_system_compatibility,
    get_existing_configs,
    backup_configs,
    clean_existing_configs,
    clean_provider_configs,
)
from .system_utils import get_ssh_agent
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

# Type alias for diagnostic issues
DiagnosticIssue = Tuple[str, Optional[str], Optional[Path]]
DiagnosticResult = List[DiagnosticIssue]

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


def ensure_ssh_agent_running() -> None:
    """Ensure SSH agent is running and properly configured."""
    agent = get_ssh_agent()
    if not agent.start():
        raise GitplexError("SSH agent is required for GitPlex to function properly")


@cli.command()
@click.argument("name", required=False)
@click.option("--force", is_flag=True, help="Force update existing profile")
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

        # Ensure SSH agent is running
        ensure_ssh_agent_running()

        # Show existing profiles if any
        existing_profiles = profile_manager.list_profiles()
        if existing_profiles:
            print_info("\n🔍 Existing Profiles:")
            for p in existing_profiles:
                print_info(f"\n• Profile: {p.name}")
                print_info(f"  - Email: {p.credentials.email}")
                print_info(f"  - Username: {p.credentials.username}")
                print_info(f"  - Workspace: {p.workspace_dir}")
                if hasattr(p, 'providers') and p.providers:
                    providers = [str(provider.type) for provider in p.providers.providers]
                    print_info(f"  - Providers: {', '.join(providers)}")
                elif hasattr(p, 'provider'):
                    print_info(f"  - Provider: {p.provider}")
                
                # Show SSH key info
                if p.credentials.ssh_key:
                    print_info(f"  - SSH Key: {p.credentials.ssh_key.private_key}")
                    # Check if key is loaded in agent
                    agent = get_ssh_agent()
                    if agent.is_key_loaded(p.credentials.ssh_key.private_key):
                        print_success("    ✓ Key is loaded in SSH agent")
                    else:
                        print_warning("    ! Key is not loaded in SSH agent")
                        # Offer to load the key
                        if Confirm.ask("    Would you like to load this key into the SSH agent?"):
                            agent.add_key(p.credentials.ssh_key.private_key)

        # Scan for existing configurations
        if not clean_setup:
            print_info("\n🔍 Scanning for existing configurations...")
            existing_configs = check_existing_configs()
            
            # Only show existing configurations if they match the requested provider
            show_existing = False
            if provider:
                show_existing = any(
                    p == provider for p in existing_configs["ssh"]["providers"]
                )
            else:
                show_existing = existing_configs["git"]["exists"] or existing_configs["ssh"]["exists"]
            
            if show_existing:
                print_info("\nExisting configurations found:")
                if existing_configs["git"]["exists"]:
                    print_info("• Git configuration exists")
                if existing_configs["ssh"]["exists"]:
                    print_info("• SSH configuration exists")
                    if existing_configs["ssh"]["providers"]:
                        print_info(f"  Providers: {', '.join(existing_configs['ssh']['providers'])}")
                    
                    # Show SSH keys detail
                    if existing_configs["ssh"]["keys"]:
                        print_info("\nSSH Keys:")
                        for key in existing_configs["ssh"]["keys"]:
                            print_info(f"  • {key.name} ({key.key_type})")
                            # Check if key is loaded in agent
                            try:
                                agent_output = subprocess.check_output(
                                    ["ssh-add", "-l"],
                                    text=True
                                )
                                key_loaded = str(key.private_key) in agent_output
                                if key_loaded:
                                    print_success("    ✓ Key is loaded in SSH agent")
                                else:
                                    print_warning("    ! Key is not loaded in SSH agent")
                                    # Offer to load the key
                                    if Confirm.ask("    Would you like to load this key into the SSH agent?"):
                                        try:
                                            subprocess.run(["ssh-add", key.private_key], check=True)
                                            print_success("    ✓ Key loaded successfully")
                                        except subprocess.CalledProcessError as e:
                                            print_error(f"    ✗ Failed to load key: {e}")
                            except subprocess.CalledProcessError:
                                print_warning("    ! Could not check SSH agent status")
                
                if not force and not clean_setup:
                    if Confirm.ask(
                        "\nWould you like to back up your existing configurations?",
                        default=True,
                    ):
                        backup_configs()
                        print_success("Configurations backed up successfully")
                    elif Confirm.ask(
                        "\n⚠️  Would you like to clean up existing configurations?",
                        default=False,
                    ):
                        clean_existing_configs()
                        print_success("Existing configurations cleaned up")

        # Get profile name
        if not name and not non_interactive:
            name = prompt_name()
        elif not name:
            raise GitplexError("Profile name is required in non-interactive mode")

        # Get email
        if not email and not non_interactive:
            email = prompt_email()
        elif not email:
            raise GitplexError("Email is required in non-interactive mode")

        # Get username
        if not username and not non_interactive:
            username = prompt_username()
        elif not username:
            raise GitplexError("Username is required in non-interactive mode")

        # Get provider
        if not provider and not non_interactive:
            provider = prompt_providers()
        elif not provider:
            raise GitplexError("Provider is required in non-interactive mode")

        # Get workspace directory
        if force and name in profile_manager.profiles:
            # Si estamos usando --force y el perfil existe, usar su directorio
            directory = profile_manager.profiles[name].workspace_dir
        elif not directory and not non_interactive:
            directory = prompt_directory(name)
        elif not directory:
            directory = Path.home() / "Projects" / name

        # Validate the provider before crear el perfil
        try:
            from .providers import ProviderType
            # Esto validará el provider y lanzará ValueError si no es válido
            ProviderType.from_str(provider)
        except ValueError as e:
            raise GitplexError(str(e))
        
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
            
            if force:
                print_success(f"Added provider '{provider}' to profile '{name}'")
            else:
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
                if force:
                    print_success(f"Added provider '{provider}' to profile '{name}'")
                else:
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

def run_diagnostic(provider: str, profile: Optional[str] = None, fix: bool = False) -> DiagnosticResult:
    """Run diagnostic checks and optionally fix issues."""
    # Get existing configs
    existing_configs = check_existing_configs()
    
    if not existing_configs["ssh"]["exists"]:
        print_error("No SSH keys found")
        return []
    
    # Find key for provider
    provider_key = None
    for key in existing_configs["ssh"]["keys"]:
        if key.provider.lower() == provider.lower():
            provider_key = key
            break
    
    if not provider_key:
        print_error(f"No SSH key found for provider: {provider}")
        return []
    
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
    
    if issues and fix:
        print_info("\n🔧 Applying fixes...")
        
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
        return run_diagnostic(provider, profile=profile, fix=False)
    
    return issues

@keys.command()
@click.argument("provider")
@click.option("--fix", is_flag=True, help="Automatically fix issues found")
@click.option("--profile", help="Configure Git settings for a specific profile")
@handle_errors
def diagnose(provider: str, fix: bool, profile: str | None) -> None:
    """Diagnose and optionally fix SSH and Git configuration issues."""
    issues = run_diagnostic(provider, profile=profile, fix=fix)
    
    if not fix and issues:
        print_info("\nTo automatically fix these issues, run:")
        print_info(f"  gitplex keys diagnose {provider} --fix" + (f" --profile {profile}" if profile else ""))
    elif not issues:
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

def configure_ssh_agent_persistence() -> None:
    """Configure SSH agent to start automatically and persist keys."""
    # 1. Start SSH agent now if not running
    try:
        # First try to use existing agent
        subprocess.run(["ssh-add", "-l"], capture_output=True, check=True)
    except subprocess.CalledProcessError:
        # Agent not running or no connection, try to start it
        try:
            # Start agent and capture its environment
            agent_output = subprocess.check_output(
                ["ssh-agent", "-s"],
                text=True
            )
            
            # Parse and export SSH agent environment variables
            for line in agent_output.splitlines():
                if "=" in line:
                    var, value = line.split(";", 1)[0].split("=", 1)
                    os.environ[var] = value
                    # Also export to parent shell
                    print(f"export {var}={value}")
        except subprocess.CalledProcessError as e:
            print_error(f"Failed to start SSH agent: {e}")
            return
    
    # 2. Add all SSH keys to agent now
    ssh_dir = Path.home() / ".ssh"
    keys_added = False
    
    for key_file in ssh_dir.glob("id_*"):
        if not key_file.name.endswith(".pub"):
            try:
                # Check if key is already added
                key_fingerprint = subprocess.check_output(
                    ["ssh-keygen", "-lf", str(key_file)],
                    text=True
                ).split()[1]
                
                agent_keys = subprocess.check_output(
                    ["ssh-add", "-l"],
                    text=True
                )
                
                if key_fingerprint not in agent_keys:
                    subprocess.run(["ssh-add", key_file], check=True)
                    print_success(f"✓ Added key {key_file} to SSH agent")
                    keys_added = True
            except subprocess.CalledProcessError:
                print_warning(f"Failed to add key {key_file} to SSH agent")
    
    if not keys_added:
        print_info("All keys are already loaded in the SSH agent")
    
    # 3. Configure persistence in shell RC file
    shell_rc = None
    shell = os.environ.get("SHELL", "")
    
    if "zsh" in shell:
        shell_rc = Path.home() / ".zshrc"
    elif "bash" in shell:
        shell_rc = Path.home() / ".bashrc"
    
    if shell_rc:
        content = shell_rc.read_text() if shell_rc.exists() else ""
        
        # Check if SSH agent config already exists
        if "eval `ssh-agent -s`" not in content and "ssh-add" not in content:
            with shell_rc.open("a") as f:
                f.write("\n# Added by GitPlex - SSH agent configuration\n")
                f.write('# Start SSH agent if not running\n')
                f.write('if [ -z "$SSH_AUTH_SOCK" ]; then\n')
                f.write('    eval `ssh-agent -s` > /dev/null 2>&1\n')
                f.write('fi\n\n')
                # Add all keys in .ssh directory
                f.write('# Add SSH keys if not already added\n')
                f.write('find ~/.ssh -type f -name "id_*" ! -name "*.pub" | while read key; do\n')
                f.write('    if ! ssh-add -l | grep -q "$(ssh-keygen -lf "$key" | awk \'{print $2}\')"; then\n')
                f.write('        ssh-add "$key" > /dev/null 2>&1\n')
                f.write('    fi\n')
                f.write('done\n')
            print_success("✓ Configured SSH agent to start automatically")
            print_info("Please restart your terminal or run: source " + str(shell_rc))

def verify_clone_url(url: str) -> tuple[bool, str]:
    """Verify if a Git clone URL is using the correct protocol."""
    if url.startswith("https://"):
        ssh_url = url.replace("https://", "git@").replace("/", ":", 1)
        return False, ssh_url
    return True, url

@cli.command()
@click.argument("url")
@click.option("--directory", help="Directory to clone into")
@handle_errors
def clone(url: str, directory: str | None = None) -> None:
    """Clone a repository using the correct SSH configuration."""
    # Verify URL protocol
    is_ssh, correct_url = verify_clone_url(url)
    if not is_ssh:
        print_warning("HTTPS URL detected. Converting to SSH URL...")
        print_info(f"Original URL: {url}")
        print_info(f"SSH URL: {correct_url}")
        url = correct_url
    
    # Extract provider from URL
    provider = None
    for p in ["github.com", "gitlab.com", "bitbucket.org"]:
        if p in url:
            provider = p.split(".")[0]
            break
    
    if not provider:
        raise GitplexError("Could not determine Git provider from URL")
    
    # Configure SSH agent first
    configure_ssh_agent_persistence()
    
    # Run diagnostic and fix issues
    issues = run_diagnostic(provider, fix=True)
    if issues:
        # Try to start agent and add key directly
        try:
            # Export SSH agent variables to current environment
            agent_output = subprocess.check_output(
                ["ssh-agent", "-s"],
                text=True
            )
            for line in agent_output.splitlines():
                if "=" in line:
                    var, value = line.split(";", 1)[0].split("=", 1)
                    os.environ[var] = value
            
            # Add the key
            ssh_dir = Path.home() / ".ssh"
            for key_file in ssh_dir.glob(f"*{provider}*"):
                if not key_file.name.endswith(".pub"):
                    subprocess.run(["ssh-add", key_file], check=True)
                    print_success(f"✓ Added key {key_file} to SSH agent")
        except subprocess.CalledProcessError as e:
            print_error(f"Failed to configure SSH agent: {e}")
    
    # Try to clone
    try:
        # Use GIT_SSH_COMMAND to force SSH to use the correct key
        env = os.environ.copy()
        key_path = next(Path.home().glob(f".ssh/*{provider}*"))
        if not key_path.name.endswith(".pub"):
            env["GIT_SSH_COMMAND"] = f"ssh -i {key_path}"
        
        cmd = ["git", "clone", url]
        if directory:
            cmd.append(directory)
        
        subprocess.run(cmd, env=env, check=True)
        print_success("✓ Repository cloned successfully")
    except subprocess.CalledProcessError as e:
        print_error("Failed to clone repository")
        print_info("\nTroubleshooting steps:")
        print_info("1. Run: ssh -vT git@" + provider + ".com")
        print_info("2. Check if your SSH key is added to " + provider.title() + ":")
        print_info("   " + provider + ".com/settings/keys")
        print_info("3. Try running: eval `ssh-agent -s` && ssh-add")
        raise click.Abort()
