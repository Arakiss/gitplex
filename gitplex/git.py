"""Git configuration management functionality."""

import configparser
import os
from pathlib import Path
from typing import Optional


def update_gitconfig(
    config_path: Path,
    name: str,
    email: str,
    username: Optional[str] = None,
) -> None:
    """Update Git configuration file.
    
    Args:
        config_path: Path to .gitconfig file
        name: Git user name
        email: Git user email
        username: Optional Git username for credentials
    """
    config = configparser.ConfigParser()
    
    # Read existing config if it exists
    if config_path.exists():
        config.read(config_path)
    
    # Update user section
    if "user" not in config:
        config["user"] = {}
    config["user"]["name"] = name
    config["user"]["email"] = email
    
    # Update credential section if username is provided
    if username:
        if "credential" not in config:
            config["credential"] = {}
        config["credential"]["username"] = username
    
    # Write updated config
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w") as f:
        config.write(f)
    os.chmod(config_path, 0o644)


def create_directory_gitconfig(
    directory: Path,
    name: str,
    email: str,
    username: Optional[str] = None,
) -> None:
    """Create a directory-specific Git configuration.
    
    Args:
        directory: Directory path
        name: Git user name
        email: Git user email
        username: Optional Git username for credentials
    """
    # Ensure directory exists
    directory = directory.expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    
    # Create .gitconfig in directory
    config_path = directory / ".gitconfig"
    update_gitconfig(config_path, name, email, username)
    
    # Update Git's global config to use directory config
    git_dir_config = configparser.ConfigParser()
    if "includeIf" not in git_dir_config:
        git_dir_config["includeIf \"gitdir:{}\"".format(str(directory))] = {
            "path": str(config_path)
        }
    
    # Write to global config
    global_config = Path.home() / ".gitconfig"
    with global_config.open("a") as f:
        git_dir_config.write(f) 