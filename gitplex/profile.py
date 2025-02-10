"""Profile management module for GitPlex."""

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, List

from rich.prompt import Confirm

from .exceptions import GitplexError, ProfileError
from .gpg import GPGKey, setup_gpg_key
from .ssh import SSHKey, setup_ssh_keys, test_ssh_connection
from .ui import print_error, print_info, print_success, print_warning, print_gpg_key_info, print_ssh_key_info
from .workspace import (
    GITPLEX_DIR,
    GitConfig,
    get_workspace_git_config,
    setup_workspace,
    validate_workspace,
)
from .credentials import Credentials, CredentialsManager

PROFILES_FILE = GITPLEX_DIR / "profiles.json"

@dataclass
class Profile:
    """Git profile configuration."""
    name: str
    credentials: Credentials
    provider: str
    workspace_dir: Path
    is_active: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert profile to dictionary for serialization."""
        return {
            "name": self.name,
            "credentials": self.credentials.to_dict(),
            "provider": self.provider,
            "workspace_dir": str(self.workspace_dir),
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        """Create profile from dictionary."""
        return cls(
            name=data["name"],
            credentials=Credentials.from_dict(data["credentials"]),
            provider=data["provider"],
            workspace_dir=Path(data["workspace_dir"]),
            is_active=data.get("is_active", False),
        )

class ProfileManager:
    """Manages Git profiles."""

    def __init__(self) -> None:
        """Initialize profile manager."""
        self.profiles: dict[str, Profile] = {}
        self.credentials_manager = CredentialsManager()
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
            # Extract unique credentials
            for profile in self.profiles.values():
                self.credentials_manager.add_credentials(profile.credentials)
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

    def find_matching_credentials(self, email: str, username: str) -> Optional[Credentials]:
        """Find existing credentials that match the given email and username."""
        return self.credentials_manager.find_matching_credentials(email, username)

    def create_profile(
        self,
        name: str,
        email: str,
        username: str,
        provider: str,
        base_dir: Path,
        force: bool = False,
        reuse_credentials: bool = True,
        skip_gpg: bool = False,
    ) -> Profile:
        """Create a new Git profile."""
        # Validate name
        if not name:
            raise ProfileError("Profile name cannot be empty")
        
        # Check if profile exists
        if name in self.profiles and not force:
            existing_profile = self.profiles[name]
            raise ProfileError(
                f"Profile '{name}' already exists",
                profile_name=name,
                current_config={
                    "Email": existing_profile.credentials.email,
                    "Username": existing_profile.credentials.username,
                    "Workspace": str(existing_profile.workspace_dir),
                    "Provider": existing_profile.provider
                }
            )
        
        # Create workspace directory
        workspace_dir = base_dir / name
        workspace_dir.mkdir(parents=True, exist_ok=True)
        print_success(f"Created workspace directory: {workspace_dir}")
        
        # Create or reuse credentials
        credentials = None
        if reuse_credentials:
            existing_creds = self.find_matching_credentials(email, username)
            if existing_creds:
                credentials = Credentials(
                    email=existing_creds.email,
                    username=existing_creds.username,
                    gpg_key=existing_creds.gpg_key,  # Reuse GPG key if exists
                    ssh_key=None  # Don't reuse SSH key - each profile needs its own
                )
        
        if not credentials:
            credentials = Credentials(email=email, username=username)
        
        # Create new profile
        profile = Profile(
            name=name,
            credentials=credentials,
            provider=provider,
            workspace_dir=workspace_dir,
        )
        
        # Set up SSH keys
        ssh_key = setup_ssh_keys(
            profile_name=name,
            provider=provider,
            email=email,
            force=force
        )
        credentials.ssh_key = ssh_key
        
        # Set up GPG key if needed
        if not skip_gpg and not credentials.gpg_key:
            try:
                gpg_key = setup_gpg_key(email=email, name=username)
                credentials.gpg_key = gpg_key
                print_gpg_key_info(gpg_key)
            except GitplexError as e:
                if "GPG is not installed" in str(e):
                    print_warning("GPG is not installed, skipping GPG key generation")
                    print_info("You can install GPG later and run 'gitplex setup' again to enable commit signing")
                else:
                    raise
        
        # Add credentials and profile
        self.credentials_manager.add_credentials(credentials)
        self.profiles[name] = profile
        
        # Save changes
        self._save_profiles()
        
        return profile

    def get_profile(self, name: str) -> Profile:
        """Get a profile by name."""
        if name not in self.profiles:
            raise GitplexError(f"Profile not found: {name}")
        return self.profiles[name]

    def list_profiles(self) -> list[Profile]:
        """Get all profiles."""
        return list(self.profiles.values())

    def delete_profile(
        self,
        name: str,
        keep_files: bool = False,
        keep_credentials: bool = True
    ) -> None:
        """Delete a profile.
        
        Args:
            name: Profile name
            keep_files: Whether to keep workspace and SSH files
            keep_credentials: Whether to keep shared credentials
        """
        if name not in self.profiles:
            raise GitplexError(f"Profile not found: {name}")
        
        profile = self.profiles[name]
        
        if not keep_files and profile.credentials.ssh_key:
            # Only remove SSH keys if they're not used by other profiles
            if not keep_credentials and not any(
                p.credentials.email == profile.credentials.email
                and p.credentials.username == profile.credentials.username
                and p.name != name
                for p in self.profiles.values()
            ):
                try:
                    profile.credentials.ssh_key.private_key.unlink(missing_ok=True)
                    profile.credentials.ssh_key.public_key.unlink(missing_ok=True)
                    print_success("Removed SSH keys")
                    # Remove credentials
                    self.credentials_manager.remove_credentials(
                        profile.credentials.email,
                        profile.credentials.username
                    )
                except OSError as e:
                    print_warning(f"Failed to remove SSH keys: {e}")
            else:
                print_info("SSH keys are shared with other profiles, keeping them")
            
            # Remove workspace
            try:
                if Confirm.ask(
                    f"Remove workspace directory: {profile.workspace_dir}?",
                    default=False
                ):
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
        if profile.credentials.ssh_key and not profile.credentials.ssh_key.exists():
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
                config["user.email"] != profile.credentials.email
                or config["user.name"] != profile.credentials.username
                or config["github.user"] != profile.credentials.username
            ):
                print_error("Git configuration mismatch")
                return False
        except GitplexError as e:
            print_error(f"Git configuration error: {e}")
            return False
        
        return True
