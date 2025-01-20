"""Backup and configuration management utilities."""

import os
import shutil
import subprocess
import logging
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .exceptions import SystemConfigError, GitplexError
from .ui_common import print_error, print_info, print_success, print_warning

logger = logging.getLogger(__name__)

GITPLEX_DIR = Path.home() / ".gitplex"
BACKUP_DIR = GITPLEX_DIR / "backups"
GIT_CONFIG = Path.home() / ".gitconfig"
SSH_CONFIG = Path.home() / ".ssh" / "config"

def check_existing_configs() -> bool:
    """Check for existing Git and SSH configurations.
    
    Returns:
        True if any configurations exist, False otherwise
    """
    return any([
        GIT_CONFIG.exists(),
        SSH_CONFIG.exists(),
    ])

def backup_configs() -> Path:
    """Back up existing Git and SSH configurations.
    
    Returns:
        Path to backup directory
    """
    try:
        # Create backup directory with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"backup_{timestamp}"
        backup_path.mkdir(parents=True, exist_ok=True)
        
        # Back up Git config
        if GIT_CONFIG.exists():
            git_backup = backup_path / "gitconfig_backup.tar"
            with tarfile.open(git_backup, "w:gz") as tar:
                tar.add(GIT_CONFIG, arcname=GIT_CONFIG.name)
            print_success("Git configuration backed up")
        
        # Back up SSH config
        if SSH_CONFIG.exists():
            ssh_backup = backup_path / "ssh_backup.tar"
            with tarfile.open(ssh_backup, "w:gz") as tar:
                tar.add(SSH_CONFIG, arcname=SSH_CONFIG.name)
            print_success("SSH configuration backed up")
        
        return backup_path
    except Exception as e:
        raise GitplexError(f"Failed to create backup: {e}") from e

def restore_git_config(backup_path: Path) -> None:
    """Restore Git configuration from backup.
    
    Args:
        backup_path: Path to backup directory
    """
    try:
        git_backup = backup_path / "gitconfig_backup.tar"
        if not git_backup.exists():
            raise GitplexError("Git configuration backup not found")
        
        # Extract backup
        with tarfile.open(git_backup, "r:gz") as tar:
            tar.extractall(Path.home())
        
        print_success("Git configuration restored")
    except Exception as e:
        raise GitplexError(f"Failed to restore Git configuration: {e}") from e

def restore_ssh_config(backup_path: Path) -> None:
    """Restore SSH configuration from backup.
    
    Args:
        backup_path: Path to backup directory
    """
    try:
        ssh_backup = backup_path / "ssh_backup.tar"
        if not ssh_backup.exists():
            raise GitplexError("SSH configuration backup not found")
        
        # Extract backup
        with tarfile.open(ssh_backup, "r:gz") as tar:
            tar.extractall(Path.home())
        
        print_success("SSH configuration restored")
    except Exception as e:
        raise GitplexError(f"Failed to restore SSH configuration: {e}") from e

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