"""System utilities and backup functionality."""

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from gitplex.exceptions import BackupError, SystemConfigError


def check_git_installation() -> Tuple[bool, str]:
    """Check if Git is installed and get its version.
    
    Returns:
        Tuple of (is_installed, version_string)
    """
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        return True, result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return False, ""


def check_ssh_agent() -> bool:
    """Check if SSH agent is running.
    
    Returns:
        True if running, False otherwise
    """
    try:
        result = subprocess.run(
            ["ssh-add", "-l"],
            capture_output=True,
            text=True,
        )
        return result.returncode in (0, 1)  # 0: has keys, 1: no keys but running
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def get_existing_configs() -> Dict[str, Path]:
    """Get paths of existing Git and SSH configurations.
    
    Returns:
        Dictionary of config names and their paths
    """
    home = Path.home()
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
    config_paths: Dict[str, Path],
    backup_dir: Optional[Path] = None,
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
    backup_root = backup_dir or Path.home() / ".gitplex" / "backups"
    backup_path = backup_root / f"backup_{timestamp}"
    
    try:
        backup_path.mkdir(parents=True, exist_ok=True)
        
        # Copy each config
        for name, path in config_paths.items():
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
        )


def check_system_compatibility() -> List[str]:
    """Check system compatibility and return warnings.
    
    Returns:
        List of warning messages
    """
    warnings = []
    
    # Check Git
    git_installed, git_version = check_git_installation()
    if not git_installed:
        raise SystemConfigError(
            "Git is not installed",
            "Please install Git before using GitPlex"
        )
    
    # Check SSH agent
    if not check_ssh_agent():
        warnings.append(
            "SSH agent is not running. Some features may not work properly.\n"
            "Run 'eval $(ssh-agent)' to start it."
        )
    
    # Check existing configs
    configs = get_existing_configs()
    if configs:
        warnings.append(
            "Existing Git/SSH configurations found. They will be backed up\n"
            "before any modifications."
        )
    
    return warnings


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
        ) 