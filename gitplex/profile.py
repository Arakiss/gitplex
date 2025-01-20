"""Git profile management."""

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from gitplex.exceptions import ProfileError
from gitplex.ssh import SSHConfig
from gitplex.system import get_home_dir


class GitProvider(Enum):
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
    directories: list[str]  # Store as strings for serialization
    providers: list[str]
    ssh_key: str | None = None
    active: bool = False

    def __post_init__(self) -> None:
        """Convert string paths to Path objects."""
        # Store all paths as strings
        self.directories = [str(d) for d in self.directories]

    def to_dict(self) -> dict[str, Any]:
        """Convert profile to dictionary for serialization."""
        return {
            "name": self.name,
            "email": self.email,
            "username": self.username,
            "directories": self.directories,
            "providers": self.providers,
            "ssh_key": self.ssh_key,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        """Create profile from dictionary."""
        return cls(
            name=data["name"],
            email=data["email"],
            username=data["username"],
            directories=data["directories"],
            providers=data["providers"],
            ssh_key=data.get("ssh_key"),
            active=data.get("active", False),
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
            self.profiles = {
                name: Profile.from_dict(profile_data)
                for name, profile_data in data.items()
            }
        except Exception as e:
            raise ProfileError(f"Failed to load profiles: {e}") from e

    def _save_profiles(self) -> None:
        """Save profiles to file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        try:
            data = {name: profile.to_dict() for name, profile in self.profiles.items()}
            self.profiles_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            raise ProfileError(f"Failed to save profiles: {e}") from e

    def profile_exists(self, name: str) -> bool:
        """Check if profile exists."""
        return name in self.profiles

    def has_provider_conflict(
        self, providers: list[str], email: str
    ) -> tuple[bool, str | None]:
        """Check if there's a conflict with existing profiles.

        Returns:
            Tuple of (has_conflict: bool, conflicting_profile: str | None)
        """
        for name, profile in self.profiles.items():
            if (
                profile.email != email
                and any(p in profile.providers for p in providers)
            ):
                return True, name
        return False, None

    def remove_profile(self, name: str) -> None:
        """Remove a profile."""
        if name not in self.profiles:
            raise ProfileError(f"Profile '{name}' does not exist")

        del self.profiles[name]
        self._save_profiles()

    def get_profile_dir(self, name: str) -> Path:
        """Get the directory for a profile."""
        return self.config_dir / name

    def _save_profile(self, profile: Profile) -> None:
        """Save a profile."""
        self.profiles[profile.name] = profile
        self._save_profiles()

    def create_profile(
        self,
        name: str,
        email: str,
        username: str,
        directories: list[Path],
        providers: list[str],
        ssh_key: str | None = None,
    ) -> Profile:
        """Create a new Git profile."""
        if name in self.profiles:
            raise ProfileError(f"Profile '{name}' already exists")

        profile = Profile(
            name=name,
            email=email,
            username=username,
            directories=[str(d) for d in directories],
            providers=providers,
            ssh_key=ssh_key,
        )

        # Configure SSH for each provider if key is provided
        if ssh_key:
            key_path = Path(ssh_key)
            self.ssh_config.add_key(name, key_path, providers)

        self._save_profile(profile)
        return profile

    def switch_profile(self, name: str) -> Profile:
        """Switch to a different Git profile."""
        if name not in self.profiles:
            raise ProfileError(f"Profile '{name}' does not exist")

        # Deactivate current profile
        for profile in self.profiles.values():
            profile.active = False

        # Activate new profile
        profile = self.profiles[name]
        profile.active = True
        self._save_profiles()
        return profile

    def list_profiles(self) -> list[Profile]:
        """List all profiles."""
        return list(self.profiles.values())

    def get_active_profile(self) -> Profile | None:
        """Get active profile."""
        for profile in self.profiles.values():
            if profile.active:
                return profile
        return None
