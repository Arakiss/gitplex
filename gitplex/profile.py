"""Git profile management."""

import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import List

from gitplex.exceptions import ProfileError, SystemConfigError
from gitplex.git import GitConfig
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
    providers: List[GitProvider]
    active: bool = False

    def __post_init__(self):
        """Convert string paths to Path objects and string providers to GitProvider."""
        if isinstance(self.directories[0], str):
            self.directories = [Path(d) for d in self.directories]
        if isinstance(self.providers[0], str):
            self.providers = [GitProvider(p) for p in self.providers]

    def to_dict(self) -> dict:
        """Convert profile to dictionary for serialization."""
        return {
            "name": self.name,
            "email": self.email,
            "username": self.username,
            "directories": [str(d) for d in self.directories],
            "providers": [p.value for p in self.providers],
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
        self.git_config = GitConfig()
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
                    providers=[GitProvider(p) for p in profile_data["providers"]],
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
                    "providers": [p.value for p in profile.providers],
                    "active": profile.active,
                }
                for name, profile in self.profiles.items()
            }
            self.profiles_file.write_text(json.dumps(data, indent=2))
        except OSError as e:
            raise ProfileError(f"Failed to save profiles: {e}")

    def setup_profile(
        self,
        name: str,
        email: str,
        username: str,
        directories: list[str],
        providers: list[str],
        ssh_key: str | None = None,
    ) -> Profile:
        """Set up a new Git profile.

        Args:
            name: Profile name
            email: Git email
            username: Git username
            directories: List of workspace directories
            providers: List of Git providers
            ssh_key: Optional path to SSH key

        Returns:
            Created profile
        """
        try:
            # Create profile
            if name in self.profiles:
                raise ProfileError(f"Profile '{name}' already exists")

            # Convert and validate directories
            try:
                profile_dirs = []
                for d in directories:
                    path = Path(d).expanduser().resolve()
                    profile_dirs.append(path)
            except Exception as e:
                raise ProfileError(f"Invalid directory path: {e}")

            profile = Profile(
                name=name,
                email=email,
                username=username,
                directories=profile_dirs,
                providers=[GitProvider(p) for p in providers],
            )

            # Create workspace directories
            for directory in profile.directories:
                try:
                    directory.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    raise ProfileError(f"Failed to create directory {directory}: {e}")

            # Configure Git and SSH
            try:
                self.git_config.setup(name, email, username)
                self.ssh_config.setup(name, username, providers)
            except Exception as e:
                raise ProfileError(f"Failed to configure Git/SSH: {e}")

            # Save profile
            self.profiles[name] = profile
            self._save_profiles()

            return profile

        except Exception as e:
            # Ensure the error message is properly formatted
            error_msg = str(e).replace("[", "\\[").replace("]", "\\]")
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
            try:
                self.git_config.update(name, profile.email, profile.username)
                self.ssh_config.update(name, profile.username, [p.value for p in profile.providers])
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
            # Ensure the error message is properly formatted
            error_msg = str(e).replace("[", "\\[").replace("]", "\\]")
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
