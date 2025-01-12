"""SSH key management functionality."""

import os
from pathlib import Path
from typing import Optional, Tuple

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa


def generate_ssh_key_pair(
    key_path: Path,
    passphrase: Optional[str] = None,
    use_ed25519: bool = True,
) -> Tuple[Path, Path]:
    """Generate a new SSH key pair.
    
    Args:
        key_path: Path where to save the key pair
        passphrase: Optional passphrase to encrypt the private key
        use_ed25519: Whether to use Ed25519 (True) or RSA (False)
        
    Returns:
        Tuple of (private_key_path, public_key_path)
    """
    # Generate key
    if use_ed25519:
        private_key = ed25519.Ed25519PrivateKey.generate()
    else:
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
        )

    # Prepare encryption algorithm if passphrase is provided
    encryption_algorithm = (
        serialization.BestAvailableEncryption(passphrase.encode())
        if passphrase
        else serialization.NoEncryption()
    )

    # Save private key
    private_key_path = key_path
    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    private_key_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=encryption_algorithm,
    )
    private_key_path.write_bytes(private_key_bytes)
    os.chmod(private_key_path, 0o600)

    # Save public key
    public_key = private_key.public_key()
    public_key_path = key_path.with_suffix(".pub")
    public_key_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    )
    public_key_path.write_bytes(public_key_bytes + b"\n")
    os.chmod(public_key_path, 0o644)

    return private_key_path, public_key_path


def update_ssh_config(
    config_path: Path,
    host: str,
    identity_file: Path,
    user: str,
    hostname: Optional[str] = None,
) -> None:
    """Update SSH config with a new host entry.
    
    Args:
        config_path: Path to SSH config file
        host: Host pattern to match
        identity_file: Path to SSH private key
        user: Username for the connection
        hostname: Optional real hostname (if different from host)
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Read existing config
    config_content = config_path.read_text() if config_path.exists() else ""
    
    # Prepare new host entry
    host_entry = f"\nHost {host}\n"
    host_entry += f"    IdentityFile {identity_file}\n"
    host_entry += f"    User {user}\n"
    if hostname:
        host_entry += f"    HostName {hostname}\n"
    
    # Check if host already exists
    if f"Host {host}" in config_content:
        # TODO: Update existing host entry
        pass
    else:
        # Append new host entry
        config_content += host_entry
    
    # Write updated config
    config_path.write_text(config_content)
    os.chmod(config_path, 0o600) 