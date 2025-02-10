"""System compatibility and configuration module."""

import json
import os
import shutil
import subprocess
import logging
from datetime import datetime
from pathlib import Path
import platform
from typing import Any, Dict, List, Optional

from .exceptions import BackupError, SystemConfigError
from .ui_common import (
    console,
    print_error,
    print_info,
    print_success,
    print_warning,
)

logger = logging.getLogger(__name__)


def check_git_installation() -> tuple[bool, str]:
    """Check if Git is installed and get its version.

    Returns:
        Tuple of (is_installed, version_string)
    """
    logger.debug("Checking Git installation")
    try:
        result = subprocess.run(
            ["git", "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.debug(f"Git version: {result.stdout.strip()}")
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"Git check failed: {e.stderr}")
        raise SystemConfigError(
            "Git is not installed or not accessible",
            details=f"Error: {e.stderr}",
        )
    except FileNotFoundError:
        logger.error("Git not found")
        raise SystemConfigError(
            "Git is not installed",
            details="Please install Git to use this tool",
        )


def check_ssh_agent() -> bool:
    """Check if SSH agent is running.

    Returns:
        True if SSH agent is running
    """
    logger.debug("Checking SSH agent")
    try:
        result = subprocess.run(
            ["ssh-add", "-l"],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.debug("SSH agent check successful")
        return True
    except subprocess.CalledProcessError as e:
        logger.debug(f"SSH agent check returned code {e.returncode}")
        if e.returncode == 1:  # No identities
            return True
        logger.error("SSH agent not running")
        raise SystemConfigError(
            "SSH agent is not running",
            details="Please start the SSH agent with 'eval $(ssh-agent)'",
        )
    except FileNotFoundError:
        logger.error("SSH not installed")
        raise SystemConfigError(
            "SSH is not installed",
            details="Please install OpenSSH to use this tool",
        )


def get_home_dir() -> Path:
    """Get the user's home directory based on the OS."""
    os_info = get_os_info()
    system = os_info["system"]
    
    if system == "windows":
        # On Windows, we use USERPROFILE
        home = Path(subprocess.getoutput("echo %USERPROFILE%"))
    else:
        # On Unix-like systems (Linux, macOS), we use HOME
        home = Path(subprocess.getoutput("echo $HOME"))
    
    logger.debug(f"Using home directory: {home}")
    return home


def get_existing_configs() -> Dict[str, Any]:
    """Get detailed information about existing Git and SSH configurations.

    Returns:
        Dictionary containing information about existing configurations
    """
    home = get_home_dir()
    configs = {
        "git": {
            "global_config": home / ".gitconfig",
            "exists": False,
            "email": None,
            "username": None,
            "providers": [],
        },
        "ssh": {
            "config": home / ".ssh" / "config",
            "keys_dir": home / ".ssh",
            "exists": False,
            "keys": [],
            "providers": [],
        }
    }
    
    # Check Git config
    git_config = configs["git"]["global_config"]
    if git_config.exists():
        configs["git"]["exists"] = True
        try:
            # Get Git config values
            email = subprocess.run(
                ["git", "config", "--global", "user.email"],
                capture_output=True,
                text=True,
                check=True
            ).stdout.strip()
            username = subprocess.run(
                ["git", "config", "--global", "user.name"],
                capture_output=True,
                text=True,
                check=True
            ).stdout.strip()
            
            configs["git"]["email"] = email
            configs["git"]["username"] = username
            
            # Try to detect providers from remotes
            try:
                remotes = subprocess.run(
                    ["git", "remote", "-v"],
                    capture_output=True,
                    text=True,
                    check=True
                ).stdout
                
                for remote in remotes.splitlines():
                    if "github.com" in remote:
                        if "github" not in configs["git"]["providers"]:
                            configs["git"]["providers"].append("github")
                    elif "gitlab.com" in remote:
                        if "gitlab" not in configs["git"]["providers"]:
                            configs["git"]["providers"].append("gitlab")
                    elif "bitbucket.org" in remote:
                        if "bitbucket" not in configs["git"]["providers"]:
                            configs["git"]["providers"].append("bitbucket")
                    elif "dev.azure.com" in remote:
                        if "azure" not in configs["git"]["providers"]:
                            configs["git"]["providers"].append("azure")
            except subprocess.CalledProcessError:
                # Not in a git repository, ignore
                pass
                
        except subprocess.CalledProcessError:
            # Config exists but values not set
            pass
    
    # Check SSH config and keys
    ssh_dir = configs["ssh"]["keys_dir"]
    if ssh_dir.exists():
        configs["ssh"]["exists"] = True
        
        # Check SSH config
        ssh_config = configs["ssh"]["config"]
        if ssh_config.exists():
            config_content = ssh_config.read_text()
            
            # Try to detect providers from SSH config
            for provider in ["github.com", "gitlab.com", "bitbucket.org", "dev.azure.com"]:
                if provider in config_content:
                    provider_name = provider.split(".")[0]
                    if provider_name not in configs["ssh"]["providers"]:
                        configs["ssh"]["providers"].append(provider_name)
        
        # List SSH keys
        for key_file in ssh_dir.glob("id_*"):
            if key_file.suffix != ".pub":
                key_info = {
                    "path": key_file,
                    "type": key_file.stem.split("_")[-1],
                    "name": key_file.stem,
                }
                
                # Try to get key comment (usually contains email)
                pub_key = key_file.with_suffix(".pub")
                if pub_key.exists():
                    try:
                        key_comment = pub_key.read_text().strip().split(" ")[-1]
                        key_info["comment"] = key_comment
                    except Exception:
                        pass
                
                configs["ssh"]["keys"].append(key_info)
    
    return configs


def backup_configs() -> Path:
    """Backup Git and SSH configurations.
    
    Returns:
        Path to backup directory
    """
    try:
        # Create backup directory with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = Path.home() / ".gitplex" / "backups" / f"backup_{timestamp}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Backup Git config
        git_config = Path.home() / ".gitconfig"
        if git_config.exists():
            shutil.copy2(git_config, backup_dir / "gitconfig")
            logger.debug(f"Git config backed up to {backup_dir / 'gitconfig'}")
        
        # Backup SSH config and keys
        ssh_dir = Path.home() / ".ssh"
        if ssh_dir.exists():
            ssh_backup_dir = backup_dir / "ssh"
            ssh_backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Backup SSH config
            ssh_config = ssh_dir / "config"
            if ssh_config.exists():
                shutil.copy2(ssh_config, ssh_backup_dir / "config")
                logger.debug(f"SSH config backed up to {ssh_backup_dir / 'config'}")
            
            # Backup SSH keys
            for key_file in ssh_dir.glob("id_*"):
                shutil.copy2(key_file, ssh_backup_dir / key_file.name)
                logger.debug(f"SSH key {key_file.name} backed up to {ssh_backup_dir / key_file.name}")
            
            # Backup known_hosts
            known_hosts = ssh_dir / "known_hosts"
            if known_hosts.exists():
                shutil.copy2(known_hosts, ssh_backup_dir / "known_hosts")
                logger.debug(f"known_hosts backed up to {ssh_backup_dir / 'known_hosts'}")
        
        return backup_dir
        
    except Exception as e:
        logger.error(f"Failed to backup configurations: {e}")
        raise SystemConfigError(f"Failed to backup configurations: {e}")


def restore_configs(backup_path: Path) -> None:
    """Restore Git and SSH configurations from backup.
    
    Args:
        backup_path: Path to backup directory
    """
    try:
        if not backup_path.exists():
            raise SystemConfigError(f"Backup directory not found: {backup_path}")
        
        # Restore Git config
        git_backup = backup_path / "gitconfig"
        if git_backup.exists():
            shutil.copy2(git_backup, Path.home() / ".gitconfig")
            logger.debug("Git config restored")
        
        # Restore SSH config and keys
        ssh_backup_dir = backup_path / "ssh"
        if ssh_backup_dir.exists():
            ssh_dir = Path.home() / ".ssh"
            ssh_dir.mkdir(parents=True, exist_ok=True)
            
            # Restore SSH config
            ssh_config_backup = ssh_backup_dir / "config"
            if ssh_config_backup.exists():
                shutil.copy2(ssh_config_backup, ssh_dir / "config")
                logger.debug("SSH config restored")
            
            # Restore SSH keys
            for key_file in ssh_backup_dir.glob("id_*"):
                shutil.copy2(key_file, ssh_dir / key_file.name)
                # Ensure correct permissions for private keys
                if not key_file.name.endswith(".pub"):
                    (ssh_dir / key_file.name).chmod(0o600)
                logger.debug(f"SSH key {key_file.name} restored")
            
            # Restore known_hosts
            known_hosts_backup = ssh_backup_dir / "known_hosts"
            if known_hosts_backup.exists():
                shutil.copy2(known_hosts_backup, ssh_dir / "known_hosts")
                logger.debug("known_hosts restored")
        
    except Exception as e:
        logger.error(f"Failed to restore configurations: {e}")
        raise SystemConfigError(f"Failed to restore configurations: {e}")


def check_system_compatibility() -> None:
    """Check system compatibility and requirements."""
    try:
        # Check Git installation
        try:
            subprocess.run(
                ["git", "--version"],
                check=True,
                capture_output=True,
                text=True,
            )
            print_success("Git is installed")
        except subprocess.CalledProcessError:
            raise SystemConfigError("Git is not installed")
        
        # Check SSH installation
        try:
            subprocess.run(
                ["ssh", "-V"],
                check=True,
                capture_output=True,
                text=True,
            )
            print_success("SSH is installed")
        except subprocess.CalledProcessError:
            raise SystemConfigError("SSH is not installed")
        
        # Check SSH agent
        if not os.environ.get("SSH_AUTH_SOCK"):
            print_warning("SSH agent is not running")
        else:
            print_success("SSH agent is running")
        
        # Check write permissions
        home = Path.home()
        gitconfig = home / ".gitconfig"
        ssh_dir = home / ".ssh"
        
        # Check .gitconfig
        if gitconfig.exists() and not os.access(gitconfig, os.W_OK):
            raise SystemConfigError("No write permission for .gitconfig")
        
        # Check .ssh directory
        if ssh_dir.exists() and not os.access(ssh_dir, os.W_OK):
            raise SystemConfigError("No write permission for .ssh directory")
        
        print_success("System compatibility check passed")
    except Exception as e:
        logger.error("System compatibility check failed", exc_info=True)
        raise SystemConfigError(f"System compatibility check failed: {e}") from e


def _check_ssh_agent_windows() -> None:
    """Check SSH agent on Windows."""
    try:
        result = subprocess.run(
            ["sc", "query", "ssh-agent"],
            capture_output=True,
            text=True
        )
        if "RUNNING" not in result.stdout:
            print_warning(
                "SSH agent is not running on Windows. "
                "Please enable OpenSSH Authentication Agent service"
            )
    except subprocess.CalledProcessError as e:
        logger.error("Failed to check SSH agent status on Windows", exc_info=True)
        raise SystemConfigError(
            "Unable to verify SSH agent status on Windows"
        ) from e


def _check_ssh_agent_unix(os_name: str) -> None:
    """Check SSH agent on Unix-like systems."""
    try:
        result = subprocess.run(
            ["ssh-add", "-l"],
            capture_output=True,
            text=True
        )
        if result.returncode == 2:
            print_warning(
                f"SSH agent is not running on {os_name}. "
                "Please start it with: eval `ssh-agent -s`"
            )
        logger.debug(f"SSH agent check returned code {result.returncode}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to check SSH agent status on {os_name}", exc_info=True)
        raise SystemConfigError(
            f"Unable to verify SSH agent status on {os_name}"
        ) from e


def get_os_info() -> Dict[str, Any]:
    """Get detailed information about the operating system.
    
    Returns:
        Dictionary containing OS information
    """
    return {
        'system': platform.system().lower(),
        'release': platform.release(),
        'version': platform.version(),
        'machine': platform.machine(),
        'processor': platform.processor()
    }

def get_os_display_name() -> str:
    """Get a user-friendly display name for the current OS.
    
    Returns:
        String containing OS name and version
    """
    os_info = get_os_info()
    system = os_info['system']
    
    if system == 'darwin':
        return f"macOS {os_info['release']}"
    elif system == 'linux':
        return f"Linux {os_info['release']}"
    elif system == 'windows':
        return f"Windows {os_info['release']}"
    else:
        return f"Unknown OS ({system} {os_info['release']})"

def get_system_info() -> dict[str, str]:
    """Get system information.
    
    Returns:
        Dictionary containing system information
    """
    return {
        "os": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
    }

def clean_existing_configs() -> None:
    """Remove ALL Git and SSH configurations.
    
    WARNING: This is a destructive operation that will remove:
    - Global Git config (~/.gitconfig)
    - ALL SSH keys and configurations in ~/.ssh
    - GPG keys containing 'gitplex' (if GPG is installed)
    - GitPlex profiles and settings
    
    Make sure to backup any important configurations before calling this function.
    """
    home = get_home_dir()
    cleaned_items = []
    existing_items = []
    
    # Check Git config
    git_config = home / ".gitconfig"
    if git_config.exists():
        existing_items.append(f"Global Git config: {git_config}")
        try:
            git_config.unlink()
            cleaned_items.append(f"Global Git config: {git_config}")
        except OSError as e:
            print_error(f"Failed to remove Git config: {e}")
    
    # Check SSH config and keys
    ssh_dir = home / ".ssh"
    if ssh_dir.exists():
        # Handle SSH config
        ssh_config = ssh_dir / "config"
        if ssh_config.exists():
            existing_items.append(f"SSH config: {ssh_config}")
            try:
                # Backup original config
                backup_path = ssh_config.with_suffix(".bak")
                shutil.copy2(ssh_config, backup_path)
                print_success(f"Original SSH config backed up to: {backup_path}")
                
                # Remove the config file completely
                ssh_config.unlink()
                cleaned_items.append(f"SSH config: {ssh_config}")
            except OSError as e:
                print_error(f"Failed to remove SSH config: {e}")
        
        # Remove ALL SSH keys
        removed_keys = []
        for key_file in ssh_dir.glob("id_*"):
            existing_items.append(f"SSH key: {key_file}")
            try:
                key_file.unlink(missing_ok=True)
                pub_key = key_file.with_suffix(".pub")
                if pub_key.exists():
                    pub_key.unlink()
                removed_keys.append(key_file.name)
            except OSError as e:
                print_error(f"Failed to remove SSH key {key_file}: {e}")
        
        if removed_keys:
            cleaned_items.append(f"SSH keys in {ssh_dir}: {', '.join(removed_keys)}")
    
    # Check GPG configurations (only GitPlex-related ones for safety)
    try:
        # Check if GPG is installed
        subprocess.run(
            ["gpg", "--version"],
            capture_output=True,
            check=True,
        )
        
        # List and remove GitPlex GPG keys
        result = subprocess.run(
            ["gpg", "--list-secret-keys", "--keyid-format", "LONG"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if "gitplex" in line.lower():
                    try:
                        key_id = line.split("/")[1].split(" ")[0]
                        existing_items.append(f"GPG key: {key_id}")
                        subprocess.run(
                            ["gpg", "--delete-secret-and-public-key", "--yes", key_id],
                            capture_output=True,
                            check=True,
                        )
                        cleaned_items.append(f"GPG key: {key_id}")
                    except (subprocess.CalledProcessError, IndexError) as e:
                        print_error(f"Failed to remove GPG key: {e}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print_warning("GPG is not installed, skipping GPG cleanup")
    
    # Remove GitPlex directory
    gitplex_dir = home / ".gitplex"
    if gitplex_dir.exists():
        existing_items.append(f"GitPlex data directory: {gitplex_dir}")
        try:
            shutil.rmtree(gitplex_dir)
            cleaned_items.append(f"GitPlex data directory: {gitplex_dir}")
        except OSError as e:
            print_error(f"Failed to remove GitPlex directory: {e}")
    
    # Print summary
    if not existing_items:
        print_info("No existing configurations found - starting with a clean slate")
    else:
        if cleaned_items:
            console.print("\n[bold green]Cleaned configurations:[/bold green]")
            for item in cleaned_items:
                console.print(f"[green]✓[/green] {item}")
        else:
            print_warning("Found configurations but failed to clean them. Check the errors above.")

def clean_provider_configs(provider: str | None = None, profile_name: str | None = None) -> None:
    """Clean provider-specific configurations.
    
    Args:
        provider: Provider name to clean (e.g., 'github', 'azure')
        profile_name: Profile name to clean
    """
    home = Path.home()
    ssh_dir = home / ".ssh"
    ssh_config = ssh_dir / "config"
    gitplex_dir = home / ".gitplex"
    
    # Clean SSH keys for specific provider
    if provider:
        for key_file in ssh_dir.glob(f"id_*{provider}*"):
            try:
                key_file.unlink()
                pub_key = key_file.with_suffix(".pub")
                if pub_key.exists():
                    pub_key.unlink()
                print_success(f"Removed SSH key: {key_file}")
            except Exception as e:
                print_warning(f"Could not remove {key_file}: {e}")
    
    # Clean SSH config entries for provider
    if ssh_config.exists():
        config_content = ssh_config.read_text()
        new_content = []
        skip_block = False
        
        for line in config_content.splitlines():
            if provider:
                if line.strip().startswith(f"Host {provider}") or line.strip().startswith(f"Host *.{provider}"):
                    skip_block = True
                    continue
                elif line.strip() and not line.startswith(" ") and not line.startswith("\t"):
                    skip_block = False
            
            if not skip_block:
                new_content.append(line)
        
        ssh_config.write_text("\n".join(new_content))
        print_success("Updated SSH config")
    
    # Clean profile-specific data
    if profile_name:
        profile_dir = gitplex_dir / "profiles" / profile_name
        if profile_dir.exists():
            try:
                import shutil
                shutil.rmtree(profile_dir)
                print_success(f"Removed profile directory: {profile_dir}")
            except Exception as e:
                print_warning(f"Could not remove profile directory: {e}")
        
        # Also clean any profile-specific Git config
        git_config = home / ".gitconfig"
        if git_config.exists():
            try:
                subprocess.run(["git", "config", "--global", "--remove-section", f"profile.{profile_name}"], check=False)
                print_success("Removed profile-specific Git config")
            except Exception as e:
                print_warning(f"Could not remove Git config section: {e}")
    
    print_success("Provider-specific cleanup completed")
