"""Profile management module for GitPlex."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from rich.prompt import Confirm

from .exceptions import GitplexError
from .ssh import SSHKey, setup_ssh_keys, test_ssh_connection
from .ui import print_error, print_info, print_success, print_warning
from .workspace import (
    GITPLEX_DIR,
    GitConfig,
    get_workspace_git_config,
    setup_workspace,
    validate_workspace,
)

PROFILES_FILE = GITPLEX_DIR / "profiles.json"


@dataclass
class Profile:
    """Git profile configuration."""
    name: str
    email: str
    username: str
    provider: str
    workspace_dir: Path
    ssh_key: SSHKey
    is_active: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert profile to dictionary for serialization."""
        return {
            "name": self.name,
            "email": self.email,
            "username": self.username,
            "provider": self.provider,
            "workspace_dir": str(self.workspace_dir),
            "ssh_key": {
                "private_key": str(self.ssh_key.private_key),
                "public_key": str(self.ssh_key.public_key),
                "key_type": self.ssh_key.key_type,
                "comment": self.ssh_key.comment,
                "provider": self.ssh_key.provider,
                "profile_name": self.ssh_key.profile_name,
            },
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        """Create profile from dictionary."""
        ssh_data = data["ssh_key"]
        ssh_key = SSHKey(
            private_key=Path(ssh_data["private_key"]),
            public_key=Path(ssh_data["public_key"]),
            key_type=ssh_data["key_type"],
            comment=ssh_data["comment"],
            provider=ssh_data["provider"],
            profile_name=ssh_data["profile_name"],
        )
        
        return cls(
            name=data["name"],
            email=data["email"],
            username=data["username"],
            provider=data["provider"],
            workspace_dir=Path(data["workspace_dir"]),
            ssh_key=ssh_key,
            is_active=data.get("is_active", False),
        )


class ProfileManager:
    """Manages Git profiles."""

    def __init__(self) -> None:
        """Initialize profile manager."""
        self.profiles: dict[str, Profile] = {}
        self._load_profiles()

    def _load_profiles(self) -> None:
        """Load profiles from disk."""
        if not PROFILES_FILE.exists():
            return
        
        try:
            data = json.loads(PROFILES_FILE.read_text())
            self.profiles = {
                name: Profile.from_dict(profile_data)
                for name, profile_data in data.items()
            }
        except Exception as e:
            raise GitplexError(f"Failed to load profiles: {e}") from e

    def _save_profiles(self) -> None:
        """Save profiles to disk."""
        try:
            GITPLEX_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                name: profile.to_dict()
                for name, profile in self.profiles.items()
            }
            PROFILES_FILE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            raise GitplexError(f"Failed to save profiles: {e}") from e

    def create_profile(
        self,
        name: str,
        email: str,
        username: str,
        provider: str,
        base_dir: Optional[Path] = None,
        force: bool = False,
    ) -> Profile:
        """Create a new Git profile.
        
        Args:
            name: Profile name
            email: Git email
            username: Git username
            provider: Git provider
            base_dir: Base directory for workspaces
            force: Whether to overwrite existing profile
        
        Returns:
            Created Profile object
        """
        # Check if profile exists
        if name in self.profiles and not force:
            if not Confirm.ask(
                f"Profile {name} already exists. Overwrite?",
                default=False
            ):
                raise GitplexError("Profile creation cancelled")
        
        # Set up SSH keys
        ssh_key = setup_ssh_keys(name, provider, email)
        
        # Set up workspace
        workspace_dir = setup_workspace(
            profile_name=name,
            email=email,
            username=username,
            provider=provider,
            ssh_key=ssh_key.private_key,
            base_dir=base_dir,
        )
        
        # Create profile
        profile = Profile(
            name=name,
            email=email,
            username=username,
            provider=provider,
            workspace_dir=workspace_dir,
            ssh_key=ssh_key,
        )
        
        # Save profile
        self.profiles[name] = profile
        self._save_profiles()
        
        print_success(f"Created profile: {name}")
        return profile

    def get_profile(self, name: str) -> Profile:
        """Get a profile by name.
        
        Args:
            name: Profile name
        
        Returns:
            Profile object
        """
        if name not in self.profiles:
            raise GitplexError(f"Profile not found: {name}")
        return self.profiles[name]

    def list_profiles(self) -> list[Profile]:
        """Get all profiles.
        
        Returns:
            List of Profile objects
        """
        return list(self.profiles.values())

    def delete_profile(self, name: str, keep_files: bool = False) -> None:
        """Delete a profile.
        
        Args:
            name: Profile name
            keep_files: Whether to keep workspace and SSH files
        """
        if name not in self.profiles:
            raise GitplexError(f"Profile not found: {name}")
        
        profile = self.profiles[name]
        
        if not keep_files:
            # Remove SSH keys
            try:
                profile.ssh_key.private_key.unlink(missing_ok=True)
                profile.ssh_key.public_key.unlink(missing_ok=True)
                print_success("Removed SSH keys")
            except OSError as e:
                print_warning(f"Failed to remove SSH keys: {e}")
            
            # Remove workspace
            try:
                if Confirm.ask(
                    f"Remove workspace directory: {profile.workspace_dir}?",
                    default=False
                ):
                    import shutil
                    shutil.rmtree(profile.workspace_dir)
                    print_success("Removed workspace directory")
            except OSError as e:
                print_warning(f"Failed to remove workspace: {e}")
        
        # Remove from profiles
        del self.profiles[name]
        self._save_profiles()
        
        print_success(f"Deleted profile: {name}")

    def activate_profile(self, name: str) -> None:
        """Activate a profile.
        
        Args:
            name: Profile name
        """
        if name not in self.profiles:
            raise GitplexError(f"Profile not found: {name}")
        
        # Deactivate current profile
        for profile in self.profiles.values():
            profile.is_active = False
        
        # Activate new profile
        profile = self.profiles[name]
        profile.is_active = True
        
        # Validate workspace
        if not validate_workspace(profile.workspace_dir):
            raise GitplexError(f"Invalid workspace directory: {profile.workspace_dir}")
        
        # Test SSH connection
        if not test_ssh_connection(profile.provider):
            print_warning("SSH connection test failed")
        
        # Save changes
        self._save_profiles()
        
        print_success(f"Activated profile: {name}")

    def get_active_profile(self) -> Optional[Profile]:
        """Get the currently active profile.
        
        Returns:
            Active Profile object or None
        """
        for profile in self.profiles.values():
            if profile.is_active:
                return profile
        return None

    def validate_profile(self, name: str) -> bool:
        """Validate a profile's configuration.
        
        Args:
            name: Profile name
        
        Returns:
            True if valid, False otherwise
        """
        if name not in self.profiles:
            return False
        
        profile = self.profiles[name]
        
        # Check SSH keys
        if not profile.ssh_key.exists():
            print_error("SSH keys not found")
            return False
        
        # Check workspace
        if not validate_workspace(profile.workspace_dir):
            print_error("Invalid workspace directory")
            return False
        
        # Check Git config
        try:
            config = get_workspace_git_config(profile.workspace_dir)
            if (
                config["user.email"] != profile.email
                or config["user.name"] != profile.username
                or config["github.user"] != profile.username
            ):
                print_error("Git configuration mismatch")
                return False
        except GitplexError as e:
            print_error(f"Git configuration error: {e}")
            return False
        
        return True
