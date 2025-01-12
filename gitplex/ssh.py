"""SSH key management functionality."""

import os
from pathlib import Path
import subprocess
import configparser

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa


class SystemConfigError(Exception):
    pass


def generate_ssh_key_pair(
    name: str,
    provider: str,
    ssh_dir: Path,
) -> None:
    """Generate SSH key pair for a Git provider.

    Args:
        name: Profile name
        provider: Git provider name
        ssh_dir: SSH directory path
    """
    try:
        # Create SSH directory if it doesn't exist
        ssh_dir.mkdir(parents=True, exist_ok=True)
        ssh_dir.chmod(0o700)

        # Generate key pair
        key_path = ssh_dir / f"{name}_{provider}"
        if key_path.exists():
            key_path.unlink()
        if key_path.with_suffix(".pub").exists():
            key_path.with_suffix(".pub").unlink()

        subprocess.run(
            [
                "ssh-keygen",
                "-t", "ed25519",
                "-f", str(key_path),
                "-N", "",
                "-C", f"{name}@{provider}",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        # Set permissions
        key_path.chmod(0o600)
        key_path.with_suffix(".pub").chmod(0o644)

        # Update SSH config
        config_path = ssh_dir / "config"
        if not config_path.exists():
            config_path.touch()
            config_path.chmod(0o600)

        # Add key to SSH config
        with config_path.open("a") as f:
            f.write(f"\nHost {provider}\n")
            f.write(f"  IdentityFile {key_path}\n")

    except subprocess.CalledProcessError as e:
        raise SystemConfigError(
            f"Failed to generate SSH key: {e.stderr}",
            details=f"Command: {' '.join(e.cmd)}\nOutput: {e.stdout}\nError: {e.stderr}",
        )
    except OSError as e:
        raise SystemConfigError(
            f"Failed to create SSH key file: {e}",
            details=f"Path: {key_path}",
        )


def update_ssh_config(
    ssh_dir: Path,
    name: str,
    providers: list[str],
    user: str,
) -> None:
    """Update SSH configuration file.

    Args:
        ssh_dir: SSH directory path
        name: Profile name
        providers: List of Git providers
        user: Git username
    """
    try:
        # Create SSH directory if it doesn't exist
        ssh_dir.mkdir(parents=True, exist_ok=True)
        ssh_dir.chmod(0o700)

        # Create or update SSH config
        config_path = ssh_dir / "config"
        if not config_path.exists():
            config_path.touch()
            config_path.chmod(0o600)

        # Read existing config
        config_content = config_path.read_text() if config_path.exists() else ""

        # Add new config
        for provider in providers:
            key_path = ssh_dir / f"{name}_{provider}"
            if not key_path.exists():
                continue

            config_content += f"\nHost {provider}\n"
            config_content += f"  User {user}\n"
            config_content += f"  IdentityFile {key_path}\n"

        # Write config
        config_path.write_text(config_content)

    except OSError as e:
        raise SystemConfigError(
            f"Failed to update SSH config: {e}",
            details=f"Path: {config_path}",
        )


"""SSH configuration management."""

import subprocess
from pathlib import Path
from typing import List

from .exceptions import SystemConfigError
from .system import get_home_dir


class SSHConfig:
    """SSH configuration manager."""

    def __init__(self) -> None:
        """Initialize SSH configuration manager."""
        self.home_dir = get_home_dir()
        self.ssh_dir = self.home_dir / ".ssh"

    def setup(self, name: str, username: str, providers: List[str]) -> None:
        """Set up SSH configuration.

        Args:
            name: Profile name
            username: Git username
            providers: List of Git providers
        """
        try:
            # Create SSH directory
            self.ssh_dir.mkdir(parents=True, exist_ok=True)
            self.ssh_dir.chmod(0o700)

            # Generate keys and update config
            for provider in providers:
                self._generate_key_pair(name, provider)
            self._update_config(name, username, providers)

        except (OSError, subprocess.CalledProcessError) as e:
            raise SystemConfigError(f"Failed to setup SSH config: {e}")

    def update(self, name: str, username: str, providers: List[str]) -> None:
        """Update SSH configuration.

        Args:
            name: Profile name
            username: Git username
            providers: List of Git providers
        """
        try:
            self._update_config(name, username, providers)
        except OSError as e:
            raise SystemConfigError(f"Failed to update SSH config: {e}")

    def _generate_key_pair(self, name: str, provider: str) -> None:
        """Generate SSH key pair.

        Args:
            name: Profile name
            provider: Git provider
        """
        key_path = self.ssh_dir / f"{name}_{provider}"

        # Remove existing keys
        if key_path.exists():
            key_path.unlink()
        if key_path.with_suffix(".pub").exists():
            key_path.with_suffix(".pub").unlink()

        # Generate new key pair
        subprocess.run(
            [
                "ssh-keygen",
                "-t", "ed25519",
                "-f", str(key_path),
                "-N", "",
                "-C", f"{name}@{provider}",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        # Set permissions
        key_path.chmod(0o600)
        key_path.with_suffix(".pub").chmod(0o644)

    def _update_config(self, name: str, username: str, providers: List[str]) -> None:
        """Update SSH configuration file.

        Args:
            name: Profile name
            username: Git username
            providers: List of Git providers
        """
        config_path = self.ssh_dir / "config"

        # Create config file if it doesn't exist
        if not config_path.exists():
            config_path.touch()
            config_path.chmod(0o600)

        # Read existing config
        config_content = config_path.read_text() if config_path.exists() else ""

        # Add new config
        for provider in providers:
            key_path = self.ssh_dir / f"{name}_{provider}"
            if not key_path.exists():
                continue

            config_content += f"\nHost {provider}\n"
            config_content += f"  User {username}\n"
            config_content += f"  IdentityFile {key_path}\n"

        # Write config
        config_path.write_text(config_content)
