"""Git profile management."""

import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional

from gitplex.exceptions import ProfileError, SystemConfigError
from gitplex.ssh import SSHConfig
from gitplex.system import get_home_dir


class GitProvider(str, Enum):
    """Supported Git providers."""
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    AZURE = "azure"


@dataclass
class Profile:
    """Git profile configuration."""
    name: str
    email: str
    username: str
    directories: List[Path]
    providers: List[str]
    ssh_key: Optional[str] = None
    active: bool = False

    def __post_init__(self):
        """Convert string paths to Path objects."""
        if isinstance(self.directories[0], str):
            self.directories = [Path(d) for d in self.directories]

    def to_dict(self) -> dict:
        """Convert profile to dictionary for serialization."""
        return {
            "name": self.name,
            "email": self.email,
            "username": self.username,
            "directories": [str(d) for d in self.directories],
            "providers": self.providers,
            "ssh_key": self.ssh_key,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        """Create profile from dictionary."""
        return cls(
            name=data["name"],
            email=data["email"],
            username=data["username"],
            directories=data["directories"],
            providers=data["providers"],
            ssh_key=data.get("ssh_key"),
            active=data["active"],
        )


class ProfileManager:
    """Manages Git profiles."""

    def __init__(self, config_dir: Path | None = None) -> None:
        """Initialize the profile manager.
        
        Args:
            config_dir: Optional path to the config directory.
                       Defaults to ~/.config/gitplex.
        """
        if config_dir is None:
            home_dir = get_home_dir()
            config_dir = home_dir / ".config" / "gitplex"
        
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.ssh_config = SSHConfig()
        self.profiles: dict[str, Profile] = {}
        self._load_profiles()

    def _load_profiles(self) -> None:
        """Load profiles from disk."""
        if not self.profiles_file.exists():
            return

        try:
            data = json.loads(self.profiles_file.read_text())
            for name, profile_data in data.items():
                self.profiles[name] = Profile(
                    name=profile_data["name"],
                    email=profile_data["email"],
                    username=profile_data["username"],
                    directories=[Path(d) for d in profile_data["directories"]],
                    providers=profile_data["providers"],
                    ssh_key=profile_data.get("ssh_key"),
                    active=profile_data.get("active", False),
                )
        except (json.JSONDecodeError, KeyError) as e:
            raise ProfileError(f"Failed to load profiles: {e}")

    def _save_profiles(self) -> None:
        """Save profiles to file."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            data = {
                name: {
                    "name": profile.name,
                    "email": profile.email,
                    "username": profile.username,
                    "directories": [str(d) for d in profile.directories],
                    "providers": profile.providers,
                    "ssh_key": profile.ssh_key,
                    "active": profile.active,
                }
                for name, profile in self.profiles.items()
            }
            self.profiles_file.write_text(json.dumps(data, indent=2))
        except OSError as e:
            raise ProfileError(f"Failed to save profiles: {e}")

    def profile_exists(self, name: str) -> bool:
        """Check if profile exists."""
        return name in self.profiles

    def has_provider_conflict(self, providers: List[str], email: str) -> tuple[bool, Optional[str]]:
        """Check if there's a conflict with existing profiles for the given providers and email.
        
        Returns:
            Tuple of (has_conflict: bool, conflicting_profile: Optional[str])
        """
        for profile_name, profile in self.profiles.items():
            # Check if any of the requested providers overlap with existing profile
            if any(provider in profile.providers for provider in providers):
                # If providers overlap, check if email is different
                if profile.email != email:
                    return True, profile_name
        return False, None

    def remove_profile(self, name: str) -> None:
        """Remove a profile."""
        if name in self.profiles:
            del self.profiles[name]
            self._save_profiles()

    def get_profile_dir(self, name: str) -> Path:
        """Get the directory for a profile."""
        return self.config_dir / name

    def _save_profile(self, profile: Profile) -> None:
        """Save a profile."""
        self.profiles[profile.name] = profile
        self._save_profiles()

    def setup_profile(
        self,
        name: str,
        email: str,
        username: str,
        directories: List[Path],
        providers: List[str],
        ssh_key: Optional[str] = None,
        force: bool = False,
    ) -> Profile:
        """Set up a new Git profile.
        
        Args:
            name: Profile name
            email: Git email
            username: Git username
            directories: List of workspace directories
            providers: List of Git providers
            ssh_key: Optional SSH key path
            force: If True, overwrite existing profile
        
        Returns:
            Created Profile instance
        
        Raises:
            ProfileError: If profile creation fails
        """
        try:
            # Check for provider conflicts first
            has_conflict, conflicting_profile = self.has_provider_conflict(providers, email)
            if has_conflict and not force:
                raise ProfileError(
                    f"Profile '{conflicting_profile}' already exists with different email "
                    f"for one or more providers: {', '.join(providers)}. "
                    "Use --force to overwrite or choose different providers."
                )
            
            # Check if profile exists
            if self.profile_exists(name):
                if not force:
                    raise ProfileError(f"Profile '{name}' already exists. Use --force to overwrite.")
                else:
                    # Remove existing profile
                    self.remove_profile(name)
            
            # Create profile directory
            profile_dir = self.get_profile_dir(name)
            profile_dir.mkdir(parents=True, exist_ok=True)

            # Validate and convert providers
            validated_providers = []
            for provider in providers:
                try:
                    validated_providers.append(provider)
                except ValueError as e:
                    raise ProfileError(f"Invalid Git provider: {provider}") from e

            # Create profile
            profile = Profile(
                name=name,
                email=email,
                username=username,
                directories=[d.expanduser().resolve() for d in directories],
                providers=validated_providers,
                ssh_key=ssh_key,
                active=False,
            )

            # Create workspace directories
            for directory in profile.directories:
                try:
                    directory.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    raise ProfileError(f"Failed to create directory: {e}")

            # Configure SSH
            if ssh_key:
                try:
                    ssh_config = SSHConfig()
                    ssh_config.add_key(Path(ssh_key), profile.name)
                except Exception as e:
                    raise ProfileError(f"Failed to configure SSH: {e}")

            # Configure Git for each workspace
            from gitplex.git import GitConfig
            git_config = GitConfig(profile.name)
            for directory in profile.directories:
                try:
                    git_config.setup_config(
                        email=profile.email,
                        username=profile.username,
                        ssh_key_path=Path(ssh_key) if ssh_key else None,
                        providers=profile.providers,
                        directory=directory
                    )
                except Exception as e:
                    raise ProfileError(f"Failed to configure Git: {e}")

            # Save profile
            self._save_profile(profile)
            return profile

        except Exception as e:
            error_msg = str(e)
            raise ProfileError(f"Failed to setup profile: {error_msg}")

    def switch_profile(self, name: str) -> Profile:
        """Switch to a different Git profile.
        
        Args:
            name: Profile name
        
        Returns:
            Activated profile
        """
        try:
            if name not in self.profiles:
                raise ProfileError(f"Profile '{name}' not found")

            profile = self.profiles[name]

            # Update configurations
            from gitplex.git import GitConfig
            git_config = GitConfig(profile.name)
            try:
                git_config.update(name, profile.email, profile.username)
                self.ssh_config.update(name, profile.username, profile.providers)
            except Exception as e:
                raise ProfileError(f"Failed to update Git/SSH configuration: {e}")

            # Update active profile
            for p in self.profiles.values():
                p.active = False
            profile.active = True

            try:
                self._save_profiles()
            except Exception as e:
                raise ProfileError(f"Failed to save profile changes: {e}")

            return profile

        except Exception as e:
            error_msg = str(e)
            raise ProfileError(f"Failed to switch profile: {error_msg}")

    def list_profiles(self) -> list[Profile]:
        """List all profiles.
        
        Returns:
            List of profiles
        """
        return list(self.profiles.values())

    def get_active_profile(self) -> Profile | None:
        """Get active profile."""
        for profile in self.profiles.values():
            if profile.active:
                return profile
        return None
