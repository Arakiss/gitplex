"""Workspace and Git configuration management module for GitPlex."""

import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import git
from rich.prompt import Confirm

from .exceptions import GitplexError
from .ui import print_error, print_info, print_success, print_warning

GITPLEX_DIR = Path.home() / ".gitplex"
BACKUP_DIR = GITPLEX_DIR / "backups"


@dataclass
class GitConfig:
    """Git configuration for a profile."""
    email: str
    username: str
    provider: str
    ssh_key: Path
    workspace_dir: Path


def setup_gitplex_directory() -> None:
    """Set up GitPlex directory structure."""
    GITPLEX_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)


def backup_git_config() -> Path:
    """Backup current Git configuration.
    
    Returns:
        Path to the backup file
    """
    setup_gitplex_directory()
    
    # Create backup filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"gitconfig_backup_{timestamp}"
    
    # Check for existing global config
    global_config = Path.home() / ".gitconfig"
    if global_config.exists():
        shutil.copy2(global_config, backup_file)
        print_success(f"Git config backed up to: {backup_file}")
        return backup_file
    
    print_info("No existing Git config found")
    return backup_file


def create_workspace_directory(path: Path, create: bool = True) -> Path:
    """Create and validate workspace directory.
    
    Args:
        path: Directory path
        create: Whether to create the directory if it doesn't exist
    
    Returns:
        Validated Path object
    """
    path = path.expanduser().resolve()
    
    if path.exists() and not path.is_dir():
        raise GitplexError(f"Path exists but is not a directory: {path}")
    
    if not path.exists():
        if not create:
            raise GitplexError(f"Directory does not exist: {path}")
        try:
            path.mkdir(parents=True)
            print_success(f"Created workspace directory: {path}")
        except OSError as e:
            raise GitplexError(f"Failed to create directory: {e}") from e
    
    return path


def create_git_config(config: GitConfig) -> None:
    """Create Git configuration for a profile.
    
    Args:
        config: GitConfig object with profile settings
    """
    # Create workspace directory
    workspace = create_workspace_directory(config.workspace_dir)
    
    # Create profile-specific gitconfig
    config_file = workspace / ".gitconfig"
    
    # Prepare Git configuration
    git_config = f"""[user]
    email = {config.email}
    name = {config.username}

[github]
    user = {config.username}

[core]
    sshCommand = "ssh -i {config.ssh_key}"

[init]
    defaultBranch = main
"""
    
    # Write configuration
    config_file.write_text(git_config)
    print_success(f"Created Git config: {config_file}")
    
    # Update global gitconfig to include profile config
    update_global_gitconfig(workspace)


def update_global_gitconfig(workspace: Path) -> None:
    """Update global Git configuration to include profile config.
    
    Args:
        workspace: Path to workspace directory
    """
    global_config = Path.home() / ".gitconfig"
    
    # Create if doesn't exist
    if not global_config.exists():
        global_config.touch()
    
    current_config = global_config.read_text()
    
    # Prepare includeIf directive
    include_config = f"""
[includeIf "gitdir:{workspace}/"]
    path = {workspace}/.gitconfig
"""
    
    # Check if config already exists
    if include_config.strip() in current_config:
        print_info(f"Git config for {workspace} already exists")
        return
    
    # Append new config
    with global_config.open("a") as f:
        f.write(include_config)
    
    print_success(f"Updated global Git config to include: {workspace}")


def validate_workspace(path: Path) -> bool:
    """Validate a workspace directory.
    
    Args:
        path: Directory to validate
    
    Returns:
        True if valid, False otherwise
    """
    try:
        # Check if directory exists and is writable
        if not path.exists():
            return False
        
        # Try to create a temporary file
        test_file = path / ".gitplex_test"
        test_file.touch()
        test_file.unlink()
        
        return True
    except (OSError, PermissionError):
        return False


def setup_workspace(
    profile_name: str,
    email: str,
    username: str,
    provider: str,
    ssh_key: Path,
    base_dir: Optional[Path] = None,
) -> Path:
    """Set up a new workspace for a Git profile.
    
    This function:
    1. Creates the workspace directory
    2. Backs up existing Git config
    3. Creates profile-specific Git config
    4. Updates global Git config
    
    Args:
        profile_name: Name of the Git profile
        email: Git email
        username: Git username
        provider: Git provider
        ssh_key: Path to SSH private key
        base_dir: Base directory for workspaces (default: ~/Projects)
    
    Returns:
        Path to the created workspace
    """
    # Set default base directory if not provided
    if base_dir is None:
        base_dir = Path.home() / "Projects"
    
    # Create workspace path
    workspace_dir = base_dir / profile_name
    
    # Backup existing config
    backup_git_config()
    
    # Create Git configuration
    config = GitConfig(
        email=email,
        username=username,
        provider=provider,
        ssh_key=ssh_key,
        workspace_dir=workspace_dir,
    )
    
    # Create workspace and config
    create_git_config(config)
    
    return workspace_dir


def get_workspace_git_config(workspace: Path) -> dict[str, Any]:
    """Get Git configuration for a workspace.
    
    Args:
        workspace: Path to workspace directory
    
    Returns:
        Dictionary with Git configuration
    """
    config_file = workspace / ".gitconfig"
    if not config_file.exists():
        raise GitplexError(f"Git config not found: {config_file}")
    
    try:
        repo = git.Repo(workspace)
        config = repo.config_reader()
        
        return {
            "user.name": config.get_value("user", "name"),
            "user.email": config.get_value("user", "email"),
            "github.user": config.get_value("github", "user"),
            "core.sshCommand": config.get_value("core", "sshCommand"),
        }
    except (git.InvalidGitRepositoryError, git.NoSuchPathError) as e:
        raise GitplexError(f"Failed to read Git config: {e}") from e 