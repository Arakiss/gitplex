"""SSH key management utilities."""

import subprocess
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from .exceptions import SystemConfigError
from .ui import print_info, print_warning, confirm_action


class KeyType(str, Enum):
    """Supported SSH key types."""
    ED25519 = "ed25519"  # Most secure, recommended by GitHub
    RSA = "rsa"  # Legacy support


class SSHKey(BaseModel):
    """SSH key pair information."""
    private_key: Path
    public_key: Path
    type: KeyType
    bits: Optional[int] = Field(None, description="Only for RSA keys")
    comment: Optional[str] = None

    @property
    def public_key_content(self) -> str:
        """Get the public key content."""
        return self.public_key.read_text().strip()

    class Config:
        arbitrary_types_allowed = True


class SSHConfig:
    """Manages SSH configuration for Git providers."""

    def __init__(self, ssh_dir: Optional[Path] = None):
        """Initialize SSH configuration manager."""
        self.ssh_dir = ssh_dir or Path.home() / ".ssh"
        self.ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.config_file = self.ssh_dir / "config"
        self._ensure_config_file()
        self.key_manager = SSHKeyManager(self.ssh_dir)

    def _ensure_config_file(self) -> None:
        """Ensure SSH config file exists with correct permissions."""
        if not self.config_file.exists():
            self.config_file.touch(mode=0o600)

    def setup(self, name: str, username: str, providers: list[str]) -> SSHKey:
        """Set up SSH configuration for a new profile.
        
        Args:
            name: Profile name
            username: Git username
            providers: List of Git providers
            
        Returns:
            SSHKey: The generated SSH key
        """
        print_info("Generating SSH key pair...")
        key = self.key_manager.generate_key(
            name=name,
            email=f"{username}@{providers[0]}.com",  # Use first provider for key comment
        )

        # Configure SSH for each provider
        for provider in providers:
            print_info(f"Configuring SSH for {provider}...")
            self._update_config(key, f"{provider}.com")
            # Show provider-specific instructions
            print_info(self.key_manager.get_provider_instructions(key, provider))

        return key

    def update(self, name: str, username: str, providers: list[str]) -> SSHKey:
        """Update SSH configuration for an existing profile.
        
        Args:
            name: Profile name
            username: Git username
            providers: List of Git providers
            
        Returns:
            SSHKey: The existing SSH key
        """
        key_path = self.ssh_dir / f"id_{name}_ed25519"
        if not key_path.exists():
            raise SystemConfigError(f"SSH key not found: {key_path}")

        key = SSHKey(
            private_key=key_path,
            public_key=key_path.with_suffix(".pub"),
            type=KeyType.ED25519,
            comment=f"{username}@{providers[0]}.com",
        )

        # Validate the key
        if not self.key_manager.validate_key(key):
            raise SystemConfigError("Invalid SSH key found")

        # Update SSH config for each provider
        for provider in providers:
            print_info(f"Updating SSH config for {provider}...")
            self._update_config(key, f"{provider}.com")
            # Show provider-specific instructions
            print_info(self.key_manager.get_provider_instructions(key, provider))

        return key

    def _update_config(self, key: SSHKey, host: str) -> None:
        """Update SSH config to use the specified key for a host."""
        config = self.config_file.read_text() if self.config_file.exists() else ""

        # Check if host already exists
        host_exists = any(
            line.strip().startswith(f"Host {host}")
            for line in config.splitlines()
        )

        if not host_exists:
            # Add new host configuration
            new_config = f"""
# Added by GitPlex
Host {host}
    IdentityFile {key.private_key}
    UseKeychain yes
    AddKeysToAgent yes
    PreferredAuthentications publickey
    UpdateHostKeys yes
"""
            with self.config_file.open("a") as f:
                f.write(new_config)

        # Set correct permissions
        self.config_file.chmod(0o600)


class SSHKeyManager:
    """Manages SSH key operations."""

    def __init__(self, ssh_dir: Optional[Path] = None):
        """Initialize SSH key manager."""
        self.ssh_dir = ssh_dir or Path.home() / ".ssh"
        self.ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    def validate_key(self, key: SSHKey) -> bool:
        """Validate that an SSH key is properly formatted and has correct permissions."""
        try:
            # Check that files exist
            if not key.private_key.exists() or not key.public_key.exists():
                return False

            # Check permissions
            if key.private_key.stat().st_mode & 0o777 != 0o600:
                print_warning("Private key has incorrect permissions. Fixing...")
                key.private_key.chmod(0o600)

            if key.public_key.stat().st_mode & 0o777 != 0o644:
                print_warning("Public key has incorrect permissions. Fixing...")
                key.public_key.chmod(0o644)

            # Validate public key format
            pub_content = key.public_key_content
            parts = pub_content.split()
            if len(parts) < 2:
                return False

            key_type = parts[0].split("-")[1]  # ssh-ed25519 -> ed25519
            if key_type != key.type.value:
                return False

            # Test key with ssh-keygen
            result = subprocess.run(
                ["ssh-keygen", "-l", "-f", str(key.public_key)],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0

        except Exception:
            return False

    def get_existing_key(self, name: str, key_type: KeyType = KeyType.ED25519) -> Optional[SSHKey]:
        """Get existing SSH key if it exists."""
        key_path = self.ssh_dir / f"id_{name}_{key_type.value}"
        pub_path = key_path.with_suffix(".pub")
        
        if key_path.exists() and pub_path.exists():
            # Try to get the comment from the public key
            try:
                pub_content = pub_path.read_text().strip()
                comment = pub_content.split()[-1] if len(pub_content.split()) > 2 else None
            except Exception:
                comment = None
            
            key = SSHKey(
                private_key=key_path,
                public_key=pub_path,
                type=key_type,
                comment=comment,
            )
            
            # Validate the key
            if self.validate_key(key):
                return key
            
            print_warning("Found invalid SSH key.")
            return None
            
        return None

    def remove_key(self, name: str, key_type: KeyType = KeyType.ED25519) -> None:
        """Remove an existing SSH key pair."""
        key_path = self.ssh_dir / f"id_{name}_{key_type.value}"
        pub_path = key_path.with_suffix(".pub")
        
        try:
            if key_path.exists():
                key_path.unlink()
            if pub_path.exists():
                pub_path.unlink()
        except Exception as e:
            raise SystemConfigError(f"Failed to remove SSH key: {e}")

    def generate_key(
        self,
        name: str,
        email: str,
        key_type: KeyType = KeyType.ED25519,
        bits: int = 4096,
        passphrase: str = "",
        force: bool = False,
    ) -> SSHKey:
        """Generate a new SSH key pair.
        
        Args:
            name: Profile name
            email: Git email
            key_type: Type of key to generate
            bits: Number of bits for RSA keys
            passphrase: Optional passphrase for the key
            force: Whether to overwrite existing keys
        """
        key_path = self.ssh_dir / f"id_{name}_{key_type.value}"
        
        # Check for existing key
        if not force and (key_path.exists() or key_path.with_suffix(".pub").exists()):
            existing_key = self.get_existing_key(name, key_type)
            if existing_key:
                print_info("Found existing SSH key.")
                # Show key details
                result = subprocess.run(
                    ["ssh-keygen", "-l", "-f", str(existing_key.public_key)],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    print_info(f"Key fingerprint: {result.stdout.strip()}")
                
                if confirm_action("Would you like to use the existing key?", default=True):
                    return existing_key
                elif confirm_action("Would you like to generate a new key?", default=False):
                    self.remove_key(name, key_type)
                else:
                    raise SystemConfigError("SSH key setup cancelled by user")
            else:
                # Key files exist but are invalid/incomplete
                print_warning("Found invalid/incomplete SSH key files.")
                if confirm_action("Would you like to remove them and generate a new key?", default=True):
                    self.remove_key(name, key_type)
                else:
                    raise SystemConfigError("SSH key setup cancelled by user")

        # Build command based on key type
        cmd = ["ssh-keygen", "-t", key_type.value, "-C", email, "-f", str(key_path)]
        
        if key_type == KeyType.RSA:
            if bits < 2048:
                print_warning("RSA keys should be at least 2048 bits. Using 2048 bits.")
                bits = 2048
            cmd.extend(["-b", str(bits)])
        
        if passphrase:
            cmd.extend(["-N", passphrase])
        else:
            cmd.extend(["-N", ""])

        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            msg = f"Failed to generate SSH key: {e.stderr.decode()}"
            raise SystemConfigError(msg) from e

        # Set correct permissions
        key_path.chmod(0o600)
        key_path.with_suffix(".pub").chmod(0o644)

        return SSHKey(
            private_key=key_path,
            public_key=key_path.with_suffix(".pub"),
            type=key_type,
            bits=bits if key_type == KeyType.RSA else None,
            comment=email,
        )

    def get_provider_instructions(self, key: SSHKey, provider: str) -> str:
        """Get provider-specific instructions for adding the SSH key."""
        # Get key fingerprint for display
        result = subprocess.run(
            ["ssh-keygen", "-l", "-f", str(key.public_key)],
            capture_output=True,
            text=True,
        )
        fingerprint = result.stdout.strip() if result.returncode == 0 else "Unable to get fingerprint"

        # Format the public key for display
        public_key = key.public_key_content

        instructions = {
            "github": f"""
╭──────────────────── GitHub SSH Key Setup ────────────────────╮
│ 1. Go to: https://github.com/settings/ssh/new                │
│ 2. Title: GitPlex Key ({key.type.value})                     │
│ 3. Key Type: Authentication Key                              │
│                                                             │
│ Your SSH Public Key:                                        │
╰─────────────────────────────────────────────────────────────╯
{public_key}

╭─────────────────────── Key Details ───────────────────────╮
│ Fingerprint: {fingerprint}                                │
│ Type: {key.type.value.upper()}                           │
│ Location: {key.private_key}                              │
╰───────────────────────────────────────────────────────────╯
""",
            "gitlab": f"""
╭──────────────────── GitLab SSH Key Setup ────────────────────╮
│ 1. Go to: https://gitlab.com/-/profile/keys                  │
│ 2. Title: GitPlex Key ({key.type.value})                     │
│ 3. Key Type: Authentication Key                              │
│                                                             │
│ Your SSH Public Key:                                        │
╰─────────────────────────────────────────────────────────────╯
{public_key}

╭─────────────────────── Key Details ───────────────────────╮
│ Fingerprint: {fingerprint}                                │
│ Type: {key.type.value.upper()}                           │
│ Location: {key.private_key}                              │
╰───────────────────────────────────────────────────────────╯
""",
            "bitbucket": f"""
╭────────────────── Bitbucket SSH Key Setup ──────────────────╮
│ 1. Go to: https://bitbucket.org/account/settings/ssh-keys/  │
│ 2. Click 'Add key'                                          │
│ 3. Title: GitPlex Key ({key.type.value})                    │
│                                                             │
│ Your SSH Public Key:                                        │
╰─────────────────────────────────────────────────────────────╯
{public_key}

╭─────────────────────── Key Details ───────────────────────╮
│ Fingerprint: {fingerprint}                                │
│ Type: {key.type.value.upper()}                           │
│ Location: {key.private_key}                              │
╰───────────────────────────────────────────────────────────╯
""",
        }
        return instructions.get(provider.lower(), "Provider not supported")
