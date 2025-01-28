"""Credentials management module."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict

from .exceptions import GitplexError
from .ssh import SSHKey
from .gpg import GPGKey


@dataclass
class Credentials:
    """Git credentials that can be shared between profiles."""
    email: str
    username: str
    ssh_key: Optional[SSHKey] = None
    gpg_key: Optional[GPGKey] = None

    def to_dict(self) -> dict:
        """Convert credentials to dictionary for serialization."""
        return {
            "email": self.email,
            "username": self.username,
            "ssh_key": self.ssh_key.to_dict() if self.ssh_key else None,
            "gpg_key": self.gpg_key.to_dict() if self.gpg_key else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Credentials":
        """Create credentials from dictionary."""
        ssh_data = data.get("ssh_key")
        gpg_data = data.get("gpg_key")
        
        ssh_key = SSHKey.from_dict(ssh_data) if ssh_data else None
        gpg_key = GPGKey.from_dict(gpg_data) if gpg_data else None
        
        return cls(
            email=data["email"],
            username=data["username"],
            ssh_key=ssh_key,
            gpg_key=gpg_key,
        )


class CredentialsManager:
    """Manages Git credentials that can be shared between profiles."""

    def __init__(self) -> None:
        """Initialize credentials manager."""
        self.credentials: Dict[str, Credentials] = {}

    def add_credentials(self, credentials: Credentials) -> None:
        """Add credentials to the manager.
        
        Args:
            credentials: The credentials to add
        """
        key = f"{credentials.email}_{credentials.username}"
        self.credentials[key] = credentials

    def find_matching_credentials(self, email: str, username: str) -> Optional[Credentials]:
        """Find existing credentials that match the given email and username.
        
        Args:
            email: Git email
            username: Git username
            
        Returns:
            Matching credentials if found, None otherwise
        """
        key = f"{email}_{username}"
        return self.credentials.get(key)

    def remove_credentials(self, email: str, username: str) -> None:
        """Remove credentials from the manager.
        
        Args:
            email: Git email
            username: Git username
        """
        key = f"{email}_{username}"
        if key in self.credentials:
            del self.credentials[key] 