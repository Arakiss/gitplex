"""Backup and configuration management utilities."""

import shutil
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from .exceptions import SystemConfigError
from .ui import print_backup_info, print_info

logger = logging.getLogger(__name__)

def check_existing_configs() -> dict[str, bool]:
    """Check for existing Git and SSH configurations."""
    logger.debug("Checking for existing configurations")
    git_config = Path.home() / ".gitconfig"
    ssh_dir = Path.home() / ".ssh"
    ssh_config = ssh_dir / "config"

    configs = {
        "git_config_exists": git_config.exists(),
        "ssh_config_exists": ssh_config.exists(),
    }
    
    logger.debug(f"Found configurations: {configs}")
    return configs


def create_backup_dir() -> Path:
    """Create backup directory if it doesn't exist."""
    logger.debug("Creating backup directory")
    backup_dir = Path.home() / ".gitplex" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Backup directory: {backup_dir}")
    return backup_dir


def backup_git_config() -> Path:
    """Backup global Git configuration."""
    logger.debug("Starting Git config backup")
    git_config = Path.home() / ".gitconfig"
    if not git_config.exists():
        logger.debug("No Git config found to backup")
        return None

    try:
        backup_dir = create_backup_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"gitconfig_backup_{timestamp}"

        shutil.copy2(git_config, backup_path)
        logger.debug(f"Git config backed up to: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Failed to backup Git config: {e}", exc_info=True)
        raise SystemConfigError(f"Failed to backup Git config: {e}")


def backup_ssh_config() -> Path:
    """Backup SSH configuration and keys."""
    logger.debug("Starting SSH config backup")
    ssh_dir = Path.home() / ".ssh"
    if not ssh_dir.exists():
        logger.debug("No SSH config found to backup")
        return None

    try:
        backup_dir = create_backup_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"ssh_backup_{timestamp}"

        # Create a tarfile with SSH config and keys
        shutil.make_archive(str(backup_path), "tar", ssh_dir)
        logger.debug(f"SSH config backed up to: {backup_path}.tar")
        return Path(f"{backup_path}.tar")
    except Exception as e:
        logger.error(f"Failed to backup SSH config: {e}", exc_info=True)
        raise SystemConfigError(f"Failed to backup SSH config: {e}")


def restore_git_config(backup_path: Path) -> None:
    """Restore Git configuration from backup."""
    if not backup_path.exists():
        raise SystemConfigError(f"Backup file not found: {backup_path}")

    git_config = Path.home() / ".gitconfig"
    shutil.copy2(backup_path, git_config)
    print_info(f"Git config restored from {backup_path}")


def restore_ssh_config(backup_path: Path) -> None:
    """Restore SSH configuration from backup."""
    if not backup_path.exists():
        raise SystemConfigError(f"Backup file not found: {backup_path}")

    ssh_dir = Path.home() / ".ssh"
    if ssh_dir.exists():
        # Create a backup of current SSH config before restoring
        backup_ssh_config()

    # Extract the backup
    shutil.unpack_archive(backup_path, ssh_dir)
    print_info(f"SSH config restored from {backup_path}")


def backup_configs() -> tuple[Path | None, Path | None]:
    """Backup both Git and SSH configurations."""
    logger.debug("Starting backup of all configurations")
    try:
        git_backup = backup_git_config()
        ssh_backup = backup_ssh_config()

        if git_backup:
            print_backup_info(git_backup, "Git configuration")
        if ssh_backup:
            print_backup_info(ssh_backup, "SSH configuration")

        logger.debug("Backup completed successfully")
        return git_backup, ssh_backup
    except Exception as e:
        logger.error(f"Backup failed: {e}", exc_info=True)
        raise


def generate_ssh_key(email: str, key_name: str) -> tuple[Path, Path]:
    """Generate a new SSH key pair."""
    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)

    key_path = ssh_dir / key_name
    if key_path.exists() or key_path.with_suffix(".pub").exists():
        raise SystemConfigError(f"SSH key already exists: {key_path}")

    # Generate ED25519 key (more secure than RSA)
    try:
        cmd = [
            "ssh-keygen",
            "-t", "ed25519",
            "-C", email,
            "-f", str(key_path),
            "-N", "",  # Empty passphrase for automation
        ]
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        msg = f"Failed to generate SSH key: {e.stderr.decode()}"
        raise SystemConfigError(msg) from e

    return key_path, key_path.with_suffix(".pub")


def update_ssh_config(key_path: Path, host: str) -> None:
    """Update SSH config to use the specified key for a host."""
    ssh_dir = Path.home() / ".ssh"
    config_path = ssh_dir / "config"

    # Create config if it doesn't exist
    if not config_path.exists():
        config_path.touch()

    # Read existing config
    config = config_path.read_text() if config_path.exists() else ""

    # Check if host already exists
    host_exists = any(
        line.strip().startswith(f"Host {host}")
        for line in config.splitlines()
    )

    if not host_exists:
        # Add new host configuration
        new_config = f"""
# Added by GitPlex
Host {host}
    IdentityFile {key_path}
    UseKeychain yes
    AddKeysToAgent yes
"""
        with config_path.open("a") as f:
            f.write(new_config)

    # Set correct permissions
    config_path.chmod(0o600)