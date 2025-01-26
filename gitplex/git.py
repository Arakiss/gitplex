"""Git configuration management."""

import logging
from pathlib import Path
from typing import Optional, List

from .exceptions import SystemConfigError

logger = logging.getLogger(__name__)

class GitConfig:
    """Manages Git configuration for a profile."""
    
    def __init__(
        self,
        profile_name: str,
        email: str,
        username: str,
        provider: str,
        ssh_key: Path,
        workspace_dir: Path,
        gpg_key: Optional[str] = None,
    ) -> None:
        """Initialize Git configuration manager.
        
        Args:
            profile_name: Name of the profile
            email: Git email
            username: Git username
            provider: Git provider name
            ssh_key: Path to SSH key
            workspace_dir: Path to workspace directory
            gpg_key: GPG key ID for signing commits
        """
        self.profile_name = profile_name
        self.email = email
        self.username = username
        self.provider = provider
        self.ssh_key = ssh_key
        self.workspace_dir = workspace_dir
        self.gpg_key = gpg_key
        self.global_config = Path.home() / ".gitconfig"
        
        # Set up configuration immediately
        self.setup_config()

    def setup_config(self) -> None:
        """Set up Git configuration for the workspace."""
        # Create workspace directory if it doesn't exist
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        # Create workspace-specific config
        workspace_config = self.workspace_dir / ".gitconfig"
        config_content = f"""[user]
    email = {self.email}
    name = {self.username}
"""

        if self.gpg_key:
            config_content += f"""    signingkey = {self.gpg_key}

[commit]
    gpgsign = true

[tag]
    gpgsign = true

[gpg]
    program = gpg
"""

        config_content += f"""
[core]
    sshCommand = "ssh -i {self.ssh_key}"

[init]
    defaultBranch = main

[{self.provider}]
    user = {self.username}
"""
        workspace_config.write_text(config_content)

        # Add includeIf to global config
        if not self.global_config.exists():
            self.global_config.touch()

        global_content = self.global_config.read_text()
        workspace_section = f"""
[includeIf "gitdir:{self.workspace_dir}/"]
    path = {workspace_config}
"""
        if workspace_section not in global_content:
            self.global_config.write_text(global_content + workspace_section)

    def update(self, name: str, email: str, username: str) -> None:
        """Update Git configuration."""
        # This method now only needs to update the global config if needed
        pass

    def remove_config(self, directory: Path) -> None:
        """Remove Git configuration for a workspace."""
        # Remove workspace config
        workspace_config = directory / ".gitconfig"
        if workspace_config.exists():
            workspace_config.unlink()
        
        # Remove include statement from global config
        if self.global_config.exists():
            current_config = self.global_config.read_text()
            workspace_section = f"""
[includeIf "gitdir:{directory}/"]
    path = {workspace_config}
"""
            new_config = current_config.replace(workspace_section, "")
            self.global_config.write_text(new_config)
        
        logger.debug(f"Git config removed for workspace {directory}")
