"""System utilities and backup functionality."""

import json
import os
import shutil
import subprocess
import logging
from datetime import datetime
from pathlib import Path
import platform
from typing import Any, Dict

from gitplex.exceptions import BackupError, SystemConfigError
from gitplex.ui import print_warning, print_info

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


def get_existing_configs() -> dict[str, Path]:
    """Get paths of existing Git and SSH configurations.

    Returns:
        Dictionary of config names and their paths
    """
    home = get_home_dir()
    configs = {
        "git_config": home / ".gitconfig",
        "ssh_config": home / ".ssh" / "config",
        "ssh_keys": home / ".ssh",
    }
    return {
        name: path
        for name, path in configs.items()
        if path.exists()
    }


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
    """Check system compatibility."""
    # Check OS
    os_info = platform.platform()
    print_info(f"Running on {os_info}")

    # Check Git version
    try:
        git_version = subprocess.check_output(
            ["git", "--version"], universal_newlines=True
        ).strip()
        print_info(f"Git version: {git_version}")
    except subprocess.CalledProcessError as e:
        raise SystemConfigError("Git is not installed") from e
    except FileNotFoundError as e:
        raise SystemConfigError("Git is not installed") from e


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
