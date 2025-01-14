"""Git configuration management."""

import logging
from pathlib import Path
from typing import Optional, List

from .exceptions import SystemConfigError

logger = logging.getLogger(__name__)

class GitConfig:
    """Manages Git configuration for a profile."""
    
    def __init__(self, profile_name: str) -> None:
        """Initialize Git configuration manager."""
        self.profile_name = profile_name
        self.global_config = Path.home() / ".gitconfig"

    def setup_config(
        self,
        email: str,
        username: str,
        ssh_key_path: Optional[Path],
        providers: List[str],
        directory: Path,
    ) -> None:
        """Set up Git configuration for a workspace."""
        # Create workspace directory if it doesn't exist
        directory.mkdir(parents=True, exist_ok=True)

        # Create workspace-specific config
        workspace_config = directory / ".gitconfig"
        workspace_config.write_text(
            f"""[user]
    email = {email}
    name = {username}

[core]
    sshCommand = "ssh -i {ssh_key_path if ssh_key_path else '~/.ssh/id_' + self.profile_name + '_ed25519'}"

[init]
    defaultBranch = main
"""
        )

        # Add includeIf to global config
        if not self.global_config.exists():
            self.global_config.touch()

        global_content = self.global_config.read_text()
        workspace_section = f"""
[includeIf "gitdir:{directory}/"]
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
