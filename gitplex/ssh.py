"""SSH key management module for GitPlex."""

import os
import subprocess
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Any, Union

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

    def to_dict(self) -> dict[str, Any]:
        """Convert SSH key to dictionary for serialization."""
        return {
            "private_key": str(self.private_key),
            "public_key": str(self.public_key),
            "key_type": self.key_type,
            "comment": self.comment,
            "provider": self.provider,
            "profile_name": self.profile_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SSHKey":
        """Create SSH key from dictionary."""
        return cls(
            private_key=Path(data["private_key"]),
            public_key=Path(data["public_key"]),
            key_type=data["key_type"],
            comment=data["comment"],
            provider=data["provider"],
            profile_name=data["profile_name"],
        )

def copy_to_clipboard(text: str) -> None:
    """Copy text to clipboard."""
    try:
        import platform
        system = platform.system().lower()
        
        if system == "darwin":  # macOS
            cmd = ["pbcopy"]
        elif system == "linux":
            # Try different clipboard commands available on Linux
            if shutil.which("xclip"):
                cmd = ["xclip", "-selection", "clipboard"]
            elif shutil.which("xsel"):
                cmd = ["xsel", "--clipboard", "--input"]
            elif shutil.which("wl-copy"):
                cmd = ["wl-copy"]
            else:
                raise FileNotFoundError("No clipboard command found. Please install xclip, xsel, or wl-copy")
        elif system == "windows":
            cmd = ["clip"]
        else:
            raise OSError(f"Unsupported operating system: {system}")
        
        # Execute copy command
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        process.communicate(text.encode())
        print_success("Public key copied to clipboard")
    except FileNotFoundError as e:
        print_warning(f"Could not copy to clipboard: {e}")
        print_info("To copy the key on Linux, install one of these packages:")
        print_info("  sudo apt install xclip        # Debian/Ubuntu")
        print_info("  sudo dnf install xclip        # Fedora")
        print_info("  sudo pacman -S xclip         # Arch Linux")
        print_info("Or copy the key manually from above")
    except Exception as e:
        print_warning(f"Could not copy to clipboard: {e}")
        print_info("Please copy the key manually from above")

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

def get_provider_hostname(provider: str) -> str:
    """Get hostname for Git provider."""
    hostnames = {
        "github": "github.com",
        "gitlab": "gitlab.com",
        "bitbucket": "bitbucket.org",
        "azure": "ssh.dev.azure.com",  # Azure DevOps requires ssh.dev.azure.com
    }
    return hostnames.get(provider.lower(), provider)

def add_to_ssh_agent(key: Union[str, SSHKey]) -> None:
    """Add SSH key to SSH agent.
    
    Args:
        key: Either a path to the private key as string or an SSHKey object
    """
    try:
        # Get the key path, whether it's a string or SSHKey object
        key_path = str(key.private_key) if hasattr(key, 'private_key') else str(key)
        
        # Detect OS
        import platform
        system = platform.system().lower()
        
        # First try to add the key directly
        try:
            subprocess.run(
                ["ssh-add", key_path],
                check=True,
                capture_output=True,
                text=True,
            )
            print_success(f"Added key to SSH agent: {key_path}")
            return
        except subprocess.CalledProcessError:
            pass  # Continue with agent initialization
        
        # OS-specific agent initialization
        if system == "darwin":  # macOS
            agent_cmd = ["ssh-agent", "-s"]
        else:  # Linux and others
            agent_cmd = ["ssh-agent"]
            
        # Try to start the agent and get its environment variables
        agent_output = subprocess.check_output(
            agent_cmd,
            text=True
        )
        
        # Parse SSH agent environment variables
        env_vars = {}
        for line in agent_output.splitlines():
            if "=" in line:
                name, value = line.split(";", 1)[0].split("=", 1)
                env_vars[name.strip()] = value.strip()
        
        # Update current environment with SSH agent variables
        os.environ.update(env_vars)
        
        # Now try to add the key again with the new environment
        try:
            subprocess.run(
                ["ssh-add", key_path],
                check=True,
                env=os.environ,
                capture_output=True,
                text=True,
            )
            print_success(f"Added key to SSH agent: {key_path}")
            
            # Print OS-specific instructions for persisting the SSH agent
            if system == "darwin":
                print_info("\nTo persist the SSH agent on macOS, add this to your ~/.zshrc:")
                print_info('if [ -z "$SSH_AUTH_SOCK" ]; then')
                print_info('   eval "$(ssh-agent -s)" > /dev/null')
                print_info('fi')
            else:  # Linux
                print_info("\nTo persist the SSH agent on Linux, add this to your ~/.bashrc:")
                print_info('if [ -z "$SSH_AUTH_SOCK" ]; then')
                print_info('   eval "$(ssh-agent)" > /dev/null')
                print_info('fi')
            
        except subprocess.CalledProcessError as e:
            raise GitplexError(f"Failed to add key to SSH agent: {e.stderr}")
            
    except Exception as e:
        raise GitplexError(f"Failed to add key to SSH agent: {str(e)}")

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

def add_to_ssh_config(key: SSHKey) -> None:
    """Add SSH key to SSH config file."""
    config_path = SSH_DIR / "config"
    
    try:
        # Create config file if it doesn't exist
        if not config_path.exists():
            config_path.touch(mode=0o600)
        
        # Read existing config
        config = config_path.read_text()
        
        # Get provider hostname
        hostname = get_provider_hostname(key.provider)
        
        # Build host config with Azure-specific settings if needed
        if key.provider == "azure":
            host_config = f"""
# GitPlex: {key.profile_name} ({key.provider})
Host {hostname}
    HostName {hostname}
    User git
    IdentityFile {key.private_key}
    IdentitiesOnly yes
    HostKeyAlgorithms +ssh-rsa
    PubkeyAcceptedAlgorithms +ssh-rsa

"""
        else:
            host_config = f"""
# GitPlex: {key.profile_name} ({key.provider})
Host {hostname}
    HostName {hostname}
    User git
    IdentityFile {key.private_key}
    IdentitiesOnly yes

"""
        
        # Check if host already exists
        if f"Host {hostname}" in config:
            print_warning(f"SSH config for {hostname} already exists, updating...")
            # Remove existing config
            lines = config.splitlines()
            new_lines = []
            skip = False
            for line in lines:
                if f"Host {hostname}" in line:
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

def setup_ssh_keys(
    profile_name: str,
    provider: str,
    email: str,
    force: bool = False,
) -> SSHKey:
    """Set up SSH keys for a profile.
    
    Args:
        profile_name: Profile name
        provider: Git provider name
        email: Git email
        force: Force key generation even if key exists
        
    Returns:
        SSHKey object
    """
    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(mode=0o700, exist_ok=True)
    
    # Define key type and name based on provider
    provider = provider.lower()
    if provider == "azure":
        key_type = "rsa"
        key_name = f"id_rsa_{profile_name}_{provider}"
    else:
        key_type = "ed25519"
        key_name = f"id_ed25519_{profile_name}_{provider}"
    
    private_key = ssh_dir / key_name
    public_key = ssh_dir / f"{key_name}.pub"
    
    # Check for existing key
    if private_key.exists() and not force:
        print_warning(f"SSH key {key_name} already exists, skipping generation")
        # Create SSHKey object from existing key
        key = SSHKey(
            private_key=private_key,
            public_key=public_key,
            key_type=key_type,
            comment=email,
            provider=provider,
            profile_name=profile_name,
        )
    else:
        # Generate new key pair
        try:
            cmd = [
                "ssh-keygen",
                "-t", key_type,
                "-C", email,
                "-f", str(private_key),
                "-N", "",  # Empty passphrase
            ]
            
            # Add RSA specific options for Azure
            if provider == "azure":
                cmd.extend(["-b", str(DEFAULT_RSA_BITS)])
                
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )
            # Create SSHKey object for new key
            key = SSHKey(
                private_key=private_key,
                public_key=public_key,
                key_type=key_type,
                comment=email,
                provider=provider,
                profile_name=profile_name,
            )
            print_success(f"Generated new {key_type.upper()} key pair")
        except subprocess.CalledProcessError as e:
            raise GitplexError(f"Failed to generate SSH key: {e.stderr}") from e
    
    # Set correct permissions
    private_key.chmod(0o600)
    public_key.chmod(0o644)
    
    # Update SSH config
    add_to_ssh_config(key)
    
    # Add to SSH agent
    add_to_ssh_agent(key)
    
    return key
