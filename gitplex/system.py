"""System utilities and backup functionality."""

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from gitplex.exceptions import BackupError, SystemConfigError


def check_git_installation() -> tuple[bool, str]:
    """Check if Git is installed and get its version.

    Returns:
        Tuple of (is_installed, version_string)
    """
    try:
        result = subprocess.run(
            ["git", "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise SystemConfigError(
            "Git is not installed or not accessible",
            details=f"Error: {e.stderr}",
        )
    except FileNotFoundError:
        raise SystemConfigError(
            "Git is not installed",
            details="Please install Git to use this tool",
        )


def check_ssh_agent() -> bool:
    """Check if SSH agent is running.

    Returns:
        True if SSH agent is running
    """
    try:
        result = subprocess.run(
            ["ssh-add", "-l"],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        if e.returncode == 1:  # No identities
            return True
        raise SystemConfigError(
            "SSH agent is not running",
            details="Please start the SSH agent with 'eval $(ssh-agent)'",
        )
    except FileNotFoundError:
        raise SystemConfigError(
            "SSH is not installed",
            details="Please install OpenSSH to use this tool",
        )


def get_home_dir() -> Path:
    """Get home directory.

    Returns:
        Home directory path
    """
    if "GITPLEX_TEST_HOME" in os.environ:
        return Path(os.environ["GITPLEX_TEST_HOME"])
    return Path.home()


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
    """Check if the system has all required dependencies."""
    try:
        # Check Git installation
        is_git_installed, git_version = check_git_installation()
        print("Git version:", git_version)

        # Check SSH agent
        if check_ssh_agent():
            print("SSH agent is running")
    except SystemConfigError as e:
        raise SystemConfigError(
            "System compatibility check failed",
            details=f"{e.message}\n{e.details}",
        )


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
