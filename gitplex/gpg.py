"""GPG key management module for GitPlex."""

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

from .exceptions import GitplexError
from .ui_common import print_error, print_info, print_success, print_warning

@dataclass
class GPGKey:
    """Represents a GPG key."""
    key_id: str
    email: str
    name: str
    comment: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert GPG key to dictionary for serialization."""
        return {
            "key_id": self.key_id,
            "email": self.email,
            "name": self.name,
            "comment": self.comment,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GPGKey":
        """Create GPG key from dictionary."""
        return cls(
            key_id=data["key_id"],
            email=data["email"],
            name=data["name"],
            comment=data.get("comment"),
        )

def check_gpg_installed() -> bool:
    """Check if GPG is installed."""
    try:
        subprocess.run(
            ["gpg", "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def list_gpg_keys() -> List[GPGKey]:
    """List existing GPG keys."""
    try:
        result = subprocess.run(
            ["gpg", "--list-secret-keys", "--keyid-format", "LONG"],
            check=True,
            capture_output=True,
            text=True,
        )
        
        keys = []
        current_key = None
        
        for line in result.stdout.splitlines():
            if line.startswith("sec"):
                # Extract key ID
                key_id = line.split("/")[1].split(" ")[0]
                current_key = {"key_id": key_id}
            elif line.strip().startswith("uid") and current_key:
                # Extract name and email
                uid = line.strip()[4:].strip()
                if "(" in uid and ")" in uid:
                    name, rest = uid.split("(", 1)
                    comment, email = rest.rsplit(")", 1)
                elif "<" in uid and ">" in uid:
                    name, email = uid.rsplit("<", 1)
                    email = email.rstrip(">")
                    comment = None
                else:
                    continue
                
                current_key["name"] = name.strip()
                current_key["email"] = email.strip()
                current_key["comment"] = comment.strip() if comment else None
                
                keys.append(GPGKey(**current_key))
                current_key = None
        
        return keys
    except subprocess.CalledProcessError as e:
        raise GitplexError(f"Failed to list GPG keys: {e.stderr}") from e

def generate_gpg_key(name: str, email: str, comment: Optional[str] = None) -> GPGKey:
    """Generate a new GPG key pair."""
    if not check_gpg_installed():
        raise GitplexError(
            "GPG is not installed",
            details="Please install GPG to enable commit signing"
        )
    
    # Create batch input for key generation
    batch_input = f"""Key-Type: RSA
Key-Length: 4096
Name-Real: {name}
Name-Email: {email}
"""
    
    if comment:
        batch_input += f"Name-Comment: {comment}\n"
    
    batch_input += """Expire-Date: 0
%no-protection
%commit
"""
    
    try:
        # Generate key
        process = subprocess.Popen(
            ["gpg", "--batch", "--gen-key"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate(batch_input)
        
        if process.returncode != 0:
            raise GitplexError(f"Failed to generate GPG key: {stderr}")
        
        # Get the key ID
        keys = list_gpg_keys()
        for key in keys:
            if key.email == email and key.name == name:
                print_success("Generated GPG key pair")
                return key
        
        raise GitplexError("Failed to find generated GPG key")
    except subprocess.CalledProcessError as e:
        raise GitplexError(f"Failed to generate GPG key: {e.stderr}") from e

def export_public_key(key_id: str) -> str:
    """Export public GPG key."""
    try:
        result = subprocess.run(
            ["gpg", "--armor", "--export", key_id],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise GitplexError(f"Failed to export GPG key: {e.stderr}") from e

def setup_gpg_key(name: str, email: str, comment: Optional[str] = None) -> GPGKey:
    """Set up GPG key for signing commits."""
    # Check for existing keys
    keys = list_gpg_keys()
    for key in keys:
        if key.email == email:
            print_warning(f"GPG key for {email} already exists, using existing key")
            return key
    
    # Generate new key
    key = generate_gpg_key(name, email, comment)
    
    # Export public key
    public_key = export_public_key(key.key_id)
    print_info("\nYour GPG public key (add this to your GitHub account):")
    print_info(public_key)
    
    # Copy to clipboard
    try:
        process = subprocess.Popen(
            ["pbcopy" if os.uname().sysname == "Darwin" else "xclip"],
            stdin=subprocess.PIPE,
        )
        process.communicate(public_key.encode())
        print_success("Public key copied to clipboard")
    except:
        print_warning("Could not copy to clipboard, please copy manually")
    
    return key 