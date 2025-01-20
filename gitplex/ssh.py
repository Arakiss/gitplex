"""SSH key management module for GitPlex."""

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .exceptions import GitplexError
from .ui_common import print_error, print_info, print_success, print_warning

SSHKeyType = Literal["ed25519", "rsa"]
DEFAULT_KEY_TYPE = "ed25519"
DEFAULT_RSA_BITS = 4096
SSH_DIR = Path.home() / ".ssh"

@dataclass
class SSHKey:
    """Represents an SSH key pair."""
    private_key: Path
    public_key: Path
    key_type: SSHKeyType
    comment: str
    provider: str
    profile_name: str

    @property
    def name(self) -> str:
        """Get the base name of the key."""
        return self.private_key.stem

    def exists(self) -> bool:
        """Check if both private and public keys exist."""
        return self.private_key.exists() and self.public_key.exists()
    
    def get_public_key(self) -> str:
        """Get the contents of the public key file."""
        if not self.public_key.exists():
            raise GitplexError(f"Public key not found: {self.public_key}")
        return self.public_key.read_text().strip()

def copy_to_clipboard(text: str) -> None:
    """Copy text to clipboard."""
    try:
        # Determine OS and use appropriate command
        if os.uname().sysname == "Darwin":  # macOS
            cmd = ["pbcopy"]
        elif os.uname().sysname == "Linux":
            cmd = ["xclip", "-selection", "clipboard"]
        else:  # Windows
            cmd = ["clip"]
        
        # Execute copy command
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        process.communicate(text.encode())
        print_success("Public key copied to clipboard")
    except Exception as e:
        print_warning(f"Could not copy to clipboard: {e}")
        print_info("Please copy the key manually")

def setup_ssh_directory() -> None:
    """Set up SSH directory with correct permissions."""
    try:
        # Create .ssh directory if it doesn't exist
        SSH_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        
        # Ensure correct permissions
        SSH_DIR.chmod(0o700)
        
        print_success("SSH directory setup complete")
    except OSError as e:
        raise GitplexError(f"Failed to set up SSH directory: {e}") from e

def generate_ssh_key(
    key_type: SSHKeyType,
    key_path: Path,
    comment: str,
    bits: int | None = None,
) -> None:
    """Generate a new SSH key pair."""
    try:
        # Build command
        cmd = ["ssh-keygen", "-t", key_type, "-f", str(key_path), "-C", comment, "-N", ""]
        if key_type == "rsa" and bits:
            cmd.extend(["-b", str(bits)])
        
        # Run command
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        # Set correct permissions
        key_path.chmod(0o600)
        key_path.with_suffix(".pub").chmod(0o644)
        
        print_success(f"Generated {key_type.upper()} key pair")
    except subprocess.CalledProcessError as e:
        raise GitplexError(f"Failed to generate SSH key: {e.stderr}") from e
    except OSError as e:
        raise GitplexError(f"Failed to set key permissions: {e}") from e

def add_to_ssh_config(key: SSHKey) -> None:
    """Add SSH key to SSH config file."""
    config_path = SSH_DIR / "config"
    
    try:
        # Create config file if it doesn't exist
        if not config_path.exists():
            config_path.touch(mode=0o600)
        
        # Read existing config
        config = config_path.read_text()
        
        # Build host config
        host_config = f"""
# GitPlex: {key.profile_name} ({key.provider})
Host {key.provider}
    HostName {get_provider_hostname(key.provider)}
    User git
    IdentityFile {key.private_key}
    IdentitiesOnly yes

"""
        
        # Check if host already exists
        if f"Host {key.provider}" in config:
            print_warning(f"SSH config for {key.provider} already exists, updating...")
            # Remove existing config
            lines = config.splitlines()
            new_lines = []
            skip = False
            for line in lines:
                if f"Host {key.provider}" in line:
                    skip = True
                elif skip and not line.strip():
                    skip = False
                elif not skip:
                    new_lines.append(line)
            config = "\n".join(new_lines)
        
        # Add new config
        config = config.rstrip() + "\n" + host_config
        
        # Write config
        config_path.write_text(config)
        config_path.chmod(0o600)
        
        print_success("Updated SSH config")
    except OSError as e:
        raise GitplexError(f"Failed to update SSH config: {e}") from e

def add_to_ssh_agent(key: SSHKey) -> None:
    """Add SSH key to SSH agent."""
    try:
        # Start ssh-agent if not running
        if not os.environ.get("SSH_AUTH_SOCK"):
            result = subprocess.run(
                ["ssh-agent", "-s"],
                capture_output=True,
                text=True,
                check=True,
            )
            for line in result.stdout.splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    value = value.rstrip(";").strip('"')
                    os.environ[key] = value
        
        # Add key to agent
        subprocess.run(
            ["ssh-add", str(key.private_key)],
            check=True,
            capture_output=True,
            text=True,
        )
        
        print_success("Added key to SSH agent")
    except subprocess.CalledProcessError as e:
        raise GitplexError(f"Failed to add key to SSH agent: {e.stderr}") from e

def test_ssh_connection(provider: str) -> bool:
    """Test SSH connection to provider."""
    try:
        hostname = get_provider_hostname(provider)
        subprocess.run(
            ["ssh", "-T", f"git@{hostname}"],
            check=True,
            capture_output=True,
            text=True,
        )
        print_success(f"SSH connection to {provider} successful")
        return True
    except subprocess.CalledProcessError as e:
        # Some providers return non-zero even on success
        if "successfully authenticated" in e.stderr.lower():
            print_success(f"SSH connection to {provider} successful")
            return True
        print_error(f"SSH connection to {provider} failed: {e.stderr}")
        return False

def get_provider_hostname(provider: str) -> str:
    """Get hostname for Git provider."""
    hostnames = {
        "github": "github.com",
        "gitlab": "gitlab.com",
        "bitbucket": "bitbucket.org",
        "azure": "dev.azure.com",
    }
    return hostnames.get(provider, provider)

def setup_ssh_keys(
    profile_name: str,
    provider: str,
    email: str,
    key_type: SSHKeyType = DEFAULT_KEY_TYPE,
) -> SSHKey:
    """Set up SSH keys for a profile."""
    # Set up SSH directory
    setup_ssh_directory()
    
    # Generate key paths
    key_name = f"id_{profile_name}_{key_type}"
    private_key = SSH_DIR / key_name
    public_key = private_key.with_suffix(".pub")
    
    # Create key object
    key = SSHKey(
        private_key=private_key,
        public_key=public_key,
        key_type=key_type,
        comment=f"{email} ({profile_name})",
        provider=provider,
        profile_name=profile_name,
    )
    
    # Generate key pair
    if not key.exists():
        generate_ssh_key(
            key_type=key_type,
            key_path=private_key,
            comment=key.comment,
            bits=DEFAULT_RSA_BITS if key_type == "rsa" else None,
        )
    else:
        print_warning(f"SSH key {key_name} already exists, skipping generation")
    
    # Add to SSH config
    add_to_ssh_config(key)
    
    # Add to SSH agent
    add_to_ssh_agent(key)
    
    # Display public key and copy to clipboard
    public_key_content = key.get_public_key()
    print_info("\nYour public SSH key (add this to your GitHub account):")
    print_info(public_key_content)
    copy_to_clipboard(public_key_content)
    print_info("\nAdd this key to your GitHub account at: https://github.com/settings/keys")
    
    # Test connection
    test_ssh_connection(provider)
    
    return key
