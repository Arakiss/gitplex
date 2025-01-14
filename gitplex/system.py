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


def create_backup(
    config_paths: dict[str, Path],
    backup_dir: Path | None = None,
) -> Path:
    """Create a backup of existing configurations.

    Args:
        config_paths: Paths to configurations to backup
        backup_dir: Optional custom backup directory

    Returns:
        Path to backup directory

    Raises:
        BackupError: If backup fails
    """
    # Create backup directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = backup_dir or get_home_dir() / ".gitplex" / "backups"
    backup_path = backup_root / f"backup_{timestamp}"

    try:
        backup_path.mkdir(parents=True, exist_ok=True)

        # Copy each config
        for _name, path in config_paths.items():
            if path.is_file():
                shutil.copy2(path, backup_path / path.name)
            elif path.is_dir():
                shutil.copytree(path, backup_path / path.name)

        # Save backup metadata
        metadata = {
            "timestamp": timestamp,
            "configs": {
                name: str(path) for name, path in config_paths.items()
            }
        }
        (backup_path / "metadata.json").write_text(json.dumps(metadata, indent=2))

        return backup_path

    except (OSError, shutil.Error) as e:
        raise BackupError(
            "Failed to create backup",
            f"Error: {str(e)}"
        ) from e


def check_system_compatibility() -> None:
    """Check if the current system is compatible with GitPlex."""
    os_info = get_os_info()
    logger.debug(f"Starting system compatibility check")
    logger.debug(f"Detected OS info: {os_info}")
    
    # Log OS information
    logger.debug(f"Running on {os_info['system']} {os_info['release']} ({os_info['machine']})")
    
    # Display OS information to user
    print_info(f"Running on {get_os_display_name()}")
    
    # Check Git installation
    logger.debug("Checking Git installation")
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        git_version = result.stdout.strip()
        logger.debug(f"Git version: {git_version}")
        print_info(f"Git version: {git_version}")
    except subprocess.CalledProcessError:
        raise SystemConfigError("Git is not installed or not accessible")
    
    # Check SSH agent
    logger.debug("Checking SSH agent")
    result = subprocess.run(
        ["ssh-add", "-l"],
        capture_output=True,
        text=True
    )
    logger.debug(f"SSH agent check returned code {result.returncode}")
    
    if result.returncode == 2:
        raise SystemConfigError(
            "SSH agent is not running. Please start it with:\n"
            "eval `ssh-agent -s`"
        )
    
    logger.debug("System compatibility check completed successfully")


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


def restore_backup(backup_path: Path) -> None:
    """Restore a backup.

    Args:
        backup_path: Path to backup directory

    Raises:
        BackupError: If restore fails
    """
    try:
        # Read metadata
        metadata = json.loads((backup_path / "metadata.json").read_text())

        # Restore each config
        for name, path_str in metadata["configs"].items():
            path = Path(path_str)
            backup_item = backup_path / path.name

            if backup_item.is_file():
                shutil.copy2(backup_item, path)
            elif backup_item.is_dir():
                if path.exists():
                    shutil.rmtree(path)
                shutil.copytree(backup_item, path)

    except (OSError, shutil.Error, json.JSONDecodeError) as e:
        raise BackupError(
            "Failed to restore backup",
            f"Error: {str(e)}"
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
