"""Profile management functionality."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, model_serializer

from gitplex.git import create_directory_gitconfig, update_gitconfig
from gitplex.ssh import generate_ssh_key_pair, update_ssh_config


class GitProvider(BaseModel):
    """Git provider configuration."""

    name: str = Field(..., description="Name of the Git provider (github, gitlab, azure-devops)")
    organization: Optional[str] = Field(None, description="Organization name for enterprise setups")
    username: str = Field(..., description="Username for this provider")


class Profile(BaseModel):
    """Git profile configuration."""

    name: str = Field(..., description="Profile name")
    email: str = Field(..., description="Git email")
    username: str = Field(..., description="Default Git username")
    directories: List[Path] = Field(default_factory=list, description="Workspace directories")
    providers: List[Union[str, GitProvider]] = Field(
        default_factory=list, description="Git providers configuration"
    )

    @model_serializer
    def serialize_model(self) -> dict:
        """Custom serializer to handle Path objects."""
        return {
            "name": self.name,
            "email": self.email,
            "username": self.username,
            "directories": [str(d) for d in self.directories],
            "providers": [
                p.model_dump() if isinstance(p, GitProvider) else p
                for p in self.providers
            ],
        }


class ProfileManager:
    """Manages multiple Git profiles and their configurations."""

    def __init__(self, config_dir: Optional[Path] = None) -> None:
        """Initialize the profile manager.
        
        Args:
            config_dir: Optional custom configuration directory path
        """
        self.config_dir = config_dir or Path.home() / ".gitplex"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_file = self.config_dir / "profiles.json"
        self.ssh_dir = self.config_dir.parent / ".ssh"
        self.git_config = self.config_dir.parent / ".gitconfig"
        self._load_profiles()

    def _load_profiles(self) -> None:
        """Load profiles from disk."""
        self.profiles: Dict[str, Profile] = {}
        if self.profiles_file.exists():
            data = json.loads(self.profiles_file.read_text())
            for profile_data in data.values():
                # Convert directory strings back to Path objects
                if "directories" in profile_data:
                    profile_data["directories"] = [
                        Path(d) for d in profile_data["directories"]
                    ]
                profile = Profile.model_validate(profile_data)
                self.profiles[profile.name] = profile

    def _save_profiles(self) -> None:
        """Save profiles to disk."""
        data = {name: profile.model_dump() for name, profile in self.profiles.items()}
        self.profiles_file.write_text(json.dumps(data, indent=2))

    def setup_profile(
        self,
        name: str,
        email: str,
        username: str,
        directories: Optional[List[str]] = None,
        providers: Optional[List[Union[str, dict]]] = None,
    ) -> Profile:
        """Set up a new Git profile.
        
        Args:
            name: Profile name
            email: Git email
            username: Default Git username
            directories: List of workspace directories
            providers: List of Git providers (strings or dicts with config)
            
        Returns:
            The created Profile instance
        """
        # Convert string paths to Path objects
        dir_paths = [Path(d).expanduser() for d in (directories or [])]
        
        # Create profile
        profile = Profile(
            name=name,
            email=email,
            username=username,
            directories=dir_paths,
            providers=providers or [],
        )
        
        # Generate SSH keys for each provider
        self.ssh_dir.mkdir(parents=True, exist_ok=True)
        for provider in profile.providers:
            provider_name = provider.name if isinstance(provider, GitProvider) else provider
            key_name = f"{profile.name}_{provider_name}"
            key_path = self.ssh_dir / key_name
            
            # Generate key pair
            private_key, public_key = generate_ssh_key_pair(key_path)
            
            # Update SSH config
            provider_config = provider if isinstance(provider, GitProvider) else GitProvider(
                name=provider,
                username=username
            )
            
            host = f"{provider_config.name}.com"
            if provider_config.organization:
                host = f"{provider_config.organization}.{host}"
            
            update_ssh_config(
                self.ssh_dir / "config",
                host=host,
                identity_file=private_key,
                user=provider_config.username,
            )
        
        # Create Git configs for each directory
        for directory in profile.directories:
            create_directory_gitconfig(
                directory,
                name=username,
                email=email,
                username=username,
            )
        
        # Save profile
        self.profiles[profile.name] = profile
        self._save_profiles()
        
        return profile

    def list_profiles(self) -> List[Profile]:
        """List all configured profiles.
        
        Returns:
            List of configured profiles
        """
        return list(self.profiles.values())

    def switch_profile(self, name: str) -> Profile:
        """Switch to a different Git profile.
        
        Args:
            name: Name of the profile to switch to
            
        Returns:
            The activated Profile instance
            
        Raises:
            ValueError: If profile doesn't exist
        """
        if name not in self.profiles:
            raise ValueError(f"Profile '{name}' not found")
        
        profile = self.profiles[name]
        
        # Update global Git config
        self.git_config.parent.mkdir(parents=True, exist_ok=True)
        update_gitconfig(
            self.git_config,
            name=profile.username,
            email=profile.email,
            username=profile.username,
        )
        
        return profile 