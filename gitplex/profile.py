"""Profile management module for GitPlex."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional, List

from rich.prompt import Confirm

from .exceptions import GitplexError
from .gpg import GPGKey, setup_gpg_key
from .ssh import SSHKey, setup_ssh_keys, test_ssh_connection
from .ui import print_error, print_info, print_success, print_warning, print_gpg_key_info
from .workspace import (
    GITPLEX_DIR,
    GitConfig,
    get_workspace_git_config,
    setup_workspace,
    validate_workspace,
)

PROFILES_FILE = GITPLEX_DIR / "profiles.json"

@dataclass
class GitCredentials:
    """Git credentials that can be shared between profiles."""
    email: str
    username: str
    ssh_key: Optional[SSHKey] = None
    gpg_key: Optional[GPGKey] = None

@dataclass
class Profile:
    """Git profile configuration."""
    name: str
    credentials: GitCredentials
    provider: str  # Ahora es un solo string
    workspace_dir: Path
    is_active: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert profile to dictionary for serialization."""
        return {
            "name": self.name,
            "credentials": {
                "email": self.credentials.email,
                "username": self.credentials.username,
                "ssh_key": self.credentials.ssh_key.to_dict() if self.credentials.ssh_key else None,
                "gpg_key": self.credentials.gpg_key.to_dict() if self.credentials.gpg_key else None,
            },
            "provider": self.provider,
            "workspace_dir": str(self.workspace_dir),
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        """Create profile from dictionary."""
        cred_data = data["credentials"]
        ssh_data = cred_data.get("ssh_key")
        gpg_data = cred_data.get("gpg_key")
        
        ssh_key = SSHKey.from_dict(ssh_data) if ssh_data else None
        gpg_key = GPGKey.from_dict(gpg_data) if gpg_data else None
        
        credentials = GitCredentials(
            email=cred_data["email"],
            username=cred_data["username"],
            ssh_key=ssh_key,
            gpg_key=gpg_key,
        )
        
        return cls(
            name=data["name"],
            credentials=credentials,
            provider=data["provider"],
            workspace_dir=Path(data["workspace_dir"]),
            is_active=data.get("is_active", False),
        )

class ProfileManager:
    """Manages Git profiles."""

    def __init__(self) -> None:
        """Initialize profile manager."""
        self.profiles: dict[str, Profile] = {}
        self.credentials: dict[str, GitCredentials] = {}
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
            self.credentials = {
                f"{p.credentials.email}_{p.credentials.username}": p.credentials
                for p in self.profiles.values()
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

    def find_matching_credentials(self, email: str, username: str) -> Optional[GitCredentials]:
        """Find existing credentials that match the given email and username."""
        cred_key = f"{email}_{username}"
        return self.credentials.get(cred_key)

    def create_profile(
        self,
        name: str,
        email: str,
        username: str,
        provider: str,
        base_dir: Optional[Path] = None,
        force: bool = False,
        reuse_credentials: bool = True,
        skip_gpg: bool = False,
    ) -> Profile:
        """Create a new Git profile.
        
        Args:
            name: Profile name
            email: Git email
            username: Git username
            provider: Git provider name (e.g. 'github')
            base_dir: Base directory for workspace
            force: Force overwrite existing profile
            reuse_credentials: Reuse existing credentials if they match
            skip_gpg: Skip GPG key generation
        
        Returns:
            Created profile
        """
        if name in self.profiles and not force:
            if not Confirm.ask(
                f"Profile {name} already exists. Overwrite?",
                default=False
            ):
                raise GitplexError(f"Profile {name} already exists")
        
        # Check for existing credentials
        credentials = None
        if reuse_credentials:
            credentials = self.find_matching_credentials(email, username)
            if credentials:
                print_info(f"Found existing credentials for {email} ({username})")
                if not Confirm.ask("Would you like to reuse these credentials?", default=True):
                    credentials = None
        
        if not credentials:
            # Set up SSH key for the provider (not profile-specific)
            ssh_key = None
            provider_key_name = f"id_{provider}"  # e.g. id_github
            ssh_key_path = Path(f"~/.ssh/{provider_key_name}").expanduser()
            
            if ssh_key_path.exists():
                print_info(f"\n🔑 Found existing SSH key for {provider}")
                ssh_key = SSHKey(
                    private_key=ssh_key_path,
                    public_key=Path(f"{ssh_key_path}.pub"),
                )
                # Show the existing key
                print_info("\nExisting SSH public key:")
                print_info("-" * 50)
                print_info(ssh_key.public_key.read_text().strip())
                print_info("-" * 50)
                
                # Test the connection
                if test_ssh_connection(provider):
                    print_success("✅ SSH connection test successful!")
                else:
                    print_warning("⚠️  SSH connection test failed")
                    print_info("\nPossible solutions:")
                    print_info("1. Verify the key is added to your GitHub account")
                    print_info("2. Check your SSH agent: ssh-add ~/.ssh/id_github")
                    print_info("3. Test connection manually: ssh -T git@github.com")
                    if Confirm.ask("Would you like to create a new key instead?", default=False):
                        ssh_key = None
            
            if not ssh_key:
                print_info(f"\n🔑 Creating new SSH key for {provider}...")
                ssh_key = setup_ssh_keys(provider_key_name, provider, email)
                
                # Show the new key prominently
                print_info("\n📋 Your new SSH public key (copied to clipboard):")
                print_info("-" * 50)
                key_content = ssh_key.public_key.read_text().strip()
                print_info(key_content)
                print_info("-" * 50)
                
                # Copy to clipboard
                import pyperclip
                try:
                    pyperclip.copy(key_content)
                    print_success("✅ Key copied to clipboard!")
                except Exception:
                    print_warning("Could not copy to clipboard automatically")
                
                # Show next steps clearly
                print_info("\n📝 Next steps:")
                if provider == "github":
                    print_info("1. Open GitHub SSH settings: https://github.com/settings/keys")
                    print_info("2. Click 'New SSH key'")
                    print_info("3. Paste the key (it's already in your clipboard)")
                    print_info("4. Click 'Add SSH key'")
                elif provider == "gitlab":
                    print_info("1. Open GitLab SSH settings: https://gitlab.com/-/profile/keys")
                    print_info("2. Paste the key (it's already in your clipboard)")
                    print_info("3. Click 'Add key'")
                
                # Wait for user to add the key
                print_info("\nPress Enter after adding the key to test the connection...")
                input()
                
                # Test the connection
                if test_ssh_connection(provider):
                    print_success("✅ SSH connection test successful!")
                else:
                    print_warning("⚠️  SSH connection test failed")
                    print_info("\nTroubleshooting steps:")
                    print_info("1. Verify you added the key correctly")
                    print_info("2. Try: ssh-add ~/.ssh/id_github")
                    print_info("3. Test manually: ssh -T git@github.com")
                    print_info("\nContinuing with setup, but please fix the SSH connection later")
            
            # Set up GPG key if not skipped
            gpg_key = None
            if not skip_gpg:
                try:
                    print_info("\n🔐 Setting up GPG key...")
                    gpg_key = setup_gpg_key(username, email, f"GitPlex {name}")
                    print_gpg_key_info(gpg_key)
                except FileNotFoundError:
                    print_warning("GPG is not installed, skipping GPG key generation")
            
            credentials = GitCredentials(
                email=email,
                username=username,
                ssh_key=ssh_key,
                gpg_key=gpg_key,
            )
            self.credentials[f"{email}_{username}"] = credentials
        
        # Set up workspace
        print_info("\n📁 Setting up workspace...")
        workspace_dir = setup_workspace(
            profile_name=name,
            email=email,
            username=username,
            provider=provider,
            ssh_key=credentials.ssh_key.private_key if credentials.ssh_key else None,
            gpg_key=credentials.gpg_key.key_id if credentials.gpg_key else None,
            base_dir=base_dir,
        )
        
        # Create profile
        profile = Profile(
            name=name,
            credentials=credentials,
            provider=provider,
            workspace_dir=workspace_dir,
        )
        
        # Save profile
        self.profiles[name] = profile
        self._save_profiles()
        
        print_success(f"\n✨ Profile '{name}' created successfully!")
        
        # Show final configuration summary
        print_info("\n📝 Configuration Summary:")
        print_info(f"• Profile: {name}")
        print_info(f"• Email: {email}")
        print_info(f"• Username: {username}")
        print_info(f"• Provider: {provider}")
        print_info(f"• Workspace: {workspace_dir}")
        print_info(f"• SSH Key: {credentials.ssh_key.private_key if credentials.ssh_key else 'None'}")
        print_info(f"• GPG Key: {credentials.gpg_key.key_id if credentials.gpg_key else 'None'}")
        
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
            cred_key = f"{profile.credentials.email}_{profile.credentials.username}"
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
                    self.credentials.pop(cred_key, None)
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
        if not profile.credentials.ssh_key.exists():
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
